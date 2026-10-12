# Home Assistant

Integrace potřebuje běžící IDS JMK API dostupné ze sítě Home Assistantu. GTFS se stahuje a zpracovává pouze v parseru. Ten může běžet na samostatném serveru nebo jako [aplikace přímo v HA OS](../home-assistant/ids_jmk/DOCS.md). Aplikace je dostupná od verze 0.1.4 a je zatím označena jako experimentální.

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
# show_header: true
# show_footer: true
# show_platform: true
# show_accessibility: true
# show_transport_icon: true
# show_line_number: true
# show_departure_day: true
```

ID entity nahraďte skutečným ID vytvořeného senzoru. Karta podporuje světlý i tmavý motiv HA. Sloupec **Odjezd** uvádí jízdní řád, sloupec **Zpož. min** obsahuje nenulové odhadované zpoždění; sloupec **Za** již zahrnuje dostupný odhad, nic se k němu nepřičítá. Odpočet se přepočítává každých 15 sekund, data senzoru každých 30 sekund. Piktogramy vozíčku a kola vycházejí z jízdního řádu, nepotvrzují aktuálně nasazené vozidlo. Při výpadku API karta zobrazí hlášení; zastaralá data označí ve viditelném zápatí.

Vzhled **Moderní** používá větší odpočet a vzdušnější řádky. **Kompaktní** má menší záhlaví a každý spoj je vždy na jednom řádku stejné výšky, včetně zpoždění a stanoviště. Sloupec zpoždění se v obou variantách zobrazí pouze tehdy, pokud alespoň jeden z viditelných nezrušených spojů obsahuje nenulové zpoždění po zaokrouhlení na minuty. Jinak se automaticky skryje včetně záhlaví a uvolní prostor pro směr. Při vypnutém realtime zůstává skrytý. Pokud je sloupec zobrazený, řádky bez zpoždění mají prázdnou buňku, aby zůstaly zarovnané. Údaje i ikony jsou svisle vycentrované. Číslo v drobném štítku vedle cíle označuje stanoviště. Ikonky vybavení se zobrazují vedle cíle a lze je vypnout přepínačem v editoru (`show_accessibility: false`). Moderní vzhled dlouhé cíle zalamuje; kompaktní je zkracuje výpustkou a plný název ponechá v popisku.

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

Volba **Zobrazit den odjezdu** (`show_departure_day`, výchozí `true`) přidává před čas samostatný sloupec zarovnaný doprava. Dnešní odjezdy mají prázdnou buňku, následující kalendářní den označení „zítra“ a ostatní dny datum, například „13.10.“. Plné datum včetně roku je v popisku. Sloupec se zobrazí pouze tehdy, pokud některý z viditelných odjezdů není dnes. Po vypnutí se prostor vrátí sloupci směru. Den patří k času podle jízdního řádu ve vedlejším sloupci a počítá se v pásmu Europe/Prague, včetně přechodu přes půlnoc a změn letního času. Zpoždění ovlivňuje odpočet, nikoli toto datum jízdního řádu.

## Karta upozornění z více tabulí

Od verze 0.1.3 je součástí integrace také samostatná karta **IDS JMK — Upozornění**. V editoru dashboardu vyberte jeden nebo více senzorů odjezdových tabulí. Karta čte jejich atribut `alerts`, neodesílá další dotazy na server a stejné upozornění zobrazí pouze jednou. Upozornění na různých linkách se sloučí včetně čísel odpovídajících linek a názvů zdrojových tabulí. Text lze rozbalit; rozbalení zůstává zachované při aktualizaci.

```yaml
type: custom:ids-jmk-alerts-card
title: Omezení na mých trasách
entities:
  - sensor.ids_jmk_nadrazi
  - sensor.ids_jmk_prace
```

Nahraďte příklady skutečnými ID senzorů. Pole `entities` je dostupné i ve vizuálním editoru, YAML není nutný. Po aktualizaci integrace restartujte Home Assistant a obnovte stránku; JavaScript karty se registruje automaticky stejně jako u odjezdové tabule. Podpora upozornění vyžaduje aktualizované API i integraci a na serveru `REALTIME_ENABLED=true`.

Nedostupný senzor, zastaralý feed, starší API bez podpory upozornění a záměrně vypnutý realtime mají odlišný popisek. Upozornění z neaktuálních zdrojů se nezobrazují jako platná; zbývající aktuální senzory se dále používají. Prázdný seznam při nedostupném zdroji nepotvrzuje provoz bez omezení. U linkových upozornění ověřte dopad na zastávku v původním textu.

Při výchozím `REALTIME_ENABLED=false` funguje běžná odjezdová karta pouze s jízdním řádem a v zápatí uvádí „Jízdní řád · realtime vypnutý“. Nevyžaduje polohy ani zpoždění. Pro tento režim není potřeba přidávat kartu upozornění.

Volba **Zobrazit číslo linky** (`show_line_number`, výchozí `true`) skrývá číslo nezávisle na piktogramu druhu dopravy. Hodí se například pro zastávku s jedinou linkou. Pokud skryjete číslo i piktogram, celý sloupec zmizí a uvolní prostor pro název směru. Při skrytém čísle a neznámém druhu dopravy všech viditelných spojů se prázdný sloupec rovněž nezobrazuje. Nastavení ovlivňuje pouze vzhled karty, nikoli filtry nebo data senzoru.

Volby **Zobrazit záhlaví** (`show_header`) a **Zobrazit zápatí** (`show_footer`) jsou výchozí zapnuté a lze je vypnout nezávisle. Skrytí záhlaví odstraní ikonu a název tabule; názvy sloupců zůstanou viditelné. Skrytí zápatí odstraní stav dat a čas aktualizace. Vypnutím obou voleb získáte samotnou tabulku v moderním i kompaktním vzhledu. Hlášení o nedostupném senzoru nebo prázdné tabuli zůstávají zobrazená.
