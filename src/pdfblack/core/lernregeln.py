"""Lerndatei in feste Regeln ueberfuehren.

Die Beispiele aus der Lerndatei gelten vorlaeufig. Was sich daraus als Muster
ableiten laesst, schreibt ``tools/lerndatei_regeln.py`` als Daten in
``core/gelernt.py``; diese Regeln greifen danach ohne Lerndatei. Alles, was
sich nicht sauber verallgemeinern laesst, steht im Bericht des Werkzeugs unter
"offen" - und im Lernfenster in der Spalte "im Code".

Musterableitung: Ziffernfolgen im Text werden zu ``\\d+``, alles andere bleibt
woertlich. ``IAO-4711`` und ``IAO-2233`` ergeben so das gemeinsame Muster
``IAO-\\d+``. Ein Beispiel ohne Gegenstueck bleibt Einzelfall und wird nur
woertlich uebernommen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import gelernt, lerndatei
from .models import Category, Finding

# Kuerzere Texte taugen nicht als Regel: sie wuerden zu viel treffen.
MINDESTLAENGE = 3

_ZAHL = re.compile(r"(\d+)")


def _grenzen(quelle: str) -> str:
    """Muster nur auf ganze Ausdruecke anwenden, nicht mitten im Wort."""
    return rf"(?<![\w]){quelle}(?![\w])"


# Einmal beim Import uebersetzen - die Regeln stehen fest im Code.
_AUSGESCHLOSSEN: tuple[re.Pattern[str], ...] = tuple(
    re.compile(_grenzen(muster), re.IGNORECASE) for muster in gelernt.AUSGESCHLOSSEN
)
_ZUGEORDNET: tuple[tuple[re.Pattern[str], Category], ...] = tuple(
    (re.compile(_grenzen(muster), re.IGNORECASE), kategorie)
    for muster, kategorie in gelernt.ZUGEORDNET
)


@dataclass(frozen=True)
class Vorschlag:
    """Ein Muster mit Ziel und den Beispielen, aus denen es entstand."""

    muster: str
    kategorie: Category | None  # None = Fehlalarm
    vorher: str
    beispiele: tuple[str, ...]


@dataclass
class Auswertung:
    """Ergebnis der Auswertung: uebernehmbare Muster und offene Beispiele."""

    muster: list[Vorschlag] = field(default_factory=list)
    einzelfaelle: list[Vorschlag] = field(default_factory=list)
    offen: list[tuple[dict, str]] = field(default_factory=list)
    gesamt: int = 0


def _normalisiert(text: object) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())


def _ziel(eintrag: dict) -> tuple[bool, Category | None]:
    """Ziel eines Beispiels: ``(True, Kategorie)`` oder ``(True, None)`` fuer
    Fehlalarm; ``(False, None)`` bei unbekannter Kategorie."""
    nachher = eintrag.get("kategorie_nachher")
    if not isinstance(nachher, str) or not nachher:
        return False, None
    if nachher == lerndatei.KEIN_TREFFER:
        return True, None
    for category in Category:
        if category.value == nachher:
            return True, category
    return False, None


def _rumpf(text: str) -> str:
    """Musterkern: Ziffernfolgen allgemein, alles andere woertlich."""
    teile: list[str] = []
    for stueck in _ZAHL.split(text):
        if not stueck:
            continue
        teile.append(r"\d+" if stueck.isdigit() else re.escape(stueck))
    return "".join(teile)


def _ablehnung(eintrag: dict, text: str, ziele: dict[str, set[str]]) -> str | None:
    """Grund, warum ein Beispiel keine feste Regel werden kann."""
    if not text:
        return "Text fehlt"
    if len(text) < MINDESTLAENGE:
        return "Text zu kurz für eine Regel"
    if not _ziel(eintrag)[0]:
        return "Kategorie unbekannt"
    if len(ziele.get(text, ())) > 1:
        return "widersprüchliche Beispiele zum selben Text"
    quelle = str(eintrag.get("quelle") or "")
    if quelle.lower().startswith("manuell") or eintrag.get("entity") in (
        "MANUAL",
        "REGEX",
    ):
        return "manuell eingegeben oder eigene Regex"
    if not _ZAHL.sub("", text).strip(" -_/.,:"):
        return "Text besteht nur aus Ziffern"
    return None


def auswerten(beispiele: list[dict]) -> Auswertung:
    """Beispiele in Muster, Einzelfaelle und offene Stellen sortieren."""
    ergebnis = Auswertung(gesamt=len(beispiele))

    ziele: dict[str, set[str]] = {}
    for eintrag in beispiele:
        text = _normalisiert(eintrag.get("text"))
        erfolg, ziel = _ziel(eintrag)
        if erfolg and text:
            ziele.setdefault(text, set()).add("" if ziel is None else ziel.value)

    gruppen: dict[tuple[str, str, str], list[tuple[str, dict]]] = {}
    for eintrag in beispiele:
        text = _normalisiert(eintrag.get("text"))
        grund = _ablehnung(eintrag, text, ziele)
        if grund is not None:
            ergebnis.offen.append((eintrag, grund))
            continue
        _, ziel = _ziel(eintrag)
        vorher = str(eintrag.get("kategorie_vorher") or "")
        schluessel = ("" if ziel is None else ziel.value, vorher, _rumpf(text))
        gruppen.setdefault(schluessel, []).append((text, eintrag))

    # Derselbe Musterkern mit verschiedenen Zielen ist nicht eindeutig.
    ziele_je_rumpf: dict[str, set[str]] = {}
    for ziel_name, _vorher, rumpf in gruppen:
        ziele_je_rumpf.setdefault(rumpf, set()).add(ziel_name)

    for (ziel_name, vorher, rumpf), eintraege in gruppen.items():
        if len(ziele_je_rumpf[rumpf]) > 1:
            for _text, eintrag in eintraege:
                ergebnis.offen.append(
                    (eintrag, "Muster mit widersprüchlichen Zielen")
                )
            continue
        texte = tuple(dict.fromkeys(text for text, _ in eintraege))
        ziel = None if ziel_name == "" else _ziel_hart(ziel_name)
        if r"\d+" in rumpf and len(texte) >= 2:
            ergebnis.muster.append(Vorschlag(rumpf, ziel, vorher, texte))
        else:
            ergebnis.einzelfaelle.append(
                Vorschlag(re.escape(texte[0]), ziel, vorher, texte)
            )

    ergebnis.muster.sort(key=lambda v: (v.kategorie is None, v.muster))
    ergebnis.einzelfaelle.sort(key=lambda v: v.beispiele[0].casefold())
    return ergebnis


def _ziel_hart(name: str) -> Category:
    """Kategoriename aus einem bereits geprueften Beispiel."""
    for category in Category:
        if category.value == name:
            return category
    raise ValueError(f"Unbekannte Kategorie: {name}")


def _ziel_text(kategorie: Category | None) -> str:
    return "Fehlalarm (nicht schwärzen)" if kategorie is None else kategorie.value


def bericht(auswertung: Auswertung) -> str:
    """Lesbarer Bericht: was uebernommen wird und was offen bleibt."""
    einzelne = len(auswertung.einzelfaelle)
    zeilen = [
        f"{auswertung.gesamt} Beispiele · {len(auswertung.muster)} Muster · "
        f"{einzelne} {'Einzelfall' if einzelne == 1 else 'Einzelfälle'} · "
        f"{len(auswertung.offen)} offen",
        "",
    ]
    if auswertung.muster:
        zeilen.append("Muster (gelten danach ohne Lerndatei):")
        for vorschlag in auswertung.muster:
            zeilen.append(
                f"  {vorschlag.muster}  ->  {_ziel_text(vorschlag.kategorie)}"
                f"   [{', '.join(vorschlag.beispiele)}]"
            )
    else:
        zeilen.append(
            "Muster: keine - für ein Muster braucht es zwei Beispiele mit "
            "gleichem Aufbau (z. B. IAO-4711 und IAO-2233)."
        )
    zeilen.append("")
    if auswertung.einzelfaelle:
        zeilen.append("Einzelfälle (wörtlich, nur mit --einzelfaelle übernehmen):")
        for vorschlag in auswertung.einzelfaelle:
            zeilen.append(
                f"  {vorschlag.beispiele[0]}  ->  {_ziel_text(vorschlag.kategorie)}"
            )
    else:
        zeilen.append("Einzelfälle: keine")
    zeilen.append("")
    if auswertung.offen:
        zeilen.append("Offen (nicht übernehmbar):")
        for eintrag, grund in auswertung.offen:
            text = _normalisiert(eintrag.get("text")) or "(ohne Text)"
            zeilen.append(f"  {text}  –  {grund}")
    else:
        zeilen.append("Offen: nichts")
    return "\n".join(zeilen)


def _beispiele_text(vorschlag: Vorschlag) -> str:
    """Beispiele als Kommentarzeile im erzeugten Modul."""
    text = " | ".join(_normalisiert(beispiel) for beispiel in vorschlag.beispiele)
    return text if len(text) <= 100 else text[:97] + "..."


def modul(vorschlaege: list[Vorschlag], quelle: str) -> str:
    """Quelltext fuer ``core/gelernt.py`` bauen."""
    ausgeschlossen = [v for v in vorschlaege if v.kategorie is None]
    zugeordnet = [v for v in vorschlaege if v.kategorie is not None]
    zeilen = [
        '"""Feste Regeln aus der Lerndatei - erzeugt von tools/lerndatei_regeln.py.',
        "",
        "Nicht von Hand aendern: neue Beispiele in die Lerndatei aufnehmen, die",
        "exportierte Datei mit dem Werkzeug einlesen und dieses Modul neu erzeugen.",
        "Die Muster greifen danach ohne Lerndatei.",
        "",
        f"Quelle: {quelle}",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from .models import Category",
        "",
        "# Fehlalarme: passt ein Treffer auf eines dieser Muster, wird er nicht",
        "# geschwaerzt.",
    ]
    aus = []
    for vorschlag in ausgeschlossen:
        aus.append(f"    # Beispiele: {_beispiele_text(vorschlag)}")
        aus.append(f"    {_literal(vorschlag.muster)},")
    zeilen += _block("AUSGESCHLOSSEN: tuple[str, ...]", aus)
    zeilen.append("")
    zeilen.append("# Zuordnung: Muster -> Kategorie.")
    zu = []
    for vorschlag in zugeordnet:
        zu.append(f"    # Beispiele: {_beispiele_text(vorschlag)}")
        zu.append(
            f"    ({_literal(vorschlag.muster)}, Category.{vorschlag.kategorie.name}),"
        )
    zeilen += _block("ZUGEORDNET: tuple[tuple[str, Category], ...]", zu)
    zeilen.append("")
    return "\n".join(zeilen)


def _block(kopf: str, eintraege: list[str]) -> list[str]:
    """Zuweisung mit Eintraegen; ohne Eintraege als leeres Tupel."""
    if not eintraege:
        return [f"{kopf} = ()"]
    return [f"{kopf} = ("] + eintraege + [")"]


def _literal(muster: str) -> str:
    """Muster als Python-Literal - am lesbarsten als Raw-String."""
    if not muster.endswith("\\") and '"' not in muster:
        return f'r"{muster}"'
    if not muster.endswith("\\") and "'" not in muster:
        return f"r'{muster}'"
    return repr(muster)


def _passt(muster: re.Pattern[str], text: str) -> bool:
    return muster.search(" ".join(text.split())) is not None


def anwenden(findings: list[Finding]) -> list[Finding]:
    """Feste Regeln auf die Treffer anwenden - ohne Lerndatei.

    Ein Treffer, der auf ein ausgeschlossenes Muster passt, wird nicht mehr
    angehakt; ein Treffer mit zugeordnetem Muster bekommt diese Kategorie.
    Manuell eingegebene Werte und eigene Regex-Treffer bleiben unangetastet.
    """
    if not _AUSGESCHLOSSEN and not _ZUGEORDNET:
        return findings
    for finding in findings:
        if finding.entity == "MANUAL" or finding.category is Category.REGEX:
            continue
        if any(_passt(muster, finding.text) for muster in _AUSGESCHLOSSEN):
            finding.enabled = False
            if "im Code" not in finding.source:
                finding.source = f"{finding.source} · im Code: Fehlalarm".lstrip(" ·")
            continue
        for muster, kategorie in _ZUGEORDNET:
            if finding.category is kategorie or not _passt(muster, finding.text):
                continue
            finding.source = (
                f"{finding.source} · im Code: {kategorie.value}".lstrip(" ·")
            )
            finding.category = kategorie
            finding.entity = "GELERNT"
            break
    return findings


def abgedeckt(eintrag: dict) -> bool:
    """Steckt dieses Beispiel schon in einer festen Regel im Code?"""
    text = _normalisiert(eintrag.get("text"))
    if not text:
        return False
    nachher = eintrag.get("kategorie_nachher")
    if nachher == lerndatei.KEIN_TREFFER:
        return any(_passt(muster, text) for muster in _AUSGESCHLOSSEN)
    return any(
        kategorie.value == nachher and _passt(muster, text)
        for muster, kategorie in _ZUGEORDNET
    )


__all__ = [
    "MINDESTLAENGE",
    "Auswertung",
    "Vorschlag",
    "abgedeckt",
    "anwenden",
    "auswerten",
    "bericht",
    "modul",
]
