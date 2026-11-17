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


def test_erkennung_markiert_das_geburtsdatum_und_zeigt_alle_daten(tmp_path):
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
    geburt = [finding for finding in daten if finding.category is Category.BIRTHDATE]
    assert [finding.text for finding in geburt] == ["Geburtsdatum: 12.03.1985"]
    assert "ältestes Datum" in geburt[0].source
    # Die uebrigen Daten bleiben als Datum in der Trefferliste.
    assert {finding.text for finding in daten if finding.category is Category.DATE} == {
        "01.09.2020",
        "20.10.2026",
    }


def test_erkennung_ohne_15_jahre_abstand_zeigt_daten_ohne_geburtsdatum(tmp_path):
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
    # Kein Geburtsdatum - die Daten selbst bleiben aber sichtbar.
    assert [finding for finding in daten if finding.category is Category.BIRTHDATE] == []
    assert {finding.text for finding in daten} == {"01.03.2020", "20.10.2026"}


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


def test_erkennung_ohne_juengere_jahreszahl_bleibt_datums_treffer(tmp_path):
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "nah.pdf",
        ["Geburtsdatum 05/02/1990", "Anmeldung beim Amt 1998"],
    )
    ergebnis = run_detection(str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",)))

    daten = [
        finding
        for finding in ergebnis.findings
        if finding.category in (Category.DATE, Category.BIRTHDATE)
    ]
    # 1998 liegt zu nah fuer ein Geburtsdatum - das Datum bleibt trotzdem da.
    assert [finding for finding in daten if finding.category is Category.BIRTHDATE] == []
    assert [finding.text for finding in daten] == ["Geburtsdatum 05/02/1990"]


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


def test_februar_in_allen_schreibweisen():
    """05.02.1990 auch ausgeschrieben und abgekuerzt."""
    faelle = {
        "5. Februar 1990": date(1990, 2, 5),
        "05. Februar 1990": date(1990, 2, 5),
        "5. Feb. 1990": date(1990, 2, 5),
        "5. Feb 1990": date(1990, 2, 5),
        "5. Feb. 90": date(1990, 2, 5),
        "5. Febr. 1990": date(1990, 2, 5),
        "5. Febr. 90": date(1990, 2, 5),
        "5. Jän. 1990": date(1990, 1, 5),
    }
    for text, erwartet in faelle.items():
        assert geburtsdatum.als_datum(text) == erwartet, text


@pytest.mark.parametrize(
    ("monat", "nummer"),
    [
        ("Januar", 1),
        ("Februar", 2),
        ("März", 3),
        ("April", 4),
        ("Mai", 5),
        ("Juni", 6),
        ("Juli", 7),
        ("August", 8),
        ("September", 9),
        ("Oktober", 10),
        ("November", 11),
        ("Dezember", 12),
    ],
)
def test_alle_zwoelf_monatsnamen(monat, nummer):
    """Jeder Monatsname ergibt mit Tag und Jahr ein vollstaendiges Datum."""
    assert geburtsdatum.als_datum(f"5. {monat} 1990") == date(1990, nummer, 5)
    assert geburtsdatum.als_datum(f"5 {monat} 90") == date(1990, nummer, 5)


def test_ausgeschriebenes_datum_in_getrennten_feldern(tmp_path):
    """Tag, Monatsname und Jahr stehen in eigenen Textfeldern derselben Zeile.

    So sehen Formulare aus: die Felder sind eigene Textobjekte mit grossem
    Abstand. Der Text muss trotzdem als "5. Februar 1990" gelesen und mit den
    uebrigen Daten verglichen werden.
    """
    from pdfblack.core.detect import DetectionOptions, run_detection

    doc = pymupdf.open()
    seite = doc.new_page(width=595, height=842)
    felder = [
        (50, 100, "Geburtsdatum:"),
        (230, 100, "5."),
        (260, 100, "Februar"),
        (370, 100, "1990"),
        (50, 140, "Eintritt:"),
        (230, 140, "01.09.2020"),
        (50, 180, "Zeugnis:"),
        (230, 180, "12.03.2026"),
    ]
    for x, y, text in felder:
        seite.insert_text((x, y), text, fontsize=11, fontname="helv")
    quelle = tmp_path / "geb_felder.pdf"
    doc.save(str(quelle))
    doc.close()

    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",))
    )
    texte = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert texte == ["Geburtsdatum: 5. Februar 1990"]


def test_ausgeschriebenes_geburtsdatum_wird_erkannt(tmp_path):
    """Der Monatsname zaehlt wie die Zahlenform als Geburtsdatum."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "geb_wort.pdf",
        [
            "Geburtsdatum: 5. Februar 1990",
            "Eintritt 01.09.2020",
            "Zeugnis vom 12.03.2026",
        ],
    )
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",))
    )
    texte = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert texte == ["Geburtsdatum: 5. Februar 1990"]


def test_kurzform_des_monats_wird_erkannt(tmp_path):
    """"Geburtstag: 5. Febr. 90" ist dasselbe Datum."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "geb_kurz.pdf",
        ["Geburtstag: 5. Febr. 90", "Eintritt 01.09.2020"],
    )
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("date",))
    )
    texte = [
        finding.text
        for finding in ergebnis.findings
        if finding.category is Category.BIRTHDATE
    ]
    assert texte == ["Geburtstag: 5. Febr. 90"]


def test_datum_hinter_beschriftung_geht_nicht_verloren(tmp_path):
    """"Eintritt 01.09.2020": die Zahl beginnt ein Datum und ist keine Hausnummer.

    Ohne diese Sperre las die Hausnummern-Regel "Eintritt 01" und verdraengte
    das Datum - damit fehlte auch ein Vergleichswert fuer das Geburtsdatum.
    """
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "beschriftung.pdf",
        ["Eintritt 01.09.2020", "Geburtsdatum: 05.02.1990"],
    )
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("address", "date"))
    )
    texte = {finding.category: [] for finding in ergebnis.findings}
    for finding in ergebnis.findings:
        texte.setdefault(finding.category, []).append(finding.text)
    assert "01.09.2020" in texte.get(Category.DATE, [])
    assert "Geburtsdatum: 05.02.1990" in texte.get(Category.BIRTHDATE, [])
    assert not any("Eintritt" in text for text in texte.get(Category.ADDRESS, []))


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


def test_kurzes_datum_und_jahr_werden_erkannt(tmp_path):
    """5.8.11 als Datum, 2025 als Jahr - beides erscheint in der Liste."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(
        tmp_path / "kurz.pdf",
        ["Anmeldung 5.8.11", "Bericht 2025"],
    )
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("date", "year"))
    )

    kategorien = {finding.text: finding.category for finding in ergebnis.findings}
    assert kategorien["5.8.11"] is Category.DATE
    assert kategorien["2025"] is Category.YEAR
    assert Category.BIRTHDATE not in kategorien.values()


def test_jahr_zerlegt_kein_datum(tmp_path):
    """Das Jahr in einem vollstaendigen Datum wird nicht eigens markiert."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(tmp_path / "datum.pdf", ["Zeugnis vom 20.10.2026"])
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("date", "year"))
    )

    assert [finding.text for finding in ergebnis.findings] == ["20.10.2026"]
    assert ergebnis.findings[0].category is Category.DATE


def test_jahr_steht_nicht_in_einer_nummer(tmp_path):
    """1998 hinter "Personalnummer" bleibt eine Nummer, kein Jahr."""
    from pdfblack.core.detect import DetectionOptions, run_detection

    quelle = _pdf(tmp_path / "nummer.pdf", ["Personalnummer: 1998"])
    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("id", "year"))
    )

    assert [(finding.text, finding.category) for finding in ergebnis.findings] == [
        ("1998", Category.ID)
    ]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
