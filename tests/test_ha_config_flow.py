"""HA-specific regressions (run with Home Assistant installed)."""

import asyncio
from itertools import product
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")
from custom_components.ids_jmk.config_flow import ALL_VALUES, BoardSubentryFlow, ConfigFlow  # noqa: E402


@pytest.mark.parametrize("realtime", [False, True])
def test_all_filter_combinations(realtime):
    async def run():
        for platform, line, direction in product([ALL_VALUES, "U15118Z2"], [ALL_VALUES, "501"],
                                                 [ALL_VALUES, "Nebovidy, dolní konec"]):
            flow = BoardSubentryFlow()
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
                if str(field) in ("platform", "line", "direction"):
                    assert "" not in validator.container
            data = schema({"platform": platform, "line": line, "direction": direction,
                           "limit": 10, "realtime": realtime})
            with patch.object(flow, "_get_entry", return_value=SimpleNamespace(subentries={})):
                result = await flow.async_step_board(data)
            assert result["type"] == "create_entry"
            stored = result["data"]
            assert stored["stop_id"] == ("U15118N1858" if platform == ALL_VALUES else platform)
            assert stored["realtime"] is realtime
            assert stored["line"] == ("" if line == ALL_VALUES else line)
            assert stored["direction"] == ("" if direction == ALL_VALUES else direction)
            flow.client.departures.assert_awaited_once_with(
                stored["stop_id"], {name: stored[name] for name in ("line", "direction", "limit", "realtime")}
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
            msg['action'] = 'stops'
            await handler(hass, connection, msg)
            client.return_value.get.assert_awaited_once_with('map/stops', payload=msg['selections'])
            client.return_value.get.reset_mock()
            entry.domain = 'other'
            await handler(hass, connection, msg)
            client.return_value.get.assert_not_awaited()
            connection.send_error.assert_called_once()

    asyncio.run(run())


def test_source_flow_creates_source_without_board_and_rejects_duplicate():
    async def run():
        flow = ConfigFlow()
        flow.context = {"source": "user"}
        flow.hass = Mock()
        with patch('custom_components.ids_jmk.config_flow.async_get_clientsession'), \
             patch('custom_components.ids_jmk.config_flow.Client') as client, \
             patch.object(flow, 'async_set_unique_id', new=AsyncMock()) as unique, \
             patch.object(flow, '_abort_if_unique_id_configured') as duplicate:
            client.return_value.get = AsyncMock(return_value={'ready': True, 'instance_id': 'server-a'})
            result = await flow.async_step_user({'base_url': 'http://example.test/'})
            assert result['data'] == {'base_url': 'http://example.test', 'instance_id': 'server-a'}
            unique.assert_awaited_once_with('server-a')
            duplicate.assert_called_once()
            client.return_value.get.assert_awaited_once_with('status')
        assert flow.async_get_supported_subentry_types(None) == {'board': BoardSubentryFlow}
    asyncio.run(run())


def test_board_uses_parent_url_and_duplicate_is_rejected():
    async def run():
        entry = SimpleNamespace(
            data={'base_url': 'http://source.test', 'instance_id': 'source'}, subentries={},
        )
        flow = BoardSubentryFlow()
        flow.context = {'source': 'user'}
        flow.hass = Mock()
        with patch.object(flow, '_get_entry', return_value=entry), \
             patch('custom_components.ids_jmk.config_flow.async_get_clientsession'), \
             patch('custom_components.ids_jmk.config_flow.Client') as client:
            form = await flow.async_step_user()
            assert form['step_id'] == 'search'
            assert 'base_url' not in {str(key) for key in form['data_schema'].schema}
            assert client.call_args.args[1] == 'http://source.test'
            flow.settings.update(stop_id='stop', stop_name='Stop')
            flow.client.departures = AsyncMock()
            data = {'line': ALL_VALUES, 'direction': ALL_VALUES, 'platform': ALL_VALUES, 'limit': 10}
            first = await flow.async_step_board(data)
            entry.subentries['board'] = SimpleNamespace(unique_id=first['unique_id'])
            second = await flow.async_step_board(data)
            assert second['reason'] == 'already_configured'
    asyncio.run(run())


def test_statistics_entities_use_lifetime_and_remain_unavailable_on_failure():
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.const import UnitOfInformation

    from custom_components.ids_jmk.sensor import StatisticsSensor

    coordinator = Mock(data={'lifetime': {'gtfs': {'bytes': 123}, 'realtime': {'bytes': 456}}},
                       last_update_success=True)
    entry = SimpleNamespace(data={'instance_id': 'server', 'base_url': 'http://source.test'}, title='Source')
    sensor = StatisticsSensor(coordinator, entry, 'total', 'bytes')
    assert sensor.native_value == 579
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor.device_class == SensorDeviceClass.DATA_SIZE
    assert sensor.native_unit_of_measurement == UnitOfInformation.BYTES
    coordinator.last_update_success = False
    assert sensor.available is False
    # Failed polling never substitutes zero, which would manufacture a meter reset.
    assert sensor.native_value == 579
    coordinator.data = None
    assert sensor.native_value is None


def test_source_setup_isolates_failed_boards_and_statistics(tmp_path):
    from homeassistant.core import HomeAssistant

    from custom_components.ids_jmk import async_setup_entry, async_unload_entry
    from custom_components.ids_jmk.client import APIError
    from custom_components.ids_jmk.sensor import async_setup_entry as setup_sensors

    async def run():
        hass = HomeAssistant(str(tmp_path))
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        boards = {
            key: SimpleNamespace(subentry_id=key, subentry_type='board', unique_id=key,
                                 title=key, data={'stop_id': key})
            for key in ('good', 'bad')
        }
        entry = Mock(entry_id='source', data={'base_url': 'http://source.test', 'instance_id': 'source'},
                     subentries=boards, title='Source', pref_disable_polling=False)

        async def departures(stop, options):
            if stop == 'bad':
                raise APIError('Unavailable')
            return {'departures': [], 'generated_at': 'now'}

        with patch('custom_components.ids_jmk.async_get_clientsession'), \
             patch('custom_components.ids_jmk.Client') as client:
            client.return_value.statistics = AsyncMock(side_effect=APIError('Old API'))
            client.return_value.departures = AsyncMock(side_effect=departures)
            assert await async_setup_entry(hass, entry)
            runtime = hass.data['ids_jmk']['source']
            assert runtime['statistics'].last_update_success is False
            assert runtime['boards']['good'].last_update_success is True
            assert runtime['boards']['bad'].last_update_success is False
            client.return_value.statistics.assert_awaited_once()
            assert client.return_value.departures.await_count == 2
            assert runtime['statistics'].update_interval.total_seconds() == 60
            assert runtime['boards']['good'].update_interval.total_seconds() == 30
            add = Mock()
            await setup_sensors(hass, entry, add)
            assert len(add.call_args_list[0].args[0]) == 18
            assert add.call_args_list[1].kwargs == {'config_subentry_id': 'good'}
            assert add.call_args_list[2].kwargs == {'config_subentry_id': 'bad'}
            unavailable_board = add.call_args_list[2].args[0][0]
            assert unavailable_board.available is False
            assert unavailable_board.native_value is None
            assert unavailable_board.extra_state_attributes == {}
            client.return_value.statistics.side_effect = None
            client.return_value.statistics.return_value = {'lifetime': {}}
            await runtime['statistics'].async_refresh()
            assert runtime['statistics'].last_update_success is True
            assert await async_unload_entry(hass, entry)
            assert 'source' not in hass.data['ids_jmk']
        await hass.async_stop()
    asyncio.run(run())


def test_subentry_reconfigure_updates_limit_without_changing_identity():
    async def run():
        flow = BoardSubentryFlow()
        flow.context = {'source': 'reconfigure'}
        entry = Mock()
        board = SimpleNamespace(data={'limit': 10})
        with patch.object(flow, '_get_entry', return_value=entry), \
             patch.object(flow, '_get_reconfigure_subentry', return_value=board), \
             patch.object(flow, 'async_update_and_abort', return_value={'type': 'abort'}) as update:
            form = await flow.async_step_reconfigure()
            assert form['data_schema']({}) == {'limit': 10, 'realtime': True}
            await flow.async_step_reconfigure({'limit': 25, 'realtime': False})
            update.assert_called_once_with(entry, board, data_updates={'limit': 25, 'realtime': False})
    asyncio.run(run())


def test_statistics_client_rejects_missing_negative_or_boolean_counters():
    from custom_components.ids_jmk.client import APIError, Client

    async def run():
        client = Client(Mock(), 'http://source.test')
        metrics = ('requests', 'downloads', 'not_modified', 'errors', 'bytes',
                   'responses_2xx', 'responses_3xx', 'responses_4xx', 'responses_5xx')
        valid = {'lifetime': {source: dict.fromkeys(metrics, 0) for source in ('gtfs', 'realtime', 'api')}}
        with patch.object(client, 'get', new=AsyncMock(return_value=valid)):
            assert await client.statistics() == valid
            for bad in (-1, True, None, '100'):
                valid['lifetime']['gtfs']['bytes'] = bad
                with pytest.raises(APIError):
                    await client.statistics()
    asyncio.run(run())


def test_departures_client_sends_explicit_realtime_preference():
    from custom_components.ids_jmk.client import Client

    async def run():
        client = Client(Mock(), 'http://source.test')
        with patch.object(client, 'get', new=AsyncMock(return_value={
            'departures': [], 'generated_at': 'now',
        })) as get:
            for options, expected in (({}, 'true'), ({'realtime': True}, 'true'),
                                      ({'realtime': False}, 'false')):
                await client.departures('P', options)
                assert get.call_args.args[1]['realtime'] == expected
    asyncio.run(run())
