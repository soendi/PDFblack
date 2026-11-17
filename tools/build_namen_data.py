"""Baut das Schweizer Namensverzeichnis fuer PDFblack.

Quellen (Bundesamt fuer Statistik, OPEN-BY - freie Nutzung, Quellenangabe
Pflicht, Stand 31.12.2025):

* Weibliche Vornamen der Bevoelkerung nach Jahrgang (ts-x-01.04.00.10)
* Maennliche Vornamen der Bevoelkerung nach Jahrgang (ts-x-01.04.00.11)
* Nachnamen der staendigen Wohnbevoelkerung nach Kanton (ts-x-01.04.00.14)

Beruecksichtigt sind Namen, die schweizweit mindestens dreimal vorkommen. Die
Datei wird von der BFS-Nummer aus aufgeloest, damit im naechsten Jahr nichts
nachgetragen werden muss.

Aufruf:  python tools/build_namen_data.py
Ergebnis: src/pdfblack/data/namen_ch.json
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))

from pdfblack.core.namen import normalisiere  # noqa: E402

# BFS-Nummern der Tabellen; die Download-Adresse steckt in der Asset-Seite.
VORNAMEN = ("ts-x-01.04.00.10", "ts-x-01.04.00.11")
NACHNAMEN = ("ts-x-01.04.00.14",)
ASSET = "https://www.bfs.admin.ch/asset/de/{nummer}"

ZIEL = WURZEL / "src" / "pdfblack" / "data" / "namen_ch.json"

_MASTER = re.compile(
    r"https://dam-api\.bfs\.admin\.ch/hub/api/dam/assets/\d+/master"
)
_NUTZER = "PDFblack/1.3 (Namensverzeichnis, Build-Werkzeug)"


def _lade(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": _NUTZER})
    with urllib.request.urlopen(anfrage, timeout=300) as antwort:  # noqa: S310
        return antwort.read()


def _adresse(nummer: str) -> str:
    """Download-Adresse der CSV-Datei zu einer BFS-Nummer."""
    seite = _lade(ASSET.format(nummer=nummer)).decode("utf-8", "replace")
    treffer = _MASTER.search(seite)
    if treffer is None:
        raise SystemExit(f"Keine Download-Adresse fuer {nummer} gefunden.")
    return treffer.group(0)


def _lies(nummer: str, spalte: str) -> list[str]:
    text = _lade(_adresse(nummer)).decode("utf-8-sig")
    return [
        (zeile.get(spalte) or "").strip()
        for zeile in csv.DictReader(io.StringIO(text))
    ]


def _sauber(name: str) -> str:
    """Name in Vergleichsschreibweise; leer, wenn er nicht taugt."""
    name = " ".join(name.split())
    if not name or len(name) > 40 or not name[0].isalpha():
        return ""
    if not all(zeichen.isalpha() or zeichen in " -'." for zeichen in name):
        return ""
    schluessel = normalisiere(name)
    if len(schluessel) < 2:
        return ""
    return schluessel


def _sammle(namen: list[str]) -> list[str]:
    return sorted({schluessel for name in namen if (schluessel := _sauber(name))})


def sammle() -> tuple[list[str], list[str]]:
    vornamen: list[str] = []
    for nummer in VORNAMEN:
        vornamen += _lies(nummer, "firstname")
    nachnamen: list[str] = []
    for nummer in NACHNAMEN:
        nachnamen += _lies(nummer, "LASTNAME")
    return _sammle(vornamen), _sammle(nachnamen)


def main() -> int:
    vornamen, nachnamen = sammle()
    daten = {
        "stand": str(date.today().year - 1),
        "land": "CH",
        "quellen": [
            "Bundesamt fuer Statistik, Vornamen und Nachnamen der staendigen "
            "Wohnbevoelkerung (OPEN-BY, Quellenangabe Pflicht)",
        ],
        "vornamen": vornamen,
        "nachnamen": nachnamen,
    }
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(
        json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    groesse = ZIEL.stat().st_size
    print(
        f"{len(vornamen)} Vornamen und {len(nachnamen)} Nachnamen geschrieben "
        f"({groesse / 1024:.0f} kB)"
    )
    for probe in ("Hans", "Joana", "Müller", "Meier", "Hélène", "Sägmühl"):
        schluessel = normalisiere(probe)
        print(
            probe,
            "->",
            "Vorname" if schluessel in vornamen else
            "Nachname" if schluessel in nachnamen else "unbekannt",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
