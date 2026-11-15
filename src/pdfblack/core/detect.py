"""Erkennungspipeline.

Erster Durchlauf: KI (Presidio/NLP) plus deutsche Muster.
Zweiter Durchlauf: die vom Benutzer eingegebenen Werte und eigenen Regexe.
Ueberlappende Treffer werden zusammengefasst, damit jede Stelle nur einmal
geschwaerzt wird.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Callable

from .extract import TextMap, open_document
from .models import Category, Finding
from .rules import Rule, compiled as compiled_rule, rules_for_groups

LOGGER = logging.getLogger(__name__)

AI_SOURCE = "KI (Presidio)"
MANUAL_SOURCE = "Manuell"
REGEX_SOURCE = "Regex"

# Reihenfolge: hoehere Zahl gewinnt bei gleicher Laenge.
PRIORITY_MANUAL = 300
PRIORITY_REGEX = 200
PRIORITY_RULE = 100
PRIORITY_AI = 50

# Woerter, die das NER-Modell gern faelschlich als Person/Ort ausgibt.
_AI_STOPWORDS = frozenset(
    {
        "unser",
        "unsere",
        "unseren",
        "ihr",
        "ihre",
        "ihren",
        "ihrem",
        "sehr",
        "bitte",
        "danke",
        "geehrte",
        "geehrter",
        "freundlichen",
        "gruessen",
        "grüßen",
        "mit",
        "und",
        "oder",
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "zeichen",
        "betreff",
        "datum",
        "seite",
        "iban",
        "telefon",
        "e-mail",
        "email",
        "personalnummer",
        "geburtsdatum",
        "anschrift",
        "adresse",
    }
)

_ENTITY_CATEGORY: dict[str, Category] = {
    "PERSON": Category.PERSON,
    "LOCATION": Category.POSTAL,
    "EMAIL_ADDRESS": Category.CONTACT,
    "PHONE_NUMBER": Category.CONTACT,
    "IBAN_CODE": Category.BANK,
    "CREDIT_CARD": Category.BANK,
    "DATE_TIME": Category.DATE,
}

ProgressFn = Callable[[int, int, str], bool | None]


@dataclass(frozen=True)
class ManualTerm:
    """Ein vom Benutzer eingegebener Wert fuer den zweiten Durchlauf."""

    label: str
    value: str
    category: Category


@dataclass(frozen=True)
class RegexSpec:
    """Ein vom Benutzer eingegebener regul aerer Ausdruck."""

    name: str
    pattern: str


@dataclass
class DetectionOptions:
    use_ai: bool = True
    ai_entities: tuple[str, ...] = ("PERSON",)
    rule_groups: tuple[str, ...] = ("address", "id", "contact")
    threshold: float = 0.45
    manual_terms: tuple[ManualTerm, ...] = ()
    regexes: tuple[RegexSpec, ...] = ()
    regex_ignore_case: bool = True

    def is_empty(self) -> bool:
        return not (
            (self.use_ai and self.ai_entities)
            or self.rule_groups
            or self.manual_terms
            or self.regexes
        )


@dataclass
class DetectionResult:
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Candidate:
    page: int
    start: int
    end: int
    text: str
    category: Category
    source: str
    entity: str
    score: float
    priority: int


# --------------------------------------------------------------------------
# Presidio
# --------------------------------------------------------------------------

_ENGINE_LOCK = threading.Lock()
_ENGINE: object | None = None
_ENGINE_ERROR: str | None = None
_ENGINE_TRIED = False


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model = os.environ.get("PDFBLACK_SPACY_MODEL", "de_core_news_md")
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": model}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
    # Wichtig: Die Registry muss dieselbe Sprache kennen wie der Analyzer,
    # sonst verweigert Presidio den Start ("supported languages have to be
    # consistent"). Der deutsche spaCy-NER-Erkenner wird dabei automatisch
    # mitregistriert.
    registry = RecognizerRegistry(supported_languages=["de"])
    registry.load_predefined_recognizers(languages=["de"], nlp_engine=nlp_engine)
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["de"],
        default_score_threshold=0.3,
    )


def get_analyzer():
    """Presidio-Analyzer einmalig aufbauen (threadsicher)."""
    global _ENGINE, _ENGINE_ERROR, _ENGINE_TRIED
    with _ENGINE_LOCK:
        if not _ENGINE_TRIED:
            _ENGINE_TRIED = True
            logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
            logging.getLogger("presidio_analyzer").setLevel(logging.ERROR)
            try:
                _ENGINE = _build_analyzer()
            except Exception as exc:  # pragma: no cover - haengt vom System ab
                _ENGINE_ERROR = f"{type(exc).__name__}: {exc}"
                LOGGER.warning("Presidio nicht verfuegbar: %s", _ENGINE_ERROR)
                _ENGINE = None
        return _ENGINE, _ENGINE_ERROR


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------


def term_pattern(value: str) -> str:
    """Suchmuster fuer einen frei eingegebenen Begriff (Wortgrenzen, Leerraum)."""
    tokens = [re.escape(part) for part in re.split(r"\s+", value.strip()) if part]
    body = r"\s+".join(tokens)
    return rf"(?<!\w){body}(?!\w)"


def compile_regexes(
    specs: tuple[RegexSpec, ...], ignore_case: bool
) -> list[tuple[RegexSpec, re.Pattern[str]]]:
    """Benutzer-Regexe uebersetzen. Wirft ValueError bei ungueltigem Muster."""
    flags = re.UNICODE
    if ignore_case:
        flags |= re.IGNORECASE
    result: list[tuple[RegexSpec, re.Pattern[str]]] = []
    for spec in specs:
        try:
            result.append((spec, re.compile(spec.pattern, flags)))
        except re.error as exc:
            raise ValueError(f"Regex \u201e{spec.name}\u201c ist ungueltig: {exc}") from exc
    return result


def _resolve(candidates: list[_Candidate]) -> list[_Candidate]:
    """Ueberlappungen aufloesen: laengster Treffer gewinnt, dann Prioritaet."""
    per_page: dict[int, list[_Candidate]] = {}
    for candidate in candidates:
        if candidate.end > candidate.start:
            per_page.setdefault(candidate.page, []).append(candidate)

    accepted_all: list[_Candidate] = []
    for items in per_page.values():
        items.sort(key=lambda c: (-(c.end - c.start), -c.priority, c.start))
        taken: list[tuple[int, int]] = []
        for candidate in items:
            if any(candidate.start < end and start < candidate.end for start, end in taken):
                continue
            taken.append((candidate.start, candidate.end))
            accepted_all.append(candidate)

    accepted_all.sort(key=lambda c: (c.page, c.start))
    return accepted_all


def _iter_lines(text: str):
    """Zeilen mit ihrer absoluten Startposition liefern."""
    offset = 0
    for line in text.splitlines():
        yield offset, line
        offset += len(line) + 1


def _ai_text_allowed(entity_text: str) -> bool:
    """Offensichtlichen Unsinn des NER-Modells aussortieren."""
    cleaned = entity_text.strip()
    if len(cleaned) < 2:
        return False
    if not any(char.isalnum() for char in cleaned):
        return False
    if cleaned.lower() in _AI_STOPWORDS:
        return False
    words = cleaned.split()
    if len(words) == 1 and cleaned[0].islower():
        return False
    return True


def _strip_span(text: str, start: int, end: int) -> tuple[int, int]:
    raw = text[start:end]
    lead = len(raw) - len(raw.lstrip())
    trail = len(raw) - len(raw.rstrip())
    return start + lead, max(start + lead, end - trail)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def run_detection(
    path: str,
    options: DetectionOptions,
    password: str | None = None,
    progress: ProgressFn | None = None,
) -> DetectionResult:
    """Alle Treffer einer PDF-Datei ermitteln (ohne zu schwaerzen)."""
    warnings: list[str] = []

    rules: list[Rule] = rules_for_groups(options.rule_groups)

    regexes: list[tuple[RegexSpec, re.Pattern[str]]] = []
    if options.regexes:
        try:
            regexes = compile_regexes(options.regexes, options.regex_ignore_case)
        except ValueError as exc:
            warnings.append(str(exc))

    flags = re.UNICODE | (re.IGNORECASE if options.regex_ignore_case else 0)
    terms: list[tuple[ManualTerm, re.Pattern[str]]] = []
    for term in options.manual_terms:
        value = term.value.strip()
        if not value:
            continue
        terms.append((term, re.compile(term_pattern(value), flags)))

    analyzer = None
    if options.use_ai and options.ai_entities:
        if progress and progress(0, 0, "KI-Modell wird geladen ...") is False:
            return DetectionResult([], warnings)
        analyzer, error = get_analyzer()
        if analyzer is None:
            message = (
                "KI-Erkennung ist nicht verfuegbar (Presidio/spaCy-Modell fehlt). "
                "Es wird nur mit Mustern, manuellen Werten und Regex gesucht."
            )
            if error:
                message += f" Ursache: {error}"
            warnings.append(message)

    doc = open_document(path, password)
    try:
        textmap = TextMap(doc)
        total = doc.page_count
        candidates: list[_Candidate] = []

        for index in range(total):
            if progress and progress(index, total, f"Seite {index + 1} von {total}") is False:
                return DetectionResult([], warnings)

            page_text = textmap.page(index)
            if not page_text.text:
                continue

            # --- zweiter Durchlauf: eigene Regexe -------------------------
            for spec, pattern in regexes:
                for match in pattern.finditer(page_text.text):
                    start, end = match.span()
                    if end <= start:
                        continue
                    candidates.append(
                        _Candidate(
                            page=index,
                            start=start,
                            end=end,
                            text=match.group(0),
                            category=Category.REGEX,
                            source=f"Regex \u00b7 {spec.name}" if spec.name else REGEX_SOURCE,
                            entity="REGEX",
                            score=1.0,
                            priority=PRIORITY_REGEX,
                        )
                    )

            # --- zweiter Durchlauf: manuelle Werte ------------------------
            for term, pattern in terms:
                for match in pattern.finditer(page_text.text):
                    start, end = match.span()
                    if end <= start:
                        continue
                    candidates.append(
                        _Candidate(
                            page=index,
                            start=start,
                            end=end,
                            text=match.group(0),
                            category=term.category,
                            source=f"{MANUAL_SOURCE} \u00b7 {term.label}",
                            entity="MANUAL",
                            score=1.0,
                            priority=PRIORITY_MANUAL,
                        )
                    )

            # --- erster Durchlauf: deutsche Muster ------------------------
            for rule in rules:
                for match in compiled_rule(rule).finditer(page_text.text):
                    try:
                        start, end = match.span(rule.group_index)
                    except IndexError:
                        start, end = match.span()
                    if end <= start:
                        continue
                    candidates.append(
                        _Candidate(
                            page=index,
                            start=start,
                            end=end,
                            text=match.group(rule.group_index),
                            category=rule.category,
                            source=f"Muster \u00b7 {rule.label}",
                            entity=rule.key,
                            score=0.9,
                            priority=PRIORITY_RULE,
                        )
                    )

            # --- erster Durchlauf: KI ------------------------------------
            # Zeilenweise analysieren: Namen in Anreden und Adressbloecken
            # werden so zuverlaessiger erkannt, und Treffer koennen nicht
            # versehentlich ueber den Zeilenumbruch hinauslaufen.
            if analyzer is not None:
                for line_offset, line in _iter_lines(page_text.text):
                    if not line.strip():
                        continue
                    try:
                        results = analyzer.analyze(
                            text=line,
                            language="de",
                            entities=list(options.ai_entities),
                            score_threshold=options.threshold,
                            allow_list=None,
                        )
                    except Exception as exc:  # pragma: no cover
                        warnings.append(f"KI-Analyse auf Seite {index + 1} fehlgeschlagen: {exc}")
                        break
                    for result in results:
                        category = _ENTITY_CATEGORY.get(result.entity_type)
                        if category is None:
                            continue
                        entity_text = line[result.start : result.end]
                        if not _ai_text_allowed(entity_text):
                            continue
                        candidates.append(
                            _Candidate(
                                page=index,
                                start=line_offset + result.start,
                                end=line_offset + result.end,
                                text=entity_text,
                                category=category,
                                source=f"{AI_SOURCE} · {result.entity_type}",
                                entity=result.entity_type,
                                score=float(result.score),
                                priority=PRIORITY_AI,
                            )
                        )

        findings: list[Finding] = []
        uid = 0
        for candidate in _resolve(candidates):
            page_text = textmap.page(candidate.page)
            start, end = _strip_span(page_text.text, candidate.start, candidate.end)
            if end <= start:
                continue
            rects = textmap.rects_for(candidate.page, start, end)
            if not rects:
                continue
            uid += 1
            findings.append(
                Finding(
                    text=page_text.text[start:end],
                    category=candidate.category,
                    page=candidate.page,
                    rects=rects,
                    source=candidate.source,
                    entity=candidate.entity,
                    score=round(candidate.score, 2),
                    enabled=True,
                    uid=uid,
                )
            )
        return DetectionResult(findings, warnings)
    finally:
        doc.close()
