import math
import threading

import numpy as np
import pytest

from radio_lola import main
from radio_lola.einstellungen import Radioeinstellungen
from radio_lola.steuerung import Regler

GRAD = math.pi / 180


class Medien:
    """Attrappe für `mini.media`: sammelt die Tonblöcke und meldet nach `bloecke` Blöcken das Ende."""

    def __init__(self, ende: threading.Event, bloecke: int, bei_block=None) -> None:
        self.ende, self.bloecke, self.bei_block = ende, bloecke, bei_block
        self.gespielt, self.laeuft = [], False

    def start_playing(self) -> None:
        self.laeuft = True

    def stop_playing(self) -> None:
        self.laeuft = False

    def push_audio_sample(self, block: np.ndarray) -> None:
        self.gespielt.append(block)
        if self.bei_block is not None:
            self.bei_block(len(self.gespielt))
        if len(self.gespielt) >= self.bloecke:
            self.ende.set()


class Mini:
    """Attrappe für `ReachyMini`: Antennen in Radiant, jede Bewegung landet im Protokoll."""

    def __init__(self, rechts: float, links: float, medien: Medien | None = None) -> None:
        self.antennen = [rechts * GRAD, links * GRAD]
        self.protokoll: list[tuple] = []
        self.media = medien

    def enable_motors(self, ids=None) -> None:
        self.protokoll.append(("an", ids))

    def disable_motors(self, ids=None) -> None:
        self.protokoll.append(("aus", ids))

    def get_present_antenna_joint_positions(self) -> list[float]:
        return list(self.antennen)

    def goto_target(self, head=None, antennas=None, duration=0.5, body_yaw=0.0) -> None:
        assert head is None and body_yaw is None, "das Radio bewegt nur die Antennen"
        self.protokoll.append(("fahren", tuple(round(w / GRAD, 1) for w in antennas), round(duration, 2)))
        self.antennen = list(antennas)

    def wake_up(self) -> None:
        self.protokoll.append(("wecken",))
        self.antennen = [-10 * GRAD, 10 * GRAD]


class Strom:
    """Attrappe für `strom.Strom`: liefert konstanten Ton und merkt sich Start und Ende."""

    alle: list["Strom"] = []

    def __init__(self, adresse: str) -> None:
        self.adresse, self.gestartet, self.beendet = adresse, False, False
        Strom.alle.append(self)

    def starten(self) -> None:
        self.gestartet = True

    def beenden(self) -> None:
        self.beendet = True

    def lesen(self, anzahl_bytes: int) -> bytes:
        return np.full(anzahl_bytes // 4, 0.5, np.float32).tobytes()


@pytest.fixture(autouse=True)
def leere_stroeme(monkeypatch, tmp_path):
    Strom.alle = []
    monkeypatch.setattr(Regler.__init__, "__defaults__", (tmp_path / "regler.json",))


def regler(namen=("Eins",)) -> Regler:
    return Regler(list(namen))


EIN_SENDER = Radioeinstellungen(sender=[("Eins", "https://eins.example/")], lautstaerke=1.0, bereich=360,
                                richtung=1, ueberblendung=0)
ZWEI_SENDER = Radioeinstellungen(sender=[("Eins", "https://eins.example/"), ("Zwei", "https://zwei.example/")],
                                 lautstaerke=1.0, bereich=360, richtung=1, ueberblendung=0)


def test_heimholen_schaltet_erst_ein_dann_nacheinander_heim():
    mini = Mini(1086.3, -1443.6)
    main.heimholen(mini)
    assert mini.protokoll == [("an", None), ("fahren", (1086.3, -1440.0), 0.3), ("fahren", (0.0, -1440.0), 3.02),
                              ("fahren", (0.0, 0.0), 4.0)]


def test_wecken_holt_heim_weckt_und_gibt_die_antennen_frei():
    mini = Mini(45, 0)
    main.wecken(mini)
    assert mini.protokoll == [("an", None), ("fahren", (0.0, 0.0), 0.3), ("wecken",), ("fahren", (0.0, 0.0), 0.5),
                              ("aus", ["right_antenna", "left_antenna"])]


def test_spielen_mischt_sender_und_lautstaerke_weich():
    ende = threading.Event()
    mini = Mini(90, -180, Medien(ende, 5))  # Sender 0 in der Feldmitte, Lautstärke halb
    main.spielen(mini, EIN_SENDER, ende, regler(), Strom)
    bloecke = mini.media.gespielt
    assert len(bloecke) == 5 and all(b.dtype == np.float32 and b.shape == (main.BLOCK,) for b in bloecke)
    assert bloecke[0][0] == 0.0  # beginnt still und wird je Block um höchstens 0,05 lauter
    assert bloecke[-1][-1] == pytest.approx(0.5 * 0.25)
    assert [s.adresse for s in Strom.alle] == ["https://eins.example/"]
    assert Strom.alle[0].gestartet and Strom.alle[0].beendet


def test_im_rauschfeld_nur_rauschen():
    """Der nächste Sender läuft schon mit, ist aber nicht zu hören: der Block ist reines Rauschen um null."""
    ende = threading.Event()
    mini = Mini(270, -270, Medien(ende, 20))
    main.spielen(mini, EIN_SENDER, ende, regler(), Strom)
    letzter = mini.media.gespielt[-1]
    assert abs(float(np.mean(letzter))) < 0.05 < float(np.std(letzter))


def test_senderwechsel_beendet_den_alten_strom():
    ende = threading.Event()
    mini = Mini(45, -90, None)

    def drehen(anzahl: int) -> None:
        if anzahl == 2:
            mini.antennen[main.SUCHE] = 225 * GRAD  # Mitte von Sender 1 bei vier Feldern

    mini.media = Medien(ende, 4, drehen)
    main.spielen(mini, ZWEI_SENDER, ende, regler(("Eins", "Zwei")), Strom)
    assert [s.adresse for s in Strom.alle] == ["https://eins.example/", "https://zwei.example/"]
    assert all(s.beendet for s in Strom.alle)


def test_run_endet_mit_antennen_daheim_und_motoren_an(monkeypatch):
    app = main.RadioLola()
    mini = Mini(30, 60, Medien(app.stop_event, 3))
    monkeypatch.setattr(main, "Strom", Strom)
    monkeypatch.setattr(main, "fehlende_faehigkeiten", lambda: [])

    def verdrehen(anzahl: int) -> None:
        mini.antennen = [400 * GRAD, -30 * GRAD]  # beim Hören von Hand verdreht

    mini.media.bei_block = verdrehen
    app.run(mini, app.stop_event)
    nach_dem_spielen = mini.protokoll[mini.protokoll.index(("aus", main.ANTENNEN)) + 1:]
    # Links zeigt nach innen und parkt zuerst oben, dann dreht rechts über eine Runde heim (`antennen.heimweg`);
    # die letzte kurze Fahrt gleicht nur den Rundungsrest von Radiant in Grad aus.
    assert nach_dem_spielen == [("an", None), ("fahren", (400.0, 0.0), 0.3), ("fahren", (0.0, 0.0), 1.11),
                                ("fahren", (0.0, 0.0), 0.3)]
    assert mini.antennen == [0.0, 0.0] and not mini.media.laeuft


def test_fehler_beim_spielen_holt_trotzdem_heim(monkeypatch):
    app = main.RadioLola()
    mini = Mini(0, 0, Medien(app.stop_event, 100))
    monkeypatch.setattr(main, "Strom", Strom)
    monkeypatch.setattr(main, "fehlende_faehigkeiten", lambda: [])

    def kaputt(block):
        mini.antennen = [100 * GRAD, 0.0]
        raise RuntimeError("Ton weg")

    mini.media.push_audio_sample = kaputt
    with pytest.raises(RuntimeError, match="Ton weg"):
        app.run(mini, app.stop_event)
    assert mini.protokoll[-3:] == [("an", None), ("fahren", (360.0, 0.0), 0.72), ("fahren", (0.0, 0.0), 1.0)]
    assert mini.antennen == [0.0, 0.0]


def test_fehlerhafte_einstellungen_bewegen_nichts(monkeypatch, tmp_path):
    datei = tmp_path / "einstellungen.toml"
    datei.write_text("richtung = 3\n", encoding="utf-8")
    laden = main.laden
    monkeypatch.setattr(main, "laden", lambda: laden(datei))
    app = main.RadioLola()
    mini = Mini(0, 0, Medien(app.stop_event, 1))
    with pytest.raises(ValueError, match="richtung"):
        app.run(mini, app.stop_event)
    assert mini.protokoll == []


def test_handy_lautstaerke_und_stumm_wirken_zusaetzlich_zur_antenne():
    ende = threading.Event()
    mini = Mini(90, -180, Medien(ende, 5))  # Antenne halb
    halb = regler()
    halb.lautstaerke_setzen(50)
    main.spielen(mini, EIN_SENDER, ende, halb, Strom)
    assert mini.media.gespielt[-1][-1] == pytest.approx(0.5 * 0.25)  # 5 Schritte zu 0,05, Ziel 0,25 erreicht
    ende.clear()
    mini.media = Medien(ende, 3)
    still = regler()
    still.stumm_setzen(True)
    main.spielen(mini, EIN_SENDER, ende, still, Strom)
    assert all(float(np.max(np.abs(b))) == 0.0 for b in mini.media.gespielt)


def test_meldet_hoerbaren_sender_und_rauschen():
    ende = threading.Event()
    r = regler(("Eins", "Zwei"))
    mini = Mini(225, -90, Medien(ende, 2))  # Mitte von Sender 1
    main.spielen(mini, ZWEI_SENDER, ende, r, Strom)
    assert r.zustand()["aktiv"] == 1
    ende.clear()
    mini = Mini(135, -90, Medien(ende, 2))  # Mitte eines Rauschfelds
    main.spielen(mini, ZWEI_SENDER, ende, r, Strom)
    assert r.zustand()["aktiv"] is None
