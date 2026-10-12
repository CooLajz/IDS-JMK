"""Serve the bundled dashboard card through Home Assistant."""

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

CARD_PATH = Path(__file__).parent / "www" / "ids-jmk-departures-card.js"
CARD_URL = "/ids_jmk/ids-jmk-departures-card.js"


async def async_register_card(hass):
    """Register once during integration setup, independently of board entries."""
    for name in ("ids-jmk-departures-card.js", "ids-jmk-alerts-card.js", "ids-jmk-map-card.js"):
        path = CARD_PATH.with_name(name)
        url = f"/ids_jmk/{name}"
        content = await hass.async_add_executor_job(path.read_bytes)
        version = hashlib.sha256(content).hexdigest()[:12]
        await hass.http.async_register_static_paths([StaticPathConfig(url, str(path), False)])
        add_extra_js_url(hass, f"{url}?v={version}")

    vendor = CARD_PATH.parent / "map-vendor"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/ids_jmk/map-vendor", str(vendor), False)
    ])
