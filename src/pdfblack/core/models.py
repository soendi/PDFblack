"""Gemeinsame Datenmodelle fuer PDFblack."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

Rect = tuple[float, float, float, float]


class Category(str, Enum):
    """Kategorie eines Treffers - bestimmt Farbe und Beschriftung."""

    PERSON = "Person"
    ADDRESS = "Adresse"
    COMPANY = "Firma"
    POSTAL = "PLZ / Ort"
    ID = "Nummer / ID"
    CONTACT = "Kontakt"
    BANK = "Bank / Karte"
    DATE = "Datum"
    MANUAL = "Manuell"
    REGEX = "Regex"
    OTHER = "Sonstiges"

    @property
    def color(self) -> str:
        return _COLORS[self]


_COLORS: dict[Category, str] = {
    Category.PERSON: "#ff5d5d",
    Category.ADDRESS: "#ff9f45",
    Category.COMPANY: "#f7a8b8",
    Category.POSTAL: "#ffd43b",
    Category.ID: "#4dabf7",
    Category.CONTACT: "#a78bfa",
    Category.BANK: "#2fd6a5",
    Category.DATE: "#ff8cc8",
    Category.MANUAL: "#f03e3e",
    Category.REGEX: "#22c55e",
    Category.OTHER: "#9aa3b2",
}


class PdfPasswordError(RuntimeError):
    """Die PDF-Datei ist verschluesselt und das Passwort fehlt oder ist falsch."""


@dataclass
class Finding:
    """Ein einzelner Treffer, der geschwaerzt werden kann."""

    text: str
    category: Category
    page: int
    rects: list[Rect] = field(default_factory=list)
    source: str = ""
    entity: str = ""
    score: float = 1.0
    enabled: bool = True
    uid: int = 0

    @property
    def page_label(self) -> str:
        return str(self.page + 1)

    @property
    def display_text(self) -> str:
        text = " ".join(self.text.split())
        return text if len(text) <= 160 else text[:157] + "..."
