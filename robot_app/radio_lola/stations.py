"""Purpose: keeps the station list on the robot, survives updates, and adds or removes stations for the phone.

API: `Stations` (`all`, `names`, `add`, `delete`), `probe`, `FILE`.
Must not: touch hardware or sound; standard library only.
"""
# The list lives outside the installed package, so reinstalling the app does not overwrite it. On the first start it
# is filled from the starting list in settings.toml. Before a station is added, `probe` connects to the url once:
# it must answer with audio (playlists .m3u/.pls are followed to their first entry), and many stations send their
# name in the `icy-name` header. A name typed on the phone wins, then the station's own name, then the host name.

import json
import logging
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from radio_lola.settings import MAX_NAME, MAX_STATIONS, check_station

FILE = Path.home() / ".config" / "radio_lola" / "stations.json"
PLAYLISTS = ("mpegurl", "x-scpls", "pls")
AUDIO = ("audio/", "application/ogg", "application/octet-stream")

log = logging.getLogger("radio.stations")


def _playlist_entry(text: str) -> str | None:
    """First stream url in an .m3u or .pls playlist."""
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("file") and "=" in line:
            line = line.split("=", 1)[1].strip()
        if line.startswith(("http://", "https://")):
            return line
    return None


def probe(url: str, timeout: float = 6.0, depth: int = 0) -> tuple[str, str | None]:
    """(stream url, station name or None) after connecting once; ValueError if nothing playable answers."""
    request = urllib.request.Request(url, headers={"Icy-MetaData": "1", "User-Agent": "RadioLoLa/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            kind = (answer.headers.get("Content-Type") or "").lower()
            name = (answer.headers.get("icy-name") or "").strip()
            is_playlist = any(p in kind for p in PLAYLISTS) or urlparse(url).path.lower().endswith((".m3u", ".pls"))
            if is_playlist:
                inner = _playlist_entry(answer.read(65536).decode("utf-8", "replace"))
                if inner is None or depth >= 2:
                    raise ValueError("the playlist contains no stream url")
                return probe(inner, timeout, depth + 1)
            if not kind.startswith(AUDIO) and not any(h.lower().startswith("icy-") for h in answer.headers):
                raise ValueError(f"this is not an audio stream (content type “{kind or 'unknown'}”)")
    except OSError as error:
        raise ValueError(f"the stream does not answer ({error})") from None
    return url, (name[:MAX_NAME] if name and name.lower() not in ("no name", "unspecified name") else None)


class Stations:
    def __init__(self, starting: list[tuple[str, str]], file: Path | None = None) -> None:
        self._file, self._lock = file or FILE, threading.Lock()
        self._list = self._read() or list(starting)
        if not self._file.exists():
            self._save()

    def _read(self) -> list[tuple[str, str]]:
        try:
            stored = json.loads(self._file.read_text(encoding="utf-8"))
            return [check_station(s["name"], s["url"]) for s in stored][:MAX_STATIONS]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, KeyError, TypeError) as error:
            log.warning("Radio: station list %s unreadable (%s), using the starting list", self._file, error)
            return []

    def _save(self) -> None:
        with self._lock:
            data = [{"name": name, "url": url} for name, url in self._list]
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            spare = self._file.with_suffix(".tmp")
            spare.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            spare.replace(self._file)
        except OSError as error:  # then the change only lasts until the radio stops
            log.warning("Radio: station list not saved (%s)", error)

    def all(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self._list)

    def names(self) -> list[str]:
        return [name for name, _ in self.all()]

    def add(self, url: str, name: str | None = None,
            check: Callable[[str], tuple[str, str | None]] = probe) -> tuple[int, str]:
        """Checks the stream and appends it; (index, name) of the new station."""
        if len(self.all()) >= MAX_STATIONS:
            raise ValueError(f"at most {MAX_STATIONS} stations; remove one first")
        if not url.strip().startswith(("http://", "https://")):
            raise ValueError("the address must start with http:// or https://")
        stream, own_name = check(url.strip())
        chosen = (name or "").strip() or own_name or urlparse(stream).hostname or stream
        station = check_station(chosen[:MAX_NAME], stream)
        with self._lock:
            if any(existing == stream for _, existing in self._list):
                raise ValueError(f"“{station[0]}” is already in the list")
            if len(self._list) >= MAX_STATIONS:
                raise ValueError(f"at most {MAX_STATIONS} stations; remove one first")
            self._list.append(station)
            index = len(self._list) - 1
        self._save()
        log.info("Radio: station added: %s (%s)", *station)
        return index, station[0]

    def delete(self, index: int) -> str:
        """Removes station `index`; the last remaining station stays."""
        with self._lock:
            if not 0 <= index < len(self._list):
                raise ValueError(f"there is no station {index}")
            if len(self._list) == 1:
                raise ValueError("the last station cannot be removed")
            name, _ = self._list.pop(index)
        self._save()
        log.info("Radio: station removed: %s", name)
        return name
