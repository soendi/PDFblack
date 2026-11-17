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
