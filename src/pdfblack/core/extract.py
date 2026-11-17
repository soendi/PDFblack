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
# Ab diesem waagerechten Abstand gelten zwei Woerter derselben Zeile als
# getrennte Spalten und bleiben durch einen Zeilenumbruch getrennt.
_SPALTEN_ABSTAND = 48.0


def _gleiche_zeile(
    vorher: tuple[float, float, float, float], jetzt: tuple[float, float, float, float]
) -> bool:
    """Stehen zwei Wortkaesten auf derselben sichtbaren Zeile?

    PyMuPDF gruppiert die Woerter nach Textbloecken: eine Hausnummer, die als
    eigener Block neben dem Strassennamen steht (Tabelle, rechtsbuendige
    Nummer, PLZ und Ort in zwei Feldern), bekommt eine andere Zeilennummer.
    Im zusammengesetzten Text stand dann ein Zeilenumbruch mitten in der
    Adresse, und die Regel fand nur den halben Treffer. Entscheidend ist die
    Lage auf der Seite: gleiche Hoehe und kein Spaltensprung dazwischen.
    """
    hoehe = min(vorher[3] - vorher[1], jetzt[3] - jetzt[1])
    if hoehe <= 0:
        return False
    ueberlappung = min(vorher[3], jetzt[3]) - max(vorher[1], jetzt[1])
    if ueberlappung < 0.5 * hoehe:
        return False
    return jetzt[0] - vorher[2] <= _SPALTEN_ABSTAND


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
        vorher: tuple[float, float, float, float] | None = None
        # Hinweis: Werte von Formularfeldern erscheinen in dieser PyMuPDF-
        # Fassung als normaler Seitentext - aber oft in eigenen Bloecken, also
        # in getrennten Zeilen.
        for entry in page.get_text("words"):
            x0, y0, x1, y1, word = entry[0], entry[1], entry[2], entry[3], entry[4]
            word = word.strip()
            if not word:
                continue
            box = (float(x0), float(y0), float(x1), float(y1))
            if parts:
                # Zeilenumbrueche bleiben erhalten: das NER-Modell und die
                # Muster erkennen Zusammenhaenge je Zeile deutlich besser.
                # Woerter derselben sichtbaren Zeile bleiben aber zusammen,
                # auch wenn sie aus verschiedenen Textbloecken stammen.
                separator = (
                    " " if vorher is not None and _gleiche_zeile(vorher, box) else "\n"
                )
                parts.append(separator)
                cursor += len(separator)
            vorher = box
            start = cursor
            parts.append(word)
            cursor += len(word)
            words.append(
                WordBox(
                    text=word,
                    start=start,
                    end=cursor,
                    rect=box,
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
