"""Check a running API/web pair and optionally verify persistent identity after restart."""

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8090")
parser.add_argument("--state", type=Path)
parser.add_argument("--verify-state", action="store_true")
parser.add_argument("--api-only", action="store_true")
parser.add_argument("--timeout", type=int, default=240)
args = parser.parse_args()
base = args.url.rstrip("/")


def get(path):
    with urllib.request.urlopen(base + path, timeout=15) as response:
        return response.read()


def api(path):
    return json.loads(get("/api/v1/" + path))


for attempt in range(max(1, args.timeout // 2)):
    try:
        status = api("status")
        if status["ready"]:
            break
    except (OSError, ValueError, urllib.error.HTTPError):
        pass
    time.sleep(2)
else:
    raise SystemExit("API nebylo připravené do časového limitu")

stops = api("stops?query=Nebovidy")["stops"]
assert stops, "Vyhledání zastávky nevrátilo data"
stop = api("stops/" + urllib.parse.quote(stops[0]["id"], safe=""))
path = "stops/" + urllib.parse.quote(stop["id"], safe="") + "/departures"
board = api(path + "?limit=3")
assert board["stop"]["id"] == stop["id"]
assert board["previous_departures"] == []
assert len(board["departures"]) <= 3
with_previous = api(path + "?limit=3&previous_limit=1")
assert len(with_previous["previous_departures"]) <= 1
for row in board["departures"]:
    trip = api(
        "trips/" + urllib.parse.quote(row["trip_id"], safe="") + "?service_date=" + row["service_date"]
    )
    assert trip["active"] and trip["stops"]
assert json.loads(get("/openapi.json"))["info"]["version"] == status["version"]
assert b"swagger" in get("/docs").lower()
if not args.api_only:
    html = get("/").decode()
    assert "Odjezdy" in html and "API URL / JSON" in html
snapshot = {"instance_id": status["instance_id"], "schema_version": status["schedule"]["schema_version"]}
if args.state:
    if args.verify_state:
        assert snapshot == json.loads(args.state.read_text()), "Identita nebo schéma se po restartu změnily"
    else:
        args.state.write_text(json.dumps(snapshot))
print(
    json.dumps(
        {
            "ok": True,
            "version": status["version"],
            "stops": len(stops),
            "departures": len(board["departures"]),
            "realtime_enabled": status["realtime"]["enabled"],
            "realtime_stale": status["realtime"].get("stale"),
            "persistent_identity_verified": args.verify_state,
        },
        ensure_ascii=False,
    )
)
