"""Prüffenster: lokale Befunde, Frage an Copilot, Antwort aus der Zwischenablage.

Copilot hat für fremde Programme keinen Rückkanal. Deshalb: Prüfung lokal,
Frage in die Zwischenablage, Antwort zurückschneiden und einlesen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import review as review_core
from . import preferences


class ReviewDialog(QDialog):
    """Befunde zeigen und die Antwort von Copilot einsammeln."""

    def __init__(self, life: list[str], certs: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Prüfung")
        self.resize(800, 860)

        self.life = list(life)
        self.certs = list(certs)
        self.report = review_core.review(self.life, self.certs)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        titel = QLabel("Prüfung")
        titel.setObjectName("AppTitle")
        layout.addWidget(titel)

        zusammenfassung = QLabel(self.report.summary())
        zusammenfassung.setObjectName("Hint")
        layout.addWidget(zusammenfassung)

        self.findings = QPlainTextEdit(self.report.as_text())
        self.findings.setReadOnly(True)
        self.findings.setFocusPolicy(Qt.NoFocus)
        self.findings.setMinimumHeight(140)
        layout.addWidget(self.findings, 1)

        hinweis = QLabel(
            "Die Befunde oben sind ausgerechnet, ohne KI. Copilot sieht die "
            "Dateien nicht von selbst: Frage kopieren, in Copilot einsetzen, "
            "Antwort zurückkopieren. Die Frage darunter lässt sich vorher "
            "ändern – kopiert wird, was dort steht."
        )
        hinweis.setObjectName("Hint")
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)

        frage_titel = QLabel("Frage an Copilot (änderbar)")
        frage_titel.setObjectName("SectionLabel")
        layout.addWidget(frage_titel)

        self.question = QPlainTextEdit(self.prompt())
        self.question.setPlaceholderText("Frage an Copilot …")
        self.question.setMinimumHeight(150)
        layout.addWidget(self.question, 1)

        fragen = QHBoxLayout()
        fragen.setSpacing(8)
        self.ask_button = QPushButton("Frage kopieren und Copilot öffnen")
        self.ask_button.setObjectName("Agent")
        self.paste_button = QPushButton("Antwort aus Zwischenablage")
        self.paste_button.setObjectName("Ghost")
        fragen.addWidget(self.ask_button)
        fragen.addWidget(self.paste_button, 1)
        layout.addLayout(fragen)

        antwort_titel = QLabel("Antwort aus Copilot")
        antwort_titel.setObjectName("SectionLabel")
        layout.addWidget(antwort_titel)

        self.answer = QPlainTextEdit()
        self.answer.setPlaceholderText(
            "Antwort von Copilot hier einfügen (das JSON genügt) …"
        )
        self.answer.setMinimumHeight(110)
        layout.addWidget(self.answer, 1)

        self.evaluate_button = QPushButton("Antwort auswerten")
        self.evaluate_button.setObjectName("Ghost")
        layout.addWidget(self.evaluate_button, 0)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setFocusPolicy(Qt.NoFocus)
        self.result.setMinimumHeight(120)
        self.result.setPlaceholderText("Auswertung erscheint hier.")
        layout.addWidget(self.result, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.button(QDialogButtonBox.Close).setText("Schließen")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.ask_button.clicked.connect(self._ask)
        self.paste_button.clicked.connect(self._paste)
        self.evaluate_button.clicked.connect(self._evaluate)
        self.answer.setFocus()

    # ------------------------------------------------------------------

    def prompt(self) -> str:
        return review_core.build_prompt(self.report, self.life, self.certs)

    def _ask(self) -> None:
        frage = self.question.toPlainText().strip()
        if not frage:
            self.findings.appendPlainText(
                "→ Die Frage ist leer – bitte zuerst einen Text eingeben."
            )
            return
        QApplication.clipboard().setText(frage)
        geoeffnet = preferences.open_copilot(prompt=frage)
        if geoeffnet:
            self.findings.appendPlainText(
                "→ Frage kopiert, Copilot geöffnet. Antwort danach unten einsetzen."
            )
        else:
            self.findings.appendPlainText(
                "→ Frage liegt in der Zwischenablage; Copilot liess sich nicht öffnen."
            )

    def _paste(self) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            self.result.setPlainText("Die Zwischenablage ist leer.")
            return
        self.answer.setPlainText(text)
        self._evaluate()

    def _evaluate(self) -> None:
        daten = review_core.parse_answer(self.answer.toPlainText())
        if daten is None:
            self.result.setPlainText(
                "Kein JSON gefunden. Bitte die ganze Antwort aus Copilot einsetzen – "
                "oder Copilot nochmal mit der kopierten Frage bitten, nur das JSON "
                "zu liefern."
            )
            return
        self.result.setPlainText("\n".join(review_core.answer_lines(daten)))
