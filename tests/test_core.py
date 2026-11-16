"""Kurztests fuer Erkennung und Schwärzung (ohne Oberflaeche)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from make_sample import build  # noqa: E402

from pdfblack.core.detect import (  # noqa: E402
    DetectionOptions,
    ManualTerm,
    RegexSpec,
    _ai_location_is_date,
    get_analyzer,
    name_tokens,
    run_detection,
    term_pattern,
)
from pdfblack.core.models import Category  # noqa: E402
from pdfblack.core.redact import apply_redactions  # noqa: E402
from pdfblack.core.rules import RULES  # noqa: E402


@pytest.fixture(scope="module")
def sample(tmp_path_factory) -> Path:
    return build(tmp_path_factory.mktemp("pdf") / "beispiel.pdf")


def texts(findings) -> list[str]:
    return [f.text for f in findings]


def test_muster_finden_adresse_plz_und_ids(sample):
    result = run_detection(
        str(sample),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "id", "contact")),
    )
    found = texts(result.findings)
    assert any("Königsallee 42" in item for item in found)
    assert any("80331 München" in item for item in found)
    assert any("4711-2233" in item for item in found)
    assert any("maximiliane.schmidt@example.de" in item for item in found)
    assert all(f.rects for f in result.findings)


def test_manuelle_werte_und_regex(sample):
    options = DetectionOptions(
        use_ai=False,
        ai_entities=(),
        rule_groups=(),
        manual_terms=(
            ManualTerm("Nachname", "Schmidt-Lorenz", Category.PERSON),
            ManualTerm("Ort", "München", Category.POSTAL),
        ),
        regexes=(RegexSpec("Akte", r"PE-\d{4}/\d{4}"),),
    )
    result = run_detection(str(sample), options)
    found = texts(result.findings)
    # Der Name steht an drei Stellen: Anschrift, Anrede und Zustellzeile.
    assert found.count("Schmidt-Lorenz") == 3
    assert "München" in found
    assert "PE-8842/2024" in found
    assert all(f.uid for f in result.findings)


def test_ueberlappung_wird_zusammengefasst(sample):
    options = DetectionOptions(
        use_ai=False,
        ai_entities=(),
        rule_groups=(),
        manual_terms=(ManualTerm("Name", "Schmidt-Lorenz", Category.PERSON),),
        regexes=(RegexSpec("Name", r"Maximiliane Schmidt-Lorenz"),),
    )
    result = run_detection(str(sample), options)
    found = texts(result.findings)
    # An der ersten Fundstelle gewinnt der laengere Treffer, Anrede und
    # Zustellzeile bleiben als eigene, nicht ueberlappende Treffer erhalten.
    assert found.count("Maximiliane Schmidt-Lorenz") == 1
    assert found.count("Schmidt-Lorenz") == 2


def test_ungueltiger_regex_erzeugt_warnung(sample):
    result = run_detection(
        str(sample),
        DetectionOptions(
            use_ai=False,
            ai_entities=(),
            rule_groups=(),
            regexes=(RegexSpec("kaputt", r"([A-Z"),),
        ),
    )
    assert result.warnings and "ungueltig" in result.warnings[0]


def test_schwaerzen_entfernt_text(sample, tmp_path):
    result = run_detection(
        str(sample),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "id")),
    )
    assert result.findings
    for finding in result.findings:
        if "Königsallee" in finding.text:
            finding.enabled = False

    target = tmp_path / "out.pdf"
    count = apply_redactions(str(sample), str(target), result.findings)
    assert count > 0 and target.exists()

    doc = pymupdf.open(str(target))
    text = doc[0].get_text()
    doc.close()

    assert "4711-2233" not in text
    assert "80331" not in text
    # abgewaehlter Treffer bleibt sichtbar
    assert "Königsallee" in text
    # Originaldatei bleibt unveraendert
    assert "4711-2233" in pymupdf.open(str(sample))[0].get_text()


def _form_pdf(path, fields):
    """PDF mit ausfuellbaren Textfeldern anlegen."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Adressänderung", fontsize=14, fontname="helv")
    for name, value, rect in fields:
        widget = pymupdf.Widget()
        widget.field_name = name
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect = pymupdf.Rect(*rect)
        widget.field_value = value
        page.add_widget(widget)
    doc.save(str(path))
    doc.close()
    return path


def test_formularfelder_werden_erkannt_und_geleert(tmp_path):
    """PLZ und Ort in getrennten Feldern: erkennen und Wert wirklich loeschen."""
    source = _form_pdf(
        tmp_path / "formular.pdf",
        [
            ("strasse", "Musterweg 5", (120, 150, 320, 168)),
            ("plz", "9435", (120, 178, 200, 196)),
            ("ort", "Heerbrugg", (120, 206, 260, 224)),
            # umgekehrte Reihenfolge: Ort vor PLZ
            ("ort2", "St. Margrethen", (320, 178, 460, 196)),
            ("plz2", "9430", (320, 206, 400, 224)),
        ],
    )
    result = run_detection(
        str(source),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "ch_postal")),
    )
    found = texts(result.findings)
    assert any("9435" in item and "Heerbrugg" in item for item in found)
    assert any("9430" in item and "Margrethen" in item for item in found)
    assert any("Musterweg 5" in item for item in found)

    target = tmp_path / "formular_geschwaerzt.pdf"
    count = apply_redactions(str(source), str(target), result.findings)
    assert count > 0

    doc = pymupdf.open(str(target))
    page = doc[0]
    remaining = [w.field_value for w in (page.widgets() or [])]
    rest_text = page.get_text()
    doc.close()
    assert not [value for value in remaining if value], remaining
    for leaking in ("9435", "9430", "Heerbrugg", "Margrethen", "Musterweg"):
        assert leaking not in rest_text, leaking


def test_schweizer_plz_ueber_zeilenumbruch(tmp_path):
    """PLZ und Ort duerfen in getrennten Zeilen stehen."""
    path = tmp_path / "ch_umbruch.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "Musterstrasse 12",
        "9435",
        "Heerbrugg",
        "9430 st. margrethen",
        "Es kostet 1500 Franken.",
        "Von 9435 bis 9440",
        "Vertragsnummer: PE-8842/2024",
        "Personalnummer: 4711-2233",
        "Versichertennummer: 99887766",
    ]
    for index, line in enumerate(lines):
        page.insert_text((60, 100 + index * 24), line, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("ch_postal",)),
    )
    found = texts(result.findings)
    assert any(item.startswith("9435") and "Heerbrugg" in item for item in found)
    assert any(item.startswith("9430") for item in found)
    derived = [item for f, item in zip(result.findings, found) if "\n" in f.text]
    assert not derived, "Zeilenumbrueche gehoeren nicht in den Treffertext"
    assert not any("1500" in item for item in found)
    assert not any("9440" in item for item in found)
    # Nummernkreise wie "PE-8842/2024" oder "4711-2233" sind keine PLZ
    assert not any("-" in item or "/" in item for item in found)


def test_hausnummer_hinter_strassennamen(tmp_path):
    """Hausnummern auch ohne deutsches Strassen-Suffix, ohne Zahlen-Fehler."""
    path = tmp_path / "nr.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "Rue du Lac 12",
        "Unter den Linden 5a",
        "Hafenpromenade 3 a",
        "Am Markt 7",
        "Seite 12 der Anlage",
        "Kapitel 3 und 4",
        "Insgesamt 250 Stück",
        "Durchwahl 089",
        "Ihre Police 44-778 gilt ab morgen",
        "Sie 1'250.00 CHF offen",
    ]
    for index, line in enumerate(lines):
        page.insert_text((60, 100 + index * 20), line, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path), DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address",))
    )
    found = texts(result.findings)
    assert "Rue du Lac 12" in found
    assert "Unter den Linden 5a" in found
    assert "Hafenpromenade 3 a" in found
    assert "Am Markt 7" in found
    # Zahlen hinter Schluesselwoertern sind keine Hausnummern
    assert not any("Seite" in item for item in found)
    assert not any("Kapitel" in item for item in found)
    assert not any("Insgesamt" in item for item in found)
    assert not any("Durchwahl" in item for item in found)
    assert not any("Police" in item for item in found)
    assert not any("Sie 1" in item for item in found)
    # Keine doppelten Treffer fuer dieselbe Stelle
    assert len(found) == len(set(found))


def test_schweizer_plz(tmp_path):
    """Vierstellige PLZ mit CH-Praefix und mit Ort dahinter."""
    path = tmp_path / "ch.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "CH-8045 Zürich",
        "CH 3000 Bern",
        "Postadresse: 1204 Genf",
        "Bitte überweisen Sie 1500 Franken bis Ende Monat.",
        "Im Lager liegen 1200 Stück bereit.",
        "Kundennummer: CH-77120",
    ]
    for index, line in enumerate(lines):
        page.insert_text((60, 100 + index * 20), line, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("ch_postal",)),
    )
    found = texts(result.findings)
    assert "CH-8045 Zürich" in found
    assert "CH 3000 Bern" in found
    assert "1204 Genf" in found
    # Betrag und Stueckzahl sind keine Postleitzahlen
    assert not any("Franken" in item for item in found)
    assert not any("Stück" in item for item in found)
    # fuenfstellige Nummer nach CH ist keine vierstellige PLZ
    assert not any("CH-77120" in item for item in found)


def test_namensbestandteile():
    assert name_tokens("Frau Schmidt-Lorenz") == {"Schmidt-Lorenz"}
    assert name_tokens("Maximiliane Schmidt-Lorenz") == {
        "Maximiliane",
        "Schmidt-Lorenz",
    }
    # Strassen und Titel sind keine Namen
    assert name_tokens("Königsallee") == set()
    assert name_tokens("Herr Dr. Müller") == {"Müller"}


def test_name_wird_in_adresszeile_geschaerzt(sample):
    """Ein Name in der Adresszeile muss mitgeschwärzt werden.

    Die KI erkennt den Namen in Anschrift und Anrede; in der Zustellzeile steht
    er mitten in der Adresse. Die Namensübertragung muss ihn dort ebenfalls
    finden.
    """
    analyzer, _ = get_analyzer()
    if analyzer is None:
        pytest.skip("spaCy-Modell ist nicht installiert")

    result = run_detection(
        str(sample),
        DetectionOptions(
            use_ai=True, ai_entities=("PERSON",), rule_groups=("address",)
        ),
    )
    # Zustellzeile liegt unterhalb von y=600 (PDF-Punkte).
    in_delivery_line = [
        finding
        for finding in result.findings
        if finding.text == "Schmidt-Lorenz" and finding.rects[0][1] > 600
    ]
    assert in_delivery_line, [f.text for f in result.findings]


def test_term_pattern_ignoriert_leerraum():
    pattern = re.compile(term_pattern("Max  Mustermann"), re.IGNORECASE)
    assert pattern.search("hier: max   mustermann,")
    assert not pattern.search("Maximilian Mustermann")


def test_datumsformen_sind_kein_ort():
    """Datumsangaben zaehlen nicht als PLZ/Ort, Ortsnamen schon."""
    assert _ai_location_is_date("20.10.2026")
    assert _ai_location_is_date("20.10.26")
    assert _ai_location_is_date("2026-10-20")
    assert not _ai_location_is_date("9436 Balgach")
    assert not _ai_location_is_date("Balgach, 20.10.2026")
    # Eine reine Zahl ist kein Datum (PLZ allein bleibt moeglich).
    assert not _ai_location_is_date("8045")


def test_datumsregel_findet_die_drei_formen():
    rule = next(rule for rule in RULES if rule.key == "date")
    for text in ("20.10.2026", "20.10.26", "2026-10-20"):
        assert re.fullmatch(rule.pattern, text), text


def _kopfzeilen_pdf(path):
    """PDF mit allein stehendem Datum oben rechts anlegen."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((470, 60), "20.10.2026", fontsize=9, fontname="helv")
    page.insert_text((60, 200), "Mietlizenz", fontsize=14, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def test_datum_oben_rechts_ist_kein_plz_ort(tmp_path, monkeypatch):
    """Ein Datum in der Kopfzeile bleibt ein Datum.

    Das deutsche spaCy-Modell labelt ein allein stehendes Datum als Ort (LOC),
    Presidio macht daraus LOCATION und die Oberflaeche daraus "PLZ / Ort".
    Der Treffer darf nicht als PLZ/Ort erscheinen, das Datum selbst aber
    weiterhin ueber die Datumsregel gefunden werden.
    """
    source = _kopfzeilen_pdf(tmp_path / "kopfzeile.pdf")

    class FakeAnalyzer:
        """Meldet die Datumszeile als Ort, so wie es spaCy tut."""

        def analyze(self, text, **kwargs):
            cleaned = text.strip()
            if not re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", cleaned):
                return []
            start = text.index(cleaned)
            return [
                SimpleNamespace(
                    entity_type="LOCATION",
                    start=start,
                    end=start + len(cleaned),
                    score=0.85,
                )
            ]

    monkeypatch.setattr("pdfblack.core.detect.get_analyzer", lambda: (FakeAnalyzer(), None))

    result = run_detection(
        str(source),
        DetectionOptions(use_ai=True, ai_entities=("LOCATION",), rule_groups=("date",)),
    )
    found = texts(result.findings)
    assert "20.10.2026" in found
    assert [f.category for f in result.findings if f.text == "20.10.2026"] == [
        Category.DATE
    ]
    assert not [f for f in result.findings if f.category is Category.POSTAL], found


def test_unbekanntes_wort_ist_keine_ortschaft(tmp_path, monkeypatch):
    """Ein als Ort gemeldetes Wort muss in der Ortschaftenliste stehen.

    "Fachmessen" ist eine Ueberschrift in einem Lebenslauf; das Sprachmodell
    labelt sie trotzdem als Ort. Nur Namen aus der amtlichen Liste gelten als
    PLZ / Ort.
    """
    source = tmp_path / "orte.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Fachmessen", fontsize=11, fontname="helv")
    page.insert_text((60, 130), "Heerbrugg", fontsize=11, fontname="helv")
    doc.save(str(source))
    doc.close()

    class FakeAnalyzer:
        """Meldet beide Woerter als Ort, so wie es spaCy tut."""

        def analyze(self, text, **kwargs):
            cleaned = text.strip()
            if cleaned not in {"Fachmessen", "Heerbrugg"}:
                return []
            start = text.index(cleaned)
            return [
                SimpleNamespace(
                    entity_type="LOCATION",
                    start=start,
                    end=start + len(cleaned),
                    score=0.85,
                )
            ]

    monkeypatch.setattr("pdfblack.core.detect.get_analyzer", lambda: (FakeAnalyzer(), None))

    result = run_detection(
        str(source),
        DetectionOptions(use_ai=True, ai_entities=("LOCATION",), rule_groups=()),
    )
    found = texts(result.findings)
    assert "Heerbrugg" in found
    assert "Fachmessen" not in found


def test_jahreszahlen_sind_keine_postleitzahlen(tmp_path):
    """Vierstellige Jahreszahlen gehoeren nicht zu PLZ / Ort."""
    path = tmp_path / "jahre.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    zeilen = [
        "Lebenslauf",
        "2026",
        "2026 -",
        "2025 - 2026",
        "10/2026 -",
        "10/2025 - 05/2026",
        "2026 Muster AG",
        "2019 Muster AG, Zuerich",
        "2026 Berufsmaturitaet",
        "Zeitraum: 2024 - 2026",
        "Muster AG",
        "2026",
        "2000 Neuchatel",
        "1950 Sion",
        "8045 Zuerich",
        "CH-3000 Bern",
    ]
    for index, zeile in enumerate(zeilen):
        page.insert_text((60, 100 + index * 22), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("ch_postal",)),
    )
    found = texts(result.findings)

    # Kein Jahr darf als PLZ auftauchen - weder allein noch mit Firma dahinter.
    for jahr in ("2024", "2025", "2026", "2019"):
        assert not any(jahr in item for item in found), (jahr, found)
    # Echte Postleitzahlen bleiben erhalten.
    assert "2000 Neuchatel" in found
    assert "1950 Sion" in found
    assert "8045 Zuerich" in found
    assert "CH-3000 Bern" in found


def test_jahresband_ist_aktuelles_jahr_minus_siebzig():
    """Eine Jahreszahl liegt immer zwischen heute und heute minus 70."""
    from datetime import date

    from pdfblack.core.rules import ist_jahreszahl

    heute = date.today().year
    assert ist_jahreszahl(str(heute))
    assert ist_jahreszahl(str(heute - 70))
    assert not ist_jahreszahl(str(heute - 71))
    assert not ist_jahreszahl(str(heute + 1))
    assert not ist_jahreszahl("9435")
    assert not ist_jahreszahl("20 26")


def test_firma_unter_zahl(tmp_path):
    """PLZ und Ort stehen in einer Zeile - sonst ist der Name eine Firma.

    Steht eine Zahl allein und darunter ein Name, ist der Name eine Firma:
    bei einer Jahreszahl (2026) genauso wie bei einer PLZ (9435). Ein Beruf
    oder eine Ueberschrift ist keine Firma, und passt der Ort zur PLZ, ist es
    eine Adresse.
    """
    path = tmp_path / "firmen.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    zeilen = [
        "Lebenslauf",
        "2026",
        "Muster AG",
        "2019",
        "Muster GmbH",
        "2025",
        "Berufserfahrung",
        "2024",
        "Dachdecker",
        "9435",
        "Muster Verwaltung",
        "9435",
        "Heerbrugg",
        "1950",
        "Sion",
        "2000 Neuchatel",
    ]
    for index, zeile in enumerate(zeilen):
        page.insert_text((60, 100 + index * 22), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()

    result = run_detection(
        str(path),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "ch_postal")),
    )
    found = texts(result.findings)

    # Jahreszahl + Name und PLZ + fremder Name: beides eine Firma.
    for firma in ("Muster AG", "Muster GmbH", "Muster Verwaltung"):
        assert firma in found, (firma, found)
        assert all(
            f.category is Category.COMPANY for f in result.findings if f.text == firma
        ), firma
    # Ueberschrift und Beruf sind keine Firma.
    assert "Berufserfahrung" not in found
    assert "Dachdecker" not in found
    # Passt der Ort zur PLZ, bleibt es eine Adresse (1950 liegt ausserhalb
    # des Jahresbands und ist deshalb eine PLZ).
    assert "9435\nHeerbrugg" in [f.text for f in result.findings] or any(
        item.startswith("9435") and "Heerbrugg" in item for item in found
    ), found
    assert any(item.startswith("1950") and "Sion" in item for item in found), found
    # Jahreszahlen werden nicht geschwaerzt.
    assert not any(
        jahr in item for item in found for jahr in ("2026", "2019", "2025", "2024")
    ), found
    assert "2000 Neuchatel" in found


def test_ki_ort_mit_jahreszahl_ist_kein_ort():
    from pdfblack.core.detect import _ai_location_is_date

    for jahr in ("2026", "10/2026", "2025 - 2026", "10/2025 - 05/2026", "20.10.2026"):
        assert _ai_location_is_date(jahr), jahr
    for ort in ("Sion", "8045 Zürich", "Neuchâtel"):
        assert not _ai_location_is_date(ort), ort


def test_tldextract_cache_liegt_im_benutzerordner(tmp_path, monkeypatch):
    """In "Program Files" ist der Paketordner schreibgeschuetzt (WinError 5)."""
    import os
    from pathlib import Path

    from pdfblack.core import detect

    vorher = os.environ.pop("TLDEXTRACT_CACHE", None)
    try:
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        pfad = detect.prepare_tldextract()

        assert Path(pfad).is_dir()
        assert Path(pfad).parts[-2:] == ("PDFblack", "tldextract")
        assert os.environ["TLDEXTRACT_CACHE"] == pfad
    finally:
        os.environ.pop("TLDEXTRACT_CACHE", None)
        if vorher is not None:
            os.environ["TLDEXTRACT_CACHE"] = vorher


def test_tldextract_behaelt_einen_gesetzten_cache(tmp_path, monkeypatch):
    from pdfblack.core import detect

    eigen = tmp_path / "eigener-cache"
    monkeypatch.setenv("TLDEXTRACT_CACHE", str(eigen))

    assert detect.prepare_tldextract() == str(eigen)
    assert not eigen.exists()  # nichts angelegt, was der Benutzer nicht wollte


def test_tldextract_weicht_auf_temporaeren_ordner_aus(tmp_path, monkeypatch):
    """Ist der Benutzerordner nicht beschreibbar, muss es trotzdem klappen."""
    import os
    from pathlib import Path

    from pdfblack.core import detect

    blockiert = tmp_path / "blockiert"
    blockiert.write_text("kein Ordner", encoding="utf-8")

    vorher = os.environ.pop("TLDEXTRACT_CACHE", None)
    try:
        monkeypatch.setenv("LOCALAPPDATA", str(blockiert))
        monkeypatch.setenv("XDG_CACHE_HOME", str(blockiert))
        monkeypatch.setenv("HOME", str(blockiert))
        pfad = detect.prepare_tldextract()

        assert pfad
        assert Path(pfad).is_dir()
        assert str(blockiert) not in pfad
        assert os.environ["TLDEXTRACT_CACHE"] == pfad
    finally:
        os.environ.pop("TLDEXTRACT_CACHE", None)
        if vorher is not None:
            os.environ["TLDEXTRACT_CACHE"] = vorher
