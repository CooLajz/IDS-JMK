# Vydávání

Změny se nejprve ověří v CI a na testovací instalaci. Repozitář obsahuje dva Dockerfile a samostatnou HA integraci.

1. Ověřte aktuálnost licence MIT a uvedení zdrojů v `docs/data-sources.md` (GTFS i realtime: CC BY 4.0).
2. Sjednoťte verzi v `pyproject.toml`, `web/package.json`, `web/package-lock.json`, manifestu integrace, API a Compose konfiguracích. Obnovte `uv.lock` a export `requirements.txt`, pokud se změnily závislosti.
3. Spusťte testy, build webu, hassfest a oba Docker obrazy. Ověřte první import, proxy webu a persistentní data po restartu.
4. Nahrajte odpovídající tag `vX.Y.Z` pouze pro schválené vydání.
5. Workflow sestaví obrazy `ghcr.io/coolajz/ids-jmk-api:X.Y.Z` a `ghcr.io/coolajz/ids-jmk-web:X.Y.Z` pro AMD64 a ARM64 a vytvoří **draft** GitHub releasu se třemi Compose konfiguracemi, příkladem prostředí, licencí, uvedením zdrojů dat a ZIPem integrace.
6. Při prvním publikování ověřte veřejnou viditelnost obou GHCR balíčků; veřejný repozitář nezaručuje veřejný balíček. Otestujte stažení bez přihlášení, doplňte poznámky a teprve potom zveřejněte release.

Již vydané tagy nepřepisujte. Při aktualizaci v Portaineru změňte tag obrazu na vybrané vydání, stáhněte nový obraz a znovu nasaďte Stack. Zachovejte stejný svazek s daty. Databázi GTFS lze znovu vytvořit importem, ale soubor `instance-id` identifikuje server v Home Assistantu a je potřeba ho zachovat.

Tag spouští také znovu všechny kontroly z CI. Pro každý nový release ověřte jejich konkrétní běh; úspěch starší verze nezaručuje funkčnost aktuálního vydání.
