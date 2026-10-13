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
    estimated_departure: str | None = None
    departure_time: str = Field(description="Odhadovaný čas, je-li dostupný, jinak plánovaný.")
    departure_time_display: str = Field(description="Čas HH:MM pro jednoduché dashboardy.")
    minutes_until: int = Field(description="Minuty do odjezdu zaokrouhlené nahoru v okamžiku generated_at.")
    delay_seconds: int | None = None
    source: Literal["schedule", "trip_update", "vehicle_estimate"]
    realtime_updated_at: str | None = None
    cancelled: bool | None = Field(
        default=None, description="null znamená, že zrušení není potvrzeno ani vyvráceno."
    )
    vehicle_id: str | None = None
    has_vehicle_position: bool = Field(
        default=False,
        description=(
            "Pro tento provozní den je dostupná čerstvá použitelná poloha v detailu spoje; "
            "nezávisí na odhadu zpoždění."
        ),
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


class ServiceAlert(BaseModel):
    id: str
    key: str = Field(description="Obsahový klíč pro sloučení stejného upozornění z více tabulí.")
    title: str
    description: str
    title_html: str | None = Field(default=None, description="Nadpis s omezeným HTML bez atributů.")
    description_html: str | None = Field(
        default=None, description="Popis s odstavci, zvýrazněním a seznamy; omezené HTML bez atributů."
    )
    url: str | None
    cause: str
    effect: str
    scope: Literal["line", "stop", "trip", "mixed"]
    lines: list[str]
    matched_lines: list[str]
    affected_entities: list[dict]
    active_period: list[dict[str, int]] = Field(
        description="Intervaly platnosti, Unix sekundy; prázdné = dokud je ve feedu."
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
    realtime_enabled: bool
    realtime_stale: bool = False
    alerts: list[ServiceAlert] = Field(
        default_factory=list,
        description="Upozornění pro zastávku a filtry, nezávisle na limitu odjezdů.",
    )
    alerts_stale: bool = Field(
        default=False,
        description="Při neaktuálním zdroji je alerts prázdné; nejde o potvrzení provozu bez omezení.",
    )
    alerts_updated_at: str | None = None


class MapSelection(BaseModel):
    route_id: str = Field(min_length=1, max_length=200)
    direction: str = Field(default="*", max_length=20)
