"""Tests fuer Adressen mit Ort, fuenfstellige PLZ und abgeschnittene IBANs.

Geprueft wird, was in echten Zeugnissen schiefging: Hausnummer und Ort stehen
in eigenen Textbloecken (Tabelle, rechtsbuendige Nummer), hinter der
Hausnummer folgt der Ort ohne Komma, fuenfstellige PLZ stehen in Spalten, und
die IBAN laeuft ueber einen Zeilenumbruch.
"""

from __future__ import annotations

import pymupdf

from pdfblack.core.detect import DetectionOptions, run_detection
from pdfblack.core.models import Category
from pdfblack.core.rules import ALL_GROUPS


def _pdf(pfad, zeilen):
    """PDF schreiben; eine Liste von Woertern wird als Spaltenzeile gesetzt."""
    doc = pymupdf.open()
    seite = doc.new_page(width=595, height=842)
    y = 80
    for zeile in zeilen:
        if isinstance(zeile, list):
            x = 50
            for wort in zeile:
                seite.insert_text((x, y), wort, fontsize=11, fontname="helv")
                x += max(58, 7 * len(wort) + 18)
        else:
            seite.insert_text((50, y), zeile, fontsize=11, fontname="helv")
        y += 22
    doc.save(str(pfad))
    doc.close()
    return str(pfad)


def _formular(pfad, felder):
    """Felder wie in einem Formular: jedes Feld ein eigener Textblock."""
    doc = pymupdf.open()
    seite = doc.new_page(width=595, height=842)
    for x, y, text in felder:
        seite.insert_text((x, y), text, fontsize=11, fontname="helv")
    doc.save(str(pfad))
    doc.close()
    return str(pfad)


def _findings(pfad, zeilen):
    quelle = _pdf(pfad, zeilen)
    return run_detection(
        quelle, DetectionOptions(use_ai=False, rule_groups=ALL_GROUPS)
    ).findings


def _texte(findings, kategorie=None):
    return [f.text for f in findings if kategorie is None or f.category is kategorie]


def test_hausnummer_mit_ort_ohne_komma(tmp_path):
    """\"Musterstrasse 12 Zuerich\": die Hausnummer gehoert zur Adresse."""
    findings = _findings(
        tmp_path / "ort.pdf",
        ["Musterstrasse 12 Zürich", "Bahnhofstrasse 7 Bern"],
    )
    adressen = _texte(findings, Category.ADDRESS)
    assert "Musterstrasse 12" in adressen
    assert "Bahnhofstrasse 7" in adressen
    # Der Ort selbst ist keine Adresse und bleibt fuer die PLZ/Ort-Regel frei.
    assert not any("Zürich" in text for text in adressen)


def test_ort_hinter_der_hausnummer_ist_kein_freischein(tmp_path):
    """Woerter, die nur wie ein Ort aussehen, machen keine Adresse."""
    findings = _findings(
        tmp_path / "kein_ort.pdf",
        [
            "Bahnhof 5 Personen",
            "Vorarbeiterin von 10 Dachdecker",
            # "Zuege" ist nur der Anfang von "Zuegen" und kein Ortsname.
            "Bahnhof 5 Züge",
        ],
    )
    adressen = _texte(findings, Category.ADDRESS)
    assert not any("Personen" in text for text in adressen)
    assert not any("Dachdecker" in text for text in adressen)
    assert not any("Züge" in text or "Bahnhof 5" in text for text in adressen), adressen


def test_hausnummer_und_ort_in_eigenen_spalten(tmp_path):
    """Rechtsbuendige Hausnummer und PLZ stehen in eigenen Textbloecken."""
    findings = _findings(
        tmp_path / "spalten.pdf",
        [["Seestrasse", "7", "CH-8000", "Zürich"]],
    )
    assert "Seestrasse 7" in _texte(findings, Category.ADDRESS)
    assert "CH-8000 Zürich" in _texte(findings, Category.POSTAL)


def test_hausnummer_und_ort_in_weit_getrennten_feldern(tmp_path):
    """Strasse, Hausnummer, PLZ und Ort stehen in eigenen, weit entfernten Feldern.

    "Wolfsbachstrasse" allein wurde gefunden, "Wolfsbachstrasse 6" nicht, weil
    zwischen Name und Nummer ein Zeilenumbruch lag. Ebenso verschwand
    "9436 Balgach", wenn PLZ und Ort in zwei Feldern standen.
    """
    quelle = _formular(
        tmp_path / "formular.pdf",
        [
            (50, 100, "Wolfsbachstrasse"),
            (330, 100, "6"),
            (50, 140, "9436"),
            (330, 140, "Balgach"),
        ],
    )
    findings = run_detection(
        quelle, DetectionOptions(use_ai=False, rule_groups=ALL_GROUPS)
    ).findings
    assert "Wolfsbachstrasse 6" in _texte(findings, Category.ADDRESS)
    assert "9436 Balgach" in _texte(findings, Category.POSTAL)


def test_zahl_am_datumsanfang_ist_keine_hausnummer(tmp_path):
    """"Eintritt 01.09.2020" ist ein Datum, keine Adresse "Eintritt 01"."""
    findings = _findings(
        tmp_path / "datum_keine_nr.pdf",
        [
            "Eintritt 01.09.2020",
            "Zeugnis 12.03.2026",
            "Geburt 5.2.90",
            # Ein Hausnummernbereich bleibt eine Hausnummer.
            "Hauptstrasse 12-14",
        ],
    )
    adressen = _texte(findings, Category.ADDRESS)
    assert not any(
        "Eintritt" in text or "Zeugnis" in text or "Geburt" in text
        for text in adressen
    ), adressen
    assert "Hauptstrasse 12-14" in adressen
    daten = _texte(findings, Category.DATE) + _texte(findings, Category.BIRTHDATE)
    assert "01.09.2020" in daten
    assert "12.03.2026" in daten


def test_fuenfstellige_plz_mit_ort(tmp_path):
    """Deutsche PLZ mit angehaengter Ortschaft, auch in Spalten."""
    findings = _findings(
        tmp_path / "plz5.pdf",
        ["82140 Olching", "D-82140 Olching", ["82140", "Olching"]],
    )
    plz = [text for text in _texte(findings, Category.POSTAL) if "Olching" in text]
    assert len(plz) == 3, plz
    assert all(text.startswith("82140") for text in plz)
    # Fuenfstellige Nummern sind vollstaendig: aus 82140 wird keine 8214.
    assert not any("8214 Olching" in text for text in plz)


def test_iban_ueber_zeilenumbruch(tmp_path):
    """Die letzten Zeichen einer umbrochenen IBAN bleiben nicht offen."""
    findings = _findings(
        tmp_path / "iban_umbruch.pdf",
        ["IBAN: DE89 3704 0044", "0532 0130 00"],
    )
    bank = _texte(findings, Category.BANK)
    assert bank == ["DE89 3704 0044 0532 0130 00"], bank
    assert all(f.hinweis == "" for f in findings if f.category is Category.BANK)


def test_iban_in_spalten(tmp_path):
    findings = _findings(
        tmp_path / "iban_spalten.pdf",
        [["DE89", "3704", "0044", "0532", "0130", "00"]],
    )
    assert _texte(findings, Category.BANK) == ["DE89 3704 0044 0532 0130 00"]


def test_abgeschnittene_iban_wird_nicht_erfunden(tmp_path):
    """Ohne Fortsetzung bleibt die abgeschnittene Nummer, wie sie ist."""
    findings = _findings(tmp_path / "iban_kurz.pdf", ["DE89 3704 0044 0532"])
    bank = [f for f in findings if f.category is Category.BANK]
    assert [f.text for f in bank] == ["DE89 3704 0044 0532"]
    assert bank[0].hinweis == "IBAN-Pruefziffer stimmt nicht"
