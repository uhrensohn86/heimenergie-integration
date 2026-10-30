# HeimEnergie Integration — v0.2.0-alpha (experimentell)

Backend für das [HeimEnergie Dashboard](https://github.com/uhrensohn86/heimenergie-dashboard).
**Kein Netzbezugszähler erforderlich.** Daten und Gerätekonfiguration bleiben ausschließlich lokal in Home Assistant. Keine Benutzer-YAML, keine manuell zu erstellenden Home-Assistant-Helfer.

> **Alpha-Version**: Code und Rechenfunktionen sind lokal geprüft, noch nicht auf einer echten Home-Assistant-Instanz getestet. Vor dem produktiven Einsatz vollständiges Backup erstellen. Die Integration erstellt eigene Sensoren, verändert oder löscht jedoch keine bestehenden Sensoren/Utility Meter.

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
- Prüft vorhandene passende Tages-/Wochen-/Monats-/Jahreszähler und Kostenentitäten auf eindeutige Zuordnung. **Bei Mehrdeutigkeit wird nichts blind zugeordnet; fehlende Sensoren werden neu bereitgestellt.**
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
