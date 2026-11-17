"""Tests fuer den Weg von der Lerndatei zu festen Regeln im Programmcode."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import lerndatei, lernregeln  # noqa: E402
from pdfblack.core.models import Category, Finding  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]


def _beispiel(text: str, vorher: Category, nachher: Category | None, **rest) -> dict:
    """Ein Beispiel wie aus der Lerndatei."""
    eintrag = {
        "art": "korrektur",
        "text": text,
        "kategorie_vorher": vorher.value,
        "kategorie_nachher": lerndatei.KEIN_TREFFER
        if nachher is None
        else nachher.value,
        "quelle": "KI (Presidio) · LOCATION",
        "entity": "LOCATION",
        "score": 0.8,
        "seite": 1,
    }
    eintrag.update(rest)
    return eintrag


def test_gleicher_aufbau_wird_ein_muster():
    auswertung = lernregeln.auswerten(
        [
            _beispiel("IAO-4711", Category.ID, Category.PERSON),
            _beispiel("IAO-2233", Category.ID, Category.PERSON),
            _beispiel("Fachmessen", Category.POSTAL, Category.PERSON),
        ]
    )

    assert [vorschlag.muster for vorschlag in auswertung.muster] == [r"IAO\-\d+"]
    assert auswertung.muster[0].kategorie is Category.PERSON
    assert auswertung.muster[0].beispiele == ("IAO-4711", "IAO-2233")
    # Ein einzelnes Beispiel bleibt Einzelfall.
    assert [vorschlag.beispiele[0] for vorschlag in auswertung.einzelfaelle] == [
        "Fachmessen"
    ]
    assert auswertung.offen == []


def test_fehlalarme_werden_ausgeschlossen():
    auswertung = lernregeln.auswerten(
        [
            _beispiel("Kd 4711", Category.ID, None),
            _beispiel("Kd 2233", Category.ID, None),
        ]
    )

    assert [vorschlag.muster for vorschlag in auswertung.muster] == [r"Kd\ \d+"]
    assert auswertung.muster[0].kategorie is None


def test_offene_beispiele_werden_benannt():
    auswertung = lernregeln.auswerten(
        [
            # Widerspruch: derselbe Text mit zwei Zielen.
            _beispiel("Muster AG", Category.COMPANY, Category.PERSON),
            _beispiel("Muster AG", Category.COMPANY, Category.ADDRESS),
            # Zu kurz.
            _beispiel("AG", Category.COMPANY, Category.PERSON),
            # Nur Ziffern: als Muster zu allgemein.
            _beispiel("4711-2233", Category.ID, Category.PERSON),
            # Manuell eingegeben.
            _beispiel("Max Mustermann", Category.PERSON, Category.OTHER, entity="MANUAL"),
            # Unbekannte Kategorie.
            _beispiel("Irgendwas", Category.ID, None)
            | {"kategorie_nachher": "Zauberei"},
        ]
    )

    gruende = {text: grund for eintrag, grund in auswertung.offen for text in [eintrag["text"]]}
    assert "widersprüchliche" in gruende["Muster AG"]
    assert "zu kurz" in gruende["AG"]
    assert "nur aus Ziffern" in gruende["4711-2233"]
    assert "manuell" in gruende["Max Mustermann"]
    assert "unbekannt" in gruende["Irgendwas"]


def test_verschiedene_ziele_fuer_dasselbe_muster_bleiben_offen():
    auswertung = lernregeln.auswerten(
        [
            _beispiel("IAO-4711", Category.ID, Category.PERSON),
            _beispiel("IAO-2233", Category.ID, Category.ADDRESS),
        ]
    )

    assert auswertung.muster == []
    assert {grund for _, grund in auswertung.offen} == {
        "Muster mit widersprüchlichen Zielen"
    }


def test_erzeugtes_modul_ist_gueltiger_python_code():
    auswertung = lernregeln.auswerten(
        [
            _beispiel("IAO-4711", Category.ID, Category.PERSON),
            _beispiel("IAO-2233", Category.ID, Category.PERSON),
            _beispiel("Kd 4711", Category.ID, None),
            _beispiel("Kd 2233", Category.ID, None),
        ]
    )

    quelltext = lernregeln.modul(auswertung.muster, "lerndatei.jsonl")
    compile(quelltext, "gelernt.py", "exec")

    raum: dict = {
        "__name__": "pdfblack.core.gelernt",
        "__package__": "pdfblack.core",
    }
    exec(quelltext, raum)  # noqa: S102 - erzeugter Code im Test
    assert raum["AUSGESCHLOSSEN"] == (r"Kd\ \d+",)
    assert raum["ZUGEORDNET"] == ((r"IAO\-\d+", Category.PERSON),)
    assert "Beispiele: IAO-4711" in quelltext


def _lade(quelltext: str) -> dict:
    """Erzeugtes Modul wie ein Modul im Paket ausfuehren."""
    raum: dict = {
        "__name__": "pdfblack.core.gelernt",
        "__package__": "pdfblack.core",
    }
    exec(compile(quelltext, "gelernt.py", "exec"), raum)  # noqa: S102
    return raum


def test_ohne_muster_bleiben_leere_tupel():
    raum = _lade(lernregeln.modul([], "leer.jsonl"))

    assert raum["AUSGESCHLOSSEN"] == ()
    assert raum["ZUGEORDNET"] == ()
    assert "= ()" in lernregeln.modul([], "leer.jsonl")


def test_muster_mit_anfuehrungszeichen_bleibt_gueltiger_code():
    vorschlag = lernregeln.Vorschlag(
        "Kd \"A's\" \\d+", Category.PERSON, "Nummer", ("Kd \"A's\" 4711",)
    )

    raum = _lade(lernregeln.modul([vorschlag], "x.jsonl"))

    assert raum["ZUGEORDNET"] == ((vorschlag.muster, Category.PERSON),)


def test_bericht_nennt_muster_einzelfaelle_und_offene():
    text = lernregeln.bericht(
        lernregeln.auswerten(
            [
                _beispiel("IAO-4711", Category.ID, Category.PERSON),
                _beispiel("IAO-2233", Category.ID, Category.PERSON),
                _beispiel("Fachmessen", Category.POSTAL, Category.PERSON),
                _beispiel("AG", Category.COMPANY, Category.PERSON),
            ]
        )
    )

    assert "2 Muster" not in text  # nur ein Muster, Einzelfall zaehlt separat
    assert "IAO" in text and "Fachmessen" in text and "AG" in text
    assert "Offen (nicht übernehmbar):" in text
    assert "zu kurz" in text


def test_feste_regeln_aendern_und_hakeln_treffer_ab(monkeypatch):
    import re

    monkeypatch.setattr(
        lernregeln,
        "_ZUGEORDNET",
        ((re.compile(r"(?<![\w])IAO\-\d+(?![\w])", re.IGNORECASE), Category.PERSON),),
    )
    monkeypatch.setattr(
        lernregeln,
        "_AUSGESCHLOSSEN",
        (re.compile(r"(?<![\w])Fachmessen(?![\w])", re.IGNORECASE),),
    )
    treffer = [
        Finding(text="iao-4711", category=Category.ID, page=0, source="Muster · Nummer", uid=1),
        Finding(text="Fachmessen", category=Category.POSTAL, page=0, source="Muster · PLZ", uid=2),
        Finding(text="Personalnummer", category=Category.ID, page=0, entity="MANUAL", uid=3),
    ]

    lernregeln.anwenden(treffer)

    assert treffer[0].category is Category.PERSON
    assert treffer[0].source == "Muster · Nummer · im Code: Person"
    assert treffer[1].enabled is False
    assert "im Code: Fehlalarm" in treffer[1].source
    # Manuell eingegebene Werte bleiben unangetastet.
    assert treffer[2].enabled is True and treffer[2].category is Category.ID


def test_abgedeckt_erkennt_uebernommene_beispiele(monkeypatch):
    import re

    monkeypatch.setattr(
        lernregeln,
        "_ZUGEORDNET",
        ((re.compile(r"(?<![\w])IAO\-\d+(?![\w])", re.IGNORECASE), Category.PERSON),),
    )
    monkeypatch.setattr(lernregeln, "_AUSGESCHLOSSEN", ())

    assert lernregeln.abgedeckt(_beispiel("IAO-4711", Category.ID, Category.PERSON))
    assert not lernregeln.abgedeckt(_beispiel("IAO-4711", Category.ID, Category.ADDRESS))
    assert not lernregeln.abgedeckt(_beispiel("Fachmessen", Category.POSTAL, Category.PERSON))


def test_erkennung_nutzt_feste_regeln_ohne_lerndatei(tmp_path, monkeypatch):
    """Was im Code steht, greift auch ohne Lerndatei."""
    import re

    import pymupdf

    from pdfblack.core.detect import DetectionOptions, run_detection

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "gibt-es-nicht.jsonl")
    monkeypatch.setattr(
        lernregeln,
        "_ZUGEORDNET",
        ((re.compile(r"(?<![\w])IAO\-\d+(?![\w])", re.IGNORECASE), Category.PERSON),),
    )
    quelle = tmp_path / "brief.pdf"
    doc = pymupdf.open()
    seite = doc.new_page(width=595, height=842)
    seite.insert_text((60, 100), "Personalnummer: IAO-4711", fontsize=12, fontname="helv")
    doc.save(str(quelle))
    doc.close()

    ergebnis = run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("id",))
    )

    assert [finding.text for finding in ergebnis.findings] == ["IAO-4711"]
    assert ergebnis.findings[0].category is Category.PERSON
    assert "im Code: Person" in ergebnis.findings[0].source
    # Die Lerndatei war nicht beteiligt.
    assert ergebnis.learned_off == 0 and ergebnis.learned_changed == 0


def test_werkzeug_zeigt_bericht_und_schreibt_die_regeln(tmp_path):
    """Der Weg von der exportierten Lerndatei bis in die Programmmdatei."""
    import importlib.util

    datei = tmp_path / "PDFblack-Lerndatei.jsonl"
    eintraege = [
        _beispiel("IAO-4711", Category.ID, Category.PERSON),
        _beispiel("IAO-2233", Category.ID, Category.PERSON),
        _beispiel("AG", Category.COMPANY, Category.PERSON),
    ]
    datei.write_text(
        "\n".join(__import__("json").dumps(e, ensure_ascii=False) for e in eintraege)
        + "\n",
        encoding="utf-8",
    )

    spez = importlib.util.spec_from_file_location(
        "lerndatei_regeln", WURZEL / "tools" / "lerndatei_regeln.py"
    )
    assert spez is not None and spez.loader is not None
    werkzeug = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(werkzeug)

    ziel = tmp_path / "gelernt.py"
    assert werkzeug.main([str(datei), "--schreiben", "--ziel", str(ziel)]) == 0
    quelltext = ziel.read_text(encoding="utf-8")
    compile(quelltext, "gelernt.py", "exec")
    assert "IAO" in quelltext and "Category.PERSON" in quelltext

    # Ohne --schreiben bleibt die Zieldatei unberuehrt.
    ziel.unlink()
    assert werkzeug.main([str(datei)]) == 0
    assert not ziel.exists()


def test_werkzeug_meldet_fehlende_datei(tmp_path, capsys):
    import importlib.util

    spez = importlib.util.spec_from_file_location(
        "lerndatei_regeln", WURZEL / "tools" / "lerndatei_regeln.py"
    )
    assert spez is not None and spez.loader is not None
    werkzeug = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(werkzeug)

    assert werkzeug.main([str(tmp_path / "fehlt.jsonl")]) == 1
    assert "Keine Beispiele" in capsys.readouterr().out


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
