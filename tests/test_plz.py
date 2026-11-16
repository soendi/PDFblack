"""Die amtliche PLZ-Liste und ihre Pruefungen."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import plz  # noqa: E402


def test_liste_ist_vorhanden():
    assert plz.verfuegbar()
    assert plz.anzahl() > 3000
    assert plz.stand() == "2026-11"
    assert any("swisstopo" in quelle for quelle in plz.quellen())


def test_bekannte_postleitzahlen():
    for code in ("1000", "1950", "2000", "3000", "8000", "8045", "9435", "9490"):
        assert plz.is_postal_code(code), code
    # Keine PLZ: Jahreszahlen ohne Ortschaft, Betraege, Nummernkreise.
    # (2024 dagegen ist eine echte PLZ bei Neuchatel, 2026 gibt es nicht.)
    for zahl in ("1500", "2026", "4711", "77120", "0000"):
        assert not plz.is_postal_code(zahl), zahl


def test_orte_passen_zur_plz():
    assert plz.is_place("1950", "Sion")
    assert plz.is_place("1950", "Sitten")  # deutscher Name derselben Stadt
    assert plz.is_place("2000", "Neuchâtel")
    assert plz.is_place("2000", "Neuenburg")
    assert plz.is_place("8000", "Zürich")
    assert plz.is_place("8000", "Zuerich")
    assert plz.is_place("8000", "zurich")
    assert plz.is_place("9430", "st. margrethen")
    assert plz.is_place("1204", "Genf")
    assert not plz.is_place("8000", "Muster")
    assert not plz.is_place("1950", "Zürich")
    assert not plz.is_place("2026", "Bern")


def test_plz_und_ort_aus_treffer():
    assert plz.plz_vor_ort("1950 Sion") == ("1950", "Sion")
    assert plz.plz_vor_ort("CH-8045 Zürich") == ("8045", "Zürich")
    assert plz.plz_vor_ort("9435\nHeerbrugg") == ("9435", "Heerbrugg")
    assert plz.plz_vor_ort("ohne Zahl") is None


def test_build_nimmt_die_liste_mit():
    """Ohne Datendatei im Paket erkennt PDFblack keine Schweizer PLZ mehr."""
    spec = (Path(__file__).resolve().parents[1] / "packaging" / "pdfblack.spec").read_text(
        encoding="utf-8"
    )
    assert "plz_ch.json" in spec
