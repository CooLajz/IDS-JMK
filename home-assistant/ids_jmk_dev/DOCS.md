# Vývojová aplikace

Ve stejném repozitáři jsou dvě samostatné aplikace:

| Aplikace | Aktualizace |
| --- | --- |
| **IDS JMK Parser** | Nové číselné vydání po úspěšném sestavení releasu |
| **IDS JMK Parser (Dev)** | Nové sestavení po úspěšných kontrolách a publikování obrazů z větve `develop` |

Dev používá vlastní verze, například `0.1.5-dev42001`. Číslo určuje konkrétní sestavení a jeho pokus. Každá verze má odpovídající Docker tag; již nainstalovaná aplikace se tím sama nezmění. HA nabídne aktualizaci při další obnově seznamu aplikací. V HA si můžete zapnout automatické aktualizace.

## Instalace

1. Přidejte repozitář `https://github.com/CooLajz/IDS-JMK` v obchodě s aplikacemi HA.
2. Po prvním úspěšném vývojovém sestavení obnovte seznam aplikací a vyberte **IDS JMK Parser (Dev)**.
3. Nastavte aplikaci, spusťte ji a vyčkejte na první import. Spouštění Dev při startu systému je výchozí vypnuté; podle potřeby je zapněte.
4. Integraci připojte k adrese z protokolu této aplikace, například `http://<identifikátor-repozitáře>-ids-jmk-parser-dev:8080`.

Pro nastavení realtime, portů a záloh použijte [společný návod parseru](https://github.com/CooLajz/IDS-JMK/blob/main/home-assistant/ids_jmk/DOCS.md).

## Přechod mezi variantami

Každá aplikace má vlastní databázi a identitu. Instalace Dev nepřevede data ani nastavení z vydané aplikace. Při změně varianty se znovu načtou jízdní řády a integraci je potřeba připojit k API nové instance. Ve výchozím nastavení nepublikují aplikace port do LAN; pokud jej zapnete u obou, zvolte rozdílné hostitelské porty.

Pro běžné použití ponechte spuštěnou jednu variantu, aby se dopravní data zbytečně nestahovala dvakrát. Pro souběžné testování můžete provozovat obě jako oddělené instance. Před změnou varianty nebo větší aktualizací vytvořte zálohu.
