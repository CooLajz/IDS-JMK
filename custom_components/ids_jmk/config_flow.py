"""Server -> stop search -> stop/platform -> direction and line."""

import hashlib
from urllib.parse import quote

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import APIError, Client, normalize_url
from .const import DOMAIN

# Required HA select fields reject empty strings even when an option is selected.
ALL_VALUES = "__all__"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.settings = {}
        self.stops = {}
        self.details = {}
        self.client = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                base = normalize_url(user_input["base_url"])
                self.client = Client(async_get_clientsession(self.hass), base)
                status = await self.client.get("status")
                if not status.get("ready"):
                    errors["base"] = "not_ready"
                elif not status.get("instance_id"):
                    errors["base"] = "cannot_connect"
                else:
                    self.settings = {"base_url": base, "instance_id": status["instance_id"]}
                    return await self.async_step_search()
            except ValueError:
                errors["base"] = "invalid_url"
            except APIError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required("base_url"): str}), errors=errors
        )

    async def async_step_search(self, user_input=None):
        errors = {}
        if user_input:
            try:
                result = await self.client.get("stops", {"query": user_input["query"], "limit": 50})
                self.stops = {s["id"]: s["name"] for s in result.get("stops", [])}
                if self.stops:
                    return await self.async_step_stop()
                errors["base"] = "no_stops"
            except APIError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="search", data_schema=vol.Schema({vol.Required("query"): str}), errors=errors
        )

    async def async_step_stop(self, user_input=None):
        errors = {}
        if user_input:
            try:
                stop_id = user_input["stop_id"]
                self.details = await self.client.get(f"stops/{quote(stop_id, safe='')}")
                self.settings.update(stop_id=stop_id, stop_name=self.details["name"])
                return await self.async_step_board()
            except APIError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema({vol.Required("stop_id"): vol.In(self.stops)}),
            errors=errors,
        )

    async def async_step_board(self, user_input=None):
        errors = {}
        if user_input:
            options = {k: user_input[k] for k in ("line", "direction", "limit")}
            for name in ("line", "direction"):
                if options[name] == ALL_VALUES:
                    options[name] = ""
            platform = user_input["platform"]
            stop_id = self.settings["stop_id"] if platform in ("", ALL_VALUES) else platform
            try:
                await self.client.departures(stop_id, options)
            except APIError:
                errors["base"] = "cannot_connect"
            else:
                identity = "|".join(
                    [self.settings["instance_id"], stop_id, options["line"], options["direction"]]
                )
                await self.async_set_unique_id(hashlib.sha256(identity.encode()).hexdigest())
                self._abort_if_unique_id_configured()
                title = self.settings["stop_name"]
                if options["line"]:
                    title += f" · {options['line']}"
                return self.async_create_entry(
                    title=title, data={**self.settings, "stop_id": stop_id, **options}
                )
        platforms = {
            ALL_VALUES: "Všechna stanoviště",
            **{s["id"]: s["platform"] or s["id"] for s in self.details["platforms"]},
        }
        return self.async_show_form(
            step_id="board",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("platform", default=ALL_VALUES): vol.In(platforms),
                    vol.Required("line", default=ALL_VALUES): vol.In(
                        {ALL_VALUES: "Všechny linky", **{v: v for v in self.details["lines"]}}
                    ),
                    vol.Required("direction", default=ALL_VALUES): vol.In(
                        {ALL_VALUES: "Všechny směry", **{v: v for v in self.details["directions"]}}
                    ),
                    vol.Required("limit", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "limit",
                        default=self.config_entry.options.get("limit", self.config_entry.data["limit"]),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                }
            ),
        )
