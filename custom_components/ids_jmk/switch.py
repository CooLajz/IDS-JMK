"""Persistent per-board polling mode, independent of sensor availability."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    for subentry_id, coordinator in hass.data[DOMAIN][entry.entry_id]["boards"].items():
        async_add_entities([ContinuousUpdatesSwitch(coordinator, entry)], config_subentry_id=subentry_id)


class ContinuousUpdatesSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "continuous_updates"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:autorenew"
    _attr_should_poll = False

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self.entry = entry
        subentry = coordinator.subentry
        self._attr_unique_id = f"{subentry.unique_id}_continuous_updates"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, subentry.unique_id)})

    @property
    def is_on(self):
        return self.coordinator.continuous

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.add_mode_listener(self.async_write_ha_state))

    async def _set_mode(self, value):
        subentry = self.entry.subentries[self.coordinator.subentry.subentry_id]
        self.hass.config_entries.async_update_subentry(
            self.entry, subentry, data={**subentry.data, "continuous_updates": value},
        )
        self.coordinator.set_continuous(value)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._set_mode(True)

    async def async_turn_off(self, **kwargs):
        await self._set_mode(False)
