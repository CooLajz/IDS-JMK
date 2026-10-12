"""Service alerts with conservative GTFS selectors and the KORDIS line-name fallback."""

import hashlib
import json
from urllib.parse import urlsplit

from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2 as pb


def translated(value):
    return next(
        (t.text for t in value.translation if t.language.startswith("cs")),
        next((t.text for t in value.translation), ""),
    )


def parse_alert(entity):
    a = entity.alert
    url = translated(a.url)
    try:
        if urlsplit(url).scheme.lower() not in ("http", "https"):
            url = None
    except ValueError:
        url = None
    result = {
        "id": entity.id,
        "title": translated(a.header_text),
        "description": translated(a.description_text),
        "url": url,
        "cause": pb.Alert.Cause.Name(a.cause),
        "effect": pb.Alert.Effect.Name(a.effect),
        "affected_entities": [MessageToDict(s, preserving_proto_field_name=True) for s in a.informed_entity],
        "active_period": [{d.name: int(v) for d, v in p.ListFields()} for p in a.active_period],
    }
    # Producer IDs may be positional. Content keys also deduplicate across board sensors.
    content = {k: v for k, v in result.items() if k != "id"}
    content["affected_entities"] = sorted(
        content["affected_entities"], key=lambda s: json.dumps(s, sort_keys=True)
    )
    result["key"] = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return result


def select_alerts(alerts, contexts, routes, now):
    routes = dict(routes)

    def matches(selector, row):
        # Do not broaden selectors containing fields we cannot resolve (e.g. agency).
        if not selector or set(selector) - {"route_id", "route_type", "stop_id", "direction_id", "trip"}:
            return False
        route = selector.get("route_id")
        if route is not None:
            if route in routes:
                if route != row["route_id"]:
                    return False
            elif route.casefold() != row["line"].casefold():
                return False
        if "route_type" in selector and selector["route_type"] != row["type"]:
            return False
        if "direction_id" in selector and str(selector["direction_id"]) != str(row["direction"]):
            return False
        if "stop_id" in selector and selector["stop_id"] not in (row["stop_id"], row["parent"]):
            return False
        if "trip" in selector:
            trip = selector["trip"]
            if set(trip) != {"trip_id"} or trip["trip_id"] != row["trip_id"]:
                return False
        return True

    output = []
    seen = set()
    for alert in alerts:
        periods = alert["active_period"]
        if periods and not any(p.get("start", 0) <= now < p.get("end", float("inf")) for p in periods):
            continue
        matched = [(s, row) for s in alert["affected_entities"] for row in contexts if matches(s, row)]
        if not matched or alert["key"] in seen:
            continue
        seen.add(alert["key"])
        scopes = {"trip" if "trip" in s else "stop" if "stop_id" in s else "line" for s, _ in matched}
        output.append(
            {
                **alert,
                "scope": next(iter(scopes)) if len(scopes) == 1 else "mixed",
                "lines": sorted(
                    {
                        routes.get(s["route_id"], s["route_id"])
                        for s in alert["affected_entities"]
                        if "route_id" in s
                    }
                ),
                "matched_lines": sorted({row["line"] for _, row in matched}),
            }
        )
    return output
