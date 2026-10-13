"""Download scheduling with a controllable monotonic clock; no upstream traffic."""

import asyncio
from contextlib import suppress

from api.demand import RealtimeDemand


async def settle():
    for _ in range(20):
        await asyncio.sleep(0)


async def stop(task):
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def test_demand_sleeps_resumes_and_coalesces_requests():
    async def run():
        now = [1000]
        calls = []
        demand = RealtimeDemand(enabled=True, interval=60, idle_timeout=300, clock=lambda: now[0])

        async def update():
            calls.append(now[0])
            await asyncio.sleep(0)
            return True

        worker = asyncio.create_task(demand.run(update))
        try:
            await settle()
            assert not calls and demand.status == 'idle'
            await asyncio.gather(*(demand.request() for _ in range(20)))
            assert calls == [1000]
            now[0] = 1059
            await demand.request()
            assert calls == [1000]
            now[0] = 1060
            await demand.request()
            assert calls == [1000, 1060]
            now[0] = 1360  # Idle timeout wins over an overdue download.
            demand.wake.set()
            await settle()
            assert demand.status == 'idle'
            assert calls == [1000, 1060]
            now[0] = 2000
            await demand.request()
            assert calls == [1000, 1060, 2000]
        finally:
            await stop(worker)
    asyncio.run(run())


def test_periodic_refresh_and_failure_backoff_cannot_be_bypassed():
    async def run():
        now = [1000]
        calls = []
        demand = RealtimeDemand(enabled=True, interval=60, idle_timeout=300, clock=lambda: now[0])

        async def update():
            calls.append(now[0])
            return len(calls) > 2

        worker = asyncio.create_task(demand.run(update))
        try:
            await demand.request()
            assert demand.next_attempt == 1120
            now[0] = 1060
            await asyncio.gather(*(demand.request() for _ in range(10)))
            assert calls == [1000]
            now[0] = 1120
            demand.wake.set()
            await settle()
            assert calls == [1000, 1120]  # Periodic retry without another API request.
            assert demand.next_attempt == 1360
            now[0] = 1300
            await demand.request()
            assert len(calls) == 2
            now[0] = 1360
            await demand.request()
            assert demand.next_attempt == 1420 and demand.failures == 0
        finally:
            await stop(worker)
    asyncio.run(run())


def test_response_timeout_and_disconnect_do_not_cancel_shared_download():
    async def run():
        release = asyncio.Event()
        started = asyncio.Event()
        calls = []
        demand = RealtimeDemand(enabled=True, interval=60, idle_timeout=300, wait_timeout=0.01)

        async def update():
            calls.append(1)
            started.set()
            await release.wait()
            return True

        worker = asyncio.create_task(demand.run(update))
        try:
            first = asyncio.create_task(demand.request())
            await started.wait()
            first.cancel()
            with suppress(asyncio.CancelledError):
                await first
            await demand.request()  # Response deadline expires while the worker keeps running.
            assert demand.refreshing and calls == [1]
            release.set()
            await settle()
            assert not demand.refreshing and calls == [1]
            await demand.request()
            assert calls == [1]
        finally:
            await stop(worker)
    asyncio.run(run())


def test_disabled_and_always_on_modes():
    async def run():
        disabled = RealtimeDemand(enabled=False, interval=60, idle_timeout=0)
        await disabled.request()
        assert disabled.status == 'disabled' and disabled.last_demand is None
        demand = RealtimeDemand(enabled=True, interval=60, idle_timeout=0)
        calls = []

        async def update():
            calls.append(1)
            return True

        worker = asyncio.create_task(demand.run(update))
        try:
            await settle()
            assert demand.status == 'active' and calls == [1]
        finally:
            await stop(worker)
    asyncio.run(run())


def test_persisted_cooldown_blocks_demand_and_fresh_requests_do_not_wait():
    async def run():
        now = [1000]
        ready = asyncio.Event()
        calls = []
        demand = RealtimeDemand(enabled=True, interval=60, idle_timeout=300, clock=lambda: now[0],
                                cooldown=lambda: max(0, 1100 - now[0]))

        async def update():
            calls.append(now[0])
            await ready.wait()
            return True

        worker = asyncio.create_task(demand.run(update))
        try:
            # A persisted Retry-After returns cached data immediately and cannot be bypassed.
            await asyncio.wait_for(demand.request(), 0.1)
            await settle()
            assert not calls
            now[0] = 1100
            await asyncio.wait_for(demand.request(wait=False), 0.1)
            await settle()
            assert calls == [1100] and demand.refreshing
            await asyncio.wait_for(demand.request(wait=False), 0.1)
            assert calls == [1100]
            ready.set()
            await settle()
        finally:
            await stop(worker)
    asyncio.run(run())
