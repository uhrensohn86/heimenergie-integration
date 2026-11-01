# HeimEnergie Integration — v0.2.3-alpha (experimentell)

Backend für das [HeimEnergie Dashboard](https://github.com/uhrensohn86/heimenergie-dashboard).
**Kein Netzbezugszähler erforderlich.** Daten und Gerätekonfiguration bleiben ausschließlich lokal in Home Assistant. Keine Benutzer-YAML, keine manuell zu erstellenden Home-Assistant-Helfer.

> **Alpha-Version**: Die bisherigen Sensoren und Zähler wurden in Home Assistant getestet. Der neue v0.2.3-Einrichtungsablauf benötigt noch einen Praxistest auf Android und Home Assistant. Vor dem produktiven Einsatz vollständiges Backup erstellen. Die Integration erstellt eigene Sensoren, verändert oder löscht jedoch keine bestehenden Sensoren/Utility Meter.

## Einrichtung

1. Die `custom_components/heimenergie`-Dateien über HACS-Integration oder manuell installieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → HeimEnergie**.
4. Strompreis-Entität (optional) oder festen €/kWh-Preis sowie monatlichen Grundpreis eingeben.
5. Messgeräte (Steckdosen usw.) auswählen. Für Leistungssensoren ohne Geräteeintrag alternativ den Sensor direkt wählen.
6. **Neu:** Im nächsten Schritt pro neuem Messgerät den tatsächlich gemessenen Verbraucher wählen: vorhandenes HA-Gerät auswählen **oder** einen Verbraucher-Namen eingeben (mit optionalem Typ). Der Dialog wird pro neu hinzugefügtem Messgerät geöffnet. Bei bestehenden Zuordnungen erfolgt dies nur auf ausdrücklichen Wunsch.
7. Fertig. Die Integration sucht passende Leistungs- und Energiesensoren, prüft, ob Zeitraumsensoren schon existieren, und stellt fehlende Zähler/Kostensensoren automatisch bereit.
8. Unter **Einstellungen → Geräte & Dienste → HeimEnergie → Konfigurieren** können Geräte und Preise später verändert werden.

## Was intern geschieht

- Kein Bedarf an eigenem Zähler für den gesamten Haushalt.
- Bevorzugt bestehende kumulative kWh-Sensoren desselben HA-Geräts. Wenn kein geeigneter Gesamt-Energiezähler existiert, integriert HeimEnergie die Leistung in W zeitlich zu kWh.
- Trennt Messgerät (z. B. eine Steckdose) und Verbraucher (z. B. den daran angeschlossenen Kühlschrank) dauerhaft in der lokalen Konfiguration. Vorhandene Zähler werden unter dem ausdrücklich zugeordneten Verbrauchernamen gesucht.
- Ordnet vorhandene Tages-/Wochen-/Monats-/Jahreszähler nach Gerätenamen, Einheit, Zeitraum und Sensor-Metadaten zu. Bei mehreren Tages-Energiezählern bevorzugt die Erkennung einen vorhandenen `*_verbrauch_heute`-Utility-Meter gegenüber `*_today_energy`, sofern dies eindeutig ist. Bei gleicher Bewertung wird kein Kandidat erraten. Alte Kostensensoren werden nur übernommen, wenn ihr Name exakt zur gewählten Energieentität passt (z. B. `*_verbrauch_heute` → `*_kosten_heute`); andernfalls werden Kosten aus *derselben* Energiequelle mit dem Arbeitspreis berechnet.
- Fehlende Werte werden als Sensoren in Home Assistant angelegt. Es sind keine externen `input_number`- oder Utility-Meter-Helfer nötig.
- Der Katalogsensor `HeimEnergie Katalog` enthält ausschließlich innerhalb Home Assistants die Geräte- und Sensorzuordnung. Das Frontend kann ihn lesen, ohne öffentliche Geräteprofile.
- Die Erfassungszustände werden über Home Assistants lokalen Speicher regelmäßig gesichert und beim kontrollierten Stoppen gespeichert.
- Der Grundpreis wird **einmal pro Haushalt/Tarif** ausgewiesen: Tag anteilig nach Monatstagen, Woche als Summe aus sieben Tagesanteilen, Monat als volle Monatsgebühr, Jahr als zwölffache Monatsgebühr.
- Gerätekosten enthalten nur den Arbeitspreis. Die Entität `Erfasste Kosten inkl Grundpreis` kombiniert diese *überwachten* Gerätekosten und den einmaligen Grundpreis. **Das ist ohne vollständigen Haushaltszähler keine Gesamtrechnung des Haushalts.**

## Grenzen der Alpha

- Ein **Verbraucherwechsel an einer Steckdose** muss ausdrücklich über *Konfigurieren → Bereits zugeordnete Verbraucher erneut bearbeiten → Anderen Verbraucher angeschlossen* bestätigt werden. Dann startet eine neue, unabhängige Zähleridentität und es werden keine vollständigen historischen Tages-/Monatswerte der alten Last übernommen. Eine reine Umbenennung lässt dieselbe Identität und ihre bisherige Historie bestehen. Die bisherigen privaten Tracker bleiben gespeichert; inaktive ältere, eigene Entitäten können in Home Assistant auf *nicht verfügbar* stehen. Ein eigener historischer Verbraucher-Archivbildschirm ist noch nicht implementiert.
- Neue Zeitraumsensoren starten **ab Einrichtung**. Es gibt keine erfundenen historischen Werte und kein automatisches Nachtragen alter HA-Statistiken.
- Bei Ableitung von kWh aus W hängt die Genauigkeit von der Aktualisierungsfrequenz ab. Unterbrechungen über fünf Minuten werden nicht als gemessene Energie ausgegeben. Bei kumulativen kWh-Sensoren können Zählerstände während HA-Ausfällen nachgeholt werden.
- **Änderungen des Strompreises** wirken bei selbst berechneten Zeitraumkosten zunächst auf den gesamten aktuellen Zeitraum. Historische Tarifwechsel werden noch nicht gesondert abgerechnet.
- Wenn ein kumulativer kWh-Sensor nur selten meldet und eine Periodengrenze überschreitet, kann die Differenz nicht präzise zeitlich aufgeteilt werden. Für eine korrekte zeitliche Historie sollen später HA-Langzeitstatistiken verwendet werden.
- Mehrdeutige Sensorzuordnungen und Sensoren ohne Registry-Eintrag erfordern ggf. die separate Auswahl des Leistungssensors.
- Für eine verlässliche automatische Wiederverwendung älterer, von YAML erzeugter Zeitraumsensoren muss deren Namens-/Gerätebezug eindeutig erkennbar sein.
- Keine Tarifhistorie, keine Termumeter-Anbindung und keine automatische Migration der bestehenden HeimEnergie-Dashboard-Konfiguration.

## Lizenz

MIT. Es wurden keine Quellcodebestandteile von PowerCalc oder anderen Drittprojekten übernommen.

## Aktualisieren von v0.2.1 auf v0.2.2

1. Über HACS neu herunterladen und Home Assistant neu starten.
2. **Einstellungen → Geräte & Dienste → HeimEnergie → Konfigurieren** öffnen und dieselbe Geräteauswahl erneut speichern. Nur dadurch wird die mit v0.2.1 gespeicherte Sensor-Zuordnung neu berechnet.
3. Bei dem Testgerät im `HeimEnergie Katalog` `energy_today` und `cost_today` prüfen. Vorhandene korrekte Zähler sollen wiederverwendet werden.
4. Erst danach weitere Geräte hinzufügen.

Bei einer geänderten Geräte- oder Zeitraumzuordnung bereinigt HeimEnergie jetzt alte, nicht mehr benötigte **eigene** Geräte-Zeitraumsensoren aus der Entitätsregistrierung. Fremde Sensoren werden dabei nicht entfernt.

Entfernen des HeimEnergie-Integrationseintrags löscht ab v0.2.2 auch seine eigene lokale Zähler-Checkpoint-Datei. **Ein normales Neu-Laden der Integration löscht diese Datei ausdrücklich nicht.** Andere Home-Assistant-Sensoren und Utility Meter bleiben unberührt. Die unabhängige Langzeit-Historie des Home-Assistant-Recorders wird nicht automatisch bereinigt.

Die automatische Zuordnung bleibt heuristisch: Namensgleichheit beweist keine identische Messquelle. Prüfe insbesondere nach Geräteumbenennungen oder mehreren Steckdosen pro HA-Gerät die Zuordnung im Katalog. Frühere Zählerwerte der neuen HeimEnergie-Sensoren werden nicht rückwirkend zusammengeführt.

## Neu in v0.2.3-alpha – Verbraucher hinter Messgerät

- Zwei UI-Schritte: erst Messgerät(e) und Stromtarif auswählen, danach jeden neuen Verbraucher einem Messgerät zuordnen. Entweder ein vorhandenes Home-Assistant-Gerät zuordnen oder einen **neuen logischen Verbraucher** mit frei gewähltem Namen und Typ anlegen. Der neue logische Verbraucher ist ein HeimEnergie-Datensatz; es wird **kein physisches HA-Gerät und kein Helfer** neu angelegt.
- Beispiel ohne persönliche Geräte-IDs: *Plug A* → *Kühlschrank*. Vorhandene passend benannte Energie-/Kostensensoren werden anhand des Verbrauchernamens erneut gesucht. Mehrdeutige Zuordnungen werden nicht erraten.
- Interne Zählerstände und historische Verbraucherzuordnungen werden unter stabilen Messsitzungs-IDs im lokalen Home-Assistant-Speicher gehalten. Der Anzeigename und der Gerätemodelltyp sind davon unabhängig. Das Archiv sichert auch die letzte verwendete Zuordnung bereits vorhandener Fremdsensoren, nicht deren komplette HA-Recorder-Messhistorie. Bereits vorhandene v0.2.2-Zähler behalten beim ersten Update ihre bisherige Identität, solange es sich nur um eine Umbenennung handelt.
- Für einen **echten Wechsel** der angeschlossenen Last ist die Checkbox „Anderen Verbraucher angeschlossen – neue Messung beginnen“ erforderlich. Damit wird eine neue interne Identität vergeben; bisherige, von der Steckdose kumulierte Zeitraumwerte werden **nicht** als neue Verbrauchswerte übernommen. Die alte interne Historie bleibt lokal gespeichert. Auch spätere Tarifänderungen oder Neukonfigurationen dürfen diesem Verbraucher keine alten Tages-/Monatszähler von vor dem Wechsel zuordnen.
- Beim normalen Hinzufügen weiterer Messgeräte werden bereits zugeordnete Verbraucher übernommen; für Änderungen bestehender Zuordnungen dient die Checkbox „Bereits zugeordnete Verbraucher erneut bearbeiten“.
- Der Katalog enthält zusätzlich `meter_name`, `consumer_type` und `consumer_device_id`, damit das Dashboard technische Steckdose und Verbraucher unterscheiden kann. Die persönliche Zuordnung bleibt in Home Assistant und wird nicht auf GitHub veröffentlicht.

### Upgrade v0.2.2 → v0.2.3 (empfohlen nur mit Backup)

1. Über HACS aktualisieren und Home Assistant neu starten.
2. Bei **HeimEnergie → Konfigurieren** die bisherige Geräteauswahl unverändert lassen. Weil v0.2.2 noch keine Verbraucherzuordnungen gespeichert hat, fragt die Integration einmalig für die vorhandenen Messgeräte nach dem Namen/HA-Verbraucher.
3. Den ursprünglichen Verbraucher zuordnen und **„Anderen Verbraucher angeschlossen“ ausgeschaltet lassen**, wenn die Steckdose noch dasselbe Gerät überwacht. So werden bestehende interne Zähler nicht zurückgesetzt.
4. Prüfen: `sensor.heimenergie_katalog` zeigt getrennte technische Namen und Verbrauchernamen, und die Energie- und Kostenzähler passen zum gewählten Verbraucher.
5. Einen tatsächlichen Steckdosenwechsel erst separat testen, wenn die normale Zuordnung funktioniert.

Dies ist noch keine vollständige, produktiv geprüfte Historienmigration über verschiedene Netz- und Messgeräte hinweg. Exakte rückwirkende Zeitanteile und Tarifhistorien sind weiterhin nicht implementiert.
