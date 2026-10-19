"""Purpose: plans antenna moves without collisions: home to the zero position, and on request from the phone.

API: `way_home`, `moves`, `best_route`, `points_inward`, `enters_inside`, `to_top`, `duration`.
Must not: touch hardware or move both antennas at once; standard library only, angles in degrees.
"""
# Measured on the robot (15 October 2026): seen from the front, both antennas count up clockwise, over many turns
# (−1444° to +1086°). 0° points up. The robot's right antenna (index 0, on the left seen from the front) points
# towards the middle between 0° and 180°, the left one (index 1) between 180° and 360°. They can only collide when
# both point towards the middle. Hence: first park one antenna on the shortest way out of its inner half at the top,
# then turn the other one all the way back, then the first.
# A move requested by the phone (`moves`) follows the same rule: if the other antenna points inward and the moving
# one would get into its inner half, the other one parks at the top for a moment and returns afterwards; only moving
# out is allowed without parking, as on the way home. For stations, `best_route` takes the way round the outside when
# that avoids parking. If the target itself is inside, both point inward again at the end; only the return of the
# parked antenna then moves next to an inner one.

import math

RIGHT, LEFT = 0, 1
DEGREES_PER_SECOND = 360.0  # at most one turn per second
SHORTEST_MOVE = 0.3


def points_inward(index: int, raw: float) -> bool:
    phase = raw % 360.0
    return 0.0 < phase < 180.0 if index == RIGHT else 180.0 < phase < 360.0


def to_top(index: int, raw: float) -> float:
    """Next upright position (multiple of 360°), on the way that leaves the inner half fastest."""
    phase = raw % 360.0
    if phase == 0.0:
        return raw
    backwards = phase < 90.0 if index == RIGHT else phase <= 270.0
    return raw - phase if backwards else raw + (360.0 - phase)


def way_home(right: float, left: float) -> list[tuple[float, float]]:
    """Targets [right, left] one after another; at each target only one antenna moves."""
    first = LEFT if points_inward(LEFT, left) or not points_inward(RIGHT, right) else RIGHT
    then = RIGHT if first == LEFT else LEFT
    position, targets = [right, left], []
    for index, target in ((first, to_top(first, position[first])), (then, 0.0), (first, 0.0)):
        if position[index] != target:
            position[index] = target
            targets.append((position[RIGHT], position[LEFT]))
    return targets


def duration(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Seconds for a move, at most one turn per second."""
    return max(SHORTEST_MOVE, max(abs(b - a) for a, b in zip(start, end, strict=True)) / DEGREES_PER_SECOND)


def enters_inside(index: int, start: float, end: float) -> bool:
    """Whether the antenna gets into its inner half on the way or ends there; only moving out does not count."""
    if points_inward(index, end):
        return True
    steps = max(1, math.ceil(abs(end - start)))  # one look per degree, the inner half is 180° wide
    outside = not points_inward(index, start)
    for k in range(1, steps + 1):
        inside = points_inward(index, start + (end - start) * k / steps)
        if inside and outside:
            return True
        outside = outside or not inside
    return False


def moves(index: int, target: float, right: float, left: float) -> list[tuple[int, float]]:
    """Moves (antenna, raw angle) one after another to bring antenna `index` to `target`; one antenna per move."""
    position = [right, left]
    other = LEFT if index == RIGHT else RIGHT
    if position[index] == target:
        return []
    if points_inward(other, position[other]) and enters_inside(index, position[index], target):
        return [(other, to_top(other, position[other])), (index, target), (other, position[other])]
    return [(index, target)]


def best_route(index: int, targets: list[float], right: float, left: float) -> list[tuple[int, float]]:
    """Of several equivalent targets (e.g. forwards or backwards to the same station) the one without parking,
    otherwise the nearest."""
    now = right if index == RIGHT else left
    return min((moves(index, target, right, left) for target in targets),
               key=lambda plan: (len(plan), sum(abs(a - now) for i, a in plan if i == index)))
