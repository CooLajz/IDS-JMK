# Vydávání

Změny se nejprve ověří v CI a na testovací instalaci. Repozitář obsahuje dva Dockerfile, HA variantu API (target `home-assistant`) a samostatnou HA integraci.

1. Ověřte aktuálnost licence MIT a uvedení zdrojů v `docs/data-sources.md` (GTFS i realtime: CC BY 4.0).
2. Sjednoťte verzi v `pyproject.toml`, `web/package.json`, `web/package-lock.json`, manifestu integrace, API, Compose konfiguracích a `home-assistant/ids_jmk/config.json`. Obnovte `uv.lock` a export `requirements.txt`, pokud se změnily závislosti.
3. Spusťte testy, build webu, hassfest a všechny tři Docker obrazy včetně HA varianty na ARM64 a AMD64. Ověřte první import, proxy webu a persistentní data po restartu.
4. Nahrajte odpovídající tag `vX.Y.Z` pouze pro schválené vydání.
5. Workflow sestaví obrazy `ghcr.io/coolajz/ids-jmk-api:X.Y.Z`  , `ghcr.io/coolajz/ids-jmk-web:X.Y.Z` a `ghcr.io/coolajz/ids-jmk-ha:X.Y.Z` pro AMD64 a ARM64 a vytvoří **draft** GitHub releasu se třemi Compose konfiguracemi, příkladem prostředí, licencí, uvedením zdrojů dat a ZIPem integrace.
6. Při prvním publikování ověřte veřejnou viditelnost všech tří GHCR balíčků; veřejný repozitář nezaručuje veřejný balíček. Otestujte stažení bez přihlášení, doplňte poznámky a teprve potom zveřejněte release.

Již vydané tagy nepřepisujte. Při aktualizaci v Portaineru změňte tag obrazu na vybrané vydání, stáhněte nový obraz a znovu nasaďte Stack. Zachovejte stejný svazek s daty. Databázi GTFS lze znovu vytvořit importem, ale soubor `instance-id` identifikuje server v Home Assistantu a je potřeba ho zachovat.

Tag spouští také znovu všechny kontroly z CI. Pro každý nový release ověřte jejich konkrétní běh; úspěch starší verze nezaručuje funkčnost aktuálního vydání.

## První vydání aplikace HA

Aplikace používá předem sestavený obraz; Supervisor ji nesestavuje ze zdrojů. Větev s aplikačním manifestem musí odkazovat na existující veřejný číselný tag obrazu. Aktuální verze v manifestu kopíruje verzi projektu, neznamená již vydaný HA obraz. Před vydáním sjednoťte všechny verze na nové nepoužité číslo; existující tag `v0.1.3` nepřepisujte. Po úspěšném publikování odstraňte upozornění o nedostupnosti prvního obrazu v README a návodech a doplňte changelog aplikace.

Vývojové sestavení publikuje také `ghcr.io/coolajz/ids-jmk-ha:dev` a `dev-<SHA>`. Instalační manifest HA zůstává na číselné verzi, takže běžní uživatelé nedostávají vývojové obrazy automaticky.

Před označením aplikace jako stabilní ověřte instalaci z tohoto repozitáře v HA OS, připojení integrace přes interní hostname z protokolu, změnu voleb, restart, aktualizaci a zálohu/obnovu. Na RPi změřte špičkovou RAM a místo při importu. CI testuje kontejner na obou architekturách, nikoli celý Supervisor.

Lokální sestavení HA obrazu z kořene repozitáře:

```sh
docker build --target home-assistant --build-arg BUILD_VERSION=dev -t ids-jmk-ha:test .
```

Spouštěcí skript připraví vlastní podadresář `/data/parser`, načte `/data/options.json` a před spuštěním API přejde na UID/GID 10001. Nepřidávejte web ani nástroje pro sestavení do výsledného HA obrazu.
