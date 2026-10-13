import time
from datetime import datetime

import httpx
from fastapi.testclient import TestClient
from google.transit import gtfs_realtime_pb2 as pb
from test_api import archive
from test_api import timetable as timetable

from api.alert_text import format_alert_text
from api.config import Settings
from api.gtfs import TZ
from api.main import create_app
from api.realtime import Realtime


def test_kordis_alert_markup_is_readable_and_formatted(timetable):
    f = feed()
    a = f.entity[0].alert
    a.header_text.translation[0].text = "<b>Omezení &amp; zdržení</b>"
    a.description_text.translation[0].text = (
        'Hustý provoz: <b>zdržení 5 až 15 min. <i>Modřice a Rajhrad.</i></b>'
        '<p>Děkujeme&nbsp;za pochopení.</i></b>'
    )
    alert = board(timetable, f)["alerts"][0]
    assert alert["title"] == "Omezení & zdržení"
    assert alert["title_html"] == "<strong>Omezení &amp; zdržení</strong>"
    assert alert["description"] == (
        "Hustý provoz: zdržení 5 až 15 min. Modřice a Rajhrad.\n\nDěkujeme za pochopení."
    )
    assert alert["description_html"] == (
        "Hustý provoz: <strong>zdržení 5 až 15 min. <em>Modřice a Rajhrad.</em></strong>"
        "<p>Děkujeme za pochopení.</p>"
    )


def test_alert_markup_ignores_active_content_and_attributes():
    plain, html = format_alert_text(
        '<script>alert(1)</script><style>body{display:none}</style>'
        '<svg><text>Skrytý text</text></svg><img src="x" onerror="evil()">'
        '<p onclick="evil()">Použijte <b style="color:red">jinou zastávku</b>.'
        '<a href="javascript:evil()">Podrobnosti</a></p>'
    )
    assert plain == "Použijte jinou zastávku.Podrobnosti"
    assert html == "<p>Použijte <strong>jinou zastávku</strong>.Podrobnosti</p>"


def test_encoded_and_broken_markup_and_plain_text():
    assert format_alert_text("&lt;b&gt;Výluka&lt;/b&gt;") == ("Výluka", "<strong>Výluka</strong>")
    assert format_alert_text("&amp;lt;i&amp;gt;Výluka&amp;lt;/i&amp;gt;") == ("Výluka", "<em>Výluka</em>")
    assert format_alert_text("&#60;b&#62;Výluka&#60;/b&#62;") == ("Výluka", "<strong>Výluka</strong>")
    assert format_alert_text("&#x3c;i&#x3e;Výluka&#x3c;/i&#x3e;") == ("Výluka", "<em>Výluka</em>")
    assert format_alert_text("</i></b><p>Jedna<p>Dvě") == ("Jedna\n\nDvě", "<p>Jedna</p><p>Dvě</p>")
    assert format_alert_text("A & B\nČas < 5 minut") == (
        "A & B\nČas < 5 minut", "A &amp; B<br>Čas &lt; 5 minut"
    )
    assert format_alert_text("<ul><li>Jedna</li><li>Dvě</li></ul>") == (
        "• Jedna\n\n• Dvě", "<ul><li>Jedna</li><li>Dvě</li></ul>"
    )
    nested = "<ul><li>Vnější<ul><li>Vnitřní</li></ul></li></ul>"
    assert format_alert_text(nested)[1] == nested


def feed(route="501", stop=None, start=None, end=None):
    f = pb.FeedMessage()
    f.header.gtfs_realtime_version = "2.0"
    f.header.timestamp = int(time.time())
    e = f.entity.add(id="lockout_1")
    a = e.alert
    s = a.informed_entity.add()
    if route:
        s.route_id = route
    if stop:
        s.stop_id = stop
    a.header_text.translation.add(text="Výluka", language="cs")
    a.description_text.translation.add(text="Přesun zastávky\nPodrobný text", language="cs")
    a.url.translation.add(text="https://example.test/info", language="cs")
    a.effect = pb.Alert.STOP_MOVED
    if start is not None or end is not None:
        period = a.active_period.add()
        if start is not None:
            period.start = start
        if end is not None:
            period.end = end
    return f


def board(timetable, f, stop="A", **filters):
    rt = Realtime()
    rt.ingest(f.SerializeToString())
    return timetable.board_alerts(stop, rt, datetime.now(TZ), **filters)


def test_route_id_and_kordis_line_name_fallback(timetable):
    for route in ("R", "501"):
        result = board(timetable, feed(route))
        assert len(result["alerts"]) == 1
        a = result["alerts"][0]
        assert a["matched_lines"] == ["501"]
        assert a["lines"] == ["501"]
        assert a["scope"] == "line"
        assert a["effect"] == "STOP_MOVED"
        assert a["description"].startswith("Přesun")
        assert board(timetable, feed(route), line="8")["alerts"] == []
        assert board(timetable, feed(route), direction="Jiný směr")["alerts"] == []
    assert not board(timetable, feed("unmatched"))["alerts"]


def test_selector_and_and_station_platform_scope(timetable):
    assert board(timetable, feed(stop="A"), stop="P")["alerts"]
    assert not board(timetable, feed(stop="B"), stop="A")["alerts"]
    assert board(timetable, feed(stop="P"), stop="A")["alerts"]
    assert not board(timetable, feed(route="8", stop="A"))["alerts"]
    f = feed(route="8", stop="B")
    f.entity[0].alert.informed_entity.add(route_id="501")
    assert board(timetable, f)["alerts"]  # OR across distinct selectors
    f.entity[0].alert.informed_entity[1].agency_id = "unsupported"
    assert not board(timetable, f)["alerts"]  # unknown fields cannot widen scope


def test_alert_expiry_freshness_and_removed_feed(timetable):
    now = int(time.time())
    assert not board(timetable, feed(start=now + 3600))["alerts"]
    assert not board(timetable, feed(end=now - 1))["alerts"]
    assert board(timetable, feed(start=now - 100, end=now + 100))["alerts"]
    rt = Realtime()
    f = feed()
    f.header.timestamp = now - 1000
    rt.ingest(f.SerializeToString())
    result = timetable.board_alerts("A", rt, datetime.now(TZ))
    assert result["alerts_stale"] and result["alerts"] == []
    f = feed()
    rt.ingest(f.SerializeToString())
    f.ClearField("entity")
    rt.ingest(f.SerializeToString())
    assert not timetable.board_alerts("A", rt, datetime.now(TZ))["alerts"]


def test_alert_content_key_and_unsafe_links(timetable):
    f = feed()
    first = board(timetable, f)["alerts"][0]
    f.entity[0].id = "lockout_99"
    assert board(timetable, f)["alerts"][0]["key"] == first["key"]
    f.entity[0].alert.description_text.translation[0].text = "Jiná výluka"
    assert board(timetable, f)["alerts"][0]["key"] != first["key"]
    for url in ("javascript:alert(1)", "http://[invalid"):
        f.entity[0].alert.url.translation[0].text = url
        assert board(timetable, f)["alerts"][0]["url"] is None


def test_alerts_in_same_json_independent_of_departure_limit(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data", download_enabled=False, realtime_enabled=True))
    with TestClient(app) as client:
        app.state.timetable.import_zip(archive(tmp_path / "feed.zip"))
        message = feed()
        message.entity[0].alert.description_text.translation[0].text = "<p>Výluka <b>linky 501</b>.</p>"
        app.state.realtime.ingest(message.SerializeToString())
        data = client.get("/api/v1/stops/A/departures?limit=1&horizon=1").json()
        assert data["realtime_enabled"]
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["description"] == "Výluka linky 501."
        assert data["alerts"][0]["description_html"] == "<p>Výluka <strong>linky 501</strong>.</p>"
        assert not data["alerts_stale"] and data["alerts_updated_at"]
        assert client.get("/api/v1/stops/A/departures?line=8").json()["alerts"] == []


def test_disabled_realtime_omits_data_even_if_snapshot_is_present(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data", download_enabled=False, realtime_enabled=False))
    with TestClient(app) as client:
        app.state.timetable.import_zip(archive(tmp_path / "feed.zip"))
        f = feed()
        vehicle = f.entity.add(id="vehicle").vehicle
        vehicle.trip.trip_id = "T"
        vehicle.position.latitude = 49
        vehicle.position.longitude = 16
        vehicle.timestamp = f.header.timestamp
        update = f.entity.add(id="update").trip_update
        update.trip.trip_id = "T"
        update.trip.schedule_relationship = pb.TripDescriptor.CANCELED
        app.state.realtime.ingest(f.SerializeToString())
        data = client.get("/api/v1/stops/A/departures?horizon=2880&previous_limit=1").json()
        assert data["realtime_enabled"] is False
        assert not {"alerts", "alerts_stale", "alerts_updated_at", "realtime_stale"} & data.keys()
        assert data["departures"]
        for d in data["departures"] + data["previous_departures"]:
            assert d["source"] == "schedule"
            assert (
                not {
                    "delay_seconds",
                    "estimated_departure",
                    "cancelled",
                    "vehicle_id",
                    "has_vehicle_position",
                    "realtime_updated_at",
                }
                & d.keys()
            )
        trip = client.get("/api/v1/trips/T?service_date=2026-10-11").json()
        assert trip["realtime_enabled"] is False and "vehicles" not in trip
        assert trip["stops"]
        assert client.get("/api/v1/vehicles").json() == {"realtime_enabled": False, "vehicles": []}
        assert client.get("/api/v1/status").json()["realtime"] == {"enabled": False}


def test_disabled_realtime_does_not_download_but_gtfs_does(tmp_path, monkeypatch):
    payload = archive(tmp_path / "feed.zip").read_bytes()
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, content=payload)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "api.main.httpx.AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handle)),
    )
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            realtime_enabled=False,
            gtfs_url="https://example.test/schedule",
            realtime_url="https://example.test/realtime",
        )
    )
    with TestClient(app) as client:
        for _ in range(100):
            if client.get("/health/ready").status_code == 200:
                break
            time.sleep(0.01)
        assert client.get("/health/ready").status_code == 200
    assert calls == ["/schedule"]


def test_realtime_environment_default_and_opt_in():
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env.pop("REALTIME_ENABLED", None)
    code = "from api.config import Settings; print(Settings().realtime_enabled)"
    assert subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip() == "False"
    env["REALTIME_ENABLED"] = "true"
    assert subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip() == "True"
