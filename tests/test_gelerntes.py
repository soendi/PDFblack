"""Tests fuer die aus der Lerndatei gelernten Regeln.

Jede hier geprueft Zeile steht fuer eine Korrektur aus der Lerndatei vom
17.11.2026: Telefonfragmente aus IBAN und Handelsregister, Sachwoerter, die
als Person galten, Beschriftungen wie "Tel.", Zeilen wie "Jahr" unter einer
Zahl und Zeitraeume aus Monat/Jahr, die als Telefonnummer erschienen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core.detect import (  # noqa: E402
    DetectionOptions,
    _ai_location_is_place,
    _ist_sachwort,
    name_tokens,
    run_detection,
)
from pdfblack.core.models import Category  # noqa: E402
from pdfblack.core.rules import RULES, compiled  # noqa: E402


def _pdf(path: Path, zeilen: list[str]) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for index, zeile in enumerate(zeilen):
        page.insert_text((50, 90 + index * 24), zeile, fontsize=11, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def _treffer(pfad: Path, groups: tuple[str, ...]):
    options = DetectionOptions(use_ai=False, rule_groups=groups)
    return run_detection(str(pfad), options).findings


def _kategorie(pfad: Path, kategorie: Category, groups: tuple[str, ...]) -> list[str]:
    return [
        finding.text
        for finding in _treffer(pfad, groups)
        if finding.category is kategorie
    ]


def test_sachwoerter_werden_keine_namen():
    for wort in (
        "Urlaub",
        "Wesens",
        "Kalkulation",
        "Wärmeschutz",
        "Nachtragsmanagement",
        "Arbeitsanfall",
        "Jugendnachwuchs",
        "Steildacharbeiten",
        "Schnittstellenkompetenz",
        "Telefax",
        "Tel.",
        "Mai",
        "Bachelor Professional",
    ):
        assert _ist_sachwort(wort), wort
        assert name_tokens(wort) == set(), wort

    # Echte Namen bleiben Namen.
    assert name_tokens("Frau Joana Wittler") == {"Joana", "Wittler"}
    assert name_tokens("Mustermann") == {"Mustermann"}


def test_bankkuerzel_werden_keine_namen():
    for kuerzel in ("DE80", "DE30", "BYLADEM1FFB"):
        assert _ist_sachwort(kuerzel), kuerzel
        assert name_tokens(kuerzel) == set(), kuerzel


def test_vorwahl_in_klammern_ist_kein_ort():
    assert not _ai_location_is_place("(08142)")
    assert _ai_location_is_place("Schaan")
    assert _ai_location_is_place("9435 Heerbrugg")


def test_registerangaben_sind_kein_ort():
    for text in ("HRB 10710", "BIC BYLADEM1FFB", "USt-IdNr. DE327001008", "Tel. 089 123456"):
        assert not _ai_location_is_place(text), text


def test_telefonfragmente_in_iban_und_handelsregister(tmp_path):
    quelle = _pdf(
        tmp_path / "bank.pdf",
        [
            "Münchner Bank, IBAN: DE80 6510 0000 0270 7002",
            "Handelsregister HRB 139510 20 6031 0657 0270 7002",
            "Telefon: 089 123456",
        ],
    )

    kontakt = _kategorie(quelle, Category.CONTACT, ("contact", "bank"))

    # Nur die echte Nummer bleibt uebrig - keine Vierergruppen aus IBAN
    # oder Handelsregister.
    assert kontakt == ["089 123456"]


def test_kurze_zahlenteile_sind_kein_telefon():
    rule = next(rule for rule in RULES if rule.key == "phone")
    for teil in ("0270", "0657", "08142", "08731/"):
        assert not rule.validate(teil), teil
    for nummer in ("089 123456", "08141/42449", "+41 79 761 41 79"):
        assert rule.validate(nummer), nummer


def test_datumsbereich_ist_ein_datum(tmp_path):
    quelle = _pdf(
        tmp_path / "zeitraum.pdf",
        ["Praktikum im Vertrieb", "05/2013 - 07/2013 Praktikum", "08/1997 - 07/1998 Ausbildung"],
    )

    daten = _kategorie(quelle, Category.DATE, ("date",))

    assert "05/2013 - 07/2013" in daten
    assert "08/1997 - 07/1998" in daten
    # Die Spanne bleibt ein Treffer und zerfaellt nicht in zwei Daten.
    assert "05/2013" not in daten


def test_kein_telefon_aus_zeitraum(tmp_path):
    quelle = _pdf(
        tmp_path / "zeitraum2.pdf",
        ["Lebenslauf", "05/2013 - 07/2013 Praktikum im Vertrieb"],
    )

    assert _kategorie(quelle, Category.CONTACT, ("contact", "date")) == []


def test_keine_firma_unter_einer_zahl():
    rule = next(rule for rule in RULES if rule.key == "company_after_number")

    def firmen(text: str) -> list[str]:
        return [
            match.group(1)
            for match in compiled(rule).finditer(text)
            if rule.validate(match.group(0))
        ]

    assert firmen("2020\nBachelor Professional") == []
    assert firmen("2022\nJahr") == []
    assert firmen("2024\nMai") == []
    assert firmen("5 0080\nDE80") == []
    # Eine echte Firma bleibt eine Firma.
    assert firmen("2026\nMuster AG") == ["Muster AG"]


def test_liechtenstein_ist_plz_und_ort(tmp_path):
    quelle = _pdf(tmp_path / "fl.pdf", ["Hilti AG, FL-9494 Schaan"])

    assert "FL-9494 Schaan" in _kategorie(quelle, Category.POSTAL, ("ch_postal",))
