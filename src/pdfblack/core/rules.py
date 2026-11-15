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
    # Schweizer PLZ brauchen Gross-/Kleinschreibung, sonst wuerde jede Zahl
    # mit folgendem Substantiv als Ort gelten.
    case_sensitive: bool = False


_STREET_SUFFIX = (
    r"(?:stra\u00dfe|strasse|str|weg|allee|platz|ring|gasse|ufer|damm|steig|berg|"
    r"feld|hof|markt|park|graben|wall|chaussee|pfad|zeile|koppel|kamp|siedlung|"
    r"viertel|tor|grund|blick|hain)"
)
_STREET_WORD = rf"[A-Z\u00c4\u00d6\u00dc][\w\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-']*{_STREET_SUFFIX}"
_HOUSE_NO = r"\d{1,4}\s?[a-zA-Z]?(?:[-/]\d{1,4})?"

# Hausnummer hinter einem Strassennamen ohne deutsches Suffix
# ("Rue du Lac 12", "Unter den Linden 5", "Hafenpromenade 3a").
_HOUSE_NO_SHORT = r"\d{1,3}(?:[ \t]?[a-zA-Z])?(?:[ \t]?[-/][ \t]?\d{1,2})?"
_HOUSE_NO_STOP = (
    "insgesamt|gesamt|summe|betrag|saldo|total|netto|brutto|umsatz|mwst|steuer|"
    "durchwahl|abteilung|postfach|postleitzahl|plz|betreff|betrifft|police|unsere|"
    "unser|ihre|ihren|ihrem|wir|sie|uns|mich|dich|man|alle|jede|jeder|diese|dieser|"
    "seite|seiten|kapitel|artikel|position|anzahl|menge|stueck|stück|exemplare|"
    "pakete|paket|jahre|jahr|monate|monat|tage|tag|stunden|stunde|minuten|minute|"
    "uhr|prozent|rabatt|preis|stand|version|fassung|nummer|nr|zeile|zeilen|absatz|"
    "anlage|anlagen|punkt|punkte|rate|raten|posten|lieferung|sendung|eingang|"
    "ausgang|etage|zimmer|wohnung|telefon|tel|fax|mobil|kunden|kunde|rechnung|"
    "rechnungen|bestellung|bestellungen|auftrag|auftraege|aufträge|mitarbeiter|"
    "personen|kinder|erwachsene|gewicht|groesse|größe|breite|hoehe|höhe|laenge|"
    "länge|baujahr|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|"
    "januar|februar|maerz|märz|april|mai|juni|juli|august|september|oktober|"
    "november|dezember"
)
# Strassenname: ein Wort mit Grossbuchstaben, danach bis zu drei weitere Wörter
# oder kleine Verbindungswörter (Rue du Lac, Unter den Linden).
_HOUSE_STREET = (
    r"[A-Z\u00c4\u00d6\u00dc][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-']{2,}"
    r"(?:[ \t]+(?:[A-Z\u00c4\u00d6\u00dc][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-']+|"
    r"(?i:du|de|la|le|des|der|den|dem|am|an|auf|im|in|vor|unter|auf|op|van|von|"
    r"sur|sous|aux|zum|zur|bei|beim|ob|ueber|über))){0,3}"
)

_PLZ = r"(?:0[1-9]|[1-9]\d)\d{3}"
_CITY_PART = r"[\w\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df.\-]*"
_PLZ_PREFIXES = "am|an|auf|bei|im|in|ob|ueber|unter|vor|der|dem|den|zur|zum"

# --- Schweiz: vierstellige Postleitzahlen ---------------------------------
# Ein Ort nach der Zahl ist nur dann eine PLZ, wenn das Wort kein Betrag,
# keine Menge und keine Zeiteinheit ist ("1500 Franken", "1200 Stueck").
_CH_STOPWORDS = (
    "euro|eur|chf|franken|rappen|usd|dollar|stueck|stück|stk|stck|jahr|jahre|jahren|"
    "monat|monate|monaten|woche|wochen|tag|tage|tagen|stunde|stunden|minute|minuten|"
    "sekunde|sekunden|uhr|prozent|promille|million|millionen|milliarde|milliarden|"
    "tausend|artikel|position|positionen|rechnung|rechnungen|kunde|kunden|kundin|"
    "mitarbeiter|mitarbeitende|personen|seiten|mal|punkte|gramm|kilo|kilogramm|"
    "tonnen|meter|zentimeter|millimeter|kilometer|quadratmeter|kubikmeter|anzahl|"
    "nummer|nr|bestellungen|auftraege|aufträge|pakete|exemplare|einheiten|tage|"
    "stunden|jahresgehalt|betrag|summe|saldo|gutschrift|belastung|"
    # Fuegeworter, damit ein kleingeschriebener Ort nicht jede Zahl zur PLZ
    # macht ("9435 und 9430", "9435 bis 9440").
    "und|oder|bis|von|nach|aus|auf|in|im|am|an|mit|fuer|für|zum|zur|der|die|"
    "das|den|dem|des|ein|eine|einer|einem|eines|ist|sind|wird|werden|wurde|"
    "nicht|auch|samt|sowie|bzw|ca|etwa|etc|pro|je|betraegt|beträgt|kostet|"
    "gilt|umfasst|entspricht|gem|gemaeß|gemäß|inkl|zzgl"
)
# Ortsnamen duerfen innen gross schreiben (Tour-de-Peilz, Bad Ragaz) und in
# schlecht gesetzten PDFs auch klein beginnen; die Stopwortliste faengt die
# haeufigen Fuellwoerter ab.
_CH_CITY_WORD = (
    r"[A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df\-'.]*"
)
_CH_PLZ = r"(?:1\d{3}|[2-9]\d{3})"

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
        key="house_number",
        label="Hausnummer",
        group="address",
        category=Category.ADDRESS,
        case_sensitive=True,
        pattern=(
            rf"(?<![\w])(?!(?i:{_HOUSE_NO_STOP})\b){_HOUSE_STREET}[ \t]+"
            rf"{_HOUSE_NO_SHORT}(?![\w\u20ac%'\u2019])"
            # "Police 44-778" ist keine Hausnummer, "12-14" schon.
            rf"(?![ \t]?[-/][ \t]?\d{{3,}})"
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
        pattern=r"(?:PLZ|Postleitzahl)[ \t]*:?[ \t]*\d{4,5}(?!\d)",
    ),
    Rule(
        key="ch_postal_prefix",
        label="Schweizer PLZ (CH-8045)",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"(?<!\w)(?i:CH)[ \t]*[-\u2011]?[ \t]*{_CH_PLZ}(?!\d)"
            rf"(?:[ \t]+{_CH_CITY_WORD}){{0,3}}"
        ),
    ),
    Rule(
        key="ch_postal_city",
        label="Schweizer PLZ + Ort",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"(?<![\d\w]){_CH_PLZ}(?!\d)[ \t]+"
            rf"(?!(?i:{_CH_STOPWORDS})\b)"
            rf"{_CH_CITY_WORD}(?:[ \t]+{_CH_CITY_WORD}){{0,2}}"
        ),
    ),
    Rule(
        key="ch_postal_break",
        label="Schweizer PLZ (Ort in naechster Zeile)",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"(?<![\d\w]){_CH_PLZ}(?!\d)[ \t]*\n[ \t]*"
            rf"(?!(?i:{_CH_STOPWORDS})\b)"
            rf"{_CH_CITY_WORD}(?:[ \t]+{_CH_CITY_WORD}){{0,2}}"
        ),
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
            # Landesvorwahl (+49, +41, 0049, 0041) oder fuehrende 0
            r"(?<![\w])(?:\+\d{1,3}|00\d{1,3}|0)[ \t\-/]{0,3}"
            r"(?:\([ \t]?0[ \t]?\)[ \t\-/]{0,3})?"
            r"\d{2,5}(?:[ \t\-/]{0,4}\d{1,8}){1,4}(?!\w)"
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
    rule.key: re.compile(
        rule.pattern, re.UNICODE | (0 if rule.case_sensitive else re.IGNORECASE)
    )
    for rule in RULES
}


def compiled(rule: Rule) -> re.Pattern[str]:
    return _COMPILED[rule.key]


def rules_for_groups(groups: tuple[str, ...] | set[str] | frozenset[str]) -> list[Rule]:
    wanted = set(groups)
    return [rule for rule in RULES if rule.group in wanted]


ALL_GROUPS: tuple[str, ...] = (
    "address",
    "ch_postal",
    "id",
    "contact",
    "bank",
    "date",
)
