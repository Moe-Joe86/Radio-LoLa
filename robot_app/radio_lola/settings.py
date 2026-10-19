"""Purpose: reads the radio settings from `settings.toml` next to this file and checks them.

API: `load`, `check_station`, `parse_stations`, `Settings`, `FILE`.
Must not: write anything; standard library only.
"""
# Missing values take the default. Faulty or unknown values stop the start with a clear message instead of quietly
# using a default; the message shows up in the daemon log and in the phone app. The stations in the file are only
# the starting list: from the first start on, the robot keeps its own list (`stations.py`), managed from the phone.

import tomllib
from dataclasses import dataclass
from pathlib import Path

FILE = Path(__file__).with_name("settings.toml")
DEFAULTS = {"station": [], "max_volume": 60, "span_deg": 360, "direction": 1, "crossfade_deg": 6}
MAX_STATIONS = 8
MAX_NAME = 40


@dataclass(frozen=True)
class Settings:
    stations: list[tuple[str, str]]  # (name, url), the starting list
    max_volume: float  # 0 to 1
    span: float  # usable angle of the tuning antenna in degrees
    direction: int  # +1 or -1: counting direction of the tuning antenna
    crossfade: float  # width of the crossfade at field edges in degrees


def check_station(name: object, url: object, label: str = "station") -> tuple[str, str]:
    """(name, url) cleaned up, or ValueError with a readable reason."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{label}: name is missing")
    if len(name.strip()) > MAX_NAME:
        raise ValueError(f"{label}: name is longer than {MAX_NAME} characters")
    if not isinstance(url, str) or not url.strip().startswith(("http://", "https://")):
        raise ValueError(f"{label} “{name.strip()}”: url does not start with http:// or https://")
    return name.strip(), url.strip()


def parse_stations(entries: object) -> list[tuple[str, str]]:
    """The [[station]] blocks as a list of (name, url)."""
    if not isinstance(entries, list):
        raise ValueError("station: every station needs its own [[station]] block with name and url")
    if len(entries) > MAX_STATIONS:
        raise ValueError(f"station: at most {MAX_STATIONS} stations, found {len(entries)}")
    stations = []
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"station no. {number}: name is missing")
        unknown = sorted(set(entry) - {"name", "url"})
        if unknown:
            raise ValueError(f"station no. {number}: unknown key {', '.join(unknown)}")
        stations.append(check_station(entry.get("name"), entry.get("url"), f"station no. {number}"))
    return stations


def _number(values: dict, name: str, smallest: float, largest: float) -> float:
    number = values[name]
    if isinstance(number, bool) or not isinstance(number, int | float):
        raise ValueError(f"{name}: “{number}” is not a number")
    if not smallest <= number <= largest:
        raise ValueError(f"{name}: {number:g} is not between {smallest:g} and {largest:g}")
    return float(number)


def load(file: Path = FILE) -> Settings:
    try:
        read = tomllib.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{file.name}: syntax error ({error})") from None
    unknown = set(read) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"{file.name}: unknown setting {', '.join(sorted(unknown))}")
    values = DEFAULTS | read
    if values["direction"] not in (1, -1) or isinstance(values["direction"], bool):
        raise ValueError(f"direction: “{values['direction']}”, allowed are 1 and -1")
    return Settings(
        stations=parse_stations(values["station"]),
        max_volume=_number(values, "max_volume", 0, 100) / 100,
        span=_number(values, "span_deg", 10, 360),
        direction=int(values["direction"]),
        crossfade=_number(values, "crossfade_deg", 0, 30),
    )
