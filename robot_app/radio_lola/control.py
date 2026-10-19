"""Purpose: interface for the phone app: pick a station, set the volume, mute, manage stations, report the state.

API: `Control` (`report`, `state`, `muted`, `set_muted`, `wish_station`, `wish_volume`, `next_wish`,
`add_station`, `delete_station`), `add_routes`.
Must not: touch hardware or sound; station and volume are set by the antennas alone, the phone only asks for them.
"""
# The antennas stay the single source of truth: when the phone picks a station or a volume, `main.py` drives the
# matching antenna there, and the radio listens to the antennas as always. A new wish replaces one of the same kind
# that has not started yet. Mute is only a switch in the sound and lasts until the radio stops. Adding or removing
# a station shifts all fields on the antenna, so the tuning antenna is then driven back to the station that was
# playing (or, if that one was removed, to the one now in its place). The routes hang on the web server that
# Pollen's ReachyMiniApp starts for `custom_app_url` (port 8042).

import threading

from radio_lola.stations import Stations

STATION, VOLUME = "station", "volume"


class Control:
    def __init__(self, stations: Stations) -> None:
        self.stations = stations
        self._lock = threading.Lock()
        self._new = threading.Condition(self._lock)
        self._active_url: str | None = None
        self._volume = 0
        self._muted = False
        self._wishes: dict[str, float] = {}

    def report(self, active_url: str | None, volume_share: float) -> None:
        """What the antennas say right now: url of the audible station (None in noise) and volume 0 to 1."""
        with self._lock:
            self._active_url, self._volume = active_url, round(volume_share * 100)

    def _active_index(self, stations: list[tuple[str, str]]) -> int | None:
        with self._lock:
            url = self._active_url
        return next((i for i, (_, u) in enumerate(stations) if u == url), None)

    def state(self) -> dict:
        stations = self.stations.all()
        active = self._active_index(stations)
        with self._lock:
            return {"stations": [name for name, _ in stations], "active": active, "volume": self._volume,
                    "muted": self._muted}

    def muted(self) -> bool:
        with self._lock:
            return self._muted

    def set_muted(self, on: bool) -> None:
        with self._lock:
            self._muted = on

    def wish_station(self, index: int) -> None:
        if not 0 <= index < len(self.stations.all()):
            raise ValueError(f"there is no station {index}")
        self._wish(STATION, index)

    def wish_volume(self, value: int) -> None:
        if not 0 <= value <= 100:
            raise ValueError(f"volume: {value} is not between 0 and 100")
        self._wish(VOLUME, value / 100)

    def _wish(self, kind: str, value: float) -> None:
        with self._new:
            self._wishes[kind] = value
            self._new.notify()

    def next_wish(self, timeout: float) -> tuple[str, float] | None:
        """Oldest open wish (kind, value), or None if none arrived within `timeout` seconds."""
        with self._new:
            if not self._wishes:
                self._new.wait(timeout)
            if not self._wishes:
                return None
            kind = next(iter(self._wishes))
            return kind, self._wishes.pop(kind)

    def add_station(self, url: str, name: str | None = None, **probe) -> str:
        """Adds a station (see `Stations.add`) and keeps the playing station under the antenna; returns its name."""
        playing = self._active_index(self.stations.all())
        _, added = self.stations.add(url, name, **probe)
        if playing is not None:
            self._wish(STATION, playing)
        return added

    def delete_station(self, index: int) -> str:
        """Removes a station and drives the antenna to the playing one, or to the one taking its place."""
        before = self.stations.all()
        playing = self._active_index(before)
        removed = self.stations.delete(index)
        if playing is not None:
            after = len(before) - 1
            self._wish(STATION, min(index, after - 1) if playing == index else playing - (playing > index))
        return removed


def add_routes(app, control: Control) -> None:
    """GET /radio; POST /radio/station {"index"}, /radio/volume {"value": 0…100}, /radio/mute {"on"},
    /radio/stations/add {"url", "name"?}, /radio/stations/delete {"index"}."""
    from fastapi import HTTPException
    from pydantic import BaseModel, Field

    class Station(BaseModel):
        index: int

    class Volume(BaseModel):
        value: int = Field(ge=0, le=100)

    class Mute(BaseModel):
        on: bool

    class NewStation(BaseModel):
        url: str
        name: str | None = None

    def asking(action) -> dict:
        try:
            action()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        return control.state()

    @app.get("/radio")
    def radio() -> dict:
        return control.state()

    @app.post("/radio/station")
    def station(data: Station) -> dict:
        return asking(lambda: control.wish_station(data.index))

    @app.post("/radio/volume")
    def volume(data: Volume) -> dict:
        return asking(lambda: control.wish_volume(data.value))

    @app.post("/radio/mute")
    def mute(data: Mute) -> dict:
        return asking(lambda: control.set_muted(data.on))

    @app.post("/radio/stations/add")
    def add(data: NewStation) -> dict:
        return asking(lambda: control.add_station(data.url, data.name))

    @app.post("/radio/stations/delete")
    def delete(data: Station) -> dict:
        return asking(lambda: control.delete_station(data.index))
