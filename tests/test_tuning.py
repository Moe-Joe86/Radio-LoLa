import pytest

from radio_lola.tuning import (
    HIGHEST,
    approach,
    directed,
    field,
    level,
    station_target,
    volume,
    volume_target,
)

STATION, NOISE = "station", ("noise", None)


def test_one_station_half_circle_station_half_noise():
    assert field(0, 1) == (STATION, 0)
    assert field(179.9, 1) == (STATION, 0)
    assert field(180, 1) == NOISE
    assert field(359.9, 1) == NOISE


@pytest.mark.parametrize(("angle", "expected"), [
    (0, (STATION, 0)), (44.9, (STATION, 0)), (45, NOISE), (89.9, NOISE),
    (90, (STATION, 1)), (135, NOISE), (180, (STATION, 2)), (225, NOISE),
    (270, (STATION, 3)), (314.9, (STATION, 3)), (315, NOISE), (359.9, NOISE),
])
def test_four_stations_in_fields_of_45_degrees(angle, expected):
    """The start belongs to the field, the end does not."""
    assert field(angle, 4) == expected


@pytest.mark.parametrize(("angle", "same"), [(360, 0), (405, 45), (450, 90), (720 + 100, 100), (-45, 315),
                                             (-90, 270), (-360, 0), (-1, 359)])
def test_angles_above_360_or_negative(angle, same):
    assert field(angle, 4) == field(same, 4)
    assert level(angle, 4, crossfade=6) == level(same, 4, crossfade=6)


def test_counting_direction_reverses_the_angle():
    assert directed(30, 1) == 30
    assert directed(30, -1) == 330
    assert directed(-400, 1) == 320


def test_limited_span_only_splits_that_span():
    """270° for 3 stations: fields of 45°, everything from 270° on is noise."""
    assert field(0, 3, 270) == (STATION, 0)
    assert field(45, 3, 270) == NOISE
    assert field(90, 3, 270) == (STATION, 1)
    assert field(180, 3, 270) == (STATION, 2)
    assert field(225, 3, 270) == NOISE
    assert field(270, 3, 270) == NOISE
    assert field(300, 3, 270) == NOISE


def test_without_stations_only_noise():
    assert field(10, 0) == NOISE
    assert level(10, 0, crossfade=6) == (None, 0.0)


def test_without_crossfade_hard_like_the_fields():
    for tenth in range(3600):
        angle = tenth / 10
        kind, index = field(angle, 4)
        station, share = level(angle, 4)
        assert share == (1.0 if kind == STATION else 0.0), angle
        if kind == STATION:
            assert station == index


@pytest.mark.parametrize(("angle", "expected"), [
    (45, (0, 0.5)), (42, (0, 1.0)), (43.5, (0, 0.75)), (46.5, (0, 0.25)), (48, (0, 0.0)), (67, (0, 0.0)),
    (90, (1, 0.5)), (88.5, (1, 0.25)), (91.5, (1, 0.75)), (0, (0, 0.5)), (358.5, (0, 0.25)), (1.5, (0, 0.75)),
])
def test_crossfade_at_the_field_edges(angle, expected):
    """6° crossfade: half and half at the edge, 3° further in only station, 3° further out only noise."""
    station, share = level(angle, 4, crossfade=6)
    assert (station, round(share, 6)) == expected


def test_crossfade_does_not_jump_when_jittering():
    """A small move at the edge changes the share only a little."""
    before = level(44.8, 4, crossfade=6)[1]
    after = level(45.2, 4, crossfade=6)[1]
    assert abs(before - after) < 0.1


def test_limited_span_also_fades_across_zero():
    """With 270°, noise outside the span lies before 0°; station 0 still fades in smoothly."""
    assert level(359, 3, 270, 6) == (0, pytest.approx(1 / 3))
    assert level(280, 3, 270, 6) == (2, 0.0)


@pytest.mark.parametrize(("raw", "share"), [
    (0, 0.0), (-90, 0.25), (-180, 0.5), (-270, 0.75), (1, 359 / 360), (360, 0.0), (-450, 0.25), (90, 0.75),
])
def test_volume_rises_counter_clockwise_jump_at_the_top(raw, share):
    assert volume(raw) == pytest.approx(share)


def test_volume_follows_smoothly():
    steps = [0.0]
    for _ in range(25):
        steps.append(approach(steps[-1], 1.0))
    assert all(abs(b - a) <= 0.05 + 1e-9 for a, b in zip(steps, steps[1:], strict=False))
    assert steps[-1] == pytest.approx(1.0)
    assert approach(0.5, 0.52) == pytest.approx(0.52)
    assert approach(0.5, 0.0) == pytest.approx(0.45)


@pytest.mark.parametrize(("index", "now", "target"), [(0, 0, 22.5), (1, 0, 112.5), (3, 0, -67.5), (2, 1000, 922.5),
                                                      (0, -700, -697.5)])
def test_station_target_is_the_field_middle_the_short_way(index, now, target):
    assert station_target(index, 4, now) == pytest.approx(target)
    assert field(station_target(index, 4, now), 4) == ("station", index)
    assert level(station_target(index, 4, now), 4, crossfade=6) == (index, 1.0)


def test_station_target_with_direction_and_span():
    raw = station_target(1, 3, 0, span=270, direction=-1)
    assert level(directed(raw, -1), 3, 270, 6) == (1, 1.0)


@pytest.mark.parametrize(("share", "now"), [(0.25, 90), (0.9, -10), (0.0, -300), (1.0, -20), (0.5, 1000)])
def test_volume_target_hits_without_crossing_the_jump(share, now):
    target = volume_target(share, now)
    assert volume(target) == pytest.approx(min(share, HIGHEST))
    between = [volume(now + (target - now) * k / 20) for k in range(21)]
    assert between == sorted(between) or between == sorted(between, reverse=True)
