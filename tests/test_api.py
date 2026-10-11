import csv
import io
import zipfile
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from google.transit import gtfs_realtime_pb2 as pb

from api.config import Settings
from api.gtfs import TZ, Timetable, normalize_stop, seconds, service_epoch
from api.main import create_app
from api.realtime import Realtime, Snapshot


def archive(path, invalid=False):
    files = {
        "agency.txt": [["agency_timezone"], ["Europe/Prague"]],
        "stops.txt": [
            [
                "stop_id",
                "stop_name",
                "stop_lat",
                "stop_lon",
                "parent_station",
                "location_type",
                "platform_code",
            ],
            ["P", "Nádraží", 49, 16, "", 1, ""],
            ["A", "Nádraží", 49, 16, "P", 0, "1"],
            ["B", "Náměstí", 49.01, 16.01, "", 0, ""],
            ["C", "Konečná", 49.02, 16.02, "", 0, ""],
        ],
        "routes.txt": [
            ["route_id", "route_short_name", "route_long_name", "route_type"],
            ["R", "501", "Test", 3],
        ],
        "trips.txt": [
            [
                "trip_id",
                "route_id",
                "service_id",
                "trip_headsign",
                "direction_id",
                "wheelchair_accessible",
                "bikes_allowed",
            ],
            ["T", "R", "daily", "Konečná", 0, 1, 1],
            ["N", "R", "daily", "Konečná", 0, 2, 0],
        ],
        "stop_times.txt": [
            ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "pickup_type"],
            ["T", "14:00:00", "14:00:00", "A", 1, 0],
            ["T", "14:10:00", "14:10:00", "B", 2, 0],
            ["T", "14:20:00", "14:20:00", "C", 3, 0],
            ["N", "25:05:00", "25:05:00", "A", 1, 0],
            ["N", "25:15:00", "25:15:00", "C", 2, 0],
        ],
        "calendar.txt": [
            [
                "service_id",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "start_date",
                "end_date",
            ],
            ["daily", 1, 1, 1, 1, 1, 1, 1, "20260101", "20261231"],
        ],
        "calendar_dates.txt": [["service_id", "date", "exception_type"], ["daily", "20261012", 2]],
    }
    if invalid:
        files.pop("trips.txt")
    with zipfile.ZipFile(path, "w") as z:
        for name, rows in files.items():
            s = io.StringIO()
            csv.writer(s).writerows(rows)
            z.writestr(name, s.getvalue())
    return path


@pytest.fixture
def timetable(tmp_path):
    result = Timetable(tmp_path / "db")
    result.import_zip(archive(tmp_path / "gtfs.zip"))
    return result


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


def board(timetable, stop="P", now="2026-10-11T13:59:00", rt=None, **kwargs):
    return timetable.departures(stop, rt or Realtime(), at(now), **kwargs)["departures"]


def test_import_and_search(timetable):
    assert timetable.search("nadrazi")[0]["id"] == "P"
    assert timetable.search("%") == []
    assert timetable.detail("P")["platforms"][0]["id"] == "A"
    assert timetable.detail("P")["directions"] == ["Konečná"]


def test_failed_import_preserves_old_snapshot(timetable, tmp_path):
    original = timetable.metadata()["sha256"]
    with pytest.raises(ValueError):
        timetable.import_zip(archive(tmp_path / "invalid.zip", True))
    assert timetable.metadata()["sha256"] == original
    assert board(timetable)[0]["line"] == "501"


def test_same_archive_does_not_replace_snapshot(timetable, tmp_path):
    assert not timetable.import_zip(tmp_path / "gtfs.zip")


def test_schedule_no_fake_zero_delay(timetable):
    row = board(timetable)[0]
    assert row["minutes_until"] == 1
    assert row["source"] == "schedule"
    assert row["delay_seconds"] is None and row["cancelled"] is None


def test_calendar_exclusion_and_previous_service_day(timetable):
    assert board(timetable, now="2026-10-12T13:59:00", horizon=60) == []
    row = board(timetable, now="2026-10-12T00:59:00", horizon=20)[0]
    assert row["service_date"] == "2026-10-11"
    assert row["departure_time"] == "2026-10-12T01:05:00+02:00"


def test_added_service_exception(timetable):
    import sqlite3

    with sqlite3.connect(timetable.path) as db:
        db.execute("UPDATE calendar SET days='0000000'")
        db.execute("INSERT INTO exceptions VALUES ('daily','20261011',1)")
    assert board(timetable)[0]["trip_id"] == "T"


def test_final_stop_not_a_departure(timetable):
    assert board(timetable, stop="C") == []


def test_filters(timetable):
    assert board(timetable, line="999") == []
    assert board(timetable, direction="Neexistuje") == []
    assert len(board(timetable, line="501", direction="Konečná", limit=1)) == 1


def test_time_and_normalization():
    assert seconds("25:05:00") == 90300
    assert normalize_stop("U01146Z03") == "U1146Z3"
    with pytest.raises(ValueError):
        seconds("12:99:00")


@pytest.mark.parametrize("value", ["2026-03-29", "2026-10-25"])
def test_gtfs_dst_noon_anchor(value):
    day = datetime.fromisoformat(value).date()
    assert datetime.fromtimestamp(service_epoch(day) + 12 * 3600, TZ).hour == 12


def vehicle_rt(now, age=0, stop="A", status=pb.VehiclePosition.STOPPED_AT):
    stamp = now.timestamp() - age
    return Snapshot(
        int(stamp),
        stamp,
        {
            ("T", ""): {
                "id": "V",
                "label": "Bus",
                "trip_id": "T",
                "start_date": "",
                "timestamp": stamp,
                "stop_id": stop,
                "sequence": 1,
                "status": status,
                "position": {"lat": 49, "lon": 16},
                "bearing": None,
            }
        },
        {},
        [],
    )


def test_vehicle_estimate_and_staleness(timetable):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    row = board(timetable, stop="B", now=now.isoformat(), rt=rt)[0]
    assert row["source"] == "vehicle_estimate" and row["delay_seconds"] == 180
    assert row["departure_time_display"] == "14:13"
    rt.snapshot = vehicle_rt(now, age=181)
    row = board(timetable, stop="B", now=now.isoformat(), rt=rt)[0]
    assert row["source"] == "schedule" and row["delay_seconds"] is None


def test_no_vehicle_early_departure(timetable):
    now = at("2026-10-11T13:59:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    assert board(timetable, rt=rt)[0]["delay_seconds"] == 0


def test_trip_update_cancel_and_no_data(timetable):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    u = pb.TripUpdate()
    u.trip.trip_id = "T"
    u.timestamp = int(now.timestamp())
    s = u.stop_time_update.add()
    s.stop_sequence = 2
    s.departure.delay = 240
    rt.snapshot = Snapshot(int(now.timestamp()), now.timestamp(), {}, {("T", ""): u}, [])
    row = board(timetable, stop="B", now=now.isoformat(), rt=rt)[0]
    assert row["delay_seconds"] == 240 and row["source"] == "trip_update"
    s.schedule_relationship = pb.TripUpdate.StopTimeUpdate.NO_DATA
    assert board(timetable, stop="B", now=now.isoformat(), rt=rt)[0]["source"] == "schedule"
    u.trip.schedule_relationship = pb.TripDescriptor.CANCELED
    assert board(timetable, stop="B", now=now.isoformat(), rt=rt)[0]["cancelled"] is True


def test_repeated_stop_without_sequence_is_not_guessed(timetable):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    rt.snapshot.vehicles[("T", "")]["sequence"] = None
    with timetable.connect() as db:
        stops = timetable.trip_stops(db, "T")
        row = dict(db.execute("SELECT * FROM times WHERE trip_id='T' AND seq=2").fetchone())
    assert (
        rt.estimate(
            row, now.date(), service_epoch(now.date()), [stops[0], stops[0], *stops[1:]], now.timestamp()
        )
        == {}
    )


def test_feed_parsing(monkeypatch):
    now = at("2026-10-11T14:03:00").timestamp()
    monkeypatch.setattr("api.realtime.time.time", lambda: now)
    f = pb.FeedMessage()
    f.header.gtfs_realtime_version = "2.0"
    f.header.timestamp = int(now)
    v = f.entity.add()
    v.id = "1"
    v.vehicle.trip.trip_id = "T"
    v.vehicle.stop_id = "U01146Z03"
    v.vehicle.position.latitude = 49
    v.vehicle.position.longitude = 16
    rt = Realtime()
    rt.ingest(f.SerializeToString())
    assert rt.snapshot.vehicles[("T", "")]["stop_id"] == "U1146Z3"
    f.header.incrementality = pb.FeedHeader.DIFFERENTIAL
    with pytest.raises(ValueError):
        rt.ingest(f.SerializeToString())
    assert len(rt.snapshot.vehicles) == 1


def test_api_readiness_missing_ids_and_bounds(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "app", download_enabled=False))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.get("/api/v1/stops").status_code == 503
        app.state.timetable.import_zip(archive(tmp_path / "feed.zip"))
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/stops/nope").status_code == 404
        assert client.get("/api/v1/stops/P/departures?limit=99999").status_code == 422
        assert client.get("/api/v1/trips/T?service_date=2026-99-99").status_code == 422
        assert client.get("/api/v1/stops?query=nadrazi").json()["stops"][0]["id"] == "P"
        assert client.get("/api/v1/trips/T?service_date=2026-10-11").json()["active"] is True
        assert client.get("/api/v1/trips/T?service_date=2026-10-12").json()["active"] is False
        assert client.get("/api/v1/status").json()["instance_id"]


def test_implausible_vehicle_position_is_not_mapped(monkeypatch):
    now = at("2026-10-11T14:03:00")
    monkeypatch.setattr("api.realtime.time.time", lambda: now.timestamp())
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    rt.snapshot.vehicles[("T", "")]["position"]["lon"] = 12
    vehicle = rt.vehicle_list("T", [{"lat": 49, "lon": 16}], now.date())[0]
    assert vehicle["position"] is None
    assert vehicle["position_valid"] is False


def test_explicit_future_cancellation(timetable):
    now = at("2026-10-11T14:03:00")
    u = pb.TripUpdate()
    u.trip.trip_id = "T"
    u.trip.start_date = "20261013"
    u.trip.schedule_relationship = pb.TripDescriptor.CANCELED
    rt = Realtime()
    rt.snapshot = Snapshot(int(now.timestamp()), now.timestamp(), {}, {("T", "20261013"): u}, [])
    with timetable.connect() as db:
        stops = timetable.trip_stops(db, "T")
        row = dict(db.execute("SELECT * FROM times WHERE trip_id='T' AND seq=2").fetchone())
    day = at("2026-10-13T14:00:00").date()
    assert rt.estimate(row, day, service_epoch(day), stops, now.timestamp())["cancelled"] is True


def test_previous_departure_is_separate_and_filters_apply(timetable):
    now = at("2026-10-11T18:00:00")
    result = timetable.departures("P", Realtime(), now, limit=1, previous_limit=1)
    assert len(result["departures"]) == 1
    previous = result["previous_departures"]
    assert len(previous) == 1
    assert previous[0]["trip_id"] == "T"
    assert previous[0]["minutes_until"] == -240
    assert previous[0]["source"] == "schedule"
    assert timetable.departures("P", Realtime(), now)["previous_departures"] == []
    for kwargs in ({"line": "999"}, {"direction": "Neexistuje"}):
        assert (
            timetable.departures("P", Realtime(), now, previous_limit=1, **kwargs)["previous_departures"]
            == []
        )
    assert timetable.departures("C", Realtime(), now, previous_limit=1)["previous_departures"] == []


def test_previous_midnight_service_calendar_and_empty_future(timetable):
    result = timetable.departures("A", Realtime(), at("2026-10-12T01:06:00"), horizon=60, previous_limit=2)
    assert result["departures"] == []
    assert [r["trip_id"] for r in result["previous_departures"]] == ["N", "T"]
    assert result["previous_departures"][0]["service_date"] == "2026-10-11"
    # October 12 is excluded; neither its afternoon trip nor its 25:05 service runs.
    assert (
        timetable.departures("A", Realtime(), at("2026-10-13T01:06:00"), previous_limit=1)[
            "previous_departures"
        ]
        == []
    )


def test_delayed_future_departure_not_in_previous(timetable):
    now = at("2026-10-11T14:03:00")
    update = pb.TripUpdate()
    update.trip.trip_id = "T"
    update.timestamp = int(now.timestamp())
    stop = update.stop_time_update.add()
    stop.stop_sequence = 1
    stop.departure.delay = 300
    rt = Realtime()
    rt.snapshot = Snapshot(int(now.timestamp()), now.timestamp(), {}, {("T", ""): update}, [])
    result = timetable.departures("A", rt, now, previous_limit=1)
    assert result["departures"][0]["trip_id"] == "T"
    assert result["departures"][0]["minutes_until"] == 2
    assert result["previous_departures"][0]["trip_id"] == "N"


def test_map_badge_after_vehicle_passed_stop_without_delay_estimate(timetable):
    now = at("2026-10-11T14:11:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now, stop="B")
    rt.snapshot.vehicles[("T", "")].update(sequence=2, position={"lat": 49.01, "lon": 16.01})
    result = timetable.departures("A", rt, now, previous_limit=1)
    row = result["previous_departures"][0]
    assert row["source"] == "schedule" and row["vehicle_id"] is None
    assert row["has_vehicle_position"] is True
    assert rt.trip_vehicles("T", timetable.trip("T", now.date())["stops"], now.date(), now.timestamp())[0][
        "position"
    ]
    # Reused trip IDs must not advertise today's vehicle on tomorrow's service.
    assert not any(r["has_vehicle_position"] for r in result["departures"])


@pytest.mark.parametrize("unusable", ["stale", "wrong_day", "bad_gps", "no_position", "old_feed"])
def test_map_badge_rejects_unusable_position(timetable, unusable):
    now = at("2026-10-11T13:59:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    vehicle = rt.snapshot.vehicles[("T", "")]
    if unusable == "stale":
        vehicle["timestamp"] -= 181
    elif unusable == "wrong_day":
        vehicle["start_date"] = "20261010"
    elif unusable == "bad_gps":
        vehicle["position"]["lon"] = 12
    elif unusable == "no_position":
        vehicle["position"] = None
    else:
        rt.snapshot = Snapshot(int(now.timestamp()) - 181, now.timestamp(), rt.snapshot.vehicles)
    assert board(timetable, rt=rt)[0]["has_vehicle_position"] is False


def test_previous_api_schema_and_bounds(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "app", download_enabled=False))
    with TestClient(app) as client:
        app.state.timetable.import_zip(archive(tmp_path / "feed.zip"))
        for value in (-1, 11):
            assert client.get(f"/api/v1/stops/P/departures?previous_limit={value}").status_code == 422
        response = client.get("/api/v1/stops/P/departures?previous_limit=1")
        assert response.status_code == 200
        data = response.json()
        assert "previous_departures" in data
        for row in data["departures"] + data["previous_departures"]:
            assert isinstance(row["has_vehicle_position"], bool)


@pytest.mark.parametrize("raw, expected", [(0, None), (1, True), (2, False)])
def test_planned_vehicle_features(timetable, raw, expected):
    import sqlite3

    with sqlite3.connect(timetable.path) as db:
        db.execute("UPDATE trips SET wheelchair=?,bikes=? WHERE id='T'", (raw, raw))
    row = board(timetable)[0]
    assert row["wheelchair_accessible"] is expected
    assert row["bikes_allowed"] is expected
    trip = timetable.trip("T", at("2026-10-11").date())
    assert trip["wheelchair_accessible"] is expected
    assert trip["bikes_allowed"] is expected


def test_legacy_database_upgrade_and_reimport(timetable, tmp_path):
    import sqlite3

    with sqlite3.connect(timetable.path) as db:
        db.execute("ALTER TABLE trips DROP COLUMN bikes")
        db.execute("DELETE FROM meta WHERE key='schema_version'")
    upgraded = Timetable(timetable.directory)
    assert board(upgraded)[0]["bikes_allowed"] is None
    assert upgraded.import_zip(archive(tmp_path / "same.zip"))
    assert upgraded.metadata()["schema_version"] == 2
    assert not upgraded.import_zip(tmp_path / "same.zip")


def test_import_reads_planned_vehicle_features(timetable):
    rows = board(timetable)
    assert rows[0]["wheelchair_accessible"] is True
    assert rows[0]["bikes_allowed"] is True
    assert rows[1]["wheelchair_accessible"] is False
    assert rows[1]["bikes_allowed"] is None


def test_source_outage_keeps_imported_schedule(tmp_path, monkeypatch):
    import time

    import httpx

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    monkeypatch.setattr(
        "api.main.httpx.AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    app = create_app(Settings(data_dir=tmp_path / "app", download_enabled=True))
    app.state.timetable.import_zip(archive(tmp_path / "feed.zip"))
    with TestClient(app) as client:
        for _ in range(100):
            status = client.get("/api/v1/status").json()
            if status["gtfs_error"] and status["realtime_error"]:
                break
            time.sleep(0.01)
        assert status["gtfs_error"] == "HTTPStatusError"
        assert status["realtime_error"] == "HTTPStatusError"
        assert status["ready"] and status["realtime"]["stale"]
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/stops?query=nadrazi").json()["stops"][0]["id"] == "P"


@pytest.mark.parametrize("status,label", [
    (pb.VehiclePosition.IN_TRANSIT_TO, "in_transit_to"),
    (pb.VehiclePosition.INCOMING_AT, "incoming_at"),
    (pb.VehiclePosition.STOPPED_AT, "stopped_at"),
])
def test_vehicle_reports_unique_stop_without_sequence(timetable, status, label):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now, stop="B", status=status)
    rt.snapshot.vehicles[("T", "")]["sequence"] = None
    stops = timetable.trip("T", now.date())["stops"]
    vehicle = rt.trip_vehicles("T", stops, now.date(), now.timestamp())[0]
    assert vehicle["current_stop"] == {
        "stop_id": "B", "stop_sequence": 2, "status": label, "source": "realtime"
    }


@pytest.mark.parametrize("case", ["repeated", "conflicting", "missing", "stale", "no_position"])
def test_vehicle_stop_is_not_guessed(timetable, case):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now)
    v = rt.snapshot.vehicles[("T", "")]
    stops = timetable.trip("T", now.date())["stops"]
    if case == "repeated":
        v["sequence"] = None
        stops.append({**stops[0], "seq": 4})
    elif case == "conflicting":
        v["sequence"] = 2  # Stop ID still reports A, sequence 2 belongs to B.
    elif case == "missing":
        v.update(sequence=None, stop_id="")
    elif case == "stale":
        v["timestamp"] -= 181
    else:
        v["position"] = None
    assert rt.vehicle_list("T", stops, now.date(), now=now.timestamp())[0]["current_stop"] is None


def test_vehicle_stop_sequence_disambiguates_loop_and_updates(timetable):
    now = at("2026-10-11T14:03:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now, status=pb.VehiclePosition.IN_TRANSIT_TO)
    v = rt.snapshot.vehicles[("T", "")]
    stops = timetable.trip("T", now.date())["stops"]
    stops.append({**stops[0], "seq": 4})
    v["sequence"] = 4
    current = rt.vehicle_list("T", stops, now.date(), now=now.timestamp())[0]["current_stop"]
    assert current["stop_sequence"] == 4
    v.update(sequence=2, stop_id="B")
    assert rt.vehicle_list("T", stops, now.date(), now=now.timestamp())[0]["current_stop"]["stop_id"] == "B"


@pytest.mark.parametrize("case,expected", [
    ("at_origin", "before_departure"),
    ("away_from_origin", "in_transit_to"),
    ("after_start", "in_transit_to"),
    ("later_stop", "in_transit_to"),
])
def test_vehicle_before_planned_start(timetable, case, expected):
    now = at("2026-10-11T13:55:00" if case != "after_start" else "2026-10-11T14:01:00")
    rt = Realtime()
    rt.snapshot = vehicle_rt(now, stop="B", status=pb.VehiclePosition.IN_TRANSIT_TO)
    v = rt.snapshot.vehicles[("T", "")]
    v["sequence"] = None
    if case == "away_from_origin":
        v["position"] = {"lat": 49.005, "lon": 16.005}
    elif case == "later_stop":
        v["stop_id"] = "C"
    stops = timetable.trip("T", now.date())["stops"]
    current = rt.trip_vehicles("T", stops, now.date(), now.timestamp())[0]["current_stop"]
    assert current["status"] == expected
    if expected == "before_departure":
        assert current["stop_id"] == "A"
        assert current["source"] == "schedule_and_position"
