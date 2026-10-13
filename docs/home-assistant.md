# Home Assistant: od instalace k vlastní tabuli

[← Rozcestník](../README.md) · [Provoz serveru](deployment.md) · [Pro vývojáře](development.md)

Tento návod Vás provede zobrazením odjezdů, upozornění a vozidel v dashboardu. Základní nastavení zvládnete přes formuláře, bez programování. YAML příklady jsou pouze volitelná alternativa.

## Obsah

- [Než začnete](#než-začnete)
- [Instalace vlastní integrace](#instalace-vlastní-integrace)
- [Přidání serveru a první tabule](#přidání-serveru-a-první-tabule)
- [Odjezdová karta](#vlastní-karta-ids-jmk)
- [Jak číst odjezdy](#jak-číst-odjezdy)
- [Upozornění a výluky](#karta-upozornění-z-více-tabulí)
- [Mapa vozidel](#mapa-vozidel)
- [Statistiky serveru](#kumulativní-statistiky-zdroje)
- [Alternativní karta](#alternativní-dashboard-s-flex-table-card) a [použití bez integrace](#bez-vlastní-integrace)
- [Časté potíže](#časté-potíže)
- [Aktualizace a zálohování](#aktualizace-a-zálohování)

## Než začnete

Potřebujete **běžící parser/API**, **integraci IDS JMK** a **kartu v dashboardu**. Jde o tři navazující kroky. Parser připravuje data, integrace je přenáší do HA a karta je zobrazuje. Volitelný web pro HA nepotřebujete.

| Vaše instalace | Jak získáte parser |
| --- | --- |
| Home Assistant OS na ARM64 nebo AMD64 | Nainstalujte aplikaci **IDS JMK Parser** podle [návodu krok za krokem](../home-assistant/ids_jmk/DOCS.md). Pro běžný provoz vyberte **IDS JMK Parser**; pro testování je samostatná varianta **IDS JMK Parser (Dev)** s vlastními daty a aktualizacemi z větve `main`. |
| Home Assistant Container nebo vlastní Docker server | Spusťte API podle [návodu pro Docker / Portainer](deployment.md). Obchod s aplikacemi HA OS zde není k dispozici. |
| API už běží jinde v domácí síti | Připravte si jeho adresu včetně portu a pokračujte instalací integrace. |

**Chcete pouze plánované odjezdy?** Výchozí nastavení stačí. **Chcete i polohy, odhady zpoždění a upozornění?** V aplikaci Parser povolte `realtime_enabled` a restartujte ji; v Dockeru nastavte `REALTIME_ENABLED=true` a znovu nasaďte Stack. Čerstvá data nemusejí být dostupná pro každý spoj.

První import může chvíli trvat. Vyčkejte na jeho dokončení v protokolu parseru. Pro integraci na stejném HA OS použijte adresu z řádku „Adresa API pro integraci na tomto HA“. U samostatného serveru použijte jeho adresu dostupnou z HA. `localhost` označuje samotný Home Assistant, nikoli jiný server.

## Instalace vlastní integrace

### Přes HACS

1. V HACS otevřete nabídku **⋮ → Vlastní repozitáře**.
2. Vložte `https://github.com/CooLajz/IDS-JMK` a vyberte typ **Integration** (Integrace).
3. Vyhledejte **IDS JMK**, stáhněte integraci a restartujte Home Assistant.
4. Pokračujte [přidáním serveru a tabule](#přidání-serveru-a-první-tabule).

Repozitář se do HACS přidává zvlášť, i když jste jej již přidali do obchodu s aplikacemi kvůli parseru. Názvy položek se mohou podle verze a překladu HA/HACS lišit.

### Ruční instalace

Z [vydání projektu](https://github.com/CooLajz/IDS-JMK/releases) stáhněte `ids_jmk.zip`, rozbalte složku `ids_jmk` do `config/custom_components/ids_jmk` v Home Assistantu a restartujte HA. Alternativně zkopírujte `custom_components/ids_jmk` přímo z repozitáře.

Pro HACS je repozitář připraven jako vlastní repozitář typu **Integration**. Nejde o integraci přijatou do výchozího katalogu HACS; repozitář musíte přidat ručně.

### Ikona integrace a aplikace

Integrace obsahuje vlastní ikonu a logo ve složce `custom_components/ids_jmk/brand/`, včetně variant pro displeje s vyšším rozlišením. [Místní obrázky integrací podporuje Home Assistant od verze 2026.3](https://developers.home-assistant.io/docs/core/integration/brand_images/). Při ruční instalaci zkopírujte i tuto složku; ZIP vydání ji zahrnuje automaticky. Po aktualizaci restartujte Home Assistant a obnovte stránku nebo mobilní aplikaci. Starší podporované verze HA mohou integraci používat, ale vlastní ikonu nezobrazí.

Aplikace **IDS JMK Parser** používá samostatné soubory `home-assistant/ids_jmk/icon.png` a `logo.png` vedle `config.json`. Po zveřejnění změny aktualizujte seznam repozitářů v obchodě s aplikacemi HA.

Samotný seznam HACS může nadále zobrazovat zástupnou ikonu kvůli [známému problému HACS s místními obrázky integrací](https://github.com/hacs/integration/issues/5402). To neznamená chybu instalace; logo je rovněž součástí README v detailu repozitáře. Zobrazení v HACS závisí na opravě jeho rozhraní.

## Přidání serveru a první tabule

V **Nastavení → Zařízení a služby → Přidat integraci → IDS JMK**:

1. Zadejte adresu serveru, například `http://192.168.1.10:8080`. Pokud používáte webový kontejner, můžete zadat jeho adresu a port; `/api` proxy je jeho součástí.
2. Vznikne zdroj se statistickými senzory. Pod tímto zdrojem zvolte **Přidat odjezdovou tabuli**.
3. Vyhledejte zastávku podle názvu a vyberte ji.
4. Zvolte všechna nebo konkrétní stanoviště, linku, směr a počet odjezdů. Pokud chcete pouze jízdní řád, vypněte **Používat realtime data (zpoždění a upozornění)**.

Pro každou tabuli vznikne jeden senzor. Jeho stav je počet minut do nejbližšího nezrušeného odjezdu. Atribut `departures` obsahuje celou tabulku. Při výpadku API se senzor označí jako nedostupný. Další tabuli přidejte pod stejným zdrojem, bez opětovného zadávání adresy. Počet řádků a použití realtime lze měnit volbou **Překonfigurovat** u tabule. Další server přidejte jako novou integraci; má vlastní tabule i statistiky. Změnu adresy téhož serveru proveďte volbou **Překonfigurovat** u zdroje.

Volba realtime patří **tabuli v integraci**, nikoli jednotlivé kartě dashboardu. Platí pro její senzor, všechny navázané karty i automatizace. Při vypnutí integrace posílá `realtime=false`: server vrací jen plánované časy, odpočet podle jízdního řádu a žádná realtime upozornění. Tato tabule neudržuje stahování realtime v chodu. Karta se přizpůsobí automaticky.

Výchozí hodnota volby je zapnutá, také u dosavadních tabulí; realtime musí současně povolit parser. Zapnutá tabule průběžným dotazováním udržuje server aktivní i při zavřeném dashboardu. Jiná realtime tabule nebo mapa vozidel může dál vyžadovat stahování. Pokud realtime nepotřebuje žádný klient, parser po pěti minutách usne. Samotné statistické senzory jej neprobouzejí. Pro tento režim aktualizujte API i integraci; starší API parametr nemusí respektovat.

Tabule lze jednotlivě odebrat z podřízených konfigurací zdroje.

## Vlastní karta IDS JMK

Od verze 0.1.2 integrace obsahuje vlastní kartu **IDS JMK — Odjezdová tabule**. Není potřeba instalovat `flex-table-card`, kopírovat JavaScript ani přidávat zdroj dashboardu. Karta se načte automaticky z Home Assistantu; sama neposílá další požadavky na IDS JMK API.

1. Po aktualizaci souborů restartujte Home Assistant a obnovte stránku v prohlížeči nebo aplikaci.
2. V dashboardu zvolte **Upravit → Přidat kartu** a vyhledejte **IDS JMK**.
3. Vyberte senzor odjezdové tabule. Volitelně nastavte nadpis, vzhled, počet řádků, hranici zeleného zvýraznění a zobrazení stanoviště či piktogramů. Kartu uložte.

Zastávku, linku a směr určuje vybraný senzor. Karta zobrazí nejvýše tolik řádků, kolik senzor poskytuje; více odjezdů povolte v nastavení příslušné tabule. Další kartu můžete napojit na jiný senzor.

![Odjezdové karty v moderním a kompaktním vzhledu, upozornění a mapa](screenshots/ha-dashboard.png)

*Skutečné karty vykreslené mimo HA s ukázkovými daty; okolní stránka není rozhraním HA. [Původ snímků](screenshots/README.md).*

### Jak číst odjezdy

Na obrázku je čas **14:00**. Linka **8** má plánovaný odjezd **14:02**, odhad zpoždění **+2 min** a odpočet **4 min**. Očekávaný čas tedy vychází na **14:04**; zpoždění už je v odpočtu zahrnuté.

| Prvek karty | Co znamená |
| --- | --- |
| Ikona a číslo linky | Druh dopravy a linka z jízdního řádu |
| Směr | Cíl konkrétního spoje |
| Malý štítek vedle směru | Stanoviště, pokud je uvedeno |
| Odjezd | Plánovaný čas podle jízdního řádu |
| Zpož. min | Dostupný nenulový odhad; prázdná hodnota nepotvrzuje jízdu načas |
| Za (min) | Čas do odjezdu včetně dostupného odhadu |
| Zelený odpočet | Blízký odjezd podle nastavené hranice; není potvrzením příjezdu vozidla |
| Vozíček / kolo | Plánované vybavení, nikoli záruka výbavy nebo volného místa |
| Zápatí | Stav a čas aktualizace dat; doporučujeme ponechat viditelné |

<details>
<summary>Ukázka na mobilní šířce v tmavém motivu</summary>

<img src="screenshots/ha-mobile-dark.png" alt="Skutečné HA karty na šířce 430 pixelů v tmavém ukázkovém motivu" width="360">

</details>

### Volitelná YAML konfigurace

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

Text výluk z parseru se zobrazuje s odstavci, tučným písmem, kurzívou a seznamy. HTML značky ze zdroje se nezobrazují jako text. Senzor nadále obsahuje čisté textové varianty `title` a `description`; karta využívá navíc formátování připravené serverem. Po aktualizaci parseru aktualizujte také integraci s kartou.


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

## Mapa vozidel

1. V dashboardu zvolte **Upravit → Přidat kartu → IDS JMK — Mapa vehyklů**.
2. Vyberte připojení IDS JMK, které jste již přidali do integrací.
3. Přidejte požadované linky a jeden nebo oba směry. Pro polohy zapněte realtime na parseru.
4. Volitelně povolte trvalé zobrazení zastávek a kartu uložte.
5. Klikněte na značku vozidla pro detail spoje. Přepínačem **Přehled** zapnete automatické přizpůsobení mapy.

![Detail vozidla s orientační spojnicí a seznamem zastávek](screenshots/ha-map-detail.png)

*Skutečná mapová karta v samostatném náhledu. Polohy i seznam zastávek jsou syntetické. Přerušovaná čára spojuje zastávky, nekopíruje skutečnou trasu po kolejích či silnici. Mapový podklad © OpenStreetMap.*


Karta **IDS JMK — Mapa vehyklů** (`custom:ids-jmk-map-card`) zobrazuje aktuální
polohy vybraných linek bez vytváření entit pro vozidla. V editoru vyberte existující
připojení integrace jako zdroj dat, přidejte linky a u každé zvolte jeden nebo oba
směry. Filtry mapy jsou nezávislé na zastávce a odjezdech zdrojové tabule.
Směry vycházejí z GTFS `direction_id`; názvy nabízejí nejčastější cíle a zahrnují
i zkrácené spoje stejného směru. Výběr používá `route_id`, nikoli jen číslo linky.

Interval obnovování nastavíte v editoru karty (5–3600 sekund, výchozí 30). Skrytá záložka prohlížeče nebo karta mimo viditelnou oblast obnovování pozastaví; po návratu se data obnoví. Již zahájený požadavek může doběhnout. Detail trasy žádá jen statické zastávky a neaktivuje další realtime požadavek.
Server nadále dodržuje vlastní interval stahování realtime. Zobrazuje pouze čerstvé použitelné polohy. Při chybě připojení,
zastarání dat nebo vypnutém realtime značky zmizí a karta zobrazí vysvětlení.
Kliknutím na vozidlo zobrazíte detail a zastávky celého spoje. Přerušovaná čára
je pouze orientační spojnice zastávek: aktuální zdroj GTFS neobsahuje `shapes.txt`.
Kliknutím do volného místa mapy detail zavřete a spojnice zmizí. U každé linky
můžete zapnout **Trvale zobrazovat zastávky této linky**: zobrazí se zastávky všech
variant vybraného směru i bez aktuálně jedoucího vozidla. Mimo detail se čáry
tras nezobrazují. Zastávky se načítají při otevření karty nebo změně konfigurace;
obnovování poloh je znovu nestahuje.

Přepínač **Přehled** zapíná automatické přizpůsobování mapy všem zobrazeným
vozidlům při každé obnově. Při otevření detailu zůstanou všechna vozidla ve výřezu.
Po vypnutí Přehledu můžete mapu posouvat a přibližovat ručně. Volba Přehledu
se pamatuje v daném prohlížeči i po obnovení stránky. Pokud máte zapnuté trvalé
zastávky, Přehled zahrnuje také je. Při přiblížení se zobrazí názvy zastávek.
Chyba načítání zastávek se zobrazuje samostatně pod časem aktualizace. Funkce
vyžaduje aktualizované sestavení API 0.1.5 s endpointem `/api/v1/map/stops`.
Pokud používáte dřívější sestavení stejné verze, stáhněte obraz znovu a integraci
přeinstalujte z aktuálního vydání.

Je nutné aktualizovat **API i integraci**, restartovat HA a obnovit dashboard.
Karta se registruje automaticky stejně jako tabule a upozornění. Připojení
integrace musí být načtené; není nutné přidávat další senzor. Komunikace s API
probíhá přes přihlášené WebSocket připojení HA, nikoli přímo z prohlížeče.
Mapový podklad OpenStreetMap prohlížeč načítá z internetu. Leaflet 1.9.4 je
přibalen lokálně včetně licence v `www/map-vendor`.

Konfiguraci vytváří vizuální editor; odpovídající YAML má tuto strukturu:

```yaml
type: custom:ids-jmk-map-card
title: Mapa vehyklů
entry_id: ID_PRIPOJENI_Z_EDITORU
refresh_interval: 30
selections:
  - route_id: ID_LINKY_Z_EDITORU
    direction: "*" # Oba směry; konkrétní směr má hodnotu z GTFS.
    show_stops: true # Trvale zobrazovat zastávky této linky.
```

## Kumulativní statistiky zdroje

Každý zdroj má jedno zařízení API serveru a **18 diagnostických senzorů**, obnovovaných jednou za 60 sekund:

- Celkový počet stažení a objem stažených dat (GTFS + realtime).
- Zvlášť pro GTFS a realtime: požadavky, úplná stažení, odpovědi beze změny (304), chyby a přijaté bajty.
- Pro API: požadavky, chyby a odpovědi 2xx, 3xx, 4xx a 5xx.

Čítače odpovídají kumulativním hodnotám webové statistiky za celou instanci, tedy včetně ostatních klientů. Nevynulují se o půlnoci ani při restartu HA nebo serveru. Uchovávají se na serveru v `statistics.sqlite3`; po odstranění jeho dat začnou znovu. Senzory mají `state_class: total_increasing`, bajty navíc `device_class: data_size` a jednotku `B`. Při nedostupnosti API jsou senzory nedostupné, neposílají falešnou nulu. Nefunkční statistiky neblokují ostatní tabule.

Denní či měsíční přehled vytvořte pomocníkem **Utility Meter** nad požadovaným senzorem; nepovolujte volbu, že vstupní hodnoty jsou přírůstky (delta). Například:

```yaml
utility_meter:
  ids_jmk_data_den:
    source: sensor.ids_jmk_celkem_stazena_data # Nahraďte skutečným ID senzoru.
    cycle: daily
```

Statistiky vyžadují aktualizované API s endpointem `/api/v1/statistics/cumulative` i integraci a následný restart HA. Starší server může nadále poskytovat odjezdy, statistické senzory však zůstanou nedostupné. Dotazy integrace na statistiky se započítávají do požadavků API. Přijaté bajty označují těla odpovědí zdrojů před HTTP dekompresí, včetně částečných neúspěšných přenosů; nejde o velikost odpovědí API ani celkový síťový provoz.

## Časté potíže

| Co vidíte | Co zkontrolovat |
| --- | --- |
| Integraci nelze připojit | Ověřte spuštění parseru, dokončení prvního importu a adresu dostupnou ze sítě HA. Nepoužívejte adresu `localhost` pro vzdálený server. |
| Parser funguje, ale karta není v nabídce | Nainstalujte také integraci, restartujte HA a obnovte celou stránku. Při ruční instalaci musí být přítomna složka `www`. |
| Karta nemá žádné odjezdy | Zkontrolujte zastávku, stanoviště, linku a směr v nastavení tabule; pro daný výběr nemusí v časovém rozsahu nic jet. |
| Karta ukazuje málo řádků | Zvyšte počet odjezdů v konfiguraci tabule i limit karty. Karta nevytvoří další odjezdy nad rámec senzoru. |
| Nevidíte zpoždění | Realtime je výchozí vypnutý. I po zapnutí nemusí mít spoj dostupný odhad. Sloupec se skrývá, pokud žádný viditelný spoj nemá nenulové zpoždění. |
| Mapa nemá vozidla | Ověřte realtime, zvolené linky a směry, čerstvost dat a aktualizaci API i integrace. V daném směru nemusí právě jet žádné vozidlo s dostupnou polohou. |
| Mapa nemá podklad | Mapové dlaždice se načítají z internetu přímo v prohlížeči. Ověřte jeho připojení. |
| „Data nejsou aktuální“ nebo nedostupný senzor | Prověřte dostupnost API a protokol parseru. Starý údaj nepovažujte za aktuální odjezd. |
| Upozornění jsou prázdná | Rozlišujte platný prázdný seznam od vypnutého realtime, nedostupného zdroje nebo starého feedu; karta stav vysvětluje. |
| Odjezdy fungují, statistiky či zastávky mapy ne | Aktualizujte API i integraci. Nové funkce klienta potřebují odpovídající endpointy serveru. |

## Aktualizace a zálohování

Parser a integrace jsou samostatné součásti. Aktualizujte obě, restartujte integraci prostřednictvím restartu HA a obnovte stránku dashboardu. V HACS aktualizujete integraci; v obchodě s aplikacemi HA aktualizujete parser. U Dockeru postupujte podle [provozního návodu](deployment.md).

Před větší aktualizací vytvořte zálohu. V HA OS zahrňte i aplikaci Parser. U Dockeru zachovejte celý datový svazek `ids-data`, včetně identity serveru a statistik. Podrobnosti: [zálohy aplikace HA OS](../home-assistant/ids_jmk/DOCS.md#data-místo-a-zálohy).

### Obnovování pouze při zobrazení

Každé zařízení odjezdové tabule obsahuje konfigurační přepínač **Průběžné obnovování**:

- **Vypnuto (výchozí):** odjezdy se obnovují pouze při zobrazení naší karty odjezdů nebo upozornění. Karta musí být ve viditelné části stránky a prohlížeč musí mít stránku v popředí.
- **Zapnuto:** tabule se obnovuje průběžně každých 30 sekund. Tento režim zapněte pro automatizace, jiné karty nebo další spotřebitele senzoru.

Nastavení se ukládá pro každou tabuli a zachová se po restartu. U tabulí bez uložené volby se používá režim pouze při zobrazení, tedy i po aktualizaci starší integrace. Při použití automatizací proto zapněte průběžné obnovování.

Naše karty obnovují odběr každých 30 sekund. Více karet a prohlížečů sdílí jedno načítání tabule. Skrytí karty odběr uvolní; při náhlém zavření či ztrátě spojení odběr vyprší nejpozději za 90 sekund od posledního potvrzeného požadavku. Karta upozornění aktivuje vybrané tabule i bez karty odjezdů. Ostatní karty tento mechanismus automaticky nepodporují.

Při uspání senzor uchovává poslední hodnotu, která se dále neaktualizuje. Atributy `refresh_mode`, `refresh_active` a `refresh_pending` rozlišují nastavený režim, aktivní odběr a probouzení. Před prvním načtením je senzor nedostupný; naše karta přesto umí zahájit odběr. Ruční akce `homeassistant.update_entity` provede jednorázové načtení i v úsporném režimu. Přepínač průběžného obnovování lze ovládat také automatizací.

Volba **Používat realtime data** je nezávislá na obnovování: při vypnutí se načítá pouze jízdní řád. API server přestane stahovat realtime z KORDIS až po vypršení své lhůty neaktivity a pouze tehdy, pokud realtime nepotřebuje jiný klient nebo mapa. Diagnostické senzory se obnovují zvlášť a samy stahování z KORDIS neaktivují.
