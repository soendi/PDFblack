"""Plausibilitaetspruefung gefundener Werte.

Die Pruefung schwaerzt nichts und aendert keinen Treffer. Sie liefert nur einen
kurzen Hinweis, wenn ein Wert in sich nicht stimmt: eine IBAN mit falscher
Pruefziffer, ein Datum wie "09.0.2022", eine PLZ, die es nicht gibt, oder eine
Strasse, die nicht im Verzeichnis steht. Gedacht als zweite Meinung neben dem
OCR - ein falsch gelesener Wert faellt damit in der Trefferliste auf.
"""

from __future__ import annotations

import datetime
import re

from . import plz as plz_verzeichnis
from . import strassen as strassen_verzeichnis
from .models import Category

# Nur echte IBAN-Formen pruefen, keine Nummern mit Buchstaben davor.
_IBAN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$")
_DATUM = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$")
_HAUSNUMMER_REST = re.compile(r"\s*\d.*$", re.DOTALL)
# PLZ vor Ort; die Zahl muss vollstaendig sein, sonst wuerde aus "82140"
# die Schweizer PLZ "8214" mit dem Ort "0 Olching".
_PLZ_ORT = re.compile(r"^(?:(?:CH|FL)[- ]*)?(\d{4,5})(?!\d)[ \t]+(\S.*)$")

# Regel-Kennungen, deren Treffer einen Strassennamen liefern.
STRASSEN_REGELN = frozenset(
    {"street", "street_name", "street_split", "street_name_split"}
)


def iban_gueltig(text: str) -> bool | None:
    """Pruefziffer nach ISO 13616 (Mod 97). None = keine IBAN."""
    roh = re.sub(r"\s", "", text).upper()
    if not _IBAN.match(roh):
        return None
    verdreht = roh[4:] + roh[:4]
    try:
        ziffern = "".join(str(int(zeichen, 36)) for zeichen in verdreht)
    except ValueError:
        return False
    return int(ziffern) % 97 == 1


def datum_gueltig(text: str) -> bool | None:
    """Echtes Kalenderdatum? None = sieht nicht wie ein Datum aus."""
    treffer = _DATUM.match(text.strip())
    if treffer is None:
        return None
    tag, monat, jahr = (int(gruppe) for gruppe in treffer.groups())
    if not 1900 <= jahr <= 2100:
        return False
    try:
        datetime.date(jahr, monat, tag)
    except ValueError:
        return False
    return True


def _plz_hinweis(text: str) -> str:
    treffer = _PLZ_ORT.match(text.strip())
    if treffer is None:
        return ""
    code, ort = treffer.group(1), treffer.group(2).strip()
    # Fuenfstellige Nummern sind deutsche oder oesterreichische PLZ; dafuer
    # fuehrt das Programm keine Liste.
    if len(code) != 4:
        return ""
    if not plz_verzeichnis.is_postal_code(code):
        return f"PLZ {code} steht nicht im Schweizer Verzeichnis"
    if ort and not plz_verzeichnis.is_place(code, ort):
        return f"\u201e{ort}\u201c gehoert nicht zur PLZ {code}"
    return ""


def _strasse_hinweis(text: str) -> str:
    name = _HAUSNUMMER_REST.sub("", text).strip(" .,;:")
    if not name or not strassen_verzeichnis.verfuegbar():
        return ""
    # "Haupt strasse" ist dieselbe Strasse wie "Hauptstrasse".
    for kandidat in (name, name.replace(" ", "")):
        if strassen_verzeichnis.ist_strasse(kandidat):
            return ""
    return f"\u201e{name}\u201c steht nicht im Strassenverzeichnis"


def hinweis(text: str, kategorie: Category, entity: str = "") -> str:
    """Kurzer Hinweis zu einem Treffer, oder "" wenn alles plausibel ist."""
    if kategorie in (Category.DATE, Category.BIRTHDATE):
        return (
            f"Datum \u201e{text}\u201c ist kein gueltiges Datum"
            if datum_gueltig(text) is False
            else ""
        )
    if kategorie is Category.BANK:
        return (
            "IBAN-Pruefziffer stimmt nicht"
            if iban_gueltig(text) is False
            else ""
        )
    if kategorie is Category.POSTAL:
        return _plz_hinweis(text)
    if kategorie is Category.ADDRESS and entity in STRASSEN_REGELN:
        return _strasse_hinweis(text)
    return ""


__all__ = [
    "STRASSEN_REGELN",
    "datum_gueltig",
    "hinweis",
    "iban_gueltig",
]
