"""Prüfung der Unterlagen ohne KI - und die Frage an Copilot.

Alles, was sich ausrechnen lässt, macht dieses Modul selbst: Zeiträume,
Lücken, fehlende Seiten, Scans ohne Textebene, doppelte Dateien. Copilot
bekommt nur die weichen Fragen (Bewertung, Formulierung) - und weil es keinen
Rückkanal gibt, wird die Antwort als JSON aus der Zwischenablage gelesen.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MIN_GAP_MONTHS = 3

MONATE = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

_MONATSWORTE = "|".join(MONATE)

_RANGE_MONAT_JAHR = re.compile(
    r"(?P<m1>\d{1,2})\s*[./]\s*(?P<y1>(?:19|20)\d{2})\s*"
    r"(?:-|–|—|bis)\s*"
    r"(?:(?P<m2>\d{1,2})\s*[./]\s*)?(?P<y2>(?:19|20)\d{2})"
)
_RANGE_OFFEN = re.compile(
    r"(?P<m1>\d{1,2})\s*[./]\s*(?P<y1>(?:19|20)\d{2})\s*"
    r"(?:-|–|—|bis)\s*(?:heute|jetzt|aktuell|laufend|gegenwart|datum)",
    re.IGNORECASE,
)
_RANGE_MONATSNAME = re.compile(
    rf"(?P<name1>{_MONATSWORTE})\.?\s*(?P<y1>(?:19|20)\d{{2}})\s*"
    rf"(?:-|–|—|bis)\s*"
    rf"(?:(?P<name2>{_MONATSWORTE})\.?\s*)?(?P<y2>(?:19|20)\d{{2}})",
    re.IGNORECASE,
)
_RANGE_JAHRESZAHLEN = re.compile(
    r"\b(?P<y1>(?:19|20)\d{2})\s*(?:-|–|—|bis)\s*"
    r"(?:(?P<y2>(?:19|20)\d{2})|(?P<offen>heute|jetzt|aktuell|laufend))\b",
    re.IGNORECASE,
)


def _index(jahr: int, monat: int) -> int:
    return jahr * 12 + (monat - 1)


def _from_index(wert: int) -> tuple[int, int]:
    return wert // 12, wert % 12 + 1


def _fmt(value: tuple[int, int] | None) -> str:
    if value is None:
        return "heute"
    return f"{value[1]:02d}/{value[0]}"


@dataclass(frozen=True)
class Period:
    """Ein Zeitraum aus einem Dokument."""

    start: tuple[int, int]
    end: tuple[int, int] | None
    quelle: str = ""

    def label(self) -> str:
        return f"{_fmt(self.start)}–{_fmt(self.end)}"


@dataclass(frozen=True)
class Gap:
    """Eine Lücke zwischen zwei Zeiträumen."""

    von: tuple[int, int]
    bis: tuple[int, int]
    monate: int

    def label(self) -> str:
        return f"{_fmt(self.von)} bis {_fmt(self.bis)} ({self.monate} Monate)"


@dataclass
class Finding:
    """Ein Befund des lokalen Prüflaufs."""

    level: str  # "ok" | "warn" | "info"
    text: str


@dataclass
class ReviewReport:
    """Ergebnis des Prüflaufs plus die Daten für die Copilot-Frage."""

    findings: list[Finding] = field(default_factory=list)
    periods: list[Period] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    dateien: int = 0
    seiten: int = 0

    def warnings(self) -> int:
        return sum(1 for finding in self.findings if finding.level == "warn")

    def summary(self) -> str:
        warnungen = self.warnings()
        if warnungen == 0:
            return f"{self.dateien} Dateien, {self.seiten} Seiten, keine Auffälligkeit."
        return (
            f"{self.dateien} Dateien, {self.seiten} Seiten, "
            f"{warnungen} Hinweis{'e' if warnungen != 1 else ''}."
        )

    def as_text(self) -> str:
        if not self.findings:
            return "Keine Befunde."
        zeichen = {"warn": "!", "info": "·", "ok": "✓"}
        return "\n".join(
            f"{zeichen.get(finding.level, '·')} {finding.text}"
            for finding in self.findings
        )


# ---------------------------------------------------------------------------
# PDF lesen
# ---------------------------------------------------------------------------


def page_stats(path: str | Path) -> tuple[int, int]:
    """Seitenzahl und Seiten ohne nutzbaren Text (typisch fuer Scans)."""
    try:
        import pymupdf
    except Exception:  # noqa: BLE001 - ohne PyMuPDF bleibt es unbekannt
        return 0, 0
    try:
        with pymupdf.open(str(path)) as doc:
            leer = 0
            for page in doc:
                if len(page.get_text().strip()) < 20:
                    leer += 1
            return doc.page_count, leer
    except Exception:  # noqa: BLE001 - kaputte Datei zaehlt als unlesbar
        return 0, 0


def document_text(path: str | Path) -> str:
    """Textebene einer PDF-Datei; leer, wenn es keine gibt."""
    try:
        import pymupdf
    except Exception:  # noqa: BLE001
        return ""
    try:
        with pymupdf.open(str(path)) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Zeiträume und Lücken
# ---------------------------------------------------------------------------


def _periods_monat_jahr(text: str) -> list[Period]:
    result: list[Period] = []
    for treffer in _RANGE_MONAT_JAHR.finditer(text):
        monat1 = int(treffer.group("m1"))
        jahr1 = int(treffer.group("y1"))
        monat2 = treffer.group("m2")
        jahr2 = int(treffer.group("y2"))
        if not 1 <= monat1 <= 12:
            continue
        monat2_wert = int(monat2) if monat2 else 1
        if not 1 <= monat2_wert <= 12:
            continue
        result.append(Period((jahr1, monat1), (jahr2, monat2_wert), treffer.group(0)))
    return result


def _periods_offen(text: str) -> list[Period]:
    result: list[Period] = []
    for treffer in _RANGE_OFFEN.finditer(text):
        monat = int(treffer.group("m1"))
        jahr = int(treffer.group("y1"))
        if 1 <= monat <= 12:
            result.append(Period((jahr, monat), None, treffer.group(0)))
    return result


def _periods_monatsname(text: str) -> list[Period]:
    result: list[Period] = []
    for treffer in _RANGE_MONATSNAME.finditer(text):
        name1 = treffer.group("name1").lower()
        name2 = (treffer.group("name2") or "").lower()
        monat1 = MONATE.get(name1)
        if monat1 is None:
            continue
        monat2 = MONATE.get(name2, 1) if name2 else 1
        result.append(
            Period(
                (int(treffer.group("y1")), monat1),
                (int(treffer.group("y2")), monat2),
                treffer.group(0),
            )
        )
    return result


def _periods_jahreszahlen(text: str) -> list[Period]:
    result: list[Period] = []
    for treffer in _RANGE_JAHRESZAHLEN.finditer(text):
        jahr1 = int(treffer.group("y1"))
        offen = treffer.group("offen")
        if treffer.group("y2"):
            result.append(
                Period((jahr1, 1), (int(treffer.group("y2")), 1), treffer.group(0))
            )
        elif offen:
            result.append(Period((jahr1, 1), None, treffer.group(0)))
    return result


def periods_from_text(text: str) -> list[Period]:
    """Alle Zeiträume aus einem Text - doppelte fallen weg."""
    gefunden: list[Period] = []
    gefunden += _periods_offen(text)
    gefunden += _periods_monat_jahr(text)
    gefunden += _periods_monatsname(text)
    gefunden += _periods_jahreszahlen(text)

    eindeutig: dict[tuple, Period] = {}
    for period in gefunden:
        schluessel = (period.start, period.end)
        # Der genauere Treffer (mit Monat) gewinnt gegen die blosse Jahreszahl.
        if schluessel not in eindeutig or _genauigkeit(period) > _genauigkeit(
            eindeutig[schluessel]
        ):
            eindeutig[schluessel] = period
    return sorted(
        eindeutig.values(), key=lambda period: _index(*period.start), reverse=True
    )


def _genauigkeit(period: Period) -> int:
    """1 = nur Jahreszahl, 2 = Monat in einem Ende, 3 = Monat in beiden."""
    genau = 0
    if period.start[1] != 1:
        genau += 1
    if period.end is not None and period.end[1] != 1:
        genau += 1
    return genau


def gaps(
    periods: list[Period], today: date | None = None, min_months: int = MIN_GAP_MONTHS
) -> list[Gap]:
    """Lücken zwischen den Zeiträumen, ab ``min_months`` Monaten."""
    heute = today or date.today()
    heute_index = _index(heute.year, heute.month)

    intervalle: list[tuple[int, int]] = []
    for period in periods:
        start = _index(*period.start)
        ende = _index(*period.end) if period.end else heute_index
        if ende < start:
            start, ende = ende, start
        intervalle.append((start, ende))
    intervalle.sort()

    verschmolzen: list[list[int]] = []
    for start, ende in intervalle:
        if verschmolzen and start <= verschmolzen[-1][1] + 1:
            verschmolzen[-1][1] = max(verschmolzen[-1][1], ende)
        else:
            verschmolzen.append([start, ende])

    luecken: list[Gap] = []
    for vorher, danach in zip(verschmolzen, verschmolzen[1:]):
        laenge = danach[0] - vorher[1] - 1
        if laenge >= min_months:
            luecken.append(Gap(_from_index(vorher[1] + 1), _from_index(danach[0] - 1), laenge))
    return luecken


# ---------------------------------------------------------------------------
# Doppelte Dateien und der ganze Prüflauf
# ---------------------------------------------------------------------------


def _fingerprint(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def duplicates(paths: list[str]) -> list[list[str]]:
    """Dateien mit identischem Inhalt."""
    gruppen: dict[str, list[str]] = {}
    for pfad in paths:
        datei = Path(pfad)
        if not datei.is_file():
            continue
        kennung = _fingerprint(datei)
        if kennung is None:
            continue
        gruppen.setdefault(kennung, []).append(str(datei))
    return [gruppe for gruppe in gruppen.values() if len(gruppe) > 1]


def review(life: list[str], certs: list[str]) -> ReviewReport:
    """Alles prüfen, was ohne KI prüfbar ist."""
    report = ReviewReport()
    alle = [pfad for pfad in [*life, *certs] if Path(pfad).is_file()]
    report.dateien = len(alle)

    if not life:
        report.findings.append(Finding("warn", "Kein Lebenslauf zugeordnet."))
    if not certs:
        report.findings.append(Finding("warn", "Keine Arbeitszeugnisse zugeordnet."))

    for pfad in [*life, *certs]:
        if not Path(pfad).is_file():
            report.findings.append(
                Finding("warn", f"{Path(pfad).name}: Datei ist nicht mehr vorhanden.")
            )

    seiten_gesamt = 0
    for pfad in alle:
        seiten, leer = page_stats(pfad)
        seiten_gesamt += seiten
        if seiten and leer == seiten:
            report.findings.append(
                Finding(
                    "warn",
                    f"{Path(pfad).name}: keine Textebene (Scan) – PDFblack findet "
                    "dort nichts zu schwärzen.",
                )
            )
        elif leer:
            report.findings.append(
                Finding(
                    "warn",
                    f"{Path(pfad).name}: {leer} von {seiten} Seiten ohne Textebene.",
                )
            )
    report.seiten = seiten_gesamt

    for gruppe in duplicates(alle):
        namen = ", ".join(Path(pfad).name for pfad in gruppe)
        report.findings.append(Finding("warn", f"Doppelt vorhanden: {namen}."))

    lebenslauf_text = "\n".join(document_text(pfad) for pfad in life)
    report.periods = periods_from_text(lebenslauf_text)
    if life and not report.periods:
        report.findings.append(
            Finding("info", "Im Lebenslauf keine Zeiträume erkannt (Jahreszahlen fehlen?).")
        )
    report.gaps = gaps(report.periods)
    for luecke in report.gaps:
        report.findings.append(
            Finding("warn", f"Lücke im Lebenslauf: {luecke.label()} – unerklärt?")
        )

    if report.periods and certs:
        geordnet = _cert_order(certs)
        if geordnet is not None and geordnet is False:
            report.findings.append(
                Finding("info", "Zeugnisse liegen nicht chronologisch (neuestes zuerst).")
            )

    if not report.findings:
        report.findings.append(Finding("ok", "Nichts Auffälliges gefunden."))
    return report


def _cert_order(certs: list[str]) -> bool | None:
    """Sind die Zeugnisse von neu nach alt sortiert? ``None`` = unbekannt."""
    daten: list[tuple[int, int]] = []
    for pfad in certs:
        periods = periods_from_text(document_text(pfad))
        if not periods:
            return None
        periode = periods[0]
        daten.append(periode.end or periode.start)
    indizes = [_index(*wert) for wert in daten]
    return indizes == sorted(indizes, reverse=True)


# ---------------------------------------------------------------------------
# Frage an Copilot und Antwort zurueck
# ---------------------------------------------------------------------------

ANTWORT_SCHEMA = {
    "lebenslauf_luecken": [{"von": "MM/JJJJ", "bis": "MM/JJJJ", "hinweis": "..."}],
    "zeugnisse": [{"datei": "...", "art": "Arbeitszeugnis", "zeitraum": "MM/JJJJ–MM/JJJJ"}],
    "fehlende_unterlagen": ["..."],
    "auffaelligkeiten": ["..."],
    "zusammenfassung": "zwei bis drei Sätze",
}

HANDOVER_FRAGE = (
    "Prüfe die angehängten Bewerbungsunterlagen. Antworte ausschließlich mit "
    "einem JSON-Objekt nach diesem Schema, ohne Einleitung und ohne Erklärung "
    "davor oder danach:\n"
)


def build_prompt(report: ReviewReport, life: list[str], certs: list[str]) -> str:
    """Die Frage an Copilot - Fakten kommen aus dem lokalen Prüflauf."""
    zeilen = [
        HANDOVER_FRAGE,
        json.dumps(ANTWORT_SCHEMA, ensure_ascii=False, indent=2),
        "",
        "Bekannte Angaben aus dem Programm (bitte nicht wiederholen, nur ergänzen):",
        f"- Lebenslauf: {', '.join(Path(pfad).name for pfad in life) or 'fehlt'}",
        f"- Zeugnisse: {', '.join(Path(pfad).name for pfad in certs) or 'fehlen'}",
        f"- Seiten gesamt: {report.seiten}",
    ]
    if report.periods:
        zeilen.append(
            "- Erkannte Zeiträume: "
            + ", ".join(periode.label() for periode in report.periods[:12])
        )
    if report.gaps:
        zeilen.append(
            "- Rechnerische Lücken: " + "; ".join(luecke.label() for luecke in report.gaps)
        )
    zeilen += [
        "",
        "Prüfe zusätzlich inhaltlich: Passen die Zeugnisse zum Lebenslauf, fehlen "
        "Unterlagen, wirkt etwas unstimmig? Nenne in „hinweis“ kurz, was in der "
        "Lücke steht, falls die Unterlagen es hergeben.",
    ]
    return "\n".join(zeilen)


def _json_block(text: str) -> str | None:
    """Erstes JSON-Objekt aus einer Antwort herausschneiden."""
    start = text.find("{")
    if start < 0:
        return None
    tiefe = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        zeichen = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif zeichen == "\\":
                escaped = True
            elif zeichen == '"':
                in_string = False
            continue
        if zeichen == '"':
            in_string = True
        elif zeichen == "{":
            tiefe += 1
        elif zeichen == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start : index + 1]
    return None


def parse_answer(text: str) -> dict | None:
    """Antwort aus Copilot lesen: JSON auch aus Fliesstext oder Code-Block."""
    if not text or not text.strip():
        return None
    kandidat = _json_block(text)
    if kandidat is None:
        return None
    versuche = [kandidat, re.sub(r",\s*([}\]])", r"\1", kandidat)]
    for versuch in versuche:
        try:
            daten = json.loads(versuch)
        except (TypeError, ValueError):
            continue
        if isinstance(daten, dict):
            return daten
    return None


def answer_lines(daten: dict) -> list[str]:
    """Antwort in lesbare Zeilen verwandeln."""
    zeilen: list[str] = []

    luecken = daten.get("lebenslauf_luecken")
    if isinstance(luecken, list) and luecken:
        zeilen.append("Lücken laut Copilot:")
        for eintrag in luecken[:12]:
            if isinstance(eintrag, dict):
                zeilen.append(
                    f"  {eintrag.get('von', '?')} – {eintrag.get('bis', '?')}: "
                    f"{eintrag.get('hinweis', '')}".rstrip(": ")
                )
            else:
                zeilen.append(f"  {eintrag}")

    zeugnisse = daten.get("zeugnisse")
    if isinstance(zeugnisse, list) and zeugnisse:
        zeilen.append("Zeugnisse laut Copilot:")
        for eintrag in zeugnisse[:20]:
            if isinstance(eintrag, dict):
                zeilen.append(
                    f"  {eintrag.get('datei', '?')}: {eintrag.get('art', '?')}, "
                    f"{eintrag.get('zeitraum', '?')}"
                )
            else:
                zeilen.append(f"  {eintrag}")

    for schluessel, titel in (
        ("fehlende_unterlagen", "Fehlt laut Copilot:"),
        ("auffaelligkeiten", "Auffälligkeiten:"),
    ):
        werte = daten.get(schluessel)
        if isinstance(werte, list) and werte:
            zeilen.append(titel)
            for wert in werte[:12]:
                zeilen.append(f"  {wert}")

    zusammenfassung = daten.get("zusammenfassung")
    if isinstance(zusammenfassung, str) and zusammenfassung.strip():
        zeilen.append("")
        zeilen.append(zusammenfassung.strip())

    if not zeilen:
        return ["Die Antwort enthielt keine verwertbaren Angaben."]
    return zeilen
