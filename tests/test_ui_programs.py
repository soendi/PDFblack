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
