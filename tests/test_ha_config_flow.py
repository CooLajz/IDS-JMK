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

    from custom_components.ids_jmk.frontend import CARD_PATH, CARD_URL, async_register_card

    async def run():
        hass = SimpleNamespace(
            async_add_executor_job=AsyncMock(side_effect=lambda function: function()),
            http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        )
        with patch("custom_components.ids_jmk.frontend.add_extra_js_url") as register:
            await async_register_card(hass)
        paths = hass.http.async_register_static_paths.call_args.args[0]
        assert len(paths) == 1
        assert paths[0].url_path == CARD_URL
        assert paths[0].path == str(CARD_PATH)
        assert paths[0].cache_headers is False
        version = sha256(CARD_PATH.read_bytes()).hexdigest()[:12]
        register.assert_called_once_with(hass, f"{CARD_URL}?v={version}")

    asyncio.run(run())
