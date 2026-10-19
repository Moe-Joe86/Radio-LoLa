import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from radio_lola.stations import Stations, probe

START = [("WDR 2", "https://wdr2.example/"), ("1LIVE", "https://1live.example/")]


class FakeStation(BaseHTTPRequestHandler):
    """Answers like a radio station: /live with audio and its name, /list.m3u as playlist, /page as a web page."""

    def do_GET(self):  # noqa: N802 (name given by http.server)
        if self.path == "/live":
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("icy-name", "Test FM")
            self.end_headers()
            self.wfile.write(b"\xff\xfb" * 64)
        elif self.path == "/quiet":
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.end_headers()
            self.wfile.write(b"\xff\xfb" * 64)
        elif self.path == "/list.m3u":
            self.send_response(200)
            self.send_header("Content-Type", "audio/x-mpegurl")
            self.end_headers()
            self.wfile.write(f"#EXTM3U\n#EXTINF:-1,Test\nhttp://127.0.0.1:{self.server.server_port}/live\n".encode())
        elif self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html></html>")
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def station_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeStation)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_probe_reads_the_station_name(station_url):
    assert probe(f"{station_url}/live") == (f"{station_url}/live", "Test FM")
    assert probe(f"{station_url}/quiet") == (f"{station_url}/quiet", None)


def test_probe_follows_a_playlist(station_url):
    assert probe(f"{station_url}/list.m3u") == (f"{station_url}/live", "Test FM")


@pytest.mark.parametrize(("path", "message"), [("/page", "not an audio stream"), ("/missing", "does not answer")])
def test_probe_rejects_what_does_not_play(station_url, path, message):
    with pytest.raises(ValueError, match=message):
        probe(f"{station_url}{path}")


def test_first_start_copies_the_starting_list(tmp_path):
    file = tmp_path / "radio_lola" / "stations.json"
    assert Stations(START, file).all() == START
    assert json.loads(file.read_text(encoding="utf-8")) == [{"name": n, "url": u} for n, u in START]


def test_the_list_on_the_robot_wins_over_the_starting_list(tmp_path):
    file = tmp_path / "stations.json"
    Stations(START, file).delete(0)
    assert Stations(START + [("New", "https://new.example/")], file).names() == ["1LIVE"]


def test_unreadable_file_falls_back_to_the_starting_list(tmp_path):
    file = tmp_path / "stations.json"
    file.write_text("{broken", encoding="utf-8")
    assert Stations(START, file).all() == START


def test_add_takes_typed_name_then_station_name_then_host(tmp_path):
    stations = Stations(START, tmp_path / "s.json")
    assert stations.add("https://a.example/s", "My radio", check=lambda u: (u, "Own")) == (2, "My radio")
    assert stations.add("https://b.example/s", " ", check=lambda u: (u, "Own")) == (3, "Own")
    assert stations.add("https://c.example/s", None, check=lambda u: (u, None)) == (4, "c.example")
    assert Stations([], tmp_path / "s.json").names() == ["WDR 2", "1LIVE", "My radio", "Own", "c.example"]


def test_add_with_a_real_probe(tmp_path, station_url):
    stations = Stations(START, tmp_path / "s.json")
    assert stations.add(f"{station_url}/list.m3u") == (2, "Test FM")
    assert stations.all()[2] == ("Test FM", f"{station_url}/live")


@pytest.mark.parametrize(("url", "message"), [("ftp://x", "http://"), ("https://wdr2.example/", "already")])
def test_add_refuses_bad_or_double_entries(tmp_path, url, message):
    stations = Stations(START, tmp_path / "s.json")
    with pytest.raises(ValueError, match=message):
        stations.add(url, check=lambda u: (u, None))


def test_at_most_eight_stations(tmp_path):
    stations = Stations([(f"S{i}", f"https://{i}.example/") for i in range(8)], tmp_path / "s.json")
    with pytest.raises(ValueError, match="at most 8"):
        stations.add("https://new.example/", check=lambda u: (u, None))


def test_delete_keeps_the_last_station(tmp_path):
    stations = Stations(START, tmp_path / "s.json")
    assert stations.delete(0) == "WDR 2"
    with pytest.raises(ValueError, match="last station"):
        stations.delete(0)
    with pytest.raises(ValueError, match="no station 5"):
        stations.delete(5)
