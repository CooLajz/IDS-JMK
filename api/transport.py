"""Stable transport names derived from GTFS route types, never line numbers."""

from typing import Literal

TransportMode = Literal[
    "tram", "subway", "rail", "bus", "ferry", "cable_tram", "aerial_lift",
    "funicular", "trolleybus", "monorail", "unknown",
]

BASIC_TYPES: dict[int, TransportMode] = {
    0: "tram", 1: "subway", 2: "rail", 3: "bus", 4: "ferry", 5: "cable_tram",
    6: "aerial_lift", 7: "funicular", 11: "trolleybus", 12: "monorail",
}


def transport_mode(route_type: int) -> TransportMode:
    """Preserve unknown raw codes in the API; normalize supported extended types."""
    if route_type in BASIC_TYPES:
        return BASIC_TYPES[route_type]
    # Extended GTFS/HVT codes: https://developers.google.com/transit/gtfs/reference/extended-route-types
    if 100 <= route_type <= 117 or route_type in (400, 403, 404):
        return "rail"
    if 200 <= route_type <= 209 or 700 <= route_type <= 716:
        return "bus"
    if 900 <= route_type <= 906:
        return "tram"
    return {
        401: "subway", 402: "subway", 405: "monorail", 800: "trolleybus",
        1000: "ferry", 1200: "ferry", 1300: "aerial_lift", 1301: "aerial_lift",
        1302: "aerial_lift", 1304: "aerial_lift", 1305: "aerial_lift",
        1306: "aerial_lift", 1307: "aerial_lift", 1400: "funicular",
    }.get(route_type, "unknown")
