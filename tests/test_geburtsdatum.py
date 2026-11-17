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
    assert texte == ["Geburtsdatum: 1.3.95", "Geboren am 01. März 1995"]
    assert "20.10.2026" not in texte


def test_datum_mit_schraegstrich_wird_gelesen():
    assert geburtsdatum.als_datum("05/02/1990") == date(1990, 2, 5)
    assert geburtsdatum.als_datum("5/2/90") == date(1990, 2, 5)
    # Monat/Jahr allein ist kein vollstaendiges Datum.
    assert geburtsdatum.als_datum("10/2025") is None


def test_einziges_datum_mit_15_jahre_juengerer_jahreszahl():
    """05/02/1990 und sonst nur 2020 genannt: das Datum ist das Geburtsdatum."""
    assert geburtsdatum.geburtsdatum([date(1990, 2, 5)], [2020]) == date(1990, 2, 5)
    assert geburtsdatum.geburtsdatum([date(1990, 2, 5)], [1990, 2020]) == date(
        1990, 2, 5
    )
    # Nur 10 Jahre spaeter: kein Geburtsdatum.
    assert geburtsdatum.geburtsdatum([date(1990, 2, 5)], [2000]) is None
    # Ohne Vergleichswert ebenfalls keins.
    assert geburtsdatum.geburtsdatum([date(1990, 2, 5)], []) is None
    assert geburtsdatum.geburtsdatum([date(1990, 2, 5)]) is None


def test_jahreszahlen_werden_gelesen():
    assert geburtsdatum.jahreszahlen("Anmeldung 2020, geboren 1990") == [2020, 1990]
    # Laengere Ziffernfolgen sind keine Jahreszahlen.
    assert geburtsdatum.jahreszahlen("558416824044") == []


def test_erkennung_schwaerzt_einziges_datum_mit_juengerer_jahreszahl(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "einzel.pdf",
        ["Geburtsdatum 05/02/1990", "Anmeldung beim Amt 2020"],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    treffer = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert treffer == ["Geburtsdatum 05/02/1990"]


def test_erkennung_ohne_juengere_jahreszahl_schwaerzt_nichts(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "nah.pdf",
        ["Geburtsdatum 05/02/1990", "Anmeldung beim Amt 1998"],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    assert [
        finding
        for finding in ergebnis.findings
        if finding.category in (Category.DATE, Category.BIRTHDATE)
    ] == []


def test_zahlenschreibweisen_mit_tag_und_monat():
    faelle = {
        "12.03.1985": date(1985, 3, 12),
        "12.3.85": date(1985, 3, 12),
        "3. 12 1985": date(1985, 12, 3),
        "3.12 1985": date(1985, 12, 3),
        "3. 12. 1985": date(1985, 12, 3),
        "03 . 12 . 1985": date(1985, 12, 3),
        "12/03/1985": date(1985, 3, 12),
        "5/2/90": date(1990, 2, 5),
        "12-03-1985": date(1985, 3, 12),
        "12 / 3 / 85": date(1985, 3, 12),
        "1985-03-12": date(1985, 3, 12),
        "1985.03.12": date(1985, 3, 12),
        "31.12.1999": date(1999, 12, 31),
        "1.1.00": date(2000, 1, 1),
    }
    for text, erwartet in faelle.items():
        assert geburtsdatum.als_datum(text) == erwartet, text
    # Steht der Monat vorn, wird es trotzdem richtig gelesen.
    assert geburtsdatum.als_datum("05/31/1990") == date(1990, 5, 31)


def test_monatsnamen_in_allen_abkuerzungen():
    faelle = {
        "12. März 1985": date(1985, 3, 12),
        "12. Maerz 1985": date(1985, 3, 12),
        "12. Marz 1985": date(1985, 3, 12),
        "12 März 1985": date(1985, 3, 12),
        "12. Mrz 85": date(1985, 3, 12),
        "12. Mrz. 1995": date(1995, 3, 12),
        "1. Jänner 2000": date(2000, 1, 1),
        "1. Jaenner 2000": date(2000, 1, 1),
        "1. Januar 2000": date(2000, 1, 1),
        "5. Sept 1999": date(1999, 9, 5),
        "5. September 1999": date(1999, 9, 5),
        "31. Dez. 1999": date(1999, 12, 31),
    }
    for text, erwartet in faelle.items():
        assert geburtsdatum.als_datum(text) == erwartet, text


def test_monat_jahr_ohne_tag():
    angabe = geburtsdatum.Angabe
    assert geburtsdatum.als_angabe("10/2025") == angabe(2025, 10)
    assert geburtsdatum.als_angabe("1/85") == angabe(1985, 1)
    assert geburtsdatum.als_angabe("03-2025") == angabe(2025, 3)
    assert geburtsdatum.als_angabe("03.1985") == angabe(1985, 3)
    assert geburtsdatum.als_angabe("März 1985") == angabe(1985, 3)
    assert geburtsdatum.als_angabe("September 1999") == angabe(1999, 9)
    # Ohne Tag ist es kein vollstaendiges Datum.
    assert geburtsdatum.als_datum("10/2025") is None
    # Monat 13 gibt es nicht, Preise mit Punkt bleiben unangetastet.
    assert geburtsdatum.als_angabe("13/2025") is None
    assert geburtsdatum.als_angabe("12.34") is None


def test_monat_jahr_zaehlt_nur_als_vergleich():
    """Monat/Jahr ohne Tag ist nie das Geburtsdatum, trennt aber die Daten."""
    assert geburtsdatum.geburtsdatum(
        [date(1985, 3, 12), geburtsdatum.Angabe(2025, 10)]
    ) == date(1985, 3, 12)
    # Ein halbes Datum allein reicht nicht.
    assert geburtsdatum.geburtsdatum([geburtsdatum.Angabe(1985, 3)]) is None
    # Liegt die Monat/Jahr-Angabe im selben Jahr, ist nichts sicher.
    assert geburtsdatum.geburtsdatum(
        [date(1985, 3, 12), geburtsdatum.Angabe(1985, 10)]
    ) is None


def test_datumsregel_findet_alle_schreibweisen():
    from pdfblack.core.rules import compiled, rules_for_groups

    regel = next(r for r in rules_for_groups(("date",)) if r.key == "date")
    text = (
        "12.03.1985 | 12.3.85 | 3. 12 1985 | 3.12 85 | 03 . 12 . 1985 | "
        "12/03/1985 | 5/2/90 | 12-03-1985 | 3. März 1985 | 3. Mrz 85 | "
        "2026-10-20 | 10/2025 | 1/85 | 03.1985 | März 1985"
    )
    treffer = [m.group(0) for m in compiled(regel).finditer(text)]
    assert treffer == [
        "12.03.1985",
        "12.3.85",
        "3. 12 1985",
        "3.12 85",
        "03 . 12 . 1985",
        "12/03/1985",
        "5/2/90",
        "12-03-1985",
        "3. März 1985",
        "3. Mrz 85",
        "2026-10-20",
        "10/2025",
        "1/85",
        "03.1985",
        "März 1985",
    ]


def test_erkennung_findet_neue_schreibweisen(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "cv.pdf",
        [
            "Geburtsdatum: 3. 12 1985",
            "Anstellung 10/2025",
            "Zeugnis vom 12-03-2026",
        ],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    texte = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert texte == ["Geburtsdatum: 3. 12 1985"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
