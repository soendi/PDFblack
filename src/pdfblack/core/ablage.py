"""Ablage fuer die geschwaerzten Kopien im Benutzerordner.

PDFblack schreibt jede geschwaerzte Fassung in einen eigenen Ordner im
Benutzerprofil (``PDFblack/Geschwaerzt``, unter Windows also
``C:\\Users\\<Name>\\PDFblack\\Geschwärzt``). Der Ordner ist als Zwischenablage
gedacht: Beim Beenden von PDFblack werden die Kopien wieder entfernt, das
Original bleibt unberuehrt.
"""

from __future__ import annotations

from pathlib import Path

# Ordner im Benutzerprofil. Tests ersetzen den Wert durch ein temporaeres
# Verzeichnis (siehe tests/test_ablage.py).
ORDNER = Path.home() / "PDFblack" / "Geschwärzt"


def ordner() -> Path:
    """Ablage anlegen, falls noetig, und zurueckgeben."""
    ORDNER.mkdir(parents=True, exist_ok=True)
    return ORDNER


def ziel(quelle: str) -> Path:
    """Freien Dateinamen fuer die geschwaerzte Kopie einer Datei liefern.

    Heisst die Quelle ``Brief.pdf``, entsteht ``Brief_geschwaerzt.pdf``; liegt
    die Datei schon in der Ablage, wird durchnummeriert.
    """
    basis = Path(quelle).stem or "Kopie"
    ordner_pfad = ordner()
    kandidat = ordner_pfad / f"{basis}_geschwaerzt.pdf"
    nummer = 2
    while kandidat.exists():
        kandidat = ordner_pfad / f"{basis}_geschwaerzt_{nummer}.pdf"
        nummer += 1
    return kandidat


def dateien() -> list[Path]:
    """Alle Dateien in der Ablage (leer, wenn es den Ordner nicht gibt)."""
    try:
        return sorted(pfad for pfad in ORDNER.iterdir() if pfad.is_file())
    except OSError:
        return []


def leeren() -> int:
    """Alle Dateien in der Ablage loeschen. Rueckgabe: Anzahl."""
    anzahl = 0
    for datei in dateien():
        try:
            datei.unlink()
            anzahl += 1
        except OSError:
            continue
    return anzahl
