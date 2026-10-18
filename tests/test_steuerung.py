from fastapi import FastAPI
from fastapi.testclient import TestClient

from radio_lola.steuerung import Regler, routen_anlegen


def test_startet_voll_und_nicht_stumm(tmp_path):
    r = Regler(["Eins", "Zwei"], tmp_path / "regler.json")
    assert r.zustand() == {"sender": ["Eins", "Zwei"], "aktiv": None, "lautstaerke": 100, "stumm": False}
    assert r.faktor() == 1.0


def test_stumm_behaelt_den_reglerwert_und_uebersteht_neustart(tmp_path):
    datei = tmp_path / "unter" / "regler.json"
    r = Regler([], datei)
    r.lautstaerke_setzen(30)
    r.stumm_setzen(True)
    assert r.faktor() == 0.0
    neu = Regler([], datei)
    assert (neu.zustand()["lautstaerke"], neu.zustand()["stumm"]) == (30, True)
    neu.stumm_setzen(False)
    assert neu.faktor() == 0.3


def test_kaputte_datei_heisst_voll(tmp_path):
    datei = tmp_path / "regler.json"
    datei.write_text("{kaputt", encoding="utf-8")
    assert Regler([], datei).faktor() == 1.0


def test_routen_fuer_die_handy_app(tmp_path):
    app, r = FastAPI(), Regler(["Eins"], tmp_path / "regler.json")
    routen_anlegen(app, r)
    r.sender_melden(0)
    client = TestClient(app)
    assert client.get("/radio").json() == {"sender": ["Eins"], "aktiv": 0, "lautstaerke": 100, "stumm": False}
    assert client.post("/radio/lautstaerke", json={"wert": 40}).json()["lautstaerke"] == 40
    assert client.post("/radio/stumm", json={"an": True}).json()["stumm"] is True
    assert client.post("/radio/lautstaerke", json={"wert": 140}).status_code == 422
    assert r.faktor() == 0.0
