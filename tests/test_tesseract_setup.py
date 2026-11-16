"""Tesseract-OCR nachinstallieren."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import tesseract_setup  # noqa: E402


def test_befehl_installiert_das_windows_build():
    befehl = tesseract_setup.befehl("winget")
    assert befehl[0] == "winget"
    assert befehl[1] == "install"
    assert "UB-Mannheim.TesseractOCR" in befehl
    assert "--silent" in befehl
    assert "--accept-package-agreements" in befehl


def test_auf_linux_wird_nichts_installiert():
    if sys.platform.startswith("win"):
        pytest.skip("Auf Windows waere die Installation echt")
    assert not tesseract_setup.moeglich()
    ergebnis = tesseract_setup.installieren()
    assert not ergebnis.ok
    assert "Windows" in ergebnis.message
