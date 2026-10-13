"""Conditional source downloads; validators are tied to successfully accepted local data."""

import asyncio
import hashlib
import math
import time
from email.utils import parsedate_to_datetime

from .gtfs import iso


def source_key(url):
    return hashlib.sha256(url.encode()).hexdigest()


def retry_after(value, now):
    """Parse either delay-seconds or an HTTP date; ignore malformed hints."""
    if not value:
        return 0
    try:
        delay = int(value) if value.strip().isdigit() else parsedate_to_datetime(value).timestamp() - now
        if not math.isfinite(delay):
            return 0
        delay = max(0, delay)
        iso(now + delay)  # Reject deadlines outside the representable API timestamp range.
        return delay
    except (ValueError, TypeError, OverflowError, OSError):
        return 0


class SourceDownloader:
    def __init__(self, statistics):
        self.statistics = statistics
        self.states = {}

    def remaining(self, source, url, identity):
        state = self.states.get(source)
        if state is None:
            state = self.statistics.source_state(source)
            self.states[source] = state
        if state.get("url_key") != source_key(url):
            return 0
        # A lost cache must be fetched again, but never bypass a failure cooldown.
        if not state.get("last_error") and (not identity or identity != state.get("cache_identity")):
            return 0
        return max(0, state.get("next_check_at", 0) - time.time())

    async def update(self, client, source, url, target, maximum, cache_identity, accept, *, interval=0):
        previous = self.statistics.source_state(source)
        same_source = previous.get("url_key") == source_key(url)
        state = dict(previous) if same_source else {}
        headers = {}
        identity = cache_identity()
        if same_source and identity and identity == previous.get("cache_identity"):
            if previous.get("etag"):
                headers["If-None-Match"] = previous["etag"]
            if previous.get("last_modified"):
                headers["If-Modified-Since"] = previous["last_modified"]
        response = None
        downloaded = False
        unchanged = False
        error = None
        try:
            # Avoid intermediary reuse of a fresh-looking but old realtime response.
            async with client.stream(
                "GET", url, headers={"Cache-Control": "no-cache", **headers}
            ) as response:
                state["last_http_status"] = response.status_code
                if response.status_code == 304:
                    if not headers:
                        raise ValueError("Odpověď 304 bez platné lokální kopie")
                    unchanged = True
                else:
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError("Zdroj nevrátil celý soubor")
                    total = 0
                    with target.open("wb") as out:
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > maximum:
                                raise ValueError("Stažený soubor je příliš velký")
                            out.write(chunk)
                    downloaded = True
                    state["last_downloaded_at"] = iso(time.time())
                    state["last_download_bytes"] = response.num_bytes_downloaded
                    # Do not commit validators until import/parsing and persistent cache succeed.
                    identity = await accept(target)
                state.update(
                    url_key=source_key(url),
                    cache_identity=identity,
                    etag=response.headers.get("etag", previous.get("etag") if unchanged else None),
                    last_modified=response.headers.get(
                        "last-modified", previous.get("last_modified") if unchanged else None
                    ),
                    last_success_at=iso(time.time()),
                )
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            stamp = time.time()
            failures = min(state.get("consecutive_errors", 0) + 1, 16) if error else 0
            # Large static archives must not be retried every minute throughout an outage.
            delay = min((60 if source == "gtfs" else max(15, interval)) *
                        2 ** (failures - 1 if source == "gtfs" else failures),
                        3600 if source == "gtfs" else max(interval, 900)) if error else interval
            if response is not None and response.status_code in (429, 503):
                delay = max(delay, retry_after(response.headers.get("retry-after"), stamp))
            state.update(
                url_key=source_key(url),
                consecutive_errors=failures,
                next_check_at=stamp + delay,
                last_checked_at=iso(stamp),
                last_error=error,
                last_http_status=response.status_code if response is not None else None,
                last_result="error" if error else "not_modified" if unchanged else "downloaded",
            )
            self.states[source] = state
            try:
                await asyncio.to_thread(
                    self.statistics.record,
                    source,
                    at=stamp,
                    state=state,
                    requests=1,
                    downloads=int(downloaded),
                    not_modified=int(unchanged),
                    errors=int(error is not None),
                    bytes=response.num_bytes_downloaded if response is not None else 0,
                )
            finally:
                target.unlink(missing_ok=True)
        return not unchanged
