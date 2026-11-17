"""Tests fuer Hinweis-Aktionen in der Trefferliste (quittieren, korrigieren)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402

import pdfblack.ui.main_window  # noqa: E402,F401  - Importfehler sollen auffallen
from pdfblack.core import lerndatei  # noqa: E402
from pdfblack.core.models import Category, Finding  # noqa: E402
from pdfblack.core.redact import erweitere_rects  # noqa: E402
from pdfblack.ui.panels import FindingsPanel  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def window(qt_app, tmp_path):
    # Einstellungen im Testverzeichnis halten, damit nichts Echtes angefasst wird.
    for fmt in (QtCore.QSettings.IniFormat, QtCore.QSettings.NativeFormat):
        QtCore.QSettings.setPath(fmt, QtCore.QSettings.UserScope, str(tmp_path))
    from pdfblack.ui.main_window import MainWindow

    win = MainWindow()
    yield win
    win.close()


def test_korrigierter_wert_steht_in_der_liste():
    finding = Finding(
        text="09.0.2022",
        category=Category.DATE,
        page=0,
        hinweis="Datum \u201e09.0.2022\u201c ist kein gueltiges Datum",
    )
    assert finding.display_text == "09.0.2022"
    finding.korrigiert = "09.01.2022"
    assert finding.display_text == "09.01.2022"
    # Der gefundene Text bleibt erhalten - er beschreibt die Stelle im PDF.
    assert finding.text == "09.0.2022"


def test_menue_bietet_hinweis_aktionen(qt_app):
    panel = FindingsPanel()
    panel.set_findings(
        [
            Finding(
                text="09.0.2022",
                category=Category.DATE,
                page=0,
                uid=1,
                hinweis="kein gueltiges Datum",
            ),
            Finding(text="12.04.2021", category=Category.DATE, page=0, uid=2),
        ]
    )

    mit_hinweis = [aktion.text() for aktion in panel._menu_for(0).actions()]
    ohne_hinweis = [aktion.text() for aktion in panel._menu_for(1).actions()]
    assert any("trotzdem" in text for text in mit_hinweis), mit_hinweis
    assert any("korrigieren" in text for text in mit_hinweis), mit_hinweis
    assert not any("trotzdem" in text for text in ohne_hinweis), ohne_hinweis
    assert not any("korrigieren" in text for text in ohne_hinweis), ohne_hinweis


def test_liste_und_dokument_bauen_dasselbe_menue(qt_app):
    """Beide Menues kommen aus treffer_menue() - ein Bauplan, keine Kopie."""
    from pdfblack.ui.treffermenue import treffer_menue

    finding = Finding(
        text="09.0.2022",
        category=Category.DATE,
        page=0,
        uid=1,
        hinweis="kein gueltiges Datum",
    )
    panel = FindingsPanel()
    panel.set_findings([finding])

    aus_der_liste = [
        (aktion.text(), aktion.data()) for aktion in panel._menu_for(0).actions()
    ]
    direkt = [
        (aktion.text(), aktion.data())
        for aktion in treffer_menue(panel, finding, 1).actions()
    ]
    assert aus_der_liste == direkt


def test_menue_bietet_aktionen_fuer_alle_gleichlautenden(qt_app):
    from pdfblack.ui.treffermenue import treffer_menue

    finding = Finding(text="Meier", category=Category.PERSON, page=0, uid=1)
    menu = treffer_menue(None, finding, 3)
    daten = [aktion.data() for aktion in menu.actions()]
    assert "alle-fehlalarm" in daten
    assert "alle-umschalten" in daten
    texte = [aktion.text() for aktion in menu.actions()]
    assert any("Alle \u201eMeier\u201c umschalten (3)" in text for text in texte)
    untermenue = next(
        aktion.menu() for aktion in menu.actions() if aktion.menu() is not None
    )
    assert "alle:Person" in [aktion.data() for aktion in untermenue.actions()]


def test_alle_gleichlautenden_aus_dem_dokument_umschalten(window):
    treffer = [
        Finding(text="Meier", category=Category.PERSON, page=0, uid=nummer)
        for nummer in (1, 2, 3)
    ]
    window._findings = list(treffer)
    window._sync_findings()

    window._toggle_gleichnamige(1)
    assert all(not finding.enabled for finding in treffer)

    window._toggle_gleichnamige(1)
    assert all(finding.enabled for finding in treffer)


def test_rects_werden_um_ein_zeichen_verbreitert():
    """Ein verschlucktes Zeichen darf nicht neben der Schwärzung stehen bleiben."""
    rects = [(100.0, 200.0, 140.0, 212.0)]
    breit = erweitere_rects(rects, "09.0.2022")
    zeichen = 40.0 / len("09.0.2022")
    assert breit[0][0] == pytest.approx(100.0 - zeichen)
    assert breit[0][2] == pytest.approx(140.0 + zeichen)
    # Hoehe bleibt gleich, linke Kante faellt nie unter null.
    assert breit[0][1] == 200.0 and breit[0][3] == 212.0
    assert erweitere_rects([(1.0, 5.0, 3.0, 9.0)], "12")[0][0] >= 0.0


def test_lerndatei_nimmt_den_korrigierten_wert():
    """Gelernt wird der bestaetigte Wert, der Fund bleibt als text_original."""
    finding = Finding(
        text="09.0.2022",
        category=Category.DATE,
        page=2,
        korrigiert="09.01.2022",
        source="Muster \u00b7 Datum",
    )
    eintrag = lerndatei.korrektur(
        finding, "Zeitraum bis 09.0.2022", Category.DATE, Category.DATE
    )
    assert eintrag["text"] == "09.01.2022"
    assert eintrag["text_original"] == "09.0.2022"
    # Der Kontext stammt von der Seite und damit vom gefundenen Wert.
    assert "09.0.2022" in eintrag["zeile"]


def test_ohne_korrektur_bleibt_der_fund():
    finding = Finding(text="12.04.2021", category=Category.DATE, page=0)
    eintrag = lerndatei.korrektur(
        finding, "am 12.04.2021", Category.DATE, Category.DATE
    )
    assert eintrag["text"] == "12.04.2021"
    assert "text_original" not in eintrag


def test_korrektur_landet_in_der_lerndatei(window, monkeypatch):
    """Der Weg ueber das Fenster schreibt den korrigierten Wert weg."""
    ziel = Finding(
        text="09.0.2022",
        category=Category.DATE,
        page=0,
        rects=[(100.0, 200.0, 140.0, 212.0)],
        uid=7,
        hinweis="kein gueltiges Datum",
        source="Muster \u00b7 Datum",
    )
    window._findings = [ziel]
    window.findings_panel.set_findings([ziel])

    monkeypatch.setattr(
        QtWidgets.QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("09.01.2022", True)),
    )
    gespeichert: list[dict] = []
    monkeypatch.setattr(
        lerndatei, "merken", lambda eintrag, datei=None: gespeichert.append(eintrag)
    )

    window._korrigiere_wert(7)

    assert ziel.korrigiert == "09.01.2022"
    # Die Stelle bleibt als Pruefhinweis stehen und die Flaeche ist breiter.
    assert "pr\u00fcfen" in ziel.hinweis
    assert ziel.rects[0][0] < 100.0 and ziel.rects[0][2] > 140.0
    assert gespeichert, "keine Korrektur in der Lerndatei"
    assert gespeichert[-1]["art"] == lerndatei.ART_WERTKORREKTUR
    assert gespeichert[-1]["text"] == "09.01.2022"
    assert gespeichert[-1]["text_original"] == "09.0.2022"
