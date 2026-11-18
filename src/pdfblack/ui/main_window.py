"""Hauptfenster: Datei laden, Vorschau erzeugen, pruefen, schwaerzen speichern."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, APP_TAGLINE, APP_VERSION
from ..core import ablage, lerndatei, ocr as ocr_core, plausibel
from ..core.detect import DetectionOptions, run_detection
from ..core.extract import TextMap, open_document
from ..core.models import Category, Finding, PdfPasswordError
from ..core.redact import apply_redactions, erweitere_rects
from ..core.updater import (
    Release,
    asset_for,
    download,
    fetch_latest,
    install,
    is_newer,
)
from .branding import compare_logo_pixmap, logo_pixmap, ocr_logo_pixmap
from .compare import CompareView, delete_redacted
from .lernfenster import Lernfenster
from .ocr_view import OcrView
from .preferences import PreferencesDialog
from .canvas import PdfCanvas
from .panels import ControlsPanel, DropZone, FindingsPanel
from .treffermenue import (
    AKTION_ALLE_FEHLALARM,
    AKTION_ALLE_KATEGORIE,
    AKTION_ALLE_UMSCHALTEN,
    AKTION_FEHLALARM,
    AKTION_HINWEIS_OK,
    AKTION_KATEGORIE,
    AKTION_KORRIGIEREN,
    AKTION_UMSCHALTEN,
    WAHL_KATEGORIEN,
    treffer_menue,
)

COMPARE_NAME = "PDFcompare"
COMPARE_TAGLINE = "Vergleicht PDFs miteinander und gibt eine Zusammenfassung aus"
OCR_NAME = "PDFocr"
OCR_TAGLINE = "Liest aus Bildscans den Text aus PDF Dateien."


PRIVACY_HTML = """
<h3>Alles bleibt auf diesem Rechner</h3>
<p>PDFblack liest, prüft und schwärzt PDF-Dateien ausschließlich lokal auf dem
Rechner, auf dem das Programm läuft. Der Inhalt Ihrer Dokumente, die erkannten
Namen und Adressen sowie die Namen der geöffneten Dateien werden nicht
übertragen – weder an den Hersteller noch an Dritte.</p>

<p><b>Microsoft Presidio ist kein Cloud-Dienst.</b> Presidio ist eine
Open-Source-Bibliothek (MIT-Lizenz), die im Programm selbst mitläuft – zusammen
mit dem Sprachmodell spaCy. Der Name „Microsoft“ bezeichnet nur die Herkunft des
Projekts, nicht einen Empfänger Ihrer Daten. Es gibt keine Serveradresse, an die
Text geschickt würde, und die Erkennung funktioniert auch ohne
Internetverbindung.</p>

<p><b>Netzwerkverbindungen</b> gibt es nur eine, und Sie lösen sie selbst aus:
die Update-Prüfung. Sie fragt beim Start bei GitHub (github.com bzw.
api.github.com) nach einer neueren Version. Dabei werden nur die IP-Adresse,
eine Programm-Kennung und die installierte Versionsnummer übertragen – kein
Dokumentinhalt und keine Dateinamen. Abschalten lässt sich das über
<tt>pdfblack --no-update</tt> oder die Umgebungsvariable
<tt>PDFBLACK_NO_UPDATE=1</tt>.</p>

<p>Die Texterkennung läuft vollständig im Programm mit: Tesseract und die
Sprachdateien sind mit installiert. Es wird nichts nachinstalliert und nichts
nachgeladen.</p>

<h3>Was das datenschutzrechtlich bedeutet</h3>
<ul>
<li>Ihre Daten werden nicht an einen Auftragsverarbeiter weitergegeben; ein
Vertrag zur Auftragsverarbeitung nach Art. 28 DSGVO ist dafür nicht
erforderlich.</li>
<li>Es findet keine Übermittlung in ein Drittland statt (Art. 44 ff. DSGVO),
weil keine Daten das Gerät verlassen.</li>
<li>Verantwortlich für die Verarbeitung bleiben Sie bzw. Ihre Organisation –
PDFblack ist ein Werkzeug, das auf Ihrem Gerät arbeitet.</li>
</ul>

<h3>Was Sie selbst beachten sollten</h3>
<ul>
<li>Die geschwärzte Fassung ist eine neue Datei; das Original bleibt unverändert
und enthält weiterhin alle Daten. Geben Sie nur die geschwärzte Datei weiter und
löschen Sie das Original, wenn es nicht mehr gebraucht wird.</li>
<li>Die Erkennung arbeitet statistisch. Prüfen Sie jede Datei in der Vorschau,
bevor Sie sie aus der Hand geben.</li>
<li>PDFblack verschlüsselt keine Dateien. Wer Zugriff auf den Rechner oder den
Speicherort hat, kann die gespeicherten PDFs lesen.</li>
</ul>

<p><i>Diese Hinweise beschreiben die technische Funktionsweise des Programms und
sind keine Rechtsberatung.</i></p>
"""


class DetectionWorker(QThread):
    """Fuehrt die Erkennung im Hintergrund aus, damit das Fenster bedienbar bleibt."""

    progressed = Signal(int, int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str, password: str | None, options: DetectionOptions) -> None:
        super().__init__()
        self._path = path
        self._password = password
        self._options = options
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _progress(self, index: int, total: int, message: str) -> bool:
        if self._cancelled:
            return False
        self.progressed.emit(index, total, message)
        return True

    def run(self) -> None:
        try:
            result = run_detection(
                self._path, self._options, self._password, self._progress
            )
        except Exception as exc:  # noqa: BLE001 - Fehler geht an die Oberflaeche
            if not self._cancelled:
                self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        if not self._cancelled:
            self.succeeded.emit(result)


class UpdateCheckWorker(QThread):
    """Fragt im Hintergrund die neueste Veroeffentlichung ab."""

    done = Signal(object)

    def __init__(self, timeout: float = 8.0) -> None:
        super().__init__()
        self._timeout = timeout

    def run(self) -> None:
        self.done.emit(fetch_latest(self._timeout))


class UpdateDownloadWorker(QThread):
    """Laedt die Update-Datei und meldet den Fortschritt."""

    progressed = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, target: Path) -> None:
        super().__init__()
        self._url = url
        self._target = target

    def run(self) -> None:
        try:
            path = download(self._url, self._target, progress=self.progressed.emit)
        except Exception as exc:  # noqa: BLE001 - Fehler geht an die Oberflaeche
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(str(path))


class _LogoButton(QLabel):
    """Anklickbares Logo im Kopfbereich."""

    clicked = Signal()

    def __init__(self, size: int = 34, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _BrandBlock(QWidget):
    """Logo, Titel und Untertitel eines Programms."""

    TITLE_COLOR = (230, 232, 236)
    SUBTITLE_COLOR = (139, 149, 165)

    def __init__(
        self,
        pixmap,
        title_text: str,
        subtitle_text: str,
        object_name: str = "",
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        if object_name:
            self.setObjectName(object_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(AppHeader.GAP)

        self.logo = _LogoButton(AppHeader.LOGO_SIZE, self)
        self.logo.setPixmap(pixmap)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(title_text)
        self.title.setObjectName("AppTitle")
        self.subtitle = QLabel(subtitle_text)
        self.subtitle.setObjectName("AppSubtitle")
        # Der (ausgeblendete) Text darf keine Klicks schlucken: sonst liegt er
        # ueber dem Logo eines anderen Programms, sobald sich die Bloecke
        # verschieben.
        for label in (self.title, self.subtitle):
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)

        layout.addWidget(self.logo, 0, Qt.AlignVCenter)
        layout.addLayout(titles)

        self._text_alpha = 1.0
        self._apply_text_alpha(1.0)
        self.adjustSize()

    # Der Text wird ueber die Farbe ein- und ausgeblendet, nicht ueber einen
    # QGraphicsOpacityEffect: dessen zwischengespeichertes Bild bleibt beim
    # Verschieben des Blocks stehen, wodurch Text und Logo auseinanderlaufen.
    def _apply_text_alpha(self, alpha: float) -> None:
        value = int(round(max(0.0, min(1.0, alpha)) * 255))
        red, green, blue = self.TITLE_COLOR
        self.title.setStyleSheet(
            f"color: rgba({red}, {green}, {blue}, {value}); "
            "font-size: 16px; font-weight: 700;"
        )
        red, green, blue = self.SUBTITLE_COLOR
        self.subtitle.setStyleSheet(
            f"color: rgba({red}, {green}, {blue}, {value}); font-size: 11px;"
        )

    @property
    def text_opacity(self) -> float:
        return self._text_alpha

    def set_text_opacity(self, value: float) -> None:
        # Jede Aenderung uebernehmen: mit einer Toleranz bliebe der Text nach
        # einer unterbrochenen Blende auf einem Restwert stehen.
        value = max(0.0, min(1.0, value))
        if value == self._text_alpha:
            return
        self._text_alpha = value
        self._apply_text_alpha(value)


class AppHeader(QWidget):
    """Kopfzeile mit drei Programmen.

    Die Reihenfolge ist immer dieselbe: PDFblack, PDFcompare, PDFocr - wie
    Blaettern, nie tauschen die Knoepfe die Seiten. PDFblack steht links,
    PDFcompare ab der Fenstermitte, PDFocr unmittelbar hinter dem blauen Logo.
    Bei PDFcompare faehrt nur der blaue Knopf nach links neben den roten; bei
    PDFocr fahren blau (neben rot) und gruen (neben blau) nach links. Der
    gruene Knopf ruehrt sich nicht, wenn nur PDFcompare gewaehlt wird.

    Sichtbar ist immer nur der Text des aktiven Programms.
    """

    programSelected = Signal(str)

    MARGIN = 16
    LOGO_SIZE = 34
    GAP = 11
    SLIDE_MS = 320
    TEXT_MS = 220
    # Nachlauf, in dem der Endzustand der Textblendung gesetzt wird.
    SETTLE_MS = 60

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Header")
        self.setFixedHeight(62)
        self._program = "pdfblack"

        self.black = _BrandBlock(logo_pixmap(self.LOGO_SIZE), APP_NAME, APP_TAGLINE)
        self.black.setParent(self)
        self.compare = _BrandBlock(
            compare_logo_pixmap(self.LOGO_SIZE),
            COMPARE_NAME,
            COMPARE_TAGLINE,
            object_name="BrandOverlay",
        )
        self.compare.setParent(self)
        self.ocr = _BrandBlock(
            ocr_logo_pixmap(self.LOGO_SIZE),
            OCR_NAME,
            OCR_TAGLINE,
            object_name="BrandOverlay",
        )
        self.ocr.setParent(self)

        self.version = QLabel(f"v{APP_VERSION}")
        self.version.setObjectName("VersionChip")
        self.version.setParent(self)

        self._blocks: dict[str, _BrandBlock] = {
            "pdfblack": self.black,
            "pdfcompare": self.compare,
            "pdfocr": self.ocr,
        }

        # Eine Animation je Block - wiederverwendet, damit kein Objekt waehrend
        # eines laufenden Wechsels geloescht wird.
        # Zaehler des Gleitens: ein Nachzuegler aus einer frueheren Runde darf
        # keine spaetere Bewegung mehr ueberschreiben.
        self._place_serial = 0
        self._slides: dict[str, QPropertyAnimation] = {}
        for name, block in self._blocks.items():
            if name == "pdfblack":
                continue
            animation = QPropertyAnimation(block, b"pos", self)
            animation.setDuration(self.SLIDE_MS)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            self._slides[name] = animation

        # Beim Start steht PDFblack links und allein mit Text.
        self._targets: dict[str, float] = {
            "pdfblack": 1.0,
            "pdfcompare": 0.0,
            "pdfocr": 0.0,
        }
        # Zaehler der Textblendung: ein Nachzuegler aus einer frueheren Runde
        # darf einen spaeter gestarteten Fade nicht mehr ueberschreiben.
        self._text_serial = 0
        self._fade_run: dict[str, int] = {}
        self._fades: dict[str, QVariantAnimation] = {}
        for name, block in self._blocks.items():
            block.set_text_opacity(self._targets[name])
            animation = QVariantAnimation(self)
            animation.setDuration(self.TEXT_MS)
            animation.setEasingCurve(QEasingCurve.InOutQuad)
            animation.valueChanged.connect(
                lambda value, target=block: target.set_text_opacity(float(value))
            )
            animation.finished.connect(lambda key=name: self._snap_text(key))
            self._fades[name] = animation

        for name, block in self._blocks.items():
            block.logo.setToolTip(f"{block.title.text()} anzeigen")
            block.logo.clicked.connect(
                lambda key=name: self.programSelected.emit(key)
            )

    # -- Positionen ---------------------------------------------------

    def title_x(self) -> int:
        """x-Position, an der Titel und Untertitel des ersten Programms beginnen."""
        return self.MARGIN + self.LOGO_SIZE + self.GAP

    def compare_rest_x(self) -> int:
        """Ruheposition des zweiten Programms: ab der Haelfte des Fensters.

        Reicht der Platz bis zur Versionsnummer nicht, rueckt der Block so
        weit nach links, dass er sie nicht ueberdeckt.
        """
        half = self.width() // 2
        left_limit = self.MARGIN + self.black.sizeHint().width() + 24
        right_limit = (
            self.width()
            - self.MARGIN
            - self.version.sizeHint().width()
            - 12
            - self.compare.sizeHint().width()
        )
        return max(left_limit, min(half, right_limit))

    def _bis_zur_version(self, x: int) -> int:
        """x so begrenzen, dass das Logo die Versionsnummer nicht ueberdeckt."""
        limit = (
            self.width()
            - self.MARGIN
            - self.version.sizeHint().width()
            - 12
            - self.LOGO_SIZE
        )
        return max(self.title_x(), min(x, limit))

    def ocr_rest_x(self) -> int:
        """Ruheposition von PDFocr: direkt hinter dem Logo von PDFcompare.

        Das ist genau die Stelle, an der der Text des blauen Buttons anfaengt -
        in dieser Stellung ist er ausgeblendet, das gruene Logo steht also frei.
        """
        return self._bis_zur_version(
            self.compare_rest_x() + self.LOGO_SIZE + self.GAP
        )

    def block_x(self, name: str, program: str) -> int:
        """x-Position des Logos eines Blocks fuer das gewaehlte Programm.

        Die Reihenfolge bleibt immer rot, blau, gruen - geblaettert wird nur
        nach links: blau faehrt bei PDFcompare und PDFocr neben rot, gruen
        faehrt nur beim eigenen Programm neben blau. Sonst steht jeder Block
        an seinem Platz.
        """
        if name == "pdfblack":
            return self.MARGIN
        if name == "pdfcompare":
            if program in ("pdfcompare", "pdfocr"):
                return self.title_x()
            return self.compare_rest_x()
        if program == "pdfocr":
            # Rechts neben dem blauen Button, der neben rot steht.
            return self.title_x() + self.LOGO_SIZE + self.GAP
        return self.ocr_rest_x()

    def _place(self, animate: bool, program: str | None = None) -> None:
        if not hasattr(self, "_slides"):
            return
        program = program or self._program
        height = self.height()
        self._place_serial += 1
        serial = self._place_serial
        ziele: dict[str, QPoint] = {}
        gleitet = False
        for name, block in self._blocks.items():
            block.adjustSize()
            end = QPoint(
                self.block_x(name, program),
                max(0, (height - block.height()) // 2),
            )
            ziele[name] = end
            if name == "pdfblack":
                block.move(end)
                continue
            animation = self._slides[name]
            animation.stop()
            if not animate or block.pos() == end:
                block.move(end)
                continue
            animation.setStartValue(block.pos())
            animation.setEndValue(end)
            animation.start()
            gleitet = True
        if gleitet:
            # Wie bei der Textblendung: meldet ein abgebrochenes Gleiten sein
            # Ende nicht, bleiben die Knoepfe sonst zwischen den Plaetzen stehen.
            QTimer.singleShot(
                self.SLIDE_MS + self.SETTLE_MS,
                lambda: self._settle_slides(serial, ziele),
            )

        # Feste Stapelreihenfolge von links nach rechts: so liegt der Text
        # eines Blocks nie ueber dem Logo des naechsten. Damit bleibt jeder
        # Knopf in jeder Stellung anklickbar.
        for name in ("pdfblack", "pdfcompare", "pdfocr"):
            self._blocks[name].raise_()

    def set_program(self, program: str, animate: bool = True) -> None:
        self._program = program
        self._place(animate=animate, program=program)
        self._fade_text(program, animate=animate)

    def _fade_text(self, program: str, animate: bool = True) -> None:
        """Nur der Text des aktiven Programms ist zu sehen.

        Die anderen Programme behalten ihr Logo, ihr Titel und Untertitel
        blenden aber vollstaendig aus.
        """
        for name in self._targets:
            self._targets[name] = 1.0 if name == program else 0.0

        self._text_serial += 1
        serial = self._text_serial
        blendet = False
        for name, block in self._blocks.items():
            animation = self._fades[name]
            target = self._targets[name]
            animation.stop()
            self._fade_run[name] = serial
            if not animate or block.text_opacity == target:
                block.set_text_opacity(target)
                continue
            animation.setStartValue(float(block.text_opacity))
            animation.setEndValue(float(target))
            animation.start()
            blendet = True
        if blendet:
            # Sicherheitsnetz: meldet eine unterbrochene Blende ihr Ende nicht,
            # steht sonst der halb sichtbare Text eines inaktiven Programms
            # stehen. Nach dem Nachlauf gilt der Endzustand.
            QTimer.singleShot(
                self.TEXT_MS + self.SETTLE_MS,
                lambda: self._settle_text(serial),
            )

    def _settle_slides(self, serial: int, ziele: dict[str, QPoint]) -> None:
        """Endpositionen des Gleitens erzwingen - auch ohne Abschlussmeldung."""
        if serial != self._place_serial:
            return
        for name, ziel in ziele.items():
            block = self._blocks[name]
            if block.pos() == ziel:
                continue
            animation = self._slides.get(name)
            if animation is not None:
                animation.stop()
            block.move(ziel)

    def _snap_text(self, name: str) -> None:
        """Eine beendete Blende exakt auf ihr Ziel setzen.

        Gehoert sie zu einer frueheren Runde, bleibt sie wirkungslos.
        """
        if self._fade_run.get(name) != self._text_serial:
            return
        self._blocks[name].set_text_opacity(self._targets[name])

    def _settle_text(self, serial: int) -> None:
        """Endzustand der Textblendung erzwingen - auch ohne Abschlussmeldung."""
        if serial != self._text_serial:
            return
        for name, block in self._blocks.items():
            block.set_text_opacity(self._targets[name])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        size = self.version.sizeHint()
        self.version.resize(size)
        self.version.move(
            self.width() - self.MARGIN - size.width(),
            max(0, (self.height() - size.height()) // 2),
        )
        self._place(animate=False)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1380, 900)
        self.setMinimumSize(QSize(1040, 680))
        self.setAcceptDrops(True)

        self._path: str | None = None
        # Stapel aus der zweiten Ablageflaeche: eine Datei nach der anderen.
        self._queue: list[str] = []
        self._queue_total = 0
        self._queue_pos = 0
        self._queue_done = 0
        # Ergebnis der automatisch angestossenen Texterkennung gleich laden?
        self._auto_open_ocr = False
        # Datei aus PDFocr: sie hat ihre Textebene schon - nicht erneut auslesen.
        self._ocr_result_path: str | None = None
        self._rebuild_source: tuple[str, str | None] | None = None
        self._password: str | None = None
        self._findings: list[Finding] = []
        self._worker: DetectionWorker | None = None
        self._busy = False
        self._next_uid = 1
        self._last_dir = os.path.expanduser("~")
        self._update_check: UpdateCheckWorker | None = None
        self._update_download: UpdateDownloadWorker | None = None
        self._update_progress: QProgressDialog | None = None
        self._update_silent = False
        self._update_version = ""
        self._program = "pdfblack"
        self._fades: list[QPropertyAnimation] = []
        self._fade_serial = 0

        self._build_ui()
        self._build_menus()
        self._connect()
        self._refresh_state()
        self.statusBar().showMessage(
            "Bereit – PDF-Datei hierher ziehen oder „PDF öffnen“ wählen."
        )

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = AppHeader()
        self.header.programSelected.connect(self._show_program)
        root.addWidget(self.header)

        toolbar = QWidget()
        toolbar.setObjectName("Toolbar")
        toolbar.setFixedHeight(58)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(14, 9, 14, 9)
        bar.setSpacing(8)

        self.btn_open = QPushButton("PDF öffnen …")
        self.btn_queue = QPushButton("PDFs öffnen …")
        self.btn_queue.setToolTip(
            "Mehrere PDF-Dateien als Stapel öffnen – eine nach der anderen."
        )
        self.btn_preview = QPushButton("Vorschau erzeugen")
        self.btn_preview.setObjectName("Primary")
        self.btn_save = QPushButton("Geschwärzte Kopie speichern")
        self.btn_preview.setToolTip(
            "Sucht alle Daten und markiert sie farbig – die Datei wird noch nicht verändert."
        )
        self.btn_save.setToolTip(
            "Schwärzt alle aktiven Treffer und legt die Kopie in deinem "
            "Benutzerordner ab; sie wird beim Beenden entfernt."
        )
        for button in (
            self.btn_open,
            self.btn_queue,
            self.btn_preview,
            self.btn_save,
        ):
            button.setCursor(Qt.PointingHandCursor)

        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_queue)
        bar.addWidget(self.btn_preview)
        bar.addSpacing(2)
        bar.addWidget(self.btn_save)
        bar.addStretch(1)

        # Fortschritt des Stapels („Stapel 2 von 5“) und ein Knopf, um eine
        # Datei ohne Speichern zu ueberspringen.
        self.queue_label = QLabel("")
        self.queue_label.setObjectName("Hint")
        self.queue_label.hide()
        self.btn_queue_next = QToolButton()
        self.btn_queue_next.setText("Nächste Datei")
        self.btn_queue_next.setToolTip(
            "Ohne Speichern zur nächsten Datei des Stapels"
        )
        self.btn_queue_next.clicked.connect(lambda: self._open_next_in_queue())
        self.btn_queue_next.hide()
        bar.addWidget(self.queue_label)
        bar.addWidget(self.btn_queue_next)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("\u2212")
        self.btn_zoom_out.setToolTip("Verkleinern")
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setToolTip("Vergrößern")
        self.btn_zoom_fit = QToolButton()
        self.btn_zoom_fit.setText("Anpassen")
        self.btn_zoom_fit.setToolTip("Seitenbreite ins Fenster einpassen")
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setObjectName("Hint")
        self.zoom_label.setFixedWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)

        bar.addWidget(self.btn_zoom_out)
        bar.addWidget(self.zoom_label)
        bar.addWidget(self.btn_zoom_in)
        bar.addWidget(self.btn_zoom_fit)

        self.black_view = QWidget()
        black_layout = QVBoxLayout(self.black_view)
        black_layout.setContentsMargins(0, 0, 0, 0)
        black_layout.setSpacing(0)
        black_layout.addWidget(toolbar)

        self.controls = ControlsPanel()
        self.controls.setMinimumWidth(310)
        self.controls.setMaximumWidth(420)

        self.dropzone = DropZone()
        self.queue_zone = DropZone(mehrere=True)
        self.dropzones = QWidget()
        zone_layout = QHBoxLayout(self.dropzones)
        zone_layout.setContentsMargins(16, 16, 16, 16)
        zone_layout.setSpacing(14)
        zone_layout.addWidget(self.dropzone, 1)
        zone_layout.addWidget(self.queue_zone, 1)

        self.canvas = PdfCanvas()
        self.scroll = QScrollArea()
        self.scroll.setObjectName("PreviewScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidget(self.canvas)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.dropzones)
        self.stack.addWidget(self.scroll)

        # Hinweis beim Einlesen einer PDF mit vorhandener Textebene.
        self.rebuild_bar = QWidget()
        self.rebuild_bar.setObjectName("RebuildBar")
        rebuild_layout = QHBoxLayout(self.rebuild_bar)
        rebuild_layout.setContentsMargins(14, 8, 14, 8)
        rebuild_layout.setSpacing(10)
        self.rebuild_label = QLabel(
            "Diese PDF hat bereits eine Textebene. Soll sie verworfen und per "
            "OCR neu aufgebaut werden? Die Originaldatei bleibt unverändert."
        )
        self.rebuild_label.setObjectName("Hint")
        self.rebuild_label.setWordWrap(True)
        self.btn_rebuild = QPushButton("Textebene neu aufbauen")
        self.btn_rebuild.setObjectName("Ghost")
        self.btn_rebuild.setCursor(Qt.PointingHandCursor)
        self.btn_keep = QPushButton("Behalten")
        self.btn_keep.setObjectName("Ghost")
        self.btn_keep.setCursor(Qt.PointingHandCursor)
        rebuild_layout.addWidget(self.rebuild_label, 1)
        rebuild_layout.addWidget(self.btn_rebuild)
        rebuild_layout.addWidget(self.btn_keep)
        self.rebuild_bar.hide()
        black_layout.addWidget(self.rebuild_bar)

        self.findings_panel = FindingsPanel()
        self.findings_panel.setMinimumWidth(300)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.controls)
        splitter.addWidget(self.stack)
        splitter.addWidget(self.findings_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([344, 660, 380])
        black_layout.addWidget(splitter, 1)

        self.compare_view = self._build_compare_view()
        self.ocr_view = self._build_ocr_view()

        self.workspace = QStackedWidget()
        self.workspace.addWidget(self.black_view)
        self.workspace.addWidget(self.compare_view)
        self.workspace.addWidget(self.ocr_view)
        root.addWidget(self.workspace, 1)
        self.setCentralWidget(central)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(150)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.page_label = QLabel("")
        self.page_label.setObjectName("Hint")
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().addPermanentWidget(self.page_label)

    # ------------------------------------------------------------------
    # Programmwechsel
    # ------------------------------------------------------------------

    def _build_compare_view(self) -> QWidget:
        """PDFcompare: zuletzt geschwaerzte Dateien und zwei Stapel."""
        view = CompareView()
        view.settingsRequested.connect(self._open_preferences)
        view.message.connect(self._show_compare_message)
        return view

    def _build_ocr_view(self) -> QWidget:
        """PDFocr: Bildscan auslesen und Textlayer hinter das Bild legen."""
        view = OcrView()
        view.message.connect(lambda text: self.statusBar().showMessage(text, 12000))
        view.openInBlackRequested.connect(self.load_pdf)
        view.resultReady.connect(self._on_ocr_result)
        return view

    def _show_compare_message(self, text: str) -> None:
        """Meldung der Übergabe in der Statuszeile anzeigen."""
        self.statusBar().showMessage(text, 12000)

    def _show_program(self, program: str) -> None:
        """Zwischen PDFblack, PDFcompare und PDFocr umschalten."""
        if program == "pdfocr":
            # Wer PDFocr von Hand öffnet, will das Ergebnis selbst übernehmen.
            self._auto_open_ocr = False
        if program == self._program:
            return
        self._program = program
        self.header.set_program(program)
        if program == "pdfcompare":
            self.compare_view.refresh()
        pages = {
            "pdfblack": self.black_view,
            "pdfcompare": self.compare_view,
            "pdfocr": self.ocr_view,
        }
        self._fade_to(pages[program])

    def _stop_fade(self) -> None:
        """Laufendes Ein-/Ausblenden abbrechen und volle Deckkraft herstellen.

        Ohne das Zuruecksetzen bliebe die halb ausgeblendete Maske stehen, wenn
        waehrend der Animation ein neues Ziel gewaehlt wird. Die laufende
        Nummer entwertet ausserdem alle noch haengenden Rueckrufe der alten
        Animation, damit sie nicht spaeter eine falsche Maske einschalten.
        """
        self._fade_serial += 1
        for animation in self._fades:
            animation.stop()
        self._fades.clear()
        if isinstance(self.workspace.graphicsEffect(), QGraphicsOpacityEffect):
            self.workspace.setGraphicsEffect(None)

    def _fade_to(self, page: QWidget) -> None:
        """Alte Maske ausblenden, neue einblenden."""
        self._stop_fade()
        if self.workspace.currentWidget() is page:
            return

        effect = QGraphicsOpacityEffect(self.workspace)
        effect.setOpacity(1.0)
        self.workspace.setGraphicsEffect(effect)

        serial = self._fade_serial

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(150)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        fade_in = QPropertyAnimation(effect, b"opacity", self)
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        def swap() -> None:
            if serial != self._fade_serial:
                return
            self.workspace.setCurrentWidget(page)
            fade_in.start()

        def finish() -> None:
            if serial != self._fade_serial:
                return
            self.workspace.setGraphicsEffect(None)
            self._fades.clear()

        fade_out.finished.connect(swap)
        fade_in.finished.connect(finish)
        self._fades = [fade_out, fade_in]
        fade_out.start()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&Datei")

        open_action = QAction("PDF öffnen …", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._choose_file)
        file_menu.addAction(open_action)

        save_action = QAction("Geschwärzte Kopie speichern", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_as)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        lern_action = QAction("Lerndatei herunterladen …", self)
        lern_action.setToolTip(
            "Alle Kategorie-Korrekturen als Lerndatei für die Weiterentwicklung sichern"
        )
        lern_action.triggered.connect(self._download_lerndatei)
        file_menu.addAction(lern_action)

        ansehen_action = QAction("Lerndatei ansehen …", self)
        ansehen_action.setToolTip(
            "Gelernte Beispiele prüfen und einzelne Regeln löschen"
        )
        ansehen_action.triggered.connect(self._show_lerndatei)
        file_menu.addAction(ansehen_action)

        reset_action = QAction("Lerndatei zurücksetzen …", self)
        reset_action.setToolTip("Gelernte Beispiele verwerfen und wieder nach den Programmwerten einordnen")
        reset_action.triggered.connect(self._reset_lerndatei)
        file_menu.addAction(reset_action)

        file_menu.addSeparator()
        settings_action = QAction("Einstellungen …", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_preferences)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()
        quit_action = QAction("Beenden", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&Ansicht")
        zoom_in = QAction("Vergrößern", self)
        zoom_in.setShortcut(QKeySequence.ZoomIn)
        zoom_in.triggered.connect(lambda: self._set_zoom(self.canvas.zoom * 1.15))
        view_menu.addAction(zoom_in)
        zoom_out = QAction("Verkleinern", self)
        zoom_out.setShortcut(QKeySequence.ZoomOut)
        zoom_out.triggered.connect(lambda: self._set_zoom(self.canvas.zoom / 1.15))
        view_menu.addAction(zoom_out)
        fit = QAction("An Fensterbreite anpassen", self)
        fit.setShortcut(QKeySequence("Ctrl+0"))
        fit.triggered.connect(self._fit_width)
        view_menu.addAction(fit)

        help_menu = self.menuBar().addMenu("&Hilfe")
        guide = QAction("Anleitung", self)
        guide.setShortcut(QKeySequence.HelpContents)
        guide.triggered.connect(self._show_guide)
        help_menu.addAction(guide)

        self.update_action = QAction("Nach Updates suchen …", self)
        self.update_action.triggered.connect(lambda: self._check_updates(silent=False))
        help_menu.addAction(self.update_action)
        help_menu.addSeparator()

        privacy = QAction("Datenschutz", self)
        privacy.triggered.connect(self._show_privacy)
        help_menu.addAction(privacy)

        about = QAction(f"Über {APP_NAME}", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _connect(self) -> None:
        self.btn_open.clicked.connect(self._choose_file)
        self.btn_preview.clicked.connect(self._run_detection)
        self.btn_save.clicked.connect(self._save_as)
        self.btn_zoom_in.clicked.connect(lambda: self._set_zoom(self.canvas.zoom * 1.15))
        self.btn_zoom_out.clicked.connect(lambda: self._set_zoom(self.canvas.zoom / 1.15))
        self.btn_zoom_fit.clicked.connect(self._fit_width)
        self.btn_rebuild.clicked.connect(self._rebuild_textlayer)
        self.btn_keep.clicked.connect(self.rebuild_bar.hide)

        self.dropzone.browseRequested.connect(self._choose_file)
        self.dropzone.fileDropped.connect(self.load_pdf)
        self.btn_queue.clicked.connect(self._choose_queue)
        self.queue_zone.filesDropped.connect(self.start_queue)

        self.canvas.regionDrawn.connect(self._add_manual_region)
        self.canvas.wordActivated.connect(self._add_word_region)
        self.canvas.findingActivated.connect(self._toggle_finding)
        self.canvas.zoomRequested.connect(self._set_zoom)
        self.canvas.ensureRequested.connect(self._ensure_visible)

        self.findings_panel.enabledChanged.connect(self._set_finding_enabled)
        self.findings_panel.findingSelected.connect(self._select_finding)
        self.findings_panel.selectAllRequested.connect(self._set_all_enabled)
        self.findings_panel.removeRequested.connect(self._remove_selected)
        self.findings_panel.categoryChanged.connect(self._set_finding_category)
        self.findings_panel.falsePositiveRequested.connect(self._mark_false_positive)
        self.findings_panel.hintAcknowledged.connect(self._quittiere_hinweis)
        self.findings_panel.correctionRequested.connect(self._korrigiere_wert)
        self.canvas.findingMenuRequested.connect(self._zeige_treffer_menue)

        self.scroll.verticalScrollBar().valueChanged.connect(self._update_page_label)

    # ------------------------------------------------------------------
    # Datei laden
    # ------------------------------------------------------------------

    def open_path(self, path: str) -> None:
        self.load_pdf(path)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "PDF öffnen", self._last_dir, "PDF-Dateien (*.pdf)"
        )
        if path:
            self.load_pdf(path)

    def _choose_queue(self) -> None:
        """Mehrere PDFs fuer den Stapel auswaehlen."""
        pfade, _ = QFileDialog.getOpenFileNames(
            self, "PDFs öffnen", self._last_dir, "PDF-Dateien (*.pdf)"
        )
        if pfade:
            self.start_queue(pfade)

    def start_queue(self, pfade: list[str]) -> None:
        """Einen Stapel beginnen - oder weitere Dateien anhaengen.

        Laeuft schon ein Stapel, kommen die neuen Dateien hinten dazu; die
        bereits wartenden bleiben erhalten.
        """
        if self._busy:
            return
        dateien: list[str] = []
        for pfad in pfade:
            if pfad.lower().endswith(".pdf") and pfad not in dateien:
                dateien.append(pfad)
        if not dateien:
            return
        if self._queue_total:
            bekannt = {self._path, *self._queue}
            weitere = [pfad for pfad in dateien if pfad not in bekannt]
            if not weitere:
                return
            self._queue.extend(weitere)
            self._queue_total += len(weitere)
            self._refresh_queue_label()
            self.statusBar().showMessage(
                f"{len(weitere)} Datei(en) zum Stapel hinzugefügt.", 8000
            )
            return
        self._queue = dateien
        self._queue_total = len(dateien)
        self._queue_pos = 0
        self._queue_done = 0
        self._open_next_in_queue()

    def _open_next_in_queue(self) -> None:
        """Naechste vorgemerkte Datei oeffnen; am Ende den Stapel abschliessen."""
        if self._busy:
            return
        while self._queue:
            pfad = self._queue.pop(0)
            if self.load_pdf(pfad):
                # Fortschritt zaehlt geoeffnete Dateien, nicht nur gespeicherte:
                # eine uebersprungene Datei soll die Nummer weiterruecken.
                self._queue_pos += 1
                self._refresh_queue_label()
                return
            self.statusBar().showMessage(
                f"„{os.path.basename(pfad)}“ konnte nicht geöffnet werden – "
                "übersprungen.",
                12000,
            )
        self._finish_queue()

    def _finish_queue(self) -> None:
        """Alle Dateien des Stapels sind durch."""
        gespeichert = self._queue_done
        gesamt = self._queue_total
        self._queue = []
        self._queue_total = 0
        self._queue_pos = 0
        self._queue_done = 0
        self._refresh_queue_label()
        if gespeichert:
            self.statusBar().showMessage(
                f"Stapel abgearbeitet: {gespeichert} von {gesamt} Datei(en) "
                "geschwärzt.",
                15000,
            )
        else:
            self.statusBar().showMessage(
                "Stapel beendet – keine Datei geöffnet.", 12000
            )

    def _refresh_queue_label(self) -> None:
        """Fortschritt und offene Dateien in der Werkzeugleiste anzeigen."""
        if not self._queue_total:
            self.queue_label.hide()
            self.btn_queue_next.hide()
            return
        aktuell = min(self._queue_pos, self._queue_total)
        self.queue_label.setText(f"Stapel {aktuell} von {self._queue_total}")
        rest = [os.path.basename(pfad) for pfad in self._queue]
        self.queue_label.setToolTip(
            ("Noch offen:\n" + "\n".join(rest)) if rest else "Letzte Datei im Stapel"
        )
        self.queue_label.show()
        self.btn_queue_next.setVisible(bool(rest))
        self.btn_queue_next.setEnabled(not self._busy)

    def load_pdf(self, path: str) -> bool:
        """Eine PDF oeffnen; ``False``, wenn sie nicht geoeffnet werden konnte."""
        if self._busy:
            return False
        # Ein manuell geoeffnetes Dokument beendet die OCR-Automatik.
        self._auto_open_ocr = False
        if self._program != "pdfblack":
            self._show_program("pdfblack")
        password: str | None = None
        try:
            doc = open_document(path)
        except PdfPasswordError:
            entered, ok = QInputDialog.getText(
                self,
                "Passwortgeschützt",
                f"Passwort für „{os.path.basename(path)}“:",
                QLineEdit.Password,
            )
            if not ok or not entered:
                return False
            try:
                doc = open_document(path, entered)
            except Exception as exc:  # noqa: BLE001
                self._show_error(exc)
                return False
            password = entered
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return False

        page_count = doc.page_count
        doc.close()

        try:
            self.canvas.load(path, password)
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return False

        self._path = path
        self._password = password
        self._last_dir = os.path.dirname(path) or self._last_dir
        self._findings = []
        self._next_uid = 1
        self.findings_panel.set_findings([])
        self.canvas.set_findings([])
        self.stack.setCurrentIndex(1)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} – {os.path.basename(path)}")
        self.statusBar().showMessage(
            f"{os.path.basename(path)} geladen · {page_count} Seite(n)."
        )
        self._fit_width()
        QTimer.singleShot(0, self._fit_width)
        self._update_page_label()
        self._refresh_state()

        # Ein Bildscan hat keinen Text zum Schwaerzen. Dann uebernimmt PDFocr:
        # Text auslesen und unsichtbar hinter das Bild legen, damit die Datei
        # anschliessend geschwaerzt werden kann.
        try:
            ohne_text = (
                not ocr_core.has_text(path, password)
                and path != self._ocr_result_path
            )
        except Exception:  # noqa: BLE001 - besser in PDFblack bleiben als abbrechen
            ohne_text = False
        if ohne_text:
            self._rebuild_source = None
            self.rebuild_bar.hide()
            self.ocr_view.open_path(path, password, start=True)
            self._show_program("pdfocr")
            # Sobald die Erkennung fertig ist, landet das Ergebnis von selbst
            # in PDFblack (wie der Knopf „In PDFblack öffnen“).
            self._auto_open_ocr = True
            self.statusBar().showMessage(
                "Kein Text zum Schwärzen – PDFocr liest den Scan aus.", 12000
            )
        else:
            self._offer_rebuild(path, password)
            # Ohne Klick: die Prüfung laeuft direkt nach dem Oeffnen an.
            self._auto_detect()
        return True

    def _on_ocr_result(self, path: str) -> None:
        """Fertige Texterkennung: Ergebnis gleich in PDFblack laden.

        Nur wenn die Erkennung von PDFblack selbst angestoßen wurde - wer in
        PDFocr von Hand arbeitet, entscheidet weiter selbst.
        """
        if not self._auto_open_ocr:
            return
        self._auto_open_ocr = False
        if not path or not os.path.isfile(path):
            return
        self._ocr_result_path = path
        self.statusBar().showMessage("Texterkennung fertig – PDFblack prüft den Scan.")
        self.load_pdf(path)

    def _offer_rebuild(self, path: str, password: str | None) -> None:
        """PDF mit Textebene: Neuaufbau per OCR anbieten."""
        self._rebuild_source = None
        self.rebuild_bar.hide()
        if os.environ.get("PDFBLACK_NO_OCR_CHECK"):
            return
        try:
            if not self.ocr_view.engine().available():
                return
        except Exception:  # noqa: BLE001 - ohne Erkennung kein Angebot
            return
        self._rebuild_source = (path, password)
        self.rebuild_bar.show()

    def _rebuild_textlayer(self) -> None:
        """Textebene verwerfen und per OCR neu aufsetzen.

        Die Originaldatei wird nur gelesen; PDFocr arbeitet auf einer
        temporaeren Bilddatei und legt das Ergebnis neu ab.
        """
        if not self._rebuild_source:
            return
        path, password = self._rebuild_source
        self._rebuild_source = None
        self.rebuild_bar.hide()
        self.ocr_view.open_path(path, password, ersetze_textebene=True)
        self._show_program("pdfocr")
        self.ocr_view.start()

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.critical(
            self, "Datei konnte nicht geöffnet werden", f"{exc}"
        )

    # ------------------------------------------------------------------
    # Drag and Drop auf dem Fenster
    # ------------------------------------------------------------------

    @staticmethod
    def _pdfs_from_event(event) -> list[str]:
        """Alle abgelegten PDF-Dateien in der Reihenfolge des Ablegens."""
        if not event.mimeData().hasUrls():
            return []
        pfade: list[str] = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf") and path not in pfade:
                pfade.append(path)
        return pfade

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._pdfs_from_event(event) and not self._busy:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        pfade = self._pdfs_from_event(event)
        if not pfade:
            return
        event.acceptProposedAction()
        if len(pfade) > 1:
            self.start_queue(pfade)
        else:
            self.load_pdf(pfade[0])

    # ------------------------------------------------------------------
    # Erkennung
    # ------------------------------------------------------------------

    def _auto_detect(self) -> None:
        """Nach dem Oeffnen ohne Klick pruefen.

        Dieselbe Erkennung wie ueber den Knopf, nur ohne Rueckfragen: ist
        nichts eingeschaltet oder ein Regex fehlerhaft, bleibt es bei einer
        Meldung in der Statuszeile.
        """
        if not self._path or self._busy:
            return
        if os.environ.get("PDFBLACK_NO_AUTO_DETECT") == "1":
            # Fuer Tests und Sonderfaelle: nur der Knopf loest die Pruefung aus.
            return
        try:
            options = self.controls.read_options()
        except ValueError:
            self.statusBar().showMessage(
                "Automatische Erkennung uebersprungen: der Regex-Ausdruck ist "
                "fehlerhaft."
            )
            return
        if options.is_empty():
            self.statusBar().showMessage(
                "Datei geladen. Es ist keine Erkennung eingeschaltet - bitte "
                "oben auswaehlen."
            )
            return
        self._run_detection()

    def _run_detection(self) -> None:
        if not self._path or self._busy:
            return
        try:
            options = self.controls.read_options()
        except ValueError as exc:
            QMessageBox.warning(self, "Regex-Ausdruck fehlerhaft", str(exc))
            self.controls.focus_regex()
            return
        if options.is_empty():
            QMessageBox.information(
                self,
                "Keine Erkennung ausgewählt",
                "Bitte mindestens eine Erkennungsquelle aktivieren oder links Werte eingeben.",
            )
            return

        self.controls.set_ai_hint("")
        self._set_busy(True, "Erkennung läuft …")
        self._worker = DetectionWorker(self._path, self._password, options)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_detection_done)
        self._worker.failed.connect(self._on_detection_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_progress(self, index: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(index)
        self.statusBar().showMessage(message)

    def _on_detection_done(self, result) -> None:
        self._findings = list(result.findings)
        self._next_uid = max((f.uid for f in self._findings), default=0) + 1
        self._sync_findings()
        self._set_busy(False)
        if result.warnings:
            QMessageBox.warning(self, "Hinweis zur Erkennung", "\n\n".join(result.warnings))
        if not self._findings:
            self.statusBar().showMessage(
                "Keine Treffer gefunden – Werte links ergänzen und erneut suchen."
            )
        else:
            active = sum(1 for f in self._findings if f.enabled)
            meldung = (
                f"{len(self._findings)} Treffer markiert ({active} aktiv). "
                "Prüfen, dann „Geschwärzte Kopie speichern“."
            )
            gelernt = self._lerndatei_hinweis(
                result.learned_off, result.learned_changed
            )
            if gelernt:
                meldung = f"{meldung} Lerndatei: {gelernt}."
            self.statusBar().showMessage(meldung)

    def _on_detection_failed(self, message: str) -> None:
        self._set_busy(False)
        self.statusBar().showMessage("Erkennung fehlgeschlagen.")
        QMessageBox.critical(self, "Erkennung fehlgeschlagen", message)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._refresh_state()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
            if message:
                self.statusBar().showMessage(message)
        self._refresh_state()

    # ------------------------------------------------------------------
    # Treffer verwalten
    # ------------------------------------------------------------------

    def _sync_findings(self) -> None:
        self._findings.sort(
            key=lambda f: (
                f.page,
                f.rects[0][1] if f.rects else 0.0,
                f.rects[0][0] if f.rects else 0.0,
            )
        )
        self.canvas.set_findings(self._findings)
        self.findings_panel.set_findings(self._findings)
        self._refresh_state()

    def _toggle_finding(self, uid: int) -> None:
        for finding in self._findings:
            if finding.uid == uid:
                finding.enabled = not finding.enabled
                self.canvas.set_selected(uid)
                self.findings_panel.set_enabled_state(uid, finding.enabled)
                self.findings_panel.update_counts(self._findings)
                self.canvas.update()
                self._refresh_state()
                return

    def _set_finding_enabled(self, uid: int, enabled: bool) -> None:
        for finding in self._findings:
            if finding.uid == uid:
                finding.enabled = enabled
                break
        self.findings_panel.set_enabled_state(uid, enabled)
        self.findings_panel.update_counts(self._findings)
        self.canvas.update()
        self._refresh_state()

    # --- Lerndatei ----------------------------------------------------

    def _finding(self, uid: int) -> Finding | None:
        for finding in self._findings:
            if finding.uid == uid:
                return finding
        return None

    def _gleichnamige(self, finding: Finding) -> list[Finding]:
        """Alle Treffer mit demselben Text - wie in der Liste angezeigt."""
        text = finding.display_text
        return [item for item in self._findings if item.display_text == text]

    def _set_finding_category(
        self, uid: int, category: Category, alle: bool = False
    ) -> None:
        """Kategorie eines Treffers - auf Wunsch aller gleichen - korrigieren."""
        ziel = self._finding(uid)
        if ziel is None:
            return
        betroffen = self._gleichnamige(ziel) if alle else [ziel]
        if all(finding.category is category for finding in betroffen):
            return
        vorher = ziel.category
        for finding in betroffen:
            finding.category = category
            if "vom Benutzer" not in finding.source:
                finding.source = f"{finding.source} · vom Benutzer korrigiert"
        self._lerne(ziel, vorher, category, len(betroffen))
        self._sync_findings()
        if len(betroffen) > 1:
            meldung = (
                f"{len(betroffen)} gleiche Treffer als {category.value} eingeordnet "
                "und als Lernbeispiel gespeichert."
            )
        else:
            meldung = (
                f"„{ziel.display_text}“ als {category.value} eingeordnet und als "
                "Lernbeispiel gespeichert."
            )
        self.statusBar().showMessage(meldung)

    def _mark_false_positive(self, uid: int, alle: bool = False) -> None:
        """Treffer als Fehlalarm abhaken - auf Wunsch alle gleichen."""
        ziel = self._finding(uid)
        if ziel is None:
            return
        betroffen = self._gleichnamige(ziel) if alle else [ziel]
        vorher = ziel.category
        for finding in betroffen:
            finding.enabled = False
            if "vom Benutzer" not in finding.source:
                finding.source = f"{finding.source} · vom Benutzer als Fehlalarm verworfen"
        self._lerne(ziel, vorher, None, len(betroffen))
        self._sync_findings()
        if len(betroffen) > 1:
            meldung = (
                f"{len(betroffen)} gleiche Treffer als Fehlalarm abgehakt und als "
                "Lernbeispiel gespeichert."
            )
        else:
            meldung = (
                f"„{ziel.display_text}“ als Fehlalarm abgehakt und als Lernbeispiel "
                "gespeichert."
            )
        self.statusBar().showMessage(meldung)

    def _zeige_treffer_menue(self, uid: int, position) -> None:
        """Rechte Maustaste im PDF: alle Aktionen zu dieser Fundstelle.

        Das Menue baut derselbe Baustein wie in der Trefferliste
        (``treffer_menue``), damit beide nicht auseinanderlaufen.
        """
        ziel = self._finding(uid)
        if ziel is None:
            return
        menu = treffer_menue(self, ziel, len(self._gleichnamige(ziel)))
        gewaehlt = menu.exec(position)
        if gewaehlt is None:
            return
        aktion = str(gewaehlt.data() or "")
        if aktion == AKTION_UMSCHALTEN:
            self._toggle_finding(uid)
        elif aktion == AKTION_ALLE_UMSCHALTEN:
            self._toggle_gleichnamige(uid)
        elif aktion == AKTION_FEHLALARM:
            self._mark_false_positive(uid)
        elif aktion == AKTION_ALLE_FEHLALARM:
            self._mark_false_positive(uid, True)
        elif aktion == AKTION_HINWEIS_OK:
            self._quittiere_hinweis(uid)
        elif aktion == AKTION_KORRIGIEREN:
            self._korrigiere_wert(uid)
        elif aktion.startswith(f"{AKTION_KATEGORIE}:"):
            self._waehle_kategorie(uid, aktion, False)
        elif aktion.startswith(f"{AKTION_ALLE_KATEGORIE}:"):
            self._waehle_kategorie(uid, aktion, True)

    def _waehle_kategorie(self, uid: int, aktion: str, alle: bool) -> None:
        """Kategorie aus dem Menuedaten-Wert ``kategorie:<X>`` setzen."""
        name = aktion.split(":", 1)[1]
        for category in WAHL_KATEGORIEN:
            if category.value == name:
                self._set_finding_category(uid, category, alle)
                return

    def _toggle_gleichnamige(self, uid: int) -> None:
        """Alle Treffer mit demselben Text an- oder abschalten."""
        ziel = self._finding(uid)
        if ziel is None:
            return
        neu = not ziel.enabled
        betroffen = self._gleichnamige(ziel)
        for finding in betroffen:
            finding.enabled = neu
        self._sync_findings()
        self.statusBar().showMessage(
            f"{len(betroffen)} Treffer \u201e{ziel.display_text}\u201c "
            f"{'geschw\u00e4rzt' if neu else 'nicht geschw\u00e4rzt'}."
        )

    def _quittiere_hinweis(self, uid: int) -> None:
        """Hinweis der Plausibilitaetspruefung bestaetigen - Treffer bleibt aktiv."""
        ziel = self._finding(uid)
        if ziel is None:
            return
        ziel.hinweis = ""
        ziel.enabled = True
        if "Hinweis geprüft" not in ziel.source:
            ziel.source = f"{ziel.source} · Hinweis geprüft"
        self._sync_findings()
        self.statusBar().showMessage(
            f"„{ziel.display_text}“ wird trotz Hinweis geschwärzt."
        )

    def _korrigiere_wert(self, uid: int) -> None:
        """Falsch gelesenen Wert richtigstellen.

        Geschwaerzt wird weiterhin die gefundene Stelle im PDF; der korrigierte
        Wert erscheint in der Liste und in der Lerndatei. Bleibt auch der neue
        Wert unplausibel, wird das gemeldet und nichts uebernommen.
        """
        ziel = self._finding(uid)
        if ziel is None:
            return
        vorher = ziel.display_text
        neu, bestaetigt = QInputDialog.getText(
            self,
            "Wert korrigieren",
            f"Gefunden: {vorher}\n\nRichtiger Wert (geschwärzt wird weiterhin "
            "die gefundene Stelle):",
            text=vorher,
        )
        if not bestaetigt:
            return
        neu = " ".join(neu.split())
        if not neu or neu == vorher:
            return
        rest = plausibel.hinweis(neu, ziel.category, ziel.entity)
        if rest:
            QMessageBox.warning(
                self,
                "Wert korrigieren",
                f"Der Wert ist weiterhin unplausibel:\n{rest}",
            )
            return
        ziel.korrigiert = neu
        # Ein verschlucktes Zeichen kann neben dem gefundenen Rechteck stehen:
        # die Flaeche wird um ein Zeichen verbreitert und die Stelle bleibt als
        # Pruefhinweis stehen.
        ziel.rects = erweitere_rects(ziel.rects, ziel.text)
        ziel.hinweis = "Wert korrigiert \u2013 Stelle im PDF pr\u00fcfen"
        ziel.enabled = True
        if "vom Benutzer" not in ziel.source:
            ziel.source = f"{ziel.source} · vom Benutzer korrigiert"
        # Der bestaetigte Wert geht als Lernbeispiel mit: lerndatei.korrektur
        # schreibt finding.korrigiert, der Fund bleibt als "text_original".
        self._lerne(ziel, ziel.category, ziel.category, 1)
        self._sync_findings()
        self.statusBar().showMessage(
            f"„{vorher}“ als „{neu}“ übernommen und als Lernbeispiel gespeichert; "
            "die Schwärzung wurde um ein Zeichen verbreitert \u2013 bitte die "
            "Stelle im PDF prüfen."
        )

    def _lerne(
        self,
        finding: Finding,
        vorher: Category | None,
        nachher: Category | None,
        anzahl: int = 1,
    ) -> None:
        """Eine Korrektur mit Kontext in die Lerndatei schreiben."""
        eintrag = lerndatei.korrektur(
            finding, self._seitentext(finding.page), vorher, nachher, anzahl
        )
        try:
            lerndatei.merken(eintrag)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Lerndatei",
                f"Die Korrektur konnte nicht gespeichert werden:\n{exc}",
            )

    def _seitentext(self, seite: int) -> str:
        """Text einer Seite der geoeffneten Datei - fuer den Kontext im Beispiel."""
        if not self._path:
            return ""
        doc = None
        try:
            doc = open_document(self._path, self._password)
            return TextMap(doc).page(seite).text
        except Exception:  # noqa: BLE001 - ohne Kontext trotzdem merken
            return ""
        finally:
            if doc is not None:
                doc.close()

    @staticmethod
    def _lerndatei_hinweis(abgehakt: int, umkategorisiert: int) -> str:
        """Kurztext, was die Lerndatei in diesem Durchlauf bewirkt hat."""
        teile: list[str] = []
        if abgehakt:
            teile.append(f"{abgehakt} abgehakt")
        if umkategorisiert:
            teile.append(f"{umkategorisiert} umkategorisiert")
        return ", ".join(teile)

    def _show_lerndatei(self) -> None:
        """Fenster mit den gelernten Beispielen oeffnen."""
        dialog = Lernfenster(self)
        dialog.exec()
        if not dialog.geloescht:
            return
        self.statusBar().showMessage(
            f"{dialog.geloescht} gelernte Beispiele gelöscht."
        )
        # Ohne die Beispiele gelten wieder die Programmmuster.
        if self._path is not None and not self._busy:
            self._run_detection()

    def _reset_lerndatei(self) -> None:
        """Gelernte Beispiele nach Rueckfrage verwerfen."""
        anzahl = len(lerndatei.eintraege())
        if not anzahl:
            QMessageBox.information(
                self,
                "Lerndatei",
                "Es sind keine gelernten Beispiele gespeichert.",
            )
            return
        antwort = QMessageBox.question(
            self,
            "Lerndatei zurücksetzen",
            f"{anzahl} gelernte Beispiele werden verworfen. Danach gelten wieder "
            "allein die Regeln im Programm.\n\nLerndatei wirklich zurücksetzen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return
        try:
            verworfen = lerndatei.zuruecksetzen()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Lerndatei",
                f"Die Lerndatei konnte nicht gelöscht werden:\n{exc}",
            )
            return
        self.statusBar().showMessage(
            f"Lerndatei zurückgesetzt: {verworfen} Beispiele verworfen."
        )
        # Die Liste zeigt sonst weiter den alten Lernstand.
        if self._path is not None and not self._busy:
            self._run_detection()

    def _download_lerndatei(self) -> None:
        """Alle Korrekturen als Lerndatei an einen Ort der Wahl schreiben."""
        anzahl = len(lerndatei.eintraege())
        if not anzahl:
            QMessageBox.information(
                self,
                "Lerndatei",
                "Es gibt noch keine Korrekturen. Rechtsklick auf einen Treffer in "
                "der Liste ordnet ihn einer anderen Kategorie zu; jede Änderung "
                "landet in der Lerndatei.",
            )
            return
        ziel, _ = QFileDialog.getSaveFileName(
            self,
            "Lerndatei herunterladen",
            str(Path.home() / "PDFblack-Lerndatei.jsonl"),
            "Lerndatei (*.jsonl)",
        )
        if not ziel:
            return
        try:
            geschrieben = lerndatei.exportieren(ziel)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Lerndatei",
                f"Die Datei konnte nicht geschrieben werden:\n{exc}",
            )
            return
        self.statusBar().showMessage(
            f"Lerndatei mit {geschrieben} Beispielen gespeichert: {ziel}"
        )

    def _select_finding(self, uid: int) -> None:
        self.canvas.set_selected(uid)
        self.canvas.scroll_to_finding(uid)

    def _set_all_enabled(self, enabled: bool) -> None:
        for finding in self._findings:
            finding.enabled = enabled
        self._sync_findings()

    def _remove_selected(self) -> None:
        uids = set(self.findings_panel.selected_uids())
        if not uids:
            QMessageBox.information(
                self,
                "Keine Auswahl",
                "Bitte zuerst Zeilen in der Trefferliste markieren.",
            )
            return
        self._findings = [f for f in self._findings if f.uid not in uids]
        self._sync_findings()
        self.statusBar().showMessage(f"{len(uids)} Treffer entfernt.")

    def _add_manual_region(self, page: int, x0: float, y0: float, x1: float, y1: float) -> None:
        finding = Finding(
            text="Manuell markierter Bereich",
            category=Category.MANUAL,
            page=page,
            rects=[(x0, y0, x1, y1)],
            source="Manuell · Auswahl",
            entity="MANUAL",
            score=1.0,
            enabled=True,
            uid=self._next_uid,
        )
        self._next_uid += 1
        self._findings.append(finding)
        self._sync_findings()
        self.canvas.set_selected(finding.uid)
        self.findings_panel.select_uid(finding.uid)
        self.statusBar().showMessage("Bereich manuell hinzugefügt.")

    def _add_word_region(
        self, page: int, text: str, x0: float, y0: float, x1: float, y1: float
    ) -> None:
        # Doppelklick im PDF: das Wort unter dem Cursor wird geschwaerzt.
        for finding in self._findings:
            if finding.page != page:
                continue
            for rect in finding.rects:
                if (
                    abs(rect[0] - x0) < 1.5
                    and abs(rect[1] - y0) < 1.5
                    and abs(rect[2] - x1) < 1.5
                    and abs(rect[3] - y1) < 1.5
                ):
                    self.canvas.set_selected(finding.uid)
                    self.findings_panel.select_uid(finding.uid)
                    self.statusBar().showMessage(f"„{text}“ ist bereits markiert.")
                    return
        finding = Finding(
            text=text,
            category=Category.MANUAL,
            page=page,
            rects=[(x0, y0, x1, y1)],
            source="Doppelklick",
            entity="MANUAL",
            score=1.0,
            enabled=True,
            uid=self._next_uid,
        )
        self._next_uid += 1
        self._findings.append(finding)
        self._sync_findings()
        self.canvas.set_selected(finding.uid)
        self.findings_panel.select_uid(finding.uid)
        self.statusBar().showMessage(f"„{text}“ geschwärzt.")

    # ------------------------------------------------------------------
    # Ansicht
    # ------------------------------------------------------------------

    def _set_zoom(self, zoom: float) -> None:
        self.canvas.set_zoom(zoom)
        self.zoom_label.setText(f"{round(self.canvas.zoom * 100)} %")

    def _fit_width(self) -> None:
        if not self._path:
            return
        width = self.canvas.page_width()
        if width <= 0:
            return
        available = self.scroll.viewport().width() - 2 * PdfCanvas.MARGIN - 14
        if available < 80:
            return
        self._set_zoom(available / width)

    def _ensure_visible(self, rect: QRect) -> None:
        self.scroll.ensureVisible(
            rect.center().x(),
            rect.center().y(),
            max(40, rect.width() // 2),
            max(40, rect.height() // 2),
        )

    def _update_page_label(self) -> None:
        if not self._path or self.canvas.page_count == 0:
            self.page_label.setText("")
            return
        y = self.scroll.verticalScrollBar().value() + self.scroll.viewport().height() / 3
        page = self.canvas.page_at_y(y) + 1
        self.page_label.setText(f"Seite {page} / {self.canvas.page_count}")

    def _refresh_state(self) -> None:
        has_doc = self._path is not None
        active = sum(1 for finding in self._findings if finding.enabled)
        self.btn_open.setEnabled(not self._busy)
        self.btn_queue.setEnabled(not self._busy)
        self.btn_queue_next.setEnabled(not self._busy)
        self.btn_preview.setEnabled(has_doc and not self._busy)
        self.btn_preview.setText(
            "Vorschau erzeugen" if not self._findings else "Erkennung erneuern"
        )
        self.btn_save.setEnabled(has_doc and not self._busy and active > 0)
        self.btn_save.setToolTip(
            "Schwärzt alle aktiven Treffer und legt die Kopie in deinem "
            "Benutzerordner ab; sie wird beim Beenden entfernt."
            if active
            else "Noch keine aktiven Treffer."
        )
        for button in (
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_zoom_fit,
        ):
            button.setEnabled(has_doc)
        self.findings_panel.update_counts(self._findings)

    # ------------------------------------------------------------------
    # Speichern
    # ------------------------------------------------------------------

    def _save_as(self) -> None:
        if not self._path or self._busy:
            return
        active = [finding for finding in self._findings if finding.enabled]
        if not active:
            QMessageBox.information(
                self,
                "Nichts zu schwärzen",
                "Es sind keine aktiven Treffer markiert.",
            )
            return

        try:
            target = str(ablage.ziel(self._path))
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Speichern fehlgeschlagen",
                f"Der Ordner für die geschwärzten Kopien ließ sich nicht "
                f"anlegen:\n\n{exc}",
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            count = apply_redactions(self._path, target, active, self._password)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self, "Speichern fehlgeschlagen", f"{type(exc).__name__}: {exc}"
            )
            return
        QApplication.restoreOverrideCursor()

        self.compare_view.remember(target)
        self.statusBar().showMessage(f"{count} Stellen geschwärzt: {target}")
        if self._queue_total:
            # Im Stapel ohne Rueckfrage weiter: die naechste Datei kommt gleich.
            self._queue_done += 1
            self._open_next_in_queue()
            return
        QMessageBox.information(
            self,
            "Geschwärzte Kopie gespeichert",
            f"{count} Stellen wurden geschwärzt. Die Kopie liegt im "
            f"Benutzerordner:\n\n{target}\n\nDas Original bleibt unverändert. "
            "Die Kopie wird beim Beenden von PDFblack entfernt – vorher "
            "weitergeben, wenn sie gebraucht wird.",
        )

    # ------------------------------------------------------------------
    # Hilfe
    # ------------------------------------------------------------------

    def _open_preferences(self) -> None:
        dialog = PreferencesDialog(self)
        dialog.exec()
        # Neue Agenten erscheinen sofort als Knöpfe unter den Zeugnissen.
        self.compare_view.refresh()

    def _show_guide(self) -> None:
        QMessageBox.information(
            self,
            "So funktioniert PDFblack",
            "1. PDF-Datei hierher ziehen oder über „PDF öffnen …“ auswählen.\n\n"
            "2. Beim Öffnen startet die Prüfung von selbst: Die Software sucht "
            "Namen, Adressen, PLZ/Ort, Nummern, E-Mail, Telefon, IBAN und eigene "
            "Regexe. Mit „Vorschau erzeugen“ lässt sich das jederzeit "
            "wiederholen; gefundene Stellen werden nur farbig markiert – die "
            "Datei bleibt unverändert.\n\n"
            "3. Links Werte eintragen, die die KI nicht erkannt hat (Vorname, "
            "Nachname, Adresse, PLZ, Ort, Personennummer) und erneut suchen: "
            "diese Werte werden im zweiten Durchlauf gesucht.\n\n"
            "4. Prüfen und überarbeiten: Klick auf eine Markierung schaltet sie "
            "aus oder wieder ein, Ziehen mit der Maus fügt einen eigenen Bereich "
            "hinzu, die Trefferliste rechts erlaubt Abwählen und Entfernen.\n\n"
            "5. „Geschwärzte Kopie speichern“ legt eine neue PDF-Datei im "
            "Benutzerordner an (Ordner „PDFblack/Geschwärzt“), in der der "
            "Text unter den Markierungen wirklich entfernt ist. Das Original "
            "bleibt unverändert.",
        )

    def _show_privacy(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Datenschutz")
        dialog.resize(660, 620)
        dialog.setMinimumSize(520, 400)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Datenschutz")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        subtitle = QLabel("Wie PDFblack mit den Daten in Ihren PDF-Dateien umgeht.")
        subtitle.setObjectName("AppSubtitle")
        layout.addWidget(subtitle)

        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml(PRIVACY_HTML)
        layout.addWidget(text, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Schließen")
        close.clicked.connect(dialog.accept)
        close.setDefault(True)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"Über {APP_NAME}",
            f"<h3>{APP_NAME} {APP_VERSION}</h3>"
            f"<p>{APP_TAGLINE}</p>"
            "<p>Erkennung: Microsoft Presidio mit spaCy (MIT-Lizenz).<br>"
            "PDF-Verarbeitung: PyMuPDF.<br>"
            "Oberfläche: Qt für Python (PySide6).</p>"
            "<p>Alle Schwärzungen werden beim Speichern physisch aus dem "
            "Dokument entfernt und die Datei wird neu geschrieben.</p>",
        )

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def start_auto_update(self) -> None:
        """Beim Start still nach einer neueren Version sehen."""
        QTimer.singleShot(2000, lambda: self._check_updates(silent=True))

    def _check_updates(self, silent: bool) -> None:
        if self._update_check is not None or self._update_download is not None:
            return
        if silent and self._path is not None:
            # Waehrend der Arbeit nicht ungefragt beenden und neu starten.
            return
        self._update_silent = silent
        if not silent:
            self.update_action.setEnabled(False)
            self.statusBar().showMessage("Suche nach Updates …")
        worker = UpdateCheckWorker()
        worker.done.connect(self._on_update_checked)
        worker.finished.connect(worker.deleteLater)
        self._update_check = worker
        worker.start()

    def _on_update_checked(self, release) -> None:
        self._update_check = None
        self.update_action.setEnabled(True)
        silent = self._update_silent
        if not silent:
            self.statusBar().showMessage("Bereit.", 4000)
        if release is None:
            if not silent:
                QMessageBox.warning(
                    self,
                    "Nach Updates suchen",
                    "Die Update-Quelle war nicht erreichbar. Bitte die "
                    "Internetverbindung prüfen und erneut versuchen.",
                )
            return
        if not is_newer(APP_VERSION, release.version):
            if not silent:
                QMessageBox.information(
                    self,
                    "Nach Updates suchen",
                    f"{APP_NAME} {APP_VERSION} ist auf dem neuesten Stand.",
                )
            return
        choice = asset_for(release)
        if choice is None:
            if not silent:
                QMessageBox.information(
                    self,
                    "Nach Updates suchen",
                    f"Version {release.version} ist verfügbar, für dieses "
                    "Betriebssystem gibt es aber kein passendes Paket.\n\n"
                    f"{release.page}",
                )
            return
        if not silent:
            answer = QMessageBox.question(
                self,
                "Update verfügbar",
                f"Version {release.version} ist verfügbar "
                f"(installiert: {APP_VERSION}).\n\nJetzt herunterladen und "
                "installieren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
        self._begin_update(release, choice)

    def _begin_update(self, release: Release, choice: tuple[str, str]) -> None:
        name, url = choice
        target = Path(tempfile.mkdtemp(prefix="pdfblack-update-")) / name
        self._update_version = release.version
        # Ladebalken in der Statuszeile - auch beim stillen Update.
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.statusBar().showMessage(f"Update {release.version} wird geladen …")
        if not self._update_silent:
            dialog = QProgressDialog(
                f"{APP_NAME} {release.version} wird geladen …", "", 0, 0, self
            )
            dialog.setWindowTitle("Update")
            dialog.setCancelButton(None)
            dialog.setWindowModality(Qt.WindowModal)
            dialog.setMinimumDuration(0)
            dialog.show()
            self._update_progress = dialog
        worker = UpdateDownloadWorker(url, target)
        worker.progressed.connect(self._on_update_progress)
        worker.done.connect(self._on_update_downloaded)
        worker.failed.connect(self._on_update_failed)
        worker.finished.connect(worker.deleteLater)
        self._update_download = worker
        worker.start()

    def _on_update_progress(self, received: int, total: int) -> None:
        if total:
            value = min(received, total)
            self.progress.setRange(0, total)
            self.progress.setValue(value)
            self.statusBar().showMessage(
                f"Update {self._update_version} wird geladen … "
                f"{value * 100 // total} %"
            )
        dialog = self._update_progress
        if dialog is None or not total:
            return
        dialog.setRange(0, total)
        dialog.setValue(min(received, total))

    def _on_update_downloaded(self, path: str) -> None:
        self._update_download = None
        self._close_update_progress()
        result = install(Path(path))
        if not result.ok:
            self.statusBar().showMessage(
                "Update nicht eingespielt – bitte von Hand von der Release-Seite "
                "installieren.",
                15000,
            )
            if not self._update_silent:
                QMessageBox.warning(self, "Update nicht möglich", result.message)
            return
        self.statusBar().showMessage(result.message)
        if not self._update_silent:
            QMessageBox.information(self, "Update", result.message)
        # Der Installer startet erst, wenn dieser Prozess beendet ist (der
        # Helfer wartet darauf) - das Fenster kann also sofort schliessen.
        QTimer.singleShot(250, self.close)

    def _on_update_failed(self, message: str) -> None:
        self._update_download = None
        self._close_update_progress()
        self.statusBar().showMessage("Update konnte nicht geladen werden.", 8000)
        if not self._update_silent:
            QMessageBox.warning(self, "Update fehlgeschlagen", message)

    def _close_update_progress(self) -> None:
        dialog = self._update_progress
        self._update_progress = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setValue(0)

    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._update_download is not None and self._update_download.isRunning():
            # Laufenden Download nicht abreissen, sonst endet der Thread im Nichts.
            self._update_download.wait(5000)
        if self._worker is not None:
            answer = QMessageBox.question(
                self,
                "Erkennung läuft",
                "Die Erkennung läuft noch. Abbrechen und PDFblack beenden?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker = None
        # Das geladene Dokument zuerst schliessen: unter Windows ist eine
        # geoeffnete PDF gesperrt. Wird sie erst spaeter entladen, scheitert
        # das Aufraeumen der Ablage und meldet einen Fehler fuer genau die
        # geladene Datei.
        self.canvas.clear()
        self._path = None
        self._password = None
        self._findings = []
        # Geschwaerzte Kopien liegen im Benutzerordner und verschwinden beim
        # Beenden wieder - samt Kopien im Uebergabeordner an die Agenten.
        kopien = [str(pfad) for pfad in ablage.dateien()]
        if kopien:
            delete_redacted(kopien)
        # PDFcompare: Listen leeren und nach den Dateien fragen.
        self.compare_view.cleanup_on_close(self)
        # Arbeitsdateien der Texterkennung: das Dokument ist jetzt geschlossen,
        # also darf auch seine Arbeitsdatei weg.
        self.ocr_view.cleanup_temp()
        event.accept()
