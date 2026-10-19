"""Purpose: works out from the antenna angles which station plays, how strongly, and how loud.

API: `directed`, `field`, `level`, `volume`, `approach`; the inverse: `station_target`, `volume_target`.
Must not: touch hardware, network or sound; standard library only, all angles in degrees.
"""
# The usable range is split into 2N equal fields, alternating station and noise; field 0 is a station and starts at
# 0°. The start belongs to the field, the end does not. At every edge of a station field `level` crossfades smoothly
# over `crossfade` degrees between station and noise, so it does not jump when the antenna jitters. With a range
# below 360°, everything outside the range is noise.

FULL = 360.0


def directed(raw: float, direction: int = 1) -> float:
    """Raw antenna angle (may exceed 360° or be negative) as an angle from 0 to below 360° in counting direction."""
    return (direction * raw) % FULL


def _width(n: int, span: float) -> float:
    return span / (2 * n)


def field(angle: float, n: int, span: float = FULL) -> tuple[str, int | None]:
    """("station", index) or ("noise", None) for the angle."""
    a = angle % FULL
    if n <= 0 or a >= span:
        return ("noise", None)
    k = min(int(a // _width(n, span)), 2 * n - 1)
    return ("station", k // 2) if k % 2 == 0 else ("noise", None)


def _station_fields(n: int, span: float) -> list[tuple[int, float, float]]:
    """(index, start, end) of every station field; station 0 once more after 360° for the crossing over zero."""
    w = _width(n, span)
    fields = [(i, 2 * i * w, (2 * i + 1) * w) for i in range(n)]
    return fields + [(0, FULL, FULL + w)]


def level(angle: float, n: int, span: float = FULL, crossfade: float = 0.0) -> tuple[int | None, float]:
    """Nearest station and its share from 0 (noise only) to 1 (station only); exactly 0.5 at a field edge."""
    if n <= 0:
        return (None, 0.0)
    a = angle % FULL
    best, distance, inside = None, float("-inf"), False
    for i, start, end in _station_fields(n, span):
        within = start <= a < end
        d = min(a - start, end - a) if within else -min(abs(a - start), abs(a - end))
        if d > distance:
            best, distance, inside = i, d, within
    if crossfade <= 0:
        return (best, 1.0 if inside else 0.0)
    return (best, min(1.0, max(0.0, 0.5 + distance / crossfade)))


def volume(raw: float) -> float:
    """Share 0 to 1 from the volume antenna, rising evenly over a full turn.

    Up (0°) is quiet; turning counter-clockwise (seen from the front) it rises to full just before the top again,
    so the jump sits at the top.
    """
    return (-raw % FULL) / FULL


def approach(old: float, target: float, step: float = 0.05) -> float:
    """Moves the volume by at most `step` per sound block so it follows smoothly, without clicks."""
    return old + max(-step, min(step, target - old))


def _nearest(phase: float, now: float) -> float:
    """Raw angle with this phase closest to `now` (shortest way, also across zero)."""
    return now + ((phase - now + FULL / 2) % FULL - FULL / 2)


def station_target(index: int, n: int, now: float, span: float = FULL, direction: int = 1) -> float:
    """Raw angle of the tuning antenna in the middle of station field `index`, the shortest way from `now`."""
    middle = (2 * index + 0.5) * _width(n, span)
    return _nearest((direction * middle) % FULL, now)


HIGHEST = 0.995  # at the very top the volume jumps from full to quiet; the phone never drives that far


def volume_target(share: float, now: float) -> float:
    """Raw angle of the volume antenna for `share` (0 to 1), without crossing the jump at the top."""
    share = min(HIGHEST, max(0.0, share))
    return now - (share - volume(now)) * FULL
