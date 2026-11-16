"""Rechtschreibpruefung fuer den OCR-Text.

Erkannte Woerter werden gegen ein deutsches Woerterbuch geprueft (rund 339 000
Woerter, Bibliothek ``pyspellchecker``, MIT-Lizenz) und **nur dann** korrigiert,
wenn das gefahrlos ist:

* nur klein geschriebene Einzelwoerter (Namen, Strassen, Firmen sind im
  Deutschen gross geschrieben und bleiben unangetastet),
* nur Woerter, die im Dokument **einmal** vorkommen (ein wiederholtes Wort ist
  eher ein Eigenname als ein Tippfehler),
* nur wenn es genau eine nahe Korrektur gibt.

Der Text sitzt unsichtbar hinter dem Bild; eine falsche Korrektur wuerde die
Schwaerzung nicht verschieben, aber einen Namen unauffindbar machen. Darum
lieber seltener korrigieren als raten.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Sequence

LOGGER = logging.getLogger(__name__)

# Nur solche Woerter kommen infrage: klein, ohne Ziffern, keine Bindestriche.
_WORT = re.compile(r"^[a-zäöüß]{5,30}$")


@lru_cache(maxsize=1)
def _pruefer():
    """Deutsches Woerterbuch laden (None, wenn die Bibliothek fehlt)."""
    try:
        from spellchecker import SpellChecker
    except Exception as exc:  # noqa: BLE001 - OCR soll auch ohne laufen
        LOGGER.warning("Rechtschreibpruefung nicht verfuegbar: %s", exc)
        return None
    try:
        return SpellChecker(language="de", distance=1)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Deutsches Woerterbuch liess sich nicht laden: %s", exc)
        return None


def verfuegbar() -> bool:
    return _pruefer() is not None


@lru_cache(maxsize=20000)
def _korrektur(wort: str) -> str | None:
    pruefer = _pruefer()
    if pruefer is None:
        return None
    if wort in pruefer:
        return None
    return pruefer.correction(wort)


def korrigiere_wort(wort: str, anzahl: int = 1) -> str:
    """Ein einzelnes Wort pruefen und gegebenenfalls korrigieren."""
    if anzahl > 1 or not _WORT.match(wort):
        return wort
    vorschlag = _korrektur(wort)
    if not vorschlag or vorschlag == wort:
        return wort
    # Nur uebernehmen, wenn der Vorschlag wirklich ein Wort ist.
    pruefer = _pruefer()
    if pruefer is None or vorschlag not in pruefer:
        return wort
    return vorschlag


def korrigiere(woerter: Sequence[str], haeufigkeiten: dict[str, int] | None = None) -> list[str]:
    """Liste von Woertern korrigieren (Haeufigkeit im Dokument beruecksichtigen)."""
    haeufigkeiten = haeufigkeiten or {}
    return [
        korrigiere_wort(wort, haeufigkeiten.get(wort, 1)) for wort in woerter
    ]
