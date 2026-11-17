"""Regelbasierte Erkennung typisch deutscher Daten.

Diese Muster uebernehmen, was ein NER-Modell systematisch nicht zuverlaessig
findet: Strasse + Hausnummer, PLZ + Ort und Nummern hinter Schluesselwoertern
wie "Personalnummer" oder "Ausweisnummer".
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from . import berufe as berufs_liste
from . import plz as plz_liste
from . import strassen as strassen_verzeichnis
from .geburtsdatum import (
    JAHR_LANG_MUSTER,
    JAHR_MUSTER,
    LUECKE,
    MONAT_MUSTER,
    MONATNAMEN,
    TAG_MUSTER,
    ZAHL_MUSTER,
)
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
    # Nachtraegliche Pruefung des Treffers, z. B. gegen die amtliche PLZ-Liste.
    validate: Callable[[str], bool] | None = None


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
# Nach der Hausnummer darf kein ganzes Wort folgen: "Vorarbeiterin von 10
# Dachdecker" ist keine Adresse. Verbindungen wie "in 8000 Zuerich" bleiben
# erlaubt, damit Adressen mitten im Satz weiter gefunden werden.
_HOUSE_NEXT_OK = r"(?i:in|im|bei|an|am|zu|zum|zur|und|oder|bzw|sowie|wohnhaft)"
_HOUSE_END = (
    rf"(?![ \t]+(?!{_HOUSE_NEXT_OK}\b)"
    r"[A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df])"
)
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
    "gilt|umfasst|entspricht|gem|gemaeß|gemäß|inkl|zzgl|personalnummer|"
    "versichertennummer|ausweisnummer|kundennummer|vertragsnummer|mitgliedsnummer|"
    "aktenzeichen|geburtsdatum|datum|kennung|zeichen|obligation|police"
)
# Ortsnamen duerfen innen gross schreiben (Tour-de-Peilz, Bad Ragaz) und in
# schlecht gesetzten PDFs auch klein beginnen; die Stopwortliste faengt die
# haeufigen Fuellwoerter ab.
_CH_CITY_WORD = (
    r"[A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df\-'.]*"
)
# Vor der Zahl darf kein Bindestrich, Schraegstrich oder Viertelzeichen stehen:
# "4711-2233" und "PE-8842/2024" sind Nummern, keine Postleitzahlen.
_CH_PLZ_LEAD = r"(?<![\d\w\-/.'\u2019])"
_CH_PLZ = r"(?:1\d{3}|[2-9]\d{3})"
# Die amtliche Liste der Schweizer PLZ und Ortschaften (swisstopo + GeoNames,
# siehe core/plz.py) entscheidet, was eine Postleitzahl ist.
#
# Eine Jahreszahl liegt immer zwischen dem aktuellen Jahr und dem aktuellen
# Jahr minus 70 (2026 also 1956-2026); ausserhalb gibt es keine Jahreszahlen,
# dort ist eine vierstellige Zahl eine Postleitzahl. In diesem Jahresband
# muss zusaetzlich der Ort zur PLZ passen: "2000 Neuchatel" ist eine Adresse,
# "2026 Muster AG" nicht.
_JAHRE_ZURUECK = 70


def ist_jahreszahl(zahl: str) -> bool:
    """Liegt diese vierstellige Zahl im Jahresband (heute minus 70 bis heute)?"""
    if not (len(zahl) == 4 and zahl.isdigit()):
        return False
    jahr = int(zahl)
    heute = date.today().year
    return heute - _JAHRE_ZURUECK <= jahr <= heute


# Firmenname in der Zeile nach einer Jahreszahl ("2026" / "Muster AG").
_COMPANY_WORD = r"[A-Z\u00c4\u00d6\u00dc][\w\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df&\-'.]*"
_COMPANY_NAME = rf"{_COMPANY_WORD}(?:[ \t]+(?:{_COMPANY_WORD}|&)){{0,4}}"
# Ueberschriften und Angaben, die nach einer Jahreszahl stehen, aber keine
# Firma sind ("2026" / "Berufserfahrung").
_COMPANY_STOP = frozenset(
    {
        "berufserfahrung",
        "berufliche erfahrung",
        "ausbildung",
        "berufsbildung",
        "berufsmatura",
        "berufsmaturität",
        "berufsmaturitaet",
        "matura",
        "abitur",
        "studium",
        "studien",
        "praktikum",
        "lehre",
        "weiterbildung",
        "weiterbildungen",
        "umschulung",
        "schule",
        "gymnasium",
        "kantonsschule",
        "universität",
        "universitaet",
        "hochschule",
        "fachhochschule",
        "zertifikat",
        "zertifikate",
        "diplom",
        "bachelor",
        "master",
        "kenntnisse",
        "sprachen",
        "hobbys",
        "hobbies",
        "interessen",
        "profil",
        "referenzen",
        "kontakt",
        "adresse",
        "persönliche daten",
        "persoenliche daten",
        "persönliche angaben",
        "persoenliche angaben",
        "anlagen",
        "zeugnisse",
        "bewerbung",
        "lebenslauf",
        "anstellung",
        "teilzeit",
        "vollzeit",
        "heute",
        "seit",
        "bis",
        # Monate und Zeitwoerter: "2020 - 2020" / "Jahr" und
        # "22.04.2024" / "Mai" sind keine Firmen.
        "jahr",
        "jahre",
        "jahren",
        "monat",
        "monate",
        "januar",
        "februar",
        "märz",
        "maerz",
        "april",
        "mai",
        "juni",
        "juli",
        "august",
        "september",
        "oktober",
        "november",
        "dezember",
        # Abschluesse, die unter einer Jahreszahl stehen.
        "bachelor",
        "bachelor professional",
        "master",
        "master professional",
        "professional",
        "fachhochschulreife",
        "hochschulreife",
        "mittlere reife",
    }
)


def _firma_gueltig(text: str) -> bool:
    """Ist die Zeile unter der Zahl ein Firmenname?"""
    kopf, _, rest = text.partition("\n")
    name = rest.strip()
    if not name:
        return False
    klein = name.lower().strip(" .,;:")
    if klein in _COMPANY_STOP:
        return False
    # "5 0080" / "DE80" ist der Anfang einer IBAN, keine Firma.
    if re.fullmatch(r"[A-Z]{2}\d{2}", name.strip(" .,;:")):
        return False
    # "2024" / "Dachdecker" ist ein Beruf, keine Firma.
    if berufs_liste.ist_beruf(name):
        return False
    # "8045" / "Zürich" oder "1950" / "Sion" ist eine Adresse: dort passt
    # der Ort zur PLZ, das uebernimmt die PLZ-Regel.
    paar = plz_liste.plz_vor_ort(kopf)
    if (
        paar is not None
        and plz_liste.is_postal_code(paar[0])
        and plz_liste.is_place(paar[0], name)
    ):
        return False
    return True


def _plz_zeilenumbruch(text: str) -> bool:
    """PLZ und Ort stehen in zwei Zeilen.

    Das gilt nur, wenn der Ort wirklich zu dieser PLZ gehoert: "9435" /
    "Heerbrugg" ist eine Adresse. Eine Jahreszahl ist auf zwei Zeilen nie
    Postleitzahl - "2026" / "Muster AG" ist ein Jahr mit Firmennamen.
    """
    paar = plz_liste.plz_vor_ort(text)
    if paar is None:
        return False
    plz, ort = paar
    if not plz_liste.is_postal_code(plz):
        return False
    if ist_jahreszahl(plz):
        # Zwei Zeilen: eine Jahreszahl ist nie Postleitzahl.
        return False
    if not ort:
        ort = text[: text.find(plz)].strip(" \t\n")
    return plz_liste.is_place(plz, ort)


def _plz_gueltig(text: str) -> bool:
    """Steht in diesem Treffer eine amtliche PLZ mit passendem Ort?"""
    paar = plz_liste.plz_vor_ort(text)
    if paar is None:
        return False
    plz, ort = paar
    if not plz_liste.is_postal_code(plz):
        return False
    if not ist_jahreszahl(plz):
        return True
    if not ort:
        # Ort steht in der Zeile davor ("St. Margrethen\n9430").
        ort = text[: text.find(plz)].strip(" \t\n")
    return bool(ort) and plz_liste.is_place(plz, ort)

# Datumsangaben: Tag/Monat/Jahr (20.10.2026, 3. 12 1985, 12/03/1985,
# 12-3-85, 05/31/1990), Jahr zuerst (2026-10-20), Monatsnamen
# (20. Oktober 2026) und Monat/Jahr ohne Tag (10/2025, März 1985). Die
# Bausteine kommen aus geburtsdatum.py, damit Lesen und Erkennen dieselben
# Muster verwenden.
_DATE_DOTTED = (
    rf"{TAG_MUSTER}{LUECKE}\.{LUECKE}{MONAT_MUSTER}{LUECKE}\.?{LUECKE}{JAHR_MUSTER}"
)
_DATE_STRICH = (
    rf"{TAG_MUSTER}{LUECKE}[/\-]{LUECKE}{ZAHL_MUSTER}{LUECKE}[/\-]{LUECKE}"
    rf"{JAHR_MUSTER}"
)
_DATE_ISO = (
    rf"{JAHR_LANG_MUSTER}{LUECKE}[-./]{LUECKE}{MONAT_MUSTER}{LUECKE}[-./]{LUECKE}"
    rf"{TAG_MUSTER}"
)
# 20. Oktober 2026, 3. März 85 - Monatsnamen stehen in Bewerbungen oft
# statt der Zahlenform.
_DATE_WORT = (
    rf"(?<![\d\w]){TAG_MUSTER}{LUECKE}\.?{LUECKE}(?:{MONATNAMEN})\.?"
    rf"{LUECKE},?{LUECKE}{JAHR_MUSTER}(?![\d\w])"
)
# Zeitraeume aus Monat/Jahr: 05/2013 - 07/2013, 08/1997 – 07/1998,
# Maerz 2019 - Juni 2020. Ohne diese Alternative bliebe die ganze Spanne an
# der Telefonregel haengen, die aus "05/2013 – 07/2013" eine Nummer macht.
_DATE_MONTH_PART = (
    rf"(?:{MONAT_MUSTER}{LUECKE}[/\-]{LUECKE}{JAHR_MUSTER}"
    rf"|(?:{MONATNAMEN})\.?{LUECKE}{JAHR_MUSTER})"
)
_DATE_RANGE = (
    rf"(?<![\d\w]){_DATE_MONTH_PART}{LUECKE}[\-\u2013\u2014]{LUECKE}"
    rf"{_DATE_MONTH_PART}(?![\d\w])"
)
# Monat/Jahr ohne Tag: 10/2025, 1/85, 03-2025, 03.1985 und März 1985. Der
# Punkt gilt nur mit vierstelligem Jahr, damit ein Preis wie "12.34" kein
# Datum wird.
_DATE_MONTH = (
    rf"(?:(?<![\d\w./\-]){MONAT_MUSTER}{LUECKE}"
    rf"(?:[/\-]{LUECKE}{JAHR_MUSTER}|\.{LUECKE}{JAHR_LANG_MUSTER})"
    rf"(?![\d\w]|[./\-]{LUECKE}\d)"
    rf"|(?<![\d\w])(?:{MONATNAMEN})\.?{LUECKE}{JAHR_MUSTER}(?![\d\w]))"
)
_DATE_ANY = (
    rf"(?:{_DATE_RANGE}|{_DATE_ISO}|{_DATE_WORT}|{_DATE_DOTTED}|{_DATE_STRICH}|"
    rf"{_DATE_MONTH})"
)

def _telefon_gueltig(text: str) -> bool:
    """Mindestens sechs Ziffern: eine echte Nummer, kein Zahlenteil.

    Aus der Lerndatei: "0270", "0657", "0800", "08142" und "08731/"
    stehen mitten in IBANs, Handelsregistern und Klammern und sind keine
    Telefonnummern.
    """
    return len(re.sub(r"\D", "", text)) >= 6


_ID_SUFFIX = r"[. \t-]{0,2}(?:nummer|nr\.?|identifikationsnummer|id|zeichen|kennzeichen)"
_ID_STEMS = (
    r"personal|pers|ausweis|kunden|vertrags|mitglieds|versicherungs|versicherten|"
    r"sozialversicherungs|steuer|rentenversicherungs|fall|patienten|matrikel|"
    r"mitarbeiter|dokumenten|rechnungs|objekt|akten|geschaefts|kenn"
)
_ID_LABEL = (
    rf"(?:(?:{_ID_STEMS}){_ID_SUFFIX}|sv-?nummer|aktenzeichen|geschaeftszeichen|zeichen)"
)

# Einzelne Gattungsworte stehen im amtlichen Verzeichnis als Strassenname
# irgendeiner Gemeinde ("Ring", "Park", "Hof"). Allein im Text sind sie keine
# Adresse.
_GENERISCHE_STRASSEN = frozenset(
    {
        "allee",
        "berg",
        "blick",
        "damm",
        "feld",
        "gasse",
        "grund",
        "hain",
        "hof",
        "markt",
        "park",
        "platz",
        "ring",
        "steig",
        "strasse",
        "tor",
        "ufer",
        "weg",
        "zeile",
    }
)


def _strasse_bekannt(text: str) -> bool:
    """Steht der Name im amtlichen Strassenverzeichnis (core/strassen.py)?"""
    return (
        strassen_verzeichnis.ist_strasse(text)
        and strassen_verzeichnis.normalisiere(text) not in _GENERISCHE_STRASSEN
    )


RULES: tuple[Rule, ...] = (
    Rule(
        key="street",
        label="Stra\u00dfe + Hausnummer",
        group="address",
        category=Category.ADDRESS,
        pattern=rf"(?<!\w){_STREET_WORD}\.?[ \t]*{_HOUSE_NO}(?!\w){_HOUSE_END}",
    ),
    Rule(
        key="street_prep",
        label="Stra\u00dfe mit Vorsilbe",
        group="address",
        category=Category.ADDRESS,
        pattern=(
            rf"(?<!\w)(?:Am|An|Auf|Beim|Hinter|Im|In|Unter|Vor|Zum|Zur)[ \t]+"
            rf"(?:dem|der|den)?[ \t]*[A-Z\u00c4\u00d6\u00dc]{_CITY_PART}[ \t]+{_HOUSE_NO}(?!\w){_HOUSE_END}"
        ),
    ),
    Rule(
        key="street_name",
        label="Strassenname",
        group="address",
        category=Category.ADDRESS,
        # Ein Strassenname aus dem amtlichen Verzeichnis auch ohne Hausnummer.
        # Geprueft wird gegen die Liste, nicht gegen die Endung: "Kalkulation"
        # endet nicht wie eine Strasse, "Park" ist eine.
        pattern=rf"(?<![\w]){_STREET_WORD}(?![\w])",
        validate=_strasse_bekannt,
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
            rf"{_HOUSE_END}"
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
            # CH-9435 Heerbrugg und FL-9494 Schaan (Liechtenstein).
            rf"(?<!\w)(?i:CH|FL)[ \t]*[-\u2011]?[ \t]*{_CH_PLZ}(?!\d)"
            rf"(?:[ \t]+{_CH_CITY_WORD}){{0,3}}"
        ),
        validate=_plz_gueltig,
    ),
    Rule(
        key="ch_postal_city",
        label="Schweizer PLZ + Ort",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"{_CH_PLZ_LEAD}{_CH_PLZ}(?!\d)[ \t]+"
            rf"(?!(?i:{_CH_STOPWORDS})\b)"
            rf"{_CH_CITY_WORD}(?:[ \t]+{_CH_CITY_WORD}){{0,2}}"
        ),
        validate=_plz_gueltig,
    ),
    Rule(
        key="ch_postal_break",
        label="Schweizer PLZ (Ort in naechster Zeile)",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"{_CH_PLZ_LEAD}{_CH_PLZ}(?!\d)[ \t]*\n[ \t]*"
            rf"(?!(?i:{_CH_STOPWORDS})\b)"
            rf"{_CH_CITY_WORD}(?:[ \t]+{_CH_CITY_WORD}){{0,2}}"
        ),
        validate=_plz_zeilenumbruch,
    ),
    Rule(
        key="ch_postal_before",
        label="Schweizer PLZ (Ort in vorheriger Zeile)",
        group="ch_postal",
        category=Category.POSTAL,
        case_sensitive=True,
        pattern=(
            rf"(?:^|\n)[ \t]*(?!(?i:{_CH_STOPWORDS})\b){_CH_CITY_WORD}"
            rf"(?:[ \t]+{_CH_CITY_WORD}){{0,2}}[ \t]*\n[ \t]*{_CH_PLZ}(?!\d)"
        ),
        validate=_plz_zeilenumbruch,
    ),
    Rule(
        key="company_after_number",
        label="Firmenname unter einer Zahl",
        group="address",
        category=Category.COMPANY,
        case_sensitive=True,
        group_index=1,
        pattern=(
            # PLZ und Ort stehen immer in einer Zeile. Steht die Zahl allein
            # und darunter ein Name, ist die Zahl ein Jahr (im Jahresband)
            # oder eine PLZ, der Name aber eine Firma:
            # "2026" / "Muster AG" und "9435" / "Muster AG".
            rf"{_CH_PLZ_LEAD}{_CH_PLZ}(?!\d)[ \t]*\n[ \t]*"
            rf"({_COMPANY_NAME})"
        ),
        validate=_firma_gueltig,
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
        # Kuerzere Stuecke sind Nummernteile: "0270" aus einer IBAN,
        # "08142" aus einer Klammer, "0657" aus einem Handelsregister.
        validate=_telefon_gueltig,
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
        pattern=(
            rf"(?:Geburtsdatum|Geburtstag|geb\.|geboren[ \t]+am)[ \t]*:?[ \t]*"
            rf"{_DATE_ANY}"
        ),
    ),
    Rule(
        key="date",
        label="Datum",
        group="date",
        category=Category.DATE,
        pattern=(
            # 20.10.2026, 20.10.26, 20. 10. 2026, 3. 12 1985, 12/03/1985,
            # 12-3-85, ISO 2026-10-20, 20. Oktober 2026 und Monat/Jahr wie
            # 10/2025 oder Maerz 1985. Bewusst auch ohne Beschriftung:
            # Datumsangaben stehen in Kopfzeilen und Tabellen meist ohne
            # "Datum:" davor.
            rf"(?<![\d\w]){_DATE_ANY}(?![\d\w])"
        ),
    ),
    Rule(
        key="year",
        label="Jahr",
        group="year",
        category=Category.YEAR,
        # Allein stehende Jahreszahl ("2025", "1998"). Steht sie in einem
        # vollstaendigen Datum, gewinnt die laengere Datumsregel.
        pattern=r"(?<![\d\w])(?:19|20)\d{2}(?![\d\w])",
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
    "year",
)
