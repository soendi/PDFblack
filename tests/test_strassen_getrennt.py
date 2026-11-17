"""Tests fuer aufgeteilt geschriebene Strassennamen ("Haupt strasse 56 a")."""

from __future__ import annotations

import re

import pymupdf
import pytest

from pdfblack.core import rules
from pdfblack.core.detect import DetectionOptions, Finding, run_detection
from pdfblack.core.models import Category


def _treffer(tmp_path, zeile: str) -> list[Finding]:
    quelle = tmp_path / "adresse.pdf"
    doc = pymupdf.open()
    seite = doc.new_page()
    seite.insert_text((50, 80), zeile, fontname="helv", fontsize=12)
    doc.save(str(quelle))
    doc.close()
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("address",))
    )
    return list(ergebnis.findings)


def _adressen(tmp_path, zeile: str) -> list[str]:
    return [f.text for f in _treffer(tmp_path, zeile) if f.category is Category.ADDRESS]


@pytest.mark.parametrize(
    "zeile",
    [
        "Haupt strasse 56 a",
        "Haupt str. 56 a",
        "Dorf strasse 7 a",
        "Bahnhof strasse 7",
    ],
)
def test_aufgeteilte_strasse_wird_gefunden(tmp_path, zeile):
    treffer = _adressen(tmp_path, zeile)
    assert any(" ".join(zeile.split()) == " ".join(t.split()) for t in treffer), treffer


def test_zusammengeschriebene_form_bleibt_erhalten(tmp_path):
    treffer = _adressen(tmp_path, "Hauptstr. 56 a")
    assert any("Hauptstr" in t for t in treffer), treffer


def test_unbekannter_name_wird_nicht_zur_adresse(tmp_path):
    """"Am Weg 5" steht nicht im Verzeichnis, die Regel greift nicht."""
    quellen = [f.source for f in _treffer(tmp_path, "Am Weg 5")]
    assert not [q for q in quellen if "aufgeteilt" in q], quellen


def test_grossschreibung_wird_erkannt(tmp_path):
    """Der Scan liefert Adressen auch in Grossbuchstaben."""
    treffer = [f.text for f in _treffer(tmp_path, "HAUPT STRASSE 56 a")]
    assert any("STRASSE" in t for t in treffer), treffer
    quellen = [f.source for f in _treffer(tmp_path, "HAUPT STRASSE 56 a")]
    assert any("aufgeteilt" in q for q in quellen), quellen


@pytest.mark.parametrize(
    "zeile", ["Hauptpl. 5", "Haupt pl. 5", "Haupt pl 5", "Dorfpl. 7", "Dorf pl. 7"]
)
def test_platz_abkuerzung_wird_gefunden(tmp_path, zeile):
    """"pl." ist die Abkuerzung fuer "platz", allein und aufgeteilt."""
    treffer = _adressen(tmp_path, zeile)
    assert any("pl" in t.casefold() for t in treffer), treffer


@pytest.mark.parametrize("zeile", ["Dorf platz 7", "Haupt weg 5", "Dorf gasse 3"])
def test_haeufige_endung_bleibt_getrennt_suchbar(tmp_path, zeile):
    """Endungen mit vielen Verzeichnis-Eintraegen bleiben in der Regel."""
    quellen = [f.source for f in _treffer(tmp_path, zeile)]
    assert any("aufgeteilt" in q for q in quellen), quellen


@pytest.mark.parametrize(
    ("zeile", "erwartet"),
    [
        ("wohnhaft in der Haupt strasse", "Haupt strasse"),
        ("wohnhaft in der Haupt str.", "Haupt str."),
        ("wohnhaft in der Dorf pl.", "Dorf pl."),
    ],
)
def test_aufgeteilte_strasse_ohne_hausnummer(tmp_path, zeile, erwartet):
    """Auch ohne Hausnummer wird der aufgeteilte Name gefunden."""
    treffer = [" ".join(t.split()) for t in _adressen(tmp_path, zeile)]
    assert erwartet in treffer, treffer


def test_mit_hausnummer_bleibt_der_lange_treffer(tmp_path):
    """Der laengere Treffer mit Hausnummer verdraengt den Namen allein."""
    treffer = [" ".join(t.split()) for t in _adressen(tmp_path, "Haupt strasse 56 a")]
    assert "Haupt strasse 56 a" in treffer, treffer
    assert "Haupt strasse" not in treffer, treffer


def test_unbekannter_name_ohne_hausnummer(tmp_path):
    quellen = [f.source for f in _treffer(tmp_path, "Am Weg")]
    assert not [q for q in quellen if "aufgeteilt" in q], quellen


def test_endungen_sind_abgeleitet():
    """Die getrennte Schreibweise nutzt dieselbe Endungsliste, nur gefiltert."""
    assert rules._STREET_SUFFIX_ZU_ALLGEMEIN <= set(rules._STREET_SUFFIXE)
    for endung in rules._STREET_SUFFIXE:
        assert re.fullmatch(rules._STREET_SUFFIX, endung), endung
        getrennt = re.fullmatch(rules._STREET_SUFFIX_WORT, endung) is not None
        assert getrennt == (endung not in rules._STREET_SUFFIX_ZU_ALLGEMEIN), endung
