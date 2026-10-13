# Instalace a provoz serveru

[← Rozcestník](../README.md) · [Uživatelský návod HA](home-assistant.md) · [Vývoj](development.md)

Tato část je určena správcům Dockeru a samostatného serveru. Pro Home Assistant OS použijte také [návod aplikace IDS JMK Parser](../home-assistant/ids_jmk/DOCS.md).

## Obsah

- [Docker a Portainer](#docker-a-portainer)
- [Reverse proxy](#použití-interní-sítě-reverse-proxy)
- [Vývojové obrazy](#vývojové-verze-z-hlavní-větve)
- [Nastavení API](#nastavení-api)

## Docker a Portainer

Projekt lze sestavit ze zdrojů lokálně:

```sh
docker compose -f compose.web.yaml -f compose.build.yaml up -d --build
```

Pro instalaci vydané verze použijte v Portaineru **Stacks → Add stack → Web editor**:

- [compose.yaml](../compose.yaml) pro samotné API;
- [compose.web.yaml](../compose.web.yaml) pro API a web;
- [compose.proxy.yaml](../compose.proxy.yaml) pro API a web pouze za existující Docker reverse proxy, bez publikovaných portů.

V prostředí Stacku nastavte `BIND_IP` na konkrétní interní IP Docker serveru, dále `API_PORT` a případně `WEB_PORT`. Výchozí vazba `127.0.0.1` zpřístupní porty jen na samotném serveru. Pro přístup z LAN je nutné `BIND_IP` změnit. Na webovém portu je dostupné také API přes proxy, takže ho může použít i Home Assistant.

Příklad proměnných je v [.env.example](../.env.example). Datový svazek `ids-data` uchovává jízdní řády a identitu serveru. Nemažte jej při aktualizaci. Nasazujte pouze jednu instanci API nad jedním svazkem a jeden proces Uvicornu; plánovač i realtime snapshot žijí v této instanci.

Služba v této verzi nemá vlastní přihlášení. Pro provoz mimo důvěryhodnou síť ji umístěte za odpovídajícím zabezpečením reverzní proxy. Prohlížeč používá API stejného původu, takže není potřeba povolovat plošné CORS.

### Použití interní sítě reverse proxy

V Portaineru použijte `compose.proxy.yaml` a nastavte `PROXY_NETWORK` na existující Docker síť, ke které je připojená vaše proxy (výchozí `proxy`). V proxy nastavte upstream **HTTP**, host **`ids-jmk-web`**, port **`8080`**. Doménu a HTTPS certifikát spravuje reverse proxy.

Tento Stack nepublikuje žádné porty API ani webu na hostitele. Do společné sítě je připojen pouze web; API je dostupné přes jeho `/api/v1/` proxy. Web, API i `/docs` tedy používají jednu doménu. Případný vnější nestandardní HTTPS port generátor URL automaticky zachová. Pro více samostatných instalací v jedné proxy síti zvolte unikátní síťový alias webu.

Pro lokální sestavení tohoto režimu:

```sh
docker compose -f compose.proxy.yaml -f compose.build.yaml up -d --build
```

### Vývojové verze z hlavní větve

Po každém pushi do větve `main` workflow **Kontroly** spustí testy a po jejich úspěchu publikuje tři vývojové obrazy pro Linux AMD64 a ARM64:

- `ghcr.io/coolajz/ids-jmk-api:dev`
- `ghcr.io/coolajz/ids-jmk-web:dev`
- `ghcr.io/coolajz/ids-jmk-ha:dev` (parser pro HA OS)

Tag `dev` označuje poslední publikovanou vývojovou verzi. Každý obraz dostane také tag `dev-<celý SHA commitu>` pro nasazení konkrétní revize. Nový push ruší starší probíhající běh kontrol pro stejnou větev; při rychlém sledu pushů se tedy publikuje nejnovější úspěšně dokončený běh. Publikování vývojových obrazů nemění stabilní tag `latest` ani vydané verze. Pull requesty a ostatní větve se pouze testují.

Pro testování za reverse proxy ponechte v Portaineru repozitář, větev `refs/heads/main` a cestu `compose.proxy.yaml`. V **Environment variables** nastavte `IMAGE_TAG=dev`. Poté:

1. Vyčkejte, až na GitHubu úspěšně skončí celý workflow **Kontroly**, včetně publikování API i webu.
2. V Portaineru použijte **Pull and redeploy** a zapněte **Re-pull image** (podle verze **Re-pull image and redeploy**), aby se stáhl nový obsah tagu `dev`.
3. Po aktualizaci ověřte, že oba kontejnery hlásí stav `healthy`.

Obrazy se publikují samostatně. Pokud některé publikování selže nebo je běh přerušen, nenasazujte jej; vyčkejte na úspěšné dokončení všech obrazů. Pro návrat ke konkrétnímu úspěšnému běhu nastavte `IMAGE_TAG=dev-<celý SHA commitu>`, případně pro návrat ke stabilní verzi použijte její číselný tag. Datový svazek při aktualizaci zachovejte.

Samotná kontrola změn Gitu v Portaineru nezaručuje nasazení nového obrazu: může proběhnout ještě před dokončením sestavení a později už nenajít nový commit. Automatizace nasazení proto musí navazovat až na úspěšné publikování obou obrazů. Tento workflow automatizuje publikování, nikoli aktualizaci běžícího serveru. Podrobnosti k ruční aktualizaci popisuje [dokumentace Portaineru](https://docs.portainer.io/user/docker/stacks/edit).

### Nastavení API

| Proměnná | Výchozí hodnota | Význam |
| --- | --- | --- |
| `DATA_DIR` | `data` (v obrazu `/data`) | Persistentní data |
| `GTFS_URL` | Přímá adresa KORDIS níže | Zdroj jízdních řádů |
| `REALTIME_ENABLED` | `false` | `true` zapne stahování realtime, odhady, polohy a upozornění |
| `REALTIME_URL` | Přímá adresa KORDIS níže | Zdroj realtime |
| `GTFS_INTERVAL_SECONDS` | `86400` | Kontrola jízdních řádů každých 24 hodin, minimum 3600 s |
| `REALTIME_INTERVAL_SECONDS` | `60` | Kontrola realtime při aktivitě klientů, minimum 15 s |
| `REALTIME_IDLE_TIMEOUT_SECONDS` | `300` | Uspání po neaktivitě; `0` ponechá nepřetržité stahování |
| `REALTIME_MAX_AGE_SECONDS` | `180` | Maximální stáří použitelných realtime zpráv |
| `DOWNLOAD_ENABLED` | `true` | `false` vypne stahování pro izolované testy |

Intervaly můžete změnit v Portaineru v části **Environment variables** daného Stacku pomocí `GTFS_INTERVAL_SECONDS` a `REALTIME_INTERVAL_SECONDS` (hodnoty v sekundách). Pokud proměnné neuvedete, použije se 86400 a 60 sekund. Po změně znovu nasaďte Stack. Při prvním startu bez cache se jízdní řád načte ihned. Při restartu s platnou cache se dodrží uložený čas další kontroly. Povolený realtime standardně čeká na první požadavek klienta, který jej potřebuje; po pěti minutách bez takového požadavku se uspí. Parametr API `realtime=false`, statistiky ani healthchecky aktivitu neprodlužují. `REALTIME_IDLE_TIMEOUT_SECONDS=0` obnoví nepřetržité stahování od startu. Interval určuje prodlevu mezi dokončením obnovy a dalším stažením; při chybách realtime se prodlužuje až na 15 minut (nebo nastavený interval, je-li delší). Po neúspěšném stažení GTFS se pokus opakuje za 60 sekund a při dalších chybách se čekání zdvojnásobuje až na hodinu. Oba zdroje respektují `Retry-After` u HTTP 429/503 a čekání přetrvá restart. Obnova webové tabule a HA integrace z API zůstává každých 30 sekund.

Realtime je **výchozí vypnutý**. Pro jeho použití nastavte v `.env` nebo v Portaineru `REALTIME_ENABLED=true` a znovu nasaďte Stack. Nastavení platí pro všechny přiložené Compose varianty. Hodnota `false` nebo neuvedená proměnná znamená provoz pouze podle jízdního řádu: realtime se nestahuje, odjezdy neobsahují odhady, zpoždění, polohy ani upozornění. Web nabídne mapu zastávek spoje bez vozidel. Statické GTFS se nadále obnovuje podle `GTFS_INTERVAL_SECONDS`.

Stejný obsah GTFS se znovu neimportuje. Nový archiv se zkontroluje a importuje do oddělené databáze, která pak atomicky nahradí původní. Při chybě zůstává poslední funkční jízdní řád. Realtime snapshot se pravidelně nahrazuje, nepersistuje se přes restart.
