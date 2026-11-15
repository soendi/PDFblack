"""Die Optionen der automatischen Erkennung ueberdauern den Programmstart."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:  # Qt braucht je nach System zusaetzliche Bibliotheken
    from PySide6 import QtCore, QtWidgets
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


def test_erkennungseinstellungen_werden_gemerkt(qt_app, tmp_path):
    # Beide Formate in das Testverzeichnis legen, damit die echten
    # Benutzereinstellungen unberuehrt bleiben.
    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))
    from pdfblack.ui.panels import ControlsPanel

    panel = ControlsPanel()
    assert panel.cb_ch.isChecked() and panel.cb_date.isChecked() is False

    panel.cb_ch.setChecked(False)
    panel.cb_date.setChecked(True)
    panel.cb_person.setChecked(False)
    panel.ai_check.setChecked(False)
    panel.sensitivity.setCurrentIndex(0)
    QtCore.QSettings().sync()

    wieder = ControlsPanel()
    assert wieder.cb_ch.isChecked() is False
    assert wieder.cb_date.isChecked() is True
    assert wieder.cb_person.isChecked() is False
    assert wieder.ai_check.isChecked() is False
    assert wieder.sensitivity.currentIndex() == 0
    # Nicht angetastete Optionen behalten ihren Standard.
    assert wieder.cb_address.isChecked() is True
    assert wieder.cb_ids.isChecked() is True

    # Die gespeicherten Werte landen auch in den Erkennungs-Optionen.
    options = wieder.read_options()
    assert "ch_postal" not in options.rule_groups
    assert "date" in options.rule_groups
    assert options.use_ai is False

    # Zuruecksetzen, damit folgende Laeufe nicht davon abhaengen.
    for box in wieder._auto_boxes().values():
        box.setChecked(True)
    wieder.cb_date.setChecked(False)
    wieder.sensitivity.setCurrentIndex(1)
