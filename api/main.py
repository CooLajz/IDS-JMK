import asyncio
import hashlib
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import datetime
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import Settings
from .downloads import SourceDownloader, source_key
from .gtfs import TZ, Timetable, iso
from .models import DepartureBoard, MapSelection
from .realtime import Realtime
from .statistics import Statistics, StatisticsMiddleware
from .vehicle_map import catalogue, map_stops, map_vehicles

LOG = logging.getLogger("ids_jmk")


def create_app(settings=None):
    settings = settings or Settings()
    timetable = Timetable(settings.data_dir.resolve())
    realtime = Realtime(settings.realtime_max_age)
    schedule_only = Realtime(settings.realtime_max_age)
    state = {"importing": False, "gtfs_last_checked": None, "gtfs_error": None, "realtime_error": None}
    id_file = timetable.directory / "instance-id"
    if not id_file.exists():
        id_file.write_text(str(uuid.uuid4()))
    instance_id = id_file.read_text().strip()

    statistics = Statistics(timetable.directory)
    downloader = SourceDownloader(statistics)
    rt_cache = timetable.directory / "realtime-cache.dat"
    rt_identity = None
    rt_state = statistics.source_state("realtime")
    if (
        settings.realtime_enabled
        and rt_cache.exists()
        and rt_state.get("url_key") == source_key(settings.realtime_url)
    ):
        try:
            data = rt_cache.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest == rt_state.get("cache_identity"):
                realtime.ingest(data)
                rt_identity = digest
        except Exception:
            LOG.warning("Uložený realtime nelze obnovit; bude stažen znovu")
    state["gtfs_last_checked"] = statistics.source_state("gtfs").get("last_checked_at")

    async def accept_static(target):
        state["importing"] = True
        try:
            await asyncio.to_thread(timetable.import_zip, target)
            return timetable.metadata()["sha256"]
        finally:
            state["importing"] = False

    async def accept_realtime(target):
        nonlocal rt_identity
        data = target.read_bytes()
        candidate = Realtime(settings.realtime_max_age)
        candidate.snapshot = realtime.snapshot
        candidate.ingest(data)
        target.replace(rt_cache)
        realtime.snapshot = candidate.snapshot
        rt_identity = hashlib.sha256(data).hexdigest()
        return rt_identity

    async def static_loop(client):
        while True:
            try:
                await downloader.update(
                    client,
                    "gtfs",
                    settings.gtfs_url,
                    timetable.directory / "gtfs-download.tmp",
                    100 * 1024 * 1024,
                    lambda: timetable.metadata().get("sha256"),
                    accept_static,
                )
                state.update(gtfs_last_checked=iso(time.time()), gtfs_error=None)
            except Exception as exc:
                state["gtfs_error"] = type(exc).__name__
                LOG.warning("Import GTFS selhal: %s", type(exc).__name__)
            await asyncio.sleep(settings.gtfs_interval if not state["gtfs_error"] else 60)

    async def realtime_loop(client):
        while True:
            try:
                await downloader.update(
                    client,
                    "realtime",
                    settings.realtime_url,
                    timetable.directory / "rt-download.tmp",
                    20 * 1024 * 1024,
                    lambda: rt_identity,
                    accept_realtime,
                )
                state["realtime_error"] = None
            except Exception as exc:
                state["realtime_error"] = type(exc).__name__
                LOG.warning("Aktualizace realtime selhala: %s", type(exc).__name__)
            await asyncio.sleep(settings.realtime_interval)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "IDS-JMK/0.1 (github.com/CooLajz/IDS-JMK)"},
        ) as client:
            tasks = (
                [
                    asyncio.create_task(f(client))
                    for f in ((static_loop, realtime_loop) if settings.realtime_enabled else (static_loop,))
                ]
                if settings.download_enabled
                else []
            )
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        title="IDS JMK API",
        version="0.1.5",
        lifespan=lifespan,
        description="Odjezdy a polohy vozidel. Vlastní odhady jsou označeny vehicle_estimate.",
    )
    app.add_middleware(StatisticsMiddleware, statistics=statistics)
    app.state.statistics = statistics
    app.state.timetable = timetable
    app.state.realtime = realtime

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Zastávka nebo spoj neexistuje"})

    def ready():
        if not timetable.ready:
            raise HTTPException(
                503, "Jízdní řády se připravují. Zkuste to za chvíli.", headers={"Retry-After": "30"}
            )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness():
        ready()
        return {"status": "ready"}

    def source_status():
        sources = statistics.public_sources()
        for name, enabled, interval in (
            ("gtfs", settings.download_enabled, settings.gtfs_interval),
            ("realtime", settings.download_enabled and settings.realtime_enabled, settings.realtime_interval),
        ):
            sources[name].update(enabled=enabled, interval_seconds=interval)
        return sources

    @app.get("/api/v1/statistics/cumulative")
    def cumulative_statistics():
        return {**statistics.cumulative(), "instance_id": instance_id}

    @app.get("/api/v1/statistics")
    def statistics_view(
        period: Literal["day", "month", "year"] = "day",
        date: Date | None = Query(None, description="Datum ve zvoleném období, časové pásmo Europe/Prague."),
    ):
        anchor = date or datetime.now(TZ).date()
        if not 2000 <= anchor.year <= 2099:
            raise HTTPException(422, "Datum musí být v letech 2000–2099")
        result = statistics.snapshot(period, anchor)
        result["sources"] = source_status()
        return result

    @app.get("/api/v1/status")
    def status():
        meta = timetable.metadata()
        valid_to = meta.get("valid_to")
        return {
            "version": app.version,
            "instance_id": instance_id,
            "ready": timetable.ready,
            **state,
            "schedule": meta,
            "downloads": source_status(),
            "schedule_expired": bool(valid_to and valid_to < datetime.now(TZ).strftime("%Y%m%d")),
            "realtime": {
                "enabled": True,
                "updated_at": iso(realtime.snapshot.timestamp) if realtime.snapshot.timestamp else None,
                "stale": not realtime.fresh(realtime.snapshot.timestamp, time.time()),
                "vehicles": len(realtime.snapshot.vehicles),
                "trip_updates": len(realtime.snapshot.updates),
            }
            if settings.realtime_enabled
            else {"enabled": False},
        }

    @app.get("/api/v1/stops")
    def stops(query: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=100)):
        ready()
        return {"stops": timetable.search(query.strip(), limit)}

    @app.get("/api/v1/stops/{stop_id}")
    def stop_detail(stop_id: str):
        ready()
        return timetable.detail(stop_id)

    @app.get(
        "/api/v1/stops/{stop_id}/departures", response_model=DepartureBoard, response_model_exclude_unset=True
    )
    def departures(
        stop_id: str,
        limit: int = Query(10, ge=1, le=100),
        horizon: int = Query(1440, ge=1, le=2880),
        line: str | None = Query(None, max_length=50),
        direction: str | None = Query(None, max_length=200),
        previous_limit: int = Query(
            0,
            ge=0,
            le=10,
            description="Počet minulých odjezdů za posledních 24 hodin v poli previous_departures.",
        ),
    ):
        ready()
        result = timetable.departures(
            stop_id,
            realtime if settings.realtime_enabled else schedule_only,
            datetime.now(TZ),
            limit,
            horizon,
            line,
            direction,
            previous_limit,
        )
        result["realtime_enabled"] = settings.realtime_enabled
        if settings.realtime_enabled:
            result.update(timetable.board_alerts(stop_id, realtime, datetime.now(TZ), line, direction))
            result["realtime_stale"] = not realtime.fresh(realtime.snapshot.timestamp, time.time())
        else:
            for row in result["departures"] + result["previous_departures"]:
                for key in (
                    "estimated_departure",
                    "delay_seconds",
                    "realtime_updated_at",
                    "cancelled",
                    "vehicle_id",
                    "has_vehicle_position",
                ):
                    row.pop(key, None)
        return result

    @app.get("/api/v1/trips/{trip_id}")
    def trip(trip_id: str, service_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
        ready()
        try:
            day = datetime.strptime(service_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "Neplatné datum") from None
        result = timetable.trip(trip_id, day)
        result["realtime_enabled"] = settings.realtime_enabled
        if settings.realtime_enabled:
            result["vehicles"] = (
                realtime.trip_vehicles(trip_id, result["stops"], day, time.time()) if result["active"] else []
            )
        return result

    @app.get("/api/v1/map/routes")
    def map_routes():
        ready()
        return catalogue(timetable)

    @app.post("/api/v1/map/stops")
    def selected_stops(selections: list[MapSelection]):
        ready()
        if len(selections) > 20:
            raise HTTPException(422, "Vyberte nejvýše 20 linek.")
        return map_stops(timetable, selections)

    @app.post("/api/v1/map/vehicles")
    def selected_vehicles(selections: list[MapSelection]):
        ready()
        if len(selections) > 20:
            raise HTTPException(422, "Vyberte nejvýše 20 linek.")
        return map_vehicles(timetable, realtime, selections, settings.realtime_enabled)

    @app.get("/api/v1/vehicles")
    def vehicles(trip_id: str | None = None):
        ready()
        if not settings.realtime_enabled:
            return {"realtime_enabled": False, "vehicles": []}
        ids = {key[0] for key in realtime.snapshot.vehicles if not trip_id or key[0] == trip_id}
        with timetable.connect() as db:
            positions = {key: timetable.trip_stops(db, key) for key in ids}
        return {"vehicles": realtime.vehicle_list(trip_id, stops_by_trip=positions)}

    return app


app = create_app()
