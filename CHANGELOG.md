# HeimEnergie Integration – Änderungsprotokoll

Die Integration befindet sich in der Alpha-Entwicklung. Die angegebenen Versionsnummern beziehen sich auf den Integrationscode; veröffentlichte GitHub-Releases erhalten zusätzlich einen Tag mit führendem `v`.

## 0.2.5 – Veröffentlichungs- und HACS-Pflege

- Version auf 0.2.5 erhöht, damit HACS einen neuen Release erkennen kann.
- Erstes GitHub-Release mit Release-Notes und automatischen Tests.
- Keine Änderungen an der Sensorberechnung oder den Messgerätezuordnungen.

## 0.2.4 – Messgerät-Alias und Zählerwiederverwendung

- Präzisere Zuordnung bereits vorhandener Zeitraum-Energie- und Kostensensoren anhand des technischen Messgeräts, auch wenn der angezeigte Verbraucher anders heißt.
- Mehrdeutige Kandidaten werden nicht blind zugeordnet.
- Eine ausdrücklich neu begonnene Messsitzung übernimmt keine alten Verbraucherzähler.
- Hinweis: Der neue Namens-Fallback ist noch nicht vollständig in einer realen Home-Assistant-Installation validiert.

## 0.2.3 – Verbraucherzuordnung und Messsitzungen

- Physisches Messgerät und zugehörigen Verbraucher getrennt verwalten.
- Bereits vorhandenes Home-Assistant-Gerät auswählen oder einen Verbraucher-Namen und optionalen Typ angeben.
- Wechsel des Verbrauchers ohne Übernahme von Werten aus einer früheren Messsitzung.
- Lokalen HeimEnergie-Katalog für die Dashboard-Anbindung bereitstellen.

## 0.2.2 – Sensorzuordnung und Periodenzähler

- Zuordnung vorhandener Energie-/Kostensensoren und Bereitstellung fehlender Zeitraumsensoren erweitert.
- Schutz vor mehrdeutiger Zuordnung und vor der Vermischung von Kosten mit nicht zugehörigen Energiezählern.

## 0.2.1 – Einrichtungsdialog

- Korrektur für die Auswahlfelder im Home-Assistant-Konfigurationsdialog.

## 0.2.0-alpha – Erste Integration

- Grundfunktionen für Leistungs-, Energie- und Kostensensoren sowie erfasste Gesamtsummen.
- Arbeitspreis und monatlicher Grundpreis; Grundpreis wird nur einmal je Tarif berücksichtigt.
- Kein Netzbezugszähler und keine manuell angelegten YAML-Helfer erforderlich.
