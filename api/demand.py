"""One realtime downloader, awake only while clients need its data.

All mutations run on the application's asyncio event loop. Request cancellation
or a short response deadline never cancels the shared download.
"""

import asyncio
import time


class RealtimeDemand:
    def __init__(self, *, enabled, interval, idle_timeout, wait_timeout=3, clock=time.monotonic):
        self.clock = clock
        self.enabled = enabled
        self.interval = interval
        self.idle_timeout = idle_timeout
        self.wait_timeout = wait_timeout
        self.last_demand = None
        self.last_requested_at = None
        self.next_attempt = 0
        self.refreshing = False
        self.failures = 0
        self.wake = asyncio.Event()
        self.finished = asyncio.Event()

    @property
    def active(self):
        return self.enabled and (
            self.idle_timeout == 0
            or self.last_demand is not None and self.clock() < self.last_demand + self.idle_timeout
        )

    @property
    def status(self):
        if not self.enabled:
            return "disabled"
        if self.refreshing:
            return "refreshing"
        return "active" if self.active else "idle"

    async def request(self):
        if not self.enabled:
            return
        self.last_demand = self.clock()
        self.last_requested_at = time.time()
        wait = self.refreshing or self.last_demand >= self.next_attempt
        if wait:
            self.finished.clear()
        self.wake.set()
        if wait:
            try:
                await asyncio.wait_for(self.finished.wait(), timeout=self.wait_timeout)
            except TimeoutError:
                pass

    async def run(self, update):
        while True:
            self.wake.clear()
            if not self.active:
                await self.wake.wait()
                continue
            delay = self.next_attempt - self.clock()
            if delay > 0:
                if self.idle_timeout:
                    delay = min(delay, self.last_demand + self.idle_timeout - self.clock())
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=max(0, delay))
                except TimeoutError:
                    pass
                continue
            self.refreshing = True
            self.finished.clear()
            try:
                success = await update()
                self.failures = 0 if success else min(self.failures + 1, 8)
                # New requests cannot bypass the shared retry cooldown.
                cooldown = min(self.interval * 2 ** self.failures, max(self.interval, 900))
                self.next_attempt = self.clock() + cooldown
            finally:
                self.refreshing = False
                self.finished.set()
