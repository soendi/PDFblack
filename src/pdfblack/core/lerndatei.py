"""Lerndatei: Korrekturen des Benutzers fuer die Datenerkennung.

Jede Korrektur in der Trefferliste landet als eine Zeile in einer JSONL-Datei
(ein JSON-Objekt pro Zeile, UTF-8). Die Datei ist zum Einlesen durch die
Weiterentwicklung gedacht, nicht zum Bearbeiten durch den Benutzer: Jede Zeile
nennt den gefundenen Text, die alte und die neue Kategorie, die Herkunft des
Treffers (z. B. ``KI (Presidio) · LOCATION``) und den Text davor und danach.
Daraus lassen sich Muster ableiten, die dann fest in die Erkennung wandern.

Ablage: ``<Benutzerordner>/PDFblack/lerndatei.jsonl`` - also *neben* dem
Ordner ``Geschwärt``, den die Ablage beim Beenden leert. Der Benutzerordner
selbst wird nie aufgeraeumt (abgesichert in ``tests/test_ablage.py``). Ueber
"Datei -> Lerndatei herunterladen ..." laesst sie sich an einen frei
waehlbaren Ort kopieren. Dateinamen der geprueften PDFs werden bewusst nicht
gespeichert - die Beispiele enthalten nur den Text rund um die Fundstelle.

Solange die Beispiele nicht fest im Programmcode stehen, wirken sie schon
beim naechsten Durchlauf: ``anwenden`` gibt einem Treffer die gelernte
Kategorie und hakt einen gelernten Fehlalarm nicht mehr an.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import Category, Finding

ORDNER = Path.home() / "PDFblack"
DATEI = ORDNER / "lerndatei.jsonl"
# Aufbau der Datei; steigt, wenn sich die Felder aendern.
FORMAT = 1
# So viele Zeichen Text stehen vor und hinter dem Treffer.
KONTEXT_ZEICHEN = 120

ART_KORREKTUR = "korrektur"
ART_KEIN_TREFFER = "kein_treffer"
# Reine Wertkorrektur (OCR hat ein Zeichen verschluckt): bleibt in der
# Lerndatei nachvollziehbar, taugt aber nicht als Musterbeispiel - sonst
# entstuende aus "09.01.2022" ein zusaetzliches Datums-Muster.
ART_WERTKORREKTUR = "wertkorrektur"
KEIN_TREFFER = "kein Treffer"


def _kopf() -> dict:
    """Erste Zeile der Datei: erklaert die Felder fuer die Weiterentwicklung."""
    return {
        "art": "kopf",
        "format": FORMAT,
        "programm": "PDFblack",
        "hinweis": (
            "Jede weitere Zeile ist ein Lernbeispiel: text = gefundener Ausdruck, "
            "kategorie_vorher = Einordnung der Software, kategorie_nachher = "
            "Einordnung des Benutzers (\"kein Treffer\" = Fehlalarm), kontext_vorher/"
            "kontext_nachher/zeile = Text um die Fundstelle, quelle/entity/score = "
            "Herkunft des Treffers, seite = Seitenzahl ab 1, "
            "gleichnamige_treffer = Anzahl der Treffer mit demselben Text, für "
            "die die Entscheidung gilt."
        ),
    }


def kontext(seite: str, text: str, zeichen: int = KONTEXT_ZEICHEN) -> dict[str, str]:
    """Text vor und hinter dem Treffer sowie die ganze Zeile der Fundstelle.

    Gesucht wird mit beliebigem Leerraum zwischen den Woertern, damit ein
    Treffer ueber einen Zeilenumbruch hinweg gefunden wird. Wird der Text auf
    der Seite nicht gefunden (etwa bei manuell markierten Bereichen), bleiben
    die Felder leer.
    """
    leer = {"kontext_vorher": "", "kontext_nachher": "", "zeile": ""}
    teile = [re.escape(teil) for teil in text.split()]
    if not seite or not teile:
        return leer
    treffer = re.search(r"\s+".join(teile), seite)
    if treffer is None:
        return leer
    anfang, ende = treffer.span()
    zeilen_anfang = seite.rfind("\n", 0, anfang) + 1
    zeilen_ende = seite.find("\n", ende)
    if zeilen_ende < 0:
        zeilen_ende = len(seite)
    return {
        "kontext_vorher": " ".join(seite[max(0, anfang - zeichen) : anfang].split()),
        "kontext_nachher": " ".join(seite[ende : ende + zeichen].split()),
        "zeile": " ".join(seite[zeilen_anfang:zeilen_ende].split()),
    }


def korrektur(
    finding: Finding,
    seite: str,
    vorher: Category | None,
    nachher: Category | None,
    anzahl: int = 1,
) -> dict:
    """Ein Lernbeispiel aus einer Korrektur bauen.

    ``nachher=None`` heisst: Der Treffer ist ein Fehlalarm und gehoert zu
    keiner Kategorie. ``anzahl`` nennt, fuer wie viele Treffer mit demselben
    Text die Entscheidung gilt.
    """
    # Gelernt wird der vom Benutzer bestaetigte Wert; der falsch gelesene steht
    # als "text_original" daneben, damit die Entscheidung nachvollziehbar bleibt.
    wert = " ".join((finding.korrigiert or finding.text).split())
    art = ART_KEIN_TREFFER if nachher is None else ART_KORREKTUR
    # Nur wenn ausschliesslich der Wert richtiggestellt wurde, aendert sich die
    # Kategorie nicht: das ist ein Lesefehler, kein Musterbeispiel.
    if finding.korrigiert and nachher is not None and vorher is nachher:
        art = ART_WERTKORREKTUR
    eintrag = {
        "art": art,
        "zeit": datetime.now().isoformat(timespec="seconds"),
        "seite": finding.page + 1,
        "text": wert,
        "kategorie_vorher": "" if vorher is None else vorher.value,
        "kategorie_nachher": KEIN_TREFFER if nachher is None else nachher.value,
        "quelle": finding.source,
        "entity": finding.entity,
        "score": round(finding.score, 2),
        "gleichnamige_treffer": anzahl,
    }
    if finding.korrigiert:
        eintrag["text_original"] = " ".join(finding.text.split())
    # Der Kontext wird ueber den gefundenen Text gesucht - so steht er auch auf
    # der Seite ("09.0.2022"), selbst wenn der Wert korrigiert wurde.
    eintrag.update(kontext(seite, finding.text))
    return eintrag


def merken(eintrag: dict, datei: Path | None = None) -> None:
    """Ein Beispiel an die Lerndatei anhaengen; legt sie mit Kopfzeile an."""
    ziel = Path(datei) if datei is not None else DATEI
    ziel.parent.mkdir(parents=True, exist_ok=True)
    neu = not ziel.exists()
    with ziel.open("a", encoding="utf-8") as handle:
        if neu:
            handle.write(json.dumps(_kopf(), ensure_ascii=False) + "\n")
        handle.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def eintraege(datei: Path | None = None) -> list[dict]:
    """Alle gespeicherten Beispiele lesen; Kopf- und kaputte Zeilen entfallen."""
    ziel = Path(datei) if datei is not None else DATEI
    if not ziel.exists():
        return []
    ergebnis: list[dict] = []
    for zeile in ziel.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            eintrag = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(eintrag, dict) and eintrag.get("art") != "kopf":
            ergebnis.append(eintrag)
    return ergebnis


def _normalisiert(text: object) -> str:
    """Text zum Vergleich: Leerraum vereinheitlicht, Schreibung egal."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.split()).casefold()


def _kategorie(name: object) -> Category | None:
    for category in Category:
        if category.value == name:
            return category
    return None


def regeln(datei: Path | None = None) -> dict[str, Category | None]:
    """Gelernte Zuordnungen: normalisierter Text -> Kategorie.

    ``None`` heisst "kein Treffer" (Fehlalarm). Bei mehreren Beispielen zum
    selben Text gilt das zuletzt gespeicherte.
    """
    gelernt: dict[str, Category | None] = {}
    for eintrag in eintraege(datei):
        # Reine Wertkorrekturen sind nur zur Nachvollziehbarkeit gespeichert.
        if eintrag.get("art") == ART_WERTKORREKTUR:
            continue
        schluessel = _normalisiert(eintrag.get("text"))
        if not schluessel:
            continue
        nachher = eintrag.get("kategorie_nachher")
        if not isinstance(nachher, str) or not nachher:
            continue
        if nachher == KEIN_TREFFER:
            gelernt[schluessel] = None
            continue
        kategorie = _kategorie(nachher)
        if kategorie is not None:
            gelernt[schluessel] = kategorie
    return gelernt


@dataclass(frozen=True)
class Anwendung:
    """Was die Lerndatei an den Treffern geaendert hat."""

    treffer: list[Finding]
    abgehakt: int = 0
    umkategorisiert: int = 0


def anwenden(findings: list[Finding], datei: Path | None = None) -> Anwendung:
    """Gelernte Korrekturen auf die Treffer anwenden.

    Ein korrigierter Ausdruck bekommt die gelernte Kategorie, ein als
    Fehlalarm abgehakter wird nicht mehr angehakt und damit nicht mehr
    geschwaerzt. Die Quelle behaelt die urspruengliche Herkunft und bekommt
    den Zusatz ``· gelernt: ...``. Manuell eingegebene Werte und eigene
    Regex-Treffer bleiben unangetastet: was der Benutzer dort eintraegt, gilt.
    """
    gelernt = regeln(datei)
    if not gelernt:
        return Anwendung(findings)
    abgehakt = 0
    umkategorisiert = 0
    for finding in findings:
        if finding.entity == "MANUAL" or finding.category is Category.REGEX:
            continue
        schluessel = _normalisiert(finding.text)
        if schluessel not in gelernt:
            continue
        kategorie = gelernt[schluessel]
        if kategorie is None:
            if finding.enabled:
                abgehakt += 1
            finding.enabled = False
            if "gelernt" not in finding.source:
                finding.source = (
                    f"{finding.source} · gelernt: Fehlalarm".lstrip(" ·")
                )
            continue
        if finding.category is kategorie:
            continue
        finding.source = f"{finding.source} · gelernt: {kategorie.value}".lstrip(" ·")
        finding.category = kategorie
        finding.entity = "GELERNT"
        umkategorisiert += 1
    return Anwendung(findings, abgehakt, umkategorisiert)


def zuruecksetzen(datei: Path | None = None) -> int:
    """Alle gelernten Beispiele verwerfen; liefert deren Anzahl."""
    ziel = Path(datei) if datei is not None else DATEI
    anzahl = len(eintraege(ziel))
    try:
        ziel.unlink()
    except FileNotFoundError:
        return 0
    return anzahl


def _schreiben(beispiele: list[dict], ziel: Path) -> None:
    """Die Beispiele als JSONL-Datei mit Kopfzeile schreiben."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(_kopf(), ensure_ascii=False) + "\n")
        for eintrag in beispiele:
            handle.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def loeschen(indizes: Iterable[int], datei: Path | None = None) -> int:
    """Einzelne Beispiele entfernen; die Positionen stammen aus ``eintraege()``.

    Die Datei wird neu geschrieben, die Kopfzeile bleibt. Liefert die Anzahl
    der geloeschten Beispiele.
    """
    ziel = Path(datei) if datei is not None else DATEI
    beispiele = eintraege(ziel)
    weg = {index for index in indizes if 0 <= index < len(beispiele)}
    if not weg:
        return 0
    _schreiben(
        [eintrag for index, eintrag in enumerate(beispiele) if index not in weg],
        ziel,
    )
    return len(weg)


def exportieren(ziel: str | Path) -> int:
    """Die Lerndatei an einen frei waehlbaren Ort schreiben; liefert die Anzahl."""
    beispiele = eintraege()
    _schreiben(beispiele, Path(ziel))
    return len(beispiele)


__all__ = [
    "ART_WERTKORREKTUR",
    "DATEI",
    "FORMAT",
    "KEIN_TREFFER",
    "KONTEXT_ZEICHEN",
    "ORDNER",
    "Anwendung",
    "anwenden",
    "eintraege",
    "exportieren",
    "kontext",
    "korrektur",
    "loeschen",
    "merken",
    "regeln",
    "zuruecksetzen",
]
