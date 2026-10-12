import asyncio
import gzip
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.downloads import SourceDownloader
from api.gtfs import TZ
from api.main import create_app
from api.statistics import Statistics

URL = "https://source.example/feed"
MODIFIED = "Mon, 12 Oct 2026 06:00:00 GMT"


def test_conditional_download_survives_restart_and_counts_compressed_bytes(tmp_path):
    stats = Statistics(tmp_path)
    data = gzip.compress(b"valid feed" * 100)
    seen, accepted = [], []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(
                200,
                headers={"ETag": 'W/"one"', "Last-Modified": MODIFIED, "Content-Encoding": "gzip"},
                stream=httpx.ByteStream(data),
            )
        return httpx.Response(304, headers={"ETag": 'W/"one"'})

    async def accept(path):
        accepted.append(path.read_bytes())
        return "local-valid-feed"

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for i in range(2):
                # New store/downloader objects model a process restart with restored local data.
                downloader = SourceDownloader(Statistics(tmp_path))
                assert await downloader.update(
                    client,
                    "gtfs",
                    URL,
                    tmp_path / "download",
                    5000,
                    lambda: "local-valid-feed" if i else None,
                    accept,
                ) == (i == 0)

    asyncio.run(run())
    assert accepted == [b"valid feed" * 100]
    assert "if-none-match" not in seen[0].headers
    assert seen[1].headers["if-none-match"] == 'W/"one"'
    assert seen[1].headers["if-modified-since"] == MODIFIED
    assert seen[1].headers["cache-control"] == "no-cache"
    snapshot = stats.snapshot("day", datetime.now(TZ).date())
    totals = snapshot["totals"]["gtfs"]
    assert (totals["requests"], totals["downloads"], totals["not_modified"], totals["bytes"]) == (
        2,
        1,
        1,
        len(data),
    )
    assert not (tmp_path / "download").exists()
    assert snapshot["sources"]["gtfs"]["last_downloaded_at"]
    assert "etag" not in snapshot["sources"]["gtfs"]


@pytest.mark.parametrize("change", ["missing_cache", "changed_url", "changed_local_data"])
def test_validators_are_not_used_without_matching_local_source(tmp_path, change):
    stats = Statistics(tmp_path)
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, headers={"ETag": '"version"'}, stream=httpx.ByteStream(b"ok"))

    async def accept(path):
        return "original"

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            dl = SourceDownloader(stats)
            await dl.update(client, "realtime", URL, tmp_path / "d", 100, lambda: None, accept)
            identity = (
                None if change == "missing_cache" else "new" if change == "changed_local_data" else "original"
            )
            await dl.update(
                client,
                "realtime",
                URL + ("2" if change == "changed_url" else ""),
                tmp_path / "d",
                100,
                lambda: identity,
                accept,
            )

    asyncio.run(run())
    assert "if-none-match" not in seen[1].headers


def test_failed_import_keeps_old_validators_and_retries_bad_version(tmp_path):
    stats, seen = Statistics(tmp_path), []

    def handler(request):
        seen.append(request)
        tag = '"good"' if len(seen) == 1 else '"bad"'
        return httpx.Response(200, headers={"ETag": tag}, stream=httpx.ByteStream(tag.encode()))

    async def accept(path):
        if path.read_bytes() == b'"bad"':
            raise ValueError("Invalid archive")
        return "good-local"

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            dl = SourceDownloader(stats)
            await dl.update(client, "gtfs", URL, tmp_path / "d", 100, lambda: None, accept)
            for _ in range(2):
                with pytest.raises(ValueError):
                    await dl.update(client, "gtfs", URL, tmp_path / "d", 100, lambda: "good-local", accept)

    asyncio.run(run())
    assert [r.headers.get("if-none-match") for r in seen] == [None, '"good"', '"good"']
    assert stats.source_state("gtfs")["etag"] == '"good"'
    totals = stats.snapshot("year", date.today())["totals"]["gtfs"]
    assert totals["requests"] == totals["downloads"] == 3
    assert totals["errors"] == 2


@pytest.mark.parametrize("kind", ["oversize", "304_without_cache", "http_error", "connection_error"])
def test_download_failures_count_requests_without_accepted_files(tmp_path, kind):
    stats = Statistics(tmp_path)

    def handler(request):
        if kind == "connection_error":
            raise httpx.ConnectError("Failed", request=request)
        status = {"oversize": 200, "304_without_cache": 304, "http_error": 503}[kind]
        return httpx.Response(status, stream=httpx.ByteStream(b"oversized" if status == 200 else b""))

    async def accept(path):
        pytest.fail("Failed downloads must never be accepted")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises((ValueError, httpx.HTTPError)):
                await SourceDownloader(stats).update(
                    client, "gtfs", URL, tmp_path / "d", 2, lambda: None, accept
                )

    asyncio.run(run())
    totals = stats.snapshot("day", datetime.now(TZ).date())["totals"]["gtfs"]
    assert (totals["requests"], totals["downloads"], totals["not_modified"], totals["errors"]) == (1, 0, 0, 1)
    assert totals["bytes"] == (9 if kind == "oversize" else 0)
    assert not (tmp_path / "d").exists()


@pytest.mark.parametrize("day,count", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
def test_statistics_local_calendar_handles_dst_and_month_year_totals(tmp_path, day, count):
    stats = Statistics(tmp_path)
    start = datetime.combine(day, datetime.min.time(), TZ).timestamp()
    for hour in range(count):
        stats.record("gtfs", at=start + hour * 3600, requests=1, downloads=hour % 2, bytes=10)
    # Following local day must not leak into this day; it is included in month and year.
    stats.record("gtfs", at=start + count * 3600, requests=7)
    result = stats.snapshot("day", day)
    assert len(result["series"]) == count
    assert len({r["start"] for r in result["series"]}) == count
    assert result["totals"]["gtfs"]["requests"] == count
    assert stats.snapshot("month", day)["totals"]["gtfs"]["requests"] == count + 7
    assert stats.snapshot("year", day)["totals"]["gtfs"]["requests"] == count + 7
    assert stats.snapshot("day", day.replace(day=1))["totals"]["gtfs"]["requests"] == 0


def test_api_counts_only_external_requests_and_never_persists_query_or_client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, download_enabled=False))
    with TestClient(app) as client:
        client.get("/health/live")
        client.get("/api/v1/status", headers={"X-IDS-JMK-Client": "web"})
        client.get("/api/v1/statistics", headers={"X-IDS-JMK-Client": "web"})
        client.get("/api/v1/status")
        client.get("/api/v1/stops?query=secret-stop&limit=0")
        client.get("/api/v1/secret-unknown?token=secret-token")
        response = client.get("/api/v1/statistics", headers={"X-IDS-JMK-Client": "web"})
        result = response.json()
        assert result["totals"]["api"]["requests"] == 3
        assert result["totals"]["api"]["errors"] == 2
        assert {r["endpoint"] for r in result["api_endpoints"]} == {
            "GET /api/v1/status",
            "GET /api/v1/stops",
            "GET unmatched",
        }
        for param in ["period=invalid", "date=wrong", "date=9999-01-01"]:
            assert client.get(f"/api/v1/statistics?{param}").status_code == 422
    with app.state.statistics.connect() as db:
        assert "secret" not in " ".join(db.iterdump())


def test_parallel_api_counters_are_persistent(tmp_path):
    stats = Statistics(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: stats.record_api("GET /api/v1/status", 200), range(100)))
    assert Statistics(tmp_path).snapshot("year", datetime.now(TZ).date())["totals"]["api"]["requests"] == 100


def test_realtime_cache_restores_after_restart_without_refreshing_vehicle_timestamp(tmp_path):
    import hashlib
    import time

    from google.transit import gtfs_realtime_pb2 as pb

    from api.downloads import source_key

    feed = pb.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(time.time()) - 600
    data = feed.SerializeToString()
    (tmp_path / "realtime-cache.dat").write_bytes(data)
    stats = Statistics(tmp_path)
    stats.record(
        "realtime",
        state={
            "url_key": source_key(URL),
            "cache_identity": hashlib.sha256(data).hexdigest(),
            "etag": '"cached"',
        },
    )
    settings = Settings(data_dir=tmp_path, realtime_enabled=True, realtime_url=URL, download_enabled=False)
    app = create_app(settings)
    rt = app.state.realtime
    assert rt.snapshot.timestamp == feed.header.timestamp
    assert not rt.fresh(rt.snapshot.timestamp, time.time())
    with TestClient(app) as client:
        assert client.get("/api/v1/status").json()["realtime"]["stale"]
    (tmp_path / "realtime-cache.dat").write_bytes(b"corrupted")
    assert create_app(settings).state.realtime.snapshot.timestamp == 0
    (tmp_path / "realtime-cache.dat").write_bytes(data)
    assert (
        create_app(
            Settings(data_dir=tmp_path, realtime_enabled=False, download_enabled=False)
        ).state.realtime.snapshot.timestamp
        == 0
    )


def test_both_real_http_sources_return_304_after_application_restart(tmp_path):
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from google.transit import gtfs_realtime_pb2 as pb
    from test_api import archive

    feed = pb.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = int(time.time()) - 30
    bodies = {"/gtfs": archive(tmp_path / "fixture.zip").read_bytes(), "/rt": feed.SerializeToString()}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            unchanged = self.headers.get("If-None-Match") == '"one"'
            self.send_response(304 if unchanged else 200)
            self.send_header("ETag", '"one"')
            self.send_header("Last-Modified", MODIFIED)
            if not unchanged:
                self.send_header("Content-Length", str(len(bodies[self.path])))
            self.end_headers()
            if not unchanged:
                self.wfile.write(bodies[self.path])

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    settings = Settings(
        data_dir=tmp_path / "store",
        gtfs_url=base + "/gtfs",
        realtime_url=base + "/rt",
        realtime_enabled=True,
        download_enabled=True,
    )
    try:
        for count in (1, 2):
            app = create_app(settings)
            with TestClient(app):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    snapshot = app.state.statistics.snapshot("day", datetime.now(TZ).date())
                    if all(
                        snapshot["totals"][source]["requests"] == count for source in ("gtfs", "realtime")
                    ):
                        break
                    time.sleep(0.01)
                else:
                    pytest.fail("Source loops did not finish")
                assert app.state.timetable.ready
                assert app.state.realtime.snapshot.timestamp == feed.header.timestamp
                for source in ("gtfs", "realtime"):
                    assert snapshot["totals"][source]["downloads"] == 1
                    assert snapshot["totals"][source]["not_modified"] == count - 1
                    assert snapshot["totals"][source]["errors"] == 0
            if count == 1:
                first = snapshot["sources"]
            else:
                assert all(
                    snapshot["sources"][s]["last_downloaded_at"] == first[s]["last_downloaded_at"]
                    for s in ("gtfs", "realtime")
                )
        for path in bodies:
            matching = [headers for p, headers in requests if p == path]
            assert len(matching) == 2
            assert matching[1]["If-None-Match"] == '"one"'
            assert matching[1]["If-Modified-Since"] == MODIFIED
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
