"""PDFcompare: die zuletzt geschwaerzten Dateien auf zwei Stapel verteilen."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import preferences
from .panels import _settings

RECENT_KEY = "compare/recent"
LIFE_KEY = "compare/lebenslauf"
CERT_KEY = "compare/arbeitszeugnisse"
MAX_RECENT = 30

LIFE_PREFIX = "Lebenslauf"
CERT_PREFIX = "Arbeitszeugnis"


def handover_folder(agent: str) -> Path:
    """Ordner, in dem die Dateien fuer einen Agenten bereitgelegt werden."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", agent).strip() or "Copilot"
    return Path(base) / "PDFblack" / "Copilot-Uebergabe" / safe


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


class RecentList(QListWidget):
    """Quelle: die zuletzt geschwaerzten PDF-Dateien."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
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


class DropList(QListWidget):
    """Ablage fuer PDF-Dateien; nimmt Ziehungen aus der linken Liste an."""

    def __init__(self, on_change=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._on_change = on_change

    # -- Ablage -------------------------------------------------------

    def _paths_from(self, event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
        ]

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
        for path in paths:
            self.add_file(path)
        event.acceptProposedAction()
        self._changed()

    def remove_path(self, path: str) -> bool:
        path = os.path.abspath(path)
        for index in range(self.count()):
            if self.item(index).data(Qt.UserRole) == path:
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
        return any(
            self.item(index).data(Qt.UserRole) == path for index in range(self.count())
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

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change(self)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.selectedItems():
                self.takeItem(self.row(item))
            self._changed()
            return
        super().keyPressEvent(event)


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
        self.recent = RecentList()
        self.recent.setToolTip("Dateien nach rechts in einen Stapel ziehen")
        left.addWidget(self.recent, 1)
        hint = QLabel("Datei auf einen Stapel rechts ziehen.")
        hint.setObjectName("Hint")
        left.addWidget(hint)
        layout.addLayout(left, 1)

        # --- rechte Seite --------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(8)

        life_title = QLabel("Lebenslauf")
        life_title.setObjectName("SectionLabel")
        right.addWidget(life_title)
        self.life = DropList(on_change=self._changed)
        self.life.setMaximumHeight(170)
        right.addWidget(self.life, 0)

        cert_title = QLabel("Arbeitszeugnisse")
        cert_title.setObjectName("SectionLabel")
        right.addWidget(cert_title)
        self.certs = DropList(on_change=self._changed)
        right.addWidget(self.certs, 1)

        # Uebergabe an Copilot: je Agent ein Knopf, ohne Agent die Einstellungen.
        self.agent_box = QWidget()
        self.agent_layout = QVBoxLayout(self.agent_box)
        self.agent_layout.setContentsMargins(0, 4, 0, 0)
        self.agent_layout.setSpacing(6)
        self.agent_buttons: list[QPushButton] = []
        right.addWidget(self.agent_box, 0)

        layout.addLayout(right, 1)

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
        preferences.open_copilot(entry)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        self.message.emit(
            f"{len(dateien)} Dateien für Copilot Agent „{entry['name']}“ bereit: {folder}"
        )

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Listen aus den Einstellungen aufbauen."""
        self._refreshing = True
        self.recent.clear()
        self.life.set_files(_read_list(LIFE_KEY))
        self.certs.set_files(_read_list(CERT_KEY))
        zugeordnet = set(self.life.paths()) | set(self.certs.paths())
        for path in _read_list(RECENT_KEY):
            if not os.path.exists(path) or path in zugeordnet:
                continue
            item = QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)
        self._refreshing = False
        self._rebuild_agent_buttons()

    def remember(self, path: str) -> None:
        """Eine frisch geschwaerzte Datei oben in die Liste aufnehmen."""
        path = os.path.abspath(path)
        if path in self.life.paths() or path in self.certs.paths():
            # Steht schon in einem Stapel - eine Datei ist nur einmal gelistet.
            return
        entries = [item for item in _read_list(RECENT_KEY) if item != path]
        entries.insert(0, path)
        _write_list(RECENT_KEY, entries[:MAX_RECENT])
        self.refresh()

    def _changed(self, source: "DropList") -> None:
        """Nach dem Ablegen: eine Datei steht immer nur in einer Liste."""
        if self._refreshing:
            return
        assigned = set(source.paths())
        other = self.certs if source is self.life else self.life
        for path in list(other.paths()):
            if path in assigned:
                other.remove_path(path)
        for path in assigned:
            self._forget(path)
        self._store()

    def _forget(self, path: str) -> None:
        """Datei aus der Liste der zuletzt geschwaerzten entfernen."""
        for index in range(self.recent.count()):
            if self.recent.item(index).data(Qt.UserRole) == path:
                self.recent.takeItem(index)
                break
        rest = [entry for entry in _read_list(RECENT_KEY) if entry != path]
        _write_list(RECENT_KEY, rest)

    def _store(self) -> None:
        if self._refreshing:
            return
        _write_list(LIFE_KEY, self.life.paths())
        _write_list(CERT_KEY, self.certs.paths())
