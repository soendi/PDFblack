"""Geburtsdatum bestimmen: das aelteste Datum im Dokument.

PDFblack liest beim Durchlauf alle Datumsangaben mit - ``12.03.1985``,
``12.3.85``, ``3. 12 1985``, ``12/03/1985``, ``12-3-85``, ``12. Maerz 1985``,
``3. Maerz 85`` und ``2026-10-20`` sowie Monat/Jahr-Angaben wie ``10/2025``,
``1/85``, ``03.1985`` und ``Maerz 1985``. Das aelteste vollstaendige Datum
gilt als Geburtsdatum, aber nur, wenn es mindestens 15 Jahre vor dem
naechstjuengeren Datum liegt. Geschwaerzt wird dann allein dieses Datum; die
uebrigen Datumsangaben dienen nur dieser Einordnung.

Die Bausteine der Muster (``TAG_MUSTER``, ``MONAT_MUSTER``, ``JAHR_MUSTER``,
``MONATNAMEN``) nutzt auch ``rules.py``, damit Lesen und Erkennen nicht
auseinanderlaufen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# Mindestabstand des Geburtsdatums zum naechsten Datum in Jahren.
MINDESTABSTAND = 15

MONATE: dict[str, int] = {
    "januar": 1,
    "jänner": 1,
    "jaenner": 1,
    "jän": 1,
    "jan": 1,
    "februar": 2,
    # "Febr." ist die haeufigste Abkuerzung in Zeugnissen.
    "febr": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "marz": 3,
    "mär": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}

# --- Bausteine der Datumsmuster -------------------------------------------
MONATNAMEN = "|".join(sorted(MONATE, key=len, reverse=True))

TAG_MUSTER = r"(?:0?[1-9]|[12]\d|3[01])"
MONAT_MUSTER = r"(?:0?[1-9]|1[0-2])"
# Eine oder zwei Ziffern fuer Tag und Monat, wenn die Reihenfolge noch offen
# ist ("05/31/1990"): sortiert wird in ``_tag_monat``, geprueft in ``_angabe``.
ZAHL_MUSTER = r"\d{1,2}"
JAHR_LANG_MUSTER = r"(?:1[6-9]\d{2}|20\d{2})"
JAHR_KURZ_MUSTER = r"\d{2}"
JAHR_MUSTER = rf"(?:{JAHR_LANG_MUSTER}|{JAHR_KURZ_MUSTER})"
# Zwischen den Teilen darf Leerraum stehen ("3. 12 1985", "12 / 3 / 85").
LUECKE = r"[ \t]*"
# Vor und hinter einer Angabe muss eine Grenze liegen.
_LINKS = r"(?<![\d\w])"
_RECHTS = r"(?![\d\w])"

# 1985-03-12, 1985.03.12, 1985/03/12
_ISO = re.compile(
    rf"{_LINKS}({JAHR_LANG_MUSTER}){LUECKE}[-./]{LUECKE}({MONAT_MUSTER}){LUECKE}"
    rf"[-./]{LUECKE}({TAG_MUSTER}){_RECHTS}"
)
# 12.03.1985, 12. 3. 85, 3. 12 1985, 3.12 85
_PUNKT = re.compile(
    rf"{_LINKS}({TAG_MUSTER}){LUECKE}\.{LUECKE}({MONAT_MUSTER}){LUECKE}\.?{LUECKE}"
    rf"({JAHR_MUSTER}){_RECHTS}"
)
# 12/03/1985, 5/2/90, 12-3-85, 12 / 03 / 1985 und 05/31/1990 (Monat vorn)
_STRICH = re.compile(
    rf"{_LINKS}({TAG_MUSTER}){LUECKE}[/\-]{LUECKE}({ZAHL_MUSTER}){LUECKE}"
    rf"[/\-]{LUECKE}({JAHR_MUSTER}){_RECHTS}"
)
# 12. Maerz 1985, 3. Maerz 85, 12 Maerz 1985, 3. Sept. 1999
_WORT = re.compile(
    rf"{_LINKS}({TAG_MUSTER}){LUECKE}\.?{LUECKE}({MONATNAMEN})\.?{LUECKE},?{LUECKE}"
    rf"({JAHR_MUSTER}){_RECHTS}",
    re.IGNORECASE,
)
# 10/2025, 1/85, 03-2025 und 03.1985 - der Punkt nur mit vierstelligem Jahr,
# damit Preise wie "12.34" keine Datumsangabe werden.
_MONAT_JAHR = re.compile(
    rf"(?<![\d\w./\-])({MONAT_MUSTER}){LUECKE}(?:"
    rf"[/\-]{LUECKE}({JAHR_MUSTER})"
    rf"|\.{LUECKE}({JAHR_LANG_MUSTER})"
    rf")(?![\d\w]|[./\-]{LUECKE}\d)"
)
# Maerz 1985, September 1999
_MONAT_WORT = re.compile(
    rf"{_LINKS}({MONATNAMEN})\.?{LUECKE}({JAHR_MUSTER}){_RECHTS}", re.IGNORECASE
)

# Jede vollstaendige Schreibweise eines Datums in einem Rutsch - auch
# Varianten, die keine Regel erfasst ("01. Maerz 1995", "1. 3. 1995").
_SCHREIBWEISE = re.compile(
    rf"{_LINKS}(?:"
    rf"{JAHR_LANG_MUSTER}{LUECKE}[-./]{LUECKE}{MONAT_MUSTER}{LUECKE}[-./]{LUECKE}"
    rf"{TAG_MUSTER}"
    rf"|{TAG_MUSTER}{LUECKE}\.{LUECKE}{MONAT_MUSTER}{LUECKE}\.?{LUECKE}{JAHR_MUSTER}"
    rf"|{TAG_MUSTER}{LUECKE}[/\-]{LUECKE}{ZAHL_MUSTER}{LUECKE}[/\-]{LUECKE}"
    rf"{JAHR_MUSTER}"
    rf"|{TAG_MUSTER}{LUECKE}\.?{LUECKE}(?:{MONATNAMEN})\.?{LUECKE},?{LUECKE}"
    rf"{JAHR_MUSTER}"
    rf"){_RECHTS}",
    re.IGNORECASE,
)

# Vierstellige Jahreszahlen im Text - sie entscheiden, wenn nur ein Datum da ist.
_JAHRESZAHL = re.compile(rf"(?<!\d)({JAHR_LANG_MUSTER})(?!\d)")


@dataclass(frozen=True)
class Angabe:
    """Eine Datumsangabe; ohne Tagesangabe bleibt ``tag`` leer."""

    jahr: int
    monat: int
    tag: int | None = None

    @property
    def datum(self) -> date | None:
        """Vollstaendiges Datum - ``None``, wenn der Tag fehlt."""
        if self.tag is None:
            return None
        return date(self.jahr, self.monat, self.tag)

    def anfang(self) -> date:
        """Erster Tag der Angabe, fuer den Vergleich von Monat/Jahr."""
        return date(self.jahr, self.monat, self.tag or 1)


def _jahr(wert: str) -> int:
    """Zweistellige Jahre aufloesen - nicht in die Zukunft."""
    jahr = int(wert)
    if jahr >= 100:
        return jahr
    heute = date.today().year
    kandidat = 2000 + jahr
    return kandidat if kandidat <= heute else 1900 + jahr


def _angabe(jahr: int, monat: int, tag: int | None = None) -> Angabe | None:
    """Werte pruefen und daraus eine Angabe bauen."""
    if not 1 <= monat <= 12:
        return None
    if not 1500 <= jahr <= 2200:
        return None
    if tag is None:
        return Angabe(jahr, monat)
    try:
        date(jahr, monat, tag)
    except ValueError:
        return None
    return Angabe(jahr, monat, tag)


def _tag_monat(erster: str, zweiter: str) -> tuple[int, int]:
    """Tag und Monat aus zwei Zahlen.

    Tag zuerst ("05/02/1990" ist der 5. Februar), ausser die zweite Zahl ist
    zu gross fuer einen Monat: dann steht der Monat vorn ("05/31/1990").
    """
    erste, zweite = int(erster), int(zweiter)
    if erste <= 12 < zweite:
        return zweite, erste
    return erste, zweite


def als_angabe(text: str) -> Angabe | None:
    """Erste Datumsangabe im Text lesen - mit oder ohne Tag.

    Die Beschriftung davor stoert nicht: aus "Geburtsdatum: 12.03.1985" wird
    der 12.03.1985, aus "Anstellung 01/2019" der Januar 2019.
    """
    treffer = _ISO.search(text)
    if treffer is not None:
        return _angabe(
            int(treffer.group(1)), int(treffer.group(2)), int(treffer.group(3))
        )

    treffer = _PUNKT.search(text)
    if treffer is not None:
        tag, monat = _tag_monat(treffer.group(1), treffer.group(2))
        return _angabe(_jahr(treffer.group(3)), monat, tag)

    treffer = _STRICH.search(text)
    if treffer is not None:
        tag, monat = _tag_monat(treffer.group(1), treffer.group(2))
        return _angabe(_jahr(treffer.group(3)), monat, tag)

    treffer = _WORT.search(text)
    if treffer is not None:
        return _angabe(
            _jahr(treffer.group(3)),
            MONATE[treffer.group(2).lower()],
            int(treffer.group(1)),
        )

    treffer = _MONAT_JAHR.search(text)
    if treffer is not None:
        jahr = treffer.group(2) or treffer.group(3)
        return _angabe(_jahr(jahr), int(treffer.group(1)))

    treffer = _MONAT_WORT.search(text)
    if treffer is not None:
        return _angabe(_jahr(treffer.group(2)), MONATE[treffer.group(1).lower()])

    return None


def als_datum(text: str) -> date | None:
    """Vollstaendiges Datum aus einem Treffer; ``None`` ohne Tagesangabe."""
    angabe = als_angabe(text)
    return None if angabe is None else angabe.datum


def jahreszahlen(text: str) -> list[int]:
    """Alle vierstelligen Jahreszahlen im Text."""
    return [int(treffer.group(1)) for treffer in _JAHRESZAHL.finditer(text)]


def datumsspanne(text: str) -> tuple[int, int] | None:
    """Stelle der ersten vollstaendigen Datumsangabe im Text."""
    treffer = _SCHREIBWEISE.search(text)
    return treffer.span() if treffer is not None else None


def schreibweisen(text: str, ziel: date) -> list[tuple[int, int]]:
    """Alle Stellen im Text, die genau dieses Datum nennen - egal wie.

    Aus dem gefundenen ``1.3.95`` werden so auch ``01. März 1995``,
    ``1. 3. 1995``, ``3/1/1995`` und ``1995-03-01`` erkannt.
    """
    stellen: list[tuple[int, int]] = []
    for treffer in _SCHREIBWEISE.finditer(text):
        if als_datum(treffer.group(0)) == ziel:
            stellen.append(treffer.span())
    return stellen


def jahre_zwischen(frueher: date, spaeter: date) -> int:
    """Volle Jahre zwischen zwei Daten."""
    jahre = spaeter.year - frueher.year
    if (spaeter.month, spaeter.day) < (frueher.month, frueher.day):
        jahre -= 1
    return jahre


def _als_angabe(wert: date | Angabe) -> Angabe | None:
    """Datum und Angabe vergleichbar machen."""
    if isinstance(wert, date):
        return Angabe(wert.year, wert.month, wert.day)
    if wert.tag is None:
        return wert
    return wert if wert.datum is not None else None


def geburtsdatum(
    daten: list[date | Angabe], weitere_jahre: list[int] | None = None
) -> date | None:
    """Aeltestes vollstaendiges Datum, wenn es weit genug entfernt ist.

    Gibt es mehrere Daten, entscheidet das naechstjuengere; Monat/Jahr-
    Angaben ohne Tag zaehlen dabei mit. Ist nur ein vollstaendiges Datum
    genannt, entscheidet die naechsthoehere Jahreszahl im Dokument
    ("05/02/1990" und sonst nur "2020" -> Geburtsdatum). Eine Monat/Jahr-
    Angabe gilt nie selbst als Geburtsdatum: ein halbes Datum ist keins, und
    eine Nummer wie "12/34" waere sonst ein Treffer. Ohne Vergleichswert gibt
    es kein Geburtsdatum.
    """
    vollstaendig: set[date] = set()
    ohne_tag: set[date] = set()
    for wert in daten:
        angabe = _als_angabe(wert)
        if angabe is None:
            continue
        if angabe.tag is None:
            ohne_tag.add(angabe.anfang())
        else:
            vollstaendig.add(angabe.datum)

    if not vollstaendig:
        return None
    aeltestes = min(vollstaendig)
    juenger = [datum for datum in vollstaendig if datum > aeltestes]
    juenger += [datum for datum in ohne_tag if datum > aeltestes]
    if juenger:
        if jahre_zwischen(aeltestes, min(juenger)) < MINDESTABSTAND:
            return None
        return aeltestes

    spaeter = [jahr for jahr in weitere_jahre or [] if jahr > aeltestes.year]
    if not spaeter:
        return None
    if min(spaeter) - aeltestes.year < MINDESTABSTAND:
        return None
    return aeltestes


__all__ = [
    "JAHR_KURZ_MUSTER",
    "JAHR_LANG_MUSTER",
    "JAHR_MUSTER",
    "LUECKE",
    "MINDESTABSTAND",
    "MONATE",
    "MONATNAMEN",
    "MONAT_MUSTER",
    "TAG_MUSTER",
    "ZAHL_MUSTER",
    "Angabe",
    "als_angabe",
    "als_datum",
    "datumsspanne",
    "geburtsdatum",
    "jahre_zwischen",
    "jahreszahlen",
    "schreibweisen",
]
