# API v1

Časy jsou ISO 8601 s offsetem pásma Europe/Prague. Identifikátory jsou řetězce; nikdy je nepřevádějte na čísla. Chyby mají HTTP stav a JSON `detail`. Při prvním importu vrací datové endpointy 503, ne prázdný jízdní řád.

| GET | Výsledek |
| --- | --- |
| `/api/v1/status` | Identita, verze, připravenost, stav importu, platnost a stáří dat |
| `/api/v1/stops?query=nadrazi&limit=20` | Zastávky; hledání bez diakritiky, stanoviště seskupená pod rodičem |
| `/api/v1/stops/{id}` | Detail včetně stanovišť, linek a cílových směrů z jízdního řádu |
| `/api/v1/stops/{id}/departures?limit=10&horizon=1440` | Odjezdy, rodičovská zastávka zahrnuje svá stanoviště |
| `/api/v1/trips/{id}?service_date=2026-10-11` | Zastávky konkrétního spoje a dostupná poloha |
| `/api/v1/vehicles?trip_id=123` | Vozidla, souřadnice a stáří zpráv |
| `/health/live` | Proces běží |
| `/health/ready` | Byl dokončen alespoň jeden platný import |

Parametry odjezdů: `limit` 1–100, `horizon` 1–2880 minut, `line` (například `501`), `direction` (přesný název cíle z detailu zastávky), `previous_limit` 0–10 (výchozí 0). Pro konkrétní stanoviště použijte jeho ID v URL. Směry v detailu jsou všechny varianty v platném souboru GTFS, nikoli jen aktuálně jedoucí varianty.

Základ odpovědi odjezdů je `stop`, `generated_at`, `timezone`, `realtime_enabled` a pole `departures` a `previous_departures`. Schéma každého řádku je popsané v OpenAPI. Pro HA jsou připravená také pole `departure_time_display` a `minutes_until`. Minuty platí k `generated_at`, nejsou běžícími hodinami; klient musí odpověď obnovovat.

`departure_time` je odhad, pokud je dostupný, jinak plánovaný čas. `scheduled_departure` zůstává zachován. `service_date` určuje provozní den: odjezd v 01:05 může patřit předchozímu dni jako 25:05. Seznam se řadí podle výsledného okamžiku. Konečné zastávky bez dalšího pokračování spoje se nevydávají za odjezdy.

## Původ časů

- `schedule`: pouze jízdní řád; při zapnutém realtime jsou `delay_seconds` a `estimated_departure` `null`, při vypnutém realtime se tato pole vynechávají.
- `trip_update`: přímá předpověď pro dané zastavení ze zdroje. Zpracuje se explicitní čas nebo zpoždění odjezdu, zrušení spoje a vynechaná zastávka. `NO_DATA` potlačí odhad.
- `vehicle_estimate`: vlastní přibližný výpočet. U stojícího vozidla porovná čas zprávy s plánovaným odjezdem. Při jízdě mezi zastávkami odhadne postup z poměru vzdáleností k předchozí a následující zastávce a porovná jej s jízdním řádem. Nepoužívá skutečnou geometrii silnice ani predikci dopravce.

Odhad z vozidla kontroluje stáří feedu i zprávy, provozní den/časové okolí spoje, pořadí zastávek a příliš vzdálené souřadnice. Nejednoznačné opakované zastávky bez pořadí vynechá. Vlastní odhady neohlašují předčasný odjezd a jsou omezené na dvě hodiny zpoždění. Při nedostatku podkladů se vrátí jízdní řád. Zpoždění nad dvě hodiny nemusí být v tabuli zachyceno.

Výpočet je orientační. Nejde o naměřený okamžik odjezdu. `cancelled: null` znamená neznámý stav, nikoli potvrzení provozu. `realtime_stale: false` potvrzuje pouze čerstvost feedu, nikoli existenci předpovědi pro každý spoj.

Veřejné API neposkytuje stažené archivy ani administrační mutace. Import je určen pro aktuální JMK data v Europe/Prague; intervalové spoje `frequencies.txt` a jiné časové pásmo v této verzi explicitně odmítne. Další části GTFS jako tarify, přestupové vyhledávání nebo geometrie tras nejsou implementovány.

Polohy vzdálené více než 25 km od všech zastávek přiřazeného spoje se vracejí s `position: null` a `position_valid: false`. Jde o hrubou kontrolu zjevně chybných souřadnic, nikoli potvrzení přesnosti GPS. `position_valid: null` znamená, že polohu nebylo možné porovnat se zastávkami spoje. Mapový klient používá jen čerstvé nenulové polohy.

## Minulý odjezd a mapa

S `previous_limit=1` vrátí `previous_departures` poslední odjezd z uplynulých 24 hodin, i když v blízké budoucnosti žádný nejede. Platí stejné filtry zastávky, stanoviště, linky, směru i kalendáře. Při větším limitu jsou minulé odjezdy řazené od nejnovějšího. Budoucí `departures` a jeho `limit` se nemění, takže stávající senzory HA stále ukazují příští spoj. `minutes_until` je u minulých odjezdů záporné (první necelou minutu 0).

Minulý čas je aktuálně dostupný odhad, jinak jízdní řád, nikoli uložený skutečný odjezd. API nearchivuje historické polohy ani zpoždění. Web tuto nejistotu uvádí přímo u řádku a umožňuje otevřít detail i po odjezdu.

`has_vehicle_position` u každého řádku znamená, že v okamžiku odpovědi má daný provozní den spoje čerstvou použitelnou polohu. Používá stejné časové a souřadnicové kontroly jako detail spoje. Je nezávislé na `vehicle_id` odhadu: mapa může být dostupná i bez vypočteného zpoždění, například když vozidlo zastávku již minulo. Při pozdějším otevření detailu může poloha mezitím přestat být dostupná.

Web používá AJAX (`fetch`) po 30 sekundách i po návratu na záložku nebo obnovení připojení. Minuty přepočítává průběžně mezi odpověďmi. Otevřená mapa obnovuje vozidla bez změny uživatelova přiblížení a posunutí.

## Vybavení plánovaného spoje

`wheelchair_accessible` a `bikes_allowed` jsou ve výpisu odjezdů i detailu spoje. Čtou se ze statického `trips.txt`: hodnota `1` se převádí na `true`, `2` na `false` a `0` / prázdné na `null`. Význam odpovídá [specifikaci GTFS](https://gtfs.org/documentation/schedule/reference/#tripstxt). Neznámá informace není zákaz. Web ukazuje piktogramy pouze pro `true`; detail používá stejné ikony s popiskem. Záporné a neznámé hodnoty zůstávají dostupné v API.

Jde o plánované vlastnosti vozidla/spoje, nikoli potvrzení výbavy právě nasazeného vozu. Přístupnost vozidla neznamená přístupnost zastávky či nástupiště a povolení kol negarantuje volné místo. Klimatizaci současné zpracovávané zdroje neuvádějí. Starší databáze zůstane při aktualizaci čitelná a při dalším importu se doplní nově načítaná data, i když se archiv nezměnil.

## Generování odkazu na webu

Tlačítko **API URL / JSON** pod tabulí vytvoří absolutní URL se stejnou zastávkou či stanovištěm, linkou, směrem, limitem a časovým rozsahem, jaké používá web. URL lze zkopírovat nebo otevřít v nové záložce. Každé načtení poskytne aktuální odpověď.

Volba **Zobrazit poslední minulý odjezd** je na webu výchozí **vypnutá**. Po zapnutí přidá do API URL `previous_limit=1`; minulý spoj je pak v `previous_departures`, budoucí v `departures`. Volba se přenáší i ve sdílené URL webu jako `previous=1`. Bez tohoto parametru se stránka otevře jen s budoucími odjezdy.

## Zastávka hlášená vozidlem

Vozidla obsahují `current_stop` s `stop_id`, `stop_sequence` a `status`: `in_transit_to` znamená následující zastávku, `incoming_at` příjezd a `stopped_at` stání v uvedené zastávce. Nejde o konečnou zastávku spoje. Při stání neoznačujeme tuto zastávku za následující.

Pořadí se ověřuje proti jízdnímu řádu. Pokud ho zdroj neposkytuje (aktuální feed KORDIS uvádí pouze ID zastávky), použije se ID jen při jednoznačném výskytu v trase. Při nejednoznačnosti, rozporu, zastaralé zprávě nebo chybějící použitelné poloze je `current_stop: null`. Web zvýrazňuje odpovídající zastávku v seznamu i na mapě a zvýraznění obnovuje s polohou vozidla.

Seznam zastávek v detailu má vlastní posouvání. Při otevření a změně zastávky hlášené vozidlem se zvýrazněný řádek posune do středu seznamu. Obnova stejné zastávky zachová ruční posunutí seznamu; mapa se neposouvá.

Volba **Sledovat vozidlo** je při otevření detailu vypnutá. Po zapnutí se mapa vystředí na vozidlo a při každé aktualizaci následuje jeho čerstvou polohu bez změny přiblížení. Po vypnutí zůstává ruční poloha mapy zachována.

V detailu konkrétního provozního dne může `current_stop.status` mít hodnotu `before_departure`: před plánovaným začátkem jízdy je čerstvá poloha do 100 m od výchozí zastávky a realtime odkazuje na první nebo druhou zastávku. V tom případě se označí výchozí zastávka s `source: schedule_and_position` a popiskem „Před plánovaným odjezdem“. Jde o kombinaci plánu a polohy, nikoli potvrzení, že vozidlo stojí. Ostatní stavy mají `source: realtime`.

V detailu spoje obsahuje `current_stop` také `delay_seconds` a `delay_source` (`vehicle_estimate`, `trip_update` nebo `null`). Odhad se počítá pro tuto konkrétní zastávku stejným postupem jako v odjezdové tabuli. Bez podkladů nebo před plánovaným začátkem jízdy zůstane neznámý. Web uvádí nenulové zpoždění u zvýrazněné zastávky; chybějící odhad ani nulu nezobrazuje.

## Druh dopravy

Každý řádek v `departures` i `previous_departures` a detail `/api/v1/trips/{trip_id}` obsahuje:

```json
{
  "line": "8",
  "route_type": 0,
  "transport_mode": "tram"
}
```

`route_type` zachovává původní číselnou hodnotu z `routes.txt`. `transport_mode` poskytuje stabilní název pro klienty, například HA nebo Živý obraz:

| Základní GTFS kód | `transport_mode` | Druh dopravy |
| --- | --- | --- |
| 0 | `tram` | Šalina / lehká kolejová doprava |
| 1 | `subway` | Metro |
| 2 | `rail` | Vlak |
| 3 | `bus` | Autobus |
| 4 | `ferry` | Lodní doprava |
| 5 | `cable_tram` | Pozemní pouliční dráha tažená lanem |
| 6 | `aerial_lift` | Visutá lanovka |
| 7 | `funicular` | Pozemní lanovka |
| 11 | `trolleybus` | Trolejbus |
| 12 | `monorail` | Jednokolejnicová dráha |

Mapování vychází ze [specifikace GTFS](https://gtfs.org/documentation/schedule/reference/#routestxt). Podporované [rozšířené kódy](https://developers.google.com/transit/gtfs/reference/extended-route-types) se převádějí na stejná označení: železnice 100–117 a 400/403/404, autobusy 200–209 a 700–716, trolejbusy 800, šaliny 900–906, metro 401/402, monorail 405, lodní doprava 1000/1200, visuté lanovky 1300–1302 a 1304–1307, pozemní lanovky 1400. Neznámé kódy vracejí `transport_mode: "unknown"`; původní `route_type` zůstane zachován.

Jde o druh dopravy linky podle jízdního řádu, nikoli ověření aktuálně nasazeného vozidla či jeho modelu. Typ se neodhaduje z čísla linky ani polohy. Integrace HA předává tato pole v atributech odjezdů beze změny. Pro nová pole aktualizujte API server na verzi 0.1.2 nebo novější; samotná aktualizace HA integrace starší server nerozšíří.

## Volitelný realtime

Realtime je výchozí vypnutý. Zapněte jej na serveru pomocí `REALTIME_ENABLED=true` a restartujte aplikaci / znovu nasaďte Stack. `REALTIME_ENABLED=false` vypne samotné stahování, zpracování a poskytování realtime; aktualizace statického GTFS pokračují.

Při vypnutí obsahuje odpověď odjezdů `realtime_enabled: false`, jízdní řád a `source: "schedule"`. Pole `estimated_departure`, `delay_seconds`, `realtime_updated_at`, `cancelled`, `vehicle_id`, `has_vehicle_position` se v jednotlivých odjezdech **vynechávají**, stejně jako `realtime_stale`, `alerts`, `alerts_stale` a `alerts_updated_at` v celé tabuli. Platí to i pro `previous_departures`. `departure_time` odpovídá `scheduled_departure`; chybějící realtime není chyba ani potvrzení nulového zpoždění.

Detail spoje vrací `realtime_enabled: false` a zastávky, bez pole `vehicles`. Endpoint vozidel vrací `{"realtime_enabled": false, "vehicles": []}` a stav serveru `realtime: {"enabled": false}`. Web skryje upozornění a odhady, nabídne tlačítko **Trasa** a mapu zastávek v pořadí spoje. Jednotlivé zastávky zobrazuje jako body bez spojovacích čar. Neoznačuje se aktuální ani následující zastávka vozidla.

## Upozornění a výluky

Při zapnutém realtime obsahuje stejná odpověď odjezdové tabule také:

- `alerts`: odpovídající aktuální upozornění; každé obsahuje `id`, obsahový `key`, `title`, `description`, bezpečný odkaz `url`, `cause`, `effect`, `scope`, `lines`, `matched_lines`, `affected_entities` a `active_period`.
- `alerts_stale`: zda zdroj upozornění není aktuální. V takovém případě je `alerts` prázdné; neznamená to provoz bez omezení.
- `alerts_updated_at`: čas zdrojového feedu, případně `null`.

`lines` uvádí linky z upozornění, `matched_lines` jen linky odpovídající vybrané tabuli a filtrům. `scope` rozlišuje `line`, `stop`, `trip` a `mixed`. Obsahový `key` slouží ke sloučení stejného upozornění z více tabulí. Intervaly `active_period` používají Unix sekundy, začátek je včetně a konec bez uvedeného okamžiku. Pokud interval chybí, upozornění platí po dobu přítomnosti v aktuálním feedu.

Přiřazení respektuje zastávku či stanoviště, linku a cílový směr. Není omezené počtem vypsaných odjezdů ani jejich časovým horizontem; vychází z linek a spojů obsluhujících zastávku v načteném jízdním řádu. Více podmínek jednoho GTFS selektoru platí současně, více selektorů představuje alternativy. Podporovány jsou `route_id`, `route_type`, `direction_id`, `stop_id` a `trip` obsahující pouze `trip_id`. Selektory s dalšími nepodporovanými podmínkami (například `agency_id` či datum konkrétní jízdy uvnitř `trip`) se nepřiřazují, aby nedošlo k rozšíření jejich platnosti.

Feed KORDIS v ověřeném vzorku uvádí u upozornění čísla/názvy linek místo GTFS ID. Nejprve se proto hledá skutečné `route_id`; pouze pokud v jízdním řádu neexistuje, zkusí se shoda s názvem linky bez rozlišení velikosti písmen. Linkové upozornění **nepotvrzuje dopad na konkrétní zastávku nebo směr**. Web jej označuje jako omezení na lince a nad odjezdovou tabulí nabízí rozbalení původního textu s podrobnostmi.

## Veřejné statistiky provozu

`GET /api/v1/statistics/cumulative` vrací malý kumulativní přehled pro Home Assistant a další monitorovací klienty: `instance_id`, `generated_at`, `tracking_since` a `lifetime` se skupinami `gtfs`, `realtime`, `api` a metrikami popsanými níže. Neobsahuje denní grafy ani filtr období. Čítače pokrývají celou zachovanou historii databáze, nepodléhají dennímu resetu a fungují i před importem GTFS. Jejich hodnoty odpovídají poli `lifetime` původního statistického endpointu. Také tento dotaz se započítá do externích API požadavků až po sestavení odpovědi.


`GET /api/v1/statistics?period=day&date=2026-10-12` vrací souhrny instance bez přihlášení. `period` přijímá `day`, `month` nebo `year`; `date` je libovolné datum ve vybraném období (výchozí dnešek, podporované roky 2000–2099). Dny a měsíce se vyhodnocují v pásmu **Europe/Prague**. Denní graf má při změně letního času 23 nebo 25 hodin; opakované hodiny rozlišuje časový posun.

- `tracking_since`: začátek měření. Provoz před nasazením této funkce se zpětně nedopočítává.
- `sources.gtfs` a `sources.realtime`: zapnutí stahování, interval, poslední kontrola (`last_checked_at`), úplné stažení (`last_downloaded_at`), úspěšné zpracování nebo potvrzení 304 (`last_success_at`), HTTP stav, poslední chyba, velikost posledního souboru a HTTP `Last-Modified`.
- `totals`: součty vybraného období, zvlášť pro `gtfs`, `realtime` a `api`.
- `lifetime`: součty od začátku měření.
- `series`: hodinové, denní nebo měsíční body pro grafy; obsahují stejné skupiny a metriky jako `totals`.
- `api_endpoints`: součty externích dotazů podle metody a šablony endpointu (například `GET /api/v1/stops/{stop_id}/departures`). Neobsahují skutečná ID, vyhledávací řetězce ani IP adresy. Neznámé cesty se slučují do `unmatched`.

Metriky stahování:

| Pole | Význam |
| --- | --- |
| `requests` | Pokusy o kontrolu zdroje, včetně odpovědí 304 a chyb. Přesměrování je součástí jednoho pokusu. |
| `downloads` | Úplně přijaté soubory HTTP 200; včetně souborů následně odmítnutých při zpracování. |
| `not_modified` | Platné odpovědi HTTP 304 při dostupné lokální kopii. |
| `errors` | Selhání spojení, HTTP chyby, překročení velikosti nebo neúspěšné zpracování. |
| `bytes` | Přijaté bajty těla konečné odpovědi před rozbalením HTTP komprese. Bez HTTP hlaviček, přesměrovacích těl a TLS; nejde o fakturační měření síťového provozu. Zahrnují i již přijaté části neúspěšných downloadů. |

Pro `api` se počítají dokončené požadavky na `/api/`, chyby 4xx/5xx a počty odpovědí `responses_2xx` až `responses_5xx`. Aktuální dotaz na statistiky se objeví až v následující odpovědi. Healthchecky, dokumentace a statické soubory se nepočítají. Naše webové rozhraní posílá hlavičku `X-IDS-JMK-Client: web`, která jeho požadavky z čítačů vynechá. Jde o konvenci pro rozlišení klientů, nikoli ověření jejich identity; externí klient může stejnou hlavičku také poslat. Běžné požadavky HA, Živého obrazu a ostatních klientů bez této hlavičky se počítají.

Statistiky a HTTP validátory se ukládají do `statistics.sqlite3` v `DATA_DIR`, tedy do stejného persistentního svazku jako jízdní řády. Zachovejte celý svazek při restartu nebo aktualizaci. Statistiky se ukládají jako hodinové součty, bez jednotlivých přístupových záznamů. Veřejný endpoint funguje i před prvním importem GTFS a při vypnutém realtime. Přehled `sources` je také v `/api/v1/status` pod klíčem `downloads`.

### Podmíněné stahování

Oba zdroje používají `If-None-Match` a `If-Modified-Since`, pokud zdroj dříve poskytl `ETag` nebo `Last-Modified` a server má odpovídající platná lokální data. HTTP 304 nevyvolá nové zpracování a neposune čas posledního stažení. Bez podpory validátorů se soubor stáhne běžným GETem. Poškozený či neúplný soubor nepřepíše validátory poslední přijaté verze.

Validátory platí pouze pro konkrétní zdrojovou URL a lokální verzi dat. Změna URL, chybějící data nebo neplatná realtime kopie vynutí celé stažení. Realtime kopie se ukládá do `realtime-cache.dat`; při restartu se ověří její otisk. Obnovení z disku ani odpověď 304 **neomlazují čas feedu nebo vozidel**. Posouzení stáří dál používá původní čas poskytovatele. Při `REALTIME_ENABLED=false` se uložená realtime kopie nepoužije.

### Data pro mapovou kartu

- `GET /api/v1/map/routes`: katalog linek (`id`, `line`, `name`) a směrů
  (`directions`: `id`, `label`). Popisky směrů vycházejí z nejčastějších cílů.
- `POST /api/v1/map/vehicles`: JSON pole nejvýše 20 položek
  `{"route_id":"…","direction":"*"}`. Hvězdička zahrne oba směry; prázdný
  výběr vrací prázdný seznam. Odpověď obsahuje `vehicles`, `realtime_enabled`,
  `stale`, `updated_at` a `generated_at`. Vozidla obsahují linku, směr, cíl,
  provozní den a čerstvou GPS polohu. Uplatňuje se kalendář a časové okno spoje,
  včetně předchozího provozního dne po půlnoci. Nejde o filtr příštích odjezdů.
- Pro zastávky vybraného vozidla použijte existující detail spoje s jeho
  `trip_id` a `service_date`.

HA zpřístupňuje tyto pevně vymezené operace přihlášeným klientům pomocí příkazů
`ids_jmk/map_sources` a `ids_jmk/map`. Mapová data nevytvářejí entity a neukládají
se do Recorderu.
