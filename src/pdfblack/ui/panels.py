"""Seitenleisten: Eingabefelder, Erkennungsoptionen, Trefferliste, Drop-Zone."""

from __future__ import annotations

import re

from PySide6.QtCore import QCoreApplication, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.detect import DetectionOptions, ManualTerm, RegexSpec, compile_regexes
from ..core.models import Category, Finding

# Ueberschriften der Kategorie-Gruppen in der Trefferspalte.
CATEGORY_GROUPS: dict[Category, str] = {
    Category.PERSON: "Personen",
    Category.ADDRESS: "Adressen",
    Category.COMPANY: "Firmen",
    Category.POSTAL: "PLZ / Ort",
    Category.ID: "Nummern / IDs",
    Category.CONTACT: "Kontakt",
    Category.BANK: "Bank / Karte",
    Category.DATE: "Datum",
    Category.REGEX: "Eigene Regex",
    Category.MANUAL: "Manuelle Bereiche",
    Category.OTHER: "Sonstiges",
}

SENSITIVITY = (
    ("Streng (weniger Treffer)", 0.65),
    ("Ausgewogen", 0.45),
    ("Empfindlich (mehr Treffer)", 0.28),
)


def _settings() -> QSettings:
    """Einstellungen der Anwendung, auch ohne gesetzten Anwendungsnamen."""
    if QCoreApplication.applicationName() and QCoreApplication.organizationName():
        return QSettings()
    return QSettings("PDFblack", "PDFblack")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionLabel")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def _line(placeholder: str) -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setClearButtonEnabled(True)
    return edit


def _card(title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(13, 11, 13, 12)
    layout.setSpacing(8)
    heading = QLabel(title)
    heading.setObjectName("CardTitle")
    layout.addWidget(heading)
    if description:
        layout.addWidget(_hint(description))
    return frame, layout


# ---------------------------------------------------------------------------
# Leerzustand / Drag-and-Drop
# ---------------------------------------------------------------------------


class DropZone(QWidget):
    """Grosse Ablageflaeche, solange keine Datei geladen ist."""

    fileDropped = Signal(str)
    browseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._active = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setAlignment(Qt.AlignCenter)

        self.frame = QFrame()
        self.frame.setObjectName("DropZone")
        self.frame.setProperty("dragActive", False)
        self.frame.setFixedSize(QSize(560, 340))
        outer.addWidget(self.frame)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(9)

        glyph = QLabel("\u2b07")
        glyph.setStyleSheet("font-size: 46px; color: #4a5361;")
        glyph.setAlignment(Qt.AlignCenter)

        title = QLabel("PDF-Datei hierher ziehen")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("oder")
        subtitle.setObjectName("Hint")
        subtitle.setAlignment(Qt.AlignCenter)

        button = QPushButton("PDF öffnen …")
        button.setObjectName("Primary")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedWidth(160)
        button.clicked.connect(self.browseRequested.emit)

        layout.addStretch(1)
        layout.addWidget(glyph)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        layout.addStretch(1)

        note = QLabel(
            "Die Datei bleibt unverändert – geschwärzt wird erst in der "
            "geschwärzten Kopie."
        )
        note.setObjectName("Hint")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        layout.addWidget(note)

    def _accepts(self, event) -> bool:
        return event.mimeData().hasUrls() and any(
            url.toLocalFile().lower().endswith(".pdf") for url in event.mimeData().urls()
        )

    def _set_active(self, active: bool) -> None:
        self._active = active
        self.frame.setProperty("dragActive", active)
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._accepts(event):
            self._set_active(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_active(False)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.fileDropped.emit(path)
                break


# ---------------------------------------------------------------------------
# Linke Seite: Eingaben und Optionen
# ---------------------------------------------------------------------------


class ControlsPanel(QScrollArea):
    """Alle Eingabefelder fuer den zweiten Durchlauf und die Erkennung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("Sidebar")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 16)
        layout.setSpacing(10)

        # --- manuelle Werte -------------------------------------------
        card, card_layout = _card(
            "Werte, die die KI nicht erkennt",
            "Diese Angaben werden nach der automatischen Suche zusätzlich "
            "gesucht (zweiter Durchlauf) und geschwärzt.",
        )
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setSpacing(6)
        form.setContentsMargins(0, 0, 0, 0)

        self.edit_first = _line("Maximiliane")
        self.edit_last = _line("Schmidt-Lorenz")
        self.edit_street = _line("Königsallee 42 a")
        self.edit_zip = _line("80331")
        self.edit_city = _line("München")
        self.edit_id = _line("PE-8842/2024")
        for label, widget in (
            ("Vorname", self.edit_first),
            ("Nachname", self.edit_last),
            ("Adresse", self.edit_street),
            ("PLZ", self.edit_zip),
            ("Ort", self.edit_city),
            ("Personennummer", self.edit_id),
        ):
            form.addRow(label, widget)

        self.edit_more = QPlainTextEdit()
        self.edit_more.setPlaceholderText("Weitere Begriffe – eine Zeile pro Begriff")
        self.edit_more.setFixedHeight(56)
        form.addRow("Weitere", self.edit_more)
        card_layout.addLayout(form)

        clear_button = QPushButton("Felder leeren")
        clear_button.setObjectName("Ghost")
        clear_button.setCursor(Qt.PointingHandCursor)
        clear_button.clicked.connect(self.clear_fields)
        card_layout.addWidget(clear_button, alignment=Qt.AlignRight)
        layout.addWidget(card)

        # --- Regex ----------------------------------------------------
        card, card_layout = _card(
            "Eigene Regex-Ausdrücke",
            "Ein Ausdruck pro Zeile. Optional mit Namen: Aktenzeichen = "
            "\\d{2}-\\d{4}. ^ und $ gelten pro Zeile, \\b für Wortgrenzen."
        )
        self.regex_edit = QPlainTextEdit()
        self.regex_edit.setPlaceholderText("z. B. \\b[A-Z]{2}-\\d{4}/\\d{4}\\b")
        self.regex_edit.setFixedHeight(74)
        self.regex_edit.textChanged.connect(self._validate_regex)
        card_layout.addWidget(self.regex_edit)

        self.regex_ignore_case = QCheckBox("Groß-/Kleinschreibung ignorieren")
        self.regex_ignore_case.setChecked(True)
        self.regex_ignore_case.toggled.connect(self._validate_regex)
        card_layout.addWidget(self.regex_ignore_case)

        self.regex_status = QLabel("")
        self.regex_status.setObjectName("Hint")
        self.regex_status.setWordWrap(True)
        card_layout.addWidget(self.regex_status)
        layout.addWidget(card)

        # --- Erkennung ------------------------------------------------
        card, card_layout = _card(
            "Automatische Erkennung",
            "Erster Durchlauf mit KI und deutschen Mustern.",
        )
        self.ai_check = QCheckBox("KI-Erkennung (Presidio) verwenden")
        self.ai_check.setChecked(True)
        self.ai_check.toggled.connect(self._sync_ai_state)
        card_layout.addWidget(self.ai_check)

        self.cb_person = QCheckBox("Personen (Namen, Vornamen)")
        self.cb_person.setChecked(True)
        self.cb_location = QCheckBox("Orte (Städte, Länder)")
        self.cb_location.setChecked(True)
        self.cb_address = QCheckBox("Adressen (Straße, Hausnummer, PLZ + Ort)")
        self.cb_address.setChecked(True)
        self.cb_ch = QCheckBox("Schweizer PLZ (CH-8045, 8045 Zürich)")
        self.cb_ch.setChecked(True)
        self.cb_ids = QCheckBox("Nummern & IDs (Personalnummer, Ausweis …)")
        self.cb_ids.setChecked(True)
        self.cb_contact = QCheckBox("Kontakt (E-Mail, Telefon)")
        self.cb_contact.setChecked(True)
        self.cb_bank = QCheckBox("Bankdaten (IBAN)")
        self.cb_bank.setChecked(True)
        self.cb_date = QCheckBox("Datum (Geburts-, Rechnungs-, Ablaufdatum)")
        self.cb_date.setChecked(False)
        for box in (
            self.cb_person,
            self.cb_location,
            self.cb_address,
            self.cb_ch,
            self.cb_ids,
            self.cb_contact,
            self.cb_bank,
            self.cb_date,
        ):
            card_layout.addWidget(box)

        sensitivity_row = QHBoxLayout()
        sensitivity_row.setSpacing(8)
        sensitivity_label = QLabel("Empfindlichkeit")
        sensitivity_label.setObjectName("Hint")
        self.sensitivity = QComboBox()
        for text, value in SENSITIVITY:
            self.sensitivity.addItem(text, value)
        self.sensitivity.setCurrentIndex(1)
        sensitivity_row.addWidget(sensitivity_label)
        sensitivity_row.addWidget(self.sensitivity, 1)
        card_layout.addLayout(sensitivity_row)

        self.ai_status = QLabel("")
        self.ai_status.setObjectName("Hint")
        self.ai_status.setWordWrap(True)
        card_layout.addWidget(self.ai_status)
        layout.addWidget(card)

        layout.addWidget(
            _hint(
                "Tipp: Nach der Vorschau können Sie einzelne Markierungen per Klick "
                "abwählen oder mit gedrückter Maustaste weitere Bereiche aufziehen."
            )
        )
        layout.addStretch(1)
        self.setWidget(body)
        self._restore_auto_settings()
        for box in self._auto_boxes().values():
            box.toggled.connect(self._save_auto_settings)
        self.sensitivity.currentIndexChanged.connect(self._save_auto_settings)
        self._sync_ai_state()

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Einstellungen der automatischen Erkennung merken

    def _auto_boxes(self) -> dict[str, QCheckBox]:
        return {
            "ki": self.ai_check,
            "personen": self.cb_person,
            "orte": self.cb_location,
            "adressen": self.cb_address,
            "schweizer_plz": self.cb_ch,
            "nummern": self.cb_ids,
            "kontakt": self.cb_contact,
            "bank": self.cb_bank,
            "datum": self.cb_date,
        }

    def _restore_auto_settings(self) -> None:
        """Beim Start die zuletzt gewaehlten Optionen setzen."""
        settings = _settings()
        for key, box in self._auto_boxes().items():
            stored = settings.value(f"erkennung/{key}")
            if stored is not None:
                box.setChecked(_as_bool(stored))
        stored = settings.value("erkennung/empfindlichkeit")
        if stored is not None:
            try:
                self.sensitivity.setCurrentIndex(int(stored))
            except (TypeError, ValueError):
                pass

    def _save_auto_settings(self) -> None:
        settings = _settings()
        for key, box in self._auto_boxes().items():
            settings.setValue(f"erkennung/{key}", box.isChecked())
        settings.setValue("erkennung/empfindlichkeit", self.sensitivity.currentIndex())

    # ------------------------------------------------------------------

    def _sync_ai_state(self) -> None:
        enabled = self.ai_check.isChecked()
        for box in (
            self.cb_person,
            self.cb_location,
            self.cb_contact,
            self.cb_bank,
            self.cb_date,
        ):
            box.setEnabled(enabled)
        self.ai_status.setText(
            "" if enabled else "Nur Muster, eigene Werte und Regex werden verwendet."
        )

    def set_ai_hint(self, text: str) -> None:
        self.ai_status.setText(text)

    def clear_fields(self) -> None:
        for widget in (
            self.edit_first,
            self.edit_last,
            self.edit_street,
            self.edit_zip,
            self.edit_city,
            self.edit_id,
        ):
            widget.clear()
        self.edit_more.clear()

    # ------------------------------------------------------------------

    def _parse_regex_lines(self) -> tuple[RegexSpec, ...]:
        specs: list[RegexSpec] = []
        for raw in self.regex_edit.toPlainText().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name = ""
            match = re.match(r"^([A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df0-9 _-]{1,30})\s*=\s*(.+)$", line)
            if match:
                name = match.group(1).strip()
                pattern = match.group(2).strip()
            else:
                pattern = line
            specs.append(RegexSpec(name=name or f"Muster {len(specs) + 1}", pattern=pattern))
        return tuple(specs)

    def _validate_regex(self) -> None:
        specs = self._parse_regex_lines()
        if not specs:
            self.regex_status.setObjectName("Hint")
            self.regex_status.setText("")
            self._restyle(self.regex_status)
            return
        try:
            compile_regexes(specs, self.regex_ignore_case.isChecked())
        except ValueError as exc:
            self.regex_status.setObjectName("Danger")
            self.regex_status.setText(str(exc))
        else:
            self.regex_status.setObjectName("Ok")
            self.regex_status.setText(f"{len(specs)} Ausdruck/Ausdrücke bereit.")
        self._restyle(self.regex_status)

    @staticmethod
    def _restyle(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def focus_regex(self) -> None:
        self.regex_edit.setFocus()

    # ------------------------------------------------------------------

    def manual_terms(self) -> tuple[ManualTerm, ...]:
        terms: list[ManualTerm] = []
        entries = (
            ("Vorname", self.edit_first, Category.PERSON),
            ("Nachname", self.edit_last, Category.PERSON),
            ("Adresse", self.edit_street, Category.ADDRESS),
            ("PLZ", self.edit_zip, Category.POSTAL),
            ("Ort", self.edit_city, Category.POSTAL),
            ("Personennummer", self.edit_id, Category.ID),
        )
        for label, widget, category in entries:
            value = widget.text().strip()
            if value:
                terms.append(ManualTerm(label=label, value=value, category=category))
        for line in self.edit_more.toPlainText().splitlines():
            value = line.strip()
            if value:
                terms.append(
                    ManualTerm(label="Weitere Angabe", value=value, category=Category.MANUAL)
                )
        return tuple(terms)

    def read_options(self) -> DetectionOptions:
        """Eingaben einsammeln. Wirft ValueError bei ungueltigem Regex."""
        specs = self._parse_regex_lines()
        compile_regexes(specs, self.regex_ignore_case.isChecked())

        use_ai = self.ai_check.isChecked()
        ai_entities: list[str] = []
        if use_ai:
            if self.cb_person.isChecked():
                ai_entities.append("PERSON")
            if self.cb_location.isChecked():
                ai_entities.append("LOCATION")
            if self.cb_contact.isChecked():
                ai_entities.extend(["EMAIL_ADDRESS", "PHONE_NUMBER"])
            if self.cb_bank.isChecked():
                ai_entities.extend(["IBAN_CODE", "CREDIT_CARD"])
            if self.cb_date.isChecked():
                ai_entities.append("DATE_TIME")

        groups: list[str] = []
        if self.cb_address.isChecked():
            groups.append("address")
        if self.cb_ch.isChecked():
            groups.append("ch_postal")
        if self.cb_ids.isChecked():
            groups.append("id")
        if self.cb_contact.isChecked():
            groups.append("contact")
        if self.cb_bank.isChecked():
            groups.append("bank")
        if self.cb_date.isChecked():
            groups.append("date")

        return DetectionOptions(
            use_ai=use_ai and bool(ai_entities),
            ai_entities=tuple(ai_entities),
            rule_groups=tuple(groups),
            threshold=float(self.sensitivity.currentData() or 0.45),
            manual_terms=self.manual_terms(),
            regexes=specs,
            regex_ignore_case=self.regex_ignore_case.isChecked(),
        )


# ---------------------------------------------------------------------------
# Rechte Seite: Trefferliste
# ---------------------------------------------------------------------------


class FindingsPanel(QFrame):
    """Liste aller gefundenen Stellen mit Schalter pro Treffer."""

    enabledChanged = Signal(int, bool)
    findingSelected = Signal(int)
    selectAllRequested = Signal(bool)
    removeRequested = Signal()

    COL_CHECK, COL_CATEGORY, COL_TEXT, COL_PAGE = 0, 1, 2, 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Findings")
        self.setMinimumWidth(280)
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = _section("Treffer")
        self.count_label = QLabel("0 aktiv")
        self.count_label.setObjectName("Hint")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.count_label)
        layout.addLayout(header)

        self.stack = QStackedWidget()
        empty = QLabel(
            "Noch keine Vorschau.\n\nDatei laden – die Prüfung startet dann "
            "von selbst."
        )
        empty.setObjectName("Hint")
        empty.setAlignment(Qt.AlignCenter)
        empty.setWordWrap(True)
        self.stack.addWidget(empty)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Kategorie", "Text", "S."])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        header_view.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.Fixed)
        header_view.setSectionResizeMode(self.COL_TEXT, QHeaderView.Stretch)
        header_view.setSectionResizeMode(self.COL_PAGE, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 26)
        self.table.setColumnWidth(self.COL_CATEGORY, 106)
        self.table.setColumnWidth(self.COL_PAGE, 34)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.btn_all = QPushButton("Alle an")
        self.btn_none = QPushButton("Alle aus")
        self.btn_remove = QPushButton("Entfernen")
        for button in (self.btn_all, self.btn_none, self.btn_remove):
            button.setObjectName("Ghost")
            button.setCursor(Qt.PointingHandCursor)
            button.setEnabled(False)
        self.btn_all.clicked.connect(lambda: self.selectAllRequested.emit(True))
        self.btn_none.clicked.connect(lambda: self.selectAllRequested.emit(False))
        self.btn_remove.clicked.connect(self.removeRequested.emit)
        buttons.addWidget(self.btn_all)
        buttons.addWidget(self.btn_none)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_remove)
        layout.addLayout(buttons)

        layout.addWidget(
            _hint("Klick auf eine Zeile springt zur Stelle. Häkchen entfernen = nicht schwärzen.")
        )

        # --- zweiter Abschnitt: dieselben Treffer nach Kategorie --------
        self.group_label = _section("Nach Kategorie")
        self.group_label.setVisible(False)
        layout.addWidget(self.group_label)

        self.group_hint = _hint(
            "Häkchen vor einer Überschrift schaltet die ganze Gruppe ein oder aus."
        )
        self.group_hint.setVisible(False)
        layout.addWidget(self.group_hint)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setIndentation(14)
        self.category_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.category_tree.setMinimumHeight(120)
        self.category_tree.setVisible(False)
        self.category_tree.itemChanged.connect(self._on_group_changed)
        self.category_tree.itemClicked.connect(self._on_group_clicked)
        self.category_tree.itemDoubleClicked.connect(self._on_group_double_clicked)
        layout.addWidget(self.category_tree, 1)

    # ------------------------------------------------------------------

    def set_findings(self, findings: list[Finding]) -> None:
        self._updating = True
        self.table.blockSignals(True)
        self.table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            check.setCheckState(Qt.Checked if finding.enabled else Qt.Unchecked)
            check.setData(Qt.UserRole, finding.uid)
            self.table.setItem(row, self.COL_CHECK, check)

            category = QTableWidgetItem(finding.category.value)
            category.setForeground(QColor(finding.category.color))
            category.setData(Qt.UserRole, finding.uid)
            category.setToolTip(f"{finding.source} · Seite {finding.page_label}")
            self.table.setItem(row, self.COL_CATEGORY, category)

            text = QTableWidgetItem(finding.display_text)
            text.setToolTip(f"{finding.display_text}\n\nQuelle: {finding.source}")
            text.setData(Qt.UserRole, finding.uid)
            self.table.setItem(row, self.COL_TEXT, text)

            page = QTableWidgetItem(finding.page_label)
            page.setTextAlignment(Qt.AlignCenter)
            page.setData(Qt.UserRole, finding.uid)
            self.table.setItem(row, self.COL_PAGE, page)

        self.table.blockSignals(False)
        self._updating = False
        self.stack.setCurrentIndex(1 if findings else 0)
        for button in (self.btn_all, self.btn_none, self.btn_remove):
            button.setEnabled(bool(findings))
        self._build_group_tree(findings)
        self.update_counts(findings)

    # ------------------------------------------------------------------
    # Treffer nach Kategorie

    def _build_group_tree(self, findings: list[Finding]) -> None:
        self._updating = True
        self.category_tree.blockSignals(True)
        self.category_tree.clear()

        groups: dict[Category, list[Finding]] = {}
        for finding in findings:
            groups.setdefault(finding.category, []).append(finding)

        for category, items in groups.items():
            top = QTreeWidgetItem(
                [f"{CATEGORY_GROUPS.get(category, category.value)} ({len(items)})"]
            )
            # Kein ItemIsAutoTristate: Qt wuerde beim Umschalten eines einzelnen
            # Eintrags den Gruppenhaken nachziehen und unser itemChanged fuer den
            # Kopf wieder alle Kinder ueberschreiben. Der Zustand wird deshalb
            # selbst aus den Kindern berechnet.
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable)
            top.setForeground(0, QColor(category.color))
            self.category_tree.addTopLevelItem(top)
            for finding in items:
                child = QTreeWidgetItem([finding.display_text])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setData(0, Qt.UserRole, finding.uid)
                child.setToolTip(
                    0, f"{finding.source} · Seite {finding.page_label}"
                )
                child.setCheckState(0, Qt.Checked if finding.enabled else Qt.Unchecked)
                top.addChild(child)
            top.setExpanded(True)
            self._apply_group_state(top)

        self.category_tree.blockSignals(False)
        self._updating = False
        self.category_tree.setVisible(bool(findings))
        self.group_label.setVisible(bool(findings))
        self.group_hint.setVisible(bool(findings))

    @staticmethod
    def _apply_group_state(top: QTreeWidgetItem) -> None:
        """Gruppenhaken aus den Kindern ableiten (Signale sperrt der Aufrufer)."""
        total = top.childCount()
        if not total:
            return
        checked = sum(
            1 for index in range(total) if top.child(index).checkState(0) == Qt.Checked
        )
        if checked == 0:
            state = Qt.Unchecked
        elif checked == total:
            state = Qt.Checked
        else:
            state = Qt.PartiallyChecked
        if top.checkState(0) != state:
            top.setCheckState(0, state)

    def _sync_group_state(self, top: QTreeWidgetItem) -> None:
        self.category_tree.blockSignals(True)
        self._apply_group_state(top)
        self.category_tree.blockSignals(False)

    def update_counts(self, findings: list[Finding]) -> None:
        active = sum(1 for finding in findings if finding.enabled)
        self.count_label.setText(f"{len(findings)} Treffer · {active} aktiv")

    def set_enabled_state(self, uid: int, enabled: bool) -> None:
        self._updating = True
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item is not None and item.data(Qt.UserRole) == uid:
                item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
                break
        self.table.blockSignals(False)
        self.category_tree.blockSignals(True)
        for index in range(self.category_tree.topLevelItemCount()):
            top = self.category_tree.topLevelItem(index)
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child.data(0, Qt.UserRole) == uid:
                    child.setCheckState(0, Qt.Checked if enabled else Qt.Unchecked)
                    break
            self._apply_group_state(top)
        self.category_tree.blockSignals(False)
        self._updating = False

    def selected_uids(self) -> list[int]:
        uids: list[int] = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), self.COL_CHECK)
            if item is not None:
                uid = item.data(Qt.UserRole)
                if isinstance(uid, int):
                    uids.append(uid)
        return uids

    def clear_selection(self) -> None:
        self.table.clearSelection()

    def select_uid(self, uid: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item is not None and item.data(Qt.UserRole) == uid:
                self.table.selectRow(row)
                return

    # ------------------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != self.COL_CHECK:
            return
        uid = item.data(Qt.UserRole)
        if isinstance(uid, int):
            self.enabledChanged.emit(uid, item.checkState() == Qt.Checked)

    def _on_group_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating:
            return
        uid = item.data(0, Qt.UserRole)
        if not isinstance(uid, int):
            # Gruppenkopf: alle Kinder mit umschalten (nicht darauf verlassen,
            # dass Qt das bei automatischem Tristate selbst tut).
            enabled = item.checkState(0) != Qt.Unchecked
            self._updating = True
            self.category_tree.blockSignals(True)
            for index in range(item.childCount()):
                item.child(index).setCheckState(
                    0, Qt.Checked if enabled else Qt.Unchecked
                )
            self.category_tree.blockSignals(False)
            self._updating = False
            for index in range(item.childCount()):
                child_uid = item.child(index).data(0, Qt.UserRole)
                if isinstance(child_uid, int):
                    self.enabledChanged.emit(child_uid, enabled)
            return
        self.enabledChanged.emit(uid, item.checkState(0) == Qt.Checked)
        parent = item.parent()
        if parent is not None:
            self._sync_group_state(parent)

    def _on_group_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        uid = item.data(0, Qt.UserRole)
        if isinstance(uid, int):
            self.findingSelected.emit(uid)

    def _on_group_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        uid = item.data(0, Qt.UserRole)
        if not isinstance(uid, int):
            return
        checked = item.checkState(0) == Qt.Checked
        item.setCheckState(0, Qt.Unchecked if checked else Qt.Checked)

    def _on_selection_changed(self) -> None:
        uids = self.selected_uids()
        if uids:
            self.findingSelected.emit(uids[0])

    def _on_double_clicked(self, item: QTableWidgetItem) -> None:
        check = self.table.item(item.row(), self.COL_CHECK)
        if check is None:
            return
        checked = check.checkState() == Qt.Checked
        check.setCheckState(Qt.Unchecked if checked else Qt.Checked)
