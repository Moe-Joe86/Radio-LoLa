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
    """Attrappe für `ReachyMini`, Antennen in Radiant, jede Bewegung landet im Protokoll.

    Wie am Roboter: Messungen schwanken um `zittern` Grad, nur Antennen mit Kraft folgen `goto_target`, und wer
    einer Antenne Kraft gibt, deren Ziel nicht ihre Stellung ist, lässt sie springen (`spruenge`).
    """

    NAMEN = {"right_antenna": 0, "left_antenna": 1}

    def __init__(self, rechts: float, links: float, medien: Medien | None = None, zittern: float = 0.0) -> None:
        self.antennen = [rechts * GRAD, links * GRAD]
        self.ziel, self.kraft = list(self.antennen), [True, True]
        self.zittern, self._messungen, self.spruenge = zittern, 0, []
        self.protokoll: list[tuple] = []
        self.media = medien

    def _welche(self, ids) -> list[int]:
        return [0, 1] if ids is None else [self.NAMEN[name] for name in ids]

    def enable_motors(self, ids=None) -> None:
        self.protokoll.append(("an", ids))
        if ids is None:  # alle Motoren: der Daemon setzt vorher jedes Ziel auf die Stellung (Daemon-Code 1.12.0)
            self.ziel = list(self.antennen)
        for i in self._welche(ids):
            if not self.kraft[i] and abs(self.ziel[i] - self.antennen[i]) > 0.5 * GRAD:
                self.spruenge.append(i)
                self.antennen[i] = self.ziel[i]
            self.kraft[i] = True

    def disable_motors(self, ids=None) -> None:
        self.protokoll.append(("aus", ids))
        for i in self._welche(ids):
            self.kraft[i] = False

    def get_present_antenna_joint_positions(self) -> list[float]:
        self._messungen += 1
        rauschen = self.zittern * GRAD * (1 if self._messungen % 2 else -1)
        return [w + rauschen for w in self.antennen]

    def set_target(self, head=None, antennas=None, body_yaw=None) -> None:
        self.protokoll.append(("ziel", tuple(round(w / GRAD, 1) for w in antennas)))
        self.ziel = list(antennas)

    def goto_target(self, head=None, antennas=None, duration=0.5, body_yaw=0.0) -> None:
        assert head is None and body_yaw is None, "das Radio bewegt nur die Antennen"
        self.protokoll.append(("fahren", tuple(round(w / GRAD, 1) for w in antennas), round(duration, 2)))
        self.ziel = list(antennas)
        for i in (0, 1):
            if self.kraft[i]:
                self.antennen[i] = antennas[i]

    def wake_up(self) -> None:
        self.protokoll.append(("wecken",))
        self.antennen = [-10 * GRAD, 10 * GRAD]
        self.ziel = list(self.antennen)

    def grad(self) -> tuple[float, float]:
        return tuple(round(w / GRAD, 1) for w in self.antennen)


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
def leere_stroeme():
    Strom.alle = []


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


def test_stumm_heisst_still_und_lautstaerke_kommt_von_der_antenne():
    ende = threading.Event()
    still = regler()
    still.stumm_setzen(True)
    mini = Mini(90, -180, Medien(ende, 3))
    main.spielen(mini, EIN_SENDER, ende, still, Strom)
    assert all(float(np.max(np.abs(b))) == 0.0 for b in mini.media.gespielt)
    assert still.zustand()["lautstaerke"] == 50  # die Antenne steht auf halb


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


def frei(rechts: float, links: float, zittern: float = 0.0) -> Mini:
    """Wie beim Spielen: beide Antennen ohne Kraft, ihr letztes Ziel war die Grundstellung."""
    mini = Mini(rechts, links, zittern=zittern)
    mini.ziel, mini.kraft = [0.0, 0.0], [False, False]
    return mini


def test_handy_waehlt_sender_nur_die_sender_antenne_bekommt_kraft():
    mini = frei(10, 30)  # Lautstärke-Antenne zeigt nach außen: eine Fahrt genügt
    main.wunsch_ausfuehren(mini, ZWEI_SENDER, "sender", 1)
    # Mitte von Sender 1 liegt bei 225°, also −135°: kürzester Weg rückwärts über null, rechts ist dabei innen erlaubt
    assert mini.protokoll == [("ziel", (10.0, 30.0)), ("an", ["right_antenna"]), ("fahren", (-135.0, 30.0), 0.4),
                              ("aus", ["right_antenna"])]
    assert mini.grad() == (-135.0, 30.0) and mini.spruenge == []


def test_handy_stellt_lautstaerke_nur_die_lautstaerke_antenne_faehrt():
    mini = frei(300, 90)  # Lautstärke 75 %, Sender-Antenne außen
    main.wunsch_ausfuehren(mini, EIN_SENDER, "lautstaerke", 0.25)
    assert mini.protokoll[1:] == [("an", ["left_antenna"]), ("fahren", (300.0, 270.0), 0.5),
                                  ("aus", ["left_antenna"])]
    assert main.lautstaerke(mini.grad()[main.LAUTSTAERKE]) == pytest.approx(0.25)


@pytest.mark.parametrize(("art", "wert", "bewegt"), [("lautstaerke", 0.8, 1), ("lautstaerke", 0.3, 1),
                                                     ("sender", 1, 0), ("sender", 0, 0)])
def test_messrauschen_verwechselt_die_antennen_nicht(art, wert, bewegt):
    """Fehler vom 18. Oktober: Zwei Messungen derselben ruhenden Antenne unterscheiden sich um Bruchteile eines Grades;
    das Radio gab dann der falschen Antenne Kraft. Jetzt fährt nur die gemeinte, keine springt."""
    mini = frei(300, 120, zittern=0.04)
    vorher = mini.grad()
    main.wunsch_ausfuehren(mini, ZWEI_SENDER, art, wert)
    eingeschaltet = {tuple(eintrag[1]) for eintrag in mini.protokoll if eintrag[0] == "an"}
    assert eingeschaltet == {(main.ANTENNEN[bewegt],)}
    assert mini.spruenge == []
    assert mini.grad()[1 - bewegt] == vorher[1 - bewegt]
    assert mini.grad()[bewegt] != vorher[bewegt]


def test_innere_antenne_parkt_nur_wenn_es_keinen_weg_aussen_herum_gibt():
    mini = frei(300, 270, zittern=0.04)  # Lautstärke zeigt nach innen, Sender 0 liegt rechts innen bei 45°
    main.wunsch_ausfuehren(mini, ZWEI_SENDER, "sender", 0)
    eingeschaltet = [eintrag[1][0] for eintrag in mini.protokoll if eintrag[0] == "an"]
    assert eingeschaltet == ["left_antenna", "right_antenna", "left_antenna"]
    assert mini.spruenge == []
    assert mini.grad() == (405.0, 270.0)


def test_sender_aussen_faehrt_aussen_herum_statt_zu_parken():
    zwei = Radioeinstellungen(sender=[("Eins", "a"), ("Zwei", "b")], lautstaerke=1.0, bereich=360, richtung=1,
                              ueberblendung=0)
    mini = frei(200, 270)  # Lautstärke innen; Sender 1 bei 225° liegt außen, der kurze Weg führt nicht durch innen
    main.wunsch_ausfuehren(mini, zwei, "sender", 1)
    assert [eintrag[1][0] for eintrag in mini.protokoll if eintrag[0] == "an"] == ["right_antenna"]


def test_fahrer_setzt_wuensche_um_und_endet_mit_dem_radio():
    ende, r, mini = threading.Event(), regler(("Eins", "Zwei")), frei(10, 30)
    faden = threading.Thread(target=main.fahrer, args=(mini, ZWEI_SENDER, r, ende))
    faden.start()
    r.wunsch_sender(1)
    for _ in range(50):
        if ("aus", ["right_antenna"]) in mini.protokoll:
            break
        threading.Event().wait(0.02)
    ende.set()
    faden.join(timeout=2)
    assert not faden.is_alive()
    assert mini.grad() == (-135.0, 30.0)
