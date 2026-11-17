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
import tempfile
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping

from . import (
    berufe,
    geburtsdatum as geburtsdatum_core,
    lerndatei,
    lernregeln,
    namen,
    plausibel,
    plz,
    strassen,
)
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
        "freundliche",
        "freundlicher",
        "gruessen",
        "grüßen",
        "grüsse",
        "grüße",
        "gruss",
        "gruß",
        "hochachtungsvoll",
        "herr",
        "herrn",
        "damen",
        "herren",
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

# Woerter, die das NER-Modell als Person meldet, im Dokument aber Sachwoerter
# sind: Taetigkeiten und Eigenschaften aus Zeugnissen, Beschriftungen von
# Kontaktbloecken und Bankkuerzel. Aus der Lerndatei gelernt.
_KEIN_NAME = frozenset(
    {
        "urlaub",
        "wesens",
        "kalkulation",
        "wärmeschutz",
        "waermeschutz",
        "nachtragsmanagement",
        "arbeitsanfall",
        "jugendnachwuchs",
        "fassaden",
        "flachdach",
        "schnittstellenkompetenz",
        "schnelles",
        "young",
        "wolf",
        "fi",
        "aik",
        "cross-trade",
        "bachelor",
        "master",
        "professional",
        "tel",
        "telefax",
        "fax",
        "telefon",
        "internet",
        "e-mail",
        "email",
        "ust-idnr",
        "hrb",
        "handelsregister",
        "amtsgericht",
        # Monatsnamen stehen in Daten und Tabellen, sind aber keine Namen.
        "januar",
        "februar",
        "märz",
        "maerz",
        "april",
        "mai",
        "juni",
        "juli",
        "august",
        "september",
        "oktober",
        "november",
        "dezember",
        "jan",
        "jän",
        "febr",
        "feb",
        "mär",
        "mrz",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "okt",
        "nov",
        "dez",
    }
)
# Deutsche Substantivierungen enden so; ein Name nur selten.
_KEIN_NAME_ENDE = (
    "ung",
    "ungen",
    "heit",
    "keiten",
    "keit",
    "schaft",
    "kompetenz",
    "management",
    "schutz",
    "anfall",
    "nachwuchs",
    "arbeiten",
    "faehigkeit",
    "fähigkeit",
    "bereitschaft",
)
# Erst ab dieser Laenge, sonst traefe die Endung auch kurze Namen.
_KEIN_NAME_MINDESTLAENGE = 8
# Bankkuerzel: IBAN-Anfang (DE80) und BIC (BYLADEM1FFB).
_IBAN_ANFANG = re.compile(r"[A-Z]{2}\d{2}")
_BIC = re.compile(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?")
# Spalten aus Vierergruppen: "6510 0000 0270 7002" (IBAN),
# "47 4512 0032 3070 7005" (Handelsregister).
_NUMMERNGRUPPEN = re.compile(r"(?:\d{4}[ \t]+){2,}\d{2,4}")


# Ein einmal erkannter Name wird im ganzen Dokument gesucht - auch dort, wo
# er mitten in einer Adresszeile, einem Briefkopf oder einer Fusszeile steht.
PRIORITY_NAME = 250

_NAME_TITLES = frozenset(
    {
        "herr",
        "herrn",
        "frau",
        "dr",
        "dr.",
        "prof",
        "prof.",
        "dipl",
        "dipl.-ing.",
        "dipl.-kfm.",
        "ing",
        "mag",
        "familie",
        "firma",
    }
)
_NAME_PARTICLES = frozenset(
    {"von", "van", "de", "del", "der", "den", "zu", "zur", "y", "af", "av"}
)
# Nur eindeutige Strassenendungen: "Berg" oder "Feld" koennen auch Namen sein.
_STREET_ENDINGS = (
    "stra\u00dfe",
    "strasse",
    "str",
    "weg",
    "allee",
    "platz",
    "ring",
    "gasse",
    "ufer",
    "damm",
    "chaussee",
    "pfad",
    "zeile",
    "graben",
    "wall",
    "steig",
    "viertel",
    "siedlung",
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
    # Wirkung der Lerndatei auf diesen Durchlauf.
    learned_off: int = 0
    learned_changed: int = 0


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


def _cache_ordner() -> list[Path]:
    """Moegliche Ablageorte fuer den tldextract-Cache, bester zuerst."""
    ordner: list[Path] = []
    lokal = os.environ.get("LOCALAPPDATA")
    if lokal:
        ordner.append(Path(lokal) / "PDFblack" / "tldextract")
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        ordner.append(Path(xdg) / "pdfblack" / "tldextract")
    zuhause = os.environ.get("HOME")
    if zuhause:
        ordner.append(Path(zuhause) / ".cache" / "pdfblack" / "tldextract")
    ordner.append(Path(tempfile.gettempdir()) / "pdfblack-tldextract")
    return ordner


def prepare_tldextract() -> str:
    """Beschreibbaren Cache fuer tldextract setzen.

    Presidio prueft E-Mail-Adressen mit tldextract, und die Bibliothek legt
    ihre Suffix-Liste standardmaessig im eigenen Paketordner ab. In
    ``C:\\Program Files\\PDFblack`` ist das schreibgeschuetzt - dort kam
    ``[WinError 5] Zugriff verweigert`` und die KI-Analyse brach auf jeder
    Seite ab. Deshalb wird ``TLDEXTRACT_CACHE`` vor dem ersten Presidio-Import
    auf einen Ordner im Benutzerprofil gelegt; tldextract liest die Variable
    beim Anlegen des Cache-Objekts.
    """
    vorhanden = os.environ.get("TLDEXTRACT_CACHE")
    if vorhanden:
        return vorhanden
    for kandidat in _cache_ordner():
        try:
            kandidat.mkdir(parents=True, exist_ok=True)
            probe = kandidat / ".schreibprobe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError:
            continue
        os.environ["TLDEXTRACT_CACHE"] = str(kandidat)
        return str(kandidat)
    LOGGER.warning("Kein beschreibbarer Ordner fuer den tldextract-Cache gefunden.")
    return ""


def _build_analyzer():
    # Muss vor dem Import von Presidio laufen (tldextract liest die Variable
    # beim Anlegen seines Cache-Objekts).
    prepare_tldextract()
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
    """Benutzer-Regexe uebersetzen. Wirft ValueError bei ungueltigem Muster.

    ``MULTILINE``, damit ``^`` und ``$`` auf Zeilenanfang und -ende passen:
    der Seitentext besteht aus mehreren Zeilen, und ein Muster wie
    ``^\\d{12}$`` soll eine Nummer finden, die allein in ihrer Zeile steht -
    nicht nur dann, wenn die ganze Seite aus dieser Nummer besteht.
    """
    flags = re.UNICODE | re.MULTILINE
    if ignore_case:
        flags |= re.IGNORECASE
    result: list[tuple[RegexSpec, re.Pattern[str]]] = []
    for spec in specs:
        try:
            result.append((spec, re.compile(spec.pattern, flags)))
        except re.error as exc:
            raise ValueError(f"Regex \u201e{spec.name}\u201c ist ungueltig: {exc}") from exc
    return result


def _nur_geburtsdatum(
    candidates: list[_Candidate], textmap: TextMap | None = None, total: int = 0
) -> list[_Candidate]:
    """Geburtsdatum bestimmen; alle anderen Daten bleiben als Treffer.

    Alle gefundenen Daten werden eingelesen; das aelteste gilt als
    Geburtsdatum, wenn es mindestens 15 Jahre vor dem naechsten Datum liegt.
    Die uebrigen Daten bleiben als Kategorie "Datum" in der Trefferliste und
    lassen sich dort einzeln abwaehlen - nichts verschwindet still, nur weil
    es kein Geburtsdatum ist. Manuell eingegebene Werte bleiben unangetastet.
    Wird das Datum in anderer Schreibweise genannt (1.3.95 / 01. März 1995),
    wird auch das gefunden und mitgeschwaerzt.
    """
    daten: list[tuple[_Candidate, geburtsdatum_core.Angabe]] = []
    uebrige: list[_Candidate] = []
    for candidate in candidates:
        if candidate.category is Category.DATE and candidate.entity != "MANUAL":
            angabe = geburtsdatum_core.als_angabe(candidate.text)
            if angabe is None:
                # Kein lesbares Datum ("05/2013 - 07/2013"): bleibt als
                # Datums-Treffer stehen, taugt nur nicht zur Einordnung.
                uebrige.append(candidate)
                continue
            daten.append((candidate, angabe))
        else:
            uebrige.append(candidate)

    # Ist nur ein vollstaendiges Datum genannt, entscheidet die naechsthoehere
    # Jahreszahl im Dokument ("05/02/1990" und sonst nur "2020").
    vollstaendig = {angabe.datum for _, angabe in daten if angabe.datum is not None}
    jahre: list[int] = []
    if textmap is not None and len(vollstaendig) == 1:
        for index in range(total):
            jahre.extend(geburtsdatum_core.jahreszahlen(textmap.page(index).text))

    ziel = geburtsdatum_core.geburtsdatum([angabe for _, angabe in daten], jahre)
    # Ohne Geburtsdatum bleiben alle Daten normale Datums-Treffer.
    uebrige.extend(candidate for candidate, _ in daten)
    if ziel is None:
        return uebrige
    for candidate, angabe in daten:
        if angabe.datum != ziel:
            continue
        candidate.category = Category.BIRTHDATE
        candidate.source = "Geburtsdatum \u00b7 \u00e4ltestes Datum"
        candidate.entity = "BIRTHDATE"

    # Dasselbe Datum in jeder anderen Schreibweise im ganzen Dokument suchen.
    if textmap is not None:
        for index in range(total):
            seite = textmap.page(index)
            if not seite.text:
                continue
            for start, end in geburtsdatum_core.schreibweisen(seite.text, ziel):
                uebrige.append(
                    _Candidate(
                        page=index,
                        start=start,
                        end=end,
                        text=seite.text[start:end],
                        category=Category.BIRTHDATE,
                        source="Geburtsdatum \u00b7 andere Schreibweise",
                        entity="BIRTHDATE",
                        score=0.9,
                        priority=PRIORITY_RULE,
                    )
                )
    return uebrige


def _rang(candidate: _Candidate) -> int:
    """Das Geburtsdatum geht vor.

    Andere Regeln erwischen daneben laengere Stellen ("Geboren am 01" als
    Hausnummer und Strasse); das Geburtsdatum soll trotzdem stehen bleiben.
    """
    return 0 if candidate.category is Category.BIRTHDATE else 1


def _resolve(candidates: list[_Candidate]) -> list[_Candidate]:
    """Ueberlappungen aufloesen: laengster Treffer gewinnt, dann Prioritaet."""
    per_page: dict[int, list[_Candidate]] = {}
    for candidate in candidates:
        if candidate.end > candidate.start:
            per_page.setdefault(candidate.page, []).append(candidate)

    accepted_all: list[_Candidate] = []
    for items in per_page.values():
        items.sort(
            key=lambda c: (_rang(c), -(c.end - c.start), -c.priority, c.start)
        )
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


def _ist_sachwort(text: str) -> bool:
    """Ist der Text ein Sachwort (oder Bankkuerzel) und kein Name?"""
    cleaned = text.strip(" .,;:!?\"'")
    if not cleaned:
        return True
    if cleaned.lower() in _KEIN_NAME:
        return True
    if _IBAN_ANFANG.fullmatch(cleaned) or _BIC.fullmatch(cleaned):
        return True
    woerter = cleaned.split()
    if len(woerter) > 1:
        return all(_ist_sachwort(wort) for wort in woerter)
    lowered = cleaned.lower().strip("-/")
    if len(lowered) < _KEIN_NAME_MINDESTLAENGE:
        return False
    return lowered.endswith(_KEIN_NAME_ENDE)


def _iban_verlaengern(text: str, start: int, end: int) -> int:
    """Eine am Zeilenumbruch abgeschnittene IBAN ergaenzen.

    In Briefkoepfen steht die IBAN oft in zwei Zeilen ("DE89 3704 0044" /
    "0532 0130 00"). Die Regel liest dann nur die erste Zeile; die restlichen
    Zeichen fehlten im Treffer und die Pruefziffer schlug fehl. Ergaenzt wird
    aus der naechsten Zeile - aber nur, wenn die laengere Nummer eine gueltige
    IBAN ergibt. Sonst bliebe die abgeschnittene Nummer stehen.
    """
    rest = text[end:]
    if re.match(r"[ \t]*\n[ \t]*[A-Z0-9]", rest, re.IGNORECASE) is None:
        return end
    zeilenende = rest.find("\n", rest.index("\n") + 1)
    zeile = rest if zeilenende < 0 else rest[:zeilenende]
    for treffer in re.finditer(r"[A-Z0-9]{1,4}", zeile, re.IGNORECASE):
        kandidat = text[start : end + treffer.end()]
        if len(re.sub(r"\s", "", kandidat)) > 34:
            break
        if plausibel.iban_gueltig(kandidat) is True:
            return end + treffer.end()
    return end


def _in_nummernspalte(text: str, start: int, end: int) -> bool:
    """Steht der Treffer in einer Spalte aus Vierergruppen?

    IBANs und Handelsregisternummern stehen in Vierergruppen; die Telefonregel
    liest daraus sonst einzelne Gruppen ("0270", "0032") als Nummer.
    """
    zeilen_anfang = text.rfind("\n", 0, start) + 1
    zeilen_ende = text.find("\n", end)
    if zeilen_ende < 0:
        zeilen_ende = len(text)
    zeile = text[zeilen_anfang:zeilen_ende]
    von = start - zeilen_anfang
    bis = end - zeilen_anfang
    return any(
        gruppe.start() <= von and bis <= gruppe.end()
        for gruppe in _NUMMERNGRUPPEN.finditer(zeile)
    )


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
    # Bestehen alle Woerter aus Floskeln ("Freundliche Gruesse"), ist es kein
    # Name und kein Ort.
    if all(word.strip(".,;:!?").lower() in _AI_STOPWORDS for word in words):
        return False
    if len(words) == 1 and cleaned[0].islower():
        return False
    return True


# Jahreszahlen, die das Sprachmodell als Ort meldet: "2026", "10/2026",
# "2025 - 2026", "10/2025 - 05/2026". Sie gehoeren nicht zu PLZ / Ort.
_AI_YEAR_ONLY = re.compile(
    r"(?<![\d/.])(?:\d{1,2}\s*[./]\s*)?(?:19|20)\d{2}(?![\d/])"
    r"(?:\s*(?:-|–|—|bis)\s*"
    r"(?:(?:\d{1,2}\s*[./]\s*)?(?:19|20)\d{2}|heute|jetzt|aktuell|laufend))?"
)


def _ai_location_is_date(entity_text: str) -> bool:
    """Besteht ein als Ort gemeldeter KI-Treffer nur aus einem Datum?

    Das deutsche spaCy-Modell labelt allein stehende Datumsangaben in
    Kopfzeilen regelmaessig als LOC ("20.10.2026"); Presidio macht daraus
    LOCATION und die Anzeige daraus "PLZ / Ort". Datumsangaben gehoeren zur
    Datumsregel, nicht zu den Postleitzahlen.
    """
    cleaned = entity_text.strip()
    stellen: list[tuple[int, int] | None] = [
        geburtsdatum_core.datumsspanne(cleaned)
    ]
    treffer = _AI_YEAR_ONLY.search(cleaned)
    if treffer is not None:
        stellen.append(treffer.span())
    for spanne in stellen:
        if spanne is None:
            continue
        rest = cleaned[: spanne[0]] + cleaned[spanne[1] :]
        if not any(char.isalpha() for char in rest):
            return True
    return False


_AI_HAS_DIGIT = re.compile(r"\d")


# Beschriftungen, hinter denen eine Nummer steht - das ist ein Ort, aber
# eine Registernummer, ein Kuerzel oder eine Kontaktangabe ("HRB 10710").
_KEINE_ORT_LABELS = frozenset(
    {
        "hrb",
        "hra",
        "prh",
        "bic",
        "iban",
        "uid",
        "ust",
        "ust-idnr",
        "steuer",
        "steuernr",
        "steuer-nr",
        "handelsregister",
        "amtsgericht",
        "tel",
        "tel.",
        "telefon",
        "telefax",
        "fax",
        "e-mail",
        "email",
        "internet",
        "www",
        "geschäftsführer",
        "geschaeftsfuehrer",
    }
)


def _ai_location_is_place(entity_text: str) -> bool:
    """Ist der als Ort gemeldete Text wirklich eine Ortschaft?

    Das Sprachmodell labelt auch Woerter als Ort, die keine sind
    ("Fachmessen" in einem Lebenslauf). Entscheidend ist die amtliche
    Ortschaftenliste: steht der Name dort nicht, ist es kein Ort. Treffer mit
    Zahlen (PLZ, Hausnummer) bleiben den Regeln ueberlassen.
    """
    # "(08142)" ist eine Vorwahl in Klammern, kein Ort.
    if re.fullmatch(r"\(\s*\d{3,6}\s*\)", entity_text.strip()):
        return False
    # "HRB 10710" und "BIC BYLADEM1FFB" sind Nummern, kein Ort.
    kopf = entity_text.strip().split()
    if kopf and kopf[0].strip(".,;:").lower() in _KEINE_ORT_LABELS:
        return False
    if _AI_HAS_DIGIT.search(entity_text):
        return True
    return plz.ist_ort(entity_text)


def looks_like_street(token: str) -> bool:
    lowered = token.lower()
    return any(lowered.endswith(ending) for ending in _STREET_ENDINGS)


def name_tokens(text: str) -> set[str]:
    """Einzelne Namensbestandteile aus einem erkannten oder eingegebenen Namen."""
    tokens: set[str] = set()
    # Ein Strassenname aus dem amtlichen Verzeichnis ist kein Personenname
    # ("Rue du Rhône"). Steht der Ausdruck zugleich im Namensverzeichnis
    # ("Steinberg"), gilt der Name.
    if strassen.ist_strasse(text) and not namen.ist_name(text):
        return tokens
    for raw in re.split(r"[\s,;:/()\[\]]+", text):
        token = raw.strip(".,;:!?\"'")
        if len(token) < 3:
            continue
        if not token[0].isupper():
            continue
        lowered = token.lower()
        if lowered in _AI_STOPWORDS or lowered in _NAME_TITLES:
            continue
        if lowered in _NAME_PARTICLES:
            continue
        # Endet ein Wort wie eine Strasse, ist es meist keine Person. Ein
        # Nachname aus dem Verzeichnis ("Steinberg") bleibt aber einer.
        if looks_like_street(token) and not namen.ist_name(token):
            continue
        if not any(char.isalpha() for char in token):
            continue
        # "Urlaub" und "Kalkulation" sind Sachwoerter, keine Namen.
        if _ist_sachwort(token):
            continue
        # "Dachdecker" ist ein Beruf, kein Nachname - sonst wuerde das Wort
        # im ganzen Dokument geschwaerzt.
        if berufe.ist_berufswort(lowered):
            continue
        tokens.add(token)
    return tokens


_WORT = re.compile(r"[^\W\d_][\w'\u2019-]*", re.UNICODE)


def _ein_schritt_entfernt(a: str, b: str) -> bool:
    """Unterscheiden sich zwei Woerter um genau einen Buchstaben?"""
    if a.casefold() == b.casefold() or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x.casefold() != y.casefold()) == 1
    kurz, lang = (a, b) if len(a) < len(b) else (b, a)
    i = j = 0
    fehler = 0
    while i < len(kurz) and j < len(lang):
        if kurz[i].casefold() == lang[j].casefold():
            i += 1
            j += 1
            continue
        fehler += 1
        j += 1
        if fehler > 1:
            return False
    return True


def _ist_eigenstaendiger_begriff(wort: str, kategorie: Category) -> bool:
    """Steht das Wort selbst fuer einen eigenen Begriff dieser Art?

    "Mueller" und "Moeller" sind beide Nachnamen, "Rosenweg" und "Rosenwerg"
    nicht dasselbe. Solche Woerter duerfen nicht als Lesefehler des anderen
    gelten.
    """
    if kategorie is Category.PERSON:
        return (
            namen.ist_name(wort)
            or strassen.ist_strasse(wort)
            or berufe.ist_berufswort(wort)
        )
    if kategorie is Category.ADDRESS:
        return strassen.ist_strasse(wort) or namen.ist_name(wort)
    if kategorie is Category.POSTAL:
        return (
            plz.ist_ort(wort)
            or strassen.ist_strasse(wort)
            or namen.ist_name(wort)
        )
    return False


def _vorname_lesefehler(
    begriff: str, wort: str, kategorie: Category, anzahl: int, zahl: int
) -> bool:
    """Schlaegt ein sehr haeufiger Vorname eine gueltige Vornamen-Schreibweise?

    Steht "Joana" mindestens zehnmal im Dokument und "Joanna" genau einmal,
    ist das ein Lesefehler - obwohl "Joanna" selbst ein Vorname ist. Nur fuer
    Vornamen und nur bei eindeutiger Mehrheit; Strassen- und Berufswoerter
    bleiben eigenstaendig.
    """
    if kategorie is not Category.PERSON or anzahl < 10 or zahl != 1:
        return False
    if not (namen.ist_vorname(begriff) and namen.ist_vorname(wort)):
        return False
    return not (strassen.ist_strasse(wort) or berufe.ist_berufswort(wort))


def schreibvarianten(
    page_texts: Iterable[str], begriffe: Mapping[str, Category]
) -> dict[str, Category]:
    """Seltene Schreibweisen bereits erkannter Begriffe in diesem Dokument.

    Ein Name, eine Strasse oder ein Ort steht in einem Zeugnis mehrfach. Wird
    er an einer Stelle um einen Buchstaben falsch gelesen ("Witler" neben
    10-mal "Wittler"), bliebe genau diese Stelle ungeschwaerzt. Deshalb werden
    die Woerter des Dokuments gezaehlt: Eine Schreibweise mit einem Buchstaben
    Abstand und hoechstens einem Drittel der Treffer gilt als Lesefehler
    desselben Begriffs.

    Zurueck kommt die Variante mit ihrer Kategorie. Mehrwortige Begriffe
    ("Rue du Lac") werden nicht gezaehlt.
    """
    haeufigkeit: Counter[str] = Counter()
    formen: dict[str, str] = {}
    for text in page_texts:
        if not text:
            continue
        for treffer in _WORT.finditer(text):
            wort = treffer.group(0)
            schluessel = wort.casefold()
            haeufigkeit[schluessel] += 1
            formen.setdefault(schluessel, wort)

    varianten: dict[str, Category] = {}
    for begriff, kategorie in begriffe.items():
        if " " in begriff:
            continue
        anzahl = haeufigkeit.get(begriff.casefold(), 0)
        if anzahl < 3:
            continue
        for schluessel, zahl in haeufigkeit.items():
            if zahl >= anzahl or zahl * 3 > anzahl:
                continue
            wort = formen[schluessel]
            if len(wort) < 4 or not wort[0].isupper():
                continue
            if wort[0].casefold() != begriff[0].casefold():
                continue
            if not _ein_schritt_entfernt(wort, begriff):
                continue
            if _ist_eigenstaendiger_begriff(
                wort, kategorie
            ) and not _vorname_lesefehler(begriff, wort, kategorie, anzahl, zahl):
                continue
            varianten.setdefault(wort, kategorie)
    return varianten


def namensvarianten(page_texts: Iterable[str], pool: Iterable[str]) -> set[str]:
    """Schreibvarianten erkannter Namen (Kurzform von schreibvarianten)."""
    begriffe = {name: Category.PERSON for name in pool}
    return set(schreibvarianten(page_texts, begriffe))


# Regel-Kennungen, deren Treffer einen Strassennamen liefern.
_STRASSEN_ENTITIES = {"street", "street_name", "street_split", "street_name_split"}
_HAUSNUMMER_REST = re.compile(r"[ \t]*\d.*$", re.DOTALL)
_PLZ_ORT = re.compile(r"(?:CH-)?\d{4,5}[ \t]+(.+)$")


def _strassenname(text: str) -> str:
    """Strassenname ohne Hausnummer ("Haupt strasse 56 a" -> "Haupt strasse")."""
    return _HAUSNUMMER_REST.sub("", text).strip()


def _ortsname(text: str) -> str:
    """Ort aus "82140 Olching" oder aus einem einzelnen Ortswort."""
    roh = text.strip()
    treffer = _PLZ_ORT.search(roh)
    if treffer:
        return treffer.group(1).strip(" .,;")
    return roh.strip(" .,;") if " " not in roh else ""


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
        name_pool: set[str] = set()
        for term in options.manual_terms:
            if term.category is Category.PERSON:
                name_pool |= name_tokens(term.value)

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
                    if rule.validate is not None and not rule.validate(match.group(0)):
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
                        if category is Category.POSTAL and _ai_location_is_date(entity_text):
                            # Datum statt Ort: die Datumsregel erfasst es.
                            continue
                        if category is Category.POSTAL and not _ai_location_is_place(entity_text):
                            # Kein Ort aus der Ortschaftenliste ("Fachmessen").
                            continue
                        if category is Category.PERSON:
                            if _ist_sachwort(entity_text):
                                # Sachwort, keine Person ("Urlaub", "Telefax").
                                continue
                            name_pool |= name_tokens(entity_text)
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

        # --- abgeschnittene IBAN ergaenzen ---------------------------
        # Steht der Rest einer IBAN in der naechsten Zeile, fehlten die letzten
        # Zeichen im Treffer ("DExx xxxx xxxx" statt der ganzen Nummer).
        for candidate in candidates:
            if candidate.entity != "iban":
                continue
            if plausibel.iban_gueltig(candidate.text) is True:
                continue
            seite = textmap.page(candidate.page).text
            neues_ende = _iban_verlaengern(seite, candidate.start, candidate.end)
            if neues_ende <= candidate.end:
                continue
            candidate.end = neues_ende
            candidate.text = seite[candidate.start : neues_ende]
            candidate.source = "Muster \u00b7 IBAN (Fortsetzung in der naechsten Zeile)"

        # --- Schreibvarianten ----------------------------------------
        # Steht ein Name, eine Strasse oder ein Ort mehrfach im Dokument, gilt
        # eine seltene Schreibweise mit einem Buchstaben Abstand als Lesefehler
        # desselben Begriffs ("Witler" neben 10-mal "Wittler", "Olchin" neben
        # "Olching"). Sonst bliebe genau diese Stelle offen, obwohl der Begriff
        # im Dokument bekannt ist.
        begriffe: dict[str, Category] = {
            token: Category.PERSON for token in name_pool
        }
        for candidate in candidates:
            if candidate.entity in _STRASSEN_ENTITIES:
                name = _strassenname(candidate.text)
                if len(name) >= 4:
                    begriffe.setdefault(name, Category.ADDRESS)
            elif candidate.category is Category.POSTAL:
                ort = _ortsname(candidate.text)
                if len(ort) >= 4:
                    begriffe.setdefault(ort, Category.POSTAL)

        varianten = schreibvarianten(
            (textmap.page(index).text for index in range(total)), begriffe
        )
        if varianten:
            LOGGER.debug("Schreibvarianten: %s", varianten)
        # Namensvarianten laufen ueber die Namensuebertragung weiter unten,
        # Strassen und Orte werden hier direkt gesucht.
        name_pool |= {
            wort for wort, kategorie in varianten.items() if kategorie is Category.PERSON
        }
        andere = {
            wort.casefold(): kategorie
            for wort, kategorie in varianten.items()
            if kategorie is not Category.PERSON
        }
        if andere:
            muster = "|".join(
                rf"(?<!\w){re.escape(wort)}(?!\w)"
                for wort in sorted(andere, key=len, reverse=True)
            )
            varianten_pattern = re.compile(muster, re.IGNORECASE | re.UNICODE)
            for index in range(total):
                page_text = textmap.page(index)
                if not page_text.text:
                    continue
                for match in varianten_pattern.finditer(page_text.text):
                    start, end = match.span()
                    if end <= start:
                        continue
                    kategorie = andere.get(match.group(0).casefold())
                    if kategorie is None:
                        continue
                    candidates.append(
                        _Candidate(
                            page=index,
                            start=start,
                            end=end,
                            text=match.group(0),
                            category=kategorie,
                            source=f"Variante \u00b7 {kategorie.value} im Dokument",
                            entity="VARIANT",
                            score=0.95,
                            priority=PRIORITY_NAME,
                        )
                    )

        # --- Namensuebertragung --------------------------------------
        # Damit der Name auch in der Adresszeile verschwindet, werden alle
        # Namensbestandteile im gesamten Dokument gesucht.
        if name_pool:
            if (
                progress
                and progress(total, total, "Erkannte Namen werden im Dokument gesucht ...")
                is False
            ):
                return DetectionResult([], warnings)
            alternatives = "|".join(
                rf"(?<!\w){re.escape(token)}(?!\w)"
                for token in sorted(name_pool, key=len, reverse=True)
            )
            name_pattern = re.compile(alternatives, re.IGNORECASE | re.UNICODE)
            for index in range(total):
                page_text = textmap.page(index)
                if not page_text.text:
                    continue
                for match in name_pattern.finditer(page_text.text):
                    start, end = match.span()
                    if end <= start:
                        continue
                    candidates.append(
                        _Candidate(
                            page=index,
                            start=start,
                            end=end,
                            text=match.group(0),
                            category=Category.PERSON,
                            source="Name \u00b7 im Dokument \u00fcbertragen",
                            entity="NAME",
                            score=1.0,
                            priority=PRIORITY_NAME,
                        )
                    )

        findings: list[Finding] = []
        uid = 0
        # Berufsbezeichnungen sind keine Namen und keine Adressen
        # ("Vorarbeiterin von 10 Dachdecker"). Manuell eingegebene Werte
        # bleiben unangetastet - was der Nutzer eintraegt, wird geschwaerzt.
        candidates = [
            candidate
            for candidate in candidates
            if candidate.entity == "MANUAL" or not berufe.ist_beruf(candidate.text)
        ]
        # Das Geburtsdatum wird zusaetzlich markiert; alle anderen Daten
        # bleiben als Datums-Treffer stehen.
        candidates = [
            candidate
            for candidate in candidates
            if not (
                candidate.entity in ("phone", "PHONE_NUMBER")
                and _in_nummernspalte(
                    textmap.page(candidate.page).text, candidate.start, candidate.end
                )
            )
        ]
        candidates = _nur_geburtsdatum(candidates, textmap, total)
        for candidate in _resolve(candidates):
            page_text = textmap.page(candidate.page)
            start, end = _strip_span(page_text.text, candidate.start, candidate.end)
            if end <= start:
                continue
            rects = textmap.rects_for(candidate.page, start, end)
            if not rects:
                continue
            uid += 1
            # Treffer ueber einen Zeilenumbruch (PLZ und Ort in getrennten
            # Zeilen) fuer Anzeige und Endkontrolle zusammenfassen.
            treffer_text = " ".join(page_text.text[start:end].split())
            findings.append(
                Finding(
                    text=treffer_text,
                    category=candidate.category,
                    page=candidate.page,
                    rects=rects,
                    source=candidate.source,
                    entity=candidate.entity,
                    hinweis=plausibel.hinweis(
                        treffer_text, candidate.category, candidate.entity
                    ),
                    score=round(candidate.score, 2),
                    enabled=True,
                    uid=uid,
                )
            )
        # Feste Regeln aus dem Code (aus der Lerndatei erzeugt) gelten immer,
        # die vorlaeufigen Beispiele der Lerndatei danach.
        findings = lernregeln.anwenden(findings)
        anwendung = lerndatei.anwenden(findings)
        return DetectionResult(
            anwendung.treffer,
            warnings,
            learned_off=anwendung.abgehakt,
            learned_changed=anwendung.umkategorisiert,
        )
    finally:
        doc.close()
