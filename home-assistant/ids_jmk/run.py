"""Translate Supervisor options and replace the launcher with an unprivileged API."""

import json
import os
import socket
import sys
from pathlib import Path

INTERVALS = {
    "gtfs_interval_seconds": (86400, 3600),
    "realtime_interval_seconds": (60, 15),
    "realtime_max_age_seconds": (180, 30),
    "realtime_idle_timeout_seconds": (300, 0),
}


def options_environment(options):
    if not isinstance(options, dict):
        raise ValueError("Nastavení aplikace musí být objekt JSON.")
    realtime = options.get("realtime_enabled", False)
    if type(realtime) is not bool:
        raise ValueError("Volba realtime_enabled musí být přepínač.")
    environment = {"REALTIME_ENABLED": str(realtime).lower()}
    for key, (default, minimum) in INTERVALS.items():
        value = options.get(key, default)
        if type(value) is not int or value < minimum:
            raise ValueError(f"Volba {key} musí být celé číslo nejméně {minimum}.")
        environment[key.upper()] = str(value)
    return environment


def main():
    # Fail closed if Supervisor's configuration is missing or malformed.
    options = json.loads(Path("/data/options.json").read_text())
    os.environ.update(options_environment(options))
    data = Path("/data/parser")
    data.mkdir(exist_ok=True)
    os.chown(data, 10001, 10001)
    os.environ["DATA_DIR"] = str(data)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)
    hostname = socket.gethostname().replace("_", "-")
    print(f"Adresa API pro integraci na tomto HA: http://{hostname}:8080", flush=True)
    print("Při prvním spuštění vyčkejte na dokončení importu jízdních řádů.", flush=True)
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0",
        "--port", "8080", "--workers", "1", "--no-access-log",
    ])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Aplikaci nelze spustit. Zkontrolujte nastavení a datový adresář: {exc}") from exc
