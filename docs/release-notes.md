## PDFblack 1.3.5

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.5

- **Jeder Kopfknopf bleibt klickbar:** Wurde ein Knopf verschoben, lag der ausgeblendete Text eines anderen Programms über seinem Logo – der Klick landete auf dem unsichtbaren Text und tat nichts. Betroffen war vor allem der blaue Knopf, wenn er neben dem roten stand. Die Blöcke haben jetzt eine feste Stapelreihenfolge (rot, blau, grün von unten nach oben), und Titel wie Untertitel nehmen keine Mausklicks mehr an. Alle drei Knöpfe sind damit in jeder Stellung erreichbar.
- **Textebene verwerfen und per OCR neu aufsetzen:** Wird eine PDF mit vorhandener Textebene geladen, bietet PDFblack über der Vorschau an, die Textebene zu verwerfen und aus den Seitenbildern neu aufzubauen. Die Seiten gehen dafür als Bilder in eine temporäre Datei, die ausgelesen und danach gelöscht wird – die **Originaldatei bleibt unverändert**. Das Ergebnis lässt sich speichern oder direkt in PDFblack öffnen. Fehlt Tesseract, erscheint das Angebot nicht; PDFs ohne Text gehen weiterhin von selbst an PDFocr.
- **Stapel in PDFcompare in Arbeitsreihenfolge:** Bewerbung, Lebenslauf, Arbeitszeugnisse und Diplome stehen jetzt in dieser Reihenfolge übereinander – so, wie die Unterlagen zusammengestellt werden.
- **Beim Beenden nur eigene Dateien löschen:** Die Frage, ob geschwärzte Dateien gelöscht werden sollen, betrifft nur noch Dateien, die PDFblack in dieser Sitzung selbst geschwärzt hat. Selbst zugezogene Dateien bleiben unangetastet.

## PDFblack 1.3.4

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.4

- **Die Knöpfe bleiben in ihrer Reihenfolge:** Beim Klick auf PDFcompare fährt nur der blaue Knopf nach links neben den roten – der grüne bleibt, wo er ist. Erst der Klick auf PDFocr bewegt beide: blau neben rot, grün neben blau. Es wird also nur geblättert, nie getauscht; der grüne Knopf bewegt sich nicht mehr mit, wenn nur PDFcompare gewählt wird.
- **Berufe in Zusammensetzungen gelten auch:** Steckt eine Berufsbezeichnung in einem Wort, ist das Wort ein Beruf – „Dachdeckerhandwerk“, „Dachdeckerbetrieb“, „Dachdeckerarbeiten“, „Zimmererhandwerk“ und „Arztpraxis“ werden deshalb nicht mehr als Name geschwärzt. Namen bleiben geschützt: allgemeine Rollen („Mustermeister“), Berufe, die häufiger Nachname sind („Neubauer“, „Neumaier“), und Bindestrich-Namen („Schmidt-Lorenz“) zählen nicht als Wortteil.

## PDFblack 1.3.3

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.3

- **PDFocr funktioniert wieder:** Tesseract las das abschließende `tsv` als Konfigurationsdatei aus dem Sprachordner – und der mitgelieferte Ordner enthält nur `deu.traineddata`, deshalb kam „read_params_file: Can't open tsv“ und die Erkennung brach mit „Tesseract hat keine Ausgabe geliefert“ ab. Die TSV-Ausgabe wird jetzt als Option übergeben (`-c tessedit_create_tsv=1`); dafür braucht es keine zusätzlichen Dateien.
- **Frage an Copilot ist sichtbar und änderbar:** Im Prüffenster („Unterlagen prüfen …“) steht die Frage samt Antwort-Schema in einem eigenen Feld. Kopiert und an Copilot geschickt wird, was dort steht – leeren und neu formulieren ist ausdrücklich erlaubt.
- **Text der Übergabe einstellbar:** Unter **Datei → Einstellungen …** lässt sich neben der Agentenliste der Text ändern, der beim Klick auf einen Agenten-Knopf mit der gebündelten Datei an Copilot geht. Vorgabe ist der bisherige Text; ein leeres Feld stellt die Vorgabe wieder her.
- **Grüner Knopf direkt hinter dem blauen:** Der PDFocr-Knopf steht in Ruhestellung unmittelbar hinter dem Logo von PDFcompare – genau dort, wo dessen Text beginnt – und wandert mit, wenn PDFcompare nach links fährt. Die bisherige Extra-Lücke ist weg.

## PDFblack 1.3.2

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.2

- **Das deutsche Sprachmodell ist im Programm:** `deu.traineddata` (Quelle `tessdata_fast`, Apache-2.0) liegt in der Anwendung, und PDFblack startet Tesseract immer mit `--tessdata-dir` auf diesen Ordner. Die Texterkennung funktioniert damit offline und ohne Nachladen; die Meldung „Error opening data file …\deu.traineddata“ bzw. „Failed loading language 'deu'“ kann nicht mehr auftreten. Eine Ausrichtungserkennung (`osd`) braucht PDFblack nicht.
- **Installation bringt die Sprache mit:** Die stille Installation über `winget` richtet nur das Tesseract-Programm samt Englisch ein – Deutsch kommt jetzt aus dem Programm selbst. Nach der Nachinstallation ist PDFocr sofort einsatzbereit, ohne zweiten Download und ohne Schreibrechte im Programmverzeichnis.
- **Grüner Knopf am Textanfang:** Beim Wechsel zu PDFocr steht das grüne „T“-Logo jetzt genau dort, wo der Text des blauen Knopfes beginnt; der Vergleichsknopf fährt an seinen Platz zurück, statt daneben stehen zu bleiben.

## PDFblack 1.3.1

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.1

- **Tesseract wird beim Start geprüft:** Fehlt Tesseract-OCR, meldet PDFblack das beim Öffnen und bietet an, es nachzuinstallieren. Auf Wunsch richtet `winget` das Windows-Build `UB-Mannheim.TesseractOCR` still ein (Windows fragt nach der Freigabe); danach ist PDFocr sofort bereit und der Hinweis auf der PDFocr-Seite verschwindet. Ohne winget oder ausserhalb von Windows bleibt es beim Hinweis mit der Adresse der Tesseract-Seite. Abschaltbar über `PDFBLACK_NO_OCR_CHECK=1`.
- **Nur echte Ortschaften gelten als Ort:** Meldet das Sprachmodell ein Wort als Ort, muss es in der amtlichen Ortschaftenliste stehen. Überschriften wie „Fachmessen“ oder „Dachdeckermeister“ erscheinen damit nicht mehr unter „PLZ / Ort“; Ortsnamen wie „Heerbrugg“ oder „Sion“ bleiben. Treffer mit Zahlen (PLZ, Hausnummer) prüfen weiterhin die Regeln.
- **Beruf mit Zusatz ist auch ein Beruf:** „Dachdeckermeister“, „Dachdeckermeisterin“, „Dachdeckergeselle“, „Dachdeckerlehrling“ oder „Maurermeister“ zählen wie „Dachdecker“ als Berufsbezeichnung und werden nicht geschwärzt. Ein Name mit solchem Zusatz („Mustermeister“) bleibt ein Name.

### Neu in 1.3.0

- **PDFocr – drittes Programm in der Kopfzeile:** Grüner Knopf mit „T“, Untertitel „Liest aus Bildscans den Text aus PDF Dateien.“ Beim Klick fährt der blaue Knopf wie gewohnt nach links, der grüne bleibt genau dort stehen, wo der Text des blauen anfängt; sichtbar ist immer nur der Text des aktiven Programms.
- **Bildscans werden automatisch ausgelesen:** Öffnet man in PDFblack eine Datei ohne Textebene, wechselt das Programm selbstständig zu PDFocr und startet die Erkennung. Der erkannte Text wird **unsichtbar hinter das Bild** gelegt (300 dpi, Wortkästen pixelgenau in PDF-Punkte zurückgerechnet, waagerecht auf die Kastenbreite gestaucht) – eine spätere Schwärzung trifft dieselbe Stelle im Scan und ersetzt dort auch die Bildpunkte.
- **Wörterbuch-Korrektur:** Vor dem Einsetzen laufen die erkannten Wörter gegen ein deutsches Wörterbuch (339 000 Wörter, offline). Korrigiert werden nur klein geschriebene Wörter, die im Dokument einmal vorkommen und genau einen nahen Vorschlag haben – Namen, Straßen und Firmen bleiben unangetastet. Abschaltbar über „Rechtschreibung prüfen (Wörterbuch)“.
- **Amtliche PLZ-Liste:** 3 371 Schweizer Postleitzahlen mit ihren Ortschaften (swisstopo + GeoNames, inkl. Liechtenstein) entscheiden, was eine PLZ ist. Eine Jahreszahl liegt immer zwischen dem aktuellen Jahr und dem aktuellen Jahr minus 70 (2026 also 1956–2026); ausserhalb ist eine vierstellige Zahl eine Postleitzahl, innerhalb muss der Ort dazu passen.
- **PLZ und Ort gehören in eine Zeile:** Steht eine Zahl allein und darunter ein Name, ist er eine **Firma** (neue Kategorie) – „2026 / Muster AG“ genauso wie „9435 / Muster AG“. Berufe und Überschriften darunter bleiben stehen.
- **Berufsbezeichnungen werden nicht geschwärzt:** Rund 11 500 Berufe in männlicher und weiblicher Form (Wikidata, CC0, plus gängige Berufe) gelten weder als Name noch als Adresse – „Vorarbeiterin von 10 Dachdecker“ ergibt keinen Treffer mehr. Nachnamen, die zugleich Beruf sind („Herr Müller“, „Frau Koch“), zählen weiter als Namen.
- **Hausnummern enden mit der Zahl:** Folgt nach der Nummer noch ein ganzes Wort („Hauptstraße 12 Telefon …“), ist es keine Adresse; „in 8000 Zürich“ bleibt erlaubt.
- **PDFcompare: vier Stapel:** Lebenslauf, Arbeitszeugnisse, Bewerbung und Diplome sind gleich hoch, jeder Stapel hat einen eigenen „Leeren“-Knopf, und das Verschieben einer Datei lässt die übrigen Dateien links stehen (bisher leerte sich die Liste). Die Übergabe an die Agenten nimmt alle vier Stapel mit und benennt sie `Lebenslauf_…`, `Arbeitszeugnis_…`, `Bewerbung_…`, `Diplom_…`.

### Neu in 1.2.2

- **Jahreszahlen sind keine Postleitzahlen mehr:** `2026`, `2026 -`, `2025 - 2026`, `10/2026 -` und `10/2025 - 05/2026` wurden bisher in Bewerbungen als Schweizer PLZ samt Ort erkannt, weil hinter der Zahl irgendein Wort stand („2026 Muster AG“, „2026 Berufsmaturität“). Vierstellige Zahlen von 1900 bis 2099 gelten jetzt nur noch dann als PLZ, wenn ein `CH-`/`CH ` davorsteht oder ein echter Ort folgt (`2000 Neuchâtel`, `1950 Sion`); Firmen, Ausbildungen und Rollen machen daraus keine PLZ mehr.
- **Auch die KI-Erkennung trennt beides:** Meldet das Sprachmodell eine Jahreszahl als Ort, wird sie als Datum behandelt und nicht mehr unter „PLZ / Ort“ geschwärzt. Das gilt auch für Zeiträume wie `10/2025 - 05/2026`.
- **Zeilenumbrüche:** Die Erkennung „Ort in der Zeile darüber/darunter“ gilt nur noch für eindeutige Postleitzahlen außerhalb des Jahresbands – eine allein stehende Jahreszahl am Zeilenende wird nicht mehr zur PLZ.

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

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.3.5-Setup.exe`
herunterladen und ausführen (Installer, kein Administrator- oder
Python-Zubehör nötig).

### Geprüft

- 112 automatisierte Tests für Erkennung, Doppelklick auf Wörter, Hausnummern, Schweizer PLZ in getrennten Zeilen und Formularfeldern, Berufsbezeichnungen samt Zusammensetzungen, manuelle Werte, Regex, Überlappungen, Schwärzung, den Tesseract-Aufruf, den Neuaufbau der Textebene, die Klickbarkeit der Kopfknöpfe, die änderbaren Copilot-Texte, Kopfzeilen-Positionen, Update-Abfrage und gemerkte Einstellungen
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
