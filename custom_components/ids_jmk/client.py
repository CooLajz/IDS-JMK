"""Small client shared by the config flow and coordinator."""

from urllib.parse import quote, urlsplit

import aiohttp


class APIError(Exception):
    """Invalid or unavailable IDS JMK API."""


def normalize_url(value):
    url = urlsplit(value.strip())
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("Invalid server URL")
    return value.strip().rstrip("/")


class Client:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = normalize_url(base_url)

    async def get(self, path, params=None, *, payload=None):
        try:
            async with self.session.request(
                "GET" if payload is None else "POST",
                f"{self.base_url}/api/v1/{path}",
                params=params,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    raise APIError(f"HTTP {response.status}")
                result = await response.json()
                if not isinstance(result, dict):
                    raise APIError("Invalid response")
                return result
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise APIError("API unavailable") from exc

    async def departures(self, stop_id, options):
        params = {"limit": options.get("limit", 10), "horizon": 1440}
        for key in ("line", "direction"):
            if options.get(key):
                params[key] = options[key]
        result = await self.get(f"stops/{quote(stop_id, safe='')}/departures", params)
        if not isinstance(result.get("departures"), list) or "generated_at" not in result:
            raise APIError("Invalid departure response")
        return result
