"""Amtliches Strassenverzeichnis der Schweiz.

Die Liste (``data/strassen_ch.json``) kommt aus dem amtlichen Verzeichnis der
Strassen von swisstopo (opendata.swiss, freie Nutzung). Sie enthaelt alle
Strassennamen, die im Eidgenoessischen Gebaeude- und Wohnungsregister als
Adressbestandteil deklariert sind - in allen Landessprachen, rund 130 000
Namen.

Damit laesst sich ein Strassenname auch ohne Hausnummer erkennen und von
einem Personennamen oder Sachwort unterscheiden.

Neu bauen: ``python tools/build_strassen_data.py``
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DATEN = Path(__file__).resolve().parents[1] / "data" / "strassen_ch.json"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _ohne_akzente(text: str) -> str:
    zerlegt = unicodedata.normalize("NFKD", text)
    return "".join(zeichen for zeichen in zerlegt if not unicodedata.combining(zeichen))


def normalisiere(text: str) -> str:
    """Vergleichsform eines Strassennamens.

    Klein, Umlaute als ae/oe/ue, ohne Akzente und Satzzeichen, Leerraum
    vereinfacht. So passen "Sägmühlstrasse" und "Saegmuehlstrasse" zusammen.
    """
    text = str(text).strip().lower().translate(_UMLAUTE)
    text = _ohne_akzente(text)
    text = re.sub(r"[^a-z0-9\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -")


@lru_cache(maxsize=1)
def _strassen() -> frozenset[str]:
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - nur bei kaputtem Build
        LOGGER.warning("Strassenverzeichnis fehlt oder ist unlesbar (%s): %s", DATEN, exc)
        return frozenset()
    return frozenset(str(eintrag) for eintrag in daten.get("strassen", ()))


def verfuegbar() -> bool:
    return bool(_strassen())


def anzahl() -> int:
    return len(_strassen())


def stand() -> str:
    """Stand der Liste, z. B. ``2026-11``."""
    try:
        return str(json.loads(DATEN.read_text(encoding="utf-8")).get("stand", ""))
    except (OSError, ValueError):  # pragma: no cover
        return ""


def quellen() -> list[str]:
    """Herkunft und Lizenz der Liste (fuer den Ueber-Dialog)."""
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return []
    return [str(eintrag) for eintrag in daten.get("quellen", ())]


def _kandidaten(schluessel: str) -> tuple[str, ...]:
    """Schreibweisen zu einem Namen.

    In PDFs steht die Strasse oft abgekuerzt ("Bahnhofstr. 5", "Dorfpl. 7");
    das Verzeichnis fuehrt sie ausgeschrieben. Beide Formen werden verglichen.
    """
    kandidaten = [schluessel]
    if schluessel.endswith("str") and len(schluessel) > 5:
        kandidaten.append(schluessel + "asse")
    elif schluessel.endswith("strasse") and len(schluessel) > 8:
        kandidaten.append(schluessel[:-4])
    if schluessel.endswith("pl") and len(schluessel) > 5:
        kandidaten.append(schluessel + "atz")
    elif schluessel.endswith("platz") and len(schluessel) > 7:
        kandidaten.append(schluessel[:-3])
    return tuple(dict.fromkeys(kandidaten))


def ist_strasse(text: str) -> bool:
    """Steht dieser Name im amtlichen Strassenverzeichnis?"""
    namen = _strassen()
    if not namen:
        return False
    schluessel = normalisiere(text)
    if not schluessel:
        return False
    return any(kandidat in namen for kandidat in _kandidaten(schluessel))


__all__ = [
    "DATEN",
    "anzahl",
    "ist_strasse",
    "normalisiere",
    "quellen",
    "stand",
    "verfuegbar",
]
