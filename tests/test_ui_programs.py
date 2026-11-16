"""Wechsel zwischen PDFblack und PDFcompare samt Ein- und Ausblenden."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

try:  # Qt braucht je nach System zusaetzliche Bibliotheken
    from PySide6 import QtCore, QtTest, QtWidgets
except Exception as exc:  # noqa: BLE001 - ohne Qt wird der Test uebersprungen
    pytest.skip(f"Qt nicht verfuegbar: {exc}", allow_module_level=True)


@pytest.fixture(scope="module")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        try:
            app = QtWidgets.QApplication([])
        except Exception as exc:  # noqa: BLE001 - Qt fehlt im System
            pytest.skip(f"Qt startet hier nicht: {exc}")
    return app


@pytest.fixture
def window(qt_app, tmp_path):
    # Einstellungen im Testverzeichnis halten, damit nichts Echtes angefasst wird.
    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))
    from pdfblack.ui.main_window import MainWindow
    from pdfblack.ui.theme import apply_theme

    apply_theme(qt_app)
    win = MainWindow()
    win.resize(1380, 900)
    win.show()
    qt_app.processEvents()
    yield win
    win.close()


def _effect(window):
    return window.workspace.graphicsEffect()


def _wait_until(condition, timeout_ms: int = 3000) -> bool:
    """Auf einen Zustand warten, statt mit festen Zeiten zu raten."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if condition():
            return True
        QtTest.QTest.qWait(15)
    return condition()


def _click(logo) -> None:
    QtTest.QTest.mouseClick(logo, QtCore.Qt.LeftButton)


def _fading(window) -> bool:
    effect = _effect(window)
    return (
        isinstance(effect, QtWidgets.QGraphicsOpacityEffect)
        and effect.opacity() < 1.0
    )


def test_abbruch_mitten_im_ausblenden(window):
    """Klick waehrend des Ausblendens: Deckkraft zurueck, Maske bleibt richtig."""
    _click(window.header.compare.logo)
    assert _wait_until(lambda: _fading(window)), "Ausblenden hat nicht begonnen"
    assert window.workspace.currentWidget() is window.black_view

    _click(window.header.black.logo)

    # Der abgebrochene Fade darf keine halb ausgeblendete Maske hinterlassen.
    assert _effect(window) is None
    assert window.workspace.currentWidget() is window.black_view

    # Auch spaeter darf keine alte Animation die Maske umschalten.
    QtTest.QTest.qWait(500)
    assert window.workspace.currentWidget() is window.black_view
    assert _effect(window) is None


def test_abbruch_mitten_im_einblenden(window):
    """Klick waehrend des Einblendens: danach steht die gewaehlte Maske."""
    _click(window.header.compare.logo)
    assert _wait_until(lambda: window.workspace.currentWidget() is window.compare_view)
    assert _wait_until(lambda: _fading(window)), "Einblenden laeuft nicht"

    _click(window.header.black.logo)
    QtTest.QTest.qWait(500)

    assert window.workspace.currentWidget() is window.black_view
    assert _effect(window) is None


def _scan_pdf(path) -> None:
    """PDF ohne Text: Seite mit Text rendern und als Bild einsetzen."""
    import pymupdf

    quelle = pymupdf.open()
    page = quelle.new_page(width=595, height=842)
    page.insert_text((72, 160), "Dachdecker", fontsize=24, fontname="helv")
    bild = page.get_pixmap(dpi=300).tobytes("png")
    quelle.close()

    scan = pymupdf.open()
    seite = scan.new_page(width=595, height=842)
    seite.insert_image(seite.rect, stream=bild)
    scan.save(str(path))
    scan.close()


def test_scan_wechselt_automatisch_zu_pdfocr(window, qt_app, tmp_path, monkeypatch):
    """PDF ohne Text: PDFocr oeffnet sich und liest den Scan aus."""
    import pymupdf

    from pdfblack.core.ocr import Word
    from pdfblack.ui import ocr_view

    class FakeEngine:
        name = "Test"

        def available(self) -> bool:
            return True

        def read_words(self, png, size):
            return [Word("Dachdecker", (300.0, 600.0, 540.0, 650.0))]

    monkeypatch.setattr(ocr_view, "make_engine", lambda language: FakeEngine())

    scan = tmp_path / "scan.pdf"
    _scan_pdf(scan)
    window.load_pdf(str(scan))

    assert _wait_until(lambda: window.workspace.currentWidget() is window.ocr_view)
    assert window._program == "pdfocr"
    # Die Seite ist bedienbar: Knopf zum Auslesen ist da und sichtbar.
    assert window.ocr_view.btn_read.isVisible()
    assert window.ocr_view.btn_read.text() == "Text erkennen"
    assert _wait_until(lambda: window.ocr_view._result_path is not None), "OCR lief nicht"

    doc = pymupdf.open(window.ocr_view._result_path)
    assert "Dachdecker" in doc[0].get_text()
    doc.close()

    # Eine Datei mit Text bleibt in PDFblack.
    text_pdf = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Ein normaler Brief mit Text.", fontsize=12)
    doc.save(str(text_pdf))
    doc.close()
    window.load_pdf(str(text_pdf))
    qt_app.processEvents()
    assert window._program == "pdfblack"


def test_drittes_programm_pdfocr(window):
    """PDFocr: gruener Button, eigene leere Seite, Text nur beim aktiven Programm."""
    header = window.header
    _click(header.ocr.logo)
    assert _wait_until(lambda: window.workspace.currentWidget() is window.ocr_view)
    QtTest.QTest.qWait(600)

    assert window._program == "pdfocr"
    # Blau faehrt nach links, gruen steht dort, wo der blaue Text beginnt.
    assert header.compare.x() == header.title_x()
    assert header.ocr.x() == header.title_x() + header.LOGO_SIZE + header.GAP
    # Nur PDFocr zeigt Text.
    assert header.ocr.text_opacity > 0.99
    assert header.compare.text_opacity < 0.01
    assert header.black.text_opacity < 0.01

    # Zurueck zu PDFblack: alle Texte wieder wie am Anfang.
    _click(header.black.logo)
    QtTest.QTest.qWait(600)
    assert window.workspace.currentWidget() is window.black_view
    assert header.black.text_opacity > 0.99
    assert header.compare.text_opacity < 0.01
    assert header.ocr.text_opacity < 0.01
    assert header.compare.x() == header.compare_rest_x()
    assert header.ocr.x() == header.ocr_rest_x()


def test_drei_buttons_stehen_nebeneinander(window):
    """In Ruhestellung steht der gruene Button rechts neben dem blauen."""
    header = window.header
    QtTest.QTest.qWait(100)
    assert header.black.x() == header.MARGIN
    assert header.ocr.x() > header.compare.x()
    assert header.ocr.x() + header.LOGO_SIZE <= header.width()
    assert header.ocr.title.text() == "PDFocr"
    assert header.ocr.subtitle.text().startswith("Liest aus Bildscans")


class FakeBox:
    """Ersatz fuer QMessageBox: merkt sich Text und Knoepfe."""

    Warning = QtWidgets.QMessageBox.Warning
    AcceptRole = QtWidgets.QMessageBox.AcceptRole
    RejectRole = QtWidgets.QMessageBox.RejectRole
    zuletzt = None

    def __init__(self, parent=None) -> None:
        self.buttons = []
        self.title = ""
        self.text_ = ""
        self.info = ""
        self._clicked = None
        FakeBox.zuletzt = self

    def setIcon(self, icon) -> None:
        pass

    def setWindowTitle(self, title) -> None:
        self.title = title

    def setText(self, text) -> None:
        self.text_ = text

    def setInformativeText(self, text) -> None:
        self.info = text

    def addButton(self, text, role=None):
        knopf = QtCore.QObject()
        knopf.text = text
        knopf.role = role
        self.buttons.append(knopf)
        return knopf

    def exec(self) -> int:
        return 0

    def clickedButton(self):
        return self._clicked


def test_fehlendes_tesseract_wird_angeboten(window, monkeypatch):
    """Beim Start pruefen und die Nachinstallation anbieten."""
    from pdfblack.ui import main_window

    monkeypatch.setattr(main_window.ocr_core, "find_tesseract", lambda: None)
    monkeypatch.setattr(main_window.tesseract_setup, "moeglich", lambda: True)
    monkeypatch.setattr(main_window, "QMessageBox", FakeBox)

    window._check_tesseract()

    box = FakeBox.zuletzt
    assert "Tesseract" in box.text_
    assert [knopf.text for knopf in box.buttons] == ["Jetzt installieren", "Später"]
    # Ohne Klick wird nichts installiert.
    assert window._tesseract_worker is None


def test_ohne_winget_bleibt_es_beim_hinweis(window, monkeypatch):
    from pdfblack.ui import main_window

    monkeypatch.setattr(main_window.ocr_core, "find_tesseract", lambda: None)
    monkeypatch.setattr(main_window.tesseract_setup, "moeglich", lambda: False)
    monkeypatch.setattr(main_window, "QMessageBox", FakeBox)

    window._check_tesseract()

    box = FakeBox.zuletzt
    assert [knopf.text for knopf in box.buttons] == ["Später"]
    assert "winget" in box.info


def test_vorhandenes_tesseract_fragt_nicht(window, monkeypatch):
    from pdfblack.ui import main_window

    FakeBox.zuletzt = None
    monkeypatch.setattr(main_window.ocr_core, "find_tesseract", lambda: "tesseract")
    monkeypatch.setattr(main_window, "QMessageBox", FakeBox)

    window._check_tesseract()
    assert FakeBox.zuletzt is None


def test_installation_startet_im_hintergrund(window, monkeypatch):
    from pdfblack.ui import main_window

    gestartet = []

    class StubWorker(QtCore.QObject):
        done = QtCore.Signal(object)
        finished = QtCore.Signal()

        def start(self) -> None:
            gestartet.append(True)

    class KlickBox(FakeBox):
        def exec(self) -> int:
            self._clicked = self.buttons[0]
            return 0

    monkeypatch.setattr(main_window.ocr_core, "find_tesseract", lambda: None)
    monkeypatch.setattr(main_window.tesseract_setup, "moeglich", lambda: True)
    monkeypatch.setattr(main_window, "QMessageBox", KlickBox)
    monkeypatch.setattr(main_window, "TesseractSetupWorker", StubWorker)

    window._check_tesseract()

    assert gestartet == [True]
    assert window._tesseract_worker is not None
    window._tesseract_worker = None
    if window._tesseract_progress is not None:
        window._tesseract_progress.close()
        window._tesseract_progress = None


def test_schnelles_hin_und_her_landet_in_der_letzten_wahl(window):
    """Mehrere Klicks waehrend der Animationen: die letzte Wahl gilt."""
    for logo in (
        window.header.compare.logo,
        window.header.black.logo,
        window.header.compare.logo,
        window.header.black.logo,
    ):
        _click(logo)
        QtTest.QTest.qWait(30)

    QtTest.QTest.qWait(600)
    assert window.workspace.currentWidget() is window.black_view
    assert _effect(window) is None
    assert window._program == "pdfblack"
