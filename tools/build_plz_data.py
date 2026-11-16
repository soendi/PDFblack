"""Baut die Schweizer PLZ-Liste fuer PDFblack.

Quellen (beide frei nutzbar, Quellenangabe in der Datei):

* swisstopo, "Amtliches Ortschaftenverzeichnis mit Postleitzahl und Perimeter"
  (opendata.swiss, freie Nutzung, monatlich nachgefuehrt) - amtliche Namen und
  PLZ der Schweiz und des Fuerstentums Liechtenstein.
* GeoNames, Postal Codes CH/LI (CC BY 4.0) - ergaenzt Postfach-Postleitzahlen
  wie 8000 Zuerich oder 3000 Bern, die im amtlichen Ortschaftenverzeichnis
  nicht als Ortschaft gefuehrt werden.

Aufruf:  python tools/build_plz_data.py
Ergebnis: src/pdfblack/data/plz_ch.json
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

SWISSTOPO_ZIP = (
    "https://data.geo.admin.ch/ch.swisstopo-vd.ortschaftenverzeichnis_plz/"
    "ortschaftenverzeichnis_plz/ortschaftenverzeichnis_plz_2056.csv.zip"
)
GEONAMES_ZIP = "https://download.geonames.org/export/zip/{land}.zip"
LAENDER = ("CH", "LI")

ZIEL = Path(__file__).resolve().parents[1] / "src" / "pdfblack" / "data" / "plz_ch.json"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# Zweitnamen der groesseren Orte: amtlich steht meist die eine Sprachform,
# im Dokument oft die andere ("1204 Genf" statt "Geneve", "1950 Sitten"
# statt "Sion"). Schluessel = Schreibweise aus der Liste.
ALIASE = {
    "geneve": ("Genf", "Ginevra"),
    "sion": ("Sitten",),
    "neuchatel": ("Neuenburg",),
    "bienne": ("Biel",),
    "fribourg": ("Freiburg",),
    "luzern": ("Lucerne",),
    "stgallen": ("Saint-Gall", "San Gallo"),
    "chur": ("Coire",),
    "solothurn": ("Soleure",),
    "glarus": ("Glaris",),
    "zug": ("Zoug",),
    "bern": ("Berne",),
    "delemont": ("Delsberg",),
    "porrentruy": ("Pruntrut",),
    "bellinzona": ("Bellinzone",),
}


def _ohne_akzente(text: str) -> str:
    import unicodedata

    zerlegt = unicodedata.normalize("NFKD", text)
    return "".join(zeichen for zeichen in zerlegt if not unicodedata.combining(zeichen))


def varianten(name: str) -> set[str]:
    """Schreibweisen eines Ortsnamens: mit und ohne Umlaut-Umschrift.

    In PDFs steht mal "Zürich", mal "Zuerich", mal "Zurich". Alle drei sollen
    zu 8000/8001 usw. passen, deshalb werden beide Umschriften abgelegt.
    """
    name = name.strip()
    if not name:
        return set()
    # Postfach-Zusaetze wie "Bern 60 UPD" oder "Lausanne 22" auf den Kern kuerzen.
    kern = re.sub(r"\s+\d+[A-Za-z]?$", "", name)
    kern = re.sub(r"\s+[A-Z]{2,4}$", "", kern) or kern
    ergebnis: set[str] = set()
    for form in {name, kern}:
        if not form:
            continue
        gestrichen = re.sub(r"[^a-z0-9]", "", _ohne_akzente(form).lower())
        umschrieben = re.sub(r"[^a-z0-9]", "", form.lower().translate(_UMLAUTE))
        for wert in (gestrichen, umschrieben):
            if len(wert) >= 3:
                ergebnis.add(wert)
    return ergebnis


def _lade(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as antwort:  # noqa: S310 - feste URLs
        return antwort.read()


def lies_swisstopo() -> list[tuple[str, str]]:
    rohdaten = _lade(SWISSTOPO_ZIP)
    paare: list[tuple[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(rohdaten)) as archiv:
        name = next(n for n in archiv.namelist() if n.lower().endswith(".csv"))
        text = archiv.read(name).decode("utf-8-sig")
    for zeile in csv.DictReader(io.StringIO(text), delimiter=";"):
        plz = (zeile.get("PLZ4") or "").strip()
        ort = (zeile.get("Ortschaftsname") or "").strip()
        if re.fullmatch(r"\d{4}", plz) and ort:
            paare.append((plz, ort))
    return paare


def lies_geonames() -> list[tuple[str, str]]:
    paare: list[tuple[str, str]] = []
    for land in LAENDER:
        rohdaten = _lade(GEONAMES_ZIP.format(land=land))
        with zipfile.ZipFile(io.BytesIO(rohdaten)) as archiv:
            name = next(n for n in archiv.namelist() if n.lower() == f"{land.lower()}.txt")
            text = archiv.read(name).decode("utf-8")
        for zeile in text.splitlines():
            spalten = zeile.split("\t")
            if len(spalten) < 3:
                continue
            plz, ort = spalten[1].strip(), spalten[2].strip()
            if re.fullmatch(r"\d{4}", plz) and ort:
                paare.append((plz, ort))
    return paare


def baue() -> dict:
    codes: dict[str, set[str]] = {}
    for plz, ort in lies_swisstopo() + lies_geonames():
        codes.setdefault(plz, set()).update(varianten(ort))

    for werte in codes.values():
        zusatz: set[str] = set()
        for name in list(werte):
            for alias in ALIASE.get(name, ()):
                zusatz |= varianten(alias)
        werte |= zusatz

    return {
        "stand": "2026-11",
        "land": "CH + FL",
        "quellen": [
            "swisstopo, Amtliches Ortschaftenverzeichnis mit Postleitzahl und "
            "Perimeter (opendata.swiss, freie Nutzung, Stand 01.11.2026)",
            "GeoNames, Postal Codes CH/LI (CC BY 4.0)",
        ],
        "codes": {plz: sorted(werte) for plz, werte in sorted(codes.items())},
    }


def main() -> int:
    daten = baue()
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(
        json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    groesse = ZIEL.stat().st_size
    print(f"{len(daten['codes'])} Postleitzahlen geschrieben ({groesse / 1024:.0f} kB)")
    for probe in ("1950", "2000", "8000", "3000", "9490", "2026", "2019"):
        print(probe, "->", daten["codes"].get(probe, "keine PLZ")[:4])
    return 0


if __name__ == "__main__":
    sys.exit(main())
