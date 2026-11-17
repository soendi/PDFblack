"""Baut das amtliche Strassenverzeichnis der Schweiz fuer PDFblack.

Quelle: swisstopo, "Amtliches Verzeichnis der Strassen" (opendata.swiss, freie
Nutzung, monatlich nachgefuehrt). Es enthaelt alle Strassennamen, die im
Eidgenoessischen Gebaeude- und Wohnungsregister als Adressbestandteil
deklariert sind, samt Ortschaft, Postleitzahl und Gemeinde.

Aufruf:  python tools/build_strassen_data.py
Ergebnis: src/pdfblack/data/strassen_ch.json
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))

from pdfblack.core.strassen import normalisiere  # noqa: E402

QUELLE = (
    "https://data.geo.admin.ch/ch.swisstopo.amtliches-strassenverzeichnis/"
    "amtliches-strassenverzeichnis_ch/"
    "amtliches-strassenverzeichnis_ch_2056.csv.zip"
)

ZIEL = WURZEL / "src" / "pdfblack" / "data" / "strassen_ch.json"


def lies_swisstopo() -> list[str]:
    """Alle Strassennamen aus der amtlichen CSV-Datei."""
    with urllib.request.urlopen(QUELLE, timeout=300) as antwort:  # noqa: S310 - feste URL
        rohdaten = antwort.read()
    namen: list[str] = []
    with zipfile.ZipFile(io.BytesIO(rohdaten)) as archiv:
        name = next(n for n in archiv.namelist() if n.lower().endswith(".csv"))
        text = archiv.read(name).decode("utf-8-sig")
    for zeile in csv.DictReader(io.StringIO(text), delimiter=";"):
        strasse = (zeile.get("STN_LABEL") or "").strip()
        if strasse:
            namen.append(strasse)
    return namen


def sammle() -> list[str]:
    """Strassennamen in Vergleichsschreibweise, ohne Doppelspurigkeiten."""
    namen: set[str] = set()
    for strasse in lies_swisstopo():
        schluessel = normalisiere(strasse)
        if len(schluessel) < 3 or not any(zeichen.isalpha() for zeichen in schluessel):
            continue
        namen.add(schluessel)
    return sorted(namen)


def main() -> int:
    strassen = sammle()
    daten = {
        "stand": date.today().strftime("%Y-%m"),
        "land": "CH",
        "quellen": [
            "swisstopo, Amtliches Verzeichnis der Strassen "
            "(opendata.swiss, freie Nutzung)"
        ],
        "strassen": strassen,
    }
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(
        json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    groesse = ZIEL.stat().st_size
    print(
        f"{len(strassen)} Strassennamen geschrieben ({groesse / 1024 / 1024:.1f} MB)"
    )
    for probe in (
        "Dorfstrasse",
        "Bahnhofstrasse",
        "Rue du Rhône",
        "Hauptstrasse",
        "Hauptstr.",
    ):
        print(probe, "->", normalisiere(probe) in strassen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
