"""Tests fuer das Geburtsdatum: aeltestes Datum, mindestens 15 Jahre Abstand."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import geburtsdatum  # noqa: E402
from pdfblack.core.models import Category  # noqa: E402


def _pdf(path: Path, zeilen: list[str]) -> str:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for zeile in zeilen:
        page.insert_text((60, y), zeile, fontsize=12, fontname="helv")
        y += 26
    doc.save(str(path))
    doc.close()
    return str(path)


def test_datum_wird_in_allen_schreibweisen_gelesen():
    assert geburtsdatum.als_datum("12.03.1985") == date(1985, 3, 12)
    assert geburtsdatum.als_datum("12.3.85") == date(1985, 3, 12)
    assert geburtsdatum.als_datum("12. März 1985") == date(1985, 3, 12)
    assert geburtsdatum.als_datum("3. Maerz 85") == date(1985, 3, 3)
    assert geburtsdatum.als_datum("2026-10-20") == date(2026, 10, 20)
    # Die Beschriftung davor stoert nicht.
    assert geburtsdatum.als_datum("Geburtsdatum: 12.03.1985") == date(1985, 3, 12)


def test_zweistellige_jahre_liegen_nicht_in_der_zukunft():
    heute = date.today().year
    assert geburtsdatum.als_datum("01.01.85").year == 1985
    assert geburtsdatum.als_datum(f"01.01.{heute % 100:02d}").year == heute
    assert geburtsdatum.als_datum("01.01.99").year == 1999


def test_unbrauchbare_angaben_sind_kein_datum():
    assert geburtsdatum.als_datum("32.13.1990") is None
    assert geburtsdatum.als_datum("März 1985") is None
    assert geburtsdatum.als_datum("kein Datum") is None


def test_geburtsdatum_ist_das_aelteste_mit_15_jahren_abstand():
    assert geburtsdatum.geburtsdatum([date(1985, 3, 12), date(2026, 10, 20)]) == date(
        1985, 3, 12
    )
    # Genau 15 Jahre reichen.
    assert geburtsdatum.geburtsdatum([date(2000, 1, 1), date(2015, 1, 1)]) == date(
        2000, 1, 1
    )
    # Ein Tag zu wenig: kein Geburtsdatum.
    assert geburtsdatum.geburtsdatum([date(2000, 1, 2), date(2015, 1, 1)]) is None
    # Nur ein Datum: der Abstand laesst sich nicht pruefen.
    assert geburtsdatum.geburtsdatum([date(1985, 3, 12)]) is None
    assert geburtsdatum.geburtsdatum([]) is None


def test_erkennung_schwaerzt_nur_das_geburtsdatum(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "lebenslauf.pdf",
        [
            "Geburtsdatum: 12.03.1985",
            "Anstellung seit 01.09.2020",
            "Zeugnis vom 20.10.2026",
        ],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    daten = [
        finding
        for finding in ergebnis.findings
        if finding.category in (Category.DATE, Category.BIRTHDATE)
    ]
    assert [finding.text for finding in daten] == ["Geburtsdatum: 12.03.1985"]
    assert daten[0].category is Category.BIRTHDATE
    assert "ältestes Datum" in daten[0].source


def test_erkennung_ohne_15_jahre_abstand_schwaerzt_kein_datum(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "brief.pdf",
        ["Rechnung vom 01.03.2020", "Geliefert am 20.10.2026"],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    daten = [
        finding
        for finding in ergebnis.findings
        if finding.category in (Category.DATE, Category.BIRTHDATE)
    ]
    assert daten == []


def test_monatsname_ist_ein_datum(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "monat.pdf",
        ["Geboren am 3. März 85", "Eintritt 01.09.2020"],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    treffer = [
        finding
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert len(treffer) == 1
    assert "3. März 85" in treffer[0].text


def test_andere_schreibweisen_desselben_datums():
    text = (
        "Geb. 1.3.95, nochmals 01. März 1995 und 1995-03-01; "
        "Rechnung vom 20.10.2026"
    )
    stellen = geburtsdatum.schreibweisen(text, date(1995, 3, 1))
    gelesen = [text[start:end] for start, end in stellen]
    assert gelesen == ["1.3.95", "01. März 1995", "1995-03-01"]
    # Andere Daten bleiben unangetastet.
    assert text[slice(*geburtsdatum.schreibweisen(text, date(2026, 10, 20))[0])] == (
        "20.10.2026"
    )


def test_erkennung_schwaerzt_alle_schreibweisen_des_geburtsdatums(tmp_path):
    """Gefunden: 1.3.95 -> auch 01. März 1995 wird geschwaerzt."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "bewerbung.pdf",
        [
            "Geburtsdatum: 1.3.95",
            "Geboren am 01. März 1995 in Balgach",
            "Zeugnis vom 20.10.2026",
        ],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    texte = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert texte == ["Geburtsdatum: 1.3.95", "01. März 1995"]
    assert "20.10.2026" not in texte


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
