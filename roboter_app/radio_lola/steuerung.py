"""Aufgabe: Schnittstelle zur Handy-App: Sender wählen, Lautstärke stellen, stummschalten, Zustand melden.

Knöpfe: `Regler` (`melden`, `zustand`, `stumm_setzen`, `wunsch_sender`, `wunsch_lautstaerke`, `wunsch_holen`),
`routen_anlegen`.
Darf nicht: Hardware oder Ton anfassen; Sender und Lautstärke stellt allein die Antenne, das Handy wünscht nur.
"""
# Die Antennen bleiben die eine Wahrheit: Wählt das Handy einen Sender oder eine Lautstärke, fährt `main.py` die
# passende Antenne dorthin, und das Radio hört wie immer auf die Antennen. Ein neuer Wunsch ersetzt einen noch nicht
# begonnenen gleicher Art. Stumm ist nur ein Schalter im Ton und gilt bis zum Ende des Radios. Die Routen hängen am
# Webserver, den Pollens ReachyMiniApp für `custom_app_url` startet (Port 8042).

import threading

SENDER, LAUTSTAERKE = "sender", "lautstaerke"


class Regler:
    def __init__(self, sender_namen: list[str]) -> None:
        self.sender_namen = list(sender_namen)
        self._sperre = threading.Lock()
        self._neu = threading.Condition(self._sperre)
        self._aktiv: int | None = None
        self._lautstaerke = 0
        self._stumm = False
        self._wuensche: dict[str, float] = {}

    def melden(self, aktiv: int | None, lautstaerke_anteil: float) -> None:
        """Was die Antennen gerade sagen: hörbarer Sender (oder None im Rauschen) und Lautstärke 0 bis 1."""
        with self._sperre:
            self._aktiv, self._lautstaerke = aktiv, round(lautstaerke_anteil * 100)

    def zustand(self) -> dict:
        with self._sperre:
            return {"sender": self.sender_namen, "aktiv": self._aktiv, "lautstaerke": self._lautstaerke,
                    "stumm": self._stumm}

    def stumm(self) -> bool:
        with self._sperre:
            return self._stumm

    def stumm_setzen(self, an: bool) -> None:
        with self._sperre:
            self._stumm = an

    def wunsch_sender(self, index: int) -> None:
        if not 0 <= index < len(self.sender_namen):
            raise ValueError(f"sender: {index} gibt es nicht")
        self._wuenschen(SENDER, index)

    def wunsch_lautstaerke(self, wert: int) -> None:
        if not 0 <= wert <= 100:
            raise ValueError(f"lautstaerke: {wert} liegt nicht zwischen 0 und 100")
        self._wuenschen(LAUTSTAERKE, wert / 100)

    def _wuenschen(self, art: str, wert: float) -> None:
        with self._neu:
            self._wuensche[art] = wert
            self._neu.notify()

    def wunsch_holen(self, wartezeit: float) -> tuple[str, float] | None:
        """Ältester offener Wunsch (Art, Wert) oder None, wenn in `wartezeit` Sekunden keiner kam."""
        with self._neu:
            if not self._wuensche:
                self._neu.wait(wartezeit)
            if not self._wuensche:
                return None
            art = next(iter(self._wuensche))
            return art, self._wuensche.pop(art)


def routen_anlegen(app, regler: Regler) -> None:
    """GET /radio; POST /radio/sender {"index"}, /radio/lautstaerke {"wert": 0…100}, /radio/stumm {"an"}."""
    from fastapi import HTTPException
    from pydantic import BaseModel, Field

    class Sender(BaseModel):
        index: int

    class Lautstaerke(BaseModel):
        wert: int = Field(ge=0, le=100)

    class Stumm(BaseModel):
        an: bool

    @app.get("/radio")
    def radio() -> dict:
        return regler.zustand()

    @app.post("/radio/sender")
    def sender(daten: Sender) -> dict:
        try:
            regler.wunsch_sender(daten.index)
        except ValueError as fehler:
            raise HTTPException(status_code=422, detail=str(fehler)) from None
        return regler.zustand()

    @app.post("/radio/lautstaerke")
    def lautstaerke(daten: Lautstaerke) -> dict:
        regler.wunsch_lautstaerke(daten.wert)
        return regler.zustand()

    @app.post("/radio/stumm")
    def stumm(daten: Stumm) -> dict:
        regler.stumm_setzen(daten.an)
        return regler.zustand()
