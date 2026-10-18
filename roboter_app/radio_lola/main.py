"""Aufgabe: Das Radio als Reachy-Mini-App: eine Antenne sucht Sender, die andere stellt die Lautstärke.

Knöpfe: `RadioLola`; Start und Stopp über den Daemon (POST /api/apps/start-app/radio_lola, /api/apps/stop-current-app).
Darf nicht: Ton wiederholen, den Reachy mit ausgeschalteten Antennen zurücklassen.
"""
# Läuft auf dem Reachy in Pollens apps_venv: Der Daemon startet die App als `python -m radio_lola.main` und stoppt
# sie mit SIGINT; nach 20 s ohne Ende tötet er sie. Das SDK ist lokal verbunden, deshalb gehen alle Bewegungen direkt
# über das SDK. `enable_motors()` ohne Namen ist im Daemon dasselbe wie REST `set_mode/enabled` (setzt alle Ziele auf
# die gemessene Stellung, nichts ruckt), `goto_target` wartet, bis die Bewegung fertig ist (Daemon-Code 1.12.0).
# Antennen im SDK: [rechts, links] in Radiant. SDK-rechts (von vorn links) sucht Sender, SDK-links (von vorn
# rechts) ist die Lautstärke; beide Motoren sind beim Spielen aus. Gemessen am 15. Oktober 2026.
# Das Rauschen entsteht hier mit numpy (kommt mit reachy-mini); die übrigen Dateien bleiben ohne Abhängigkeit testbar.
# Die Handy-App spricht mit dem Webserver der App (Port 8042, `steuerung.py`). Wählt sie einen Sender oder eine
# Lautstärke, fährt der Faden `fahrer` die passende Antenne dorthin; das Radio selbst hört nur auf die Antennen.
# Vor dem Einschalten eines Antennenmotors wird sein Ziel auf die gemessene Stellung gesetzt: Der Daemon schreibt
# das Ziel auch bei ausgeschaltetem Motor weiter, sonst spränge die Antenne auf das alte Ziel (Daemon-Code 1.12.0).
# Als hörbar gilt ein Sender, sobald er mindestens zur Hälfte gegen das Rauschen steht.

import logging
import math
import signal
import sys
import threading
import time
from collections.abc import Callable

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp

from radio_lola.abstimmung import angleichen, gerichtet, lautstaerke, pegel, ziel_lautstaerke, ziel_sender
from radio_lola.antennen import dauer, heimweg, zuege
from radio_lola.einstellungen import Radioeinstellungen, laden
from radio_lola.steuerung import SENDER, Regler, routen_anlegen
from radio_lola.strom import ABTASTRATE, BYTES_JE_WERT, Strom, fehlende_faehigkeiten

BLOCK = 1024  # Abtastwerte je Schub, 64 ms
RAUSCHEN = 0.3  # Stärke des weißen Rauschens (Standardabweichung)
SUCHE, LAUTSTAERKE = 0, 1  # Index der Antennen im SDK
ANTENNEN = ["right_antenna", "left_antenna"]

log = logging.getLogger("radio")


def heimholen(mini: ReachyMini) -> None:
    """Alle Motoren an, Stellung lesen und die Antennen nacheinander heim (`antennen.py`)."""
    mini.enable_motors()
    jetzt = tuple(math.degrees(w) for w in mini.get_present_antenna_joint_positions())
    log.info("Radio: Antennen nach dem Einschalten bei %.0f° / %.0f°", *jetzt)
    for ziel in heimweg(*jetzt):
        log.info("Radio: Antennen fahren auf %.0f° / %.0f°", *ziel)
        mini.goto_target(antennas=[math.radians(w) for w in ziel], duration=dauer(jetzt, ziel), body_yaw=None)
        jetzt = ziel


def wecken(mini: ReachyMini) -> None:
    heimholen(mini)
    mini.wake_up()
    mini.goto_target(antennas=[0.0, 0.0], duration=0.5, body_yaw=None)
    mini.disable_motors(ANTENNEN)
    log.info("Radio: geweckt, Antennen frei")


def antennen_fahren(mini: ReachyMini, ziele: list[tuple[float, float]]) -> None:
    """Fährt die Stellungen aus `antennen.zuege` ab; nur die bewegte Antenne hat dabei Kraft, danach ist sie frei."""
    jetzt = tuple(math.degrees(w) for w in mini.get_present_antenna_joint_positions())
    for ziel in ziele:
        welche = ANTENNEN[0] if ziel[0] != jetzt[0] else ANTENNEN[1]
        mini.set_target(antennas=[math.radians(w) for w in jetzt])
        time.sleep(0.1)  # ein paar Takte des Daemons, damit das Ziel beim Motor ankommt
        mini.enable_motors([welche])
        mini.goto_target(antennas=[math.radians(w) for w in ziel], duration=dauer(jetzt, ziel), body_yaw=None)
        mini.disable_motors([welche])
        jetzt = ziel


def wunsch_ausfuehren(mini: ReachyMini, e: Radioeinstellungen, art: str, wert: float) -> None:
    jetzt = [math.degrees(w) for w in mini.get_present_antenna_joint_positions()]
    if art == SENDER:
        index, ziel = SUCHE, ziel_sender(int(wert), len(e.sender), jetzt[SUCHE], e.bereich, e.richtung)
        log.info("Radio: Handy wählt %s, Antenne fährt auf %.0f°", e.sender[int(wert)][0], ziel)
    else:
        index, ziel = LAUTSTAERKE, ziel_lautstaerke(wert, jetzt[LAUTSTAERKE])
        log.info("Radio: Handy stellt Lautstärke %.0f %%, Antenne fährt auf %.0f°", wert * 100, ziel)
    antennen_fahren(mini, zuege(index, ziel, *jetzt))


def fahrer(mini: ReachyMini, e: Radioeinstellungen, regler: Regler, ende: threading.Event) -> None:
    """Eigener Faden: setzt Wünsche vom Handy um, damit der Ton währenddessen weiterläuft."""
    while not ende.is_set():
        wunsch = regler.wunsch_holen(0.2)
        if wunsch is None:
            continue
        try:
            wunsch_ausfuehren(mini, e, *wunsch)
        except Exception:  # ein misslungener Wunsch darf das Radio nicht beenden
            log.exception("Radio: Antennenfahrt misslungen")


def mischen(strom: Strom | None, anteil: float, rauschen: np.ndarray, laut: np.ndarray) -> np.ndarray:
    musik = np.zeros(BLOCK, np.float32) if strom is None else np.frombuffer(strom.lesen(BLOCK * BYTES_JE_WERT),
                                                                         np.float32)
    return np.clip((anteil * musik + (1 - anteil) * rauschen) * laut, -1, 1).astype(np.float32)


def spielen(mini: ReachyMini, e: Radioeinstellungen, ende: threading.Event, regler: Regler,
            neuer_strom: Callable[[str], Strom] | None = None) -> None:
    oeffnen = neuer_strom or Strom
    zufall, aktiv, strom, laut = np.random.default_rng(), None, None, 0.0
    takt = time.monotonic()
    try:
        while not ende.is_set():
            winkel = [math.degrees(w) for w in mini.get_present_antenna_joint_positions()]
            sender, anteil = pegel(gerichtet(winkel[SUCHE], e.richtung), len(e.sender), e.bereich, e.ueberblendung)
            if sender != aktiv:  # Wechsel mitten im Rauschfeld, wo der Sender nicht zu hören ist
                if strom is not None:
                    strom.beenden()
                aktiv, strom = sender, None if sender is None else oeffnen(e.sender[sender][1])
                if strom is not None:
                    log.info("Radio: Sender %s", e.sender[sender][0])
                    strom.starten()
            regler.melden(sender if anteil >= 0.5 else None, lautstaerke(winkel[LAUTSTAERKE]))
            neu = angleichen(laut, 0.0 if regler.stumm() else lautstaerke(winkel[LAUTSTAERKE]) * e.lautstaerke)
            rauschen = zufall.standard_normal(BLOCK, dtype=np.float32) * np.float32(RAUSCHEN)
            verlauf = np.linspace(laut, neu, BLOCK, dtype=np.float32)  # innerhalb des Blocks gleitend, ohne Knacken
            mini.media.push_audio_sample(mischen(strom, anteil, rauschen, verlauf))
            laut = neu
            takt += BLOCK / ABTASTRATE
            warten = takt - time.monotonic()
            if warten < -1.0:  # weit hinterher, etwa nach einer Störung: Takt neu setzen statt aufzuholen
                takt = time.monotonic()
            ende.wait(max(0.0, warten))
    finally:
        if strom is not None:
            strom.beenden()


class RadioLola(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"  # Webserver für die Handy-App (`steuerung.py`)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        # Meldungen nach stdout; stderr bleibt für Fehler, deren letzte Zeilen der Daemon als Grund des Abbruchs meldet.
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stdout)
        e = laden()
        log.info("Radio: gestartet, %d Sender", len(e.sender))
        regler = Regler([name for name, _ in e.sender])
        if self.settings_app is not None:
            routen_anlegen(self.settings_app, regler)
        try:
            fehlt = fehlende_faehigkeiten()
        except Exception as fehler:  # nur eine Auskunft fürs Protokoll, darf den Start nicht verhindern
            fehlt = [f"Prüfung unmöglich ({fehler})"]
        if fehlt:
            log.warning("Radio: GStreamer kann auf diesem Roboter nicht: %s", ", ".join(fehlt))
        faden = threading.Thread(target=fahrer, args=(reachy_mini, e, regler, stop_event), name="fahrer")
        try:
            wecken(reachy_mini)
            reachy_mini.media.start_playing()
            faden.start()
            spielen(reachy_mini, e, stop_event, regler)
        finally:
            stop_event.set()
            if faden.is_alive():
                faden.join(timeout=10)  # eine laufende Fahrt zu Ende fahren lassen
            heimholen(reachy_mini)
            reachy_mini.media.stop_playing()
            log.info("Radio: beendet, Antennen daheim, Motoren an")


if __name__ == "__main__":
    app = RadioLola()
    # Der Daemon stoppt mit SIGINT. Statt mitten in einer Bewegung abzubrechen, endet die Schleife sauber und die
    # Antennen fahren heim.
    for zeichen in (signal.SIGINT, signal.SIGTERM):
        signal.signal(zeichen, lambda *_: app.stop_event.set())
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
