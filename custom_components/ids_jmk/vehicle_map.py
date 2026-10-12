"""Authenticated, fixed-path map API bridge. No vehicle entities or recorder writes."""

from urllib.parse import quote

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import APIError, Client
from .const import DOMAIN


@websocket_api.websocket_command({vol.Required("type"): "ids_jmk/map_sources"})
@callback
def sources(hass, connection, msg):
    connection.send_result(
        msg["id"],
        [
            {"id": entry.entry_id, "name": entry.title}
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in hass.data.get(DOMAIN, {})
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ids_jmk/map",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(["routes", "vehicles", "trip"]),
        vol.Optional("selections", default=[]): vol.All(
            [
                {
                    vol.Required("route_id"): vol.All(str, vol.Length(min=1, max=200)),
                    vol.Required("direction"): vol.All(str, vol.Length(max=20)),
                }
            ],
            vol.Length(max=20),
        ),
        vol.Optional("trip_id"): vol.All(str, vol.Length(min=1, max=200)),
        vol.Optional("service_date"): vol.Match(r"^\d{4}-\d{2}-\d{2}$"),
    }
)
@websocket_api.async_response
async def request(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if not entry or entry.domain != DOMAIN or entry.entry_id not in hass.data.get(DOMAIN, {}):
        connection.send_error(msg["id"], "not_found", "Připojení IDS JMK není dostupné.")
        return
    client = Client(async_get_clientsession(hass), entry.data["base_url"])
    try:
        if msg["action"] == "routes":
            result = await client.get("map/routes")
        elif msg["action"] == "vehicles":
            result = await client.get("map/vehicles", payload=msg["selections"])
        else:
            if not msg.get("trip_id") or not msg.get("service_date"):
                connection.send_error(msg["id"], "invalid_format", "Chybí spoj nebo provozní den.")
                return
            result = await client.get(
                f"trips/{quote(msg['trip_id'], safe='')}", {"service_date": msg["service_date"]}
            )
        connection.send_result(msg["id"], result)
    except APIError:
        connection.send_error(
            msg["id"], "api_error", "Mapová data nejsou dostupná. Ověřte připojení a verzi API."
        )


@callback
def register_map(hass):
    websocket_api.async_register_command(hass, sources)
    websocket_api.async_register_command(hass, request)
