# Vydávání

Změny se nejprve ověří v CI a na testovací instalaci. Repozitář obsahuje dva Dockerfile, HA variantu API (target `home-assistant`) a samostatnou HA integraci.

1. Ověřte aktuálnost licence MIT a uvedení zdrojů v `docs/data-sources.md` (GTFS i realtime: CC BY 4.0).
2. Sjednoťte verzi v `pyproject.toml`, `web/package.json`, `web/package-lock.json`, manifestu integrace, API a Compose konfiguracích. Nastavení aplikace upravujte ve společné šabloně `home-assistant/ids_jmk/manifest.json`; distribuované `config.json` neměňte ručně, aktualizuje je workflow až po publikování obrazů. Obnovte `uv.lock` a export `requirements.txt`, pokud se změnily závislosti.
3. Spusťte testy, build webu, hassfest a všechny tři Docker obrazy včetně HA varianty na ARM64 a AMD64. Ověřte první import, proxy webu a persistentní data po restartu.
4. Nahrajte odpovídající tag `vX.Y.Z` pouze pro schválené vydání.
5. Workflow sestaví obrazy `ghcr.io/coolajz/ids-jmk-api:X.Y.Z`, `ghcr.io/coolajz/ids-jmk-web:X.Y.Z` a `ghcr.io/coolajz/ids-jmk-ha:X.Y.Z` pro AMD64 a ARM64 a vytvoří **draft** GitHub releasu se třemi Compose konfiguracemi, příkladem prostředí, licencí, uvedením zdrojů dat a ZIPem integrace.
6. Při prvním publikování ověřte veřejnou viditelnost všech tří GHCR balíčků; veřejný repozitář nezaručuje veřejný balíček. Otestujte stažení bez přihlášení, doplňte poznámky a teprve potom zveřejněte release.

Již vydané tagy nepřepisujte. Při aktualizaci v Portaineru změňte tag obrazu na vybrané vydání, stáhněte nový obraz a znovu nasaďte Stack. Zachovejte stejný svazek s daty. Databázi GTFS lze znovu vytvořit importem, ale soubor `instance-id` identifikuje server v Home Assistantu a je potřeba ho zachovat.

Tag spouští také znovu všechny kontroly z CI. Pro každý nový release ověřte jejich konkrétní běh; úspěch starší verze nezaručuje funkčnost aktuálního vydání.

## První vydání aplikace HA

Aplikace používá předem sestavený obraz; Supervisor ji nesestavuje ze zdrojů. První vydání aplikace je `0.1.4` a jeho sestavení spouští tag `v0.1.4`. Instalační manifest musí odkazovat na existující veřejný číselný tag obrazu. Při dalších vydáních sjednoťte zdrojové verze na nové nepoužité číslo a aktualizujte changelog aplikace. Distribuovaný manifest stabilní aplikace zůstává na poslední sestavené verzi, dokud není hotové vydávací workflow. Již vydané tagy nepřepisujte.

## Pracovní a distribuční větev

Vývoj provádějte ve větvi `develop` a nastavte její upstream na `origin/develop`. Codex pak běžně commituje a pushuje tuto pracovní větev. Větev `main` slouží pro distribuci: workflow do ní po úspěšném sestavení přenese zdroje a aktualizuje manifesty HA. Do `main` neprovádějte běžné vývojové commity. Zdrojové definice workflow se používají přímo z `develop`; automatika je do `main` nekopíruje. Pokud je potřeba sladit definice workflow i ve výchozí větvi GitHubu, proveďte to jednorázovým běžným pushem po kontrole změny.

Toto rozdělení zachovává URL repozitáře, identitu aplikací, jejich data a adresy API v HA. HACS zůstává ve stávajícím repozitáři. Oproti přidání větve do URL HA není potřeba aplikace přeinstalovat ani přepojovat integraci.

Vydání připravujte a tagujte nad otestovaným commitem pracovní větve. Již existující tagy a vzdálené commity nepřepisujte.

## Kanály aplikace HA

Workflow **Kontroly** po úspěšném pushi do pracovní větve `develop` publikuje také HA obraz s jedinečnou verzí `<verze-projektu>-dev<pořadové-číslo>`. Čítač je `číslo běhu × 1000 + pokus`, takže jej knihovna verzí Home Assistantu správně řadí i při opakovaném spuštění (pokus 1–999). Nadále zachovává aliasy `dev` a `dev-<SHA>` pro Docker instalace. HA varianta Dev odkazuje na konkrétní sestavení, aby Supervisor mohl nabídnout aktualizaci.

Teprve po úspěšném dokončení všech vývojových obrazů zavolá workflow publikování nabídky Dev. Workflow **Vydání** aktualizuje stabilní nabídku po dokončení obrazů i příloh releasu. Společný workflow `ha-channel.yaml` přenese úspěšně otestované zdroje z `develop` do distribuční větve `main`, vygeneruje manifesty ze společné šablony a zapíše je účtem `github-actions[bot]`. Používá `GITHUB_TOKEN` s oprávněním `contents: write`; nepotřebuje další tajný token. Pravidla větve musí tento zápis dovolovat. Pokud zápis selže, nabídka zůstane na předchozím sestavení a workflow hlásí chybu.

Automatické commity obsahují `[skip ci]` a použitý `GITHUB_TOKEN` při pushi sám nespouští další workflow, takže nevzniká nekonečné sestavování. Automatika nezapisuje do pracovní větve `develop`, takže nevyžaduje stahování svých commitů před dalším vývojovým pushem. GitHub, HACS i stávající HA repozitář nadále používají `main`.

Starý vývojový běh nesmí aktualizovat nabídku, pokud `develop` již obsahuje novější změny zdrojů. Opakovaný starší release ani starší dev sestavení nesmí nabídku vrátit zpět. Souběžné zápisy kanálů jsou serializované; při závodu s jiným pushem se zápis zkusí znovu bez force push.

Soubory `home-assistant/ids_jmk/config.json` a `home-assistant/ids_jmk_dev/config.json` jsou distribuční výstupy, nikoli zdrojové nastavení. Dev manifest, překlad a changelog se vytvoří až po prvním úspěšném sestavení. Testy a CI používají zdrojovou šablonu `manifest.json`, takže mohou ověřit budoucí nastavení před jeho nabídnutím uživatelům. Obě varianty používají stejný runtime bez dalších balíčků; odlišují se manifestem a verzí obrazu.

Před označením aplikace jako stabilní ověřte instalaci z tohoto repozitáře v HA OS, připojení integrace přes interní hostname z protokolu, změnu voleb, restart, aktualizaci a zálohu/obnovu. Na RPi změřte špičkovou RAM a místo při importu. CI testuje kontejner na obou architekturách, nikoli celý Supervisor.

Lokální sestavení HA obrazu z kořene repozitáře:

```sh
docker build --target home-assistant --build-arg BUILD_VERSION=dev -t ids-jmk-ha:test .
```

Spouštěcí skript připraví vlastní podadresář `/data/parser`, načte `/data/options.json` a před spuštěním API přejde na UID/GID 10001. Nepřidávejte web ani nástroje pro sestavení do výsledného HA obrazu.
