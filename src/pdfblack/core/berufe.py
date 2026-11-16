"""Deutsche Berufsbezeichnungen - sie werden nicht geschwaerzt.

Die Liste (``data/berufe.json``) kommt aus Wikidata (CC0) und einer eigenen
Liste gaengiger Berufe und Rollen; weibliche Formen sind enthalten.

Neu bauen: ``python tools/build_berufe_data.py``
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DATEN = Path(__file__).resolve().parents[1] / "data" / "berufe.json"


def normalisiere(text: str) -> str:
    """Vergleichsform: klein, ohne Zusaetze wie ``(m/w/d)``, ohne Satzzeichen."""
    text = re.sub(r"\(.*?\)", " ", str(text).lower())
    text = re.sub(r"[^\wäöüß\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _berufe() -> frozenset[str]:
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - nur bei kaputtem Build
        LOGGER.warning("Berufsliste fehlt oder ist unlesbar (%s): %s", DATEN, exc)
        return frozenset()
    return frozenset(str(eintrag) for eintrag in daten.get("berufe", ()))


@lru_cache(maxsize=1)
def _einzelwoerter() -> frozenset[str]:
    return frozenset(eintrag for eintrag in _berufe() if " " not in eintrag)


def verfuegbar() -> bool:
    return bool(_berufe())


def anzahl() -> int:
    return len(_berufe())


def ist_beruf(text: str) -> bool:
    """Ist dieser Text (nur) eine Berufsbezeichnung?"""
    return normalisiere(text) in _berufe()


# Woerter, die Beruf und haeufiger Nachname zugleich sind ("Herr Mueller",
# "Frau Koch"). Sie duerfen weiter als Name gelten, sonst wuerde der Name
# nicht im ganzen Dokument gefunden.
_AUCH_NACHNAME = frozenset(
    {
        "müller", "mueller", "koch", "schreiner", "bäcker", "baecker",
        "fischer", "wagner", "schuster", "metzger", "schmied", "kaufmann",
        "richter", "vogt", "zimmermann", "maurer", "jäger", "jaeger",
        "förster", "foerster", "kellner", "krämer", "kraemer", "bader",
        "weber", "schneider", "glaser", "pfeiffer", "sattler", "töpfer",
        "toepfer", "küfer", "feger", "hüter", "hueter",
    }
)


def ist_berufswort(wort: str) -> bool:
    """Ist dieses einzelne Wort eine Berufsbezeichnung?

    Nachnamen, die zugleich einen Beruf bezeichnen ("Müller"), bleiben
    ausgenommen.
    """
    klein = normalisiere(wort)
    if klein in _AUCH_NACHNAME:
        return False
    return klein in _einzelwoerter()


def quellen() -> list[str]:
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return []
    return [str(eintrag) for eintrag in daten.get("quellen", ())]
