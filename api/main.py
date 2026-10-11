import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import Settings
from .gtfs import TZ, Timetable, iso
from .models import DepartureBoard
from .realtime import Realtime

LOG = logging.getLogger("ids_jmk")


def create_app(settings=None):
    settings = settings or Settings()
    timetable = Timetable(settings.data_dir.resolve())
    realtime = Realtime(settings.realtime_max_age)
    state = {"importing": False, "gtfs_last_checked": None, "gtfs_error": None, "realtime_error": None}
    id_file = timetable.directory / "instance-id"
    if not id_file.exists():
        id_file.write_text(str(uuid.uuid4()))
    instance_id = id_file.read_text().strip()

    async def download(client, url, path, maximum):
        total = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with path.open("wb") as out:
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > maximum:
                        raise ValueError("Stažený soubor je příliš velký")
                    out.write(chunk)

    async def static_loop(client):
        while True:
            target = timetable.directory / "gtfs-download.tmp"
            try:
                state["importing"] = True
                await download(client, settings.gtfs_url, target, 100 * 1024 * 1024)
                await asyncio.to_thread(timetable.import_zip, target)
                state.update(gtfs_last_checked=iso(time.time()), gtfs_error=None)
            except Exception as exc:
                # URL credentials and response bodies must not leak into logs or public status.
                state["gtfs_error"] = type(exc).__name__
                LOG.warning("Import GTFS selhal: %s", type(exc).__name__)
            finally:
                state["importing"] = False
                target.unlink(missing_ok=True)
            await asyncio.sleep(settings.gtfs_interval if not state["gtfs_error"] else 60)

    async def realtime_loop(client):
        while True:
            target = timetable.directory / "rt-download.tmp"
            try:
                await download(client, settings.realtime_url, target, 20 * 1024 * 1024)
                realtime.ingest(target.read_bytes())
                state["realtime_error"] = None
            except Exception as exc:
                state["realtime_error"] = type(exc).__name__
                LOG.warning("Aktualizace realtime selhala: %s", type(exc).__name__)
            finally:
                target.unlink(missing_ok=True)
            await asyncio.sleep(settings.realtime_interval)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "IDS-JMK/0.1 (github.com/CooLajz/IDS-JMK)"},
        ) as client:
            tasks = (
                [asyncio.create_task(f(client)) for f in (static_loop, realtime_loop)]
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
        version="0.1.0",
        lifespan=lifespan,
        description="Odjezdy a polohy vozidel. Vlastní odhady jsou označeny vehicle_estimate.",
    )
    app.state.timetable = timetable
    app.state.realtime = realtime

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Zastávka nebo spoj neexistuje"})

    def ready():
        if not timetable.ready:
            raise HTTPException(
                503, "Jízdní řády se připravují. Zkus to za chvíli.", headers={"Retry-After": "30"}
            )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness():
        ready()
        return {"status": "ready"}

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
            "schedule_expired": bool(valid_to and valid_to < datetime.now(TZ).strftime("%Y%m%d")),
            "realtime": {
                "updated_at": iso(realtime.snapshot.timestamp) if realtime.snapshot.timestamp else None,
                "stale": not realtime.fresh(realtime.snapshot.timestamp, time.time()),
                "vehicles": len(realtime.snapshot.vehicles),
                "trip_updates": len(realtime.snapshot.updates),
            },
        }

    @app.get("/api/v1/stops")
    def stops(query: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=100)):
        ready()
        return {"stops": timetable.search(query.strip(), limit)}

    @app.get("/api/v1/stops/{stop_id}")
    def stop_detail(stop_id: str):
        ready()
        return timetable.detail(stop_id)

    @app.get("/api/v1/stops/{stop_id}/departures", response_model=DepartureBoard)
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
            stop_id, realtime, datetime.now(TZ), limit, horizon, line, direction, previous_limit
        )
        result["realtime_stale"] = not realtime.fresh(realtime.snapshot.timestamp, time.time())
        return result

    @app.get("/api/v1/trips/{trip_id}")
    def trip(trip_id: str, service_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
        ready()
        try:
            day = datetime.strptime(service_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "Neplatné datum") from None
        result = timetable.trip(trip_id, day)
        result["vehicles"] = (
            realtime.trip_vehicles(trip_id, result["stops"], day, time.time()) if result["active"] else []
        )
        return result

    @app.get("/api/v1/vehicles")
    def vehicles(trip_id: str | None = None):
        ready()
        ids = {key[0] for key in realtime.snapshot.vehicles if not trip_id or key[0] == trip_id}
        with timetable.connect() as db:
            positions = {key: timetable.trip_stops(db, key) for key in ids}
        return {"vehicles": realtime.vehicle_list(trip_id, stops_by_trip=positions)}

    return app


app = create_app()
