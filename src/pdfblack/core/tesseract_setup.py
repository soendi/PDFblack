"""Tesseract-OCR nachinstallieren.

PDFocr braucht Tesseract als eigenes Programm; fehlt es, bietet PDFblack beim
Start an, es ueber die Windows-Paketverwaltung ``winget`` zu installieren
(Paket ``UB-Mannheim.TesseractOCR``, das verbreitete Windows-Build). Die
deutsche Sprachdatei ist im Programm enthalten und wird Tesseract per
``--tessdata-dir`` gezeigt - es wird nichts nachgeladen.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass

from .ocr import find_tesseract

LOGGER = logging.getLogger(__name__)

WINGET_ID = "UB-Mannheim.TesseractOCR"
SEITE = "https://github.com/UB-Mannheim/tesseract/wiki"
TIMEOUT = 900.0


@dataclass(frozen=True)
class SetupResult:
    """Ergebnis der Nachinstallation."""

    ok: bool
    message: str


def winget() -> str | None:
    """Pfad zu winget, falls vorhanden."""
    return shutil.which("winget")


def moeglich() -> bool:
    """Kann PDFblack Tesseract selbst installieren?"""
    return sys.platform.startswith("win") and winget() is not None


def befehl(programm: str = "winget") -> list[str]:
    """Aufruf fuer die stille Installation."""
    return [
        programm,
        "install",
        "--id",
        WINGET_ID,
        "--exact",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]


def installieren(timeout: float = TIMEOUT) -> SetupResult:
    """Tesseract-OCR still installieren (blockiert, gehoert in einen Thread)."""
    if not sys.platform.startswith("win"):
        return SetupResult(
            False,
            "Automatisch nachinstallieren geht nur unter Windows. Bitte "
            f"Tesseract-OCR ueber die Paketverwaltung installieren ({SEITE}).",
        )
    programm = winget()
    if programm is None:
        return SetupResult(
            False,
            "winget wurde nicht gefunden. Bitte Tesseract-OCR von Hand "
            f"installieren ({SEITE}).",
        )
    try:
        ergebnis = subprocess.run(  # noqa: S603 - fester Aufruf
            befehl(programm),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.warning("Tesseract-Installation fehlgeschlagen: %s", exc)
        return SetupResult(False, f"Die Installation liess sich nicht starten: {exc}")
    if ergebnis.returncode != 0:
        LOGGER.warning(
            "winget meldet Fehler %s: %s", ergebnis.returncode, ergebnis.stderr
        )
        return SetupResult(
            False,
            f"winget konnte Tesseract-OCR nicht installieren ({SEITE}).",
        )
    if find_tesseract() is None:
        return SetupResult(
            False,
            "Die Installation lief durch, Tesseract wurde aber nicht gefunden. "
            "Bitte PDFblack neu starten oder den Pfad in der "
            "Umgebungsvariablen PDFBLACK_TESSERACT setzen.",
        )
    return SetupResult(
        True,
        "Tesseract-OCR ist installiert. Das deutsche Sprachmodell bringt "
        "PDFblack selbst mit.",
    )
