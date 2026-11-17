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


# Allgemeine Rollen, die allein nichts ueber den Beruf sagen: "Mustermeister"
# ist kein Beruf, nur weil "Meister" darin steckt.
_ZU_ALLGEMEIN = frozenset(
    {
        "meister", "meisterin", "geselle", "gesellin", "helfer", "helferin",
        "fachmann", "fachfrau", "lehrling", "praktikant", "praktikantin",
        "kraft", "hilfskraft", "azubi",
    }
)


@lru_cache(maxsize=1)
def _berufsteile() -> frozenset[str]:
    """Berufsworte, die auch in einem zusammengesetzten Wort gelten.

    Sehr kurze Eintraege der Liste ("rat", "fax") und allgemeine Rollen
    taugen nicht als Teilwort.
    """
    return frozenset(
        eintrag
        for eintrag in _einzelwoerter()
        if len(eintrag) >= 4
        and eintrag not in _ZU_ALLGEMEIN
        and eintrag not in _AUCH_NACHNAME
    )


def verfuegbar() -> bool:
    return bool(_berufe())


def anzahl() -> int:
    return len(_berufe())


def ist_beruf(text: str) -> bool:
    """Ist dieser Text (nur) eine Berufsbezeichnung?"""
    klein = normalisiere(text)
    if klein in _berufe():
        return True
    if " " in klein:
        return False
    return _aus_beruf(klein) or _als_zusammensetzung(klein)


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


# Zusaetze, die aus einem Beruf eine Steigerung machen: "Dachdecker" ->
# "Dachdeckermeister", "Dachdeckerin" -> "Dachdeckermeisterin". Laengere
# Zusaetze stehen vorn, damit "Dachdeckergeselle" nicht an "gesell" haengen
# bleibt.
_ZUSATZ = (
    "meisterin",
    "meister",
    "gesellin",
    "geselle",
    "helferin",
    "helfer",
    "fachfrau",
    "fachmann",
    "lehrling",
)


def _als_zusammensetzung(klein: str) -> bool:
    """Steckt ein Beruf in einem zusammengesetzten Wort?

    "Dachdeckerhandwerk" und "Dachdeckerbetrieb" enthalten "Dachdecker" und
    gelten damit als Berufsbezeichnung. Berufe, die zugleich haeufiger
    Nachname sind ("Maurer", "Koch"), zaehlen dabei nicht mit, und
    zusammengesetzte Namen mit Bindestrich ("Schmidt-Lorenz") bleiben Namen.
    """
    if "-" in klein:
        return False
    teile = _berufsteile()
    for start in range(len(klein)):
        for ende in range(start + 4, len(klein) + 1):
            if klein[start:ende] in teile:
                return True
    return False


def _aus_beruf(klein: str) -> bool:
    """Beruf mit Zusatz, z. B. "dachdeckermeisterin"?"""
    for zusatz in _ZUSATZ:
        if not klein.endswith(zusatz):
            continue
        stamm = klein[: -len(zusatz)]
        if len(stamm) >= 4 and stamm in _einzelwoerter():
            return True
    return False


def ist_berufswort(wort: str) -> bool:
    """Ist dieses einzelne Wort eine Berufsbezeichnung?

    Nachnamen, die zugleich einen Beruf bezeichnen ("Müller"), bleiben
    ausgenommen.
    """
    klein = normalisiere(wort)
    if klein in _AUCH_NACHNAME:
        return False
    if klein in _einzelwoerter():
        return True
    return _aus_beruf(klein) or _als_zusammensetzung(klein)


def quellen() -> list[str]:
    try:
        daten = json.loads(DATEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return []
    return [str(eintrag) for eintrag in daten.get("quellen", ())]
