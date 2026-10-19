import pytest

from radio_lola.settings import FILE, check_station, load, parse_stations


def test_defaults_without_a_file(tmp_path):
    s = load(tmp_path / "missing.toml")
    assert (s.stations, s.max_volume, s.span, s.direction, s.crossfade) == ([], 0.6, 360.0, 1, 6.0)


def test_shipped_file_is_valid():
    s = load(FILE)
    assert [name for name, _ in s.stations] == ["WDR 2", "1LIVE", "WDR 3", "WDR 4", "WDR 5"]
    assert all(url.startswith("https://") for _, url in s.stations)
    assert (s.max_volume, s.span, s.direction, s.crossfade) == (0.6, 360.0, 1, 6.0)


def test_values_from_the_file(tmp_path):
    file = tmp_path / "settings.toml"
    file.write_text(
        "max_volume = 80\nspan_deg = 270\ndirection = -1\ncrossfade_deg = 4.5\n"
        '[[station]]\nname = "One"\nurl = "https://one.example/stream.mp3"\n'
        '[[station]]\nname = " Two "\nurl = "http://two.example/a.aac"\n',
        encoding="utf-8",
    )
    s = load(file)
    assert s.stations == [("One", "https://one.example/stream.mp3"), ("Two", "http://two.example/a.aac")]
    assert (s.max_volume, s.span, s.direction, s.crossfade) == (0.8, 270.0, -1, 4.5)


@pytest.mark.parametrize(("entries", "message"), [
    ([{"name": "One"}], "url"), ([{"name": "One", "url": "ftp://x"}], "url"),
    ([{"url": "https://x"}], "name is missing"), ([{"name": "  ", "url": "https://x"}], "name is missing"),
    ([{"name": "One", "url": "https://x", "adress": "y"}], "unknown key adress"), ("One|https://x", "block"),
    ([{"name": f"S{i}", "url": "https://x"} for i in range(9)], "at most 8"),
])
def test_faulty_station_stops(entries, message):
    with pytest.raises(ValueError, match=message):
        parse_stations(entries)


def test_name_too_long():
    with pytest.raises(ValueError, match="longer than 40"):
        check_station("x" * 41, "https://x")


@pytest.mark.parametrize(("line", "name"), [
    ("max_volume = 120", "max_volume"), ('max_volume = "loud"', "max_volume"), ("span_deg = 400", "span_deg"),
    ("direction = 2", "direction"), ("crossfade_deg = -1", "crossfade_deg"), ("volume = 50", "unknown"),
    ("max_volume = ", "syntax error"), ("direction = true", "direction"),
])
def test_faulty_values_stop_with_their_name(tmp_path, line, name):
    file = tmp_path / "settings.toml"
    file.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=name):
        load(file)
