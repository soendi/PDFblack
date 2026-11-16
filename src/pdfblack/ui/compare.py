"""PDFcompare: die zuletzt geschwaerzten Dateien auf zwei Stapel verteilen."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pymupdf

from PySide6.QtCore import QMimeData, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import preferences
from .panels import _settings
from .review import ReviewDialog

RECENT_KEY = "compare/recent"
LIFE_KEY = "compare/lebenslauf"
CERT_KEY = "compare/arbeitszeugnisse"
MAX_RECENT = 30

LIFE_PREFIX = "Lebenslauf"
CERT_PREFIX = "Arbeitszeugnis"

HANDOVER_PROMPT = (
    "Hier sind Lebenslauf und Arbeitszeugnisse. Bitte lies die Unterlagen "
    "und fasse sie zusammen."
)


def handover_base() -> Path:
    """Wurzel der Uebergabeordner (ein Unterordner je Agent)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return Path(base) / "PDFblack" / "Copilot-Uebergabe"


def handover_folder(agent: str) -> Path:
    """Ordner, in dem die Dateien fuer einen Agenten bereitgelegt werden."""
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", agent).strip() or "Copilot"
    return handover_base() / safe


def handover_files(
    folder: Path, life: list[str], certs: list[str]
) -> list[Path]:
    """Dateien so kopieren, dass Copilot Lebenslauf und Zeugnisse erkennt.

    Aus ``bewerbung.pdf`` im Stapel Lebenslauf wird ``Lebenslauf_bewerbung.pdf``,
    aus dem Stapel Arbeitszeugnisse ``Arbeitszeugnis_bewerbung.pdf``. Der Ordner
    wird vorher geleert, damit ein zweiter Klick dieselben Namen erzeugt.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for alt in folder.glob("*.pdf"):
        try:
            alt.unlink()
        except OSError:
            pass
    kopiert: list[Path] = []
    for prefix, pfade in ((LIFE_PREFIX, life), (CERT_PREFIX, certs)):
        for pfad in pfade:
            quelle = Path(pfad)
            if not quelle.is_file():
                continue
            ziel = folder / f"{prefix}_{quelle.stem}.pdf"
            nummer = 2
            while ziel.exists():
                ziel = folder / f"{prefix}_{quelle.stem}_{nummer}.pdf"
                nummer += 1
            shutil.copy2(quelle, ziel)
            kopiert.append(ziel)
    return kopiert


def bundle_pdfs(files: list[Path], target: Path) -> Path | None:
    """Mehrere PDFs zu einer Datei zusammenfassen.

    Copilot bekommt nur eine Datei uebergeben. Nicht lesbare Dateien werden
    uebersprungen; ist keine einzige lesbar, gibt es kein Buendel.
    """
    merged = pymupdf.open()
    try:
        for pfad in files:
            try:
                quelle = pymupdf.open(str(pfad))
            except Exception:  # noqa: BLE001 - kaputte Datei ueberspringen
                continue
            try:
                merged.insert_pdf(quelle)
            finally:
                quelle.close()
        if merged.page_count == 0:
            return None
        merged.save(str(target))
    finally:
        merged.close()
    return target


def delete_redacted(paths: list[str]) -> tuple[int, list[str]]:
    """Geschwaerzte Dateien und ihre Kopien im Uebergabeordner loeschen.

    Zurueck kommen die Anzahl geloeschter Dateien und die Fehlermeldungen;
    fehlende Dateien gelten nicht als Fehler.
    """
    geloescht = 0
    fehler: list[str] = []
    stems: list[str] = []

    for path in paths:
        datei = Path(path)
        stems.append(datei.stem)
        try:
            if datei.is_file():
                datei.unlink()
                geloescht += 1
        except OSError as exc:
            fehler.append(f"{datei.name}: {exc}")

    base = handover_base()
    if not base.is_dir():
        return geloescht, fehler

    for folder in sorted(entry for entry in base.iterdir() if entry.is_dir()):
        kopien = [folder / "Unterlagen.pdf"]
        for stem in stems:
            kopien.append(folder / f"{LIFE_PREFIX}_{stem}.pdf")
            kopien.append(folder / f"{CERT_PREFIX}_{stem}.pdf")
        for kopie in kopien:
            try:
                if kopie.is_file():
                    kopie.unlink()
                    geloescht += 1
            except OSError as exc:
                fehler.append(f"{kopie.name}: {exc}")
        try:
            if not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass

    return geloescht, fehler


def _norm(path: str) -> str:
    """Pfad fuer Vergleiche - unter Windows ohne Ruecksicht auf Schreibweise."""
    return os.path.normcase(os.path.abspath(str(path)))


def _read_list(key: str) -> list[str]:
    """Gespeicherte Pfadliste lesen (QSettings liefert je nach System String)."""
    value = _settings().value(key, [])
    if isinstance(value, str):
        return [value] if value else []
    if value is None:
        return []
    return [str(item) for item in value]


def _write_list(key: str, paths: list[str]) -> None:
    _settings().setValue(key, list(paths))


class PathList(QListWidget):
    """Liste von PDF-Pfaden, in beide Richtungen ziehbar.

    Was abgelegt wird, meldet die Liste per ``dropped``; das Verschieben
    zwischen den Listen macht die Ansicht, damit eine Datei nur in einer steht.
    """

    changed = Signal()
    dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def mimeData(self, items) -> QMimeData:  # type: ignore[override]
        mime = QMimeData()
        paths = [
            str(item.data(Qt.UserRole))
            for item in items
            if isinstance(item.data(Qt.UserRole), str)
        ]
        if paths:
            mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
            mime.setText("\n".join(paths))
        return mime

    # -- Ablage -------------------------------------------------------

    def accepts(self, path: str) -> bool:
        """Darf diese Datei hier abgelegt werden?"""
        return True

    def _paths_from(self, event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        paths = [
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
        ]
        return [path for path in paths if self.accepts(path)]

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._paths_from(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._paths_from(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = self._paths_from(event)
        if not paths:
            event.ignore()
            return
        added = [path for path in paths if self.add_file(path)]
        event.acceptProposedAction()
        if added:
            self.dropped.emit(added)
        self.changed.emit()

    def remove_path(self, path: str) -> bool:
        gesucht = _norm(path)
        for index in range(self.count()):
            if _norm(self.item(index).data(Qt.UserRole)) == gesucht:
                self.takeItem(index)
                return True
        return False

    # -- Inhalt -------------------------------------------------------

    def add_file(self, path: str) -> bool:
        path = os.path.abspath(path)
        if self.contains_path(path):
            return False
        item = QListWidgetItem(os.path.basename(path))
        item.setToolTip(path)
        item.setData(Qt.UserRole, path)
        self.addItem(item)
        return True

    def contains_path(self, path: str) -> bool:
        gesucht = _norm(path)
        return any(
            _norm(self.item(index).data(Qt.UserRole)) == gesucht
            for index in range(self.count())
        )

    def paths(self) -> list[str]:
        return [
            str(self.item(index).data(Qt.UserRole)) for index in range(self.count())
        ]

    def set_files(self, paths: list[str]) -> None:
        self.clear()
        for path in paths:
            if path:
                self.add_file(path)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.selectedItems():
                self.takeItem(self.row(item))
            self.changed.emit()
            return
        super().keyPressEvent(event)


class RecentList(PathList):
    """Zuletzt geschwaerzt: nimmt nur Dateien aus den beiden Stapeln zurueck."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._from_stacks: set[str] = set()

    def allow(self, paths) -> None:
        """Welche Dateien gerade in einem Stapel stehen."""
        self._from_stacks = {_norm(path) for path in paths}

    def accepts(self, path: str) -> bool:
        return _norm(path) in self._from_stacks


class DropList(PathList):
    """Stapel fuer Lebenslauf oder Zeugnisse."""

    def __init__(self, on_change=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        if on_change is not None:
            self.changed.connect(lambda: on_change(self))


def trash_pixmap(size: int = 22) -> QPixmap:
    """Kleiner roter Muellimer fuer die Ablagezone."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    s = float(size)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#e5484d"))
    painter.drawRoundedRect(QRectF(s * 0.42, s * 0.04, s * 0.16, s * 0.07), s * 0.03, s * 0.03)
    painter.drawRoundedRect(QRectF(s * 0.26, s * 0.11, s * 0.48, s * 0.09), s * 0.04, s * 0.04)
    painter.drawRoundedRect(QRectF(s * 0.21, s * 0.24, s * 0.58, s * 0.66), s * 0.10, s * 0.10)
    painter.setBrush(QColor("#14161b"))
    for x in (0.34, 0.47, 0.60):
        painter.drawRoundedRect(QRectF(s * x, s * 0.34, s * 0.05, s * 0.44), s * 0.02, s * 0.02)
    painter.end()
    return pixmap


class TrashZone(QFrame):
    """Kleine Ablage: entfernt eine Datei aus der Liste, nicht vom Rechner."""

    dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Trash")
        self.setFixedHeight(56)
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(trash_pixmap(22))
        text = QLabel("Datei hierher ziehen, um sie aus der Liste zu entfernen")
        text.setObjectName("Hint")
        text.setWordWrap(True)
        layout.addWidget(icon, 0, Qt.AlignVCenter)
        layout.addWidget(text, 1)

    def _paths_from(self, event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
        ]

    def _active(self, active: bool) -> None:
        self.setProperty("dragActive", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._paths_from(event):
            self._active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._paths_from(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = self._paths_from(event)
        self._active(False)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.dropped.emit(paths)


class CompareView(QWidget):
    """Linke Spalte: zuletzt geschwaerzt, rechte Spalte: zwei Stapel."""

    settingsRequested = Signal()
    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        # --- linke Seite ---------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(8)
        left_title = QLabel("Zuletzt geschwärzt")
        left_title.setObjectName("SectionLabel")
        left.addWidget(left_title)
        # Beide Stapel zuerst, damit die Knoepfe links alle Listen kennen.
        self.recent = RecentList()
        self.recent.setToolTip("Dateien zwischen den Listen hin und her ziehen")
        self.life = DropList()
        self.certs = DropList()
        left.addWidget(self.recent, 1)

        # Drei Knoepfe: je eine Liste leeren (Dateien bleiben auf dem Rechner).
        leer_layout = QHBoxLayout()
        leer_layout.setSpacing(6)
        for text, liste in (
            ("Zuletzt leeren", self.recent),
            ("Lebenslauf leeren", self.life),
            ("Zeugnisse leeren", self.certs),
        ):
            knopf = QPushButton(text)
            knopf.setObjectName("Ghost")
            knopf.clicked.connect(lambda _=False, ziel=liste: self.clear_list(ziel))
            leer_layout.addWidget(knopf)
        left.addLayout(leer_layout)

        hint = QLabel("Dateien zwischen den Listen ziehen; Entf entfernt einen Eintrag.")
        hint.setObjectName("Hint")
        left.addWidget(hint)
        layout.addLayout(left, 1)

        # --- rechte Seite --------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(8)

        life_title = QLabel("Lebenslauf")
        life_title.setObjectName("SectionLabel")
        right.addWidget(life_title)
        self.life.setMaximumHeight(170)
        right.addWidget(self.life, 0)

        cert_title = QLabel("Arbeitszeugnisse")
        cert_title.setObjectName("SectionLabel")
        right.addWidget(cert_title)
        right.addWidget(self.certs, 1)

        # Kleine Ablage unter den Zeugnissen.
        self.trash = TrashZone()
        right.addWidget(self.trash, 0)

        # Uebergabe an Copilot: je Agent ein Knopf, ohne Agent die Einstellungen.
        self.agent_box = QWidget()
        self.agent_layout = QVBoxLayout(self.agent_box)
        self.agent_layout.setContentsMargins(0, 4, 0, 0)
        self.agent_layout.setSpacing(6)
        self.agent_buttons: list[QPushButton] = []
        right.addWidget(self.agent_box, 0)

        # Unterlagen pruefen (lokale Befunde) und an Copilot fragen.
        self.review_button = QPushButton("Unterlagen prüfen …")
        self.review_button.setObjectName("Review")
        self.review_button.setToolTip(
            "Lücken, Scans und Vollständigkeit prüfen; Frage an Copilot kopieren"
        )
        self.review_button.clicked.connect(self._open_review)
        right.addWidget(self.review_button, 0)

        layout.addLayout(right, 1)

        for liste in (self.recent, self.life, self.certs):
            liste.changed.connect(self._store)
            liste.dropped.connect(
                lambda paths, ziel=liste: self._moved(ziel, paths)
            )
        self.trash.dropped.connect(self._trash_dropped)

        self._refreshing = False
        self.refresh()

    def _rebuild_agent_buttons(self) -> None:
        """Knöpfe unter der Zeugnisliste neu aufbauen."""
        while self.agent_layout.count():
            item = self.agent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.agent_buttons = []

        entries = preferences.agents()
        if not entries:
            knopf = QPushButton("Einstellungen Copilot")
            knopf.setObjectName("AgentSettings")
            knopf.setToolTip("Agenten hinterlegen, an die PDFcompare übergeben soll")
            knopf.clicked.connect(self.settingsRequested.emit)
            self.agent_layout.addWidget(knopf)
            self.agent_buttons.append(knopf)
            return

        for entry in entries:
            knopf = QPushButton(f"An Copilot Agent „{entry['name']}“ übergeben")
            knopf.setObjectName("Agent")
            knopf.setToolTip(
                f"Lebenslauf und Zeugnisse benannt an „{entry['name']}“ übergeben"
            )
            knopf.clicked.connect(
                lambda _checked=False, eintrag=entry: self._hand_over(eintrag)
            )
            self.agent_layout.addWidget(knopf)
            self.agent_buttons.append(knopf)

    def _open_review(self) -> None:
        """Prüffenster mit lokalen Befunden und der Copilot-Frage öffnen."""
        if not preferences.review_enabled():
            return
        dialog = ReviewDialog(self.life.paths(), self.certs.paths(), self)
        dialog.exec()

    def _hand_over(self, entry: dict[str, str]) -> None:
        """Stapel benannt bereitlegen und Copilot mit dem Agenten öffnen."""
        life = self.life.paths()
        certs = self.certs.paths()
        if not life and not certs:
            self.message.emit(
                "Keine Dateien zum Übergeben: erst Lebenslauf und Zeugnisse zuordnen."
            )
            return

        folder = handover_folder(entry["name"])
        dateien = handover_files(folder, life, certs)
        if not dateien:
            self.message.emit("Die Dateien der beiden Stapel wurden nicht gefunden.")
            return

        QApplication.clipboard().setText("\n".join(str(pfad) for pfad in dateien))

        # Copilot nimmt nur eine Datei entgegen: alles zu einer PDF buendeln.
        anhang = dateien[0]
        if len(dateien) > 1:
            gebuendelt = bundle_pdfs(dateien, folder / "Unterlagen.pdf")
            if gebuendelt is not None:
                anhang = gebuendelt

        geoeffnet = preferences.open_copilot(
            entry, prompt=HANDOVER_PROMPT, file=str(anhang)
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if geoeffnet:
            self.message.emit(
                f"{len(dateien)} Dateien für Copilot Agent „{entry['name']}“ "
                f"bereit, Copilot mit „{anhang.name}“ geöffnet."
            )
        else:
            self.message.emit(
                f"{len(dateien)} Dateien für Copilot Agent „{entry['name']}“ "
                f"bereit: {folder}"
            )

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Listen aus den Einstellungen aufbauen."""
        self._refreshing = True
        self.recent.clear()
        self.life.set_files(_read_list(LIFE_KEY))
        self.certs.set_files(_read_list(CERT_KEY))
        zugeordnet = {_norm(path) for path in self.life.paths() + self.certs.paths()}
        for path in _read_list(RECENT_KEY):
            if not os.path.exists(path) or _norm(path) in zugeordnet:
                continue
            item = QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)
        self._sync_allowed()
        self._refreshing = False
        self._rebuild_agent_buttons()
        # Die Pruefung ist fakultativ: ohne Schalter kein Knopf.
        self.review_button.setVisible(preferences.review_enabled())

    def remember(self, path: str) -> None:
        """Eine frisch geschwaerzte Datei oben in die Liste aufnehmen."""
        path = os.path.abspath(path)
        zugeordnet = {_norm(item) for item in self.life.paths() + self.certs.paths()}
        if _norm(path) in zugeordnet:
            # Steht schon in einem Stapel - eine Datei ist nur einmal gelistet.
            return
        entries = [item for item in _read_list(RECENT_KEY) if _norm(item) != _norm(path)]
        entries.insert(0, path)
        _write_list(RECENT_KEY, entries[:MAX_RECENT])
        self.refresh()

    def _moved(self, target: "PathList", paths: list[str]) -> None:
        """Nach dem Ablegen: eine Datei steht immer nur in einer Liste."""
        if self._refreshing:
            return
        verschoben = [path for path in paths if os.path.exists(path)]
        for path in verschoben:
            for liste in (self.recent, self.life, self.certs):
                if liste is not target:
                    liste.remove_path(path)
        if target is self.recent and verschoben:
            # Zurueck nach links: die Datei steht dort wieder oben.
            for path in reversed(verschoben):
                for index in range(self.recent.count()):
                    item = self.recent.item(index)
                    if _norm(item.data(Qt.UserRole)) == _norm(path):
                        self.recent.takeItem(index)
                        self.recent.insertItem(0, item)
                        break
        self._sync_allowed()
        self._store()

    def _sync_allowed(self) -> None:
        """Die linke Liste nimmt nur zurueck, was in einem Stapel steht."""
        self.recent.allow(set(self.life.paths()) | set(self.certs.paths()))

    def _store(self) -> None:
        if self._refreshing:
            return
        _write_list(RECENT_KEY, self.recent.paths())
        _write_list(LIFE_KEY, self.life.paths())
        _write_list(CERT_KEY, self.certs.paths())

    def clear_list(self, liste: "PathList") -> None:
        """Eine Liste leeren - die Dateien auf dem Rechner bleiben."""
        if not liste.count():
            return
        liste.clear()
        self._sync_allowed()
        self._store()

    def clear_all(self) -> None:
        """Alle drei Listen leeren, auch die gespeicherten."""
        self._refreshing = True
        try:
            for liste in (self.recent, self.life, self.certs):
                liste.clear()
            for key in (RECENT_KEY, LIFE_KEY, CERT_KEY):
                _write_list(key, [])
            self._sync_allowed()
        finally:
            self._refreshing = False

    def _trash_dropped(self, paths: list[str]) -> None:
        """Ablegen auf dem Muellimer: nur aus der Liste entfernen."""
        if not paths:
            return
        namen = "\n".join(os.path.basename(path) for path in paths)
        antwort = QMessageBox.question(
            self,
            "Wirklich entfernen?",
            f"{namen}\n\nAus der Liste entfernen? Die Datei bleibt auf dem "
            "Rechner erhalten.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return
        for path in paths:
            for liste in (self.recent, self.life, self.certs):
                liste.remove_path(path)
        self._sync_allowed()
        self._store()
        self.message.emit("Aus der Liste entfernt – die Datei bleibt erhalten.")

    def cleanup_on_close(self, parent: QWidget) -> None:
        """Beim Beenden die Listen leeren und nach den Dateien fragen."""
        paths = list(
            dict.fromkeys(self.recent.paths() + self.life.paths() + self.certs.paths())
        )
        self.clear_all()
        if not paths:
            return

        antwort = QMessageBox.question(
            parent,
            "Listen geleert",
            "Die drei Listen sind geleert.\n\nAuch die geschwärzten Dateien auf dem "
            f"Rechner löschen ({len(paths)})? Kopien im Copilot-Übergabeordner "
            "werden dann ebenfalls entfernt.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return

        _, fehler = delete_redacted(paths)
        if fehler:
            QMessageBox.warning(
                parent,
                "Nicht alles gelöscht",
                "Diese Dateien konnten nicht gelöscht werden:\n\n"
                + "\n".join(fehler[:8]),
            )
