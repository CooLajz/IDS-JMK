"""Authenticated card heartbeats. Leases expire even after an abrupt disconnect."""

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import LEASE_SECONDS


@websocket_api.websocket_command({
    vol.Required("type"): "ids_jmk/board_visibility",
    vol.Required("client_id"): vol.All(str, vol.Length(min=1, max=64)),
    vol.Required("visible"): bool,
    vol.Optional("entity_ids", default=[]): vol.All([str], vol.Length(max=50)),
})
@callback
def visibility(hass, connection, msg):
    targets = set()
    if msg["visible"]:
        registry = er.async_get(hass)
        for entity_id in set(msg["entity_ids"]):
            entity = registry.async_get(entity_id)
            runtime = hass.data.get(DOMAIN, {}).get(entity.config_entry_id) if entity else None
            board = runtime["boards"].get(entity.config_subentry_id) if runtime else None
            if (
                not entity or entity.platform != DOMAIN or not entity_id.startswith("sensor.")
                or entity.disabled_by is not None or board is None
                or entity.unique_id != f"{board.subentry.unique_id}_departures"
                or not connection.user.permissions.check_entity(entity_id, POLICY_READ)
            ):
                connection.send_error(msg["id"], "not_found", "Odjezdová tabule není dostupná.")
                return
            targets.add(board)
    owner = (id(connection), msg["client_id"])
    for runtime in hass.data.get(DOMAIN, {}).values():
        for board in runtime["boards"].values():
            if board in targets or owner in board.leases:
                board.set_visible(owner, board in targets)
    connection.send_result(msg["id"], {"lease_seconds": LEASE_SECONDS})


@callback
def register_visibility(hass):
    websocket_api.async_register_command(hass, visibility)
