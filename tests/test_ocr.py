"""PDFocr: Bildscan auslesen, unsichtbaren Textlayer, Schwaerzung im Bild."""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfblack.core.models import Category, Finding  # noqa: E402
from pdfblack.core.ocr import (  # noqa: E402
    Word,
    _lies_tsv,
    has_text,
    ocr_pdf,
    place_words,
)
from pdfblack.core.redact import apply_redactions

DPI = 300


def _scan_pdf(path, text: str = "Dachdecker Meier", size: float = 24.0):
    """Bildscan nachstellen: Text auf eine Seite, Seite als Bild speichern.

    Rueckgabe: die Wortrechtecke in Punkten und der Faktor Punkte -> Pixel.
    """
    quelle = pymupdf.open()
    page = quelle.new_page(width=595, height=842)
    page.insert_text((72, 160), text, fontsize=size, fontname="helv")
    woerter = page.get_text("words")
    bild = page.get_pixmap(dpi=DPI).tobytes("png")
    quelle.close()

    scan = pymupdf.open()
    seite = scan.new_page(width=595, height=842)
    seite.insert_image(seite.rect, stream=bild)
    scan.save(str(path))
    scan.close()
    return woerter, DPI / 72.0


class FakeEngine:
    """Engine, die die Woerter an den bekannten Stellen meldet."""

    name = "Test"

    def __init__(self, woerter, faktor: float = DPI / 72.0) -> None:
        self._woerter = woerter
        self._faktor = faktor

    def available(self) -> bool:
        return True

    def read_words(self, png: bytes, size: tuple[int, int]) -> list[Word]:
        return [
            Word(
                text=wort[4],
                box=(
                    wort[0] * self._faktor,
                    wort[1] * self._faktor,
                    wort[2] * self._faktor,
                    wort[3] * self._faktor,
                ),
            )
            for wort in self._woerter
        ]


def test_has_text_unterscheidet_scan_und_text(tmp_path):
    text_pdf = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Ein normaler Brief mit Text.", fontsize=12)
    doc.save(str(text_pdf))
    doc.close()
    assert has_text(str(text_pdf))

    scan, _ = _scan_pdf(tmp_path / "scan.pdf")
    assert scan
    assert not has_text(str(tmp_path / "scan.pdf"))


def test_tsv_auswertung_liest_wortrechtecke():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\t"
        "width\theight\tconf\ttext\n"
        "1\t1\t0\t0\t0\t0\t0\t0\t595\t842\t-1\t\n"
        "5\t1\t1\t1\t1\t1\t100\t200\t80\t20\t96.5\tDachdecker\n"
        "5\t1\t1\t1\t1\t2\t190\t200\t60\t20\t88.0\tMeier\n"
        "5\t1\t1\t1\t1\t3\t250\t200\t0\t20\t0.0\t\n"
    )
    woerter = _lies_tsv(tsv)
    assert [wort.text for wort in woerter] == ["Dachdecker", "Meier"]
    assert woerter[0].box == (100.0, 200.0, 180.0, 220.0)
    assert woerter[0].confidence > 0.9


def test_platzierung_ist_deckungsgleich():
    """Der unsichtbare Text muss genau in den Rechtecken des Bildes stehen."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    ziele = [
        ("Dachdecker", (100.0, 200.0, 196.0, 222.0)),
        ("Müller", (210.0, 200.0, 275.0, 222.0)),
        ("Vorarbeiterin", (100.0, 240.0, 250.0, 262.0)),
    ]
    faktor = DPI / 72.0
    # Die Engine liefert Pixelrechtecke, die Platzierten muessen in Punkten
    # wieder genau darueber liegen.
    woerter = [
        Word(text=text, box=tuple(wert * faktor for wert in box))
        for text, box in ziele
    ]
    assert place_words(page, woerter, DPI) == 3

    gefunden = {wort[4]: pymupdf.Rect(wort[:4]) for wort in page.get_text("words")}
    assert set(gefunden) == {text for text, _ in ziele}
    for text, box in ziele:
        ziel = pymupdf.Rect(box)
        ist = gefunden[text]
        # Waagerecht genau, senkrecht hoechstens zwei Punkte daneben.
        assert abs(ist.x0 - ziel.x0) < 1.0, (text, ist, ziel)
        assert abs(ist.x1 - ziel.x1) < 1.0, (text, ist, ziel)
        assert abs(ist.y0 - ziel.y0) < 2.5, (text, ist, ziel)
        assert abs(ist.y1 - ziel.y1) < 2.5, (text, ist, ziel)

    # Der Text ist unsichtbar: keine Fuell-/Streichfarbe in der Anzeige.
    arten = {span["type"] for span in page.get_texttrace()}
    assert arten == {3}, arten


def test_ocr_layer_laesst_sich_schwaerzen(tmp_path):
    """Erst Textlayer, dann Schwaerzung: das Bild muss mit verschwinden."""
    scan = tmp_path / "scan.pdf"
    woerter, faktor = _scan_pdf(scan)
    ziel = tmp_path / "scan_ocr.pdf"

    ergebnis = ocr_pdf(str(scan), str(ziel), FakeEngine(woerter, faktor))
    assert ergebnis.pages == 1
    assert ergebnis.words == 2

    doc = pymupdf.open(str(ziel))
    page = doc[0]
    text = page.get_text()
    assert "Dachdecker" in text and "Meier" in text
    # Unsichtbar und hinter dem Bild (unter dem Seiteninhalt).
    assert {span["type"] for span in page.get_texttrace()} == {3}
    treffer = next(w for w in page.get_text("words") if w[4] == "Dachdecker")
    box = pymupdf.Rect(treffer[:4])
    doc.close()

    # So wuerde PDFblack die Stelle schwaerzen.
    finding = Finding(
        text="Dachdecker",
        category=Category.PERSON,
        page=0,
        rects=[tuple(box)],
        uid=1,
    )
    geschwaerzt = tmp_path / "scan_ocr_geschwaerzt.pdf"
    assert apply_redactions(str(ziel), str(geschwaerzt), [finding]) == 1

    doc = pymupdf.open(str(geschwaerzt))
    page = doc[0]
    assert "Dachdecker" not in page.get_text()
    # Im Schwärzungsbereich ist das Bild ersetzt, nicht nur der Text entfernt.
    pix = page.get_pixmap(dpi=150, clip=box)
    doc.close()
    proben = pix.samples
    assert proben
    assert max(proben) < 40, "im Bereich steht noch das Bild (helle Scan-Pixel)"


def test_textebene_wird_verworfen_und_neu_aufgesetzt(tmp_path):
    """PDF mit Textebene: Seiten werden gerastert und neu ausgelesen."""
    quelle = tmp_path / "brief.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 160), "Dachdecker Meier", fontsize=24, fontname="helv")
    woerter = page.get_text("words")
    doc.save(str(quelle))
    doc.close()
    vorher = quelle.read_bytes()

    ziel = tmp_path / "brief_neu.pdf"
    ergebnis = ocr_pdf(
        str(quelle), str(ziel), FakeEngine(woerter), ersetze_textebene=True
    )

    assert ergebnis.pages == 1
    assert ergebnis.words == 2
    # Nichts uebersprungen: die alte Textebene zaehlt nicht mehr.
    assert ergebnis.skipped == []
    # Die Originaldatei bleibt Byte fuer Byte unveraendert.
    assert quelle.read_bytes() == vorher

    doc = pymupdf.open(str(ziel))
    assert "Dachdecker" in doc[0].get_text()
    assert {span["type"] for span in doc[0].get_texttrace()} == {3}
    doc.close()


def test_tesseract_bekommt_tsv_als_option(tmp_path, monkeypatch):
    """Kein "tsv"-Argument: der mitgelieferte Sprachordner hat keine configs/.

    Tesseract liest ein abschliessendes "tsv" als Konfigurationsdatei aus dem
    tessdata-Ordner und bricht sonst mit "read_params_file: Can't open tsv" ab.
    """
    from pdfblack.core import ocr

    programm = tmp_path / "tesseract"
    programm.write_text("", encoding="utf-8")
    aufrufe: list[list[str]] = []

    class Ergebnis:
        returncode = 0
        stderr = b""

    def fake_run(befehl, **kwargs):
        aufrufe.append(befehl)
        Path(befehl[2]).with_suffix(".tsv").write_text(
            "level\tpage_num\n5\t1\n", encoding="utf-8"
        )
        return Ergebnis()

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    engine = ocr.TesseractEngine(language="deu", path=str(programm))
    assert engine.read_words(b"png", (10, 10)) == []

    befehl = aufrufe[0]
    assert "tsv" not in befehl
    assert befehl[befehl.index("-c") + 1] == "tessedit_create_tsv=1"
    assert befehl[befehl.index("--tessdata-dir") + 1] == str(ocr.TESSDATA)
