"""Map catalogue and active vehicle selection without per-vehicle HA entities."""

from collections import Counter
from datetime import datetime, timedelta

from .gtfs import TZ, iso
from .transport import transport_mode


def catalogue(timetable):
    with timetable.connect() as db:
        routes = []
        by_route = {}
        for trip in db.execute("SELECT route_id,direction,headsign FROM trips"):
            groups = by_route.setdefault(trip["route_id"], {})
            groups.setdefault(trip["direction"], Counter())[trip["headsign"]] += 1
        for route in db.execute("SELECT * FROM routes ORDER BY length(line),line,id"):
            groups = by_route.get(route["id"], {})
            routes.append(
                {
                    **dict(route),
                    "directions": [
                        {"id": key, "label": " / ".join(name for name, _ in names.most_common(4))}
                        for key, names in sorted(groups.items())
                    ],
                }
            )
        return {"routes": routes}


def map_stops(timetable, selections):
    """All stop occurrences on selected route variants, independent of live vehicles."""
    if not selections:
        return {"stops": []}
    conditions, args = [], []
    for route_id, direction in sorted({(s.route_id, s.direction) for s in selections}):
        conditions.append("(t.route_id=? AND (?='*' OR t.direction=?))")
        args.extend((route_id, direction, direction))
    with timetable.connect() as db:
        rows = db.execute(
            """SELECT DISTINCT t.route_id,t.direction,r.line,s.id AS stop_id,s.name,s.lat,s.lon
            FROM trips t JOIN routes r ON r.id=t.route_id
            JOIN times st ON st.trip_id=t.id JOIN stops s ON s.id=st.stop_id
            WHERE """ + " OR ".join(conditions) + " ORDER BY r.line,s.name,s.id,t.direction",
            args,
        )
        return {"stops": [dict(row) for row in rows]}


def map_vehicles(timetable, realtime, selections, enabled, now=None):
    now = now or datetime.now(TZ)
    result = {
        "generated_at": now.isoformat(),
        "realtime_enabled": enabled,
        "stale": not realtime.fresh(realtime.snapshot.timestamp, now.timestamp()),
        "updated_at": iso(realtime.snapshot.timestamp) if realtime.snapshot.timestamp else None,
        "vehicles": [],
    }
    if not enabled or result["stale"] or not selections:
        return result
    selected = {(s.route_id, s.direction) for s in selections}
    seen = set()
    with timetable.connect() as db:
        services = {}
        for trip_id, start_date in realtime.snapshot.vehicles:
            trip = db.execute(
                "SELECT t.*,r.line,r.type FROM trips t JOIN routes r ON r.id=t.route_id WHERE t.id=?",
                (trip_id,),
            ).fetchone()
            if not trip or not (
                (trip["route_id"], "*") in selected or (trip["route_id"], trip["direction"]) in selected
            ):
                continue
            try:
                days = (
                    [datetime.strptime(start_date, "%Y%m%d").date()]
                    if start_date
                    else [now.date(), now.date() - timedelta(days=1)]
                )
            except ValueError:
                continue
            stops = timetable.trip_stops(db, trip_id)
            for day in days:
                if day not in services:
                    services[day] = timetable.active_services(db, day)
                if trip["service_id"] not in services[day]:
                    continue
                for vehicle in realtime.trip_vehicles(trip_id, stops, day, now.timestamp()):
                    if vehicle["stale"] or not vehicle["position"]:
                        continue
                    item = {
                        **vehicle,
                        "route_id": trip["route_id"],
                        "line": trip["line"],
                        "direction": trip["direction"],
                        "destination": trip["headsign"],
                        "service_date": day.isoformat(),
                        "transport_mode": transport_mode(trip["type"]),
                    }
                    if item["id"] not in seen:
                        seen.add(item["id"])
                        result["vehicles"].append(item)
    return result
