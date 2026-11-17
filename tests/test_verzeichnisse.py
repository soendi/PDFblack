"""Tests fuer das Strassen- und das Namensverzeichnis.

Die Listen selbst kommen aus den amtlichen Quellen (``tools/build_strassen_data.py``
und ``tools/build_namen_data.py``). Geprueft wird die Vergleichsschreibweise und
dass die Erkennung beide Verzeichnisse nutzt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core import namen, strassen  # noqa: E402
from pdfblack.core.detect import (  # noqa: E402
    DetectionOptions,
    name_tokens,
    run_detection,
)
from pdfblack.core.models import Category  # noqa: E402


def _pdf(path: Path, zeilen: list[str]) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index, zeile in enumerate(zeilen):
        page.insert_text((50, 90 + index * 24), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def _kategorie(pfad: Path, kategorie: Category) -> list[str]:
    options = DetectionOptions(use_ai=False, rule_groups=("address",))
    return [
        finding.text
        for finding in run_detection(str(pfad), options).findings
        if finding.category is kategorie
    ]


def test_strassenverzeichnis_kennt_amtliche_namen():
    assert strassen.verfuegbar()
    assert strassen.anzahl() > 100_000
    for name in ("Dorfstrasse", "Bahnhofstrasse", "Hauptstrasse", "Rue du Rhône"):
        assert strassen.ist_strasse(name), name
    assert not strassen.ist_strasse("Kalkulation")


def test_schreibweise_und_abkuerzung_passen_zusammen():
    # Umlaut-Umschrift und Akzente spielen beim Vergleich keine Rolle.
    assert strassen.normalisiere("Sägmühlstrasse") == "saegmuehlstrasse"
    assert strassen.normalisiere("Rue du Rhône") == strassen.normalisiere("Rue du Rhone")
    # "Bahnhofstr." ist im Verzeichnis als "Bahnhofstrasse" gefuehrt.
    assert strassen.ist_strasse("Bahnhofstr.")


def test_strassenname_ohne_hausnummer_wird_erkannt(tmp_path):
    quelle = _pdf(
        tmp_path / "adresse.pdf",
        ["Wohnhaft an der", "Bahnhofstrasse", "8000 Zuerich"],
    )
    assert "Bahnhofstrasse" in _kategorie(quelle, Category.ADDRESS)


def test_gattungswort_allein_ist_keine_adresse(tmp_path):
    quelle = _pdf(
        tmp_path / "text.pdf",
        ["Der Ring bleibt bis Mai gesperrt", "Wir treffen uns im Park"],
    )
    assert _kategorie(quelle, Category.ADDRESS) == []


def test_namensverzeichnis_kennt_schweizer_namen():
    vornamen, nachnamen = namen.anzahl()
    assert vornamen > 40_000
    assert nachnamen > 100_000
    assert namen.ist_vorname("Hans")
    assert namen.ist_vorname("Hélène")
    assert namen.ist_nachname("Müller")
    assert namen.ist_name("Hans Müller")
    for wort in ("Kalkulation", "Fachmessen", "Urlaub"):
        assert not namen.ist_name(wort), wort


def test_nachname_bleibt_name_trotz_strassenendung():
    # "Steinberg" endet wie eine Strasse, steht aber im Namensverzeichnis.
    assert name_tokens("Steinberg") == {"Steinberg"}
    # Ein Strassenname liefert keine Namensbestandteile.
    assert name_tokens("Bahnhofstrasse") == set()
    assert name_tokens("Rue du Rhône") == set()
