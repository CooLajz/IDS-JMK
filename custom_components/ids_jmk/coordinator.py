"""Board polling controlled by an explicit mode and expiring card leases."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import APIError

LOGGER = logging.getLogger(__name__)
LEASE_SECONDS = 90


class BoardCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, subentry, client):
        self.subentry = subentry
        self.client = client
        self.continuous = subentry.data.get("continuous_updates", False)
        self.leases = {}
        self._lease_timer = None
        self._wake_task = None
        self._fetch_task = None
        self._manual = 0
        self._mode_listeners = set()
        super().__init__(
            hass, LOGGER, name=subentry.title, config_entry=entry,
            update_interval=timedelta(seconds=30) if self.continuous else None,
        )

    @property
    def active(self):
        return not self.config_entry.pref_disable_polling and (
            self.continuous or any(deadline > self.hass.loop.time() for deadline in self.leases.values())
        )

    @property
    def waking(self):
        return self._wake_task is not None

    def add_mode_listener(self, listener):
        self._mode_listeners.add(listener)
        return lambda: self._mode_listeners.discard(listener)

    def set_continuous(self, value):
        self.continuous = value
        self._sync_activity()
        for listener in tuple(self._mode_listeners):
            listener()

    def set_visible(self, owner, visible):
        if visible:
            self.leases[owner] = self.hass.loop.time() + LEASE_SECONDS
        else:
            self.leases.pop(owner, None)
        self._expire_leases()

    def _expire_leases(self):
        if self._lease_timer:
            self._lease_timer.cancel()
            self._lease_timer = None
        now = self.hass.loop.time()
        self.leases = {key: deadline for key, deadline in self.leases.items() if deadline > now}
        if self.leases:
            self._lease_timer = self.hass.loop.call_at(min(self.leases.values()), self._expire_leases)
        self._sync_activity()

    def _sync_activity(self):
        was_active = self.update_interval is not None
        active = self.active
        self.update_interval = timedelta(seconds=30) if active else None
        if not active:
            self._unschedule_refresh()
        elif not was_active and self._wake_task is None:
            self._wake_task = self.hass.async_create_task(self._wake_refresh(), eager_start=False)
        self.async_update_listeners()

    async def _wake_refresh(self):
        try:
            await self.async_refresh()
        finally:
            self._wake_task = None
            self.async_update_listeners()

    async def _fetch(self):
        try:
            return await self.client.departures(self.subentry.data["stop_id"], self.subentry.data)
        except APIError as exc:
            raise UpdateFailed("IDS JMK API není dostupné") from exc

    async def _async_update_data(self):
        # A queued refresh may run just after the last card disappeared.
        if not self.active and not self._manual:
            return self.data
        if self._fetch_task is None:
            self._fetch_task = self.hass.async_create_task(self._fetch(), eager_start=False)
        task = self._fetch_task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done() and self._fetch_task is task:
                self._fetch_task = None

    async def async_manual_refresh(self):
        self._manual += 1
        try:
            await self.async_refresh()
        finally:
            self._manual -= 1

    async def async_shutdown(self):
        if self._lease_timer:
            self._lease_timer.cancel()
            self._lease_timer = None
        self.leases.clear()
        await super().async_shutdown()
        tasks = [task for task in (self._wake_task, self._fetch_task) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
