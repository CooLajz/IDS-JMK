"""Home Assistant client for the separately deployed IDS JMK server."""

import logging
from datetime import timedelta

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import APIError, Client
from .const import DOMAIN, PLATFORMS
from .frontend import async_register_card


async def async_setup(hass, config):
    await async_register_card(hass)
    return True


async def async_setup_entry(hass, entry):
    client = Client(async_get_clientsession(hass), entry.data["base_url"])

    async def fetch():
        try:
            return await client.departures(entry.data["stop_id"], {**entry.data, **entry.options})
        except APIError as exc:
            raise UpdateFailed("IDS JMK API není dostupné") from exc

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=fetch,
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
