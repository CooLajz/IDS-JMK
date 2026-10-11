import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    gtfs_url: str = os.getenv("GTFS_URL", "https://kordis-jmk.cz/gtfs/gtfs.zip")
    realtime_url: str = os.getenv("REALTIME_URL", "https://kordis-jmk.cz/gtfs/gtfsReal.dat")
    gtfs_interval: int = max(3600, int(os.getenv("GTFS_INTERVAL_SECONDS", "86400")))
    realtime_interval: int = max(15, int(os.getenv("REALTIME_INTERVAL_SECONDS", "60")))
    realtime_max_age: int = max(30, int(os.getenv("REALTIME_MAX_AGE_SECONDS", "180")))
    download_enabled: bool = os.getenv("DOWNLOAD_ENABLED", "true").lower() == "true"
