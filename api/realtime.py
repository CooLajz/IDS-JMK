"""Immutable RT snapshots and explicitly labelled, bounded vehicle estimates."""

import math
import time
from dataclasses import dataclass, field

from google.transit import gtfs_realtime_pb2 as pb

from .gtfs import iso, normalize_stop, service_epoch


def distance(a, b):
    lat = math.radians((a["lat"] + b["lat"]) / 2)
    return math.hypot((a["lon"] - b["lon"]) * math.cos(lat), a["lat"] - b["lat"]) * 111_195


@dataclass(frozen=True)
class Snapshot:
    timestamp: int = 0
    received_at: float = 0
    vehicles: dict = field(default_factory=dict)
    updates: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)


class Realtime:
    def __init__(self, max_age=180):
        self.max_age = max_age
        self.snapshot = Snapshot()

    def ingest(self, data):
        feed = pb.FeedMessage()
        feed.ParseFromString(data)
        if not feed.IsInitialized() or feed.header.incrementality != pb.FeedHeader.FULL_DATASET:
            raise ValueError("Neplatný nebo nepodporovaný realtime feed")
        stamp = feed.header.timestamp
        if not stamp or stamp > time.time() + 60:
            raise ValueError("Chybí platný čas realtime feedu")
        if stamp < self.snapshot.timestamp:
            raise ValueError("Realtime feed se vrátil do minulosti")
        vehicles, updates, alerts = {}, {}, []
        for entity in feed.entity:
            if entity.is_deleted:
                continue
            if entity.HasField("vehicle"):
                v = entity.vehicle
                key = (v.trip.trip_id, v.trip.start_date)
                if not key[0]:
                    continue
                position = None
                if (
                    v.HasField("position")
                    and -90 <= v.position.latitude <= 90
                    and -180 <= v.position.longitude <= 180
                ):
                    position = {"lat": v.position.latitude, "lon": v.position.longitude}
                value = {
                    "id": v.vehicle.id or entity.id,
                    "label": v.vehicle.label,
                    "trip_id": key[0],
                    "start_date": key[1],
                    "timestamp": v.timestamp or stamp,
                    "stop_id": normalize_stop(v.stop_id),
                    "sequence": v.current_stop_sequence if v.HasField("current_stop_sequence") else None,
                    "status": v.current_status,
                    "position": position,
                    "bearing": v.position.bearing if v.position.HasField("bearing") else None,
                }
                if value["timestamp"] >= vehicles.get(key, {}).get("timestamp", 0):
                    vehicles[key] = value
            if entity.HasField("trip_update"):
                t = entity.trip_update
                updates[(t.trip.trip_id, t.trip.start_date)] = t
            if entity.HasField("alert"):
                a = entity.alert

                def translated(text):
                    return next(
                        (x.text for x in text.translation if x.language.startswith("cs")),
                        next((x.text for x in text.translation), ""),
                    )

                alerts.append(
                    {
                        "id": entity.id,
                        "title": translated(a.header_text),
                        "description": translated(a.description_text),
                    }
                )
        self.snapshot = Snapshot(stamp, time.time(), vehicles, updates, alerts)

    def fresh(self, stamp, now):
        return bool(stamp) and -60 <= now - stamp <= self.max_age

    def trip_vehicles(self, trip_id, stops, day, now):
        """Share service-instance bounds between board badges and trip maps."""
        origin = service_epoch(day)
        if not stops or not (
            origin + stops[0]["departure"] - 1800 <= now <= origin + stops[-1]["arrival"] + 7200
        ):
            return []
        vehicles = self.vehicle_list(trip_id, stops, day, now=now)
        for vehicle in vehicles:
            current = vehicle["current_stop"]
            if current is None:
                continue
            current.update(delay_seconds=None, delay_source=None)
            if current["status"] == "before_departure":
                continue
            row = next(s for s in stops if s["seq"] == current["stop_sequence"])
            estimate = self.estimate(row, day, origin, stops, now)
            current.update(
                delay_seconds=estimate.get("delay_seconds"), delay_source=estimate.get("source")
            )
        return vehicles

    @staticmethod
    def current_stop(vehicle, stops, service_date=None, now=None):
        """Resolve the reported stop occurrence; never guess repeated or conflicting stops."""
        sequence, stop_id = vehicle.get("sequence"), vehicle.get("stop_id")
        matches = [
            s for s in (stops or [])
            if (s.get("seq") == sequence if sequence is not None else
                bool(stop_id) and s.get("normalized") == stop_id)
        ]
        if len(matches) != 1:
            return None
        stop = matches[0]
        if stop_id and stop.get("normalized") != stop_id:
            return None
        status = {
            pb.VehiclePosition.IN_TRANSIT_TO: "in_transit_to",
            pb.VehiclePosition.INCOMING_AT: "incoming_at",
            pb.VehiclePosition.STOPPED_AT: "stopped_at",
        }.get(vehicle.get("status"))
        if status is None:
            return None
        # Some KORDIS vehicles already report the second stop while waiting at the origin.
        if service_date is not None and now is not None and vehicle.get("position"):
            first = stops[0]
            departure = service_epoch(service_date) + first["departure"]
            if (
                now < departure
                and vehicle["timestamp"] < departure
                and stop["seq"] in {s["seq"] for s in stops[:2]}
                and distance(vehicle["position"], first) <= 100
            ):
                return {
                    "stop_id": first["stop_id"], "stop_sequence": first["seq"],
                    "status": "before_departure", "source": "schedule_and_position",
                }
        return {
            "stop_id": stop["stop_id"], "stop_sequence": stop["seq"],
            "status": status, "source": "realtime",
        }

    def vehicle_list(self, trip_id=None, stops=None, service_date=None, stops_by_trip=None, now=None):
        snap = self.snapshot
        now = time.time() if now is None else now
        result = []
        for v in snap.vehicles.values():
            if trip_id and v["trip_id"] != trip_id:
                continue
            if service_date and v.get("start_date") and v["start_date"] != service_date.strftime("%Y%m%d"):
                continue
            position = v["position"]
            valid = None
            trip_stops = stops_by_trip.get(v["trip_id"], []) if stops_by_trip is not None else stops
            if trip_stops and position:
                # Broad sanity bound for JMK, not map matching. Reject gross source GPS errors.
                valid = min(distance(position, stop) for stop in trip_stops) <= 25_000
                if not valid:
                    position = None
            stale = not (self.fresh(snap.timestamp, now) and self.fresh(v["timestamp"], now))
            result.append(
                {
                    "id": v["id"],
                    "label": v["label"],
                    "trip_id": v["trip_id"],
                    "position": position,
                    "position_valid": valid,
                    "bearing": v["bearing"],
                    "updated_at": iso(v["timestamp"]),
                    "stale": stale,
                    "current_stop": (
                        self.current_stop(v, trip_stops, service_date, now)
                        if not stale and position else None
                    ),
                }
            )
        return result

    def estimate(self, row, day, origin, stops, now):
        snap = self.snapshot
        if not self.fresh(snap.timestamp, now):
            return {}
        trip_id = row["trip_id"]
        day_id = day.strftime("%Y%m%d")
        # A feed without start_date may only be applied near this service instance.
        in_window = (
            bool(stops)
            and origin + stops[0]["departure"] - 1800 <= now <= origin + stops[-1]["arrival"] + 7200
        )
        update = snap.updates.get((trip_id, day_id))
        if update is None and in_window:
            update = snap.updates.get((trip_id, ""))
        scheduled = origin + row["departure"]
        if update is not None and self.fresh(update.timestamp or snap.timestamp, now):
            timestamp = update.timestamp or snap.timestamp
            base = {"source": "trip_update", "timestamp": timestamp}
            if update.trip.schedule_relationship == pb.TripDescriptor.CANCELED:
                return {**base, "cancelled": True}
            # Never propagate past NO_DATA, SKIPPED, or an unrepresented downstream stop.
            for s in update.stop_time_update:
                match = (
                    s.stop_sequence == row["seq"]
                    if s.HasField("stop_sequence")
                    else normalize_stop(s.stop_id) == normalize_stop(row["stop_id"])
                )
                if not match:
                    continue
                if s.schedule_relationship == pb.TripUpdate.StopTimeUpdate.SKIPPED:
                    return {**base, "cancelled": True}
                if s.schedule_relationship == pb.TripUpdate.StopTimeUpdate.NO_DATA:
                    return {}
                event = s.departure
                if not s.HasField("departure"):
                    return {}
                epoch = (
                    event.time
                    if event.HasField("time")
                    else (scheduled + event.delay if event.HasField("delay") else None)
                )
                if epoch is not None:
                    return {
                        **base,
                        "estimated_epoch": epoch,
                        "delay_seconds": int(epoch - scheduled),
                        "cancelled": False,
                    }
            # TripUpdate exists but doesn't predict this stop; don't override with a weaker guess.
            return {}
        if not in_window:
            return {}
        v = snap.vehicles.get((trip_id, day_id)) or snap.vehicles.get((trip_id, ""))
        if not v or not self.fresh(v["timestamp"], now):
            return {}
        matches = [
            i
            for i, s in enumerate(stops)
            if (s["seq"] == v["sequence"] if v["sequence"] is not None else s["normalized"] == v["stop_id"])
        ]
        if len(matches) != 1:
            return {}  # Repeated stops require a stop_sequence to disambiguate.
        index = matches[0]
        current = stops[index]
        if row["seq"] < current["seq"]:
            return {}
        if v["status"] == pb.VehiclePosition.STOPPED_AT:
            if v["position"] and distance(v["position"], current) > 500:
                return {}
            anchor = current["departure"]
        else:
            # Approximate progress between adjacent stops, not road geometry. Never extrapolate.
            if not index or not v["position"]:
                return {}
            previous = stops[index - 1]
            span = distance(previous, current)
            to_previous, to_current = distance(v["position"], previous), distance(v["position"], current)
            if span < 30 or to_previous + to_current > max(span * 2, span + 1000):
                return {}
            progress = to_previous / max(to_previous + to_current, 1)
            anchor = previous["departure"] + progress * (current["arrival"] - previous["departure"])
        delay = round(v["timestamp"] - (origin + anchor))
        if abs(delay) > 7200:
            return {}
        # Timetable-based vehicle estimates never advertise an early departure.
        delay = max(0, delay)
        return {
            "source": "vehicle_estimate",
            "timestamp": v["timestamp"],
            "vehicle_id": v["id"],
            "estimated_epoch": scheduled + delay,
            "delay_seconds": delay,
            "cancelled": None,
        }
