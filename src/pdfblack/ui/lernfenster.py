"""Fenster mit den gelernten Beispielen: ansehen und einzeln loeschen.

Die Lerndatei sammelt Korrekturen aus der Trefferliste. Dieses Fenster zeigt
sie alle - Text, alte und neue Kategorie, Zeitpunkt - und laesst falsche
Regeln markieren und entfernen, ohne gleich die ganze Datei zu verwerfen.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import lerndatei, lernregeln
from ..core.models import Category

HINWEIS = (
    "Jede Zeile ist eine Korrektur aus der Trefferliste: Der Text wurde vorher "
    "als linke Kategorie gefunden und gehoert jetzt zur rechten; „kein Treffer“ "
    "heißt Fehlalarm. „im Code“ heißt: Das Beispiel ist schon als feste Regel "
    "im Programm (core/gelernt.py), die Lerndatei braucht es dafür nicht mehr. "
    "Markierte Zeilen lassen sich löschen – die übrigen Regeln bleiben bestehen."
)


def _zeit(wert: object) -> str:
    """ISO-Zeitstempel lesbar machen (``2026-11-17T14:17:57``)."""
    if not isinstance(wert, str) or not wert:
        return ""
    try:
        return datetime.fromisoformat(wert).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return wert


def _farbe(name: str) -> QColor:
    """Farbe der Kategorie, sonst neutral (z. B. für „kein Treffer“)."""
    for category in Category:
        if category.value == name:
            return QColor(category.color)
    return QColor(Category.OTHER.color)


def _tipp(eintrag: dict) -> str:
    """Tooltip eines Eintrags: Seite, Umgebung und urspruengliche Quelle."""
    zeilen = [f"Seite {eintrag.get('seite', '?')}"]
    vorher = str(eintrag.get("kontext_vorher") or "")
    nachher = str(eintrag.get("kontext_nachher") or "")
    if vorher or nachher:
        zeilen.append(f"… {vorher} [hier] {nachher} …".replace("  ", " ").strip())
    quelle = str(eintrag.get("quelle") or "")
    if quelle:
        zeilen.append(f"Quelle: {quelle}")
    return "\n".join(zeilen)


class Lernfenster(QDialog):
    """Alle Beispiele der Lerndatei; einzelne lassen sich loeschen."""

    COL_TEXT, COL_VORHER, COL_NACHHER, COL_ZEIT, COL_CODE = 0, 1, 2, 3, 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gelernte Beispiele")
        self.resize(780, 520)
        # Wie viele Beispiele in diesem Fenster geloescht wurden.
        self.geloescht = 0
        self.beispiele: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        titel = QLabel("Gelernte Beispiele")
        titel.setObjectName("AppTitle")
        layout.addWidget(titel)

        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Text", "vorher", "jetzt", "wann", "im Code"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        kopf = self.table.horizontalHeader()
        kopf.setSectionResizeMode(self.COL_TEXT, QHeaderView.Stretch)
        for spalte in (self.COL_VORHER, self.COL_NACHHER):
            kopf.setSectionResizeMode(spalte, QHeaderView.Fixed)
            self.table.setColumnWidth(spalte, 118)
        kopf.setSectionResizeMode(self.COL_ZEIT, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_ZEIT, 124)
        kopf.setSectionResizeMode(self.COL_CODE, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CODE, 68)
        layout.addWidget(self.table, 1)

        hinweis = QLabel(HINWEIS)
        hinweis.setObjectName("Hint")
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)

        unten = QHBoxLayout()
        unten.setSpacing(6)
        self.btn_delete = QPushButton("Ausgewählte löschen")
        self.btn_delete.setObjectName("Ghost")
        self.btn_delete.setEnabled(False)
        unten.addWidget(self.btn_delete)
        unten.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.button(QDialogButtonBox.Close).setText("Schließen")
        buttons.rejected.connect(self.reject)
        unten.addWidget(buttons)
        layout.addLayout(unten)

        self.btn_delete.clicked.connect(self.loeschen)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        self.laden()

    # ------------------------------------------------------------------

    def laden(self) -> None:
        """Die Beispiele aus der Lerndatei in die Tabelle holen."""
        self.beispiele = lerndatei.eintraege()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.beispiele))
        for zeile, eintrag in enumerate(self.beispiele):
            text = str(eintrag.get("text", ""))
            tipp = _tipp(eintrag)
            text_item = QTableWidgetItem(text)
            text_item.setToolTip(tipp)
            self.table.setItem(zeile, self.COL_TEXT, text_item)
            for spalte, schluessel in (
                (self.COL_VORHER, "kategorie_vorher"),
                (self.COL_NACHHER, "kategorie_nachher"),
            ):
                name = str(eintrag.get(schluessel, ""))
                item = QTableWidgetItem(name)
                item.setForeground(_farbe(name))
                item.setToolTip(tipp)
                self.table.setItem(zeile, spalte, item)
            zeit = QTableWidgetItem(_zeit(eintrag.get("zeit")))
            zeit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            zeit.setToolTip(tipp)
            self.table.setItem(zeile, self.COL_ZEIT, zeit)
            fest = lernregeln.abgedeckt(eintrag)
            code = QTableWidgetItem("✓" if fest else "–")
            code.setTextAlignment(Qt.AlignCenter)
            code.setToolTip(
                "Bereits feste Regel im Programm (core/gelernt.py)"
                if fest
                else "Noch offen: wirkt nur über die Lerndatei"
            )
            self.table.setItem(zeile, self.COL_CODE, code)
        self.table.blockSignals(False)

        fehlalarme = sum(
            1
            for eintrag in self.beispiele
            if eintrag.get("kategorie_nachher") == lerndatei.KEIN_TREFFER
        )
        fest = sum(1 for eintrag in self.beispiele if lernregeln.abgedeckt(eintrag))
        if self.beispiele:
            self.summary.setText(
                f"{len(self.beispiele)} Beispiele · {fehlalarme} Fehlalarme · "
                f"{fest} fest im Programm"
            )
        else:
            self.summary.setText(
                "Noch keine gelernten Beispiele – Rechtsklick auf einen Treffer "
                "ordnet ihn einer Kategorie zu."
            )
        self._update_buttons()

    def _auswahl(self) -> list[int]:
        """Zeilen der markierten Beispiele."""
        return sorted(
            {index.row() for index in self.table.selectionModel().selectedRows()}
        )

    def _update_buttons(self) -> None:
        self.btn_delete.setEnabled(bool(self._auswahl()))

    def loeschen(self) -> int:
        """Markierte Beispiele entfernen; liefert deren Anzahl."""
        zeilen = self._auswahl()
        if not zeilen:
            return 0
        try:
            anzahl = lerndatei.loeschen(zeilen)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Lerndatei",
                f"Die Beispiele konnten nicht gelöscht werden:\n{exc}",
            )
            return 0
        self.geloescht += anzahl
        self.laden()
        return anzahl


__all__ = ["Lernfenster"]
