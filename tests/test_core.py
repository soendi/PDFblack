"""Kurztests fuer Erkennung und Schwärzung (ohne Oberflaeche)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from make_sample import build  # noqa: E402

from pdfblack.core.detect import (  # noqa: E402
    DetectionOptions,
    ManualTerm,
    RegexSpec,
    get_analyzer,
    name_tokens,
    run_detection,
    term_pattern,
)
from pdfblack.core.models import Category  # noqa: E402
from pdfblack.core.redact import apply_redactions  # noqa: E402


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
