# IDS JMK

Samostatně nasaditelná služba pro zpracování jízdních řádů a realtime dat IDS JMK. Cílem je poskytovat jednoduché JSON API pro aplikace, weby, odjezdové displeje a další systémy.

> Projekt je ve fázi návrhu. Zatím neobsahuje funkční aplikaci, Docker obrazy ani instalační release.

## Plánované součásti

- **API** — stahování a zpracování GTFS a realtime dat, lokální databáze, vyhledávání zastávek, odjezdy, odhady zpoždění a polohy vozidel.
- **Web** — volitelný klient stejného API s vyhledáváním zastávek, výběrem stanoviště či směru, odjezdovou tabulí a mapou vozidla na vybraném spoji.

Obě součásti budou mít samostatný Docker obraz. API bude fungovat i bez webu.

## Plánované nasazení

Pro Docker Compose a Portainer budou připraveny dvě konfigurace:

1. Pouze API.
2. API a web v jednom Stacku.

Uživatel si zvolí publikovaný port. Služba si při prvním startu stáhne a zpracuje data; odjezdy zpřístupní po dokončení importu. Databáze bude uložena v persistentním svazku bez požadavku na samostatnou databázovou službu.

Plánujeme verzované veřejné Docker obrazy pro AMD64 a ARM64, GitHub Releases s odpovídajícími Compose konfiguracemi, návod k aktualizaci a dokumentaci API. Automatické aktualizace zdrojových dat budou oddělené od aktualizací samotné aplikace.

## Zdroje dat

- [Statické GTFS — jízdní řády](https://kordis-jmk.cz/gtfs/gtfs.zip)
- [GTFS Realtime — provozní data](https://kordis-jmk.cz/gtfs/gtfsReal.dat)

Poskytovatelem zdrojových dat je KORDIS JMK. Tento projekt je nezávislý a není oficiální aplikací poskytovatele.

Realtime feed může obsahovat polohy vozidel bez předpovědí odjezdů typu TripUpdate. V takovém případě chceme odjezdy odhadovat propojením údajů o vozidle s jízdním řádem. Vlastní odhad nebude označován jako dopravcem potvrzený čas.

API bude rozlišovat plánovaný čas, předpověď ze zdroje a vlastní odhad. Uvede stáří realtime dat; při chybějících či zastaralých údajích poskytne jízdní řád bez předstírání nulového zpoždění.

## První plánovaný rozsah

- Vyhledávání zastávek a jejich stanovišť.
- Odjezdy se zohledněním provozních kalendářů, výjimek a spojů po půlnoci.
- Odhadované odjezdy a zpoždění z dostupných realtime údajů.
- Přístup k polohám vozidel pro navazující klienty.
- Stav služby, průběh počátečního importu a stáří dat.
- Volitelná webová odjezdová tabule a detail spoje.

Konkrétní API, technologie a intervaly obnovování ještě nejsou stanovené. Nejdříve bude podporován a ověřován IDS JMK; podpora jiných dopravních systémů není zatím garantována.

## Licence

Licence projektu bude zvolena před vydáním implementace. Veřejná dostupnost repozitáře sama o sobě nenahrazuje licenci. Podmínky použití zdrojových dopravních dat se řídí jejich poskytovatelem a budou zdokumentovány samostatně.
