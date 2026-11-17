"""Kontextmenue fuer einen Treffer.

Trefferliste und Dokument zeigen dieselben Aktionen; damit sie nicht
auseinanderlaufen, bauen beide ihr Menue hier. Jede Aktion traegt ihre
Bedeutung in ``data()``; ausgefuehrt wird sie vom Aufrufer, weil nur der die
Trefferliste kennt.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu, QWidget

from ..core.models import Category, Finding

# Kategorien, die der Benutzer waehlen kann: alle inhaltlichen Einordnungen,
# nicht die Herkuenfte "Manuell" und "Regex".
WAHL_KATEGORIEN: tuple[Category, ...] = tuple(
    category
    for category in Category
    if category not in (Category.MANUAL, Category.REGEX)
)

# Werte in data() der Aktionen.
AKTION_UMSCHALTEN = "umschalten"
AKTION_ALLE_UMSCHALTEN = "alle-umschalten"
AKTION_FEHLALARM = "fehlalarm"
AKTION_ALLE_FEHLALARM = "alle-fehlalarm"
AKTION_KATEGORIE = "kategorie"
AKTION_ALLE_KATEGORIE = "alle"
AKTION_HINWEIS_OK = "hinweis-ok"
AKTION_KORRIGIEREN = "korrigieren"


def treffer_menue(
    parent: QWidget, finding: Finding, gleichnamige: int = 1
) -> QMenu:
    """Menue mit allen Aktionen zu einer Fundstelle.

    ``gleichnamige`` ist die Anzahl der Treffer mit demselben Text; ab zwei
    kommen die Aktionen fuer alle hinzu.
    """
    menu = QMenu(parent)
    kopf = menu.addAction(finding.display_text)
    kopf.setEnabled(False)

    umschalten = menu.addAction(
        "Nicht schw\u00e4rzen" if finding.enabled else "Schw\u00e4rzen"
    )
    umschalten.setData(AKTION_UMSCHALTEN)

    menu.addSeparator()
    kopf_kategorie = menu.addAction("Diesen Treffer einordnen:")
    kopf_kategorie.setEnabled(False)
    for category in WAHL_KATEGORIEN:
        aktion = menu.addAction(category.value)
        aktion.setCheckable(True)
        aktion.setChecked(category is finding.category)
        aktion.setData(f"{AKTION_KATEGORIE}:{category.value}")

    fehlalarm = menu.addAction("Kein Treffer (Fehlalarm)")
    fehlalarm.setData(AKTION_FEHLALARM)

    if finding.hinweis:
        menu.addSeparator()
        geprueft = menu.addAction(
            "Hinweis gepr\u00fcft \u2013 trotzdem schw\u00e4rzen"
        )
        geprueft.setData(AKTION_HINWEIS_OK)
        korrigieren = menu.addAction("Wert korrigieren \u2026")
        korrigieren.setData(AKTION_KORRIGIEREN)

    if gleichnamige >= 2:
        menu.addSeparator()
        kopf_alle = menu.addAction(
            f"F\u00fcr alle {gleichnamige} Treffer mit "
            f"\u201e{finding.display_text}\u201c:"
        )
        kopf_alle.setEnabled(False)
        unter = menu.addMenu("Kategorie f\u00fcr alle \u00e4ndern")
        for category in WAHL_KATEGORIEN:
            aktion = unter.addAction(category.value)
            aktion.setData(f"{AKTION_ALLE_KATEGORIE}:{category.value}")
        alle_fehlalarm = menu.addAction(
            f"Alle {gleichnamige} als Fehlalarm abhaken"
        )
        alle_fehlalarm.setData(AKTION_ALLE_FEHLALARM)
        alle_umschalten = menu.addAction(
            f"Alle \u201e{finding.display_text}\u201c umschalten ({gleichnamige})"
        )
        alle_umschalten.setData(AKTION_ALLE_UMSCHALTEN)
    return menu


__all__ = [
    "AKTION_ALLE_FEHLALARM",
    "AKTION_ALLE_KATEGORIE",
    "AKTION_ALLE_UMSCHALTEN",
    "AKTION_FEHLALARM",
    "AKTION_HINWEIS_OK",
    "AKTION_KATEGORIE",
    "AKTION_KORRIGIEREN",
    "AKTION_UMSCHALTEN",
    "WAHL_KATEGORIEN",
    "treffer_menue",
]
