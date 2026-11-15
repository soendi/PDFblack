"""Text aus PDF-Seiten lesen und Zeichenpositionen auf Rechtecke abbilden.

Presidio liefert Zeichen-Offsets (start/end) in einem Text. Damit daraus
physische Schwaerzungsflaechen werden, wird der Seitentext aus den Worten von
PyMuPDF zusammengesetzt und parallel die Position jedes Wortes gemerkt.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

from .models import PdfPasswordError, Rect

# Ab dieser Luecke (in PDF-Punkten) gelten zwei Woerter als getrennt.
_MERGE_GAP = 2.5


@dataclass(slots=True)
class WordBox:
    text: str
    start: int
    end: int
    rect: Rect


@dataclass(slots=True)
class PageText:
    index: int
    text: str
    width: float
    height: float
    words: list[WordBox]


def open_document(path: str, password: str | None = None) -> pymupdf.Document:
    """PDF oeffnen und - falls noetig - entschluesseln."""
    doc = pymupdf.open(path)
    if doc.needs_pass:
        if not password:
            doc.close()
            raise PdfPasswordError("Die PDF-Datei ist passwortgeschuetzt.")
        if not doc.authenticate(password):
            doc.close()
            raise PdfPasswordError("Das eingegebene Passwort ist falsch.")
    if doc.page_count == 0:
        doc.close()
        raise ValueError("Die PDF-Datei enthaelt keine Seiten.")
    return doc


def merge_rects(rects: list[Rect]) -> list[Rect]:
    """Waagerecht benachbarte Rechtecke einer Zeile zu einem Kasten verbinden."""
    merged: list[Rect] = []
    for rect in sorted(rects, key=lambda r: (round(r[1], 1), r[0])):
        placed = False
        for i, box in enumerate(merged):
            same_line = abs(box[1] - rect[1]) < 2.0 and abs(box[3] - rect[3]) < 2.0
            touches = rect[0] - box[2] <= _MERGE_GAP and rect[0] >= box[0] - 0.5
            if same_line and touches:
                merged[i] = (
                    box[0],
                    min(box[1], rect[1]),
                    max(box[2], rect[2]),
                    max(box[3], rect[3]),
                )
                placed = True
                break
        if not placed:
            merged.append(rect)
    return merged


class TextMap:
    """Zwischenspeicher fuer den Text und die Wortkoordinaten aller Seiten."""

    def __init__(self, doc: pymupdf.Document) -> None:
        self._doc = doc
        self._pages: dict[int, PageText] = {}

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def page(self, index: int) -> PageText:
        cached = self._pages.get(index)
        if cached is not None:
            return cached
        page = self._doc[index]
        words: list[WordBox] = []
        parts: list[str] = []
        cursor = 0
        last_line: tuple[int, int] | None = None
        for entry in page.get_text("words"):
            x0, y0, x1, y1, word = entry[0], entry[1], entry[2], entry[3], entry[4]
            block_no = int(entry[5]) if len(entry) > 5 else 0
            line_no = int(entry[6]) if len(entry) > 6 else 0
            word = word.strip()
            if not word:
                continue
            if parts:
                # Zeilenumbrueche bleiben erhalten: das NER-Modell und die
                # Muster erkennen Zusammenhaenge je Zeile deutlich besser.
                separator = "\n" if (block_no, line_no) != last_line else " "
                parts.append(separator)
                cursor += len(separator)
            last_line = (block_no, line_no)
            start = cursor
            parts.append(word)
            cursor += len(word)
            words.append(
                WordBox(
                    text=word,
                    start=start,
                    end=cursor,
                    rect=(float(x0), float(y0), float(x1), float(y1)),
                )
            )
        result = PageText(
            index=index,
            text="".join(parts),
            width=page.rect.width,
            height=page.rect.height,
            words=words,
        )
        self._pages[index] = result
        return result

    def rects_for(self, index: int, start: int, end: int) -> list[Rect]:
        """Alle Wortkaesten, die den Zeichenbereich beruehren."""
        if end <= start:
            return []
        page = self.page(index)
        hits = [w.rect for w in page.words if w.end > start and w.start < end]
        return merge_rects(hits)
