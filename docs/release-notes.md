## PDFblack 1.4.0

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.4.0

- **Zweite Ablagefläche für ganze Stapel:** Zieht man mehrere PDFs auf die rechte Fläche, öffnet PDFblack die erste und arbeitet danach eine Datei nach der anderen ab. Nach „Geschwärzte Kopie speichern“ kommt die nächste Datei von selbst; die Werkzeugleiste zeigt „Stapel 2 von 5“ mit dem Fortschritt, und im Stapelbetrieb entfällt die Rückfrage nach dem Speichern, damit der Ablauf nicht stockt.
- **Nächste Datei und Nachschub:** „Nächste Datei“ überspringt eine Datei ohne zu speichern. Werden während des Laufs weitere PDFs auf die rechte Fläche gezogen, hängen sie sich an den Stapel an, statt ihn zu ersetzen – die bereits abgearbeiteten Dateien bleiben abgehakt.
- **Scans im Stapel gehen denselben Weg wie einzeln abgelegte Dateien:** Hat die nächste Datei keinen Textlayer, öffnet sich PDFocr, liest den Scan aus und lädt das Ergebnis zurück nach PDFblack. Eine noch laufende Erkennung wird beim Wechsel abgebrochen, damit nicht das Ergebnis der vorherigen Datei in der neuen landet.
- **Kopfzeile zeigt nur noch einen Text:** Schnelles Hin- und Herschieben zwischen PDFblack, PDFcompare und PDFocr konnte den Text eines inaktiven Fensters eingeblendet lassen. Jede Blende landet jetzt zuverlässig im Zielzustand – es bleibt genau ein Text stehen.
- **Beim Beenden wird die Datei zuerst entladen:** Bisher war die geladene PDF beim Schließen noch offen, während PDFblack die geschwärzten Kopien löschte. Unter Windows scheiterte das an der Dateisperre und meldete „Diese Dateien konnten nicht gelöscht werden“ für genau die geladene Datei. Jetzt schließt PDFblack das Dokument vor dem Aufräumen; die Meldung erscheint nicht mehr, und auch die Arbeitsdatei der Texterkennung wird entfernt.

## PDFblack 1.3.18

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.18

- **Die Textebene aus Scans steht in Leserichtung:** PDFocr legte die erkannten Wörter mit `overlay=False` hinter das Bild, und PyMuPDF stellt jede solche Einfügung **vor** den bisherigen Inhalt. Die Textebene kam dadurch rückwärts heraus – die Wörter jeder Zeile in umgekehrter Reihenfolge, die Zeilen von unten nach oben. Aus „5. Februar 1990“ wurde `1990, Februar 5.`, aus „Wolfsbachstr. 6“ wurde `6 Wolfsbachstr.`, aus „9436 Balgach“ wurde `Balgach 9436`, und eine IBAN zerfiel in Bruchstücke. In der Vorschau blieben deshalb genau die Stellen leer, die im Scan klar dastehen: Geburtsdatum, Adresse samt Hausnummer und PLZ/Ort, Bankverbindung – dazu kamen Treffer an falschen Stellen. Die Wörter werden jetzt rückwärts eingesetzt, damit sie im Inhalt wieder vorwärts stehen; die Textebene liest sich wie der Scan, und die Regeln finden Geburtsdatum, Adresse und IBAN vollständig. Bereits ausgelesene Scans bringen ihre alte Textebene mit – die Datei in PDFocr neu einlesen, damit der Text in Leserichtung steht.

## PDFblack 1.3.17

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.17

- **Zeilen aus getrennten Textfeldern:** In vielen PDFs stehen die Teile einer Zeile in eigenen Textobjekten – Formularfelder, Tabellenzellen, rechtsbündige Hausnummern. Zwischen „Wolfsbachstrasse“ und „6“ oder zwischen „9436“ und „Balgach“ setzte die Textaufbereitung einen Zeilenumbruch, und der Treffer endete beim halben Wert: „Wolfsbachstrasse“ wurde gefunden, „Wolfsbachstrasse 6“ nicht, und „9436 Balgach“ verschwand. Jetzt entscheidet allein die Lage auf der Seite: Was auf derselben sichtbaren Zeile steht, wird als eine Zeile gelesen – auch über eine grosse Lücke zwischen zwei Feldern hinweg. Was PyMuPDF ohnehin als eine Zeile führt, bleibt immer zusammen. Geschützte, schmale und unsichtbare Leerzeichen, die beim Einlesen mitten im Wort stehen bleiben, zählen dabei als Trennzeichen.
- **Ausgeschriebene Geburtsdaten:** „5. Februar 1990“ wird jetzt auch dann als Datum gelesen und mit den übrigen Daten verglichen, wenn Tag, Monatsname und Jahr in getrennten Feldern stehen. Alle zwölf Monatsnamen sind abgedeckt, mit Tag ein- oder zweistellig (mit oder ohne Punkt) und Jahr zwei- oder vierstellig. Steht dasselbe Datum zusätzlich in Zahlenform (`05.02.1990`) im Dokument, tragen beide Stellen die Kategorie „Geburtsdatum“.
- **Datumsbeginn ist keine Hausnummer:** In einer Zeile wie „Eintritt 01.09.2020“ machte die Hausnummern-Regel bisher die Adresse „Eintritt 01“ daraus und verdrängte das Datum – ein Geburtsdatum konnte dadurch als Vergleichswert fehlen. Eine Zahl, die ein Datum beginnt (`01.09.2020`, `1. 9. 2020`, `01-09-2020`, `5.2.90`), gilt jetzt nicht mehr als Hausnummer. Hausnummernbereiche wie „Hauptstrasse 12-14“ bleiben Adressen.

## PDFblack 1.3.16

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.16

- **Ausgeschriebene Monate:** Das Geburtsdatum wird auch in Worten erkannt – „5. Februar 1990“, „5. Feb. 1990“ und „5. Feb. 90“ sind dasselbe Datum wie `05.02.1990`. Neu dazu kommt die in Zeugnissen häufige Abkürzung „Febr.“ („5. Febr. 1990“), ebenso „Jän.“. Die Schreibweise gilt für die Datums- und Geburtstagsmuster und für alle weiteren Stellen, an denen dasselbe Datum im Dokument steht.
- **Hausnummer mit Ort in einer Zeile:** „Musterstrasse 12 Zürich“ und „Seestrasse 7 CH-8000 Zürich“ werden jetzt vollständig gefunden. Bisher gehörte die Hausnummer nicht dazu, weil hinter ihr ohne Komma ein Wort stand – der Treffer endete beim Strassennamen. Der Ort selbst wird dabei nicht mitgeschwärzt, er bleibt ein eigener PLZ/Ort-Treffer.
- **Hausnummern in Spalten:** Stand die Hausnummer (oder PLZ und Ort) in einem eigenen Textblock neben dem Strassennamen – Tabelle, rechtsbündige Nummer, Formularfeld –, setzte die Textaufbereitung mitten in die Adresse einen Zeilenumbruch, und nur der halbe Treffer blieb übrig. Jetzt entscheidet die Lage auf der Seite: Wörter derselben sichtbaren Zeile bleiben zusammen.
- **Fünfstellige PLZ mit Ortschaft:** „82140 Olching“ und „D-82140 Olching“ werden auch dann erkannt, wenn PLZ und Ort in getrennten Feldern stehen. Die Ziffern bleiben vollständig – aus `82140` wird nie die Schweizer PLZ `8214`.
- **Umbrochene IBANs:** Steht der Rest einer IBAN in der nächsten Zeile, fehlten die letzten Zeichen im Treffer und die Prüfziffer schlug fehl. Die Nummer wird jetzt aus der Folgezeile ergänzt – aber nur, wenn sie damit eine gültige IBAN (Mod 97) ergibt. Reicht die Fortsetzung nicht, bleibt die abgeschnittene Nummer stehen und der Hinweis meldet es weiterhin.
- **Strengere Ortsprüfung:** Nur ein echter Ortsname macht die Hausnummer zur Adresse. „Bahnhof 5 Züge“ ist keine Adresse mehr, nur weil „Zügen“ in der Ortsliste steht – verglichen wird die genaue Schreibweise (Akzente und Umlaut-Umschrift bleiben erlaubt). Bei PLZ und Ort bleibt die bisherige Toleranz erhalten.

## PDFblack 1.3.15

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.15

- **Plausibilitätsprüfung mit Hinweisen:** Jeder gefundene Wert wird gegengeprüft, bevor du ihn schwärzt – ohne dass sich an der Schwärzung etwas ändert. IBANs laufen über die Mod-97-Prüfziffer („IBAN-Pruefziffer stimmt nicht“), Daten müssen ein echtes Kalenderdatum sein („09.0.2022“ fällt auf, ebenso der 31. Februar oder ein Jahr vor 1900), vierstellige PLZ werden samt Ortschaft gegen die amtliche Liste geprüft („PLZ 9999 steht nicht im Schweizer Verzeichnis“, „„Olching“ gehoert nicht zur PLZ 8200“) und Strassen gegen das Strassenverzeichnis, auch in aufgeteilter Schreibweise. Fünfstellige PLZ aus Deutschland und Österreich bleiben ungeprüft – dafür führt das Programm keine Liste und meldet deshalb auch nichts. Die Hinweise stehen in einer eigenen Spalte der Trefferliste und im Tooltip.
- **Blinkende Prüfstellen:** Treffer mit einem solchen Hinweis – und Stellen mit korrigiertem Wert – pulsieren im Dokument in Warn-Orange (rund zweimal pro Sekunde, mit halbtransparenter Fläche). Die Stelle ist damit sofort zu finden, auch über der farbigen Kategorie-Markierung. Sobald du den Hinweis quittierst oder den Wert korrigierst, hört das Blinken auf; sind keine Prüfstellen mehr übrig, stoppt es ganz.
- **Rechtsklick-Menü im PDF:** Ein Rechtsklick auf eine Fundstelle im Dokument öffnet dasselbe Menü wie in der Trefferliste: schwärzen oder nicht schwärzen, Kategorie ändern (mit Häkchen an der aktuellen), „Kein Treffer (Fehlalarm)“, bei einem Prüfhinweis „Hinweis geprüft – trotzdem schwärzen“ und „Wert korrigieren …“. Ab zwei gleichen Stellen kommen die Aktionen für alle hinzu: Kategorie für alle ändern, alle als Fehlalarm abhaken, alle umschalten. Beide Menüs baut derselbe Baustein, sie können also nicht mehr auseinanderlaufen.
- **Wert korrigieren mit eigener Lern-Art:** Hat OCR eine Ziffer verschluckt, lässt sich der Wert im Menü richtigstellen. Der neue Wert wird erneut geprüft („31.02.2022“ wird abgelehnt), erscheint in der Liste und in der Lerndatei; geschwärzt wird weiterhin die gefundene Stelle, ihr Rechteck dabei um rund ein Zeichen je Seite verbreitert, damit kein Rest der verschluckten Ziffer stehen bleibt – die Stelle behält dafür den Hinweis „Wert korrigiert – Stelle im PDF prüfen“. Solche Korrekturen landen als eigener Eintragstyp `wertkorrektur` in der Lerndatei: nachvollziehbar im Lernfenster, aber ohne Beitrag zur Musterableitung.
- **Namens-, Strassen- und Ortsvarianten:** Steht ein Begriff mehrfach im Dokument, gilt eine seltene Schreibweise mit genau einem Buchstaben Abstand als Lesefehler desselben Begriffs – „Witler“ neben zehnmal „Wittler“ wird mitgeschwärzt, ebenso „Olchin“ neben „Olching“ oder „Säagmühlstrasse“ neben „Sägmühlstrasse“. Voraussetzung sind mindestens drei Treffer des richtigen Begriffs und höchstens ein Drittel davon für die Variante. Was selbst im Namens-, Strassen- oder Berufsverzeichnis steht, bleibt eigenständig: „Müller“ und „Möller“ verschmelzen nicht, ebenso zwei echte Ortschaften.
- **Vornamen-Ausnahme:** Steht ein Vorname mindestens zehnmal im Dokument und eine Schreibweise mit einem Buchstaben Abstand genau einmal, gilt sie auch dann als Lesefehler, wenn sie selbst ein Vorname ist („Joana“ zehnmal, „Joanna“ einmal). Neun Treffer oder zwei Varianten reichen nicht – so bleibt eine zweite Person im Dokument unangetastet.
- **Aufgeteilte Strassen:** Der Scanner trennt Strassennamen manchmal auf. „Haupt strasse 56 a“, „Haupt str. 56 a“ und „Dorf pl. 7“ werden jetzt gefunden – mit Hausnummer und ohne („wohnhaft in der Haupt strasse“). Geprüft wird immer der zusammengesetzte Name am Verzeichnis, deshalb wird „Am Weg 5“ nicht zur Adresse. Die Endungen stammen aus einer einzigen Liste, aus der sich die getrennte Schreibweise ableitet; `str`/`str.` stehen für „Strasse“, `pl.` für „Platz“, und Endungen, die im Verzeichnis praktisch nicht vorkommen, bleiben als Einzelwort aussen vor.

## PDFblack 1.3.14

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.14

- **Strassenverzeichnis der Schweiz:** Das amtliche Verzeichnis der Strassen von swisstopo steckt jetzt im Programm – 130 320 Strassennamen in allen Landessprachen (freie Nutzung). Ein Strassenname wird damit auch **ohne Hausnummer** erkannt („Bahnhofstrasse“ allein reicht), und Abkürzungen passen zur ausgeschriebenen Form: „Bahnhofstr.“ wird als „Bahnhofstrasse“ gefunden, „Sägmühlstrasse“ als „Saegmuehlstrasse“. Einzelne Gattungsworte, die in irgendeiner Gemeinde als Strasse geführt werden („Ring“, „Park“, „Hof“), bleiben unangetastet, damit normaler Text nicht angestrichen wird. Neu bauen: `python tools/build_strassen_data.py`.
- **Namensverzeichnis der Schweiz:** Vor- und Nachnamen der ständigen Wohnbevölkerung vom Bundesamt für Statistik (65 150 Vornamen, 206 023 Nachnamen, OPEN-BY). Ein Nachname, der wie eine Strasse endet, bleibt damit ein Name („Steinberg“), und ein erkannter Strassenname liefert keine Namensbestandteile mehr („Rue du Rhône“). Das Verzeichnis wirkt nur bei der Namensübertragung; als Ort gemeldete Treffer der KI werden nicht umetikettiert. Neu bauen: `python tools/build_namen_data.py`.
- **Aus der Lerndatei gelernt:** Telefonnummern brauchen mindestens sechs Ziffern – Vierergruppen aus IBAN und Handelsregister ergeben keine Nummer mehr. Sachwörter wie „Urlaub“ oder „Nachtragsmanagement“ und Kürzel wie „DE80“ gelten nicht mehr als Person. „HRB 10710“, BIC und Vorwahlen in Klammern sind kein Ort. Zeiträume wie `05/2013 - 07/2013` bleiben ein Datum, und ein Monat oder „Jahr“ unter einer Zahl ist keine Firma.

## PDFblack 1.3.13

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.13

- **Jedes Datum bleibt ein Treffer:** Bisher blieb von den Datumsangaben nur das Geburtsdatum übrig – ein Datum wie `5.8.11` verschwand, sobald es zu nah am nächsten Datum lag (2011 zu 2025 sind 14 Jahre). Jetzt stehen alle erkannten Daten in der Trefferliste und lassen sich einzeln abwählen; nichts verschwindet mehr still, nur weil es kein Geburtsdatum ist.
- **Das Geburtsdatum wird zusätzlich markiert:** Liegt das älteste Datum mindestens 15 Jahre vor dem nächsten, trägt es weiterhin die Kategorie **„Geburtsdatum“** mit der Quelle „ältestes Datum“; die übrigen Daten stehen daneben als **„Datum“**. Gibt es kein Geburtsdatum, bleiben trotzdem alle Daten sichtbar. Das Häkchen heißt jetzt „Datum (Geburtsdatum = ältestes Datum)“.
- **Neue Kategorie „Jahr“ mit eigenem Häkchen:** Allein stehende Jahreszahlen von 1900 bis 2099 – etwa „Bericht 2025“ – erscheinen als **„Jahr“** in eigener Farbe und lassen sich über „Jahr (allein stehende Jahreszahl)“ getrennt ein- und ausschalten. Steht die Jahreszahl in einem vollständigen Datum, bleibt sie Teil des Datums; eine Nummer wie „Personalnummer: 1998“ bleibt eine Nummer.

## PDFblack 1.3.12

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.12

- **PDFblack lernt aus Korrekturen:** Rechtsklick auf einen Treffer öffnet die Kategorieliste – alle Kategorien aus den Gruppen, ohne „Manuell“ und „Regex“. Die Wahl gilt sofort, steht danach in der Quelle („KI (Presidio) · LOCATION · gelernt: Person“) und wird als Beispiel gespeichert; beim nächsten Durchlauf ordnet PDFblack denselben Text von selbst so ein. Auf Wunsch gilt die Korrektur für **alle Treffer mit demselben Text** – ein Eintrag im Kontextmenü, ein Klick.
- **Fehlalarme beibringen:** „Als Fehlalarm melden“ nimmt einen Treffer aus den Schwärzungen, lässt ihn aber in der Liste stehen, damit die Entscheidung nachvollziehbar bleibt. Auch das gilt auf Wunsch für alle gleichen Textes. Manuell gesetzte Werte und eigene Regexe bleiben unangetastet.
- **Lerndatei im Datei-Menü:** „Lerndatei herunterladen …“ speichert alle Beispiele als JSONL-Datei für die Weiterentwicklung. „Lerndatei ansehen …“ zeigt sie in einem Fenster mit Text, alter und neuer Kategorie, Zeitpunkt sowie Seite und Quelle im Tooltip; markierte Zeilen lassen sich einzeln löschen, die übrigen Regeln bleiben. „Lerndatei zurücksetzen …“ verwirft nach Rückfrage alles.
- **Die Lerndatei bleibt erhalten:** Sie liegt unter `%USERPROFILE%\PDFblack\lerndatei.jsonl`, und das Aufräumen beim Beenden betrifft nur den Ordner `Geschwärt` – Gelerntes überlebt also jeden Programmstart.
- **Statuszeile zählt mit:** Nach jedem Durchlauf steht dort, wie viele Treffer die Lerndatei abgehakt und wie viele sie umkategorisiert hat.
- **Gelerntes wird zu festen Regeln:** `python tools/lerndatei_regeln.py <Lerndatei>` wertet die exportierten Beispiele aus und schreibt mit `--schreiben` die tauglichen Muster nach `core/gelernt.py` – sie greifen danach ohne Lerndatei. Mehrfach belegte Muster werden verallgemeinert (`IAO-4711` und `IAO-2233` ergeben `IAO-\d+`), Fehlalarme werden ausgeschlossen, Einzelfälle nur auf Wunsch wörtlich übernommen. Was offen bleibt – nur Ziffern, zu kurze Texte, widersprüchliche Beispiele, manuell Eingegebenes – steht im Bericht und im Lernfenster in der Spalte „im Code“ als „–“.
- **Datumsangaben in allen üblichen Schreibweisen:** Erkannt werden jetzt `12.03.1985`, `12.3.85`, `3. 12 1985`, `12. 03. 1985`, `12/03/1985`, `5/2/90`, `12-3-85`, `05/31/1990` (Monat vorn, wenn die zweite Zahl kein Tag sein kann), `12. März 1985`, `3. März 85`, `3. Sept. 1999`, `1985-03-12` und `1985.03.12` – dazu die Schreibweisen `März`, `Maerz`, `Marz` und `Jänner`/`Jaenner`. Lesen und Erkennen nutzen dieselben Muster, ein Format kann also nicht mehr nur an einer Stelle dazukommen.
- **Monat/Jahr ist kein Geburtsdatum:** `10/2025`, `1/85`, `03.1985` und „März 1985“ dienen nur noch als Vergleichsdatum – sonst würde jede Nummer wie `12/34` zum Datum. Bei fehlendem Tag entscheidet weiterhin der Mindestabstand von 15 Jahren.
- **Arbeitsdateien der Texterkennung werden beim Beenden gelöscht:** Nach dem Neuaufbau einer Textebene und dem Auslesen eines Scans bleiben im temporären Ordner keine PDFs mehr liegen; die geöffnete Datei wird erst entfernt, nachdem das Dokument geschlossen ist.

## PDFblack 1.3.11

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.11

- **Einziges Datum im Dokument wird als Geburtsdatum erkannt:** Steht nur ein vollständiges Datum in der PDF – etwa `05/02/1990` –, vergleicht PDFblack es mit der nächsthöheren Jahreszahl im Text. Liegen dazwischen mindestens 15 Jahre (z. B. „Anmeldung 2020“), gilt das Datum als Geburtsdatum und wird geschwärzt. Liegt die nächste Jahreszahl näher („1998“), bleibt es unangetastet.
- **Datumsangaben mit Schrägstrich:** `05/02/1990` und `5/2/90` (Tag/Monat/Jahr) werden gelesen und geschwärzt – bisher nur die Punktform. `10/2025` bleibt Monat/Jahr und zählt nicht als vollständiges Datum.

## PDFblack 1.3.10

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.10

- **Das Geburtsdatum ist das älteste Datum:** PDFblack liest beim Durchlauf alle Datumsangaben mit – `12.03.1985`, `12.3.85`, `12. März 1985`, `3. März 85` und ISO `2026-10-20` – und nimmt das älteste davon als Geburtsdatum. Voraussetzung: Es liegt mindestens 15 Jahre vor dem nächstjüngeren Datum. Erscheint es in der Trefferliste, steht dort die Kategorie **„Geburtsdatum"**. Das Häkchen „Geburtsdatum (ältestes Datum)" ist jetzt standardmäßig an, die Regel greift also beim Öffnen ohne weiteres Zutun.
- **Nur das Geburtsdatum wird geschwärzt:** Rechnungs-, Ablauf- und Eintrittsdaten dienen nur noch der Einordnung des Geburtsdatums und erscheinen nicht mehr als Treffer. Gibt es nur ein Datum oder liegen die beiden ältesten näher als 15 Jahre beieinander, wird kein Datum geschwärzt.
- **Alle Schreibweisen werden mitgeschwärzt:** Wird das Geburtsdatum als `1.3.95` erkannt, verschwinden auch `01. März 1995`, `1. 3. 1995`, `01.03.1995`, `1. Maerz 95` und `1995-03-01` im ganzen Dokument. Damit dabei keine andere Regel dazwischenfunkt („Geboren am 01" als Hausnummer), hat das Geburtsdatum beim Auflösen von Überlappungen Vorrang.
- **Gleichlautende Treffer zusammen umschalten:** Rechtsklick oder Doppelklick auf einen Treffer schaltet alle Einträge mit demselben Namen auf einmal – angehakt → alle aus, abgehakt → alle an. Das gilt in der Trefferliste wie im Abschnitt „Nach Kategorie", und beide Listen bleiben dabei im Gleichklang.

## PDFblack 1.3.9

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.9

- **Der ausgelesene Scan steht von selbst in PDFblack:** Wird eine PDF ohne Textebene geöffnet, wechselt PDFblack wie bisher zu PDFocr und startet die Erkennung. Ist sie fertig, lädt PDFblack das Ergebnis jetzt selbst – genau wie ein Klick auf „In PDFblack öffnen“: Der Scan ist samt neuer Textebene geladen, und die Prüfung beginnt sofort mit Namen, Adressen, Nummern und Regexen. Der Knopf bleibt für den Fall, dass man das Ergebnis später noch einmal holen will.
- **Handarbeit in PDFocr bleibt Handarbeit:** Nur die von PDFblack angestoßene Erkennung öffnet sich von selbst. Wer PDFocr selbst öffnet oder dort eine andere Datei ausliest, entscheidet weiterhin selbst, was in PDFblack landet.
- **Kein zweiter Durchlauf für dieselbe Datei:** Das Ergebnis einer Erkennung wird nicht noch einmal ausgelesen, auch wenn der Scan wenig Text enthält. Jeder Erkennungslauf bekommt außerdem eine eigene Arbeitsdatei, damit eine weitere Erkennung die bereits geöffnete Datei nicht überschreibt.

## PDFblack 1.3.8

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.8

- **Geschwärzte Kopie im Benutzerordner:** Der Knopf „Neu speichern unter …“ heißt jetzt **„Geschwärzte Kopie speichern“** und fragt nicht mehr nach einem Speicherort. Die geschwärzte Fassung landet automatisch in `%USERPROFILE%\PDFblack\Geschwärt` (unter Linux/macOS `~/PDFblack/Geschwärt`); heißt die Quelle `Brief.pdf`, entsteht `Brief_geschwaerzt.pdf`, bei Bedarf durchnummeriert. Die Meldung nennt den vollständigen Pfad, die Kopie steht weiterhin unter „Zuletzt geschwärzt“.
- **Die Ablage räumt sich beim Beenden selbst auf:** Beim Schließen von PDFblack werden die Kopien in diesem Ordner samt eventueller Kopien im Copilot-Übergabeordner gelöscht – die alte Rückfrage nach den geschwärzten Dateien entfällt damit. Das Original bleibt unverändert; wer die Kopie behalten will, gibt sie vor dem Beenden weiter.
- **Regex-Anker gelten pro Zeile:** `^` und `$` in eigenen Ausdrücken wurden bisher gegen den gesamten Seitentext geprüft, ein Muster wie `^\d{12}$` fand deshalb nur Seiten, die ausschließlich aus der Nummer bestehen. Jetzt passen die Anker auf Zeilenanfang und Zeilenende, die Lizenznummer `558416824044` wird also auch dann gefunden, wenn sie allein in ihrer Zeile steht. Steht sie mitten in einer Zeile („Lizenznummer: 558416824044“), nimmt man Wortgrenzen: `\b\d{12}\b`.

## PDFblack 1.3.7

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.7

- **Die Texterkennung steckt komplett im Programm:** Tesseract und Leptonica kommen als Bibliotheken mit (`tesserocr`), die Sprachdateien liegen in der Anwendung. PDFocr und der Neuaufbau der Textebene brauchen damit **keine Tesseract-Installation, keine Adminrechte und keinen Download** mehr – auch auf Rechnern ohne Tesseract. Die Nachinstallation über `winget` samt Prüfung beim Start ist entfallen; die Umgebungsvariablen `PDFBLACK_TESSERACT` und `PDFBLACK_NO_OCR_CHECK` gibt es nicht mehr.
- **Alle Sprachen der Auswahlliste liegen bei:** Deutsch, Englisch, Französisch und Italienisch (`tessdata_fast`, Apache-2.0) sind enthalten. Die Erkennung läuft offline; eine Meldung über fehlende Sprachdateien kann nur noch auftreten, wenn eine Installation unvollständig ist.
- **Die Prüfung startet beim Öffnen von selbst:** Wird eine PDF mit Textebene geladen, sucht PDFblack Namen, Adressen, PLZ/Ort, Nummern, Kontaktdaten, eigene Werte und Regexe sofort – ein Klick auf „Vorschau erzeugen“ ist nicht mehr nötig; der Knopf bleibt zum Wiederholen. Ist keine Erkennung eingeschaltet oder ein Regex fehlerhaft, erscheint nur ein Hinweis in der Statuszeile.
- **Datenschutzhinweis angepasst:** Die einzige Netzwerkverbindung ist die Update-Prüfung – die Nachinstallation von Tesseract über `winget` entfällt.

## PDFblack 1.3.6

PDF-Dateien automatisch schwärzen – mit farbiger Vorschau vor dem Speichern.

### Neu in 1.3.6

- **„Unterlagen prüfen …“ nimmt alle Stapel mit:** Bisher gingen nur Lebenslauf und Arbeitszeugnisse in den Prüflauf; Dateien aus „Bewerbung“ und „Diplome“ blieben unberücksichtigt, auch wenn sie hinterlegt waren. Jetzt prüft PDFcompare alle vier Stapel auf fehlende Textebenen (Scans), doppelte Dateien und nicht mehr vorhandene Dateien – die Zusammenfassung zählt sie mit. Die Frage an Copilot nennt zusätzlich die Dateien aus Bewerbung und Diplomen. Zeiträume und Lücken kommen weiterhin aus dem Lebenslauf, die Reihenfolge aus den Zeugnissen.

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

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.4.0-Setup.exe`

PDFblack läuft unter Windows 10 und 11. `PDFblack-1.3.18-Setup.exe`
herunterladen und ausführen (Installer, kein Administrator- oder
Python-Zubehör nötig).

### Geprüft

- 295 automatisierte Tests für Erkennung, Doppelklick auf Wörter, Hausnummern (auch mit Ort dahinter, in getrennten Textblöcken und mit einem Datum davor), fünfstellige PLZ mit Ortschaft, Schweizer PLZ in getrennten Zeilen und Formularfeldern, das Schweizer Strassen- und Namensverzeichnis samt Vergleichsschreibweise, aufgeteilte Strassen und Abkürzungen, Schreibvarianten von Namen, Strassen und Orten, Berufsbezeichnungen samt Zusammensetzungen, alle Datumsformate samt ausgeschriebenen und abgekürzten Monaten („Febr.“, alle zwölf Monatsnamen, auch in getrennten Textfeldern), umbrochene IBANs, die Kategorie „Jahr“ und die Geburtsdatums-Regel, die Plausibilitätsprüfung (IBAN-Prüfziffer, Kalenderdatum, PLZ/Ort, Strassen), die Hinweis-Aktionen samt Wertkorrektur und Prüf-Blinken, die Lerndatei (Korrekturen, Fehlalarme, Wertkorrekturen, Export, Zurücksetzen, Erhalt beim Beenden), die festen Regeln aus der Lerndatei, manuelle Werte, Regex, Überlappungen, Schwärzung, den Tesseract-Aufruf, die Leserichtung der aus Scans erzeugten Textebene, den Neuaufbau der Textebene, die Klickbarkeit der Kopfknöpfe, die änderbaren Copilot-Texte, Kopfzeilen-Positionen samt Blendenaustausch bei schnellem Wechsel, den Stapel (zweite Ablagefläche, Nächste Datei, Nachschub, Scan im Stapel), das Entladen des Dokuments vor dem Aufräumen beim Beenden, Update-Abfrage und gemerkte Einstellungen
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
