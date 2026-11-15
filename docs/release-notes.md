## PDFblack 1.0.7

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.0.7

- **Kein stiller Fehlschlag mehr:** Bricht das Setup beim Update sofort ab, schließt sich PDFblack nicht mehr, sondern bleibt offen und nennt den Link zur Release-Seite. Bisher war das Programm danach einfach weg, ohne dass etwas installiert wurde.

### Neu in 1.0.6

- **Einzelne Häkchen in der Kategorie-Übersicht:** In der unteren Sektion lässt sich jetzt jeder einzelne Eintrag an- und abhaken; der Haken der Überschrift folgt automatisch (alle an = Haken, alle aus = leer, gemischt = Strich). Bisher hat das Umschalten eines einzelnen Eintrags die ganze Gruppe wieder eingeschaltet.
- **Neustart nach dem Update:** Der Installer öffnet PDFblack nach dem Einbau selbst – auch beim stillen Update. Der Start-Eintrag im Setup war bisher auf sichtbare Installationen beschränkt.

### Neu in 1.0.5

- **Doppelklick schwärzt Wörter:** Ein Doppelklick auf ein Wort im PDF nimmt genau dieses Wort als Schwärzung auf (Kategorie „Manuell“, Quelle „Doppelklick“) – so schnell wie ein darum gezogener Rahmen. Ein zweiter Doppelklick auf dasselbe Wort legt keinen doppelten Treffer an, Einzelklicks schalten Treffer weiterhin ein und aus.

### Neu in 1.0.4

- **Treffer nach Kategorie:** Die Trefferspalte zeigt unterhalb der Liste einen zweiten Abschnitt, gruppiert nach Personen, Adressen, PLZ/Ort, Nummern, Kontakt, Bank und Datum. Das Häkchen vor einer Überschrift schaltet die ganze Gruppe ein oder aus (bei gemischtem Zustand zeigt es einen Strich), ein Häkchen am Eintrag nur diesen.
- **Ladebalken:** Während das automatische Update herunterlädt, zeigt die Statuszeile einen Fortschrittsbalken mit Prozentangabe.
- **Formular-PDFs:** Werte in Formularfeldern werden erkannt, und beim Schwärzen werden die betroffenen Felder geleert und entfernt. Bisher konnte ein Feldwert trotz geschwärzter Fläche im PDF erhalten bleiben.
- **Hausnummern:** die Nummer hinter dem Straßennamen wird auch dann geschwärzt, wenn die Straße kein deutsches Suffix hat („Rue du Lac 12“, „Unter den Linden 5a“). Erkannt werden Zahl (`12`), Zahl mit Leerzeichen und Buchstabe (`12 a`) und Zahl mit Buchstabe ohne Abstand (`12a`).
- **Schweizer Postleitzahlen:** vierstellige PLZ mit Präfix (`CH-8045`, `CH 3000 Bern`) und mit nachgestelltem Ort (`8045 Zürich`, `CH-1814 La Tour-de-Peilz`) – auch wenn Ort und PLZ in getrennten Zeilen oder getrennten Formularfeldern stehen (`9435` / `Heerbrugg`, in beiden Reihenfolgen) und wenn der Ort kleingeschrieben ist. Beträge, Mengen, Zeiträume und Nummernkreise (`4711-2233`, `PE-8842/2024`) gelten nicht als PLZ.
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

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.0.7-Setup.exe`
herunterladen und ausführen (Installer, kein Administrator- oder
Python-Zubehör nötig).

### Geprüft

- 24 automatisierte Tests für Erkennung, Doppelklick auf Wörter, Hausnummern, Schweizer PLZ in getrennten Zeilen und Formularfeldern, manuelle Werte, Regex, Überlappungen, Schwärzung, Update-Abfrage und gemerkte Einstellungen
- Selbsttest der gepackten Anwendung (`PDFblack --self-test`) im Windows-Build
- Speicherprobe mit Schweizer Adresse und Formularfeldern: kein Resttext der geschwärzten Werte im Ergebnis-PDF

### Hinweis zum Update aus 1.0.5

In 1.0.5 startete der Updater das Setup über die Windows-Shell; sie las den
Aufruf falsch und meldete eine nicht gefundene Datei, es wurde nichts
installiert. Wer 1.0.5 installiert hat, installiert 1.0.6 deshalb einmal von
Hand; ab 1.0.6 läuft die Aktualisierung wieder selbsttätig.

### Hinweis zum Update aus 1.0.0

Die Fassung 1.0.0 enthielt den Updater noch nicht. Wer 1.0.0 installiert hat,
installiert diese Fassung einmal von Hand; ab 1.0.1 läuft die Aktualisierung
selbsttätig.
