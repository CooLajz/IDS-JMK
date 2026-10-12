# 0.1.5

- Přidáno API pro mapu vozidel: výběr linek a směrů, aktuální polohy a provozní den spoje.
- Nová samostatná karta Mapa vehyklů v integraci HA bez entit pro jednotlivá vozidla. Aktualizujte také integraci.
- Zachována kontrola stáří poloh a platnosti jízdního řádu, včetně spojů po půlnoci.

# 0.1.4

První vydání aplikace pro Home Assistant; do ověření skutečné instalace v HA OS je označena jako experimentální.

- Samostatná aplikace parseru pro HA OS na ARM64 a AMD64.
- Nastavení realtime a intervalů přímo v HA.
- Trvalá data, studené zálohy a volitelný přístup k API z LAN.
- Společný základ se samostatným API bez webu a dalších runtime závislostí.
