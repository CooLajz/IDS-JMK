"""Visibility polling has no upstream demand while idle."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")
from homeassistant.core import HomeAssistant  # noqa: E402

from custom_components.ids_jmk.coordinator import BoardCoordinator  # noqa: E402


def test_polling_leases_manual_refresh_and_modes(tmp_path):
    async def run():
        hass = HomeAssistant(str(tmp_path))
        entry = Mock(pref_disable_polling=False)
        sub = SimpleNamespace(title="Board", data={"stop_id": "stop"})
        client = SimpleNamespace(departures=AsyncMock(return_value={"departures": []}))
        board = BoardCoordinator(hass, entry, sub, client)
        assert not board.active
        await board.async_refresh()
        client.departures.assert_not_awaited()
        assert board.data is None
        board.set_visible("a", True)
        board.set_visible("b", True)
        await board._wake_task
        assert client.departures.await_count == 1
        board.set_visible("a", False)
        assert board.active
        board.leases["b"] = hass.loop.time() - 1
        board._expire_leases()
        assert not board.active
        assert board.update_interval is None
        await board.async_refresh()
        assert client.departures.await_count == 1
        await board.async_manual_refresh()
        assert client.departures.await_count == 2
        assert not board.active
        board.set_continuous(True)
        await board._wake_task
        assert client.departures.await_count == 3
        board.set_visible("a", True)
        board.set_continuous(False)
        assert board.active
        board.set_visible("a", False)
        assert not board.active
        entry.pref_disable_polling = True
        board.set_visible("a", True)
        assert not board.active
        await board.async_shutdown()
        assert not board.leases and board._lease_timer is None
        await hass.async_stop()
    asyncio.run(run())


def test_visibility_validates_permissions_and_releases_only_own_lease():
    from custom_components.ids_jmk.board_visibility import visibility

    board = Mock(subentry=SimpleNamespace(unique_id="board"), leases={})
    entity = SimpleNamespace(config_entry_id="source", config_subentry_id="b", platform="ids_jmk",
                             disabled_by=None, unique_id="board_departures")
    hass = SimpleNamespace(data={"ids_jmk": {"source": {"boards": {"b": board}}}})
    connection = Mock()
    connection.user.permissions.check_entity.return_value = False
    msg = {"id": 1, "type": "ids_jmk/board_visibility", "client_id": "card", "visible": True,
           "entity_ids": ["sensor.board"]}
    with patch("custom_components.ids_jmk.board_visibility.er.async_get") as registry:
        registry.return_value.async_get.return_value = entity
        visibility(hass, connection, msg)
        connection.send_error.assert_called_once()
        board.set_visible.assert_not_called()
        connection.user.permissions.check_entity.return_value = True
        visibility(hass, connection, msg)
        owner = (id(connection), "card")
        board.set_visible.assert_called_once_with(owner, True)
        board.leases[owner] = 90
        visibility(hass, connection, {**msg, "visible": False, "entity_ids": []})
        board.set_visible.assert_called_with(owner, False)


def test_switch_persists_mode_without_reloading_other_boards(tmp_path):
    from custom_components.ids_jmk import async_reload_entry, async_setup_entry, async_unload_entry
    from custom_components.ids_jmk.switch import ContinuousUpdatesSwitch

    async def run():
        hass = HomeAssistant(str(tmp_path))
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_reload = AsyncMock()
        sub = SimpleNamespace(subentry_id="b", subentry_type="board", unique_id="b", title="Board",
                              data={"stop_id": "stop", "realtime": False})
        entry = Mock(entry_id="source", title="Source", pref_disable_polling=False,
                     data={"base_url": "http://source.test", "instance_id": "source"}, subentries={"b": sub})
        with patch("custom_components.ids_jmk.async_get_clientsession"), \
             patch("custom_components.ids_jmk.Client") as client:
            client.return_value.statistics = AsyncMock(return_value={"lifetime": {}})
            client.return_value.departures = AsyncMock(return_value={"departures": []})
            await async_setup_entry(hass, entry)
            client.return_value.departures.assert_not_awaited()
            board = hass.data["ids_jmk"]["source"]["boards"]["b"]
            switch = ContinuousUpdatesSwitch(board, entry)
            switch.hass = hass
            switch.async_write_ha_state = Mock()
            assert switch.is_on is False
            assert switch.available is True

            def update(entry, subentry, *, data):
                subentry.data = data
            hass.config_entries.async_update_subentry.side_effect = update
            await switch.async_turn_on()
            await board._wake_task
            assert sub.data == {"stop_id": "stop", "realtime": False, "continuous_updates": True}
            await async_reload_entry(hass, entry)
            hass.config_entries.async_reload.assert_not_awaited()
            assert client.return_value.departures.await_count == 1
            await switch.async_turn_off()
            assert not board.active
            assert sub.data["continuous_updates"] is False
            await async_unload_entry(hass, entry)
        await hass.async_stop()
    asyncio.run(run())
