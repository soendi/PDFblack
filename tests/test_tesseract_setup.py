"""Tesseract-OCR nachinstallieren und mitgelieferte Sprachdatei."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import ocr, tesseract_setup  # noqa: E402


def test_befehl_installiert_das_windows_build():
    befehl = tesseract_setup.befehl("winget")
    assert befehl[0] == "winget"
    assert befehl[1] == "install"
    assert "UB-Mannheim.TesseractOCR" in befehl
    assert "--silent" in befehl
    assert "--accept-package-agreements" in befehl


def test_deutsche_sprachdatei_ist_mitgeliefert():
    """deu.traineddata liegt im Programm - kein Download noetig."""
    datei = ocr.TESSDATA / "deu.traineddata"
    assert datei.is_file()
    assert datei.stat().st_size > 100_000
    assert "deu" in ocr.sprachen_mitgeliefert()


def test_engine_zeigt_auf_die_mitgelieferte_datei():
    engine = ocr.TesseractEngine(language="deu", path="tesseract")
    assert engine.tessdata_dir() == str(ocr.TESSDATA)
    # Eine Sprache, die nicht mitgeliefert wird, bleibt beim Standardordner.
    fremd = ocr.TesseractEngine(language="jpn", path="tesseract")
    assert fremd.tessdata_dir() is None


def test_auf_linux_wird_nichts_installiert():
    if sys.platform.startswith("win"):
        pytest.skip("Auf Windows waere die Installation echt")
    assert not tesseract_setup.moeglich()
    ergebnis = tesseract_setup.installieren()
    assert not ergebnis.ok
    assert "Windows" in ergebnis.message
