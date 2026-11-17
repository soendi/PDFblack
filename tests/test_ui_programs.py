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

    # PDFocr bekommt den Scan und liest ihn aus. Mit einer sofort fertigen
    # Ersatz-Engine steht das Ergebnis schon in PDFblack, bevor hier geprueft
    # wird - deshalb haengt der Test nicht am Zwischenzustand.
    assert _wait_until(lambda: window.ocr_view._path == str(scan)), "Scan nicht übergeben"
    assert window.ocr_view.btn_read.text() == "Text erkennen"
    assert _wait_until(lambda: window.ocr_view._result_path is not None), "OCR lief nicht"

    doc = pymupdf.open(window.ocr_view._result_path)
    assert "Dachdecker" in doc[0].get_text()
    doc.close()

    # Ist die Erkennung fertig, steht der Scan von selbst in PDFblack.
    ergebnis = window.ocr_view._result_path
    assert _wait_until(lambda: window._path == ergebnis), "Ergebnis nicht geladen"
    assert _wait_until(lambda: window.workspace.currentWidget() is window.black_view)
    assert window._program == "pdfblack"
    assert window.ocr_view._result_path == ergebnis

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


def test_arbeitsdateien_der_erkennung_verschwinden_beim_beenden(
    window, tmp_path, monkeypatch
):
    """Die Temp-Dateien der Texterkennung werden beim Beenden aufgeraeumt."""
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
    assert _wait_until(
        lambda: window._path == window.ocr_view._result_path, 8000
    ), "Ergebnis nicht geladen"
    ergebnis = Path(window.ocr_view._result_path)
    ordner = ergebnis.parent
    assert ergebnis.exists()

    # Ein zweiter Lauf legt eine weitere Arbeitsdatei an - beide raeumen sich.
    zweiter = tmp_path / "scan2.pdf"
    _scan_pdf(zweiter)
    window.ocr_view.open_path(str(zweiter), start=True)
    assert _wait_until(
        lambda: len(list(ordner.glob("scan2_ocr-*.pdf"))) > 0, 8000
    ), "zweiter Lauf ohne Ergebnis"
    assert len(list(ordner.glob("*.pdf"))) >= 2

    window.close()
    QtTest.QTest.qWait(200)
    assert not ergebnis.exists(), "Arbeitsdatei blieb liegen"
    assert not ordner.exists(), "Temp-Ordner blieb liegen"


def test_drittes_programm_pdfocr(window):
    """PDFocr: gruener Button, eigene leere Seite, Text nur beim aktiven Programm."""
    header = window.header
    _click(header.ocr.logo)
    assert _wait_until(lambda: window.workspace.currentWidget() is window.ocr_view)
    QtTest.QTest.qWait(600)

    assert window._program == "pdfocr"
    # Blau steht neben rot, gruen direkt neben blau - Reihenfolge bleibt.
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


def test_blau_faehrt_allein_nach_links(window):
    """Klick auf PDFcompare: blau faehrt neben rot, gruen bleibt stehen."""
    header = window.header
    QtTest.QTest.qWait(100)
    gruen_ruhe = header.ocr_rest_x()
    assert header.ocr.x() == gruen_ruhe

    _click(header.compare.logo)
    assert _wait_until(lambda: window.workspace.currentWidget() is window.compare_view)
    QtTest.QTest.qWait(600)

    assert header.compare.x() == header.title_x()
    # Gruen ruehrt sich nicht und bleibt rechts von blau.
    assert header.ocr.x() == gruen_ruhe
    assert header.compare.x() < header.ocr.x()
    assert header.black.x() == header.MARGIN


def test_drei_buttons_stehen_nebeneinander(window):
    """In Ruhestellung steht der gruene Button rechts neben dem blauen."""
    header = window.header
    QtTest.QTest.qWait(100)
    assert header.black.x() == header.MARGIN
    assert header.ocr.x() > header.compare.x()
    # Direkt hinter dem blauen Logo - genau dort, wo sein Text anfaengt.
    assert header.ocr.x() == header.compare_rest_x() + header.LOGO_SIZE + header.GAP
    assert header.ocr.x() + header.LOGO_SIZE <= header.width()
    assert header.ocr.title.text() == "PDFocr"
    assert header.ocr.subtitle.text().startswith("Liest aus Bildscans")


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


def test_jedes_logo_bleibt_klickbar(window, qt_app):
    """Jeder Kopfknopf wird in jeder Stellung getroffen."""
    header = window.header
    for zustand in ("pdfblack", "pdfcompare", "pdfocr"):
        header.set_program(zustand, animate=False)
        qt_app.processEvents()
        for block in (header.black, header.compare, header.ocr):
            punkt = block.mapTo(header, block.logo.rect().center())
            treffer = header.childAt(punkt)
            assert treffer is block.logo, (zustand, block, treffer)


def test_mittlerer_knopf_nach_dem_verschieben(window, qt_app):
    """Blau bleibt anklickbar, wenn es neben rot steht."""
    header = window.header
    _click(header.ocr.logo)
    assert _wait_until(lambda: window._program == "pdfocr")
    QtTest.QTest.qWait(600)

    punkt = header.compare.mapTo(header, header.compare.logo.rect().center())
    ziel = header.childAt(punkt)
    assert ziel is header.compare.logo
    QtTest.QTest.mouseClick(ziel, QtCore.Qt.LeftButton)
    assert _wait_until(lambda: window._program == "pdfcompare")


def _text_pdf(path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Ein normaler Brief mit Text.", fontsize=12)
    doc.save(str(path))
    doc.close()


def _fake_engine(monkeypatch):
    from pdfblack.core.ocr import Word
    from pdfblack.ui import ocr_view

    class FakeEngine:
        name = "Test"

        def available(self) -> bool:
            return True

        def read_words(self, png, size):
            return [Word("Brief", (300.0, 600.0, 420.0, 640.0))]

    monkeypatch.setattr(ocr_view, "make_engine", lambda language: FakeEngine())


def test_textebene_neu_aufsetzen_wird_angeboten(window, qt_app, tmp_path, monkeypatch):
    """PDF mit Textebene: Angebot einblenden, Original bleibt unberuehrt."""
    _fake_engine(monkeypatch)
    text_pdf = tmp_path / "brief.pdf"
    _text_pdf(text_pdf)
    vorher = text_pdf.read_bytes()

    window.load_pdf(str(text_pdf))
    qt_app.processEvents()

    assert window.rebuild_bar.isVisible()
    assert "Textebene" in window.rebuild_label.text()

    gestartet = []
    monkeypatch.setattr(window.ocr_view, "start", lambda: gestartet.append(True))
    _click(window.btn_rebuild)

    assert not window.rebuild_bar.isVisible()
    assert window.ocr_view._ersetze is True
    assert window.ocr_view._path == str(text_pdf)
    assert gestartet == [True]
    assert _wait_until(lambda: window._program == "pdfocr")
    # Die Originaldatei wurde nur gelesen.
    assert text_pdf.read_bytes() == vorher


def test_angebot_laesst_sich_ablehnen(window, qt_app, tmp_path, monkeypatch):
    _fake_engine(monkeypatch)
    text_pdf = tmp_path / "brief.pdf"
    _text_pdf(text_pdf)

    window.load_pdf(str(text_pdf))
    qt_app.processEvents()
    assert window.rebuild_bar.isVisible()

    gestartet = []
    monkeypatch.setattr(window.ocr_view, "start", lambda: gestartet.append(True))
    _click(window.btn_keep)

    assert not window.rebuild_bar.isVisible()
    assert gestartet == []
    assert window._program == "pdfblack"


def test_ohne_tesseract_kein_angebot(window, qt_app, tmp_path, monkeypatch):
    from pdfblack.ui import ocr_view

    class Stumm:
        name = "Stumm"

        def available(self) -> bool:
            return False

    monkeypatch.setattr(ocr_view, "make_engine", lambda language: Stumm())
    text_pdf = tmp_path / "brief.pdf"
    _text_pdf(text_pdf)

    window.load_pdf(str(text_pdf))
    qt_app.processEvents()

    assert not window.rebuild_bar.isVisible()
    assert window._rebuild_source is None


def test_erkennung_startet_beim_oeffnen_von_selbst(
    window, qt_app, tmp_path, monkeypatch
):
    """PDF mit Textebene: Treffer erscheinen ohne Klick auf „Vorschau erzeugen“."""
    import pymupdf

    # Die conftest.py schaltet die Automatik fuer UI-Tests ab - hier nicht.
    monkeypatch.delenv("PDFBLACK_NO_AUTO_DETECT", raising=False)

    pdf = tmp_path / "brief.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Personalnummer: 4711-2233", fontsize=12)
    doc.save(str(pdf))
    doc.close()

    # KI aus: die Muster finden die Nummer, der Test bleibt schnell.
    window.controls.ai_check.setChecked(False)

    window.load_pdf(str(pdf))
    assert window._worker is not None or window._busy

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if window._worker is None and not window._busy:
            break
        QtTest.QTest.qWait(50)

    assert not window._busy
    texte = [finding.text for finding in window._findings]
    assert any("4711-2233" in text for text in texte), texte


def test_geschwaerzte_kopie_landet_im_benutzerordner(
    window, qt_app, tmp_path, monkeypatch
):
    """Speichern fragt nicht mehr nach einem Ort, sondern nutzt die Ablage."""
    import pymupdf

    from pdfblack.core import ablage
    from pdfblack.ui import main_window

    monkeypatch.setattr(ablage, "ORDNER", tmp_path / "Ablage")
    monkeypatch.setattr(
        main_window.QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )

    pdf = tmp_path / "Brief.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Personalnummer: 4711-2233", fontsize=12)
    doc.save(str(pdf))
    doc.close()

    assert window.btn_save.text() == "Geschwärzte Kopie speichern"

    window.controls.ai_check.setChecked(False)
    window.load_pdf(str(pdf))
    window._run_detection()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if window._worker is None and not window._busy and window._findings:
            break
        QtTest.QTest.qWait(50)
    assert window._findings, "ohne Treffer gibt es nichts zu speichern"

    window._save_as()

    kopien = ablage.dateien()
    assert [datei.name for datei in kopien] == ["Brief_geschwaerzt.pdf"]
    doc = pymupdf.open(str(kopien[0]))
    try:
        assert "4711-2233" not in doc[0].get_text()
    finally:
        doc.close()

    # Das Original bleibt unveraendert.
    doc = pymupdf.open(str(pdf))
    try:
        assert "4711-2233" in doc[0].get_text()
    finally:
        doc.close()

    # Beim Beenden wird die Ablage geleert.
    window.close()
    qt_app.processEvents()
    assert ablage.dateien() == []


def test_rechtsklick_ordnet_neu_und_schreibt_die_lerndatei(
    window, qt_app, tmp_path, monkeypatch
):
    """Kategorie im Kontextmenü ändern und als Lernbeispiel ablegen."""
    from pdfblack.core import lerndatei
    from pdfblack.core.models import Category, Finding

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    finding = Finding(
        text="Muster AG",
        category=Category.COMPANY,
        page=0,
        rects=[(10.0, 20.0, 80.0, 34.0)],
        source="KI (Presidio) · LOCATION",
        entity="LOCATION",
        score=0.8,
        uid=1,
    )
    window._findings = [finding]
    window._next_uid = 2
    window._sync_findings()
    qt_app.processEvents()

    panel = window.findings_panel
    menu = panel._menu_for(0)
    assert menu is not None
    texte = [aktion.text() for aktion in menu.actions()]
    assert "Person" in texte and "Adresse" in texte
    assert "Kein Treffer (Fehlalarm)" in texte
    firma = next(aktion for aktion in menu.actions() if aktion.text() == "Firma")
    assert firma.isChecked(), "die aktuelle Kategorie ist angehakt"
    menu.deleteLater()

    panel.categoryChanged.emit(1, Category.PERSON, False)
    qt_app.processEvents()
    assert finding.category is Category.PERSON
    assert "vom Benutzer korrigiert" in finding.source
    beispiele = lerndatei.eintraege()
    assert beispiele[-1]["kategorie_vorher"] == "Firma"
    assert beispiele[-1]["kategorie_nachher"] == "Person"
    assert beispiele[-1]["gleichnamige_treffer"] == 1

    panel.falsePositiveRequested.emit(1, False)
    qt_app.processEvents()
    assert finding.enabled is False
    assert lerndatei.eintraege()[-1]["kategorie_nachher"] == "kein Treffer"
    assert lerndatei.eintraege()[-1]["kategorie_vorher"] == "Person"


def test_kategorie_gilt_auf_wunsch_fuer_alle_gleichen(window, qt_app, tmp_path, monkeypatch):
    """Rechtsklick auf einen von 15 gleichen Treffern ändert alle auf einmal."""
    from pdfblack.core import lerndatei
    from pdfblack.core.models import Category, Finding

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    treffer = [
        Finding(
            text="Fachmessen",
            category=Category.POSTAL,
            page=seite,
            rects=[(10.0, 20.0, 80.0, 34.0)],
            source="KI (Presidio) · LOCATION",
            entity="LOCATION",
            score=0.6,
            uid=seite + 1,
        )
        for seite in range(3)
    ]
    window._findings = list(treffer)
    window._next_uid = 10
    window._sync_findings()
    qt_app.processEvents()

    panel = window.findings_panel
    menu = panel._menu_for(0)
    assert menu is not None
    texte = [aktion.text() for aktion in menu.actions()]
    assert any("als Fehlalarm abhaken" in text for text in texte)
    untermenue = next(
        aktion.menu() for aktion in menu.actions() if aktion.menu() is not None
    )
    assert [aktion.data() for aktion in untermenue.actions()][0] == "alle:Person"
    menu.deleteLater()

    panel.categoryChanged.emit(1, Category.PERSON, True)
    qt_app.processEvents()
    assert {finding.category for finding in treffer} == {Category.PERSON}
    assert lerndatei.eintraege()[-1]["gleichnamige_treffer"] == 3

    panel.falsePositiveRequested.emit(1, True)
    qt_app.processEvents()
    assert not any(finding.enabled for finding in treffer)
    assert lerndatei.eintraege()[-1]["kategorie_nachher"] == "kein Treffer"
    assert lerndatei.eintraege()[-1]["gleichnamige_treffer"] == 3


def test_status_nennt_die_wirkung_der_lerndatei(window, qt_app):
    """Die Statuszeile sagt, was die Lerndatei abgehakt und umkategorisiert hat."""
    from pdfblack.core.detect import DetectionResult
    from pdfblack.core.models import Category, Finding

    treffer = Finding(
        text="4711-2233",
        category=Category.ID,
        page=0,
        rects=[(1.0, 2.0, 3.0, 4.0)],
        enabled=False,
        uid=1,
    )
    window._on_detection_done(
        DetectionResult([treffer], [], learned_off=1, learned_changed=2)
    )

    text = window.statusBar().currentMessage()
    assert "1 abgehakt" in text
    assert "2 umkategorisiert" in text


def test_lerndatei_zuruecksetzen_fragt_nach(window, qt_app, tmp_path, monkeypatch):
    """Zurücksetzen nur nach Bestätigung; der Menüeintrag ist vorhanden."""
    from pdfblack.core import lerndatei
    from pdfblack.core.models import Category, Finding
    from pdfblack.ui import main_window as mw

    class _FakeBox:
        """Ersetzt QMessageBox im Test - es darf kein Dialog aufgehen."""

        Yes, No = True, False
        antwort = False
        gemeldet: list[str] = []

        @classmethod
        def question(cls, *args, **kwargs):
            return cls.antwort

        @classmethod
        def information(cls, *args, **kwargs):
            cls.gemeldet.append(str(args[2]) if len(args) > 2 else "")

        @classmethod
        def critical(cls, *args, **kwargs):
            cls.gemeldet.append(str(args[2]) if len(args) > 2 else "")

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    lerndatei.merken(
        lerndatei.korrektur(
            Finding(text="4711-2233", category=Category.ID, page=0, uid=1),
            "",
            Category.ID,
            Category.PERSON,
        )
    )
    assert lerndatei.eintraege()

    # Abbrechen laesst die gelernten Beispiele stehen.
    _FakeBox.antwort = _FakeBox.No
    window._reset_lerndatei()
    assert lerndatei.eintraege()

    # Zustimmen verwirft sie.
    _FakeBox.antwort = _FakeBox.Yes
    window._reset_lerndatei()
    assert lerndatei.eintraege() == []

    texte = [
        aktion.text()
        for menue in window.menuBar().findChildren(QtWidgets.QMenu)
        for aktion in menue.actions()
    ]
    assert "Lerndatei zurücksetzen …" in texte
    assert "Lerndatei herunterladen …" in texte
    assert "Lerndatei ansehen …" in texte


def test_menue_oeffnet_das_lernfenster(window, qt_app, monkeypatch):
    """„Lerndatei ansehen …“ öffnet das Fenster; ohne Löschung passiert nichts."""
    from pdfblack.ui import main_window as mw

    aufgerufen: list[object] = []

    class _FakeFenster:
        geloescht = 0

        def __init__(self, parent=None):
            aufgerufen.append(parent)

        def exec(self):
            aufgerufen.append("exec")
            return 0

    monkeypatch.setattr(mw, "Lernfenster", _FakeFenster)
    window._show_lerndatei()

    assert aufgerufen[0] is window
    assert aufgerufen[1] == "exec"
    assert len(aufgerufen) == 2, "ohne Löschung wird keine Erkennung gestartet"


def test_lernfenster_zeigt_und_loescht_einzelne_beispiele(
    qt_app, tmp_path, monkeypatch
):
    """Das Fenster listet die Beispiele und löscht nur die markierten."""
    from pdfblack.core import lerndatei
    from pdfblack.core.models import Category, Finding
    from pdfblack.ui.lernfenster import Lernfenster

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(
            Finding(text="Fachmessen", category=Category.POSTAL, page=0, uid=1),
            "Die Fachmessen 2026 in Zuerich",
            Category.POSTAL,
            Category.PERSON,
        )
    )
    lerndatei.merken(
        lerndatei.korrektur(
            Finding(text="Muster AG", category=Category.COMPANY, page=0, uid=2),
            "",
            Category.COMPANY,
            None,
        )
    )

    fenster = Lernfenster()
    assert fenster.table.rowCount() == 2
    assert [fenster.table.item(zeile, 0).text() for zeile in range(2)] == [
        "Fachmessen",
        "Muster AG",
    ]
    assert fenster.table.item(0, 1).text() == "PLZ / Ort"
    assert fenster.table.item(0, 2).text() == "Person"
    assert fenster.table.item(1, 2).text() == "kein Treffer"
    assert fenster.table.item(0, 0).toolTip().startswith("Seite 1")
    assert fenster.btn_delete.isEnabled() is False

    fenster.table.selectRow(0)
    qt_app.processEvents()
    assert fenster.btn_delete.isEnabled()
    assert fenster.loeschen() == 1
    assert fenster.geloescht == 1
    assert fenster.table.rowCount() == 1
    assert [eintrag["text"] for eintrag in lerndatei.eintraege()] == ["Muster AG"]
    fenster.close()
