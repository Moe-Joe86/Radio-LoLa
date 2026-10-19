import pytest

from radio_lola.antennas import (
    LEFT,
    RIGHT,
    best_route,
    duration,
    enters_inside,
    moves,
    points_inward,
    to_top,
    way_home,
)


@pytest.mark.parametrize(("index", "raw", "inward"), [
    (RIGHT, 90, True), (RIGHT, 10, True), (RIGHT, -10, False), (RIGHT, 270, False), (RIGHT, 0, False),
    (RIGHT, 1080, False), (RIGHT, 1086, True), (RIGHT, 450, True),
    (LEFT, 270, True), (LEFT, -10, True), (LEFT, 10, False), (LEFT, 90, False),
    (LEFT, -1440, False), (LEFT, -1444, True),
])
def test_inward_means_towards_the_other_antenna(index, raw, inward):
    assert points_inward(index, raw) is inward


@pytest.mark.parametrize(("index", "raw", "target"), [
    (RIGHT, 45, 0), (RIGHT, 135, 360), (RIGHT, 270, 360), (RIGHT, 1086, 1080), (RIGHT, 720, 720),
    (LEFT, 315, 360), (LEFT, 225, 0), (LEFT, 90, 0), (LEFT, -1444, -1440),
])
def test_to_top_leaves_the_inner_half_the_short_way(index, raw, target):
    assert to_top(index, raw) == target


def test_never_both_at_once():
    before = (1086.0, -1444.0)
    for target in way_home(*before):
        assert sum(a != b for a, b in zip(before, target, strict=True)) == 1
        before = target


def test_inner_antenna_parks_first_then_the_other_fully_then_the_first():
    """Right points inward (45°), left outward (90°): right parks at the top, left turns home, then right."""
    assert way_home(45.0, 90.0) == [(0.0, 90.0), (0.0, 0.0)]
    assert way_home(405.0, 450.0) == [(360.0, 450.0), (360.0, 0.0), (0.0, 0.0)]


def test_readings_from_15_october():
    """+1086° and −1444°: both nearly up, each 4 to 6° inward; left parks, right turns home, then left."""
    assert way_home(1086.3, -1443.6) == [(1086.3, -1440.0), (0.0, -1440.0), (0.0, 0.0)]


def test_both_inward_left_parks_first():
    assert way_home(90.0, 270.0) == [(90.0, 0.0), (0.0, 0.0)]


def test_already_home_nothing_to_do():
    assert way_home(0.0, 0.0) == []


def test_duration_at_most_one_turn_per_second():
    assert duration((1086.0, 0.0), (0.0, 0.0)) == pytest.approx(1086 / 360)
    assert duration((0.0, 0.0), (0.0, 10.0)) == 0.3


@pytest.mark.parametrize(("index", "start", "end", "enters"), [
    (RIGHT, 270, 350, False), (RIGHT, 350, 370, True), (RIGHT, 90, 200, False), (RIGHT, 200, 900, True),
    (RIGHT, 10, 30, True), (LEFT, 10, 170, False), (LEFT, 170, 190, True), (LEFT, 270, 90, False),
    (LEFT, 360, 540, False),
])
def test_enters_inside_only_moving_out_is_harmless(index, start, end, enters):
    assert enters_inside(index, start, end) is enters


def test_safe_move_only_moves_the_one_antenna():
    assert moves(RIGHT, 225.0, 10.0, 30.0) == [(RIGHT, 225.0)]
    assert moves(LEFT, 270.0, 300.0, 90.0) == [(LEFT, 270.0)]
    assert moves(LEFT, 90.0, 300.0, 90.0) == []


def test_moving_inward_parks_the_other_inward_antenna():
    """Right goes into its inner half while left points inward: left parks, right moves, left returns."""
    assert moves(RIGHT, 405.0, 300.0, 270.0) == [(LEFT, 0.0), (RIGHT, 405.0), (LEFT, 270.0)]


def test_best_route_takes_the_detour_round_the_outside():
    # From 200° to 340° (outside) directly stays outside; backwards across the inside would mean parking
    assert best_route(RIGHT, [340.0, -20.0], 200.0, 270.0) == [(RIGHT, 340.0)]
    # From 350° to 190°: forwards across 0° would pass the inside, backwards round the outside needs no parking
    assert best_route(RIGHT, [550.0, 190.0], 350.0, 270.0) == [(RIGHT, 190.0)]
