# Zdroje a licence dopravních dat

Poskytovatelem jízdních řádů a realtime dat je **KORDIS JMK, a.s.** Projekt IDS JMK parser je nezávislý a není oficiální aplikací poskytovatele.

- [Statické GTFS](https://kordis-jmk.cz/gtfs/gtfs.zip)
- [Dynamické GTFS Realtime](https://kordis-jmk.cz/gtfs/gtfsReal.dat)
- [Oficiální podmínky](https://www.idsjmk.cz/a/kontakty.html), sekce „Otevřená data (GTFS)“
- [Licence CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Ověřeno 11. 10. 2026: přímo nad odkazy na oba zdroje poskytovatel uvádí „Data lze použít v souladu s licencí CC BY40.“ Tato konkrétní informace o GTFS má přednost před obecným licenčním textem v patičce webu poskytovatele.

Parser stahuje původní zdroje přímo z KORDIS, nikoli týdenní kopii z portálu Brna. Stažená data nejsou součástí zdrojového repozitáře, Docker obrazů ani instalačních archivů. Každá instance je získá při spuštění a následně aktualizuje.

## Uvedení zdroje ve vlastních aplikacích

Pro odjezdové tabule, Živý obraz, Home Assistant nebo jiného klienta použij například:

> Data: KORDIS JMK, CC BY 4.0. Zpracování: IDS JMK parser. Odhady odjezdů jsou vypočtené z dostupných dat.

Uveď odkazy na poskytovatele, licenci a [projekt](https://github.com/CooLajz/IDS-JMK) na vhodném místě rozhraní nebo v informacích o zdrojích. Zachovej rozlišení mezi jízdním řádem, přímou předpovědí a vlastním odhadem (`source`). Zpracovaná odpověď JSON a vlastní odhad nejsou nezměněným původním GTFS feedem.

Licence MIT v kořeni projektu platí pro vlastní kód a dokumentaci, nikoli pro data poskytovatele. Mapový podklad podléhá samostatným [podmínkám OpenStreetMap](https://www.openstreetmap.org/copyright) a [provozu dlaždic](https://operations.osmfoundation.org/policies/tiles/). Web zobrazuje mapovou atribuci přímo v mapě.
