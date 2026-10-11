# Home Assistant

Integrace potřebuje běžící IDS JMK API dostupné ze sítě Home Assistantu. GTFS se stahuje a zpracovává pouze na serveru.

## Instalace vlastní integrace

Před prvním veřejným vydáním zkopíruj složku `custom_components/ids_jmk` z tohoto projektu do `config/custom_components/ids_jmk` v Home Assistantu a restartuj HA. V release bude připraven také ZIP; obsah `ids_jmk` patří do `custom_components`.

Pro HACS je repozitář připraven jako vlastní repozitář typu **Integration**. Možnost skutečné instalace z GitHubu závisí na zveřejnění těchto souborů; nejde zatím o integraci přijatou do výchozího katalogu HACS.

V **Nastavení → Zařízení a služby → Přidat integraci → IDS JMK**:

1. Zadej adresu serveru, například `http://192.168.1.10:8080`. Pokud používáš webový kontejner, můžeš zadat jeho adresu a port; `/api` proxy je jeho součástí.
2. Vyhledej zastávku podle názvu.
3. Vyber nalezenou zastávku.
4. Zvol všechna nebo konkrétní stanoviště, linku, směr a počet odjezdů.

Vznikne jeden senzor. Jeho stav je počet minut do nejbližšího nezrušeného odjezdu. Atribut `departures` obsahuje celou tabulku. Při výpadku API se senzor označí jako nedostupný. Další tabuli přidej opakováním průvodce; počet řádků lze měnit v možnostech integrace.

## Dashboard s flex-table-card

Integrace vytváří senzor; kartu do uživatelova dashboardu sama nevkládá. Nainstaluj [flex-table-card](https://github.com/custom-cards/flex-table-card), přidej ruční kartu a změň pouze ID entity podle skutečně vytvořeného senzoru:

```yaml
type: custom:flex-table-card
title: Odjezdy
entities:
  include: sensor.ids_jmk_nadrazi
columns:
  - name: Linka
    data: departures
    modify: x.line
  - name: Směr
    data: departures
    modify: String(x.destination).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  - name: Čas
    data: departures
    modify: x.departure_time_display
  - name: Za (min)
    data: departures
    modify: x.cancelled ? 'Zrušeno' : x.minutes_until
```

Čas v tabulce je odhadovaný, pokud existuje, jinak plánovaný. Pro rozlišení lze přidat sloupec `source`, případně `delay_seconds`. Pro noční odjezdy je datum dostupné v `departure_time` a provozní den v `service_date`.

## Bez vlastní integrace

Webové tlačítko **Použít v Home Assistantu** vygeneruje alternativní REST senzor i konfiguraci tabulky podle aktuálně vybrané zastávky a filtrů. Část `rest:` vlož do konfigurace HA; část karty zvlášť do dashboardu. Pokud již konfigurace `rest:` existuje, přidej položku do jejího seznamu, nevytvářej duplicitní klíč. Pro více tabulí změň názvy a `unique_id` senzorů.

Na běžném HTTP nemusí prohlížeč dovolit kopírování do schránky; text se v tom případě označí pro ruční kopírování. Nepoužívej `localhost` jako adresu vzdáleného serveru — v HA by označoval samotný Home Assistant.

Integrace obnovuje data každých 30 sekund. Pole odjezdů a čas aktualizace nejsou určeny k dlouhodobému ukládání do historie; integrace je označuje jako atributy bez záznamu do recorderu.
