## PDFblack 1.0.0

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Funktionen

- **Erkennung:** Personen und Vornamen (Microsoft Presidio + spaCy, deutsches Modell), Straße + Hausnummer, PLZ + Ort, Personal-, Ausweis-, Versicherten-, Kunden-, Vertrags- und Aktenzeichen, E-Mail, Telefon, IBAN, Datum
- **Zweiter Durchlauf:** eigene Werte für Vorname, Nachname, Adresse, PLZ, Ort, Personennummer und weitere Begriffe
- **Eigene Regexe:** beliebig viele Muster, ungültige Ausdrücke werden vor dem Start gemeldet
- **Namen überall:** ein erkannter Name wird auch innerhalb von Adresszeilen, Briefköpfen und Fußzeilen geschwärzt
- **Vorschau:** alle Fundstellen farbig nach Kategorie markiert, die Datei bleibt unverändert
- **Überarbeiten:** Markierung per Klick abwählen, Bereiche mit der Maus aufziehen, Trefferliste mit Häkchen, Erkennung mit ergänzten Werten wiederholen
- **Echtes Schwärzen:** Text unter den Markierungen wird entfernt, Links darauf gelöscht, Datei neu geschrieben – Original bleibt unangetastet
- Drag & Drop, Seitenzoom, passwortgeschützte PDFs

### Installation

**Windows:** `PDFblack-1.0.0-Setup.exe` herunterladen und ausführen (Installer, kein Administrator- oder Python-Zubehör nötig).

**Linux (Debian/Ubuntu):**

```bash
sudo apt install ./PDFblack_1.0.0_amd64.deb
pdfblack
```

Alternativ das Archiv `PDFblack-1.0.0-linux-x86_64.tar.gz` entpacken und `PDFblack/PDFblack` starten.

**macOS:** aus dem Quellcode mit `bash packaging/build_macos.sh` bauen.

### Geprüft

- 8 automatisierte Tests für Erkennung, manuelle Werte, Regex, Überlappungen und Schwärzung
- Selbsttest der gepackten Anwendung (`PDFblack --self-test`) in beiden Builds
- Speichern-Weg der Oberfläche: 29 Stellen geschwärzt, anschließend kein Resttext der geschwärzten Werte im PDF

### Lizenzen

Eigener Code MIT. Microsoft Presidio und spaCy MIT. PyMuPDF steht unter AGPL-3.0 oder einer kommerziellen Lizenz von Artifex – für eine kommerzielle Weitergabe ohne Quelloffenlegung ist eine PyMuPDF-Lizenz nötig. PySide6/Qt unter LGPL-3.0.
