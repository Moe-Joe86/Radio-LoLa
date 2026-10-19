import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from radio_lola.control import STATION, VOLUME, Control, add_routes
from radio_lola.stations import Stations

START = [("One", "https://one.example/"), ("Two", "https://two.example/"), ("Three", "https://three.example/")]


@pytest.fixture
def control(tmp_path):
    return Control(Stations(START, tmp_path / "stations.json"))


def test_reports_what_the_antennas_say(control):
    control.report("https://two.example/", 0.426)
    assert control.state() == {"stations": ["One", "Two", "Three"], "active": 1, "volume": 43, "muted": False}
    control.report(None, 0.0)
    assert control.state()["active"] is None


def test_new_wish_replaces_the_old_one_of_the_same_kind(control):
    control.wish_volume(20)
    control.wish_station(0)
    control.wish_volume(70)
    assert control.next_wish(0) == (VOLUME, 0.7)
    assert control.next_wish(0) == (STATION, 0)
    assert control.next_wish(0.01) is None


def test_adding_keeps_the_playing_station_under_the_antenna(control):
    control.report("https://two.example/", 0.5)
    assert control.add_station("https://four.example/", "Four", check=lambda u: (u, None)) == "Four"
    assert control.next_wish(0) == (STATION, 1)  # all fields shifted: drive back to "Two"


@pytest.mark.parametrize(("playing", "removed", "wish"), [
    ("https://three.example/", 0, 1),  # "Three" moves up from 2 to 1
    ("https://one.example/", 2, 0),  # "One" keeps its place
    ("https://two.example/", 1, 1),  # the playing one goes: "Three" takes its place
    ("https://three.example/", 2, 1),  # the last one goes: the new last one
])
def test_deleting_drives_to_the_playing_or_the_next_station(control, playing, removed, wish):
    control.report(playing, 0.5)
    control.delete_station(removed)
    assert control.next_wish(0) == (STATION, wish)


def test_in_the_noise_nothing_moves_after_a_change(control):
    control.report(None, 0.5)
    control.delete_station(0)
    assert control.next_wish(0.01) is None


def test_routes_for_the_phone_app(control):
    app = FastAPI()
    add_routes(app, control)
    client = TestClient(app)
    assert client.get("/radio").json() == {"stations": ["One", "Two", "Three"], "active": None, "volume": 0,
                                           "muted": False}
    assert client.post("/radio/station", json={"index": 1}).status_code == 200
    assert client.post("/radio/station", json={"index": 5}).status_code == 422
    assert client.post("/radio/volume", json={"value": 40}).status_code == 200
    assert client.post("/radio/volume", json={"value": 140}).status_code == 422
    assert client.post("/radio/mute", json={"on": True}).json()["muted"] is True
    assert control.next_wish(0) == (STATION, 1) and control.next_wish(0) == (VOLUME, 0.4) and control.muted()
    answer = client.post("/radio/stations/add", json={"url": "ftp://x"})
    assert answer.status_code == 422 and "http://" in answer.json()["detail"]
    assert client.post("/radio/stations/delete", json={"index": 0}).json()["stations"] == ["Two", "Three"]
