## PDFblack 1.0.1

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.0.1

- **Hausnummern:** die Nummer hinter dem Straßennamen wird auch dann geschwärzt, wenn die Straße kein deutsches Suffix hat („Rue du Lac 12“, „Unter den Linden 5a“). Erkannt werden Zahl (`12`), Zahl mit Leerzeichen und Buchstabe (`12 a`) und Zahl mit Buchstabe ohne Abstand (`12a`).
- **Schweizer Postleitzahlen:** vierstellige PLZ mit Präfix (`CH-8045`, `CH 3000 Bern`) und mit nachgestelltem Ort (`8045 Zürich`, `CH-1814 La Tour-de-Peilz`) – auch dann, wenn der Ort erst in der nächsten Zeile steht (`9435` / `Heerbrugg`) oder kleingeschrieben ist. Beträge, Mengen und Zeiteinheiten gelten nicht als Ort – „1500 Franken" bleibt stehen. Eigener Schalter in der automatischen Erkennung.
- **Automatische Updates:** PDFblack prüft beim Start im Hintergrund, ob eine neue Version bereitsteht, lädt sie und spielt sie ohne Assistent ein. Von Hand über **Hilfe → Nach Updates suchen …**.
- **Gemerkte Einstellungen:** die Häkchen der automatischen Erkennung und die Empfindlichkeit gelten beim nächsten Start weiter.
- **Telefonnummern** mit beliebiger Ländervorwahl (`+41 …`), nicht mehr nur `+49`.
- Anrede- und Grußfloskeln („Herrn", „Freundliche Grüsse") werden nicht mehr als Namen markiert.

### Funktionen

- **Erkennung:** Personen und Vornamen (Microsoft Presidio + spaCy, deutsches Modell), Straße + Hausnummer, PLZ + Ort (Deutschland und Schweiz), Personal-, Ausweis-, Versicherten-, Kunden-, Vertrags- und Aktenzeichen, E-Mail, Telefon, IBAN, Datum
- **Zweiter Durchlauf:** eigene Werte für Vorname, Nachname, Adresse, PLZ, Ort, Personennummer und weitere Begriffe
- **Eigene Regexe:** beliebig viele Muster, ungültige Ausdrücke werden vor dem Start gemeldet
- **Namen überall:** ein erkannter Name wird auch innerhalb von Adresszeilen, Briefköpfen und Fußzeilen geschwärzt
- **Vorschau:** alle Fundstellen farbig nach Kategorie markiert, die Datei bleibt unverändert
- **Überarbeiten:** Markierung per Klick abwählen, Bereiche mit der Maus aufziehen, Trefferliste mit Häkchen, Erkennung mit ergänzten Werten wiederholen
- **Echtes Schwärzen:** Text unter den Markierungen wird entfernt, Links darauf gelöscht, Datei neu geschrieben – Original bleibt unangetastet
- Drag & Drop, Seitenzoom, passwortgeschützte PDFs

### Installation

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.0.1-Setup.exe`
herunterladen und ausführen (Installer, kein Administrator- oder
Python-Zubehör nötig).

### Geprüft

- 18 automatisierte Tests für Erkennung, Schweizer PLZ, manuelle Werte, Regex, Überlappungen, Schwärzung, Update-Abfrage und gemerkte Einstellungen
- Selbsttest der gepackten Anwendung (`PDFblack --self-test`) in beiden Builds
- Speicherprobe mit Schweizer Adresse: kein Resttext der geschwärzten Werte im Ergebnis-PDF

### Hinweis zum Update aus 1.0.0

Die Fassung 1.0.0 enthielt den Updater noch nicht. Wer 1.0.0 installiert hat, installiert 1.0.1 einmal von Hand; ab 1.0.1 läuft die Aktualisierung selbsttätig.

### Lizenzen

Eigener Code MIT. Microsoft Presidio und spaCy MIT. PyMuPDF steht unter AGPL-3.0 oder einer kommerziellen Lizenz von Artifex – für eine kommerzielle Weitergabe ohne Quelloffenlegung ist eine PyMuPDF-Lizenz nötig. PySide6/Qt unter LGPL-3.0.
