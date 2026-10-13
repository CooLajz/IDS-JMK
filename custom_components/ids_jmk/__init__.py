"""Home Assistant sources with departure-board subentries."""

import logging
from datetime import timedelta

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .board_visibility import register_visibility
from .client import APIError, Client
from .const import DOMAIN, PLATFORMS
from .coordinator import BoardCoordinator
from .frontend import async_register_card
from .vehicle_map import register_map

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    await async_register_card(hass)
    register_map(hass)
    register_visibility(hass)
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

        board_coordinator = BoardCoordinator(hass, entry, subentry, client)
        if board_coordinator.continuous:
            await board_coordinator.async_refresh()
        boards[subentry.subentry_id] = board_coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "statistics": statistics, "boards": boards,
        "source_settings": dict(entry.data),
        "board_settings": {key: dict(board.subentry.data) for key, board in boards.items()},
    }
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass, entry):
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    settings = {key: dict(s.data) for key, s in entry.subentries.items() if s.subentry_type == "board"}
    def without_mode(data):
        return {k: v for k, v in data.items() if k != "continuous_updates"}
    if (
        runtime and runtime["source_settings"] == dict(entry.data)
        and settings != runtime["board_settings"]
        and settings.keys() == runtime["board_settings"].keys()
        and all(without_mode(data) == without_mode(runtime["board_settings"][key])
                for key, data in settings.items())
    ):
        for key, data in settings.items():
            runtime["boards"][key].set_continuous(data.get("continuous_updates", False))
        runtime["board_settings"] = settings
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime = hass.data[DOMAIN].pop(entry.entry_id, None)
        if runtime:
            for coordinator in [runtime["statistics"], *runtime["boards"].values()]:
                await coordinator.async_shutdown()
        return True
    return False
