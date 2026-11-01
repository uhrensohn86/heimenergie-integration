# HeimEnergie Integration — v0.2.2-alpha (experimentell)

Backend für das [HeimEnergie Dashboard](https://github.com/uhrensohn86/heimenergie-dashboard).
**Kein Netzbezugszähler erforderlich.** Daten und Gerätekonfiguration bleiben ausschließlich lokal in Home Assistant. Keine Benutzer-YAML, keine manuell zu erstellenden Home-Assistant-Helfer.

> **Alpha-Version**: Erste Einrichtung und Erzeugung von Sensoren wurden in Home Assistant erfolgreich erprobt; die v0.2.2-Korrekturen benötigen noch einen Praxistest. Vor dem produktiven Einsatz vollständiges Backup erstellen. Die Integration erstellt eigene Sensoren, verändert oder löscht jedoch keine bestehenden Sensoren/Utility Meter.

## Einrichtung

1. Die `custom_components/heimenergie`-Dateien über HACS-Integration oder manuell installieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → HeimEnergie**.
4. Strompreis-Entität (optional) oder festen €/kWh-Preis sowie monatlichen Grundpreis eingeben.
5. Gewünschte Geräte in der Geräteliste wählen. Für Sensoren ohne Geräteeintrag alternativ direkt einen Leistungssensor wählen.
6. Fertig. Die Integration sucht passende Leistungs- und Energiesensoren, prüft, ob Zeitraumsensoren schon existieren, und stellt fehlende Zähler/Kostensensoren automatisch bereit.
7. Unter **Einstellungen → Geräte & Dienste → HeimEnergie → Konfigurieren** können Geräte und Preise später verändert werden.

## Was intern geschieht

- Kein Bedarf an eigenem Zähler für den gesamten Haushalt.
- Bevorzugt bestehende kumulative kWh-Sensoren desselben HA-Geräts. Wenn kein geeigneter Gesamt-Energiezähler existiert, integriert HeimEnergie die Leistung in W zeitlich zu kWh.
- Ordnet vorhandene Tages-/Wochen-/Monats-/Jahreszähler nach Gerätenamen, Einheit, Zeitraum und Sensor-Metadaten zu. Bei mehreren Tages-Energiezählern bevorzugt die Erkennung einen vorhandenen `*_verbrauch_heute`-Utility-Meter gegenüber `*_today_energy`, sofern dies eindeutig ist. Bei gleicher Bewertung wird kein Kandidat erraten. Alte Kostensensoren werden nur übernommen, wenn ihr Name exakt zur gewählten Energieentität passt (z. B. `*_verbrauch_heute` → `*_kosten_heute`); andernfalls werden Kosten aus *derselben* Energiequelle mit dem Arbeitspreis berechnet.
- Fehlende Werte werden als Sensoren in Home Assistant angelegt. Es sind keine externen `input_number`- oder Utility-Meter-Helfer nötig.
- Der Katalogsensor `HeimEnergie Katalog` enthält ausschließlich innerhalb Home Assistants die Geräte- und Sensorzuordnung. Das Frontend kann ihn lesen, ohne öffentliche Geräteprofile.
- Die Erfassungszustände werden über Home Assistants lokalen Speicher regelmäßig gesichert und beim kontrollierten Stoppen gespeichert.
- Der Grundpreis wird **einmal pro Haushalt/Tarif** ausgewiesen: Tag anteilig nach Monatstagen, Woche als Summe aus sieben Tagesanteilen, Monat als volle Monatsgebühr, Jahr als zwölffache Monatsgebühr.
- Gerätekosten enthalten nur den Arbeitspreis. Die Entität `Erfasste Kosten inkl Grundpreis` kombiniert diese *überwachten* Gerätekosten und den einmaligen Grundpreis. **Das ist ohne vollständigen Haushaltszähler keine Gesamtrechnung des Haushalts.**

## Grenzen der Alpha

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
