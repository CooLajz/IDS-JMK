"""One departure-board entity with structured rows in its attributes."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        StatisticsSensor(runtime["statistics"], entry, source, metric)
        for source, metrics in STATISTICS.items() for metric in metrics
    ])
    for subentry_id, coordinator in runtime["boards"].items():
        async_add_entities(
            [DeparturesSensor(coordinator, entry, entry.subentries[subentry_id])],
            config_subentry_id=subentry_id,
        )


class DeparturesSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:bus-clock"
    _attr_native_unit_of_measurement = "min"
    # Rows change frequently and are useful live, not as recorder history.
    _unrecorded_attributes = frozenset({"departures", "generated_at", "alerts", "alerts_updated_at"})

    def __init__(self, coordinator, entry, subentry):
        super().__init__(coordinator)
        self.subentry = subentry
        self._attr_unique_id = f"{subentry.unique_id}_departures"
        self._attr_name = f"IDS JMK {subentry.title}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.unique_id)}, name=subentry.title,
            manufacturer="IDS JMK", model="Odjezdová tabule",
            via_device=(DOMAIN, entry.data["instance_id"]),
        )

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_update(self):
        if self.enabled:
            await self.coordinator.async_manual_refresh()

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return next(
            (d["minutes_until"] for d in self.coordinator.data["departures"] if not d.get("cancelled")), None
        )

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        metadata = {
            "stop_id": self.subentry.data["stop_id"],
            "stop_name": self.subentry.data.get("stop_name", self.subentry.title),
            "refresh_mode": "continuous" if self.coordinator.continuous else "visible",
            "refresh_active": self.coordinator.active,
            "refresh_pending": self.coordinator.waking,
        }
        if data is None:
            return {**metadata, "departures": []}
        return {
            **metadata,
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


STATISTICS = {
    "total": ("downloads", "bytes"),
    "gtfs": ("requests", "downloads", "not_modified", "errors", "bytes"),
    "realtime": ("requests", "downloads", "not_modified", "errors", "bytes"),
    "api": ("requests", "errors", "responses_2xx", "responses_3xx", "responses_4xx", "responses_5xx"),
}


class StatisticsSensor(CoordinatorEntity, SensorEntity):
    """Server lifetime counters, suitable for recorder and Utility Meter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, entry, source, metric):
        super().__init__(coordinator)
        self.source, self.metric = source, metric
        self._attr_unique_id = f"{entry.data['instance_id']}_{source}_{metric}"
        self._attr_translation_key = f"{source}_{metric}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["instance_id"])},
            name=f"IDS JMK {entry.title}", manufacturer="IDS JMK", model="API server",
            configuration_url=entry.data["base_url"],
        )
        if metric == "bytes":
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
        else:
            self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        totals = self.coordinator.data["lifetime"]
        if self.source == "total":
            return sum(totals[source][self.metric] for source in ("gtfs", "realtime"))
        return totals[self.source][self.metric]
