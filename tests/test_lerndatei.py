"""Tests fuer die Lerndatei: Korrekturen mit Kontext sammeln und ausgeben."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import lerndatei  # noqa: E402
from pdfblack.core.models import Category, Finding  # noqa: E402


def test_reine_wertkorrektur_hat_eigenen_art():
    finding = _finding(text="09.0.2022", category=Category.DATE, korrigiert="09.01.2022")
    eintrag = lerndatei.korrektur(
        finding, "Zeitraum bis 09.0.2022", Category.DATE, Category.DATE
    )

    assert eintrag["art"] == lerndatei.ART_WERTKORREKTUR
    assert eintrag["text"] == "09.01.2022"
    assert eintrag["text_original"] == "09.0.2022"


def test_wertkorrektur_gilt_nicht_als_gelernte_regel(tmp_path):
    """Auch die vorlaeufige Regelanwendung bleibt unberuehrt."""
    datei = tmp_path / "lerndatei.jsonl"
    finding = _finding(
        text="09.0.2022", category=Category.DATE, korrigiert="09.01.2022"
    )
    lerndatei.merken(
        lerndatei.korrektur(finding, "", Category.DATE, Category.DATE), datei
    )
    assert lerndatei.eintraege(datei), "Eintrag fehlt"
    assert lerndatei.regeln(datei) == {}


def test_kategoriewechsel_bleibt_eine_korrektur():
    """Nur der reine Wertfall bekommt den eigenen Typ."""
    finding = _finding(text="09.0.2022", category=Category.ID, korrigiert="09.01.2022")
    eintrag = lerndatei.korrektur(finding, "", Category.ID, Category.DATE)
    assert eintrag["art"] == "korrektur"


def _finding(**felder) -> Finding:
    vorgabe = {
        "text": "Muster AG",
        "category": Category.COMPANY,
        "page": 1,
        "source": "KI (Presidio) · LOCATION",
        "entity": "LOCATION",
        "score": 0.85,
        "uid": 3,
    }
    vorgabe.update(felder)
    return Finding(**vorgabe)


def test_korrektur_haelt_text_und_kontext_fest(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    seite = (
        "Bewerbung\n"
        "Sehr geehrte Damen und Herren\n"
        "Muster\n"
        "AG\n"
        "9435 Heerbrugg, 20.10.2026"
    )
    eintrag = lerndatei.korrektur(
        _finding(), seite, Category.COMPANY, Category.ADDRESS
    )

    assert eintrag["art"] == "korrektur"
    assert eintrag["text"] == "Muster AG"
    assert eintrag["kategorie_vorher"] == "Firma"
    assert eintrag["kategorie_nachher"] == "Adresse"
    assert eintrag["seite"] == 2
    assert eintrag["quelle"] == "KI (Presidio) · LOCATION"
    assert eintrag["entity"] == "LOCATION"
    assert eintrag["score"] == 0.85
    # Der Treffer steht über einen Zeilenumbruch - der Kontext findet ihn.
    assert "Sehr geehrte Damen und Herren" in eintrag["kontext_vorher"]
    assert eintrag["kontext_nachher"].startswith("9435 Heerbrugg")
    assert eintrag["zeile"] == "Muster AG"

    lerndatei.merken(eintrag)
    zeilen = (tmp_path / "lerndatei.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(zeilen[0])["art"] == "kopf"
    gespeichert = json.loads(zeilen[1])
    assert gespeichert["kategorie_nachher"] == "Adresse"
    assert lerndatei.eintraege() == [gespeichert]


def test_fehlalarm_wird_als_kein_treffer_vermerkt(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    finding = _finding(text="Fachmessen", category=Category.POSTAL)

    eintrag = lerndatei.korrektur(
        finding, "Die Fachmessen 2026 in Zuerich", finding.category, None
    )

    assert eintrag["art"] == "kein_treffer"
    assert eintrag["kategorie_nachher"] == "kein Treffer"
    assert eintrag["zeile"] == "Die Fachmessen 2026 in Zuerich"


def test_anzahl_gleichnamiger_treffer_steht_im_beispiel():
    viele = lerndatei.korrektur(
        _finding(), "", Category.COMPANY, Category.PERSON, anzahl=15
    )
    assert viele["gleichnamige_treffer"] == 15
    einer = lerndatei.korrektur(_finding(), "", Category.COMPANY, None)
    assert einer["gleichnamige_treffer"] == 1


def test_ohne_fundstelle_bleiben_die_kontextfelder_leer(tmp_path):
    eintrag = lerndatei.korrektur(
        _finding(text="Manuell markierter Bereich"), "", Category.OTHER, Category.PERSON
    )
    assert eintrag["kontext_vorher"] == ""
    assert eintrag["kontext_nachher"] == ""
    assert eintrag["zeile"] == ""
    assert eintrag["text"] == "Manuell markierter Bereich"


def test_export_schreibt_alle_beispiele(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    finding = _finding(text="12.03.1985", category=Category.DATE, page=0)
    lerndatei.merken(
        lerndatei.korrektur(
            finding, "Geb. 12.03.1985", Category.DATE, Category.BIRTHDATE
        )
    )
    lerndatei.merken(
        lerndatei.korrektur(finding, "Geb. 12.03.1985", Category.DATE, Category.PERSON)
    )

    ziel = tmp_path / "PDFblack-Lerndatei.jsonl"
    assert lerndatei.exportieren(ziel) == 2

    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3
    assert json.loads(zeilen[0])["art"] == "kopf"
    assert "Lernbeispiel" in json.loads(zeilen[0])["hinweis"]
    assert [json.loads(zeile)["kategorie_nachher"] for zeile in zeilen[1:]] == [
        "Geburtsdatum",
        "Person",
    ]


def test_kaputte_zeilen_werden_uebersprungen(tmp_path, monkeypatch):
    datei = tmp_path / "lerndatei.jsonl"
    datei.write_text(
        '{"art": "kopf", "format": 1}\n'
        '{"art": "korrektur", "text": "a"}\n'
        "keine json zeile\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lerndatei, "DATEI", datei)

    assert lerndatei.eintraege() == [{"art": "korrektur", "text": "a"}]


def test_ohne_datei_gibt_es_keine_beispiele(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "fehlt.jsonl")
    assert lerndatei.eintraege() == []


def test_gelernte_korrektur_setzt_die_kategorie(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(
            _finding(text="Fachmessen"), "", Category.POSTAL, Category.PERSON
        )
    )
    treffer = Finding(
        text="fachmessen",
        category=Category.POSTAL,
        page=0,
        source="KI (Presidio) · LOCATION",
        uid=1,
    )

    lerndatei.anwenden([treffer])

    # Schreibung und Leerraum spielen beim Vergleich keine Rolle.
    assert treffer.category is Category.PERSON
    # Die urspruengliche Herkunft bleibt stehen und bekommt den Zusatz.
    assert treffer.source == "KI (Presidio) · LOCATION · gelernt: Person"
    assert treffer.enabled is True


def test_fehlalarm_aus_der_lerndatei_wird_nicht_mehr_angehakt(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="Fachmessen"), "", Category.POSTAL, None)
    )
    treffer = Finding(text="Fachmessen", category=Category.POSTAL, page=0, uid=1)

    lerndatei.anwenden([treffer])

    assert treffer.enabled is False
    assert "gelernt: Fehlalarm" in treffer.source
    # Die Kategorie bleibt stehen; der Treffer ist nur nicht mehr angehakt.
    assert treffer.category is Category.POSTAL


def test_manuelle_werte_bleiben_unangetastet(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="Muster AG"), "", Category.COMPANY, None)
    )
    manuell = Finding(
        text="Muster AG",
        category=Category.PERSON,
        page=0,
        entity="MANUAL",
        uid=1,
    )

    lerndatei.anwenden([manuell])

    assert manuell.enabled is True
    assert manuell.category is Category.PERSON


def test_zuletzt_gespeichertes_beispiel_gewinnt(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(
            _finding(text="Muster AG"), "", Category.COMPANY, Category.PERSON
        )
    )
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="Muster AG"), "", Category.PERSON, None)
    )

    assert lerndatei.regeln() == {"muster ag": None}


def _pdf(path: Path, zeilen: list[str]) -> str:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 100
    for zeile in zeilen:
        page.insert_text((60, y), zeile, fontsize=12, fontname="helv")
        y += 26
    doc.save(str(path))
    doc.close()
    return str(path)


def test_erkennung_nutzt_die_gelernte_kategorie(tmp_path, monkeypatch):
    from pdfblack.core.detect import DetectionOptions, run_detection

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="4711-2233"), "", Category.ID, Category.PERSON)
    )
    quelle = _pdf(tmp_path / "brief.pdf", ["Personalnummer: 4711-2233"])

    ergebnis = run_detection(
        quelle, DetectionOptions(use_ai=False, rule_groups=("id",))
    )

    assert [finding.text for finding in ergebnis.findings] == ["4711-2233"]
    assert ergebnis.findings[0].category is Category.PERSON
    assert "· gelernt: Person" in ergebnis.findings[0].source
    assert ergebnis.learned_changed == 1
    assert ergebnis.learned_off == 0


def test_erkennung_uebernimmt_fehlalarme_aus_der_lerndatei(tmp_path, monkeypatch):
    from pdfblack.core.detect import DetectionOptions, run_detection

    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="4711-2233"), "", Category.ID, None)
    )
    quelle = _pdf(tmp_path / "brief.pdf", ["Personalnummer: 4711-2233"])

    ergebnis = run_detection(
        quelle, DetectionOptions(use_ai=False, rule_groups=("id",))
    )

    assert [finding.enabled for finding in ergebnis.findings] == [False]
    assert "gelernt: Fehlalarm" in ergebnis.findings[0].source
    assert ergebnis.learned_off == 1
    assert ergebnis.learned_changed == 0


def test_anwenden_zaehlt_abgehakte_und_umkategorisierte(tmp_path, monkeypatch):
    monkeypatch.setattr(lerndatei, "DATEI", tmp_path / "lerndatei.jsonl")
    lerndatei.merken(
        lerndatei.korrektur(
            _finding(text="Fachmessen"), "", Category.POSTAL, Category.PERSON
        )
    )
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="Muster AG"), "", Category.COMPANY, None)
    )
    treffer = [
        Finding(text="Fachmessen", category=Category.POSTAL, page=0, uid=1),
        Finding(text="Muster AG", category=Category.COMPANY, page=0, uid=2),
        Finding(text="Etwas anderes", category=Category.ID, page=0, uid=3),
    ]

    anwendung = lerndatei.anwenden(treffer)

    assert anwendung.abgehakt == 1
    assert anwendung.umkategorisiert == 1
    assert anwendung.treffer == treffer


def test_einzelnes_beispiel_loeschen(tmp_path, monkeypatch):
    datei = tmp_path / "lerndatei.jsonl"
    monkeypatch.setattr(lerndatei, "DATEI", datei)
    lerndatei.merken(
        lerndatei.korrektur(
            _finding(text="Fachmessen"), "", Category.POSTAL, Category.PERSON
        )
    )
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="Muster AG"), "", Category.COMPANY, None)
    )
    lerndatei.merken(
        lerndatei.korrektur(_finding(text="4711-2233"), "", Category.ID, Category.PERSON)
    )

    assert lerndatei.loeschen([1]) == 1
    assert [eintrag["text"] for eintrag in lerndatei.eintraege()] == [
        "Fachmessen",
        "4711-2233",
    ]
    # Die Kopfzeile bleibt stehen.
    zeilen = datei.read_text(encoding="utf-8").splitlines()
    assert json.loads(zeilen[0])["art"] == "kopf"
    assert len(zeilen) == 3
    # Unbekannte Positionen aendern nichts.
    assert lerndatei.loeschen([99]) == 0


def test_zuruecksetzen_verwirft_alle_beispiele(tmp_path, monkeypatch):
    datei = tmp_path / "lerndatei.jsonl"
    monkeypatch.setattr(lerndatei, "DATEI", datei)
    lerndatei.merken(
        lerndatei.korrektur(_finding(), "", Category.COMPANY, Category.PERSON)
    )
    assert datei.exists()

    assert lerndatei.zuruecksetzen() == 1
    assert lerndatei.eintraege() == []
    assert not datei.exists()

    # Ohne Datei gibt es nichts zu verwerfen.
    assert lerndatei.zuruecksetzen() == 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
