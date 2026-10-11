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

Základ odpovědi odjezdů je `stop`, `generated_at`, `timezone`, `realtime_stale` a pole `departures` a `previous_departures`. Schéma každého řádku je popsané v OpenAPI. Pro HA jsou připravená také pole `departure_time_display` a `minutes_until`. Minuty platí k `generated_at`, nejsou běžícími hodinami; klient musí odpověď obnovovat.

`departure_time` je odhad, pokud je dostupný, jinak plánovaný čas. `scheduled_departure` zůstává zachován. `service_date` určuje provozní den: odjezd v 01:05 může patřit předchozímu dni jako 25:05. Seznam se řadí podle výsledného okamžiku. Konečné zastávky bez dalšího pokračování spoje se nevydávají za odjezdy.

## Původ časů

- `schedule`: pouze jízdní řád; `delay_seconds` a `estimated_departure` jsou `null`.
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
