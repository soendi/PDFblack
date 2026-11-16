"""Amtliche Schweizer Postleitzahlen und Ortschaften.

Die Liste stammt aus dem amtlichen Ortschaftenverzeichnis von swisstopo
(opendata.swiss, freie Nutzung) und aus den Postleitzahl-Daten von GeoNames
(CC BY 4.0), die auch Postfach-Postleitzahlen wie 8000 oder 3000 enthalten.
Damit laesst sich eine vierstellige Zahl sicher von einer Jahreszahl trennen:
Eine PLZ gibt es nur, wenn sie in der Liste steht - und im Jahresband zusaetzlich
nur, wenn der Ort dahinter zur PLZ passt.

Neu bauen: ``python tools/build_plz_data.py``
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DATEN = Path(__file__).resolve().parents[1] / "data" / "plz_ch.json"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# Erste vierstellige Zahl im Treffer (der Regelausdruck hat sie schon geprueft).
_PLZ4 = re.compile(r"\d{4}")


def _ohne_akzente(text: str) -> str:
    zerlegt = unicodedata.normalize("NFKD", text)
    return "".join(zeichen for zeichen in zerlegt if not unicodedata.combining(zeichen))


def _schluessel(text: str) -> set[str]:
    """Schreibweisen eines Ortsnamens fuer den Vergleich."""
    text = text.strip()
    if not text:
        return set()
    schlicht = re.sub(r"[^a-z0-9]", "", _ohne_akzente(text).lower())
    umschrieben = re.sub(r"[^a-z0-9]", "", text.lower().translate(_UMLAUTE))
    return {wert for wert in (schlicht, umschrieben) if len(wert) >= 3}


@lru_cache(maxsize=1)
def _codes() -> dict[str, tuple[str, ...]]:
    """PLZ -> Schreibweisen der zugehoerigen Ortschaften."""
    try:
        rohdaten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - nur bei kaputtem Build
        LOGGER.warning("PLZ-Liste fehlt oder ist unlesbar (%s): %s", DATEN, exc)
        return {}
    codes = rohdaten.get("codes") or {}
    return {
        str(plz): tuple(str(name) for name in namen)
        for plz, namen in codes.items()
    }


def verfuegbar() -> bool:
    """Liegt die amtliche Liste vor?"""
    return bool(_codes())


def stand() -> str:
    """Stand der Liste, z. B. ``2026-11``."""
    try:
        return str(json.loads(DATEN.read_text(encoding="utf-8")).get("stand", ""))
    except (OSError, ValueError):  # pragma: no cover
        return ""


def anzahl() -> int:
    return len(_codes())


def is_postal_code(value: str) -> bool:
    """Ist diese vierstellige Zahl eine amtliche Postleitzahl?"""
    return str(value).strip() in _codes()


def orte(plz: str) -> tuple[str, ...]:
    """Schreibweisen der Ortschaften zu einer PLZ (klein, ohne Akzente)."""
    return _codes().get(str(plz).strip(), ())


def quellen() -> list[str]:
    """Herkunft und Lizenz der Liste (fuer den Ueber-Dialog)."""
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return []
    return [str(eintrag) for eintrag in daten.get("quellen", ())]


def _kandidaten(ort: str) -> set[str]:
    """Schreibweisen des Orts aus dem Dokument (ein bis drei Woerter)."""
    woerter = [wort for wort in re.split(r"[\s,]+", ort.strip()) if wort]
    kandidaten: set[str] = set()
    for anzahl_woerter in (1, 2, 3):
        teil = " ".join(woerter[:anzahl_woerter])
        if teil:
            kandidaten |= _schluessel(teil)
    return kandidaten


def is_place(plz: str, ort: str) -> bool:
    """Gehoert dieser Ortsname zu dieser Postleitzahl?

    Verglichen wird ohne Akzente, mit und ohne Umlaut-Umschrift und mit
    Praefix-Toleranz ("Bern" passt zu "Bern 60 UPD", "Zürich" zu "zuerich").
    """
    namen = orte(plz)
    if not namen or not ort.strip():
        return False
    for kandidat in _kandidaten(ort):
        for name in namen:
            if name == kandidat:
                return True
            if len(kandidat) >= 4 and name.startswith(kandidat):
                return True
            if len(name) >= 4 and kandidat.startswith(name):
                return True
    return False


def plz_vor_ort(text: str) -> tuple[str, str] | None:
    """Aus einem Treffer wie ``1950 Sion`` die PLZ und den Ort holen."""
    treffer = _PLZ4.search(text)
    if treffer is None:
        return None
    return treffer.group(0), text[treffer.end() :].strip()
