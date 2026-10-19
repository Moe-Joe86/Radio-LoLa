"""Purpose: receives a radio stream via GStreamer as 16 kHz mono and keeps a short buffer ready.

API: `Stream` (`start`, `read`, `stop`, `step`), `gstreamer_source`, `missing_capabilities`, `Broken`.
Must not: repeat sound (missing audio becomes silence), use new dependencies (GStreamer comes with reachy-mini).
"""
# When the stream breaks (error, end or 5 s without sound), `step` reconnects: first after 1 s, then with doubled
# waiting time up to 30 s. The buffer holds at most 2 s; anything older is dropped. Data is float32 (4 bytes per
# sample), without numpy, so this file stays testable without the robot.

import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 4
BUFFER_SECONDS = 2.0
SILENCE_LIMIT = 5.0  # this long without sound counts as a broken stream
FIRST_WAIT, LONGEST_WAIT = 1.0, 30.0

log = logging.getLogger("radio.stream")


class Broken(Exception):
    """The source reports an error or the end of the stream."""


class Source(Protocol):
    def read(self, timeout: float) -> bytes: ...
    def close(self) -> None: ...


class _GstSource:
    def __init__(self, url: str) -> None:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        self._gst = Gst
        self._pipeline = Gst.parse_launch(
            f'uridecodebin uri="{url}" ! audioconvert ! audioresample ! '
            f"audio/x-raw,format=F32LE,channels=1,rate={SAMPLE_RATE},layout=interleaved ! "
            "appsink name=sink sync=false max-buffers=50 drop=true"
        )
        self._sink = self._pipeline.get_by_name("sink")
        self._pipeline.set_state(Gst.State.PLAYING)

    def read(self, timeout: float) -> bytes:
        gst = self._gst
        message = self._pipeline.get_bus().pop_filtered(gst.MessageType.ERROR | gst.MessageType.EOS)
        if message is not None:
            reason = message.parse_error()[0].message if message.type == gst.MessageType.ERROR else "end of stream"
            raise Broken(reason)
        sample = self._sink.emit("try-pull-sample", int(timeout * 1e9))
        if sample is None:
            return b""
        buffer = sample.get_buffer()
        return buffer.extract_dup(0, buffer.get_size())

    def close(self) -> None:
        self._pipeline.set_state(self._gst.State.NULL)


def gstreamer_source(url: str) -> Source:
    return _GstSource(url)


# Which GStreamer elements exist on the robot is not measured; per capability one of the elements is enough.
CAPABILITIES = {
    "basic elements": (("uridecodebin",), ("audioconvert",), ("audioresample",), ("appsink",)),
    "receiving via http/https": (("souphttpsrc",),),
    "MP3": (("mpg123audiodec", "avdec_mp3", "mad"),),
    "AAC": (("avdec_aac", "faad", "fdkaacdec"),),
}


def missing_capabilities(available: Callable[[str], bool] | None = None) -> list[str]:
    """Names of the capabilities in `CAPABILITIES` for which a GStreamer element is missing; empty if all exist."""
    if available is None:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        available = lambda name: Gst.ElementFactory.find(name) is not None  # noqa: E731
    return [name for name, groups in CAPABILITIES.items()
            if not all(any(available(e) for e in group) for group in groups)]


class Stream:
    def __init__(self, url: str, open_source: Callable[[str], Source] = gstreamer_source,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.url, self._open, self._clock = url, open_source, clock
        self._source: Source | None = None
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._end = threading.Event()
        self._wait = FIRST_WAIT
        self._next_attempt = 0.0
        self._last_sound = 0.0
        self.attempts = 0

    def step(self) -> None:
        """One unit of work: connect when it is time, otherwise read and detect breaks."""
        now = self._clock()
        if self._source is None:
            if now >= self._next_attempt:
                self._connect(now)
            return
        try:
            data = self._source.read(0.2)
        except Broken as error:
            self._disconnect(f"broke off ({error})")
            return
        if data:
            self._last_sound, self._wait = now, FIRST_WAIT
            with self._lock:
                self._buffer += data
                del self._buffer[: max(0, len(self._buffer) - int(BUFFER_SECONDS * SAMPLE_RATE * BYTES_PER_SAMPLE))]
        elif now - self._last_sound > SILENCE_LIMIT:
            self._disconnect(f"no sound for {SILENCE_LIMIT:g} s")

    def _connect(self, now: float) -> None:
        self.attempts += 1
        try:
            self._source = self._open(self.url)
            self._last_sound = now
        except Exception as error:  # GStreamer raises various errors; each one means: try again later
            self._source = None
            self._schedule(now, f"unreachable ({error})")

    def _disconnect(self, reason: str) -> None:
        if self._source is not None:
            self._source.close()
        self._source = None
        self._schedule(self._clock(), reason)

    def _schedule(self, now: float, reason: str) -> None:
        log.warning("Radio: %s %s, retrying in %g s", self.url, reason, self._wait)
        self._next_attempt = now + self._wait
        self._wait = min(self._wait * 2, LONGEST_WAIT)

    def read(self, byte_count: int) -> bytes:
        """Exactly `byte_count` bytes: whatever is buffered, the rest silence. Nothing is ever returned twice."""
        with self._lock:
            data = bytes(self._buffer[:byte_count])
            del self._buffer[:byte_count]
        return data + bytes(byte_count - len(data))

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name=f"stream {self.url}").start()

    def stop(self) -> None:
        """Returns at once; the receiver closes in its own thread."""
        self._end.set()

    def _run(self) -> None:
        while not self._end.is_set():
            self.step()
            if self._source is None:
                self._end.wait(0.1)
        if self._source is not None:
            self._source.close()
