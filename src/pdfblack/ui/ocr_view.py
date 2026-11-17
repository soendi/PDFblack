"""PDFocr: Bildscans einlesen und den Text hinter das Bild legen.

Die Seite gehoert zum dritten Programm im Kopfbereich. Sie nimmt eine
PDF-Datei, rendert jede Seite, laesst Tesseract den Text erkennen und legt
ihn unsichtbar und deckungsgleich hinter das Bild. Die neue Datei laesst sich
speichern und anschliessend in PDFblack schwaerzen.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.ocr import (
    SPRACHEN,
    TesserocrEngine,
    has_text,
    ocr_pdf,
)


def make_engine(language: str):
    """Engine fuer die Erkennung bauen (in Tests ersetzbar)."""
    return TesserocrEngine(language=language)


class _OcrWorker(QThread):
    """Erkennung im Hintergrund, damit das Fenster bedienbar bleibt."""

    progressed = Signal(int, int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        src: str,
        dst: str,
        engine,
        password: str | None,
        rechtschreibung: bool = True,
        ersetze_textebene: bool = False,
    ) -> None:
        super().__init__()
        self._src = src
        self._dst = dst
        self._engine = engine
        self._password = password
        self._rechtschreibung = rechtschreibung
        self._ersetze_textebene = ersetze_textebene

    def _progress(self, index: int, total: int, message: str) -> bool:
        if self.isInterruptionRequested():
            return False
        self.progressed.emit(index, total, message)
        return True

    def run(self) -> None:
        try:
            ergebnis = ocr_pdf(
                self._src,
                self._dst,
                self._engine,
                self._password,
                progress=self._progress,
                rechtschreibung=self._rechtschreibung,
                ersetze_textebene=self._ersetze_textebene,
            )
        except Exception as exc:  # noqa: BLE001 - Fehler geht an die Oberflaeche
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
            return
        if not self.isInterruptionRequested():
            self.succeeded.emit(ergebnis)


class OcrView(QWidget):
    """Seite von PDFocr."""

    message = Signal(str)
    openInBlackRequested = Signal(str)
    # Eine Erkennung ist fertig; meldet den Pfad der neuen Datei.
    resultReady = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("OcrWorkspace")
        self.setAcceptDrops(True)
        self._path: str | None = None
        self._password: str | None = None
        self._worker: _OcrWorker | None = None
        self._result_path: str | None = None
        self._target_path: str | None = None
        self._temp_dir: str | None = None
        self._ersetze = False
        self._build_ui()
        self._refresh()

    # -- Aufbau -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        kopf = QHBoxLayout()
        titel = QLabel("Bildscans auslesen")
        titel.setObjectName("CardTitle")
        kopf.addWidget(titel)
        kopf.addStretch(1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        kopf.addWidget(self.status_label)
        layout.addLayout(kopf)

        hinweis = QLabel(
            "PDFocr liest den Text aus Bildscans und legt ihn unsichtbar hinter "
            "das Bild – deckungsgleich, damit die Stelle später genau dort "
            "geschwärzt wird. Danach die Datei speichern und in PDFblack öffnen."
        )
        hinweis.setObjectName("Hint")
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)

        karte = QFrame()
        karte.setObjectName("Card")
        karten_layout = QVBoxLayout(karte)
        karten_layout.setContentsMargins(16, 14, 16, 14)
        karten_layout.setSpacing(10)

        datei_label = QLabel("DATEI")
        datei_label.setObjectName("SectionLabel")
        karten_layout.addWidget(datei_label)

        self.file_label = QLabel("Noch keine Datei gewählt")
        self.file_label.setObjectName("CardTitle")
        self.file_label.setWordWrap(True)
        karten_layout.addWidget(self.file_label)

        self.file_info = QLabel("PDF hierher ziehen oder „PDF öffnen …“ wählen.")
        self.file_info.setObjectName("Hint")
        self.file_info.setWordWrap(True)
        karten_layout.addWidget(self.file_info)

        knoepfe = QHBoxLayout()
        knoepfe.setSpacing(8)
        self.btn_open = QPushButton("PDF öffnen …")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_reset = QPushButton("Zurücksetzen")
        self.btn_reset.setObjectName("Ghost")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        knoepfe.addWidget(self.btn_open)
        knoepfe.addWidget(self.btn_reset)
        knoepfe.addStretch(1)
        knoepfe.addWidget(QLabel("Sprache:"))
        self.language = QComboBox()
        for name in SPRACHEN:
            self.language.addItem(name)
        knoepfe.addWidget(self.language)
        karten_layout.addLayout(knoepfe)

        self.check_spelling = QCheckBox("Rechtschreibung prüfen (Wörterbuch)")
        self.check_spelling.setChecked(True)
        self.check_spelling.setToolTip(
            "Korrigiert klein geschriebene Wörter, die im Dokument nur einmal "
            "vorkommen und eindeutig falsch geschrieben sind. Namen und "
            "Adressen bleiben unangetastet."
        )
        karten_layout.addWidget(self.check_spelling)

        lesen = QHBoxLayout()
        lesen.setSpacing(8)
        self.btn_read = QPushButton("Text erkennen")
        self.btn_read.setObjectName("Primary")
        self.btn_read.setCursor(Qt.PointingHandCursor)
        self.btn_read.setToolTip(
            "Rendert jede Seite in 300 dpi, liest die Wörter und legt sie "
            "unsichtbar hinter das Bild."
        )
        self.btn_read.setMinimumWidth(170)
        self.btn_read.setMaximumWidth(230)
        lesen.addWidget(self.btn_read, 0, Qt.AlignLeft)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setMaximumWidth(320)
        self.progress.hide()
        lesen.addWidget(self.progress, 1)
        karten_layout.addLayout(lesen)

        self.engine_hint = QLabel("")
        self.engine_hint.setObjectName("Danger")
        self.engine_hint.setWordWrap(True)
        self.engine_hint.hide()
        karten_layout.addWidget(self.engine_hint)
        layout.addWidget(karte)

        text_label = QLabel("ERKANNTER TEXT")
        text_label.setObjectName("SectionLabel")
        layout.addWidget(text_label)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText(
            "Noch nichts erkannt. „Text erkennen“ startet die Auswertung."
        )
        layout.addWidget(self.text, 1)

        unten = QHBoxLayout()
        unten.setSpacing(8)
        self.btn_save = QPushButton("Textlayer speichern unter …")
        self.btn_save.setObjectName("Primary")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setToolTip(
            "Schreibt eine neue PDF-Datei mit dem unsichtbaren Textlayer."
        )
        self.btn_black = QPushButton("In PDFblack öffnen")
        self.btn_black.setCursor(Qt.PointingHandCursor)
        self.btn_black.setToolTip("Die neue Datei zum Schwärzen in PDFblack laden.")
        unten.addWidget(self.btn_save)
        unten.addWidget(self.btn_black)
        unten.addStretch(1)
        layout.addLayout(unten)

        self.btn_open.clicked.connect(self._choose_file)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_read.clicked.connect(lambda: self.start())
        self.btn_save.clicked.connect(self._save_as)
        self.btn_black.clicked.connect(self._open_in_black)

    # -- Datei --------------------------------------------------------

    def open_path(
        self,
        path: str,
        password: str | None = None,
        start: bool = False,
        ersetze_textebene: bool = False,
    ) -> None:
        """Datei uebernehmen; optional die Erkennung sofort starten.

        Mit ``ersetze_textebene`` wird eine vorhandene Textebene verworfen und
        aus den gerenderten Seiten neu aufgesetzt. Die Datei selbst bleibt
        unveraendert, das Ergebnis landet in einer neuen Datei.
        """
        self._path = path
        self._password = password
        self._result_path = None
        self._ersetze = ersetze_textebene
        self.text.setPlainText("")
        self.file_label.setText(os.path.basename(path))
        self.file_info.setText(
            "Bereit – die vorhandene Textebene wird verworfen und per OCR neu "
            "aufgesetzt. Die Originaldatei bleibt unverändert."
            if ersetze_textebene
            else "Bereit – „Text erkennen“ startet die Auswertung."
        )
        self.status_label.setText("")
        self._refresh()
        if start:
            self.start()

    def _choose_file(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(
            self, "PDF öffnen", os.path.expanduser("~"), "PDF-Dateien (*.pdf)"
        )
        if pfad:
            self.open_path(pfad, start=True)

    def _reset(self) -> None:
        self._stop_worker()
        self._path = None
        self._password = None
        self._result_path = None
        self._ersetze = False
        self.text.setPlainText("")
        self.file_label.setText("Noch keine Datei gewählt")
        self.file_info.setText("PDF hierher ziehen oder „PDF öffnen …“ wählen.")
        self.status_label.setText("")
        self._refresh()

    # -- Erkennung ----------------------------------------------------

    def engine(self) -> TesserocrEngine:
        return make_engine(SPRACHEN.get(self.language.currentText(), "deu"))

    def check_engine(self, engine: TesserocrEngine | None = None) -> bool:
        """Ist die Erkennung einsatzbereit? Zeigt sonst den Hinweis an."""
        bereit = engine or self.engine()
        if bereit.available():
            self.engine_hint.hide()
            return True
        self.engine_hint.setText(
            "Die eingebaute Texterkennung ist nicht bereit. "
            f"{bereit.fehlt()} Bitte PDFblack neu installieren."
        )
        self.engine_hint.show()
        return False

    def start(self) -> None:
        if not self._path or self._worker is not None:
            return
        engine = self.engine()
        if not self.check_engine(engine):
            return
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="pdfblack-ocr-")
        # Jeder Lauf bekommt eine eigene Datei: das Ergebnis kann bereits in
        # PDFblack geoeffnet sein, waehrend die naechste Erkennung laeuft.
        handle, ziel = tempfile.mkstemp(
            prefix=f"{Path(self._path).stem}_{'neu' if self._ersetze else 'ocr'}-",
            suffix=".pdf",
            dir=self._temp_dir,
        )
        os.close(handle)
        self._target_path = ziel
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status_label.setText("Erkennung läuft …")
        self.text.setPlainText("")
        self._refresh(busy=True)

        self._worker = _OcrWorker(
            self._path,
            ziel,
            engine,
            self._password,
            rechtschreibung=self.check_spelling.isChecked(),
            ersetze_textebene=self._ersetze,
        )
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait(2000)
            self._worker = None

    def _on_progress(self, index: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(index)
        self.status_label.setText(message)

    def _on_done(self, result) -> None:
        self._result_path = self._target_path
        self.text.setPlainText(result.text.strip())
        seiten = result.pages
        teile = [
            f"{result.words} Wörter auf {seiten} Seite(n) erkannt",
        ]
        if result.skipped:
            teile.append(
                f"{len(result.skipped)} Seite(n) hatten bereits Text und blieben unverändert"
            )
        if self._ersetze:
            teile.append("Textebene neu aufgesetzt")
        meldung = " · ".join(teile)
        self.status_label.setText(meldung)
        self.file_info.setText(
            "Fertig – Textlayer ist unsichtbar hinter dem Bild. "
            "Jetzt speichern oder in PDFblack öffnen."
        )
        if self._ersetze:
            self.file_info.setText(
                "Fertig – die Textebene wurde neu aufgesetzt; die Originaldatei "
                "ist unverändert. Jetzt speichern oder in PDFblack öffnen."
            )
        self.message.emit(meldung)
        self._refresh()
        self.resultReady.emit(self._result_path)

    def _on_failed(self, meldung: str) -> None:
        self.status_label.setText("Erkennung fehlgeschlagen.")
        self.engine_hint.setText(meldung)
        self.engine_hint.show()
        self.message.emit(f"OCR fehlgeschlagen: {meldung}")

    def _on_finished(self) -> None:
        self._worker = None
        self.progress.hide()
        self._refresh()

    # -- Ergebnis -----------------------------------------------------

    def _save_as(self) -> None:
        if not self._result_path or not Path(self._result_path).exists():
            return
        basis = Path(self._path).stem if self._path else "scan"
        vorgabe = os.path.join(
            str(Path(self._path).parent) if self._path else os.path.expanduser("~"),
            f"{basis}_ocr.pdf",
        )
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Textlayer speichern unter …", vorgabe, "PDF-Dateien (*.pdf)"
        )
        if not ziel:
            return
        if not ziel.lower().endswith(".pdf"):
            ziel += ".pdf"
        try:
            shutil.copyfile(self._result_path, ziel)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(exc))
            return
        self._result_path = ziel
        self.status_label.setText(f"Gespeichert: {ziel}")
        self.message.emit(f"Textlayer gespeichert: {ziel}")
        self._refresh()

    def _open_in_black(self) -> None:
        if self._result_path:
            self.openInBlackRequested.emit(self._result_path)

    def cleanup_temp(self, keep: str | None = None) -> None:
        """Arbeitsdateien der Erkennung loeschen.

        Mit ``keep`` bleibt genau diese Datei stehen; das Beenden raeumt
        zuerst alles andere weg und die geoeffnete Datei erst, nachdem das
        Dokument geschlossen ist.
        """
        if not self._temp_dir:
            return
        ordner = Path(self._temp_dir)
        behalten = os.path.abspath(keep) if keep else None
        for datei in ordner.glob("*.pdf"):
            if behalten and os.path.abspath(str(datei)) == behalten:
                continue
            try:
                datei.unlink()
            except OSError:  # belegt oder schon weg - beim Raeumen egal
                pass
        if behalten is None:
            shutil.rmtree(ordner, ignore_errors=True)
            self._temp_dir = None

    # -- Zustand ------------------------------------------------------

    def _refresh(self, busy: bool = False) -> None:
        hat_datei = bool(self._path)
        laeuft = busy or self._worker is not None
        hat_ergebnis = bool(self._result_path and Path(self._result_path).exists())
        self.btn_open.setEnabled(not laeuft)
        self.btn_reset.setEnabled(not laeuft and hat_datei)
        self.btn_read.setEnabled(hat_datei and not laeuft)
        self.language.setEnabled(not laeuft)
        self.check_spelling.setEnabled(not laeuft)
        self.btn_save.setEnabled(hat_ergebnis and not laeuft)
        self.btn_black.setEnabled(hat_ergebnis and not laeuft)

    # -- Drag and Drop ------------------------------------------------

    @staticmethod
    def _pdf_from_event(event) -> str | None:
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            pfad = url.toLocalFile()
            if pfad.lower().endswith(".pdf"):
                return pfad
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._pdf_from_event(event) and self._worker is None:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        pfad = self._pdf_from_event(event)
        if pfad:
            event.acceptProposedAction()
            self.open_path(pfad, start=True)


__all__ = ["OcrView", "has_text", "make_engine"]
