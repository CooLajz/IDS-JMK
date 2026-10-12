"""HA-specific regressions (run with Home Assistant installed)."""

import asyncio
from itertools import product
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
from custom_components.ids_jmk.config_flow import ALL_VALUES, ConfigFlow  # noqa: E402


def test_all_filter_combinations():
    async def run():
        for platform, line, direction in product([ALL_VALUES, "U15118Z2"], [ALL_VALUES, "501"],
                                                 [ALL_VALUES, "Nebovidy, dolní konec"]):
            flow = ConfigFlow()
            flow.context = {"source": "user"}
            flow.settings = {"stop_id": "U15118N1858", "stop_name": "Nebovidy, kostel",
                             "instance_id": "test", "base_url": "http://example.test"}
            flow.details = {"platforms": [{"id": "U15118Z2", "platform": "2"}],
                            "lines": ["501"], "directions": ["Nebovidy, dolní konec"]}
            flow.client = AsyncMock()
            form = await flow.async_step_board()
            schema = form["data_schema"]
            # HA frontend rejects empty required select values, even if labelled "all".
            defaults = schema({})
            assert all(defaults[name] for name in ("platform", "line", "direction"))
            for field, validator in schema.schema.items():
                if str(field) != "limit":
                    assert "" not in validator.container
            data = schema({"platform": platform, "line": line, "direction": direction, "limit": 10})
            with patch.object(flow, "async_set_unique_id", new=AsyncMock()), \
                    patch.object(flow, "_abort_if_unique_id_configured"):
                result = await flow.async_step_board(data)
            assert result["type"] == "create_entry"
            stored = result["data"]
            assert stored["stop_id"] == ("U15118N1858" if platform == ALL_VALUES else platform)
            assert stored["line"] == ("" if line == ALL_VALUES else line)
            assert stored["direction"] == ("" if direction == ALL_VALUES else direction)
            flow.client.departures.assert_awaited_once_with(
                stored["stop_id"], {name: stored[name] for name in ("line", "direction", "limit")}
            )
            assert ALL_VALUES not in stored.values()
    asyncio.run(run())


def test_card_registration_uses_content_version():
    from hashlib import sha256
    from types import SimpleNamespace

    from custom_components.ids_jmk.frontend import CARD_PATH, async_register_card

    async def run():
        hass = SimpleNamespace(
            async_add_executor_job=AsyncMock(side_effect=lambda function: function()),
            http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        )
        with patch("custom_components.ids_jmk.frontend.add_extra_js_url") as register:
            await async_register_card(hass)
        assert hass.http.async_register_static_paths.call_count == 4
        for call, name in zip(hass.http.async_register_static_paths.call_args_list[:3],
                              ("ids-jmk-departures-card.js", "ids-jmk-alerts-card.js", "ids-jmk-map-card.js"),
                              strict=True):
            path = CARD_PATH.with_name(name)
            url = f"/ids_jmk/{name}"
            paths = call.args[0]
            assert len(paths) == 1
            assert paths[0].url_path == url
            assert paths[0].path == str(path)
            assert paths[0].cache_headers is False
            version = sha256(path.read_bytes()).hexdigest()[:12]
            register.assert_any_call(hass, f"{url}?v={version}")
        assert register.call_count == 3

    asyncio.run(run())


def test_map_bridge_uses_entry_and_fixed_paths():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from custom_components.ids_jmk.vehicle_map import request

    async def run():
        entry = SimpleNamespace(entry_id='source', domain='ids_jmk', data={'base_url': 'http://api.test'})
        hass = SimpleNamespace(data={'ids_jmk': {'source': object()}},
                               config_entries=SimpleNamespace(async_get_entry=Mock(return_value=entry)))
        connection = Mock()
        handler = request.__wrapped__
        msg = {'id': 1, 'entry_id': 'source', 'action': 'vehicles',
               'selections': [{'route_id': 'R', 'direction': '*'}]}
        with patch('custom_components.ids_jmk.vehicle_map.async_get_clientsession'), \
             patch('custom_components.ids_jmk.vehicle_map.Client') as client:
            client.return_value.get = AsyncMock(return_value={'vehicles': []})
            await handler(hass, connection, msg)
            client.return_value.get.assert_awaited_once_with('map/vehicles', payload=msg['selections'])
            connection.send_result.assert_called_once_with(1, {'vehicles': []})
            client.return_value.get.reset_mock()
            entry.domain = 'other'
            await handler(hass, connection, msg)
            client.return_value.get.assert_not_awaited()
            connection.send_error.assert_called_once()

    asyncio.run(run())
