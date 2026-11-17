"""Geburtsdatum bestimmen: das aelteste Datum im Dokument.

PDFblack liest beim Durchlauf alle Datumsangaben mit - ``dd.mm.yyyy``,
``dd.mm.yy``, ``dd. Monat yyyy`` und ``dd. Monat yy`` (auch ISO
``yyyy-mm-dd``). Das aelteste davon gilt als Geburtsdatum, aber nur, wenn es
mindestens 15 Jahre vor dem naechstjuengeren Datum liegt. Geschwaerzt wird
dann allein dieses Datum; die uebrigen Datumsangaben dienen nur dieser
Einordnung.
"""

from __future__ import annotations

import re
from datetime import date

# Mindestabstand des Geburtsdatums zum naechsten Datum in Jahren.
MINDESTABSTAND = 15

MONATE: dict[str, int] = {
    "januar": 1,
    "jänner": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
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

_MONATNAMEN = "|".join(sorted(MONATE, key=len, reverse=True))

# 20.10.2026, 20.10.26, 20. 10. 2026
_DOTTED = re.compile(r"(?<!\d)(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})(?!\d)")
# 20. Oktober 2026, 20 Oktober 26
_WORT = re.compile(
    rf"(?<!\d)(\d{{1,2}})\.?\s*({_MONATNAMEN})\.?\s*(\d{{2,4}})(?![\d\w])",
    re.IGNORECASE,
)
# 2026-10-20
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")

# Jede Schreibweise eines Datums in einem Rutsch - auch Varianten, die keine
# Regel erfasst ("01. Maerz 1995", "1. 3. 1995", "1995-03-01").
_SCHREIBWEISE = re.compile(
    r"(?<![\d\w.])("
    r"\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{2,4}"
    rf"|\d{{1,2}}\.?\s*(?:{_MONATNAMEN})\.?\s*\d{{2,4}}"
    r"|\d{4}-\d{2}-\d{2}"
    r")(?![\d\w])",
    re.IGNORECASE,
)


def _jahr(wert: str) -> int:
    """Zweistellige Jahre aufloesen - nicht in die Zukunft."""
    jahr = int(wert)
    if jahr >= 100:
        return jahr
    heute = date.today().year
    kandidat = 2000 + jahr
    return kandidat if kandidat <= heute else 1900 + jahr


def als_datum(text: str) -> date | None:
    """Datum aus einem Treffer lesen; ``None``, wenn keins darin steht.

    Die Beschriftung davor stoert nicht: aus "Geburtsdatum: 12.03.1985" wird
    der 12.03.1985.
    """
    treffer = _DOTTED.search(text)
    if treffer is not None:
        tag = int(treffer.group(1))
        monat = int(treffer.group(2))
        jahr = _jahr(treffer.group(3))
    else:
        treffer = _WORT.search(text)
        if treffer is not None:
            tag = int(treffer.group(1))
            monat = MONATE[treffer.group(2).lower()]
            jahr = _jahr(treffer.group(3))
        else:
            treffer = _ISO.search(text)
            if treffer is None:
                return None
            jahr = int(treffer.group(1))
            monat = int(treffer.group(2))
            tag = int(treffer.group(3))
    try:
        return date(jahr, monat, tag)
    except ValueError:
        return None


def schreibweisen(text: str, ziel: date) -> list[tuple[int, int]]:
    """Alle Stellen im Text, die genau dieses Datum nennen - egal wie.

    Aus dem gefundenen ``1.3.95`` werden so auch ``01. März 1995``,
    ``1. 3. 1995`` und ``1995-03-01`` erkannt.
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


def geburtsdatum(daten: list[date]) -> date | None:
    """Aeltestes Datum, wenn es weit genug vor dem naechsten liegt.

    Ohne zweites Datum laesst sich der Abstand nicht pruefen - dann gibt es
    kein Geburtsdatum.
    """
    eindeutig = sorted(set(daten))
    if len(eindeutig) < 2:
        return None
    aeltestes, naechstes = eindeutig[0], eindeutig[1]
    if jahre_zwischen(aeltestes, naechstes) < MINDESTABSTAND:
        return None
    return aeltestes


__all__ = [
    "MINDESTABSTAND",
    "MONATE",
    "als_datum",
    "geburtsdatum",
    "jahre_zwischen",
    "schreibweisen",
]
