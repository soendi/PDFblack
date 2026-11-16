"""PDFcompare-Listen mit Ziehen und Ablegen sowie die Copilot-Einstellungen."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:  # Qt braucht je nach System zusaetzliche Bibliotheken
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception as exc:  # noqa: BLE001 - ohne Qt wird der Test uebersprungen
    pytest.skip(f"Qt nicht verfuegbar: {exc}", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


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
def settings_dir(qt_app, tmp_path):
    """Einstellungen im Testverzeichnis halten, echte bleiben unberuehrt."""
    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))
    return tmp_path


def _pdf(path) -> str:
    path.write_bytes(b"%PDF-1.4\n%Testdatei\n")
    return str(path)


def _drop_event(path: str):
    """Mime-Daten und Ereignis zusammen zurueckgeben.

    QDropEvent haelt die QMimeData nicht fest; faellt die Python-Referenz weg,
    greift Qt auf freigegebenen Speicher zu.
    """
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(path)])
    event = QtGui.QDropEvent(
        QtCore.QPointF(5, 5),
        QtCore.Qt.CopyAction,
        mime,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    return mime, event


def test_zuletzt_geschwaerzt_und_ziehen(qt_app, settings_dir, tmp_path):
    from pdfblack.ui.compare import CompareView

    view = CompareView()
    pfad = _pdf(tmp_path / "bewerbung_mueller.pdf")

    view.remember(pfad)
    assert view.recent.count() == 1
    assert view.recent.item(0).text() == "bewerbung_mueller.pdf"

    mime, event = _drop_event(pfad)
    view.life.dropEvent(event)
    assert view.life.count() == 1
    assert view.life.paths() == [os.path.abspath(pfad)]

    # Zweimal ablegen legt keinen zweiten Eintrag an.
    mime, event = _drop_event(pfad)
    view.life.dropEvent(event)
    assert view.life.count() == 1

    # Die Zuordnung ueberdauert einen Neuaufbau.
    QtCore.QSettings().sync()
    wieder = CompareView()
    assert wieder.recent.count() == 1
    assert wieder.life.count() == 1
    assert wieder.certs.count() == 0

    # Entfernen mit der Entf-Taste leert den Stapel wieder.
    wieder.life.setCurrentRow(0)
    key = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier
    )
    wieder.life.keyPressEvent(key)
    assert wieder.life.count() == 0
    QtCore.QSettings().sync()
    leer = CompareView()
    assert leer.life.count() == 0

    # Qt-Widgets vor dem naechsten Test sauber abraeumen.
    for widget in (view, wieder, leer):
        widget.deleteLater()
    qt_app.processEvents()


def test_copilot_verknuepfung_wird_gemerkt(qt_app, settings_dir):
    from pdfblack.ui import preferences

    preferences.save_agents(
        [{"name": "Bewerbungen", "link": "https://example.invalid/agent"}]
    )

    dialog = preferences.PreferencesDialog()
    assert dialog.linked.isChecked() is False
    assert dialog.open_button.isEnabled() is False

    dialog.linked.setChecked(True)
    dialog.agent.setCurrentIndex(dialog.agent.findText("Bewerbungen"))
    dialog.accept()

    assert preferences.is_linked() is True
    assert preferences.active_agent() == {
        "name": "Bewerbungen",
        "link": "https://example.invalid/agent",
    }

    wieder = preferences.PreferencesDialog()
    assert wieder.linked.isChecked() is True
    assert wieder.agent.currentText() == "Bewerbungen"
    assert wieder.open_button.isEnabled() is True
