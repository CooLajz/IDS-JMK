from typing import Literal

from pydantic import BaseModel, Field

from .transport import TransportMode


class StopSummary(BaseModel):
    id: str
    name: str


class Departure(BaseModel):
    trip_id: str
    service_date: str = Field(
        description="Provozní den spoje, YYYY-MM-DD; po půlnoci může být předchozí den."
    )
    stop_id: str
    stop_sequence: int
    line: str
    route_type: int = Field(description="Původní GTFS route_type z routes.txt; druh dopravy dané linky.")
    transport_mode: TransportMode = Field(
        description="Normalizovaný druh dopravy, např. tram (šalina), bus, rail nebo trolleybus."
    )
    destination: str
    platform: str
    scheduled_departure: str = Field(description="ISO 8601 včetně offsetu Europe/Prague.")
    estimated_departure: str | None
    departure_time: str = Field(description="Odhadovaný čas, je-li dostupný, jinak plánovaný.")
    departure_time_display: str = Field(description="Čas HH:MM pro jednoduché dashboardy.")
    minutes_until: int = Field(description="Minuty do odjezdu zaokrouhlené nahoru v okamžiku generated_at.")
    delay_seconds: int | None
    source: Literal["schedule", "trip_update", "vehicle_estimate"]
    realtime_updated_at: str | None
    cancelled: bool | None = Field(description="null znamená, že zrušení není potvrzeno ani vyvráceno.")
    vehicle_id: str | None
    has_vehicle_position: bool = Field(
        description=(
            "Pro tento provozní den je dostupná čerstvá použitelná poloha v detailu spoje; "
            "nezávisí na odhadu zpoždění."
        )
    )
    wheelchair_accessible: bool | None = Field(
        description=(
            "Vozidlo přístupné vozíčkářům podle GTFS jízdního řádu; null = neuvedeno. Neověřuje nástupiště."
        )
    )
    bikes_allowed: bool | None = Field(
        description=(
            "Možnost přepravy kol podle GTFS jízdního řádu; null = neuvedeno. Neurčuje volnou kapacitu."
        )
    )


class DepartureBoard(BaseModel):
    stop: StopSummary
    generated_at: str
    timezone: str
    departures: list[Departure]
    previous_departures: list[Departure] = Field(
        description=(
            "Volitelné minulé odjezdy za posledních 24 hodin, nejnovější první. "
            "Nejde o potvrzení skutečného odjezdu ani archiv realtime dat."
        )
    )
    realtime_stale: bool
