"""Build an indexed SQLite snapshot, then atomically replace the active timetable."""

import csv
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import unicodedata
import uuid
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Prague")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def folded(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


def normalize_stop(value):
    match = re.fullmatch(r"([A-Za-z]+)0*(\d+)([A-Za-z]+)0*(\d+)", value or "")
    return f"{match[1]}{int(match[2])}{match[3]}{int(match[4])}" if match else value


def seconds(value):
    h, m, s = map(int, value.split(":"))
    if not 0 <= h <= 71 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError("Neplatný čas GTFS")
    return h * 3600 + m * 60 + s


def service_epoch(day):
    # GTFS defines the time origin as local noon minus 12 elapsed hours (also on DST days).
    return datetime.combine(day, time(12), TZ).timestamp() - 12 * 3600


def iso(epoch):
    return datetime.fromtimestamp(epoch, TZ).isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE stops (id TEXT PRIMARY KEY, name TEXT, search TEXT, lat REAL, lon REAL,
 parent TEXT, platform TEXT, kind INTEGER, normalized TEXT);
CREATE TABLE routes (id TEXT PRIMARY KEY, line TEXT, name TEXT, type INTEGER);
CREATE TABLE trips (id TEXT PRIMARY KEY, route_id TEXT, service_id TEXT, headsign TEXT,
 direction TEXT, wheelchair INTEGER, bikes INTEGER);
CREATE TABLE times (trip_id TEXT, stop_id TEXT, seq INTEGER, arrival INTEGER, departure INTEGER,
 pickup INTEGER, PRIMARY KEY(trip_id, seq));
CREATE TABLE calendar (service_id TEXT PRIMARY KEY, days TEXT, start TEXT, end TEXT);
CREATE TABLE exceptions (service_id TEXT, day TEXT, type INTEGER, PRIMARY KEY(service_id, day));
"""


class Timetable:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "schedule.sqlite3"
        if self.path.exists():
            # Keep an existing timetable readable until the next atomic reimport.
            with sqlite3.connect(self.path) as db:
                if "bikes" not in {r[1] for r in db.execute("PRAGMA table_info(trips)")}:
                    db.execute("ALTER TABLE trips ADD COLUMN bikes INTEGER DEFAULT 0")

    @property
    def ready(self):
        return self.path.exists()

    @contextmanager
    def connect(self):
        if not self.ready:
            raise RuntimeError("Jízdní řády se připravují")
        db = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def metadata(self):
        if not self.ready:
            return {}
        with self.connect() as db:
            return {r["key"]: json.loads(r["value"]) for r in db.execute("SELECT * FROM meta")}

    def import_zip(self, archive):
        digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
        meta = self.metadata()
        if meta.get("sha256") == digest and meta.get("schema_version") == 2:
            return False
        stage = self.directory / f"schedule-{uuid.uuid4().hex}.tmp"
        try:
            with zipfile.ZipFile(archive) as z, sqlite3.connect(stage) as db:
                if sum(i.file_size for i in z.infolist()) > 1024 * 1024 * 1024:
                    raise ValueError("GTFS archiv je příliš velký")
                names = set(z.namelist())
                required = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "agency.txt"}
                if not required <= names or not {"calendar.txt", "calendar_dates.txt"} & names:
                    raise ValueError("GTFS neobsahuje povinné soubory")
                if "frequencies.txt" in names:
                    raise ValueError("Intervalové jízdní řády nejsou v této verzi podporovány")

                def rows(name):
                    if name in names:
                        with z.open(name) as f:
                            yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

                if any(r["agency_timezone"] != "Europe/Prague" for r in rows("agency.txt")):
                    raise ValueError("Podporované časové pásmo je Europe/Prague")
                db.executescript(SCHEMA)
                db.executemany(
                    "INSERT INTO stops VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        (
                            r["stop_id"],
                            r["stop_name"],
                            folded(r["stop_name"]),
                            float(r["stop_lat"]),
                            float(r["stop_lon"]),
                            r.get("parent_station", ""),
                            r.get("platform_code", ""),
                            int(r.get("location_type") or 0),
                            normalize_stop(r["stop_id"]),
                        )
                        for r in rows("stops.txt")
                    ),
                )
                db.executemany(
                    "INSERT INTO routes VALUES (?,?,?,?)",
                    (
                        (r["route_id"], r["route_short_name"], r["route_long_name"], int(r["route_type"]))
                        for r in rows("routes.txt")
                    ),
                )
                db.executemany(
                    "INSERT INTO trips VALUES (?,?,?,?,?,?,?)",
                    (
                        (
                            r["trip_id"],
                            r["route_id"],
                            r["service_id"],
                            r.get("trip_headsign", ""),
                            r.get("direction_id", ""),
                            int(r.get("wheelchair_accessible") or 0),
                            int(r.get("bikes_allowed") or 0),
                        )
                        for r in rows("trips.txt")
                    ),
                )
                db.executemany(
                    "INSERT INTO times VALUES (?,?,?,?,?,?)",
                    (
                        (
                            r["trip_id"],
                            r["stop_id"],
                            int(r["stop_sequence"]),
                            seconds(r["arrival_time"]),
                            seconds(r["departure_time"]),
                            int(r.get("pickup_type") or 0),
                        )
                        for r in rows("stop_times.txt")
                    ),
                )
                db.executemany(
                    "INSERT INTO calendar VALUES (?,?,?,?)",
                    (
                        (r["service_id"], "".join(r[d] for d in WEEKDAYS), r["start_date"], r["end_date"])
                        for r in rows("calendar.txt")
                    ),
                )
                db.executemany(
                    "INSERT INTO exceptions VALUES (?,?,?)",
                    (
                        (r["service_id"], r["date"], int(r["exception_type"]))
                        for r in rows("calendar_dates.txt")
                    ),
                )
                db.executescript("""
                    CREATE INDEX stops_parent ON stops(parent);
                    CREATE INDEX stops_normalized ON stops(normalized);
                    CREATE INDEX times_stop_departure ON times(stop_id, departure);
                    CREATE INDEX exceptions_day ON exceptions(day);
                """)
                counts = {
                    t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("stops", "routes", "trips", "times")
                }
                if not all(counts.values()):
                    raise ValueError("Prázdný jízdní řád")
                for sql in (
                    "SELECT 1 FROM times t LEFT JOIN stops s ON s.id=t.stop_id WHERE s.id IS NULL LIMIT 1",
                    "SELECT 1 FROM times s LEFT JOIN trips t ON t.id=s.trip_id WHERE t.id IS NULL LIMIT 1",
                    "SELECT 1 FROM trips t LEFT JOIN routes r ON r.id=t.route_id WHERE r.id IS NULL LIMIT 1",
                ):
                    if db.execute(sql).fetchone():
                        raise ValueError("Nekonzistentní odkazy v GTFS")
                dates = db.execute(
                    "SELECT MIN(d),MAX(d) FROM (SELECT start d FROM calendar "
                    "UNION ALL SELECT end FROM calendar UNION ALL SELECT day FROM exceptions)"
                ).fetchone()
                meta = {
                    "schema_version": 2,
                    "sha256": digest,
                    "imported_at": datetime.now(UTC).isoformat(),
                    "counts": counts,
                    "valid_from": dates[0],
                    "valid_to": dates[1],
                    "max_time": db.execute("SELECT MAX(departure) FROM times").fetchone()[0],
                }
                db.executemany("INSERT INTO meta VALUES (?,?)", ((k, json.dumps(v)) for k, v in meta.items()))
                db.commit()
            os.replace(stage, self.path)
            return True
        finally:
            stage.unlink(missing_ok=True)

    @staticmethod
    def stop(db, stop_id):
        r = db.execute("SELECT * FROM stops WHERE id=?", (stop_id,)).fetchone()
        if not r:
            raise KeyError(stop_id)
        return dict(r)

    @staticmethod
    def stop_ids(db, stop_id):
        Timetable.stop(db, stop_id)
        return [stop_id] + [r[0] for r in db.execute("SELECT id FROM stops WHERE parent=?", (stop_id,))]

    def search(self, query, limit=20):
        # Literal substring matching, accent-insensitive, grouping platforms under their parent.
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    """
                SELECT s.id, s.name, s.lat, s.lon, s.platform, s.kind,
                       (SELECT COUNT(*) FROM stops p WHERE p.parent=s.id) platforms
                FROM stops s WHERE instr(s.search, ?) > 0 AND (s.parent='' OR s.parent IS NULL)
                ORDER BY CASE WHEN s.search=? THEN 0 WHEN s.kind=1 THEN 1 ELSE 2 END, s.name LIMIT ?
            """,
                    (folded(query), folded(query), limit),
                )
            ]

    def detail(self, stop_id):
        with self.connect() as db:
            stop = self.stop(db, stop_id)
            stop["platforms"] = [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,platform FROM stops WHERE parent=? ORDER BY platform,id", (stop_id,)
                )
            ]
            ids = self.stop_ids(db, stop_id)
            marks = ",".join("?" for _ in ids)
            stop["directions"] = [
                r[0]
                for r in db.execute(
                    f"""
                SELECT DISTINCT t.headsign FROM times st JOIN trips t ON t.id=st.trip_id
                WHERE st.stop_id IN ({marks}) AND st.pickup<>1 ORDER BY t.headsign""",
                    ids,
                )
            ]
            stop["lines"] = [
                r[0]
                for r in db.execute(
                    f"""
                SELECT DISTINCT r.line FROM times st JOIN trips t ON t.id=st.trip_id
                JOIN routes r ON r.id=t.route_id WHERE st.stop_id IN ({marks}) ORDER BY r.line""",
                    ids,
                )
            ]
            return stop

    @staticmethod
    def active_services(db, day):
        text = day.strftime("%Y%m%d")
        services = {
            r[0]
            for r in db.execute(
                "SELECT service_id FROM calendar WHERE start<=? AND end>=? AND substr(days,?,1)='1'",
                (text, text, day.weekday() + 1),
            )
        }
        for r in db.execute("SELECT service_id,type FROM exceptions WHERE day=?", (text,)):
            if r[1] == 1:
                services.add(r[0])
            else:
                services.discard(r[0])
        return services

    @staticmethod
    def trip_stops(db, trip_id):
        return [
            dict(r)
            for r in db.execute(
                """
            SELECT st.*,s.name,s.lat,s.lon,s.platform,s.normalized FROM times st
            JOIN stops s ON s.id=st.stop_id WHERE st.trip_id=? ORDER BY st.seq""",
                (trip_id,),
            )
        ]

    def trip(self, trip_id, service_date):
        with self.connect() as db:
            r = db.execute(
                """SELECT t.*,r.line FROM trips t JOIN routes r ON r.id=t.route_id
                              WHERE t.id=?""",
                (trip_id,),
            ).fetchone()
            if not r:
                raise KeyError(trip_id)
            origin = service_epoch(service_date)
            return {
                **dict(r),
                "wheelchair_accessible": {0: None, 1: True, 2: False}.get(r["wheelchair"]),
                "bikes_allowed": {0: None, 1: True, 2: False}.get(r["bikes"]),
                "service_date": service_date.isoformat(),
                "active": r["service_id"] in self.active_services(db, service_date),
                "stops": [
                    {**s, "scheduled_departure": iso(origin + s["departure"])}
                    for s in self.trip_stops(db, trip_id)
                ],
            }

    def departures(
        self, stop_id, realtime, now, limit=10, horizon=1440, line=None, direction=None, previous_limit=0
    ):
        end = now.timestamp() + horizon * 60
        start = now.timestamp() - (86400 if previous_limit else 0)
        output = []
        with self.connect() as db:
            stop = self.stop(db, stop_id)
            ids = self.stop_ids(db, stop_id)
            marks = ",".join("?" for _ in ids)
            max_time = json.loads(db.execute("SELECT value FROM meta WHERE key='max_time'").fetchone()[0])
            first_day = datetime.fromtimestamp(start, TZ).date() - timedelta(days=max_time // 86400 + 1)
            last_day = datetime.fromtimestamp(end, TZ).date()
            day = first_day
            trip_cache = {}
            realtime_trips = {k[0] for k in realtime.snapshot.vehicles} | {
                k[0] for k in realtime.snapshot.updates
            }
            while day <= last_day:
                active = self.active_services(db, day)
                origin = service_epoch(day)
                # Two-hour lookback retains delayed departures that have already passed in the timetable.
                lo = max(0, int(start - origin - 7200))
                hi = int(end - origin + 7200)
                sql = f"""SELECT st.*, t.service_id,t.headsign,t.direction,t.wheelchair,t.bikes,t.route_id,
                    r.line,r.type,s.platform,s.name FROM times st
                    JOIN trips t ON t.id=st.trip_id JOIN routes r ON r.id=t.route_id
                    JOIN stops s ON s.id=st.stop_id WHERE st.stop_id IN ({marks})
                    AND st.departure BETWEEN ? AND ? AND st.pickup<>1
                    AND EXISTS (SELECT 1 FROM times later
                        WHERE later.trip_id=st.trip_id AND later.seq>st.seq)"""
                args = ids + [lo, hi]
                if line:
                    sql += " AND r.line=?"
                    args.append(line)
                if direction:
                    sql += " AND t.headsign=?"
                    args.append(direction)
                for row in db.execute(sql, args):
                    if row["service_id"] not in active:
                        continue
                    scheduled = origin + row["departure"]
                    trip_id = row["trip_id"]
                    if trip_id not in trip_cache:
                        trip_cache[trip_id] = (
                            self.trip_stops(db, trip_id) if trip_id in realtime_trips else []
                        )
                    estimate = realtime.estimate(row, day, origin, trip_cache[trip_id], now.timestamp())
                    effective = estimate.get("estimated_epoch") or scheduled
                    if not start <= effective <= end:
                        continue
                    output.append(
                        {
                            "trip_id": trip_id,
                            "service_date": day.isoformat(),
                            "stop_id": row["stop_id"],
                            "stop_sequence": row["seq"],
                            "line": row["line"],
                            "destination": row["headsign"],
                            "platform": row["platform"],
                            "scheduled_departure": iso(scheduled),
                            "estimated_departure": iso(estimate["estimated_epoch"])
                            if estimate.get("estimated_epoch")
                            else None,
                            "departure_time": iso(effective),
                            "departure_time_display": datetime.fromtimestamp(effective, TZ).strftime("%H:%M"),
                            "minutes_until": math.ceil((effective - now.timestamp()) / 60),
                            "delay_seconds": estimate.get("delay_seconds"),
                            "source": estimate.get("source", "schedule"),
                            "realtime_updated_at": iso(estimate["timestamp"])
                            if estimate.get("timestamp")
                            else None,
                            "cancelled": estimate.get("cancelled"),
                            "vehicle_id": estimate.get("vehicle_id"),
                            "wheelchair_accessible": {0: None, 1: True, 2: False}.get(row["wheelchair"]),
                            "bikes_allowed": {0: None, 1: True, 2: False}.get(row["bikes"]),
                        }
                    )
                day += timedelta(days=1)
        output.sort(
            key=lambda r: (datetime.fromisoformat(r["departure_time"]).timestamp(), r["line"], r["trip_id"])
        )
        upcoming = [
            r for r in output if datetime.fromisoformat(r["departure_time"]).timestamp() >= now.timestamp()
        ][:limit]
        previous = [
            r for r in output if datetime.fromisoformat(r["departure_time"]).timestamp() < now.timestamp()
        ]
        previous = list(reversed(previous[-previous_limit:])) if previous_limit else []
        # Positions do not imply that a delay estimate is available for this stop.
        for row in upcoming + previous:
            vehicles = realtime.trip_vehicles(
                row["trip_id"],
                trip_cache[row["trip_id"]],
                datetime.fromisoformat(row["service_date"]).date(),
                now.timestamp(),
            )
            row["has_vehicle_position"] = any(v["position"] and not v["stale"] for v in vehicles)
        return {
            "stop": {"id": stop["id"], "name": stop["name"]},
            "generated_at": iso(now.timestamp()),
            "timezone": "Europe/Prague",
            "departures": upcoming,
            "previous_departures": previous,
        }
