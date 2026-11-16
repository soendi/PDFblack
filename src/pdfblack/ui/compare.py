"""PDFcompare: die zuletzt geschwaerzten Dateien auf zwei Stapel verteilen."""

from __future__ import annotations

import os

from PySide6.QtCore import QMimeData, Qt, QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .panels import _settings

RECENT_KEY = "compare/recent"
LIFE_KEY = "compare/lebenslauf"
CERT_KEY = "compare/arbeitszeugnisse"
MAX_RECENT = 30


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
            self._on_change()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.selectedItems():
                self.takeItem(self.row(item))
            self._changed()
            return
        super().keyPressEvent(event)


class CompareView(QWidget):
    """Linke Spalte: zuletzt geschwaerzt, rechte Spalte: zwei Stapel."""

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
        self.life = DropList(on_change=self._store)
        self.life.setMaximumHeight(170)
        right.addWidget(self.life, 0)

        cert_title = QLabel("Arbeitszeugnisse")
        cert_title.setObjectName("SectionLabel")
        right.addWidget(cert_title)
        self.certs = DropList(on_change=self._store)
        right.addWidget(self.certs, 1)

        layout.addLayout(right, 1)

        self._refreshing = False
        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Listen aus den Einstellungen aufbauen."""
        self._refreshing = True
        self.recent.clear()
        for path in _read_list(RECENT_KEY):
            if not os.path.exists(path):
                continue
            item = QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)
        self.life.set_files(_read_list(LIFE_KEY))
        self.certs.set_files(_read_list(CERT_KEY))
        self._refreshing = False

    def remember(self, path: str) -> None:
        """Eine frisch geschwaerzte Datei oben in die Liste aufnehmen."""
        path = os.path.abspath(path)
        entries = [item for item in _read_list(RECENT_KEY) if item != path]
        entries.insert(0, path)
        _write_list(RECENT_KEY, entries[:MAX_RECENT])
        self.refresh()

    def _store(self) -> None:
        if self._refreshing:
            return
        _write_list(LIFE_KEY, self.life.paths())
        _write_list(CERT_KEY, self.certs.paths())
