"""Dunkles Farbschema fuer PDFblack."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#e5484d"

STYLESHEET = """
QMainWindow, QDialog { background: #14161b; }
QWidget { color: #e6e8ec; }
QWidget#Header { background: #171a20; border-bottom: 1px solid #23272f; }
QWidget#Toolbar { background: #14161b; border-bottom: 1px solid #23272f; }
QFrame#Sidebar { background: #131519; border-right: 1px solid #23272f; }
QFrame#Findings { background: #131519; border-left: 1px solid #23272f; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QFrame#Card { background: #191c23; border: 1px solid #262b34; border-radius: 10px; }
QLabel { background: transparent; }
QLabel#AppTitle { font-size: 16px; font-weight: 700; }
QLabel#AppSubtitle { color: #8b95a5; font-size: 11px; }
QLabel#SectionLabel {
    color: #7f8794; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QLabel#CardTitle { font-size: 13px; font-weight: 600; }
QLabel#Hint { color: #7f8794; font-size: 11px; }
QLabel#Danger { color: #ff8a8f; font-size: 11px; }
QLabel#Ok { color: #63d9a8; font-size: 11px; }
QLabel#VersionChip {
    color: #9aa3b2; background: #1d2027; border: 1px solid #2b313c;
    border-radius: 9px; padding: 2px 9px; font-size: 11px;
}
QPushButton {
    background: #23272f; border: 1px solid #303643; border-radius: 8px;
    padding: 8px 14px; font-weight: 500;
}
QPushButton:hover { background: #2b303a; border-color: #3a4150; }
QPushButton:pressed { background: #1d2028; }
QPushButton:disabled { color: #5b6472; background: #1a1d24; border-color: #242832; }
QPushButton#Primary {
    background: #e5484d; border: 1px solid #ef5c60; color: #ffffff; font-weight: 600;
}
QPushButton#Primary:hover { background: #ef5c60; }
QPushButton#Primary:pressed { background: #d13d42; }
QPushButton#Primary:disabled { background: #3a2327; border-color: #40282c; color: #7c5b5e; }
QPushButton#Ghost { background: transparent; border: 1px solid #2b313c; color: #9aa3b2; }
QPushButton#Ghost:hover { background: #1d2027; color: #e6e8ec; }
QToolButton {
    background: #1d2027; border: 1px solid #2b313c; border-radius: 7px;
    padding: 4px 9px; font-weight: 600;
}
QToolButton:hover { background: #262b34; }
QLineEdit, QPlainTextEdit, QComboBox {
    background: #10131a; border: 1px solid #2b313c; border-radius: 7px;
    padding: 6px 8px; selection-background-color: #e5484d;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #e5484d; }
QTextBrowser {
    background: #10131a; border: 1px solid #262b34; border-radius: 8px;
    padding: 8px;
}
QLineEdit:disabled, QPlainTextEdit:disabled { color: #5b6472; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #1b1e25; border: 1px solid #2b313c; selection-background-color: #e5484d;
}
QCheckBox { spacing: 8px; }
QTableWidget {
    background: #10131a; border: 1px solid #262b34; border-radius: 8px;
    gridline-color: #1d222b; selection-background-color: #262c36;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #191c23; color: #8b95a5; border: none;
    border-bottom: 1px solid #262b34; padding: 6px; font-size: 11px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #333a46; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #414a59; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #333a46; border-radius: 4px; min-width: 32px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: #23272f; width: 1px; }
QStatusBar { background: #10131a; color: #8b95a5; border-top: 1px solid #23272f; }
QStatusBar::item { border: none; }
QMenuBar { background: #171a20; border-bottom: 1px solid #23272f; }
QMenuBar::item { padding: 5px 10px; background: transparent; }
QMenuBar::item:selected { background: #262b34; border-radius: 5px; }
QMenu { background: #1b1e25; border: 1px solid #2b313c; padding: 5px; }
QMenu::item { padding: 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: #e5484d; color: #ffffff; }
QMenu::separator { height: 1px; background: #2b313c; margin: 5px 8px; }
QToolTip {
    background: #1b1e25; color: #e6e8ec; border: 1px solid #303643; padding: 4px;
}
QFrame#DropZone {
    background: #15181e; border: 2px dashed #303643; border-radius: 16px;
}
QFrame#DropZone[dragActive="true"] { border-color: #e5484d; background: #1c1a1e; }
QProgressBar {
    background: #1d2027; border: 1px solid #2b313c; border-radius: 6px;
    height: 8px; text-align: center;
}
QProgressBar::chunk { background: #e5484d; border-radius: 5px; }
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#14161b"))
    palette.setColor(QPalette.WindowText, QColor("#e6e8ec"))
    palette.setColor(QPalette.Base, QColor("#10131a"))
    palette.setColor(QPalette.AlternateBase, QColor("#161a21"))
    palette.setColor(QPalette.Text, QColor("#e6e8ec"))
    palette.setColor(QPalette.Button, QColor("#23272f"))
    palette.setColor(QPalette.ButtonText, QColor("#e6e8ec"))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1b1e25"))
    palette.setColor(QPalette.ToolTipText, QColor("#e6e8ec"))
    palette.setColor(QPalette.PlaceholderText, QColor("#68717f"))
    palette.setColor(QPalette.Link, QColor("#ff8a8f"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#5b6472"))
    app.setPalette(palette)

    font = QFont()
    font.setPointSizeF(9.8)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)
