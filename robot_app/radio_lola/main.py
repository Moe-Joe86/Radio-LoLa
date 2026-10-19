"""Purpose: the radio as a Reachy Mini app: one antenna tunes stations, the other sets the volume.

API: `RadioLola`; started and stopped by the daemon (POST /api/apps/start-app/radio_lola, /api/apps/stop-current-app).
Must not: repeat sound, leave the robot with its antennas switched off.
"""
# Runs on the robot in Pollen's apps_venv: the daemon starts the app as `python -m radio_lola.main` and stops it with
# SIGINT; after 20 s without an end it kills it. The SDK is connected locally, so all moves go straight through the
# SDK. `enable_motors()` without names is the same in the daemon as REST `set_mode/enabled` (all targets are set to
# the measured position, nothing jerks), and `goto_target` waits until the move is done (daemon code 1.12.0).
# Antennas in the SDK: [right, left] in radians, matching motors 17 and 18 (`right_antenna`, `left_antenna`). The
# right one (on the left seen from the front) tunes, the left one (on the right seen from the front) is the volume;
# both motors are off while playing.
# The phone app talks to the app's web server (port 8042, `control.py`). When it picks a station or a volume, the
# `driver` thread drives the matching antenna there; the radio itself only listens to the antennas. Before an
# antenna motor is switched on, its target is set to the measured position: the daemon keeps writing the target
# even while the motor is off, otherwise the antenna would jump to the old target (daemon code 1.12.0).
# A station counts as audible once it is at least half against the noise. Noise is made here with numpy (it comes
# with reachy-mini); the other files stay testable without any dependency.

import logging
import math
import signal
import sys
import threading
import time
from collections.abc import Callable

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp

from radio_lola.antennas import best_route, duration, moves, way_home
from radio_lola.control import STATION, Control, add_routes
from radio_lola.settings import Settings, load
from radio_lola.stations import Stations
from radio_lola.stream import BYTES_PER_SAMPLE, SAMPLE_RATE, Stream, missing_capabilities
from radio_lola.tuning import approach, directed, level, station_target, volume, volume_target

BLOCK = 1024  # samples per push, 64 ms
NOISE = 0.3  # strength of the white noise (standard deviation)
TUNING, VOLUME = 0, 1  # index of the antennas in the SDK
ANTENNAS = ["right_antenna", "left_antenna"]

log = logging.getLogger("radio")


def bring_home(mini: ReachyMini) -> None:
    """All motors on, read the position and bring the antennas home one after the other (`antennas.py`)."""
    mini.enable_motors()
    now = tuple(math.degrees(a) for a in mini.get_present_antenna_joint_positions())
    log.info("Radio: antennas at %.0f° / %.0f° after switching on", *now)
    for target in way_home(*now):
        log.info("Radio: antennas move to %.0f° / %.0f°", *target)
        mini.goto_target(antennas=[math.radians(a) for a in target], duration=duration(now, target), body_yaw=None)
        now = target


def wake(mini: ReachyMini) -> None:
    bring_home(mini)
    mini.wake_up()
    mini.goto_target(antennas=[0.0, 0.0], duration=0.5, body_yaw=None)
    mini.disable_motors(ANTENNAS)
    log.info("Radio: awake, antennas free")


def drive_antennas(mini: ReachyMini, plan: list[tuple[int, float]]) -> None:
    """Drives the moves from `antennas.moves`; only the named antenna has power meanwhile, then it is free again.

    Every move measures afresh: the other antenna gets its measured position as target, never a planned value,
    because two readings of the same resting antenna already differ by a fraction of a degree.
    """
    for which, where in plan:
        now = [math.degrees(a) for a in mini.get_present_antenna_joint_positions()]
        target = list(now)
        target[which] = where
        mini.set_target(antennas=[math.radians(a) for a in now])
        time.sleep(0.1)  # a few daemon ticks, so the target reaches the motor
        mini.enable_motors([ANTENNAS[which]])
        try:
            mini.goto_target(antennas=[math.radians(a) for a in target], duration=duration(now, target),
                             body_yaw=None)
        finally:
            mini.disable_motors([ANTENNAS[which]])


def carry_out(mini: ReachyMini, s: Settings, stations: Stations, kind: str, value: float) -> None:
    now = [math.degrees(a) for a in mini.get_present_antenna_joint_positions()]
    if kind == STATION:
        names = stations.names()
        index = int(value)
        if index >= len(names):  # the list got shorter in the meantime
            return
        nearest = station_target(index, len(names), now[TUNING], s.span, s.direction)
        detour = nearest - 360.0 if nearest > now[TUNING] else nearest + 360.0
        plan = best_route(TUNING, [nearest, detour], *now)
        log.info("Radio: phone picks %s, moves %s", names[index], plan)
    else:
        plan = moves(VOLUME, volume_target(value, now[VOLUME]), *now)
        log.info("Radio: phone sets volume %.0f %%, moves %s", value * 100, plan)
    drive_antennas(mini, plan)


def driver(mini: ReachyMini, s: Settings, control: Control, end: threading.Event) -> None:
    """Own thread: carries out wishes from the phone, so the sound keeps playing meanwhile."""
    while not end.is_set():
        wish = control.next_wish(0.2)
        if wish is None:
            continue
        try:
            carry_out(mini, s, control.stations, *wish)
        except Exception:  # a failed wish must not end the radio
            log.exception("Radio: antenna move failed")


def mix(stream: Stream | None, share: float, noise: np.ndarray, loudness: np.ndarray) -> np.ndarray:
    music = np.zeros(BLOCK, np.float32) if stream is None else np.frombuffer(stream.read(BLOCK * BYTES_PER_SAMPLE),
                                                                           np.float32)
    return np.clip((share * music + (1 - share) * noise) * loudness, -1, 1).astype(np.float32)


def play(mini: ReachyMini, s: Settings, end: threading.Event, control: Control,
         new_stream: Callable[[str], Stream] | None = None) -> None:
    open_stream = new_stream or Stream
    rng, stream, loud = np.random.default_rng(), None, 0.0
    clock = time.monotonic()
    try:
        while not end.is_set():
            angles = [math.degrees(a) for a in mini.get_present_antenna_joint_positions()]
            stations = control.stations.all()
            index, share = level(directed(angles[TUNING], s.direction), len(stations), s.span, s.crossfade)
            url = None if index is None else stations[index][1]
            if url != (stream.url if stream else None):  # switch in the middle of a noise field, where it is silent
                if stream is not None:
                    stream.stop()
                stream = None if url is None else open_stream(url)
                if stream is not None:
                    log.info("Radio: station %s", stations[index][0])
                    stream.start()
            control.report(url if share >= 0.5 else None, volume(angles[VOLUME]))
            new = approach(loud, 0.0 if control.muted() else volume(angles[VOLUME]) * s.max_volume)
            noise = rng.standard_normal(BLOCK, dtype=np.float32) * np.float32(NOISE)
            ramp = np.linspace(loud, new, BLOCK, dtype=np.float32)  # gliding within the block, without clicks
            mini.media.push_audio_sample(mix(stream, share, noise, ramp))
            loud = new
            clock += BLOCK / SAMPLE_RATE
            wait = clock - time.monotonic()
            if wait < -1.0:  # far behind, e.g. after a hiccup: reset the clock instead of catching up
                clock = time.monotonic()
            end.wait(max(0.0, wait))
    finally:
        if stream is not None:
            stream.stop()


class RadioLola(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"  # web server for the phone app (`control.py`)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        # Messages go to stdout; stderr stays for errors, whose last lines the daemon reports as the reason.
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stdout)
        s = load()
        control = Control(Stations(s.stations))
        log.info("Radio: started, %d stations", len(control.stations.all()))
        if self.settings_app is not None:
            add_routes(self.settings_app, control)
        try:
            missing = missing_capabilities()
        except Exception as error:  # only information for the log, must not prevent the start
            missing = [f"check impossible ({error})"]
        if missing:
            log.warning("Radio: GStreamer on this robot cannot do: %s", ", ".join(missing))
        thread = threading.Thread(target=driver, args=(reachy_mini, s, control, stop_event), name="driver")
        try:
            wake(reachy_mini)
            reachy_mini.media.start_playing()
            thread.start()
            play(reachy_mini, s, stop_event, control)
        finally:
            stop_event.set()
            if thread.is_alive():
                thread.join(timeout=10)  # let a running move finish
            bring_home(reachy_mini)
            reachy_mini.media.stop_playing()
            log.info("Radio: stopped, antennas home, motors on")


if __name__ == "__main__":
    app = RadioLola()
    # The daemon stops the app with SIGINT. Instead of breaking off in the middle of a move, the loop ends cleanly
    # and the antennas go home.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: app.stop_event.set())
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
