"""Doppelklick im PDF meldet das Wort unter dem Cursor zum Schwaerzen."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf
import pytest

try:  # Qt braucht je nach System zusaetzliche Bibliotheken
    from PySide6 import QtCore, QtTest, QtWidgets
except Exception as exc:  # noqa: BLE001 - ohne Qt wird der Test uebersprungen
    pytest.skip(f"Qt nicht verfuegbar: {exc}", allow_module_level=True)


@pytest.fixture(scope="module")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        try:
            app = QtWidgets.QApplication([])
        except Exception as exc:  # noqa: BLE001 - Qt fehlt im System
            pytest.skip(f"Qt startet hier nicht: {exc}")
    return app


def _word_pdf(path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((60, 100), "Musterkasse", fontsize=14)
    doc.save(str(path))
    doc.close()


def test_doppelklick_meldet_das_wort(qt_app, tmp_path):
    pdf = tmp_path / "wort.pdf"
    _word_pdf(pdf)

    from pdfblack.ui.canvas import PdfCanvas

    canvas = PdfCanvas()
    canvas.resize(420, 420)
    canvas.load(str(pdf))

    gemeldet: list[tuple] = []
    canvas.wordActivated.connect(lambda *args: gemeldet.append(args))

    doc = pymupdf.open(str(pdf))
    word = next(w for w in doc[0].get_text("words") if w[4] == "Musterkasse")
    origin = canvas._page_pos[0]
    point = QtCore.QPointF(
        origin.x() + (word[0] + word[2]) / 2 * canvas.zoom,
        origin.y() + (word[1] + word[3]) / 2 * canvas.zoom,
    )

    QtTest.QTest.mouseDClick(
        canvas, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point.toPoint()
    )

    assert gemeldet, "Doppelklick hat kein Wort gemeldet"
    page, text, x0, y0, x1, y1 = gemeldet[0]
    assert page == 0
    assert text == "Musterkasse"
    assert all(
        abs(gemeldet_wert - erwartet) < 0.01
        for gemeldet_wert, erwartet in zip((x0, y0, x1, y1), word[:4])
    )
    doc.close()
