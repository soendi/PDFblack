"""Regelbasierte Erkennung typisch deutscher Daten.

Diese Muster uebernehmen, was ein NER-Modell systematisch nicht zuverlaessig
findet: Strasse + Hausnummer, PLZ + Ort und Nummern hinter Schluesselwoertern
wie "Personalnummer" oder "Ausweisnummer".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Category


@dataclass(frozen=True)
class Rule:
    """Ein benanntes Suchmuster."""

    key: str
    label: str
    group: str
    category: Category
    pattern: str
    group_index: int = 0


_STREET_SUFFIX = (
    r"(?:stra\u00dfe|strasse|str|weg|allee|platz|ring|gasse|ufer|damm|steig|berg|"
    r"feld|hof|markt|park|graben|wall|chaussee|pfad|zeile|koppel|kamp|siedlung|"
    r"viertel|tor|grund|blick|hain)"
)
_STREET_WORD = rf"[A-Z\u00c4\u00d6\u00dc][\w\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-']*{_STREET_SUFFIX}"
_HOUSE_NO = r"\d{1,4}\s?[a-zA-Z]?(?:[-/]\d{1,4})?"

_PLZ = r"(?:0[1-9]|[1-9]\d)\d{3}"
_CITY_PART = r"[\w\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-]*"
_PLZ_PREFIXES = "am|an|auf|bei|im|in|ob|ueber|unter|vor|der|dem|den|zur|zum"

_ID_SUFFIX = r"[. \t-]{0,2}(?:nummer|nr\.?|identifikationsnummer|id|zeichen|kennzeichen)"
_ID_STEMS = (
    r"personal|pers|ausweis|kunden|vertrags|mitglieds|versicherungs|versicherten|"
    r"sozialversicherungs|steuer|rentenversicherungs|fall|patienten|matrikel|"
    r"mitarbeiter|dokumenten|rechnungs|objekt|akten|geschaefts|kenn"
)
_ID_LABEL = (
    rf"(?:(?:{_ID_STEMS}){_ID_SUFFIX}|sv-?nummer|aktenzeichen|geschaeftszeichen|zeichen)"
)

RULES: tuple[Rule, ...] = (
    Rule(
        key="street",
        label="Stra\u00dfe + Hausnummer",
        group="address",
        category=Category.ADDRESS,
        pattern=rf"(?<!\w){_STREET_WORD}\.?[ \t]*{_HOUSE_NO}(?!\w)",
    ),
    Rule(
        key="street_prep",
        label="Stra\u00dfe mit Vorsilbe",
        group="address",
        category=Category.ADDRESS,
        pattern=(
            rf"(?<!\w)(?:Am|An|Auf|Beim|Hinter|Im|In|Unter|Vor|Zum|Zur)[ \t]+"
            rf"(?:dem|der|den)?[ \t]*[A-Z\u00c4\u00d6\u00dc]{_CITY_PART}[ \t]+{_HOUSE_NO}(?!\w)"
        ),
    ),
    Rule(
        key="postal_city",
        label="PLZ + Ort",
        group="address",
        category=Category.POSTAL,
        pattern=(
            rf"(?<!\d){_PLZ}[ \t]+[A-Z\u00c4\u00d6\u00dc]{_CITY_PART}"
            rf"(?:[ \t]+(?:{_PLZ_PREFIXES})[ \t]+[A-Z\u00c4\u00d6\u00dc]{_CITY_PART}"
            rf"|[ \t]+[A-Z\u00c4\u00d6\u00dc]{_CITY_PART})*"
        ),
    ),
    Rule(
        key="postal_label",
        label="PLZ",
        group="address",
        category=Category.POSTAL,
        pattern=r"(?:PLZ|Postleitzahl)[ \t]*:?[ \t]*\d{5}(?!\d)",
    ),
    Rule(
        key="id_number",
        label="Nummer / ID",
        group="id",
        category=Category.ID,
        pattern=(
            rf"(?:{_ID_LABEL})[ \t]*[:#]?[ \t]*"
            r"((?=[A-Za-z0-9\-/.]*\d)[A-Za-z0-9][A-Za-z0-9\-/.]{1,29})"
        ),
        group_index=1,
    ),
    Rule(
        key="email",
        label="E-Mail",
        group="contact",
        category=Category.CONTACT,
        pattern=r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]{2,})+",
    ),
    Rule(
        key="phone",
        label="Telefon",
        group="contact",
        category=Category.CONTACT,
        pattern=(
            r"(?<![\w])(?:\+49|0049|0)[ \t\-/]{0,3}(?:\([ \t]?0[ \t]?\)[ \t\-/]{0,3})?"
            r"\d{2,5}[ \t\-/]{0,4}\d{2,8}(?:[ \t\-/]{0,4}\d{1,6})?(?!\w)"
        ),
    ),
    Rule(
        key="iban",
        label="IBAN",
        group="bank",
        category=Category.BANK,
        pattern=r"(?<!\w)[A-Z]{2}\d{2}(?:[ \t]?[A-Z0-9]{4}){2,7}(?:[ \t]?[A-Z0-9]{1,4})?(?!\w)",
    ),
    Rule(
        key="birthday",
        label="Geburtsdatum",
        group="date",
        category=Category.DATE,
        pattern=r"(?:Geburtsdatum|Geburtstag|geb\.|geboren[ \t]+am)[ \t]*:?[ \t]*\d{1,2}\.[ \t]?\d{1,2}\.[ \t]?\d{2,4}",
    ),
)

_COMPILED: dict[str, re.Pattern[str]] = {
    rule.key: re.compile(rule.pattern, re.IGNORECASE | re.UNICODE) for rule in RULES
}


def compiled(rule: Rule) -> re.Pattern[str]:
    return _COMPILED[rule.key]


def rules_for_groups(groups: tuple[str, ...] | set[str] | frozenset[str]) -> list[Rule]:
    wanted = set(groups)
    return [rule for rule in RULES if rule.group in wanted]


ALL_GROUPS: tuple[str, ...] = ("address", "id", "contact", "bank", "date")
