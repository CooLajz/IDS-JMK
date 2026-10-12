# 0.1.5

- Doplněno API `/api/v1/map/stops` pro zastávky vybraných linek a směrů, nezávisle na jedoucích vozidlech.
- Karta nabízí interval obnovování (výchozí 30 sekund), trvalé zastávky a zavření detailu kliknutím do mapy.
- Přehled se pamatuje po obnovení stránky a zahrnuje všechna vozidla i zapnuté zastávky.
- Při aktualizaci dřívějšího sestavení 0.1.5 stáhněte obrazy znovu a přeinstalujte integraci.

- Doplněn kumulativní endpoint `/api/v1/statistics/cumulative` pro statistické senzory integrace.
- Integrace nyní sdružuje více tabulí pod jeden zdroj a poskytuje 18 statistických senzorů bez denního resetu.

- Přidáno API pro mapu vozidel: výběr linek a směrů, aktuální polohy a provozní den spoje.
- Nová samostatná karta Mapa vehyklů v integraci HA bez entit pro jednotlivá vozidla. Aktualizujte také integraci.
- Zachována kontrola stáří poloh a platnosti jízdního řádu, včetně spojů po půlnoci.

# 0.1.4

První vydání aplikace pro Home Assistant; do ověření skutečné instalace v HA OS je označena jako experimentální.

- Samostatná aplikace parseru pro HA OS na ARM64 a AMD64.
- Nastavení realtime a intervalů přímo v HA.
- Trvalá data, studené zálohy a volitelný přístup k API z LAN.
- Společný základ se samostatným API bez webu a dalších runtime závislostí.
