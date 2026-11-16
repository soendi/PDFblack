"""Woerterbuch-Korrektur fuer den OCR-Text."""

from __future__ import annotations

import pytest

from pdfblack.core import rechtschreibung


class StubChecker:
    """Woerterbuch für Tests: kennt wenige Woerter und einen Tippfehler."""

    WORTSCHATZ = {"bewerbung", "dachdecker", "kenntnisse", "tätig", "lebenslauf"}
    VORSCHLAEGE = {"bewerbng": "bewerbung", "kentnisse": "kenntnisse"}

    def __contains__(self, wort: str) -> bool:
        return wort in self.WORTSCHATZ

    def correction(self, wort: str) -> str | None:
        return self.VORSCHLAEGE.get(wort)


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(rechtschreibung, "_pruefer", lambda: StubChecker())
    rechtschreibung._korrektur.cache_clear()
    yield
    rechtschreibung._korrektur.cache_clear()


def test_tippfehler_wird_korrigiert(stub):
    assert rechtschreibung.korrigiere_wort("bewerbng") == "bewerbung"
    assert rechtschreibung.korrigiere_wort("kentnisse") == "kenntnisse"


def test_richtige_und_unbekannte_woerter_bleiben(stub):
    assert rechtschreibung.korrigiere_wort("bewerbung") == "bewerbung"
    # Kein Vorschlag: das Wort bleibt, wie es ist (z. B. ein Name).
    assert rechtschreibung.korrigiere_wort("musterweg") == "musterweg"


def test_grossgeschriebenes_bleibt_stehen(stub):
    """Namen, Strassen und Firmen sind gross geschrieben und bleiben unangetastet."""
    for wort in ("Bewerbng", "Musterweg", "Schmidt-Lorenz", "Muster AG"):
        assert rechtschreibung.korrigiere_wort(wort) == wort


def test_kurze_woerter_und_zahlen_bleiben(stub):
    for wort in ("tätg", "4711", "a1b2c", "pe-8842", "zürich"):
        assert rechtschreibung.korrigiere_wort(wort) == wort


def test_wiederholte_woerter_bleiben_stehen(stub):
    """Ein Wort, das im Dokument mehrfach vorkommt, ist eher ein Eigenname."""
    assert rechtschreibung.korrigiere_wort("bewerbng", anzahl=3) == "bewerbng"
    assert rechtschreibung.korrigiere_wort("bewerbng", anzahl=1) == "bewerbung"


def test_echtes_woerterbuch_korrigiert_deutsche_tippfehler():
    if not rechtschreibung.verfuegbar():
        pytest.skip("pyspellchecker ist nicht installiert")
    assert rechtschreibung.korrigiere_wort("bewerbng") == "bewerbung"
    assert rechtschreibung.korrigiere_wort("dachdeker") == "dachdecker"
    # Ein Eigenname ohne Woerterbuch-Eintrag bleibt unveraendert.
    assert rechtschreibung.korrigiere_wort("heubrugg") == "heubrugg"
