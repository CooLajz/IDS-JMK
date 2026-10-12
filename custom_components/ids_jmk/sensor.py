"""One departure-board entity with structured rows in its attributes."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([DeparturesSensor(hass.data[DOMAIN][entry.entry_id], entry)])


class DeparturesSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:bus-clock"
    _attr_native_unit_of_measurement = "min"
    # Rows change frequently and are useful live, not as recorder history.
    _unrecorded_attributes = frozenset({"departures", "generated_at", "alerts", "alerts_updated_at"})

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_departures"
        self._attr_name = f"IDS JMK {entry.title}"

    @property
    def native_value(self):
        return next(
            (d["minutes_until"] for d in self.coordinator.data["departures"] if not d.get("cancelled")), None
        )

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return {
            "departures": data["departures"],
            "realtime_enabled": data.get("realtime_enabled", True),
            "alerts": data.get("alerts", []),
            "alerts_supported": "alerts" in data,
            "alerts_stale": data.get("alerts_stale", True),
            "alerts_updated_at": data.get("alerts_updated_at"),
            "generated_at": data["generated_at"],
            "stop_id": data["stop"]["id"],
            "stop_name": data["stop"]["name"],
            "realtime_stale": data.get("realtime_stale", True),
        }
