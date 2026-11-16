"""Einstellungen: PDFcompare mit Windows Copilot verknuepfen."""

from __future__ import annotations

import json
import sys
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .panels import _settings

LINKED_KEY = "copilot/linked"
AGENTS_KEY = "copilot/agents"
ACTIVE_KEY = "copilot/agent"

COPILOT_URI = "ms-copilot:"
COPILOT_WEB = "https://m365.cloud.microsoft/chat/"

HINT = (
    "Windows Copilot bietet kein Programm-Interface, über das eine andere "
    "Anwendung einen Agenten auswählen kann. PDFblack merkt sich den Agenten "
    "und öffnet Copilot; wird ein Agent-Link hinterlegt, kannst du ihn in "
    "Copilot direkt aufrufen."
)


def agents() -> list[dict[str, str]]:
    """Gespeicherte Agenten: Name und optionaler Link."""
    raw = _settings().value(AGENTS_KEY, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    result: list[dict[str, str]] = []
    for entry in data:
        if isinstance(entry, dict) and entry.get("name"):
            result.append(
                {"name": str(entry["name"]), "link": str(entry.get("link", ""))}
            )
    return result


def save_agents(entries: list[dict[str, str]]) -> None:
    _settings().setValue(AGENTS_KEY, json.dumps(entries, ensure_ascii=False))


def is_linked() -> bool:
    return bool(_settings().value(LINKED_KEY, False, type=bool))


def active_agent() -> dict[str, str] | None:
    name = str(_settings().value(ACTIVE_KEY, "") or "")
    for entry in agents():
        if entry["name"] == name:
            return entry
    return None


def copilot_uri(prompt: str = "", file: str | None = None) -> str:
    """URI fuer Copilot mit vorformulierter Frage und angehaengter Datei.

    Der Parameter ``file`` ist nicht von Microsoft dokumentiert; der Handler
    wertet ihn nach bisherigen Berichten aus (``ms-copilot:chat?q=...&file=...``).
    Wirkt er nicht, oeffnet :func:`open_copilot` Copilot ohne Datei.
    """
    teile: list[str] = []
    if prompt:
        teile.append("q=" + quote(prompt, safe=""))
    if file:
        teile.append("file=" + quote(file, safe=":\\/"))
    if not teile:
        return COPILOT_URI
    return "ms-copilot:chat?" + "&".join(teile)


def open_copilot(
    entry: dict[str, str] | None = None,
    prompt: str = "",
    file: str | None = None,
) -> bool:
    """Copilot oeffnen - unter Windows ueber das ms-copilot-Protokoll."""
    entry = entry or active_agent()
    if sys.platform.startswith("win"):
        if QDesktopServices.openUrl(QUrl(copilot_uri(prompt, file))):
            return True
        # Der Dateiparameter ist nicht dokumentiert: notfalls ohne ihn oeffnen.
        if (prompt or file) and QDesktopServices.openUrl(QUrl(COPILOT_URI)):
            return True
    if entry and entry.get("link"):
        return QDesktopServices.openUrl(QUrl(entry["link"]))
    return QDesktopServices.openUrl(QUrl(COPILOT_WEB))


class PreferencesDialog(QDialog):
    """Einstellungen mit dem Abschnitt PDFcompare."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        section = QLabel("PDFcompare")
        section.setObjectName("SectionLabel")
        layout.addWidget(section)

        self.linked = QCheckBox("Mit Windows Copilot verknüpfen")
        self.linked.setChecked(is_linked())
        layout.addWidget(self.linked)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.agent = QComboBox()
        self.agent.setMinimumWidth(200)
        self.add_button = QPushButton("Agent hinzufügen …")
        self.add_button.setObjectName("Ghost")
        self.remove_button = QPushButton("Entfernen")
        self.remove_button.setObjectName("Ghost")
        row.addWidget(QLabel("Agent"))
        row.addWidget(self.agent, 1)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        layout.addLayout(row)

        self.open_button = QPushButton("Copilot öffnen")
        layout.addWidget(self.open_button)

        hint = QLabel(HINT)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.button(QDialogButtonBox.Ok).setText("Speichern")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.add_button.clicked.connect(self._add_agent)
        self.remove_button.clicked.connect(self._remove_agent)
        self.open_button.clicked.connect(self._open_copilot)
        self.linked.toggled.connect(self._update_enabled)

        self._load_agents()
        self._update_enabled()

    # ------------------------------------------------------------------

    def _load_agents(self) -> None:
        self.agent.clear()
        for entry in agents():
            self.agent.addItem(entry["name"], entry)
        active = str(_settings().value(ACTIVE_KEY, "") or "")
        index = self.agent.findText(active)
        if index >= 0:
            self.agent.setCurrentIndex(index)

    def _add_agent(self) -> None:
        name, ok = QInputDialog.getText(self, "Agent", "Name des Agenten:")
        name = name.strip()
        if not ok or not name:
            return
        link, _ = QInputDialog.getText(
            self, "Agent", "Agent-Link (optional, aus Copilot „Teilen“):"
        )
        entries = agents()
        entries = [entry for entry in entries if entry["name"] != name]
        entries.append({"name": name, "link": link.strip()})
        save_agents(entries)
        self._load_agents()
        self.agent.setCurrentIndex(self.agent.findText(name))

    def _remove_agent(self) -> None:
        current = self.agent.currentText()
        if not current:
            return
        save_agents([entry for entry in agents() if entry["name"] != current])
        self._load_agents()

    def _open_copilot(self) -> None:
        entry = self.agent.currentData()
        open_copilot(entry if isinstance(entry, dict) else None)

    def _update_enabled(self) -> None:
        linked = self.linked.isChecked()
        for widget in (self.agent, self.add_button, self.remove_button):
            widget.setEnabled(linked)
        self.open_button.setEnabled(linked)

    def accept(self) -> None:
        settings = _settings()
        settings.setValue(LINKED_KEY, self.linked.isChecked())
        current = self.agent.currentText()
        settings.setValue(ACTIVE_KEY, current if self.linked.isChecked() else "")
        super().accept()
