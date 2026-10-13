# Instalace a provoz

Aplikace vyžaduje Home Assistant OS na ARM64 nebo AMD64. Home Assistant Container ani 32bitový systém nejsou podporovány.

## Verze a podpora

První vydání aplikace je **0.1.4**. HA stáhne předem sestavený obraz `ghcr.io/coolajz/ids-jmk-ha` s verzí uvedenou v konfiguraci aplikace. Označení experimentální zůstává do ověření v HA OS; kontejnery byly ověřeny v CI na ARM64 i AMD64.

## Stabilní a vývojová varianta

**IDS JMK Parser** nabízí číselná vydání po úspěšném sestavení releasu. **IDS JMK Parser (Dev)** nabízí samostatně instalovatelné vývojové sestavení po úspěšných kontrolách a publikování změn z větve `develop`. Obě aplikace najdete ve stejném repozitáři; Dev se poprvé objeví až po prvním úspěšném sestavení s podporou kanálů.

HA kontroluje aktualizace při obnově seznamu aplikací. V nastavení aplikace si můžete zapnout automatické aktualizace. Samotný push do Gitu nemění právě běžící kontejner.

Varianty mají vlastní nastavení, data, identitu a adresu API. Přechod proto vyžaduje připojení integrace k nové instanci; data se automaticky nepřevádějí. Pro běžný provoz zvolte vydanou variantu a ponechte spuštěný jeden parser. [Postup pro Dev](https://github.com/CooLajz/IDS-JMK/blob/main/home-assistant/ids_jmk_dev/DOCS.md).

## Přidání repozitáře

1. V **Nastavení → Aplikace → Obchod s aplikacemi → ⋮ → Repozitáře** přidejte `https://github.com/CooLajz/IDS-JMK`. Ve starších verzích HA se aplikace označují jako doplňky.
2. Vyberte **IDS JMK Parser**, nainstalujte jej a zapněte spouštění při startu systému.
3. Na kartě **Konfigurace** případně povolte realtime, uložte nastavení a spusťte aplikaci.
4. V **Protokolu** najděte řádek „Adresa API pro integraci na tomto HA“. Tuto adresu zadejte při přidávání integrace IDS JMK v **Nastavení → Zařízení a služby**.
5. Vyčkejte na dokončení prvního importu. Do té doby API hlásí, že se jízdní řády připravují. Doba závisí na výkonu zařízení, rychlosti úložiště a připojení.

Repozitář aplikací a HACS mají rozdílnou funkci. Přidání tohoto repozitáře do obchodu s aplikacemi samo nenainstaluje integraci ani kartu; ty nadále přidejte přes HACS nebo ručně podle hlavního návodu.

## Nastavení

| Volba | Výchozí hodnota | Význam |
| --- | --- | --- |
| `realtime_enabled` | `false` | Stahování zpoždění, poloh a upozornění |
| `gtfs_interval_seconds` | `86400` | Kontrola jízdních řádů; minimum 3600 sekund |
| `realtime_interval_seconds` | `60` | Obnova realtime; minimum 15 sekund |
| `realtime_idle_timeout_seconds` | `300` | Uspání bez realtime požadavků; `0` ponechá nepřetržité stahování |
| `realtime_max_age_seconds` | `180` | Nejvyšší přijatelné stáří realtime; minimum 30 sekund |

Povolený realtime se začne stahovat až na požadavek klienta a po pěti minutách neaktivity se uspí. V nastavení jednotlivé tabule v integraci můžete vypnout **Používat realtime data (zpoždění a upozornění)**; taková tabule ani statistické senzory stahování neudržují.

Po změně nastavení aplikaci restartujte. Bez realtime jsou dostupné plánované odjezdy. Aplikace stahuje data přímo z KORDIS JMK; nepotřebuje externí instanci našeho parseru.

## Připojení a porty

Pro integraci na stejném HA použijte interní adresu z protokolu, například `http://<identifikátor-repozitáře>-ids-jmk-parser:8080`. Nepoužívejte `localhost`, který by v integraci označoval samotný HA Core. Interní adresa je dostupná v síti HA, nikoli přímo z běžného prohlížeče v LAN.

Port do LAN je výchozí vypnutý. Potřebujete-li přístup pro jiný displej či zařízení, nastavte na kartě Konfigurace v části Síť volný hostitelský port a použijte `http://<adresa-HA>:<zvolený-port>`. API nemá vlastní přihlášení; port zpřístupněte pouze důvěryhodné místní síti.

## Data, místo a zálohy

Databáze, statistiky a identita serveru se ukládají do `/data/parser`, odděleně od nastavení spravovaného HA. Restart a aktualizace data zachovají. Při zálohování vyberte i tuto aplikaci. Používá studenou zálohu: HA ji před zálohou zastaví, aby během kopírování neprobíhal import ani zápis do databáze. Po dobu zálohy může být senzor nedostupný.

Obraz vychází ze stejného Python slim základu jako samostatné API. Přidává pouze spouštěcí skript ze standardní knihovny Pythonu; neobsahuje web, Node.js, nginx ani nový správce procesů. K místu obrazu připočtěte jízdní řády a prostor pro obnovu: během importu nových dat zůstává stará databáze zachována a vzniká nová. Reálné nároky na RAM a úložiště na RPi zatím nebyly změřeny.

Při obnově zálohy zachovejte celý datový adresář včetně `instance-id`, podle kterého integrace rozpoznává server. Odinstalace aplikace může odstranit její data; před odinstalací vytvořte zálohu.

## Kontrola běhu

Watchdog kontroluje běh API přes `/health/live`. Připravenost jízdních řádů ukazuje `/health/ready`; během importu může vracet 503. Chyba stažení nemá vést k restartovací smyčce: parser se pokusí o stažení znovu a při obnově ponechá poslední funkční jízdní řád.

## Zdroje dat

Zdrojem jízdních řádů a realtime je KORDIS JMK, licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Odhady zpoždění zpracovává tato neoficiální aplikace. Podrobnosti uvádí [dokumentace zdrojů](https://github.com/CooLajz/IDS-JMK/blob/main/docs/data-sources.md).
