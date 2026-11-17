"""Tests fuer Schreibvarianten erkannter Namen (Zaehlung im Dokument)."""

from __future__ import annotations

from types import SimpleNamespace

import pymupdf

from pdfblack.core import namen
from pdfblack.core.detect import (
    DetectionOptions,
    namensvarianten,
    run_detection,
    schreibvarianten,
)
from pdfblack.core.models import Category


def test_vorname_wird_gerettet():
    """Auch Vornamen werden gezaehlt und korrigiert."""
    texte = ["Marlene"] * 5 + ["Marlenee"]
    assert schreibvarianten(texte, {"Marlene": Category.PERSON}) == {
        "Marlenee": Category.PERSON
    }


def test_echter_vorname_bleibt_unter_zehn_treffern_getrennt():
    """"Joanna" ist selbst ein Vorname; unter zehn Treffern bleibt er stehen."""
    assert namen.ist_vorname("Joanna")
    texte = ["Joana"] * 9 + ["Joanna"]
    assert schreibvarianten(texte, {"Joana": Category.PERSON}) == {}


def test_vorname_wird_ab_zehn_treffern_gerettet():
    """"Joana" 10-mal, "Joanna" 1-mal: die Ausnahme greift."""
    assert namen.ist_vorname("Joana") and namen.ist_vorname("Joanna")
    texte = ["Joana"] * 10 + ["Joanna"]
    assert schreibvarianten(texte, {"Joana": Category.PERSON}) == {
        "Joanna": Category.PERSON
    }


def test_zweimal_die_variante_bleibt_getrennt():
    """Nur eine einzelne Stelle gilt als Lesefehler, nicht zwei."""
    texte = ["Joana"] * 20 + ["Joanna"] * 2
    assert schreibvarianten(texte, {"Joana": Category.PERSON}) == {}


def test_nachname_bleibt_trotz_vieler_treffer_getrennt():
    """Die Ausnahme gilt nur fuer Vornamen."""
    assert namen.ist_vorname("Müller") is False
    texte = ["Müller"] * 20 + ["Möller"]
    assert schreibvarianten(texte, {"Müller": Category.PERSON}) == {}


def test_seltene_schreibweise_wird_zum_namen():
    """10-mal richtig, 1-mal falsch gelesen: die Stelle wird mitgeschwaerzt."""
    text = "Wittler " * 10 + "Witler"
    assert namensvarianten([text], {"Wittler"}) == {"Witler"}


def test_eigener_name_bleibt_getrennt():
    """Zwei echte Nachnamen duerfen nicht verschmelzen."""
    assert namen.ist_name("Müller") and namen.ist_name("Möller")
    assert namensvarianten(["Müller " * 6 + "Möller"], {"Müller"}) == set()


def test_ohne_klare_mehrheit_keine_anpassung():
    """Bei zwei zu zwei Treffern gibt es keine Mehrheit."""
    assert namensvarianten(["Wittler " * 2 + "Witler"], {"Wittler"}) == set()


def test_anfangsbuchstabe_muss_stimmen():
    assert namensvarianten(["Wittler " * 10 + "Qittler"], {"Wittler"}) == set()


def test_zwei_buchstaben_abstand_bleibt_fremd():
    assert namensvarianten(["Wittler " * 10 + "Witter"], {"Wittler"}) == set()


def test_strassenname_wird_gerettet():
    """4-mal richtig, 1-mal falsch: die Strasse wird als Adresse ergaenzt."""
    texte = ["Sägmühlstrasse 25 a"] * 4 + ["Säagmühlstrasse"]
    assert schreibvarianten(texte, {"Sägmühlstrasse": Category.ADDRESS}) == {
        "Säagmühlstrasse": Category.ADDRESS
    }


def test_ort_wird_gerettet():
    texte = ["82140 Olching"] * 4 + ["Olchin"]
    assert schreibvarianten(texte, {"Olching": Category.POSTAL}) == {
        "Olchin": Category.POSTAL
    }


def test_mehrwortige_begriffe_werden_nicht_gezaehlt():
    texte = ["Rue du Lac 12"] * 4 + ["Rue du Lac 12a"]
    assert schreibvarianten(texte, {"Rue du Lac": Category.ADDRESS}) == {}


def _seiten(tmp_path, zeilen) -> object:
    quelle = tmp_path / "seite.pdf"
    doc = pymupdf.open()
    seite = doc.new_page()
    y = 60
    for zeile in zeilen:
        seite.insert_text((50, y), zeile, fontname="helv", fontsize=11)
        y += 20
    doc.save(str(quelle))
    doc.close()
    return run_detection(
        str(quelle), DetectionOptions(use_ai=False, rule_groups=("address",))
    )


def test_pipeline_rettet_den_ort(tmp_path):
    """Der einmal falsch gelesene Ort wird als PLZ/Ort geschwaerzt."""
    ergebnis = _seiten(tmp_path, ["82140 Olching"] * 4 + ["Olchin"])
    gefunden = {f.text for f in ergebnis.findings if f.category is Category.POSTAL}
    assert "Olchin" in gefunden, gefunden


def test_pipeline_rettet_die_strasse(tmp_path):
    """Die einmal falsch gelesene Strasse wird als Adresse geschwaerzt."""
    ergebnis = _seiten(tmp_path, ["Sägmühlstrasse 25 a"] * 4 + ["Säagmühlstrasse"])
    gefunden = {f.text for f in ergebnis.findings if f.category is Category.ADDRESS}
    assert "Säagmühlstrasse" in gefunden, gefunden


def _zeugnis(path) -> None:
    doc = pymupdf.open()
    seite = doc.new_page()
    text = (
        "Herr Joana Wittler war bei uns beschaeftigt.\n"
        + "Frau Wittler arbeitete selbststaendig.\n" * 6
        + "Fuer Witler gilt das ebenso.\n"
    )
    seite.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontname="helv", fontsize=11)
    doc.save(str(path))
    doc.close()


def test_pipeline_schwaerzt_die_variante(tmp_path, monkeypatch):
    """Die falsch gelesene Stelle wird im ganzen Dokument gefunden."""
    source = tmp_path / "zeugnis.pdf"
    _zeugnis(source)

    class FakeAnalyzer:
        def analyze(self, text, **kwargs):
            if "Wittler" not in text:
                return []
            start = text.index("Wittler")
            return [
                SimpleNamespace(
                    entity_type="PERSON",
                    start=start,
                    end=start + len("Wittler"),
                    score=0.9,
                )
            ]

    monkeypatch.setattr("pdfblack.core.detect.get_analyzer", lambda: (FakeAnalyzer(), None))

    result = run_detection(str(source), DetectionOptions(use_ai=True, ai_entities=("PERSON",)))
    gefunden = {f.text for f in result.findings if f.category is Category.PERSON}
    assert "Witler" in gefunden
    assert "Wittler" in gefunden
