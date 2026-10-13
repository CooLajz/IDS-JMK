# Obrázky dokumentace

[← Rozcestník](../../README.md) · [Pro vývojáře](../development.md)

Snímky byly vytvořeny 13. 10. 2026 z kódu tohoto repozitáře v Chrome přes Playwright. Zachycují **skutečné vykreslení komponent**, nikoli generované obrázky nebo návrh budoucího rozhraní. Používají však **syntetická data**: nejde o aktuální jízdní řád, skutečnou výluku ani zaznamenanou jízdu vozidla.

| Soubor | Obsah |
| --- | --- |
| `ha-dashboard.png` | Moderní a kompaktní tabule, rozbalené upozornění a mapa |
| `ha-map-detail.png` | Mapová karta po kliknutí na vozidlo, orientační spojnice a seznam zastávek |
| `ha-mobile-dark.png` | Stejné karty na šířce 430 px s tmavými proměnnými motivu |
| `web-departures.png` | Skutečný web projektu s podvrženými ukázkovými odpověďmi API |

HA karty běží v [samostatné náhledové stránce](../preview/index.html), **mimo skutečný Home Assistant**. Stránka předává objekt `hass` s ukázkovými stavy a odpověďmi `callWS`, poskytuje motiv a minimální vykreslení `ha-icon` z MDI. Neukazuje přihlášení, instalační formuláře ani vizuální editor HA. Tyto snímky nepotvrzují instalaci v HA OS. Okolní stránka není napodobeninou navigace HA.

Zdrojové soubory produkčních karet se kvůli snímkům nemění. Čas prohlížeče začíná 13. 10. 2026 ve 14:00 Europe/Prague. Reálný mapový podklad načítá Leaflet z OpenStreetMap; není syntetický a může se při dalším snímkování změnit. Jeho atribuce zůstává na obrázcích viditelná: [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Ikony pocházejí z MDI; licenční oznámení je v [adresáři webu](../../web/public/MDI-LICENSE.txt).

## Opětovné vytvoření

Požadavky: Python 3, Node.js dle vývojářského návodu a instalovaný Google Chrome. Příkazy spouštějte z kořene repozitáře. Náhledové servery poslouchají pouze na `127.0.0.1` a nepotřebují spuštěný parser ani přístup k Vašemu HA. Vyžadují internet pro instalaci závislostí a mapový podklad.

```sh
npm --prefix web ci
python3 docs/preview/serve.py
```

V druhém terminálu spusťte skutečný web:

```sh
npm --prefix web run dev -- --port 18766
```

V třetím terminálu nainstalujte nástroj mimo repozitář a vytvořte snímky:

```sh
npm install --prefix /tmp/ids-docs-tools playwright@1.64.0
NODE_PATH=/tmp/ids-docs-tools/node_modules node docs/preview/capture.cjs
```

Příkaz přepíše čtyři PNG v tomto adresáři. Po dokončení zastavte oba servery pomocí Ctrl+C. Náhled lze otevřít i ručně na `http://127.0.0.1:18765/docs/preview/`; bez zmrazení času použije aktuální čas prohlížeče.

Skript kontroluje vykreslení mapy, rozbalí upozornění, otevře detail vozidla a API dialog webu, zaznamenává chyby JavaScriptu a kontroluje vodorovné přetečení na mobilu. Před zveřejněním obrázky také vizuálně ověřte: text, načtený podklad, atribuci a označení ukázkových dat. Pokud se změnil datový kontrakt nebo názvy prvků, upravte současně `preview.js` a snímkovací skript.
