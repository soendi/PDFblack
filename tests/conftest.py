"""Gemeinsame Einstellungen fuer die Tests.

Die automatische Erkennung beim Oeffnen startet in jedem UI-Test einen
Hintergrundlauf und kann beim Schliessen des Fensters nachfragen. Tests, die
genau dieses Verhalten pruefen, entfernen die Variable gezielt.
"""

import os

os.environ.setdefault("PDFBLACK_NO_AUTO_DETECT", "1")
