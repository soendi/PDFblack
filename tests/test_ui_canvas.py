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


def _treffer(uid: int, text: str, seite: int = 0, enabled: bool = True):
    from pdfblack.core.models import Category, Finding

    return Finding(
        text=text,
        category=Category.PERSON,
        page=seite,
        rects=[(10.0, 10.0, 40.0, 20.0)],
        enabled=enabled,
        uid=uid,
    )


def _haken(panel, row: int):
    return panel.table.item(row, panel.COL_CHECK).checkState()


def test_alle_gleichnamigen_treffer_umschalten(qt_app):
    """Rechte Maustaste: ein Name schaltet alle seine Treffer zusammen."""
    from PySide6.QtCore import Qt

    from pdfblack.ui.panels import FindingsPanel

    panel = FindingsPanel()
    panel.set_findings(
        [
            _treffer(1, "Meier"),
            _treffer(2, "Schmidt"),
            _treffer(3, "Meier", seite=1),
            _treffer(4, "Meier GmbH"),
        ]
    )
    assert panel.same_text_uids("Meier") == [1, 3]

    gemeldet: list[tuple[int, bool]] = []
    panel.enabledChanged.connect(lambda uid, enabled: gemeldet.append((uid, enabled)))

    # Angehakt -> alle "Meier" gehen aus, die anderen bleiben unberuehrt.
    assert panel.toggle_same_text(0) == 2
    assert gemeldet == [(1, False), (3, False)]
    assert _haken(panel, 0) == Qt.Unchecked
    assert _haken(panel, 2) == Qt.Unchecked
    assert _haken(panel, 1) == Qt.Checked
    assert _haken(panel, 3) == Qt.Checked

    # Nochmal: jetzt gehen alle "Meier" wieder an.
    gemeldet.clear()
    assert panel.toggle_same_text(2) == 2
    assert gemeldet == [(1, True), (3, True)]
    assert _haken(panel, 0) == Qt.Checked
    assert _haken(panel, 2) == Qt.Checked

    # Ein anderer Name zaehlt nicht mit ("Meier GmbH" ist nicht "Meier").
    gemeldet.clear()
    assert panel.toggle_same_text(3) == 1
    assert gemeldet == [(4, False)]
    assert _haken(panel, 1) == Qt.Checked

    panel.deleteLater()
    qt_app.processEvents()


def test_umschalten_geht_vom_zustand_der_angeklickten_zeile_aus(qt_app):
    """Gemischt: die angeklickte Zeile entscheidet, wohin alle gehen."""
    from PySide6.QtCore import Qt

    from pdfblack.ui.panels import FindingsPanel

    panel = FindingsPanel()
    panel.set_findings(
        [_treffer(1, "Meier"), _treffer(2, "Meier", enabled=False)]
    )

    # Zeile 0 ist an -> alle aus.
    assert panel.toggle_same_text(0) == 2
    assert _haken(panel, 0) == Qt.Unchecked
    assert _haken(panel, 1) == Qt.Unchecked

    # Zeile 1 (abgehakt) anklicken -> alle an.
    assert panel.toggle_same_text(1) == 2
    assert _haken(panel, 0) == Qt.Checked
    assert _haken(panel, 1) == Qt.Checked

    panel.deleteLater()
    qt_app.processEvents()


def test_doppelklick_schaltet_alle_gleichnamigen_treffer(qt_app):
    """Doppelklick auf eine Zeile wirkt wie das Kontextmenü."""
    from PySide6.QtCore import Qt

    from pdfblack.ui.panels import FindingsPanel

    panel = FindingsPanel()
    panel.set_findings(
        [_treffer(1, "Meier"), _treffer(2, "Schmidt"), _treffer(3, "Meier", seite=1)]
    )

    gemeldet: list[tuple[int, bool]] = []
    panel.enabledChanged.connect(lambda uid, enabled: gemeldet.append((uid, enabled)))

    panel._on_double_clicked(panel.table.item(0, panel.COL_TEXT))
    assert gemeldet == [(1, False), (3, False)]
    assert _haken(panel, 0) == Qt.Unchecked
    assert _haken(panel, 2) == Qt.Unchecked
    assert _haken(panel, 1) == Qt.Checked

    gemeldet.clear()
    panel._on_double_clicked(panel.table.item(2, panel.COL_TEXT))
    assert gemeldet == [(1, True), (3, True)]
    assert _haken(panel, 0) == Qt.Checked
    assert _haken(panel, 2) == Qt.Checked

    # Ein einzelner Treffer laesst sich weiterhin per Doppelklick umschalten.
    gemeldet.clear()
    panel._on_double_clicked(panel.table.item(1, panel.COL_TEXT))
    assert gemeldet == [(2, False)]
    assert _haken(panel, 1) == Qt.Unchecked

    panel.deleteLater()
    qt_app.processEvents()


def _baum_eintrag(panel, text: str):
    for index in range(panel.category_tree.topLevelItemCount()):
        top = panel.category_tree.topLevelItem(index)
        for child_index in range(top.childCount()):
            child = top.child(child_index)
            if child.text(0) == text:
                return top, child
    return None, None


def test_doppelklick_im_kategorienbaum_schaltet_alle_gleichnamigen(qt_app):
    """„Nach Kategorie“ reagiert wie die Trefferliste."""
    from PySide6.QtCore import Qt

    from pdfblack.ui.panels import FindingsPanel

    panel = FindingsPanel()
    panel.set_findings(
        [_treffer(1, "Meier"), _treffer(2, "Schmidt"), _treffer(3, "Meier", seite=1)]
    )
    gruppe, eintrag = _baum_eintrag(panel, "Meier")
    assert eintrag is not None

    gemeldet: list[tuple[int, bool]] = []
    panel.enabledChanged.connect(lambda uid, enabled: gemeldet.append((uid, enabled)))

    # Angehakt -> beide "Meier" gehen aus, auch in der Trefferliste.
    panel._on_group_double_clicked(eintrag, 0)
    assert gemeldet == [(1, False), (3, False)]
    assert _haken(panel, 0) == Qt.Unchecked
    assert _haken(panel, 2) == Qt.Unchecked
    assert _haken(panel, 1) == Qt.Checked
    # Ein von zwei Namen ist noch aktiv -> gemischte Gruppe.
    assert gruppe.checkState(0) == Qt.PartiallyChecked

    # Abgehakt -> beide wieder an.
    gemeldet.clear()
    _, eintrag = _baum_eintrag(panel, "Meier")
    panel._on_group_double_clicked(eintrag, 0)
    assert gemeldet == [(1, True), (3, True)]
    assert _haken(panel, 0) == Qt.Checked
    assert _haken(panel, 2) == Qt.Checked
    assert gruppe.checkState(0) == Qt.Checked

    # Der Gruppenkopf selbst schaltet weiterhin nichts um.
    gemeldet.clear()
    panel._on_group_double_clicked(gruppe, 0)
    assert gemeldet == []
    assert _haken(panel, 0) == Qt.Checked

    panel.deleteLater()
    qt_app.processEvents()
