"""Tests fuer die lokale Pruefung und die Copilot-Schleife ohne API."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import review


def _pdf(path: Path, text: str = "") -> str:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    if text:
        y = 90
        for zeile in text.splitlines():
            page.insert_text((60, y), zeile, fontsize=11, fontname="helv")
            y += 18
    doc.save(str(path))
    doc.close()
    return str(path)


def test_zeitraeume_aus_verschiedenen_schreibweisen():
    text = (
        "2019 - 2022 Muster AG\n"
        "01/2020–03/2022 Andere Firma\n"
        "Januar 2018 bis März 2019 Dritte Stelle\n"
        "05/2023 - heute Vierte Stelle\n"
    )
    perioden = review.periods_from_text(text)
    paare = {(periode.start, periode.end) for periode in perioden}

    assert ((2020, 1), (2022, 3)) in paare
    assert ((2018, 1), (2019, 3)) in paare
    assert ((2023, 5), None) in paare
    assert ((2019, 1), (2022, 1)) in paare


def test_luecken_zwischen_zeitraeumen():
    perioden = [
        review.Period((2019, 1), (2020, 12), "a"),
        review.Period((2022, 6), (2024, 1), "b"),
    ]
    luecken = review.gaps(perioden, today=date(2025, 1, 1))

    assert len(luecken) == 1
    assert luecken[0].von == (2021, 1)
    assert luecken[0].bis == (2022, 5)
    assert luecken[0].monate == 17
    assert "01/2021" in luecken[0].label()


def test_kurze_luecken_und_ueberlappungen_zaehlen_nicht():
    perioden = [
        review.Period((2019, 1), (2020, 12), "a"),
        review.Period((2021, 2), (2021, 12), "b"),  # ein Monat Pause
        review.Period((2021, 6), (2022, 1), "c"),  # ueberlappt
    ]
    assert review.gaps(perioden) == []


def test_doppelte_dateien(tmp_path):
    erste = tmp_path / "zeugnis.pdf"
    erste.write_bytes(b"%PDF-1.4\n%gleich\n")
    zweite = tmp_path / "zeugnis_kopie.pdf"
    zweite.write_bytes(b"%PDF-1.4\n%gleich\n")
    andere = tmp_path / "lebenslauf.pdf"
    andere.write_bytes(b"%PDF-1.4\n%anders\n")

    gruppen = review.duplicates([str(erste), str(zweite), str(andere)])
    assert len(gruppen) == 1
    assert len(gruppen[0]) == 2


def test_pruefung_meldet_fehlenden_lebenslauf_und_scan(tmp_path):
    scan = _pdf(tmp_path / "zeugnis_scan.pdf")  # leer: keine Textebene
    bericht = review.review([], [scan])

    texte = " ".join(finding.text for finding in bericht.findings)
    assert "Kein Lebenslauf" in texte
    assert "keine Textebene" in texte
    assert bericht.dateien == 1
    assert bericht.warnings() >= 2
    assert "Hinweis" in bericht.summary()


def test_pruefung_findet_luecke_im_lebenslauf(tmp_path):
    lebenslauf = _pdf(
        tmp_path / "lebenslauf.pdf",
        "01/2016 - 12/2018 Firma A\n06/2021 - heute Firma B\n",
    )
    bericht = review.review([lebenslauf], [])

    texte = " ".join(finding.text for finding in bericht.findings)
    assert "Lücke im Lebenslauf" in texte
    assert bericht.gaps and bericht.gaps[0].von == (2019, 1)
    assert "01/2019" in bericht.as_text()


def test_frage_an_copilot_enthaelt_schema_und_fakten(tmp_path):
    lebenslauf = _pdf(tmp_path / "lebenslauf.pdf", "01/2020 - heute Firma B\n")
    zeugnis = _pdf(tmp_path / "zeugnis_2021.pdf", "Arbeitszeugnis\n2021\n")
    bericht = review.review([lebenslauf], [zeugnis])

    frage = review.build_prompt(bericht, [lebenslauf], [zeugnis])

    assert "ausschließlich" in frage
    assert "lebenslauf_luecken" in frage and "fehlende_unterlagen" in frage
    assert "lebenslauf.pdf" in frage and "zeugnis_2021.pdf" in frage
    assert "Seiten gesamt" in frage


def test_antwort_wird_auch_aus_fliesstext_gelesen():
    antwort = (
        "Klar, hier das Ergebnis:\n"
        "```json\n"
        '{"lebenslauf_luecken": [{"von": "01/2019", "bis": "05/2021", "hinweis": "Elternzeit"}],\n'
        ' "zeugnisse": [{"datei": "zeugnis_2021.pdf", "art": "Arbeitszeugnis"}],\n'
        ' "fehlende_unterlagen": ["Anschreiben"],}\n'
        "```\n"
        "Sag Bescheid, wenn du mehr brauchst."
    )
    daten = review.parse_answer(antwort)

    assert daten is not None
    assert daten["lebenslauf_luecken"][0]["von"] == "01/2019"
    zeilen = "\n".join(review.answer_lines(daten))
    assert "Elternzeit" in zeilen
    assert "Fehlt laut Copilot" in zeilen and "Anschreiben" in zeilen


def test_unbrauchbare_antwort_wird_erkannt():
    assert review.parse_answer("") is None
    assert review.parse_answer("Copilot hat nichts gefunden.") is None
    assert review.parse_answer("{kaputt}") is None


# ---------------------------------------------------------------------------
# Das Fenster
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qt_app():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_fenster_zeigt_befunde_und_wertet_die_antwort_aus(qt_app, tmp_path, monkeypatch):
    from PySide6 import QtCore, QtWidgets

    from pdfblack.ui import preferences
    from pdfblack.ui.review import ReviewDialog

    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))

    lebenslauf = _pdf(
        tmp_path / "lebenslauf.pdf",
        "01/2016 - 12/2018 Firma A\n06/2021 - heute Firma B\n",
    )
    dialog = ReviewDialog([lebenslauf], [])
    assert "Lücke im Lebenslauf" in dialog.findings.toPlainText()
    assert "Keine Arbeitszeugnisse" in dialog.findings.toPlainText()

    QtWidgets.QApplication.clipboard().setText(
        '{"lebenslauf_luecken": [], "zusammenfassung": "Alles plausibel."}'
    )
    dialog.paste_button.click()
    assert "Alles plausibel." in dialog.result.toPlainText()

    QtWidgets.QApplication.clipboard().setText("keine antwort")
    dialog.paste_button.click()
    assert "Kein JSON" in dialog.result.toPlainText()

    monkeypatch.setattr(
        preferences, "open_copilot", lambda *args, **kwargs: True
    )
    dialog.ask_button.click()
    kopiert = QtWidgets.QApplication.clipboard().text()
    assert "ausschließlich" in kopiert

    # Der Prompt steht im Fenster und laesst sich vor dem Absenden aendern.
    assert "ausschließlich" in dialog.question.toPlainText()
    dialog.question.setPlainText("Bitte nur das JSON liefern.")
    dialog.ask_button.click()
    assert QtWidgets.QApplication.clipboard().text() == "Bitte nur das JSON liefern."
    dialog.deleteLater()
    qt_app.processEvents()


def test_pruefung_nimmt_alle_vier_stapel_auf(tmp_path):
    """Bewerbung, Lebenslauf, Zeugnisse und Diplome zaehlen mit."""
    bewerbung = _pdf(tmp_path / "bewerbung.pdf")  # Scan ohne Textebene
    lebenslauf = _pdf(
        tmp_path / "lebenslauf.pdf",
        "01/2016 - 12/2018 Firma A\n06/2021 - heute Firma B\n",
    )
    zeugnis = _pdf(tmp_path / "zeugnis_2021.pdf", "Arbeitszeugnis\n2021\n")
    diplom = _pdf(tmp_path / "diplom.pdf", "Diplom\n2022\n")

    bericht = review.review([lebenslauf], [zeugnis], [bewerbung], [diplom])

    assert bericht.dateien == 4
    assert bericht.seiten == 4
    assert "4 Dateien" in bericht.summary()
    texte = " ".join(finding.text for finding in bericht.findings)
    assert "bewerbung.pdf" in texte and "keine Textebene" in texte
    assert "Kein Lebenslauf" not in texte
    assert "Keine Arbeitszeugnisse" not in texte

    frage = review.build_prompt(
        bericht, [lebenslauf], [zeugnis], [bewerbung], [diplom]
    )
    for name in ("bewerbung.pdf", "lebenslauf.pdf", "zeugnis_2021.pdf", "diplom.pdf"):
        assert name in frage


def test_fehlende_datei_aus_der_bewerbung_wird_gemeldet(tmp_path):
    weg = tmp_path / "weg.pdf"
    bericht = review.review([], [], [str(weg)], [])

    texte = " ".join(finding.text for finding in bericht.findings)
    assert "weg.pdf: Datei ist nicht mehr vorhanden." in texte


def test_fenster_zeigt_befunde_aus_allen_stapeln(qt_app, tmp_path):
    from PySide6 import QtCore

    from pdfblack.ui.review import ReviewDialog

    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))

    bewerbung = _pdf(tmp_path / "bewerbung.pdf")
    lebenslauf = _pdf(tmp_path / "lebenslauf.pdf", "01/2020 - heute Firma B\n")
    dialog = ReviewDialog([lebenslauf], [], [bewerbung], [])

    befunde = dialog.findings.toPlainText()
    assert "bewerbung.pdf" in befunde
    assert "keine Textebene" in befunde
    assert "bewerbung.pdf" in dialog.question.toPlainText()

    dialog.deleteLater()
    qt_app.processEvents()
