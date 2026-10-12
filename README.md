# IDS JMK

Vlastní server pro jízdní řády a realtime data IDS JMK. Poskytuje JSON API pro odjezdové displeje, weby a Home Assistant. Volitelný web nabízí vyhledávání zastávek, odjezdovou tabuli a detail spoje s polohou vozidla.

**Verze 0.1.3.** Instalační Compose soubory pro Portainer a ZIP integrace Home Assistantu jsou součástí [vydání na GitHubu](https://github.com/CooLajz/IDS-JMK/releases). Obrazy API a webu se vydávají samostatně pro Linux AMD64 a ARM64.

## Součásti

| Součást | Funkce |
| --- | --- |
| API | Import GTFS do SQLite, automatické aktualizace, vyhledávání zastávek a stanovišť, odjezdy a vlastní odhady zpoždění, polohy vozidel, OpenAPI |
| Web | Vyhledávání bez diakritiky, filtr směru/linky/stanoviště, AJAX obnova a průběžný odpočet, poslední minulý odjezd, sdílitelná URL, detail spoje, značka a mapa čerstvé polohy, konfigurace pro HA |
| Home Assistant | Vlastní integrace s průvodcem: adresa serveru → vyhledání zastávky → stanoviště, linka a směr. Jeden senzor se seznamem odjezdů; vlastní karta dashboardu s vizuálním editorem |

API a web mají **samostatné Docker obrazy**. Web nic nestahuje z GTFS a nemá vlastní databázi. API funguje zcela bez webu. Komponenta Home Assistantu komunikuje pouze s API.

## Místní spuštění pro vývoj

Požadavky: Python 3.13, [uv](https://docs.astral.sh/uv/) a Node.js 22.12+.

```sh
uv sync --frozen
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
```

V druhém terminálu:

```sh
cd web
npm ci
npm run dev
```

Web: [http://127.0.0.1:5173](http://127.0.0.1:5173). API dokumentace: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

První start automaticky stáhne jízdní řády a vytvoří databázi v `data/`. Během importu API vrací stav 503 s vysvětlením; web počká a připojí se automaticky.

## Docker a Portainer

Projekt lze sestavit ze zdrojů lokálně:

```sh
docker compose -f compose.web.yaml -f compose.build.yaml up -d --build
```

Pro instalaci vydané verze použijte v Portaineru **Stacks → Add stack → Web editor**:

- [compose.yaml](compose.yaml) pro samotné API;
- [compose.web.yaml](compose.web.yaml) pro API a web;
- [compose.proxy.yaml](compose.proxy.yaml) pro API a web pouze za existující Docker reverse proxy, bez publikovaných portů.

V prostředí Stacku nastavte `BIND_IP` na konkrétní interní IP Docker serveru, dále `API_PORT` a případně `WEB_PORT`. Výchozí vazba `127.0.0.1` zpřístupní porty jen na samotném serveru. Pro přístup z LAN je nutné `BIND_IP` změnit. Na webovém portu je dostupné také API přes proxy, takže ho může použít i Home Assistant.

Příklad proměnných je v [.env.example](.env.example). Datový svazek `ids-data` uchovává jízdní řády a identitu serveru. Nemažte jej při aktualizaci. Nasazujte pouze jednu instanci API nad jedním svazkem a jeden proces Uvicornu; plánovač i realtime snapshot žijí v této instanci.

Služba v této verzi nemá vlastní přihlášení. Pro provoz mimo důvěryhodnou síť ji umístěte za odpovídajícím zabezpečením reverzní proxy. Prohlížeč používá API stejného původu, takže není potřeba povolovat plošné CORS.

### Použití interní sítě reverse proxy

V Portaineru použijte `compose.proxy.yaml` a nastavte `PROXY_NETWORK` na existující Docker síť, ke které je připojená vaše proxy (výchozí `proxy`). V proxy nastavte upstream **HTTP**, host **`ids-jmk-web`**, port **`8080`**. Doménu a HTTPS certifikát spravuje reverse proxy.

Tento Stack nepublikuje žádné porty API ani webu na hostitele. Do společné sítě je připojen pouze web; API je dostupné přes jeho `/api/v1/` proxy. Web, API i `/docs` tedy používají jednu doménu. Případný vnější nestandardní HTTPS port generátor URL automaticky zachová. Pro více samostatných instalací v jedné proxy síti zvolte unikátní síťový alias webu.

Pro lokální sestavení tohoto režimu:

```sh
docker compose -f compose.proxy.yaml -f compose.build.yaml up -d --build
```

### Nastavení API

| Proměnná | Výchozí hodnota | Význam |
| --- | --- | --- |
| `DATA_DIR` | `data` (v obrazu `/data`) | Persistentní data |
| `GTFS_URL` | Přímá adresa KORDIS níže | Zdroj jízdních řádů |
| `REALTIME_ENABLED` | `false` | `true` zapne stahování realtime, odhady, polohy a upozornění |
| `REALTIME_URL` | Přímá adresa KORDIS níže | Zdroj realtime |
| `GTFS_INTERVAL_SECONDS` | `86400` | Kontrola jízdních řádů každých 24 hodin, minimum 3600 s |
| `REALTIME_INTERVAL_SECONDS` | `60` | Kontrola realtime každých 60 sekund, minimum 15 s |
| `REALTIME_MAX_AGE_SECONDS` | `180` | Maximální stáří použitelných realtime zpráv |
| `DOWNLOAD_ENABLED` | `true` | `false` vypne stahování pro izolované testy |

Intervaly můžete změnit v Portaineru v části **Environment variables** daného Stacku pomocí `GTFS_INTERVAL_SECONDS` a `REALTIME_INTERVAL_SECONDS` (hodnoty v sekundách). Pokud proměnné neuvedete, použije se 86400 a 60 sekund. Po změně znovu nasaďte Stack. Při startu se jízdní řád a případně zapnutý realtime načtou ihned; interval určuje prodlevu mezi dokončením obnovy a dalším stažením. Po neúspěšném stažení GTFS se pokus opakuje za 60 sekund. Obnova webové tabule a HA integrace z API zůstává každých 30 sekund.

Realtime je **výchozí vypnutý**. Pro jeho použití nastavte v `.env` nebo v Portaineru `REALTIME_ENABLED=true` a znovu nasaďte Stack. Nastavení platí pro všechny přiložené Compose varianty. Hodnota `false` nebo neuvedená proměnná znamená provoz pouze podle jízdního řádu: realtime se nestahuje, odjezdy neobsahují odhady, zpoždění, polohy ani upozornění. Web nabídne mapu zastávek spoje bez vozidel. Statické GTFS se nadále obnovuje podle `GTFS_INTERVAL_SECONDS`.

Stejný obsah GTFS se znovu neimportuje. Nový archiv se zkontroluje a importuje do oddělené databáze, která pak atomicky nahradí původní. Při chybě zůstává poslední funkční jízdní řád. Realtime snapshot se pravidelně nahrazuje, nepersistuje se přes restart.

## API a Home Assistant

- [Popis API a odhadů](docs/api.md)
- [Instalace integrace a odjezdová tabule v HA](docs/home-assistant.md)
- [Postup vydávání](docs/releases.md)
- Interaktivní dokumentace `/docs` a strojový popis `/openapi.json`

## Zdroje a podmínky dat

Aplikace stahuje **přímo z KORDIS JMK**:

- [GTFS jízdní řády](https://kordis-jmk.cz/gtfs/gtfs.zip)
- [GTFS Realtime](https://kordis-jmk.cz/gtfs/gtfsReal.dat)

KORDIS na [oficiální stránce otevřených dat](https://www.idsjmk.cz/a/kontakty.html) uvádí pro statické GTFS i dynamické GTFS Realtime licenci **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** (ověřeno 11. 10. 2026). Při dalším použití uveďte původ dat a licenci a rozlišujte vlastní úpravy či odhady. Podrobnosti a doporučené uvedení zdroje jsou v [docs/data-sources.md](docs/data-sources.md).

Týdenní obnova zmíněná na [portálu Brna](https://data.brno.cz/datasets/379d2e9a7907460c8ca7fda1f3e84328/about) se týká jeho kopie ke stažení; není intervalem aktualizace přímých zdrojů KORDIS používaných aplikací.

Mapový podklad používá OpenStreetMap, načítá se pouze při otevření detailu s dostupnou polohou. Pro větší veřejné instalace zvolte vlastní vhodný mapový server v souladu s [podmínkami OSM dlaždic](https://operations.osmfoundation.org/policies/tiles/).

Projekt je nezávislý a není oficiální aplikací KORDIS JMK. Vlastní kód je dostupný pod [licencí MIT](LICENSE). Licence kódu nemění licenci dopravních dat ani knihoven třetích stran.

## Ověření

```sh
uv run pytest -q
uv run ruff check api custom_components tests
cd web
npm ci
npm run build
```

Testy používají malé syntetické GTFS archivy, nikoli síťové služby. Pokrývají import, zachování staré databáze, kalendáře a výjimky, časy po půlnoci, změny času, odhady a stáří realtime i odpovědi API.

GitHub Actions ověřují Python testy, web, hassfest, oba Docker obrazy, první import, webovou proxy a zachování identity po restartu. Publikování obrazů je podmíněné úspěchem těchto kontrol. Samostatná testovací instalace byla ověřena za HTTPS reverse proxy; konfigurace a senzor integrace byly ověřeny v izolovaném Home Assistantu 2025.12.5. Vlastní karta byla ověřena i v dashboardu tohoto HA, v grafickém editoru a ve světlém i tmavém motivu na mobilní šířce. Konkrétní prostředí a fyzický displej si ověřte ve své instalaci.

Piktogramy dopravy a vybavení pocházejí z [Material Design Icons od Pictogrammers](https://pictogrammers.com/library/mdi/). Web obsahuje původní SVG cesty z balíčku `@mdi/js` 7.4.47, HA využívá vestavěnou sadu MDI. Licenční oznámení webu je přiloženo v `web/public/THIRD-PARTY-NOTICES.txt`.
