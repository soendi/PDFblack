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
    alt = QtCore.QSettings.defaultFormat()
    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))
    # Unter Windows liegen NativeFormat-Einstellungen in der Registry, dort
    # greift setPath nicht. Darum schreiben die Tests in eine INI-Datei.
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    try:
        yield tmp_path
    finally:
        QtCore.QSettings.setDefaultFormat(alt)


def _same(pfad: str) -> str:
    """Pfad so vergleichen, wie die Listen ihn ablegen (unter Windows egal welche Schreibweise)."""
    return os.path.normcase(os.path.abspath(str(pfad)))


def _pfade(liste) -> list[str]:
    return [_same(pfad) for pfad in liste.paths()]


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
    geoeffnet: list[tuple] = []
    monkeypatch.setattr(
        compare.preferences,
        "open_copilot",
        lambda entry=None, **kwargs: geoeffnet.append((entry, kwargs)) or True,
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

    assert geoeffnet and geoeffnet[0][0]["name"] == "Bewerbungen"
    # Frage und Datei gehen an Copilot, nicht nur der Ordner.
    assert geoeffnet[0][1]["prompt"] == compare.HANDOVER_PROMPT
    assert geoeffnet[0][1]["file"].endswith("Lebenslauf_bewerbung_mueller.pdf")
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


def test_copilot_uri_traegt_frage_und_datei():
    """Der Aufruf an Copilot enthaelt Prompt und Datei."""
    from pdfblack.ui import preferences

    assert preferences.copilot_uri() == preferences.COPILOT_URI
    uri = preferences.copilot_uri("Bitte prüfen", r"C:\temp\meine datei.pdf")
    assert uri.startswith("ms-copilot:chat?")
    assert "q=Bitte%20pr%C3%BCfen" in uri
    assert r"file=C:\temp\meine%20datei.pdf" in uri


def test_stapel_werden_zu_einer_pdf(tmp_path):
    """Mehrere Dokumente werden fuer Copilot zu einer Datei gebuendelt."""
    import pymupdf

    from pdfblack.ui.compare import bundle_pdfs

    pfade = []
    for nummer in (1, 2):
        doc = pymupdf.open()
        seite = doc.new_page()
        seite.insert_text((72, 72), f"Dokument {nummer}")
        pfad = tmp_path / f"teil{nummer}.pdf"
        doc.save(str(pfad))
        doc.close()
        pfade.append(pfad)

    ziel = tmp_path / "Unterlagen.pdf"
    assert bundle_pdfs(pfade, ziel) == ziel
    doc = pymupdf.open(str(ziel))
    assert doc.page_count == 2
    doc.close()

    # Nicht lesbare Dateien allein ergeben kein Buendel.
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"kein pdf")
    assert bundle_pdfs([kaputt], tmp_path / "leer.pdf") is None


def test_ziehen_zwischen_allen_listen(qt_app, settings_dir, tmp_path):
    """Auch zurueck: Lebenslauf -> Zeugnisse, Stapel -> Zuletzt geschwaerzt."""
    from pdfblack.ui import compare

    view = compare.CompareView()
    view.clear_all()
    leben = _pdf(tmp_path / "lebenslauf.pdf")
    zeugnis = _pdf(tmp_path / "zeugnis.pdf")
    mime, event = _drop_event(leben)
    view.life.dropEvent(event)
    mime, event = _drop_event(zeugnis)
    view.certs.dropEvent(event)
    assert _pfade(view.life) == [_same(leben)]
    assert _pfade(view.certs) == [_same(zeugnis)]

    # Lebenslauf -> Arbeitszeugnisse
    mime, event = _drop_event(leben)
    view.certs.dropEvent(event)
    assert view.life.count() == 0 and _same(leben) in _pfade(view.certs)

    # Arbeitszeugnisse -> Zuletzt geschwaerzt
    mime, event = _drop_event(leben)
    view.recent.dropEvent(event)
    assert _same(leben) in _pfade(view.recent)
    assert _same(leben) not in _pfade(view.certs)
    assert _same(view.recent.item(0).data(QtCore.Qt.UserRole)) == _same(leben)

    # und zurueck in einen Stapel
    mime, event = _drop_event(leben)
    view.life.dropEvent(event)
    assert _pfade(view.life) == [_same(leben)]
    assert _same(leben) not in _pfade(view.recent)

    view.deleteLater()
    qt_app.processEvents()


def test_knoepfe_leeren_einzelne_listen(qt_app, settings_dir, tmp_path):
    """Drei Knoepfe unter der linken Liste leeren je eine Liste."""
    from pdfblack.ui import compare

    view = compare.CompareView()
    view.clear_all()
    for name in ("a.pdf", "b.pdf"):
        view.remember(_pdf(tmp_path / name))
    mime, event = _drop_event(_pdf(tmp_path / "leben.pdf"))
    view.life.dropEvent(event)
    mime, event = _drop_event(_pdf(tmp_path / "zeugnis.pdf"))
    view.certs.dropEvent(event)

    knoepfe = [
        knopf
        for knopf in view.findChildren(QtWidgets.QPushButton)
        if knopf.objectName() == "Ghost"
    ]
    assert [knopf.text() for knopf in knoepfe] == [
        "Zuletzt leeren",
        "Lebenslauf leeren",
        "Zeugnisse leeren",
    ]

    knoepfe[1].click()
    assert view.life.count() == 0
    assert view.certs.count() == 1 and view.recent.count() == 2

    knoepfe[0].click()
    assert view.recent.count() == 0

    view.deleteLater()
    qt_app.processEvents()


def test_muellimer_entfernt_nur_aus_der_liste(
    qt_app, settings_dir, tmp_path, monkeypatch
):
    from pdfblack.ui import compare

    datei = _pdf(tmp_path / "zeugnis.pdf")
    view = compare.CompareView()
    view.clear_all()
    mime, event = _drop_event(datei)
    view.certs.dropEvent(event)
    assert view.certs.count() == 1

    gefragt: list[str] = []

    def frage(*args, **kwargs):
        gefragt.append(args[1])
        return QtWidgets.QMessageBox.Yes

    monkeypatch.setattr(compare.QMessageBox, "question", frage)
    mime, event = _drop_event(datei)
    view.trash.dropEvent(event)

    assert gefragt and "Wirklich entfernen" in gefragt[0]
    assert view.certs.count() == 0
    assert Path(datei).exists()  # Originaldatei bleibt

    view.deleteLater()
    qt_app.processEvents()


def test_schliessen_leert_listen_und_loescht_dateien(
    qt_app, settings_dir, tmp_path, monkeypatch
):
    from pdfblack.ui import compare

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    datei = tmp_path / "geschwaerzt.pdf"
    datei.write_bytes(b"%PDF-1.4\n")
    view = compare.CompareView()
    view.clear_all()
    mime, event = _drop_event(str(datei))
    view.life.dropEvent(event)

    ordner = compare.handover_folder("Bewerbungen")
    ordner.mkdir(parents=True)
    kopie = ordner / "Lebenslauf_geschwaerzt.pdf"
    kopie.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        compare.QMessageBox, "question", lambda *a, **k: QtWidgets.QMessageBox.Yes
    )
    view.cleanup_on_close(view)

    assert view.recent.count() == 0 and view.life.count() == 0
    assert view.certs.count() == 0
    assert not datei.exists()
    assert not kopie.exists()
    assert not ordner.exists()  # leerer Agent-Ordner wird entfernt

    view.deleteLater()
    qt_app.processEvents()


def test_schliessen_behaelt_dateien_bei_abgelehnter_frage(
    qt_app, settings_dir, tmp_path, monkeypatch
):
    from pdfblack.ui import compare

    datei = tmp_path / "behalten.pdf"
    datei.write_bytes(b"%PDF-1.4\n")
    view = compare.CompareView()
    view.clear_all()
    mime, event = _drop_event(str(datei))
    view.certs.dropEvent(event)

    monkeypatch.setattr(
        compare.QMessageBox, "question", lambda *a, **k: QtWidgets.QMessageBox.No
    )
    view.cleanup_on_close(view)

    assert view.certs.count() == 0  # Listen sind trotzdem geleert
    assert datei.exists()  # Datei bleibt

    view.deleteLater()
    qt_app.processEvents()


def test_pruefung_ist_fakultativ(qt_app, settings_dir, monkeypatch):
    from pdfblack.ui import compare, preferences

    preferences.set_review_enabled(True)
    view = compare.CompareView()
    assert view.review_button.isHidden() is False

    preferences.set_review_enabled(False)
    view.refresh()
    assert view.review_button.isHidden() is True

    # Ausgeschaltet oeffnet der Knopf auch bei einem Klick nichts.
    geoeffnet: list[tuple] = []
    monkeypatch.setattr(
        compare, "ReviewDialog", lambda *args, **kwargs: geoeffnet.append(args)
    )
    view.review_button.click()
    assert geoeffnet == []

    preferences.set_review_enabled(True)
    view.refresh()
    assert view.review_button.isHidden() is False
    view.deleteLater()
    qt_app.processEvents()


def test_einstellungen_schalten_die_pruefung(qt_app, settings_dir):
    from pdfblack.ui import preferences

    dialog = preferences.PreferencesDialog()
    assert dialog.review.isChecked() is True
    dialog.review.setChecked(False)
    dialog.accept()
    assert preferences.review_enabled() is False

    wieder = preferences.PreferencesDialog()
    assert wieder.review.isChecked() is False
    for widget in (dialog, wieder):
        widget.deleteLater()
    qt_app.processEvents()
