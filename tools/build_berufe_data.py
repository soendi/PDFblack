"""Baut die Liste deutscher Berufsbezeichnungen fuer PDFblack.

Quelle: Wikidata (CC0). Abgefragt werden Berufe mit deutschem Namen und, wo
hinterlegt, die weibliche Form (Eigenschaft P2521). Ergaenzt wird eine kurze
Liste gaengiger Berufe und Rollen, die in Wikidata fehlen oder anders heissen
(Dachdecker, Vorarbeiter, Staplerfahrer, Praktikant ...); fuer alle Eintraege
werden die weiblichen Formen zusaetzlich nach deutschen Endungen gebildet.

Aufruf:  python tools/build_berufe_data.py
Ergebnis: src/pdfblack/data/berufe.json
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SPARQL_URL = "https://query.wikidata.org/sparql"
ABFRAGE = """
SELECT DISTINCT ?de ?deF WHERE {
  ?item wdt:P31 ?typ .
  ?typ wdt:P279* wd:Q28640 .
  ?item rdfs:label ?de . FILTER(LANG(?de)="de")
  OPTIONAL { ?item wdt:P2521 ?deF . FILTER(LANG(?deF)="de") }
}
"""

ZIEL = Path(__file__).resolve().parents[1] / "src" / "pdfblack" / "data" / "berufe.json"

# Weibliche Formen, die keine Endung hergibt.
AUSNAHMEN = {
    "arzt": "ärztin",
    "tierarzt": "tierärztin",
    "zahnarzt": "zahnärztin",
    "kaufmann": "kauffrau",
    "kaufmann für büromanagement": "kauffrau für büromanagement",
    "fachmann": "fachfrau",
    "zimmermann": "zimmerin",
    "koch": "köchin",
    "bote": "botin",
    "wirt": "wirtin",
    "landwirt": "landwirtin",
    "krankenpfleger": "krankenpflegerin",
    "schornsteinfeger": "schornsteinfegerin",
    "pförtner": "pförtnerin",
    "gärtner": "gärtnerin",
    "tischler": "tischlerin",
    "maler": "malerin",
}

# Gaengige Berufe und Rollen aus Bewerbungen und Arbeitszeugnissen, in der
# maennlichen Form. Die weibliche Form entsteht unten automatisch.
BERUFE = (
    # Bau, Handwerk, Technik
    "Dachdecker", "Maurer", "Zimmermann", "Schreiner", "Tischler", "Bauhelfer",
    "Bauarbeiter", "Gerüstbauer", "Betonbauer", "Fliesenleger", "Maler", "Lackierer",
    "Elektriker", "Elektroinstallateur", "Sanitärinstallateur", "Heizungsbauer",
    "Anlagenmechaniker", "Mechatroniker", "Industriemechaniker", "Zerspanungsmechaniker",
    "Werkzeugmacher", "Schlosser", "Metallbauer", "Konstruktionsmechaniker",
    "Maschinenbediener", "Maschinenführer", "Schweißer", "Dreher", "Fräser",
    "Kfz-Mechatroniker", "Kfz-Mechaniker", "Mechaniker", "Servicetechniker",
    "Wartungstechniker", "Instandhalter", "Hausmeister", "Gebäudetechniker",
    "Kältetechniker", "Schornsteinfeger", "Gärtner", "Landschaftsgärtner",
    "Reinigungskraft", "Gebäudereiniger", "Glasreiniger",
    # Logistik, Produktion, Lager
    "Lagerist", "Fachlagerist", "Staplerfahrer", "Gabelstaplerfahrer", "Kommissionierer",
    "Kraftfahrer", "Berufskraftfahrer", "Lkw-Fahrer", "Fahrer", "Kurier", "Bote",
    "Produktionsmitarbeiter", "Produktionshelfer", "Fertigungshelfer", "Montierer",
    "Qualitätsprüfer", "Prüfer", "Lagerleiter", "Schichtleiter",
    # Buero, Verwaltung, Kaufmaennisches
    "Sachbearbeiter", "Verwaltungsangestellter", "Bürokaufmann", "Industriekaufmann",
    "Einzelhandelskaufmann", "Großhandelskaufmann", "Bankkaufmann", "Buchhalter",
    "Bilanzbuchhalter", "Lohnbuchhalter", "Steuerfachangestellter", "Steuerberater",
    "Wirtschaftsprüfer", "Rechtsanwalt", "Notar", "Personalsachbearbeiter",
    "Personalreferent", "Assistent", "Assistenz", "Sekretär", "Empfangsmitarbeiter",
    "Telefonist", "Callcenteragent", "Kundenberater", "Vertriebsmitarbeiter",
    "Einkäufer", "Disponent", "Logistiker", "Archivar", "Bibliothekar",
    # IT
    "Informatiker", "Softwareentwickler", "Programmierer", "Entwickler",
    "Systemadministrator", "Netzwerkadministrator", "Datenbankadministrator",
    "IT-Support", "IT-Berater", "Webentwickler", "Fachinformatiker",
    "Anwendungsentwickler", "Systemintegrator", "Datenanalyst", "Data Scientist",
    "Softwarearchitekt", "Qualitätssicherer", "Tester", "Projektmanager",
    # Gesundheit, Pflege, Soziales
    "Pfleger", "Krankenpfleger", "Altenpfleger", "Gesundheits- und Krankenpfleger",
    "Krankenschwester", "Hebamme", "Arzt", "Facharzt", "Hausarzt", "Zahnarzt",
    "Tierarzt", "Apotheker", "Pharmazeut", "Erzieher", "Sozialarbeiter",
    "Sozialpädagoge", "Heilpädagoge", "Therapeut", "Physiotherapeut",
    "Ergotherapeut", "Logopäde", "Psychotherapeut", "Psychologe", "Betreuer",
    "Pflegehelfer", "Sanitäter", "Rettungssanitäter",
    # Bildung, Wissenschaft
    "Lehrer", "Dozent", "Trainer", "Ausbilder", "Professor", "Wissenschaftler",
    "Forscher", "Laborant", "Chemikant", "Chemiker", "Physiker", "Biologe",
    "Mathematiker", "Statistiker", "Geologe", "Archäologe",
    # Gastronomie, Lebensmittel, Handel
    "Koch", "Küchenhilfe", "Beikoch", "Kellner", "Barkeeper", "Barista",
    "Bäcker", "Konditor", "Metzger", "Fleischer", "Fachverkäufer", "Verkäufer",
    "Kaufmann", "Handelsfachwirt", "Filialleiter", "Ladenleiter", "Kassierer",
    "Friseur", "Kosmetiker", "Fußpfleger", "Masseur",
    # Sicherheit, Verkehr, Sonstiges
    "Sicherheitsmitarbeiter", "Wachmann", "Pförtner", "Feuerwehrmann", "Polizist",
    "Soldat", "Pilot", "Fluglotse", "Zugführer", "Lokführer", "Schaffner",
    "Landwirt", "Winzer", "Forstwirt", "Jäger", "Fischer", "Bergmann",
    # Rollen und Funktionen in Bewerbungen
    "Vorarbeiter", "Meister", "Schichtführer", "Teamleiter", "Gruppenleiter",
    "Abteilungsleiter", "Bereichsleiter", "Betriebsleiter", "Werkleiter",
    "Projektleiter", "Bauleiter", "Geschäftsführer", "Vorstand", "Inhaber",
    "Praktikant", "Auszubildender", "Azubi", "Lehrling", "Werkstudent",
    "Aushilfe", "Helfer", "Fachkraft", "Spezialist", "Experte", "Berater",
    "Referent", "Koordinator", "Assistant", "Praktikantin", "Bürokraft",
)

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def weibliche_form(titel: str) -> str | None:
    """Weibliche Form nach deutscher Endung, sonst None."""
    klein = titel.lower()
    if klein in AUSNAHMEN:
        return AUSNAHMEN[klein]
    for endung in ("er", "or", "ist", "ant", "ent", "eur", "oge", "ge"):
        if klein.endswith(endung):
            return titel + "in"
    # Neutrale Formen (Kraft, Hilfe, Assistenz, Support) gelten fuer beide.
    if klein.endswith(("kraft", "hilfe", "assistenz", "support", "personal")):
        return titel
    return None


def normalisiere(text: str) -> str:
    text = re.sub(r"\(.*?\)", " ", text.lower())
    text = re.sub(r"[^\wäöüß\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def lies_wikidata() -> list[tuple[str, str]]:
    url = SPARQL_URL + "?" + urllib.parse.urlencode({"query": ABFRAGE})
    anfrage = urllib.request.Request(
        url,
        headers={
            "Accept": "text/csv",
            "User-Agent": "PDFblack/1.2 (Berufsliste, Build-Werkzeug)",
        },
    )
    with urllib.request.urlopen(anfrage, timeout=180) as antwort:  # noqa: S310
        text = antwort.read().decode("utf-8-sig")
    return [
        ((zeile.get("de") or "").strip(), (zeile.get("deF") or "").strip())
        for zeile in csv.DictReader(io.StringIO(text))
    ]


def sammle() -> list[str]:
    namen: set[str] = set()

    def merke(titel: str) -> None:
        titel = titel.strip()
        if not titel or len(titel) > 60:
            return
        if re.search(r"[0-9()\[\]/]", titel):
            return
        if not titel[0].isupper():
            return
        if len(titel.split()) > 5:
            return
        namen.add(titel)

    for maennlich, weiblich in lies_wikidata():
        merke(maennlich)
        merke(weiblich)

    for titel in BERUFE:
        merke(titel)
        form = weibliche_form(titel)
        if form:
            merke(form)

    # Fuer alle Eintraege ohne vorhandene weibliche Form die Endung nutzen.
    for titel in list(namen):
        form = weibliche_form(titel)
        if form:
            namen.add(form)

    return sorted({normalisiere(titel) for titel in namen if normalisiere(titel)})


def main() -> int:
    berufe = sammle()
    daten = {
        "stand": "2026-11",
        "quellen": [
            "Wikidata, Berufe mit deutschem Namen und weiblicher Form "
            "(P2521), CC0",
            "eigene Liste gaengiger Berufe und Rollen (PDFblack)",
        ],
        "berufe": berufe,
    }
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(
        json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"{len(berufe)} Berufsbezeichnungen geschrieben ({ZIEL.stat().st_size / 1024:.0f} kB)")
    for probe in ("dachdecker", "dachdeckerin", "vorarbeiterin", "staplerfahrer",
                  "praktikantin", "sachbearbeiterin", "elektrikerin", "köchin"):
        print(probe, "->", probe in berufe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
