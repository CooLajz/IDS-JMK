# Vydávání

Změny se nejprve ověří v CI a na testovací instalaci. Repozitář obsahuje dva Dockerfile a samostatnou HA integraci.

1. Ověř aktuálnost licence MIT a uvedení zdrojů v `docs/data-sources.md` (GTFS i realtime: CC BY 4.0).
2. Sjednoť verzi v `pyproject.toml`, `web/package.json`, `web/package-lock.json`, manifestu integrace, API a Compose konfiguracích. Obnov `uv.lock` a export `requirements.txt`, pokud se změnily závislosti.
3. Spusť testy, build webu, hassfest a oba Docker obrazy. Ověř první import, proxy webu a persistentní data po restartu.
4. Nahraj odpovídající tag `vX.Y.Z` pouze pro schválené vydání.
5. Workflow sestaví obrazy `ghcr.io/coolajz/ids-jmk-api:X.Y.Z` a `ghcr.io/coolajz/ids-jmk-web:X.Y.Z` pro AMD64 a ARM64 a vytvoří **draft** GitHub releasu s oběma Compose konfiguracemi a ZIPem integrace.
6. Při prvním publikování ověř veřejnou viditelnost obou GHCR balíčků; veřejný repozitář nezaručuje veřejný balíček. Otestuj stažení bez přihlášení, doplň poznámky a teprve potom zveřejni release.

Již vydané tagy nepřepisuj. Při aktualizaci v Portaineru změň tag obrazu na vybrané vydání, stáhni nový obraz a znovu nasaď Stack. Zachovej stejný svazek s daty. Databázi GTFS lze znovu vytvořit importem, ale soubor `instance-id` identifikuje server v Home Assistantu a je potřeba ho zachovat.

Aktuálně jde o vývojovou verzi; workflow nebyl publikací souborů automaticky spuštěn a žádný release zatím nevznikl.
