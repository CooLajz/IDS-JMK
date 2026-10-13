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
    VERSION = 2

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
                if not isinstance(status.get("instance_id"), str) or not status["instance_id"]:
                    errors["base"] = "cannot_connect"
                else:
                    self.settings = {"base_url": base, "instance_id": status["instance_id"]}
                    await self.async_set_unique_id(status["instance_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=base, data=self.settings)
            except ValueError:
                errors["base"] = "invalid_url"
            except APIError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required("base_url"): str}), errors=errors
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        return {"board": BoardSubentryFlow}

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input:
            try:
                base = normalize_url(user_input["base_url"])
                status = await Client(async_get_clientsession(self.hass), base).get("status")
                if status.get("instance_id") != entry.data["instance_id"]:
                    errors["base"] = "wrong_source"
                else:
                    return self.async_update_and_abort(entry, data_updates={"base_url": base})
            except ValueError:
                errors["base"] = "invalid_url"
            except APIError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reconfigure", errors=errors, data_schema=vol.Schema({
            vol.Required("base_url", default=entry.data["base_url"]): str,
        }))


class BoardSubentryFlow(config_entries.ConfigSubentryFlow):
    def __init__(self):
        self.settings = {}
        self.stops = {}
        self.details = {}
        self.client = None

    async def async_step_user(self, user_input=None):
        self.settings = dict(self._get_entry().data)
        self.client = Client(async_get_clientsession(self.hass), self.settings["base_url"])
        return await self.async_step_search(user_input)

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
            options["realtime"] = user_input.get("realtime", True)
            for name in ("line", "direction"):
                if options[name] == ALL_VALUES:
                    options[name] = ""
            platform = user_input["platform"]
            stop_id = self.settings["stop_id"] if platform in ("", ALL_VALUES) else platform
            try:
                await self.client.departures(stop_id, {**options, "realtime": False})
            except APIError:
                errors["base"] = "cannot_connect"
            else:
                identity = "|".join(
                    [self.settings["instance_id"], stop_id, options["line"], options["direction"]]
                )
                unique_id = hashlib.sha256(identity.encode()).hexdigest()
                if any(s.unique_id == unique_id for s in self._get_entry().subentries.values()):
                    return self.async_abort(reason="already_configured")
                title = self.settings["stop_name"]
                if options["line"]:
                    title += f" · {options['line']}"
                return self.async_create_entry(
                    title=title, unique_id=unique_id,
                    data={"stop_name": self.settings["stop_name"], "stop_id": stop_id, **options}
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
                    vol.Required("realtime", default=True): bool,
                    vol.Required("limit", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                }
            ),
        )

    async def async_step_reconfigure(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        if user_input:
            return self.async_update_and_abort(
                self._get_entry(), subentry, data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required("realtime", default=subentry.data.get("realtime", True)): bool,
                vol.Required("limit", default=subentry.data.get("limit", 10)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            }),
        )
