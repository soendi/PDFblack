"""Lerndatei in feste Regeln ueberfuehren.

Liest eine exportierte Lerndatei (JSONL), zeigt Muster, Einzelfaelle und offene
Beispiele und schreibt mit ``--schreiben`` die Muster nach
``src/pdfblack/core/gelernt.py``. Danach greifen sie ohne Lerndatei.

Beispiel::

    python tools/lerndatei_regeln.py "%USERPROFILE%/PDFblack-Lerndatei.jsonl"
    python tools/lerndatei_regeln.py "%USERPROFILE%/PDFblack-Lerndatei.jsonl" --schreiben
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))

from pdfblack.core import lerndatei, lernregeln  # noqa: E402

ZIEL = WURZEL / "src" / "pdfblack" / "core" / "gelernt.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Muster aus der Lerndatei als feste Regeln uebernehmen."
    )
    parser.add_argument(
        "datei",
        nargs="?",
        default=str(lerndatei.DATEI),
        help="Lerndatei (JSONL); ohne Angabe die interne Ablage",
    )
    parser.add_argument(
        "--schreiben",
        action="store_true",
        help="die Muster nach src/pdfblack/core/gelernt.py schreiben",
    )
    parser.add_argument(
        "--einzelfaelle",
        action="store_true",
        help="auch Einzelfaelle woertlich uebernehmen",
    )
    parser.add_argument(
        "--ziel",
        default=str(ZIEL),
        help="Zieldatei fuer --schreiben (Vorgabe: src/pdfblack/core/gelernt.py)",
    )
    args = parser.parse_args(argv)

    quelle = Path(args.datei).expanduser()
    beispiele = lerndatei.eintraege(quelle)
    if not beispiele:
        print(f"Keine Beispiele in {quelle}.")
        return 1

    auswertung = lernregeln.auswerten(beispiele)
    print(lernregeln.bericht(auswertung))

    if not args.schreiben:
        print(
            "\nNur Bericht. Mit --schreiben werden die Muster als feste Regeln "
            "nach core/gelernt.py uebernommen."
        )
        return 0

    vorschlaege = list(auswertung.muster)
    if args.einzelfaelle:
        vorschlaege += auswertung.einzelfaelle
    if not vorschlaege:
        print("\nKeine Muster zum Uebernehmen.")
        return 1

    ziel = Path(args.ziel).expanduser()
    ziel.write_text(lernregeln.modul(vorschlaege, quelle.name), encoding="utf-8")
    anzahl = len(vorschlaege)
    print(f"\n{anzahl} {'Regel' if anzahl == 1 else 'Regeln'} nach {ziel} geschrieben.")
    print("Danach die Tests laufen lassen und die Datei mitcommitten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
