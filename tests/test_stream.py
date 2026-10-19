from radio_lola.stream import BYTES_PER_SAMPLE, Broken, Stream, missing_capabilities


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Source:
    """Stand-in: delivers data, empty answers or a break, one after another."""

    def __init__(self, sequence: list) -> None:
        self.sequence, self.closed = list(sequence), False

    def read(self, timeout: float) -> bytes:
        part = self.sequence.pop(0) if self.sequence else b""
        if isinstance(part, Exception):
            raise part
        return part

    def close(self) -> None:
        self.closed = True


def stream_with(*sources):
    opened, clock = [], Clock()

    def open_source(url):
        if not sources[len(opened)]:
            opened.append(None)
            raise OSError("unreachable")
        opened.append(sources[len(opened)])
        return opened[-1]

    return Stream("http://station.example/", open_source, clock), clock, opened


def test_delivers_buffered_sound_then_silence_without_repeating():
    stream, _, _ = stream_with(Source([b"\x01" * 8]))
    stream.step()  # connect
    stream.step()  # read
    assert stream.read(12) == b"\x01" * 8 + bytes(4)
    assert stream.read(8) == bytes(8)


def test_reconnects_after_a_break():
    first, second = Source([b"\x01" * 4, Broken("end of stream")]), Source([b"\x02" * 4])
    stream, clock, opened = stream_with(first, second)
    for _ in range(3):
        stream.step()
    assert first.closed and len(opened) == 1
    stream.step()  # too early: waits 1 s
    assert len(opened) == 1
    clock.now = 1.0
    stream.step()
    stream.step()
    assert len(opened) == 2
    assert stream.read(8) == b"\x01" * 4 + b"\x02" * 4


def test_five_seconds_without_sound_count_as_a_break():
    first = Source([])
    stream, clock, opened = stream_with(first, Source([]))
    stream.step()
    clock.now = 5.5
    stream.step()
    assert first.closed
    clock.now = 6.5
    stream.step()
    assert len(opened) == 2


def test_waiting_time_doubles_up_to_30_seconds():
    stream, clock, opened = stream_with(*([None] * 8))
    times = []
    while len(times) < 7:
        count = len(opened)
        stream.step()
        if len(opened) > count:
            times.append(clock.now)
        clock.now += 0.5
    assert [b - a for a, b in zip(times, times[1:], strict=False)] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]


def test_buffer_holds_at_most_two_seconds():
    block = b"\x03" * 16000 * BYTES_PER_SAMPLE  # one second
    stream, _, _ = stream_with(Source([block, block, block, b"\x04" * 4]))
    for _ in range(5):
        stream.step()
    data = stream.read(3 * len(block))
    assert data[: 2 * len(block) - 4] == b"\x03" * (2 * len(block) - 4)
    assert data[2 * len(block) - 4: 2 * len(block)] == b"\x04" * 4
    assert data[2 * len(block):] == bytes(len(block))


def test_missing_capabilities_names_what_gstreamer_cannot_do():
    everything = {"uridecodebin", "audioconvert", "audioresample", "appsink", "souphttpsrc", "mpg123audiodec", "faad"}
    assert missing_capabilities(everything.__contains__) == []
    assert missing_capabilities((everything - {"faad"}).__contains__) == ["AAC"]
    assert missing_capabilities((everything - {"souphttpsrc", "appsink"}).__contains__) == [
        "basic elements", "receiving via http/https"]
