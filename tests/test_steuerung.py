from fastapi import FastAPI
from fastapi.testclient import TestClient

from radio_lola.steuerung import LAUTSTAERKE, SENDER, Regler, routen_anlegen


def test_meldet_was_die_antennen_sagen():
    r = Regler(["Eins", "Zwei"])
    r.melden(1, 0.426)
    assert r.zustand() == {"sender": ["Eins", "Zwei"], "aktiv": 1, "lautstaerke": 43, "stumm": False}


def test_neuer_wunsch_ersetzt_den_alten_gleicher_art():
    r = Regler(["Eins", "Zwei"])
    r.wunsch_lautstaerke(20)
    r.wunsch_sender(0)
    r.wunsch_lautstaerke(70)
    assert r.wunsch_holen(0) == (LAUTSTAERKE, 0.7)
    assert r.wunsch_holen(0) == (SENDER, 0)
    assert r.wunsch_holen(0.01) is None


def test_routen_fuer_die_handy_app():
    app, r = FastAPI(), Regler(["Eins", "Zwei"])
    routen_anlegen(app, r)
    client = TestClient(app)
    assert client.get("/radio").json() == {"sender": ["Eins", "Zwei"], "aktiv": None, "lautstaerke": 0, "stumm": False}
    assert client.post("/radio/sender", json={"index": 1}).status_code == 200
    assert client.post("/radio/sender", json={"index": 5}).status_code == 422
    assert client.post("/radio/lautstaerke", json={"wert": 40}).status_code == 200
    assert client.post("/radio/lautstaerke", json={"wert": 140}).status_code == 422
    assert client.post("/radio/stumm", json={"an": True}).json()["stumm"] is True
    assert r.wunsch_holen(0) == (SENDER, 1) and r.wunsch_holen(0) == (LAUTSTAERKE, 0.4) and r.stumm()
