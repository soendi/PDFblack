"""Berufsbezeichnungen: Liste, Namensfilter und Adress-Regel."""

from __future__ import annotations

import pymupdf

from pdfblack.core import berufe
from pdfblack.core.detect import DetectionOptions, name_tokens, run_detection


def texts(findings) -> list[str]:
    return [finding.text for finding in findings]


def test_berufsliste_ist_vorhanden():
    assert berufe.verfuegbar()
    assert berufe.anzahl() > 5000
    assert any("Wikidata" in quelle for quelle in berufe.quellen())


def test_bekannte_berufe_und_ihre_weibliche_form():
    for titel in (
        "Dachdecker",
        "Dachdeckerin",
        "Vorarbeiter",
        "Vorarbeiterin",
        "Staplerfahrer",
        "Staplerfahrerin",
        "Praktikantin",
        "Sachbearbeiterin",
        "Elektrikerin",
        "Köchin",
        "Teamleiterin",
    ):
        assert berufe.ist_beruf(titel), titel
    # Zusaetze wie (m/w/d) aendern nichts.
    assert berufe.ist_beruf("Dachdecker (m/w/d)")
    assert berufe.ist_beruf("dachdeckerin")
    # Namen und Firmen sind keine Berufe.
    assert not berufe.ist_beruf("Mustermann")
    assert not berufe.ist_beruf("Muster AG")


def test_beruf_ist_kein_namensbestandteil():
    assert name_tokens("Dachdecker") == set()
    assert name_tokens("Vorarbeiterin") == set()
    assert name_tokens("Max Mustermann") == {"Max", "Mustermann"}


def test_nummer_mit_wort_dahinter_ist_keine_adresse(tmp_path):
    """„Vorarbeiterin von 10 Dachdecker“ ist keine Adresse."""
    path = tmp_path / "adressen.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    zeilen = [
        "Vorarbeiterin von 10 Dachdecker",
        "Musterweg 5",
        "Musterweg 5, 8000 Zürich",
        "Musterweg 5 in 8000 Zürich",
        "Hauptstraße 12 Telefon 089 1234",
        "Am Markt 7",
    ]
    for index, zeile in enumerate(zeilen):
        page.insert_text((60, 100 + index * 22), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address",)),
    )
    gefunden = texts(result.findings)

    assert "Am Markt 7" in gefunden
    # Alle drei Schreibweisen (allein, mit Komma, im Satz) ergeben eine Adresse.
    assert gefunden.count("Musterweg 5") == 3, gefunden
    # Ein ganzes Wort nach der Nummer macht daraus keine Adresse.
    assert not any("Vorarbeiterin" in item for item in gefunden), gefunden
    assert not any(item.startswith("Hauptstraße 12") for item in gefunden), gefunden


def test_berufsbezeichnung_wird_nicht_erkannt(tmp_path):
    """Ein Beruf taucht in keinem Treffer auf - weder als Ort noch als Name."""
    path = tmp_path / "beruf.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    zeilen = [
        "Lebenslauf",
        "Vorarbeiterin von 10 Dachdecker",
        "Als Dachdeckerin auf Grossbaustellen tätig.",
        "Beruf: Dachdecker",
    ]
    for index, zeile in enumerate(zeilen):
        page.insert_text((60, 100 + index * 22), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(
            use_ai=False,
            ai_entities=(),
            rule_groups=("address", "ch_postal", "date"),
        ),
    )
    for finding in result.findings:
        assert "Dachdecker" not in finding.text, finding.text
        assert "Vorarbeiter" not in finding.text, finding.text
