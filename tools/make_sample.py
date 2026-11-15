"""Erzeugt eine Beispiel-PDF mit frei erfundenen Daten zum Ausprobieren."""

from __future__ import annotations

from pathlib import Path

import pymupdf

# (Text, Schriftgroesse, x, y) - y waechst in PDF-Koordinaten nach unten.
LINES = [
    ("KBV Musterkasse AG", 15, 60, 84),
    ("Sachbearbeitung Leistungen", 10, 60, 104),
    ("Frau", 11, 60, 168),
    ("Maximiliane Schmidt-Lorenz", 11, 60, 186),
    ("Königsallee 42 a", 11, 60, 204),
    ("80331 München", 11, 60, 222),
    ("Unser Zeichen: PE-8842/2024", 11, 60, 272),
    ("Personalnummer: 4711-2233", 11, 60, 290),
    ("Versichertennummer: A123456789", 11, 60, 308),
    ("Geburtsdatum: 14.03.1981", 11, 60, 326),
    ("Telefon: 089 / 1234567", 11, 60, 344),
    ("E-Mail: maximiliane.schmidt@example.de", 11, 60, 362),
    ("IBAN: DE89 3704 0044 0532 0130 00", 11, 60, 380),
    ("Sehr geehrte Frau Schmidt-Lorenz,", 11, 60, 436),
    ("vielen Dank für Ihren Antrag vom 02.05.2024. Wir haben die Unterlagen", 11, 60, 462),
    ("geprüft und benötigen noch eine Bestätigung Ihrer Bank.", 11, 60, 480),
    ("Bitte senden Sie diese an die oben genannte Adresse oder per E-Mail.", 11, 60, 498),
    ("Mit freundlichen Grüßen", 11, 60, 548),
    ("Anna Müller", 11, 60, 574),
    ("Sachbearbeiterin, Durchwahl 089 / 998877", 9, 60, 590),
]


def build(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_line((60, 130), (535, 130), color=(0.6, 0.6, 0.6), width=0.7)
    for text, size, x, y in LINES:
        page.insert_text((x, y), text, fontsize=size, fontname="helv", color=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path), garbage=4, deflate=True)
    doc.close()
    return path


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "samples" / "beispiel.pdf"
    print(build(target))
