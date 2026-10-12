"""Home Assistant sources with departure-board subentries."""

import logging
from datetime import timedelta

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import APIError, Client
from .const import DOMAIN, PLATFORMS
from .frontend import async_register_card
from .vehicle_map import register_map

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    await async_register_card(hass)
    register_map(hass)
    return True


async def async_setup_entry(hass, entry):
    client = Client(async_get_clientsession(hass), entry.data["base_url"])

    def coordinator(name, fetch, seconds):
        async def update():
            try:
                return await fetch()
            except APIError as exc:
                raise UpdateFailed("IDS JMK API není dostupné") from exc
        return DataUpdateCoordinator(
            hass, _LOGGER, name=name, update_method=update,
            update_interval=timedelta(seconds=seconds), config_entry=entry,
        )

    statistics = coordinator(f"{entry.title} statistics", client.statistics, 60)
    # A missing statistics endpoint on an older server must not disable departures.
    await statistics.async_refresh()
    boards = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != "board":
            continue

        async def fetch_board(board=subentry):
            return await client.departures(board.data["stop_id"], board.data)

        board_coordinator = coordinator(subentry.title, fetch_board, 30)
        await board_coordinator.async_refresh()
        boards[subentry.subentry_id] = board_coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"statistics": statistics, "boards": boards}
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
