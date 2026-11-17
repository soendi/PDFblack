"""Schweizer Namensverzeichnis: Vornamen und Nachnamen.

Die Listen (``data/namen_ch.json``) stammen vom Bundesamt fuer Statistik
(OPEN-BY, Quellenangabe Pflicht): Vor- und Nachnamen der staendigen
Wohnbevoelkerung, wie sie schweizweit mindestens dreimal vorkommen - in allen
Landessprachen und Schreibweisen.

Damit laesst sich ein Name bestaetigen, den die Heuristik sonst als Sachwort
oder Strassenname verwirft ("Goldberg" ist ein Nachname, keine Strasse).

Neu bauen: ``python tools/build_namen_data.py``
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DATEN = Path(__file__).resolve().parents[1] / "data" / "namen_ch.json"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _ohne_akzente(text: str) -> str:
    zerlegt = unicodedata.normalize("NFKD", text)
    return "".join(zeichen for zeichen in zerlegt if not unicodedata.combining(zeichen))


def normalisiere(text: str) -> str:
    """Vergleichsform eines Namens.

    Klein, Umlaute als ae/oe/ue, ohne Akzente. Bindestrich und Apostroph
    bleiben, weil sie zum Namen gehoeren ("Müller-Lüdenscheidt", "O'Brien").
    """
    text = str(text).strip().lower().translate(_UMLAUTE)
    text = _ohne_akzente(text)
    text = re.sub(r"[^a-z0-9'\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -'")


@lru_cache(maxsize=1)
def _listen() -> tuple[frozenset[str], frozenset[str]]:
    """Vornamen und Nachnamen in Vergleichsschreibweise."""
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - nur bei kaputtem Build
        LOGGER.warning("Namensverzeichnis fehlt oder ist unlesbar (%s): %s", DATEN, exc)
        return frozenset(), frozenset()
    vornamen = frozenset(str(eintrag) for eintrag in daten.get("vornamen", ()))
    nachnamen = frozenset(str(eintrag) for eintrag in daten.get("nachnamen", ()))
    return vornamen, nachnamen


def verfuegbar() -> bool:
    vornamen, nachnamen = _listen()
    return bool(vornamen or nachnamen)


def anzahl() -> tuple[int, int]:
    """Anzahl der Vornamen und der Nachnamen."""
    vornamen, nachnamen = _listen()
    return len(vornamen), len(nachnamen)


def stand() -> str:
    """Stand der Listen, z. B. ``2025``."""
    try:
        return str(json.loads(DATEN.read_text(encoding="utf-8")).get("stand", ""))
    except (OSError, ValueError):  # pragma: no cover
        return ""


def quellen() -> list[str]:
    """Herkunft und Lizenz der Listen (fuer den Ueber-Dialog)."""
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return []
    return [str(eintrag) for eintrag in daten.get("quellen", ())]


def ist_vorname(text: str) -> bool:
    schluessel = normalisiere(text)
    return bool(schluessel) and schluessel in _listen()[0]


def ist_nachname(text: str) -> bool:
    schluessel = normalisiere(text)
    return bool(schluessel) and schluessel in _listen()[1]


def ist_name(text: str) -> bool:
    """Ist der Text ein Vor- oder Nachname?

    Mehrere Woerter gelten nur dann als Name, wenn jedes einzelne im
    Verzeichnis steht ("Joana Wittler"), damit "Hans Kalkulation" keiner ist.
    """
    schluessel = normalisiere(text)
    if not schluessel:
        return False
    vornamen, nachnamen = _listen()
    if schluessel in vornamen or schluessel in nachnamen:
        return True
    teile = schluessel.split()
    return len(teile) > 1 and all(teil in vornamen or teil in nachnamen for teil in teile)


__all__ = [
    "DATEN",
    "anzahl",
    "ist_name",
    "ist_nachname",
    "ist_vorname",
    "normalisiere",
    "quellen",
    "stand",
    "verfuegbar",
]
