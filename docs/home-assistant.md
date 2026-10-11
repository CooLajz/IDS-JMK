# Home Assistant

Integrace potřebuje běžící IDS JMK API dostupné ze sítě Home Assistantu. GTFS se stahuje a zpracovává pouze na serveru.

## Instalace vlastní integrace

Z [vydání projektu](https://github.com/CooLajz/IDS-JMK/releases) stáhněte `ids_jmk.zip`, rozbalte složku `ids_jmk` do `config/custom_components/ids_jmk` v Home Assistantu a restartujte HA. Alternativně zkopírujte `custom_components/ids_jmk` přímo z repozitáře.

Pro HACS je repozitář připraven jako vlastní repozitář typu **Integration**. Nejde o integraci přijatou do výchozího katalogu HACS; repozitář musíte přidat ručně.

V **Nastavení → Zařízení a služby → Přidat integraci → IDS JMK**:

1. Zadejte adresu serveru, například `http://192.168.1.10:8080`. Pokud používáte webový kontejner, můžete zadat jeho adresu a port; `/api` proxy je jeho součástí.
2. Vyhledejte zastávku podle názvu.
3. Vyberte nalezenou zastávku.
4. Zvolte všechna nebo konkrétní stanoviště, linku, směr a počet odjezdů.

Vznikne jeden senzor. Jeho stav je počet minut do nejbližšího nezrušeného odjezdu. Atribut `departures` obsahuje celou tabulku. Při výpadku API se senzor označí jako nedostupný. Další tabuli přidejte opakováním průvodce; počet řádků lze měnit v možnostech integrace.

## Vlastní karta IDS JMK

Od verze 0.1.2 integrace obsahuje vlastní kartu **IDS JMK — Odjezdová tabule**. Není potřeba instalovat `flex-table-card`, kopírovat JavaScript ani přidávat zdroj dashboardu. Karta se načte automaticky z Home Assistantu; sama neposílá další požadavky na IDS JMK API.

1. Po aktualizaci souborů restartujte Home Assistant a obnovte stránku v prohlížeči nebo aplikaci.
2. V dashboardu zvolte **Upravit → Přidat kartu** a vyhledejte **IDS JMK**.
3. Vyberte senzor odjezdové tabule. Volitelně nastavte nadpis, vzhled, počet řádků, hranici zeleného zvýraznění a zobrazení stanoviště či piktogramů. Kartu uložte.

Zastávku, linku a směr určuje vybraný senzor. Karta zobrazí nejvýše tolik řádků, kolik senzor poskytuje; více odjezdů povolte v možnostech integrace. Další kartu můžete napojit na jiný senzor.

Pro ruční YAML konfiguraci stačí:

```yaml
type: custom:ids-jmk-departures-card
entity: sensor.ids_jmk_nebovidy_kostel
limit: 6
layout: modern # modern nebo compact
highlight_minutes: 5 # 0 vypne zelené zvýraznění
# title: Moje odjezdy
# show_platform: true
# show_accessibility: true
# show_transport_icon: true
```

ID entity nahraďte skutečným ID vytvořeného senzoru. Karta podporuje světlý i tmavý motiv HA. Sloupec **Odjezd** uvádí jízdní řád, sloupec **Zpož. min** obsahuje nenulové odhadované zpoždění; sloupec **Za** již zahrnuje dostupný odhad, nic se k němu nepřičítá. Odpočet se přepočítává každých 15 sekund, data senzoru každých 30 sekund. Piktogramy vozíčku a kola vycházejí z jízdního řádu, nepotvrzují aktuálně nasazené vozidlo. Při výpadku API nebo zastaralých datech karta zobrazí upozornění.

Vzhled **Moderní** používá větší odpočet a vzdušnější řádky. **Kompaktní** má menší záhlaví a každý spoj je vždy na jednom řádku stejné výšky, včetně zpoždění a stanoviště. Zpoždění má v obou variantách vlastní sloupec; pokud není uvedeno nebo se zaokrouhluje na nulu, buňka zůstane prázdná. Údaje i ikony jsou svisle vycentrované. Číslo v drobném štítku vedle cíle označuje stanoviště. Ikonky vybavení se zobrazují vedle cíle a lze je vypnout přepínačem v editoru (`show_accessibility: false`). Moderní vzhled dlouhé cíle zalamuje; kompaktní je zkracuje výpustkou a plný název ponechá v popisku.

Zelený odpočet označuje blížící se odjezd v nastaveném počtu minut (výchozí **5**, rozsah **0–60**, **0** zvýraznění vypne). Hranice pracuje s odjezdem včetně dostupného odhadu zpoždění. Zrušené nebo již odjeté spoje a zastaralá data se nezvýrazňují.

Karta se sama nevkládá do existujících dashboardů. Pokud se po první instalaci neobjeví v nabídce, obnovte celou stránku HA; zkontrolujte také, že byla zkopírována podsložka `www`.

## Alternativní dashboard s flex-table-card

Integrace vytváří senzor; kartu do uživatelova dashboardu sama nevkládá. Nainstalujte [flex-table-card](https://github.com/custom-cards/flex-table-card), přidejte ruční kartu a změňte pouze ID entity podle skutečně vytvořeného senzoru:

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

Webové tlačítko **Použít v Home Assistantu** vygeneruje alternativní REST senzor i konfiguraci tabulky podle aktuálně vybrané zastávky a filtrů. Část `rest:` vložte do konfigurace HA; část karty zvlášť do dashboardu. Pokud již konfigurace `rest:` existuje, přidejte položku do jejího seznamu, nevytvářejte duplicitní klíč. Pro více tabulí změňte názvy a `unique_id` senzorů.

Na běžném HTTP nemusí prohlížeč dovolit kopírování do schránky; text se v tom případě označí pro ruční kopírování. Nepoužívejte `localhost` jako adresu vzdáleného serveru — v HA by označoval samotný Home Assistant.

Integrace obnovuje data každých 30 sekund. Pole odjezdů a čas aktualizace nejsou určeny k dlouhodobému ukládání do historie; integrace je označuje jako atributy bez záznamu do recorderu.

Ikona vedle čísla linky vychází z `transport_mode` v API. V editoru ji lze skrýt volbou **Zobrazit ikonu druhu dopravy** (`show_transport_icon: false`). Karta používá hotové [Material Design Icons od Pictogrammers](https://pictogrammers.com/library/mdi/) dostupné přímo v HA: šalina `tram`, autobus `bus`, vlak `train`, trolejbus `bus-electric`, kolo `bicycle` a vozíček `wheelchair-accessibility`. Elektrický autobus slouží jako symbol trolejbusu s odpovídajícím textovým popiskem. Chybějící nebo neznámý druh dopravy se zobrazí bez ikony; neodhaduje se z čísla linky. Ikony vybavení lze skrýt nezávisle.
