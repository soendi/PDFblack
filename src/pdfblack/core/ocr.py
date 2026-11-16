"""OCR fuer Bildscans: unsichtbaren Text hinter das Bild legen.

Ein Bildscan enthaelt keinen Text, den PDFblack schwaerzen koennte. PDFocr
liest die Seite als Bild, laesst Tesseract die Woerter erkennen und legt sie
als **unsichtbaren** Text (Render-Modus 3) wieder in die Seite - unter dem
Bild (``overlay=False``) und genau in dem Rechteck, in dem das Wort im Bild
steht. Dadurch sitzt der Text deckungsgleich ueber dem Scan, und eine spaetere
Schwaerzung trifft dieselbe Stelle im Bild.

Neu einlesen: ``ocr_pdf(quelle, ziel, engine)``
"""

from __future__ import annotations

import os
import shutil
import string
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Protocol, Sequence

import pymupdf

from .extract import open_document
from .rechtschreibung import korrigiere_wort

# Aufloesung, in der die Seite fuer die Erkennung gerendert wird. 300 dpi ist
# der uebliche Wert fuer Scans; die Pixel werden mit genau diesem Faktor in
# PDF-Punkte zurueckgerechnet, damit Text und Bild deckungsgleich bleiben.
DPI = 300

# Ab so vielen Zeichen gilt eine Seite als Seite mit Text (kein Bildscan).
MINDEST_TEXT = 20

SPRACHEN: dict[str, str] = {
    "Deutsch": "deu",
    "Englisch": "eng",
    "Französisch": "fra",
    "Italienisch": "ita",
    "Deutsch + Englisch": "deu+eng",
}

# Mitgelieferte Sprachdatei (tessdata_fast, Apache-2.0). Tesseract wird immer
# auf diesen Ordner gezeigt (--tessdata-dir): die Erkennung laeuft damit offline
# und ohne Downloads. Eine Ausrichtungserkennung (osd) braucht PDFblack nicht.
TESSDATA = Path(__file__).resolve().parents[1] / "data" / "tessdata"

# Zeichen, die die eingebaute Schrift (Helvetica) sicher setzen kann.
_ERLAUBT = set(
    string.ascii_letters
    + string.digits
    + "äöüÄÖÜßéèêàâçîïôûùüñÄÖÜÉÈÀÂÇÎÔÛÙÑ"
    + " .,;:!?()[]{}/\\-–—&%+*=<>\"'’‚«»°²³€$@#~|_"
)

Progress = Callable[[int, int, str], bool]

# Schrift des Textlayers. Die Breiten kommen aus dem Font selbst - so passen
# auch Umlaute und ß genau in das Rechteck aus dem Bild.
_SCHRIFT = pymupdf.Font("helv")


class OcrError(RuntimeError):
    """Die Texterkennung konnte nicht ausgefuehrt werden."""


@dataclass(frozen=True)
class Word:
    """Ein erkanntes Wort mit seinem Rechteck im Bild (Pixel)."""

    text: str
    box: tuple[float, float, float, float]
    confidence: float = 0.0


@dataclass
class OcrResult:
    """Ergebnis eines Durchlaufs."""

    pages: int = 0
    words: int = 0
    characters: int = 0
    skipped: list[int] = field(default_factory=list)
    text: str = ""


class Engine(Protocol):
    """Was eine Erkennungs-Engine koennen muss."""

    name: str

    def available(self) -> bool: ...

    def read_words(self, png: bytes, size: tuple[int, int]) -> list[Word]: ...


def find_tesseract() -> str | None:
    """Pfad zu Tesseract suchen (Umgebungsvariable, PATH, Windows-Standard)."""
    eigen = os.environ.get("PDFBLACK_TESSERACT")
    if eigen and Path(eigen).exists():
        return eigen
    gefunden = shutil.which("tesseract")
    if gefunden:
        return gefunden
    kandidaten = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path("/usr/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
        Path("/opt/homebrew/bin/tesseract"),
    ]
    for pfad in kandidaten:
        if pfad.exists():
            return str(pfad)
    return None


def sprachen_mitgeliefert() -> set[str]:
    """Welche Sprachdateien PDFblack mitbringt?"""
    try:
        return {datei.stem for datei in TESSDATA.glob("*.traineddata")}
    except OSError:  # pragma: no cover - unlesbarer Ordner
        return set()


class TesseractEngine:
    """Tesseract ueber die Kommandozeile, Ausgabe als TSV mit Wortrechtecken."""

    name = "Tesseract"

    def __init__(
        self,
        language: str = "deu",
        path: str | None = None,
        tessdata: str | None = None,
    ) -> None:
        self.language = language
        self.path = path or find_tesseract()
        self.tessdata = tessdata

    def available(self) -> bool:
        return bool(self.path and Path(self.path).exists())

    def sprachdateien(self) -> list[str]:
        return [name for name in self.language.split("+") if name]

    def tessdata_dir(self) -> str | None:
        """Mitgelieferte Sprachdateien - sonst der Standardordner von Tesseract."""
        if self.tessdata:
            return str(self.tessdata)
        if set(self.sprachdateien()) <= sprachen_mitgeliefert():
            return str(TESSDATA)
        return None

    def read_words(self, png: bytes, size: tuple[int, int]) -> list[Word]:
        if not self.available():
            raise OcrError(
                "Tesseract wurde nicht gefunden. Bitte Tesseract-OCR installieren "
                "oder den Pfad in der Umgebungsvariablen PDFBLACK_TESSERACT setzen."
            )
        with tempfile.TemporaryDirectory(prefix="pdfblack-ocr-") as ordner:
            bild = Path(ordner) / "seite.png"
            bild.write_bytes(png)
            basis = Path(ordner) / "seite"
            befehl = [str(self.path), str(bild), str(basis)]
            tessdata = self.tessdata_dir()
            if tessdata:
                befehl += ["--tessdata-dir", tessdata]
            befehl += [
                "-l",
                self.language,
                "--psm",
                "3",
                # TSV als Option statt als Konfigurationsdatei "tsv": Tesseract
                # sucht Konfigurationsdateien im tessdata-Ordner, und der
                # mitgelieferte enthält nur die Sprachdatei (sonst meldet
                # Tesseract "read_params_file: Can't open tsv").
                "-c",
                "tessedit_create_tsv=1",
            ]
            try:
                ergebnis = subprocess.run(  # noqa: S603 - fester Aufruf
                    befehl,
                    capture_output=True,
                    timeout=300,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                raise OcrError(f"Tesseract liess sich nicht starten: {exc}") from exc
            except subprocess.TimeoutExpired as exc:
                raise OcrError("Tesseract hat zu lange gebraucht.") from exc
            datei = basis.with_suffix(".tsv")
            if not datei.exists():
                meldung = ergebnis.stderr.decode("utf-8", "replace").strip()
                if (
                    "Failed loading language" in meldung
                    or "couldn't load any languages" in meldung
                    or "tessdata" in meldung
                ):
                    raise OcrError(
                        f"Tesseract konnte die Sprache „{self.language}“ nicht "
                        "laden. Mitgeliefert ist Deutsch; andere Sprachen "
                        "brauchen die passende Tesseract-Installation."
                    )
                raise OcrError(
                    "Tesseract hat keine Ausgabe geliefert."
                    + (f" Meldung: {meldung}" if meldung else "")
                )
            return _lies_tsv(datei.read_text(encoding="utf-8", errors="replace"))


def _lies_tsv(inhalt: str) -> list[Word]:
    """Wortrechtecke aus der TSV-Ausgabe von Tesseract holen."""
    woerter: list[Word] = []
    zeilen = inhalt.splitlines()
    for zeile in zeilen[1:]:
        spalten = zeile.split("\t")
        if len(spalten) < 12 or spalten[0] != "5":
            continue
        text = spalten[11].strip()
        if not text:
            continue
        try:
            links, oben, breite, hoehe = (int(spalten[i]) for i in range(6, 10))
            sicherheit = float(spalten[10])
        except ValueError:
            continue
        if breite <= 0 or hoehe <= 0:
            continue
        woerter.append(
            Word(
                text=text,
                box=(float(links), float(oben), float(links + breite), float(oben + hoehe)),
                confidence=max(0.0, sicherheit) / 100.0,
            )
        )
    return woerter


def has_text(path: str, password: str | None = None, minimum: int = MINDEST_TEXT) -> bool:
    """Enthaelt die Datei irgendwo auswertbaren Text?

    Ein Bildscan hat keinen - dann uebernimmt PDFocr.
    """
    doc = open_document(path, password)
    try:
        for index in range(doc.page_count):
            if len(doc[index].get_text().strip()) >= minimum:
                return True
        return False
    finally:
        doc.close()


def render_page(page: pymupdf.Page, dpi: int = DPI) -> tuple[bytes, int, int]:
    """Seite als PNG rendern - in genau der Aufloesung, in der gerechnet wird."""
    pixmap = page.get_pixmap(dpi=dpi)
    return pixmap.tobytes("png"), pixmap.width, pixmap.height


def _sauber(text: str) -> str:
    """Nur Zeichen behalten, die die Schrift setzen kann."""
    sauber = "".join(zeichen for zeichen in text if zeichen in _ERLAUBT)
    return sauber.strip()


def place_words(page: pymupdf.Page, words: Sequence[Word], dpi: int = DPI) -> int:
    """Woerter unsichtbar und deckungsgleich hinter das Bild legen.

    Rueckgabe: Anzahl der eingesetzten Woerter.
    """
    if not words:
        return 0
    skalierung = dpi / 72.0
    rotation = page.rotation % 360
    gesetzt = 0
    for word in words:
        text = _sauber(word.text)
        if not text:
            continue
        x0, y0, x1, y1 = (wert / skalierung for wert in word.box)
        breite, hoehe = x1 - x0, y1 - y0
        if breite < 0.6 or hoehe < 2.0:
            continue
        schriftgroesse = max(1.5, hoehe * 0.82)
        gemessen = _SCHRIFT.text_length(text, fontsize=schriftgroesse)
        if gemessen <= 0:
            continue
        # Waagerecht genau auf das Rechteck aus dem Bild skalieren - sonst
        # liegt der Text nicht deckungsgleich ueber dem Scan.
        stauchung = max(0.2, min(5.0, breite / gemessen))
        basislinie = pymupdf.Point(x0, y1 - hoehe * 0.14)
        ziel = pymupdf.Rect(x0, y0, x1, y1)
        if rotation:
            # Gedrehte Seiten: Rechteck und Text mit der Seitenrotation drehen.
            basislinie = basislinie * page.derotation_matrix
            ziel = ziel * page.derotation_matrix
            basislinie = pymupdf.Point(ziel.x0, ziel.y1 - ziel.height * 0.14)
        try:
            page.insert_text(
                basislinie,
                text,
                fontsize=schriftgroesse,
                fontname="helv",
                render_mode=3,  # unsichtbar
                overlay=False,  # hinter dem Seiteninhalt, also hinter dem Bild
                morph=(basislinie, pymupdf.Matrix(stauchung, 1)),
                rotate=(360 - rotation) % 360,
            )
        except Exception:  # noqa: BLE001 - einzelnes Wort darf den Lauf nicht stoppen
            continue
        gesetzt += 1
    return gesetzt


def ocr_pdf(
    src: str,
    dst: str,
    engine: Engine,
    password: str | None = None,
    dpi: int = DPI,
    progress: Progress | None = None,
    rechtschreibung: bool = True,
) -> OcrResult:
    """Textlayer fuer einen Scan schreiben und unter ``dst`` speichern.

    Seiten, die bereits Text enthalten, bleiben unangetastet. Mit
    ``rechtschreibung`` laeuft vor dem Einsetzen eine konservative
    Woerterbuch-Korrektur ueber die erkannten Woerter.
    """
    if not engine.available():
        raise OcrError(
            "Tesseract wurde nicht gefunden. Bitte Tesseract-OCR installieren "
            "oder den Pfad in der Umgebungsvariablen PDFBLACK_TESSERACT setzen."
        )
    doc = open_document(src, password)
    ergebnis = OcrResult()
    try:
        gesamt = doc.page_count
        seiten: list[tuple[pymupdf.Page, list[Word]]] = []
        for index in range(gesamt):
            if progress and progress(index, gesamt, f"Seite {index + 1} von {gesamt}") is False:
                raise OcrError("Abgebrochen.")
            page = doc[index]
            vorhanden = page.get_text().strip()
            if len(vorhanden) >= MINDEST_TEXT:
                ergebnis.skipped.append(index)
                ergebnis.text += vorhanden + "\n"
                ergebnis.characters += len(vorhanden)
                continue
            png, breite, hoehe = render_page(page, dpi)
            seiten.append((page, engine.read_words(png, (breite, hoehe))))

        if rechtschreibung and seiten:
            # Ein Wort, das im Dokument mehrfach vorkommt, ist eher ein Name
            # als ein Tippfehler - die Haeufigkeit entscheidet mit.
            haeufig = Counter(
                wort.text for _, woerter in seiten for wort in woerter
            )
            korrigiert: list[tuple[pymupdf.Page, list[Word]]] = []
            for page, woerter in seiten:
                korrigiert.append(
                    (
                        page,
                        [
                            replace(
                                wort, text=korrigiere_wort(wort.text, haeufig[wort.text])
                            )
                            for wort in woerter
                        ],
                    )
                )
            seiten = korrigiert

        for page, woerter in seiten:
            gesetzt = place_words(page, woerter, dpi)
            ergebnis.pages += 1
            ergebnis.words += gesetzt
            seite_text = " ".join(word.text for word in woerter)
            ergebnis.characters += len(seite_text)
            ergebnis.text += seite_text + "\n"
        doc.save(
            dst,
            garbage=3,
            clean=True,
            deflate=True,
            deflate_fonts=True,
        )
    finally:
        doc.close()
    return ergebnis
