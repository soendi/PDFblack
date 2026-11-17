"""Tests fuer die Plausibilitaetspruefung (IBAN, Datum, PLZ, Strasse)."""

from __future__ import annotations

import pymupdf

from pdfblack.core import plausibel
from pdfblack.core.detect import DetectionOptions, run_detection
from pdfblack.core.models import Category


def test_iban_pruefziffer():
    assert plausibel.iban_gueltig("DE89 3704 0044 0532 0130 00") is True
    assert plausibel.iban_gueltig("DE89 3704 0044 0532 0130 01") is False
    assert plausibel.iban_gueltig("0814 342") is None


def test_datum_wird_geprueft():
    assert plausibel.datum_gueltig("09.01.2022") is True
    assert plausibel.datum_gueltig("31.02.2022") is False
    assert plausibel.datum_gueltig("09.0.2022") is False
    assert plausibel.datum_gueltig("01.01.1800") is False
    assert plausibel.datum_gueltig("Kapitel 3") is None


def test_plz_und_ort():
    assert plausibel.hinweis("8200 Schaffhausen", Category.POSTAL) == ""
    assert "steht nicht" in plausibel.hinweis("9999 Nirgendwo", Category.POSTAL)
    assert "gehoert nicht" in plausibel.hinweis("8200 Olching", Category.POSTAL)
    # Fuenfstellig: dafuer gibt es keine Schweizer Liste, also kein Hinweis.
    assert plausibel.hinweis("82140 Olching", Category.POSTAL) == ""


def test_strasse_gegen_verzeichnis():
    assert plausibel.hinweis("Hauptstrasse 56 a", Category.ADDRESS, "street") == ""
    assert plausibel.hinweis("Haupt strasse 56 a", Category.ADDRESS, "street_split") == ""
    assert "steht nicht" in plausibel.hinweis(
        "Saegmuehlstrasse 25 a", Category.ADDRESS, "street"
    )
    # Ein Hausnummern-Treffer ohne Strassenregel wird nicht geprueft.
    assert plausibel.hinweis("Beispiel 5", Category.ADDRESS, "house_number") == ""


def test_pipeline_setzt_hinweis(tmp_path):
    quelle = tmp_path / "bank.pdf"
    doc = pymupdf.open()
    seite = doc.new_page()
    seite.insert_text(
        (50, 80), "IBAN: DE89 3704 0044 0532 0130 00", fontname="helv", fontsize=11
    )
    seite.insert_text(
        (50, 110), "IBAN: DE89 3704 0044 0532 0130 01", fontname="helv", fontsize=11
    )
    doc.save(str(quelle))
    doc.close()

    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("bank",))
    )
    hinweise = {
        finding.text.replace(" ", ""): finding.hinweis
        for finding in ergebnis.findings
        if finding.category is Category.BANK
    }
    assert hinweise.get("DE89370400440532013000", "") == ""
    assert "Pruefziffer" in hinweise.get("DE89370400440532013001", "")
