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
    # Zugeordnete Dateien stehen nicht mehr unter "zuletzt geschwaerzt".
    assert view.recent.count() == 0

    # Zweimal ablegen legt keinen zweiten Eintrag an.
    mime, event = _drop_event(pfad)
    view.life.dropEvent(event)
    assert view.life.count() == 1

    # Die Zuordnung ueberdauert einen Neuaufbau.
    QtCore.QSettings().sync()
    wieder = CompareView()
    assert wieder.recent.count() == 0
    assert wieder.life.count() == 1
    assert wieder.certs.count() == 0

    # Verschieben in die andere Liste: nur dort steht die Datei noch.
    mime2, event2 = _drop_event(pfad)
    wieder.certs.dropEvent(event2)
    assert wieder.certs.count() == 1
    assert wieder.life.count() == 0

    # Entfernen mit der Entf-Taste leert den Stapel wieder.

    key = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier
    )
    wieder.certs.setCurrentRow(0)
    wieder.certs.keyPressEvent(key)
    assert wieder.certs.count() == 0
    QtCore.QSettings().sync()
    leer = CompareView()
    assert leer.certs.count() == 0

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


def test_uebergabe_beschriftet_lebenslauf_und_zeugnisse(tmp_path):
    from pdfblack.ui import compare

    ordner = tmp_path / "quelle"
    ordner.mkdir()
    life = _pdf(ordner / "bewerbung_mueller.pdf")
    cert = _pdf(ordner / "zeugnis_2024.pdf")
    # Zweite Zeugnisdatei mit gleichem Namen aus einem anderen Ordner.
    zweiter = tmp_path / "alt"
    zweiter.mkdir()
    cert2 = _pdf(zweiter / "zeugnis_2024.pdf")

    ziel = compare.handover_folder("Bewerbungen")
    dateien = compare.handover_files(ziel, [life], [cert, cert2])
    namen = sorted(pfad.name for pfad in dateien)

    assert namen == [
        "Arbeitszeugnis_zeugnis_2024.pdf",
        "Arbeitszeugnis_zeugnis_2024_2.pdf",
        "Lebenslauf_bewerbung_mueller.pdf",
    ]
    assert all(pfad.read_bytes() == b"%PDF-1.4\n%Testdatei\n" for pfad in dateien)

    # Ein zweiter Klick erzeugt dieselben Namen statt immer neuer Zusaetze.
    wieder = compare.handover_files(ziel, [life], [cert, cert2])
    assert sorted(pfad.name for pfad in wieder) == namen


def test_knoepfe_unter_den_zeugnissen(qt_app, settings_dir):
    from pdfblack.ui import compare, preferences

    preferences.save_agents([])
    view = compare.CompareView()
    assert [knopf.text() for knopf in view.agent_buttons] == ["Einstellungen Copilot"]
    assert view.agent_buttons[0].objectName() == "AgentSettings"
    ausgeloest: list[bool] = []
    view.settingsRequested.connect(lambda: ausgeloest.append(True))
    view.agent_buttons[0].click()
    assert ausgeloest == [True]

    preferences.save_agents(
        [{"name": "Bewerbungen", "link": ""}, {"name": "Verträge", "link": ""}]
    )
    view.refresh()
    assert [knopf.text() for knopf in view.agent_buttons] == [
        "An Copilot Agent „Bewerbungen“ übergeben",
        "An Copilot Agent „Verträge“ übergeben",
    ]
    assert all(knopf.objectName() == "Agent" for knopf in view.agent_buttons)
    view.deleteLater()
    qt_app.processEvents()


def test_klick_uebergibt_die_dateien(qt_app, settings_dir, tmp_path, monkeypatch):
    from pdfblack.ui import compare, preferences

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    geoeffnet: list[dict] = []
    monkeypatch.setattr(
        compare.preferences,
        "open_copilot",
        lambda entry=None: geoeffnet.append(entry) or True,
    )
    monkeypatch.setattr(compare.QDesktopServices, "openUrl", lambda url: True)

    preferences.save_agents([{"name": "Bewerbungen", "link": ""}])
    view = compare.CompareView()
    life = _pdf(tmp_path / "bewerbung_mueller.pdf")
    cert = _pdf(tmp_path / "zeugnis_2024.pdf")
    mime, event = _drop_event(life)
    view.life.dropEvent(event)
    mime, event = _drop_event(cert)
    view.certs.dropEvent(event)

    meldungen: list[str] = []
    view.message.connect(meldungen.append)
    view.agent_buttons[0].click()

    assert geoeffnet and geoeffnet[0]["name"] == "Bewerbungen"
    ordner = compare.handover_folder("Bewerbungen")
    assert sorted(pfad.name for pfad in ordner.glob("*.pdf")) == [
        "Arbeitszeugnis_zeugnis_2024.pdf",
        "Lebenslauf_bewerbung_mueller.pdf",
    ]
    assert "2 Dateien" in meldungen[-1]
    zwischenablage = QtWidgets.QApplication.clipboard().text()
    assert "Lebenslauf_bewerbung_mueller.pdf" in zwischenablage

    # Ohne zugeordnete Dateien wird nichts kopiert, sondern nur gemeldet.
    leer = compare.CompareView()
    leer.life.clear()
    leer.certs.clear()
    hinweise: list[str] = []
    leer.message.connect(hinweise.append)
    leer.agent_buttons[0].click()
    assert "Keine Dateien" in hinweise[-1]

    for widget in (view, leer):
        widget.deleteLater()
    qt_app.processEvents()
