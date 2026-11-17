"""Ablage der geschwaerzten Kopien im Benutzerordner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import ablage  # noqa: E402


def test_ordner_liegt_im_benutzerprofil():
    """Der Ordner haengt direkt im Benutzerprofil."""
    assert ablage.ORDNER.parent.parent == Path.home()
    assert ablage.ORDNER.name == "Geschwärzt"


def test_ziel_legt_den_ordner_an_und_nummeriert(tmp_path, monkeypatch):
    monkeypatch.setattr(ablage, "ORDNER", tmp_path / "Ablage")

    erstes = ablage.ziel("/irgendwo/Brief.pdf")
    assert erstes.parent == tmp_path / "Ablage"
    assert erstes.parent.is_dir()
    assert erstes.name == "Brief_geschwaerzt.pdf"

    erstes.write_bytes(b"%PDF-1.7")
    zweites = ablage.ziel("/irgendwo/Brief.pdf")
    assert zweites.name == "Brief_geschwaerzt_2.pdf"


def test_lerndatei_liegt_neben_der_ablage():
    """Die Lerndatei gehoert nicht in den Ordner, den die Ablage leert."""
    from pdfblack.core import lerndatei

    assert lerndatei.ORDNER == ablage.ORDNER.parent
    assert ablage.ORDNER != lerndatei.ORDNER
    assert lerndatei.DATEI.parent == lerndatei.ORDNER


def test_lerndatei_bleibt_beim_beenden_erhalten(tmp_path, monkeypatch):
    """Was der closeEvent aufraeumt, laesst die Lerndatei stehen."""
    from pdfblack.core import lerndatei
    from pdfblack.core.models import Category, Finding
    from pdfblack.ui import compare

    profil = tmp_path / "PDFblack"
    monkeypatch.setattr(ablage, "ORDNER", profil / "Geschwärt")
    monkeypatch.setattr(lerndatei, "DATEI", profil / "lerndatei.jsonl")
    monkeypatch.setattr(compare, "handover_base", lambda: tmp_path / "Uebergabe")

    kopie = ablage.ziel("Brief.pdf")
    kopie.write_bytes(b"%PDF-1.7")
    finding = Finding(
        text="Muster AG",
        category=Category.COMPANY,
        page=0,
        source="KI (Presidio) · LOCATION",
        entity="LOCATION",
        score=0.8,
        uid=1,
    )
    lerndatei.merken(
        lerndatei.korrektur(finding, "Muster AG", Category.COMPANY, Category.PERSON)
    )

    # Genau das passiert beim Beenden: die Kopien der Ablage verschwinden.
    compare.delete_redacted([str(pfad) for pfad in ablage.dateien()])
    assert ablage.dateien() == []
    assert ablage.leeren() == 0

    beispiele = lerndatei.eintraege()
    assert beispiele, "die Lerndatei darf beim Beenden nicht verschwinden"
    assert beispiele[0]["kategorie_nachher"] == "Person"


def test_leeren_entfernt_alle_dateien(tmp_path, monkeypatch):
    monkeypatch.setattr(ablage, "ORDNER", tmp_path / "Ablage")
    ziel = ablage.ziel("Brief.pdf")
    ziel.write_bytes(b"%PDF-1.7")
    (ablage.ORDNER / "Unterordner").mkdir()

    assert [datei.name for datei in ablage.dateien()] == ["Brief_geschwaerzt.pdf"]
    assert ablage.leeren() == 1
    assert ablage.dateien() == []
    # Unterordner bleiben unangetastet.
    assert (ablage.ORDNER / "Unterordner").is_dir()
