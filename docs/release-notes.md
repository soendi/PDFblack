## PDFblack 1.2.1

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.2.1

- **Prüfung ist fakultativ:** Unter **Datei → Einstellungen …** lässt sich „Prüfung der Unterlagen anbieten“ abschalten. Dann verschwindet der Knopf „Unterlagen prüfen …“ unter den Zeugnissen und PDFcompare bleibt schlank; die Übergabe an die Agenten bleibt unberührt. Voreingestellt ist die Prüfung an.

### Neu in 1.2.0

- **Prüfung ohne KI:** Unter den Zeugnissen öffnet „Unterlagen prüfen …" ein Fenster mit allem, was sich ausrechnen lässt: Zeiträume aus dem Lebenslauf, **Lücken ab drei Monaten**, Seiten ohne Textebene (Scans, die PDFblack nicht schwärzen kann), doppelte Dateien, fehlender Lebenslauf oder fehlende Zeugnisse und die Reihenfolge der Zeugnisse. Diese Befunde sind sofort da, offline und ohne Copilot.
- **Frage an Copilot:** Ein Knopf legt eine fertige Frage samt Antwort-Schema in die Zwischenablage und öffnet Copilot. Die Fakten darin kommen aus dem Prüflauf, nicht aus Vermutungen.
- **Antwort zurückholen:** Copilot hat für fremde Programme keinen Rückkanal (die Copilot-Chat-API verlangt eine App-Registrierung beim Microsoft-Konto, die hier nicht möglich ist). Deshalb liest PDFcompare die Antwort aus der Zwischenablage: einfügen, „Antwort auswerten", und die Vorschläge erscheinen als Liste – Lücken, Zeugnisse, fehlende Unterlagen, Zusammenfassung. Das JSON wird auch aus Fließtext und Code-Blöcken herausgeschnitten; ohne gültige Antwort bleibt alles beim lokalen Befund.

### Neu in 1.1.4

- **Dateien hin und her ziehen:** In PDFcompare lassen sich Dateien jetzt in jede Richtung verschieben – von „Lebenslauf“ nach „Arbeitszeugnisse“, aus beiden Stapeln zurück nach „Zuletzt geschwärzt“ und von dort wieder in einen Stapel. Jede Datei steht weiterhin nur in einer Liste.
- **Listen einzeln leeren:** Unter „Zuletzt geschwärzt“ liegen drei Knöpfe, die je eine der drei Listen leeren. Die Dateien auf dem Rechner bleiben dabei unangetastet.
- **Mülleimer:** Unter „Arbeitszeugnisse“ gibt es eine kleine Ablage mit rotem Mülleimer. Eine dorthin gezogene Datei wird nach der Rückfrage „Wirklich entfernen?“ aus der Liste genommen – die Originaldatei bleibt erhalten.
- **Aufräumen beim Beenden:** Beim Schließen von PDFblack werden alle drei Listen geleert. Danach fragt das Programm, ob auch die geschwärzten Dateien gelöscht werden sollen; Kopien, die bereits an einen Copilot-Agenten übergeben wurden, verschwinden dabei aus dem Agent-Ordner.
- **Übergabe an Copilot:** Der Knopf übergibt die Unterlagen jetzt mit Frage und Datei an Copilot (`ms-copilot:chat?q=…&file=…`); mehrere Dokumente werden vorher zu einer PDF gebündelt. Bleibt der Aufruf ohne Wirkung, öffnet sich Copilot wie bisher und die Dateien liegen im Übergabeordner.

### Neu in 1.1.3

- **Übergabe an Copilot:** Unter der Liste „Arbeitszeugnisse“ steht für jeden hinterlegten Agenten ein blauer Knopf „An Copilot Agent „…“ übergeben“. Ein Klick legt alle zugeordneten Dateien in einem Ordner bereit (`%LOCALAPPDATA%\PDFblack\Copilot-Uebergabe\<Agent>`), öffnet den Ordner und Copilot und kopiert die Dateipfade in die Zwischenablage. Damit Copilot die Rollen erkennt, heißen die Dateien `Lebenslauf_<Name>.pdf` bzw. `Arbeitszeugnis_<Name>.pdf`.
- **Ohne Agenten:** Ist keiner hinterlegt, steht dort der Knopf „Einstellungen Copilot“, der das Einstellungsfenster öffnet.

### Neu in 1.1.2

- **Kopfzeile:** Titel und Untertitel von PDFcompare bleiben jetzt beim Wechsel exakt am Logo. Bisher blieb der eingeblendete Text an der alten Stelle stehen, weil Qt das zwischengespeicherte Bild des Einblend-Effekts beim Verschieben nicht mitgenommen hat; jetzt wird der Text über seine Farbe ein- und ausgeblendet.
- **Update ohne Fehlermeldung:** PDFblack schließt sich sofort, und der Installer startet erst, wenn der Prozess wirklich beendet ist. Ein kleiner mitgelieferter Helfer wartet auf das Ende des Fensters, startet dann das Setup und öffnet PDFblack nach dem Einbau wieder. Bisher konnte das Setup anlaufen, während das Fenster noch offen war.
- **PDFcompare-Listen:** Wird eine Datei in „Lebenslauf" oder „Arbeitszeugnisse" gezogen, verschwindet sie aus „Zuletzt geschwärzt" und aus der jeweils anderen Liste – jede Datei steht nur in einer Liste.

### Neu in 1.1.1

- **Kopfzeile ohne Kasten:** Titel und Untertitel von PDFcompare stehen jetzt ohne eigenen Hintergrund in der Kopfzeile. Ist PDFcompare rechts, bleibt sein Text unsichtbar; beim Wechsel nach links blendet er ein, während der Text von PDFblack ausblendet. Beim Zurückwechseln umgekehrt.
- **PDFcompare-Ansicht:** links die zuletzt geschwärzten PDF-Dateien, rechts zwei Stapel – „Lebenslauf“ als kürzere Liste und „Arbeitszeugnisse“ als längere. Dateien lassen sich aus der linken Liste in einen Stapel ziehen; `Entf` entfernt einen Eintrag wieder. Liste und Zuordnung bleiben über den Programmstart erhalten.
- **Einstellungen:** Unter **Datei → Einstellungen …** (`Strg+,`) lässt sich PDFcompare mit Windows Copilot verknüpfen und ein Agent auswählen. Windows bietet für andere Programme keine Schnittstelle zum Setzen eines Agenten; PDFblack merkt sich die Auswahl, öffnet Copilot per `ms-copilot:` und kann bei Bedarf einen hinterlegten Agent-Link aufrufen.

### Neu in 1.1.0

- **Zweites Programm in der Kopfzeile:** Rechts neben PDFblack steht jetzt PDFcompare mit eigenem Logo, Titel und Untertitel. Ein Klick auf ein Logo wechselt das Programm: PDFcompare fährt animiert nach links, bis sein Logo genau dort steht, wo Titel und Untertitel von PDFblack beginnen, und deckt sie ab. Ein Klick auf das PDFblack-Logo schiebt es wieder zurück an seinen Platz ab der Fenstermitte.
- **Weiche Übergänge:** Beim Wechsel blendet die aktuelle Maske aus und die neue ein. Schnelles Hin- und Herklicken bricht den laufenden Übergang ab, ohne dass eine halb ausgeblendete oder falsche Maske zurückbleibt.
- **PDFcompare-Maske:** Vorerst eine leere Ansicht mit Hinweis – der eigentliche Vergleich folgt.

### Neu in 1.0.9

- **Datum ist nicht mehr „PLZ / Ort“:** Steht ein Datum allein in der Kopfzeile („20.10.2026“), meldet das deutsche Sprachmodell es als Ort – in der Vorschau erschien es deshalb unter PLZ / Ort. Solche Treffer werden jetzt verworfen, echte Ortsnamen aber weiterhin erkannt.
- **Datumsangaben ohne Beschriftung:** Die Datumsregel findet jetzt auch Daten, denen kein „Datum:“ vorangeht – `20.10.2026`, `20.10.26` und `2026-10-20`. Das Häkchen dafür heißt entsprechend „Datum (Geburts-, Rechnungs-, Ablaufdatum)“.

### Neu in 1.0.8

- **Datenschutz im Programm erklärt:** Unter **Hilfe → Datenschutz** öffnet sich ein eigenes Fenster mit den Angaben, die man für eine Freigabe braucht: Verarbeitung ausschließlich lokal, Microsoft Presidio als mitgelieferte Open-Source-Bibliothek statt Cloud-Dienst, die Update-Prüfung als einzige Netzwerkverbindung (abschaltbar über `--no-update` bzw. `PDFBLACK_NO_UPDATE=1`) und die Folgen für Auftragsverarbeitung und Drittlandtransfer. Dazu drei Hinweise für den Alltag: das Original bleibt unverändert liegen, die Erkennung ist statistisch, und die Dateien werden nicht verschlüsselt.

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

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.2.1-Setup.exe`
herunterladen und ausführen (Installer, kein Administrator- oder
Python-Zubehör nötig).

### Geprüft

- 57 automatisierte Tests für Erkennung, Doppelklick auf Wörter, Hausnummern, Schweizer PLZ in getrennten Zeilen und Formularfeldern, manuelle Werte, Regex, Überlappungen, Schwärzung, Update-Abfrage und gemerkte Einstellungen
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
