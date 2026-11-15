"""Kurztests fuer Erkennung und Schwärzung (ohne Oberflaeche)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from make_sample import build  # noqa: E402

from pdfblack.core.detect import (  # noqa: E402
    DetectionOptions,
    ManualTerm,
    RegexSpec,
    run_detection,
    term_pattern,
)
from pdfblack.core.models import Category  # noqa: E402
from pdfblack.core.redact import apply_redactions  # noqa: E402


@pytest.fixture(scope="module")
def sample(tmp_path_factory) -> Path:
    return build(tmp_path_factory.mktemp("pdf") / "beispiel.pdf")


def texts(findings) -> list[str]:
    return [f.text for f in findings]


def test_muster_finden_adresse_plz_und_ids(sample):
    result = run_detection(
        str(sample),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "id", "contact")),
    )
    found = texts(result.findings)
    assert any("Königsallee 42" in item for item in found)
    assert any("80331 München" in item for item in found)
    assert any("4711-2233" in item for item in found)
    assert any("maximiliane.schmidt@example.de" in item for item in found)
    assert all(f.rects for f in result.findings)


def test_manuelle_werte_und_regex(sample):
    options = DetectionOptions(
        use_ai=False,
        ai_entities=(),
        rule_groups=(),
        manual_terms=(
            ManualTerm("Nachname", "Schmidt-Lorenz", Category.PERSON),
            ManualTerm("Ort", "München", Category.POSTAL),
        ),
        regexes=(RegexSpec("Akte", r"PE-\d{4}/\d{4}"),),
    )
    result = run_detection(str(sample), options)
    found = texts(result.findings)
    # Der Name steht zweimal im Dokument (Anschrift und Anrede).
    assert found.count("Schmidt-Lorenz") == 2
    assert "München" in found
    assert "PE-8842/2024" in found
    assert all(f.uid for f in result.findings)


def test_ueberlappung_wird_zusammengefasst(sample):
    options = DetectionOptions(
        use_ai=False,
        ai_entities=(),
        rule_groups=(),
        manual_terms=(ManualTerm("Name", "Schmidt-Lorenz", Category.PERSON),),
        regexes=(RegexSpec("Name", r"Maximiliane Schmidt-Lorenz"),),
    )
    result = run_detection(str(sample), options)
    found = texts(result.findings)
    # An der ersten Fundstelle gewinnt der laengere Treffer, die Anrede bleibt
    # als eigener, nicht ueberlappender Treffer erhalten.
    assert found.count("Maximiliane Schmidt-Lorenz") == 1
    assert found.count("Schmidt-Lorenz") == 1


def test_ungueltiger_regex_erzeugt_warnung(sample):
    result = run_detection(
        str(sample),
        DetectionOptions(
            use_ai=False,
            ai_entities=(),
            rule_groups=(),
            regexes=(RegexSpec("kaputt", r"([A-Z"),),
        ),
    )
    assert result.warnings and "ungueltig" in result.warnings[0]


def test_schwaerzen_entfernt_text(sample, tmp_path):
    result = run_detection(
        str(sample),
        DetectionOptions(use_ai=False, ai_entities=(), rule_groups=("address", "id")),
    )
    assert result.findings
    for finding in result.findings:
        if "Königsallee" in finding.text:
            finding.enabled = False

    target = tmp_path / "out.pdf"
    count = apply_redactions(str(sample), str(target), result.findings)
    assert count > 0 and target.exists()

    doc = pymupdf.open(str(target))
    text = doc[0].get_text()
    doc.close()

    assert "4711-2233" not in text
    assert "80331" not in text
    # abgewaehlter Treffer bleibt sichtbar
    assert "Königsallee" in text
    # Originaldatei bleibt unveraendert
    assert "4711-2233" in pymupdf.open(str(sample))[0].get_text()


def test_term_pattern_ignoriert_leerraum():
    pattern = re.compile(term_pattern("Max  Mustermann"), re.IGNORECASE)
    assert pattern.search("hier: max   mustermann,")
    assert not pattern.search("Maximilian Mustermann")
