"""Feste Regeln aus der Lerndatei - erzeugt von ``tools/lerndatei_regeln.py``.

Nicht von Hand aendern: neue Beispiele in die Lerndatei aufnehmen, die
exportierte Datei mit dem Werkzeug einlesen und dieses Modul neu erzeugen.
Die Muster greifen danach ohne Lerndatei.

Solange hier nichts steht, wirken allein die Programmmuster und die
vorlaeufigen Beispiele aus der Lerndatei.
"""

from __future__ import annotations

from .models import Category

# Fehlalarme: passt ein Treffer auf eines dieser Muster, wird er nicht
# geschwaerzt.
AUSGESCHLOSSEN: tuple[str, ...] = ()

# Zuordnung: Muster -> Kategorie. Ein Treffer, dessen Text passt, bekommt
# diese Kategorie statt der erkannten.
ZUGEORDNET: tuple[tuple[str, Category], ...] = ()
