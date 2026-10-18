"""Aufgabe: Lautstärke und Stummschalter vom Handy, dazu die Auskunft, welche Sender es gibt und welcher spielt.

Knöpfe: `Regler` (`faktor`, `lautstaerke_setzen`, `stumm_setzen`, `sender_melden`, `zustand`), `routen_anlegen`.
Darf nicht: Hardware oder Ton anfassen; die Antennen bleiben die eigentliche Bedienung.
"""
# Die Handy-Lautstärke wirkt zusätzlich zur Lautstärke-Antenne: Antenne × Höchstwert aus einstellungen.toml × Handy.
# Stumm setzt den Faktor auf null, ohne den Reglerwert zu verlieren. Beides übersteht einen Neustart (kleine
# JSON-Datei). Die Routen hängen am Webserver, den Pollens ReachyMiniApp für `custom_app_url` startet (Port 8042).

import json
import logging
import threading
from pathlib import Path

DATEI = Path.home() / ".config" / "radio_lola" / "regler.json"

log = logging.getLogger("radio.steuerung")


class Regler:
    def __init__(self, sender_namen: list[str], datei: Path = DATEI) -> None:
        self.sender_namen, self._datei = list(sender_namen), datei
        self._sperre = threading.Lock()
        self._lautstaerke, self._stumm, self._aktiv = 100, False, None
        try:
            gespeichert = json.loads(datei.read_text(encoding="utf-8"))
            self._lautstaerke = min(100, max(0, int(gespeichert["lautstaerke"])))
            self._stumm = bool(gespeichert["stumm"])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # erster Start oder kaputte Datei: voll und nicht stumm

    def faktor(self) -> float:
        """Anteil 0 bis 1, mit dem das Handy die Lautstärke der Antenne multipliziert."""
        with self._sperre:
            return 0.0 if self._stumm else self._lautstaerke / 100

    def lautstaerke_setzen(self, wert: int) -> None:
        if not 0 <= wert <= 100:
            raise ValueError(f"lautstaerke: {wert} liegt nicht zwischen 0 und 100")
        with self._sperre:
            self._lautstaerke = wert
        self._speichern()

    def stumm_setzen(self, an: bool) -> None:
        with self._sperre:
            self._stumm = an
        self._speichern()

    def sender_melden(self, index: int | None) -> None:
        """Index des hörbaren Senders oder None im Rauschen."""
        with self._sperre:
            self._aktiv = index

    def zustand(self) -> dict:
        with self._sperre:
            return {"sender": self.sender_namen, "aktiv": self._aktiv, "lautstaerke": self._lautstaerke,
                    "stumm": self._stumm}

    def _speichern(self) -> None:
        with self._sperre:
            daten = {"lautstaerke": self._lautstaerke, "stumm": self._stumm}
        try:
            self._datei.parent.mkdir(parents=True, exist_ok=True)
            self._datei.write_text(json.dumps(daten), encoding="utf-8")
        except OSError as fehler:  # dann gilt der Wert nur bis zum nächsten Start
            log.warning("Radio: Reglerstand nicht gespeichert (%s)", fehler)


def routen_anlegen(app, regler: Regler) -> None:
    """GET /radio, POST /radio/lautstaerke {"wert": 0…100}, POST /radio/stumm {"an": true|false}."""
    from pydantic import BaseModel, Field

    class Lautstaerke(BaseModel):
        wert: int = Field(ge=0, le=100)

    class Stumm(BaseModel):
        an: bool

    @app.get("/radio")
    def radio() -> dict:
        return regler.zustand()

    @app.post("/radio/lautstaerke")
    def lautstaerke(daten: Lautstaerke) -> dict:
        regler.lautstaerke_setzen(daten.wert)
        return regler.zustand()

    @app.post("/radio/stumm")
    def stumm(daten: Stumm) -> dict:
        regler.stumm_setzen(daten.an)
        return regler.zustand()
