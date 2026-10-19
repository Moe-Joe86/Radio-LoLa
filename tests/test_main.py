import math
import threading

import numpy as np
import pytest

from radio_lola import main, stations
from radio_lola.control import Control
from radio_lola.settings import Settings
from radio_lola.stations import Stations

DEG = math.pi / 180


class Media:
    """Stand-in for `mini.media`: collects the sound blocks and signals the end after `blocks` blocks."""

    def __init__(self, end: threading.Event, blocks: int, on_block=None) -> None:
        self.end, self.blocks, self.on_block = end, blocks, on_block
        self.played, self.running = [], False

    def start_playing(self) -> None:
        self.running = True

    def stop_playing(self) -> None:
        self.running = False

    def push_audio_sample(self, block: np.ndarray) -> None:
        self.played.append(block)
        if self.on_block is not None:
            self.on_block(len(self.played))
        if len(self.played) >= self.blocks:
            self.end.set()


class Mini:
    """Stand-in for `ReachyMini`, antennas in radians, every move ends up in the log.

    As on the robot: readings jitter by `jitter` degrees, only antennas with power follow `goto_target`, and giving
    power to an antenna whose target is not its position makes it jump (`jumps`).
    """

    NAMES = {"right_antenna": 0, "left_antenna": 1}

    def __init__(self, right: float, left: float, media: Media | None = None, jitter: float = 0.0) -> None:
        self.antennas = [right * DEG, left * DEG]
        self.target, self.power = list(self.antennas), [True, True]
        self.jitter, self._readings, self.jumps = jitter, 0, []
        self.log: list[tuple] = []
        self.media = media

    def _which(self, ids) -> list[int]:
        return [0, 1] if ids is None else [self.NAMES[name] for name in ids]

    def enable_motors(self, ids=None) -> None:
        self.log.append(("on", ids))
        if ids is None:  # all motors: the daemon first sets every target to the position (daemon code 1.12.0)
            self.target = list(self.antennas)
        for i in self._which(ids):
            if not self.power[i] and abs(self.target[i] - self.antennas[i]) > 0.5 * DEG:
                self.jumps.append(i)
                self.antennas[i] = self.target[i]
            self.power[i] = True

    def disable_motors(self, ids=None) -> None:
        self.log.append(("off", ids))
        for i in self._which(ids):
            self.power[i] = False

    def get_present_antenna_joint_positions(self) -> list[float]:
        self._readings += 1
        noise = self.jitter * DEG * (1 if self._readings % 2 else -1)
        return [a + noise for a in self.antennas]

    def set_target(self, head=None, antennas=None, body_yaw=None) -> None:
        self.log.append(("target", tuple(round(a / DEG, 1) for a in antennas)))
        self.target = list(antennas)

    def goto_target(self, head=None, antennas=None, duration=0.5, body_yaw=0.0) -> None:
        assert head is None and body_yaw is None, "the radio only moves the antennas"
        self.log.append(("move", tuple(round(a / DEG, 1) for a in antennas), round(duration, 2)))
        self.target = list(antennas)
        for i in (0, 1):
            if self.power[i]:
                self.antennas[i] = antennas[i]

    def wake_up(self) -> None:
        self.log.append(("wake",))
        self.antennas = [-10 * DEG, 10 * DEG]
        self.target = list(self.antennas)

    def degrees(self) -> tuple[float, float]:
        return tuple(round(a / DEG, 1) for a in self.antennas)


class Stream:
    """Stand-in for `stream.Stream`: delivers constant sound and remembers start and stop."""

    all: list["Stream"] = []

    def __init__(self, url: str) -> None:
        self.url, self.started, self.stopped = url, False, False
        Stream.all.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def read(self, byte_count: int) -> bytes:
        return np.full(byte_count // 4, 0.5, np.float32).tobytes()


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    Stream.all = []
    monkeypatch.setattr(stations, "FILE", tmp_path / "stations.json")


ONE = [("One", "https://one.example/")]
TWO = ONE + [("Two", "https://two.example/")]
SETTINGS = Settings(stations=[], max_volume=1.0, span=360, direction=1, crossfade=0)


def control(station_list=ONE) -> Control:
    return Control(Stations(station_list))


def free(right: float, left: float, jitter: float = 0.0) -> Mini:
    """As while playing: both antennas without power, their last target was the home position."""
    mini = Mini(right, left, jitter=jitter)
    mini.target, mini.power = [0.0, 0.0], [False, False]
    return mini


def test_bring_home_switches_on_first_then_one_after_the_other():
    mini = Mini(1086.3, -1443.6)
    main.bring_home(mini)
    assert mini.log == [("on", None), ("move", (1086.3, -1440.0), 0.3), ("move", (0.0, -1440.0), 3.02),
                        ("move", (0.0, 0.0), 4.0)]


def test_wake_brings_home_wakes_and_frees_the_antennas():
    mini = Mini(45, 0)
    main.wake(mini)
    assert mini.log == [("on", None), ("move", (0.0, 0.0), 0.3), ("wake",), ("move", (0.0, 0.0), 0.5),
                        ("off", ["right_antenna", "left_antenna"])]


def test_play_mixes_station_and_volume_smoothly():
    end = threading.Event()
    mini = Mini(90, -180, Media(end, 5))  # station 0 in the middle of its field, volume half
    main.play(mini, SETTINGS, end, control(), Stream)
    blocks = mini.media.played
    assert len(blocks) == 5 and all(b.dtype == np.float32 and b.shape == (main.BLOCK,) for b in blocks)
    assert blocks[0][0] == 0.0  # starts silent and gets louder by at most 0.05 per block
    assert blocks[-1][-1] == pytest.approx(0.5 * 0.25)
    assert [s.url for s in Stream.all] == ["https://one.example/"]
    assert Stream.all[0].started and Stream.all[0].stopped


def test_in_a_noise_field_only_noise():
    """The nearest station already runs along but cannot be heard: the block is pure noise around zero."""
    end = threading.Event()
    mini = Mini(270, -270, Media(end, 20))
    main.play(mini, SETTINGS, end, control(), Stream)
    last = mini.media.played[-1]
    assert abs(float(np.mean(last))) < 0.05 < float(np.std(last))


def test_changing_station_stops_the_old_stream():
    end = threading.Event()
    mini = Mini(45, -90, None)

    def turn(count: int) -> None:
        if count == 2:
            mini.antennas[main.TUNING] = 225 * DEG  # middle of station 1 with four fields

    mini.media = Media(end, 4, turn)
    main.play(mini, SETTINGS, end, control(TWO), Stream)
    assert [s.url for s in Stream.all] == ["https://one.example/", "https://two.example/"]
    assert all(s.stopped for s in Stream.all)


def test_mute_means_silence_and_the_volume_comes_from_the_antenna():
    end, quiet = threading.Event(), control()
    quiet.set_muted(True)
    mini = Mini(90, -180, Media(end, 3))
    main.play(mini, SETTINGS, end, quiet, Stream)
    assert all(float(np.max(np.abs(b))) == 0.0 for b in mini.media.played)
    assert quiet.state()["volume"] == 50  # the antenna is at half


def test_reports_the_audible_station_and_noise():
    end, c = threading.Event(), control(TWO)
    main.play(Mini(225, -90, Media(end, 2)), SETTINGS, end, c, Stream)  # middle of station 1
    assert c.state()["active"] == 1
    end.clear()
    main.play(Mini(135, -90, Media(end, 2)), SETTINGS, end, c, Stream)  # middle of a noise field
    assert c.state()["active"] is None


def test_a_station_added_while_playing_takes_effect_at_once():
    end, c = threading.Event(), control(TWO)
    mini = Mini(225, -90, None)  # station 1 of two

    def add(count: int) -> None:
        if count == 2:
            c.add_station("https://three.example/", "Three", check=lambda u: (u, None))
            mini.antennas[main.TUNING] = 300 * DEG  # middle of station 2 of three

    mini.media = Media(end, 4, add)
    main.play(mini, SETTINGS, end, c, Stream)
    assert [s.url for s in Stream.all] == ["https://two.example/", "https://three.example/"]


def test_run_ends_with_antennas_home_and_motors_on(monkeypatch):
    app = main.RadioLola()
    mini = Mini(30, 60, Media(app.stop_event, 3))
    monkeypatch.setattr(main, "Stream", Stream)
    monkeypatch.setattr(main, "missing_capabilities", lambda: [])

    def twist(count: int) -> None:
        mini.antennas = [400 * DEG, -30 * DEG]  # turned by hand while listening

    mini.media.on_block = twist
    app.run(mini, app.stop_event)
    after_playing = mini.log[mini.log.index(("off", main.ANTENNAS)) + 1:]
    # Left points inward and parks at the top first, then right turns home across one turn (`antennas.way_home`);
    # the last short move only evens out the rounding left over from radians to degrees.
    assert after_playing == [("on", None), ("move", (400.0, 0.0), 0.3), ("move", (0.0, 0.0), 1.11),
                             ("move", (0.0, 0.0), 0.3)]
    assert mini.antennas == [0.0, 0.0] and not mini.media.running


def test_an_error_while_playing_still_brings_the_antennas_home(monkeypatch):
    app = main.RadioLola()
    mini = Mini(0, 0, Media(app.stop_event, 100))
    monkeypatch.setattr(main, "Stream", Stream)
    monkeypatch.setattr(main, "missing_capabilities", lambda: [])

    def broken(block):
        mini.antennas = [100 * DEG, 0.0]
        raise RuntimeError("sound gone")

    mini.media.push_audio_sample = broken
    with pytest.raises(RuntimeError, match="sound gone"):
        app.run(mini, app.stop_event)
    assert mini.log[-3:] == [("on", None), ("move", (360.0, 0.0), 0.72), ("move", (0.0, 0.0), 1.0)]
    assert mini.antennas == [0.0, 0.0]


def test_faulty_settings_move_nothing(monkeypatch, tmp_path):
    file = tmp_path / "settings.toml"
    file.write_text("direction = 3\n", encoding="utf-8")
    load = main.load
    monkeypatch.setattr(main, "load", lambda: load(file))
    app = main.RadioLola()
    mini = Mini(0, 0, Media(app.stop_event, 1))
    with pytest.raises(ValueError, match="direction"):
        app.run(mini, app.stop_event)
    assert mini.log == []


def test_phone_picks_station_only_the_tuning_antenna_gets_power():
    mini = free(10, 30)  # the volume antenna points outward: one move is enough
    main.carry_out(mini, SETTINGS, Stations(TWO), "station", 1)
    # The middle of station 1 is at 225°, i.e. −135°: shortest way backwards across zero; right may go inward here
    assert mini.log == [("target", (10.0, 30.0)), ("on", ["right_antenna"]), ("move", (-135.0, 30.0), 0.4),
                        ("off", ["right_antenna"])]
    assert mini.degrees() == (-135.0, 30.0) and mini.jumps == []


def test_phone_sets_volume_only_the_volume_antenna_moves():
    mini = free(300, 90)  # volume 75 %, tuning antenna outward
    main.carry_out(mini, SETTINGS, Stations(ONE), "volume", 0.25)
    assert mini.log[1:] == [("on", ["left_antenna"]), ("move", (300.0, 270.0), 0.5), ("off", ["left_antenna"])]
    assert main.volume(mini.degrees()[main.VOLUME]) == pytest.approx(0.25)


@pytest.mark.parametrize(("kind", "value", "moved"), [("volume", 0.8, 1), ("volume", 0.3, 1),
                                                       ("station", 1, 0), ("station", 0, 0)])
def test_measurement_noise_does_not_mix_up_the_antennas(kind, value, moved):
    """Bug of 18 October: two readings of the same resting antenna differ by a fraction of a degree, and the radio
    then gave power to the wrong antenna. Now only the intended one moves and none jumps."""
    mini = free(300, 120, jitter=0.04)
    before = mini.degrees()
    main.carry_out(mini, SETTINGS, Stations(TWO), kind, value)
    switched_on = {tuple(entry[1]) for entry in mini.log if entry[0] == "on"}
    assert switched_on == {(main.ANTENNAS[moved],)}
    assert mini.jumps == []
    assert mini.degrees()[1 - moved] == before[1 - moved]
    assert mini.degrees()[moved] != before[moved]


def test_inner_antenna_parks_only_when_there_is_no_way_round_the_outside():
    mini = free(300, 270, jitter=0.04)  # volume points inward, station 0 lies inward on the right at 45°
    main.carry_out(mini, SETTINGS, Stations(TWO), "station", 0)
    switched_on = [entry[1][0] for entry in mini.log if entry[0] == "on"]
    assert switched_on == ["left_antenna", "right_antenna", "left_antenna"]
    assert mini.jumps == []
    assert mini.degrees() == (405.0, 270.0)


def test_station_outside_goes_round_the_outside_instead_of_parking():
    mini = free(200, 270)  # volume inward; station 1 at 225° lies outside, the short way does not pass the inside
    main.carry_out(mini, SETTINGS, Stations(TWO), "station", 1)
    assert [entry[1][0] for entry in mini.log if entry[0] == "on"] == ["right_antenna"]


def test_a_wish_for_a_station_that_was_removed_meanwhile_is_ignored():
    mini = free(10, 30)
    main.carry_out(mini, SETTINGS, Stations(ONE), "station", 1)
    assert mini.log == []


def test_driver_carries_out_wishes_and_ends_with_the_radio():
    end, c, mini = threading.Event(), control(TWO), free(10, 30)
    thread = threading.Thread(target=main.driver, args=(mini, SETTINGS, c, end))
    thread.start()
    c.wish_station(1)
    for _ in range(50):
        if ("off", ["right_antenna"]) in mini.log:
            break
        threading.Event().wait(0.02)
    end.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert mini.degrees() == (-135.0, 30.0)
