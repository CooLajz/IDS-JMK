"""Persistent aggregate counters; never store client identities or query strings."""

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

from .gtfs import TZ, iso

METRICS = (
    "requests",
    "downloads",
    "not_modified",
    "errors",
    "bytes",
    "responses_2xx",
    "responses_3xx",
    "responses_4xx",
    "responses_5xx",
)
SOURCES = ("gtfs", "realtime", "api")


class Statistics:
    def __init__(self, directory):
        self.path = directory / "statistics.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sources (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            columns = ", ".join(f"{key} INTEGER NOT NULL DEFAULT 0" for key in METRICS)
            db.execute(
                "CREATE TABLE IF NOT EXISTS buckets (hour INTEGER, source TEXT, endpoint TEXT, "
                f"{columns}, PRIMARY KEY(hour,source,endpoint))"
            )
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('started_at', ?)", (iso(time.time()),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=NORMAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def source_state(self, source):
        with self.connect() as db:
            row = db.execute("SELECT value FROM sources WHERE name=?", (source,)).fetchone()
        return json.loads(row[0]) if row else {}

    def record(self, source, *, endpoint="", at=None, state=None, **values):
        at = time.time() if at is None else at
        placeholders = ",".join("?" for _ in range(3 + len(METRICS)))
        columns = ",".join(METRICS)
        assignments = ",".join(f"{key}={key}+excluded.{key}" for key in METRICS)
        with self.connect() as db:
            db.execute(
                f"INSERT INTO buckets (hour,source,endpoint,{columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(hour,source,endpoint) DO UPDATE SET {assignments}",
                (int(at // 3600) * 3600, source, endpoint, *(values.get(key, 0) for key in METRICS)),
            )
            if state is not None:
                db.execute(
                    "INSERT INTO sources VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                    (source, json.dumps(state)),
                )

    def record_api(self, endpoint, status):
        self.record(
            "api",
            endpoint=endpoint,
            requests=1,
            errors=int(status >= 400),
            **{f"responses_{status // 100}xx": 1},
        )

    def public_sources(self):
        allowed = (
            "last_checked_at",
            "last_downloaded_at",
            "last_success_at",
            "last_http_status",
            "last_result",
            "last_error",
            "last_download_bytes",
            "last_modified",
        )
        states = {source: self.source_state(source) for source in SOURCES[:2]}
        return {source: {key: state.get(key) for key in allowed} for source, state in states.items()}

    def cumulative(self):
        """Small all-time snapshot for monitoring clients; no calendar reset."""
        lifetime = {source: dict.fromkeys(METRICS, 0) for source in SOURCES}
        with self.connect() as db:
            started = db.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()[0]
            sums = ",".join(f"SUM({key}) AS {key}" for key in METRICS)
            for row in db.execute(f"SELECT source,{sums} FROM buckets GROUP BY source"):
                lifetime[row["source"]] = {key: row[key] for key in METRICS}
        return {"generated_at": iso(time.time()), "tracking_since": started, "lifetime": lifetime}

    def snapshot(self, period, anchor):
        # UTC buckets keep both repeated autumn hours distinct. Calendar grouping is Czech local time.
        if period == "day":
            start = datetime.combine(anchor, datetime.min.time(), TZ)
            end = start + timedelta(days=1)
            stamps = range(int(start.timestamp()), int(end.timestamp()), 3600)
            bins = [(iso(stamp), datetime.fromtimestamp(stamp, TZ).strftime("%H:%M %z")) for stamp in stamps]
            key_of = lambda stamp: iso(stamp)  # noqa: E731
        elif period == "month":
            start = datetime(anchor.year, anchor.month, 1, tzinfo=TZ)
            end = (start + timedelta(days=32)).replace(day=1)
            bins = [
                ((start + timedelta(days=i)).date().isoformat(), str(i + 1))
                for i in range((end - start).days)
            ]
            key_of = lambda stamp: datetime.fromtimestamp(stamp, TZ).date().isoformat()  # noqa: E731
        else:
            start, end = datetime(anchor.year, 1, 1, tzinfo=TZ), datetime(anchor.year + 1, 1, 1, tzinfo=TZ)
            bins = [(f"{anchor.year}-{month:02}", str(month)) for month in range(1, 13)]
            key_of = lambda stamp: datetime.fromtimestamp(stamp, TZ).strftime("%Y-%m")  # noqa: E731
        empty = lambda: dict.fromkeys(METRICS, 0)  # noqa: E731
        series = {
            key: {"start": key, "label": label, **{source: empty() for source in SOURCES}}
            for key, label in bins
        }
        totals = {source: empty() for source in SOURCES}
        lifetime = {source: empty() for source in SOURCES}
        endpoints = {}
        with self.connect() as db:
            started = db.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()[0]
            sums = ",".join(f"SUM({key}) AS {key}" for key in METRICS)
            for row in db.execute(f"SELECT source,{sums} FROM buckets GROUP BY source"):
                lifetime[row["source"]] = {key: row[key] for key in METRICS}
            for row in db.execute(
                "SELECT * FROM buckets WHERE hour>=? AND hour<?", (start.timestamp(), end.timestamp())
            ):
                source = row["source"]
                bucket = series[key_of(row["hour"])][source]
                for key in METRICS:
                    bucket[key] += row[key]
                    totals[source][key] += row[key]
                if source == "api":
                    target = endpoints.setdefault(row["endpoint"], {"endpoint": row["endpoint"], **empty()})
                    for key in METRICS:
                        target[key] += row[key]
        return {
            "generated_at": iso(time.time()),
            "tracking_since": started,
            "timezone": "Europe/Prague",
            "period": period,
            "date": anchor.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "sources": self.public_sources(),
            "totals": totals,
            "lifetime": lifetime,
            "series": list(series.values()),
            "api_endpoints": sorted(endpoints.values(), key=lambda r: -r["requests"]),
            "bytes_description": (
                "Bajty těla odpovědí zdroje před rozbalením HTTP komprese; bez HTTP hlaviček a TLS."
            ),
        }


class StatisticsMiddleware:
    def __init__(self, app, statistics):
        self.app, self.statistics = app, statistics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            return await self.app(scope, receive, send)
        if (b"x-ids-jmk-client", b"web") in scope.get("headers", []):
            return await self.app(scope, receive, send)
        status = 500

        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", "unmatched")
            method = scope.get("method", "OTHER")
            if method not in {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}:
                method = "OTHER"
            try:
                await asyncio.to_thread(self.statistics.record_api, f"{method} {template}", status)
            except Exception:
                logging.getLogger("ids_jmk").warning("Statistiku API se nepodařilo uložit")
