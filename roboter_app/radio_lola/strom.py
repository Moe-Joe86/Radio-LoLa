"""Aufgabe: Empfängt einen Radio-Stream über GStreamer als 16 kHz mono und hält einen kurzen Puffer bereit.

Knöpfe: `Strom` (`starten`, `lesen`, `beenden`, `schritt`), `gstreamer_quelle`, `fehlende_faehigkeiten`, `Abbruch`.
Darf nicht: Ton wiederholen (fehlt etwas, kommt Stille), neue Abhängigkeiten nutzen (GStreamer kommt mit reachy-mini).
"""
# Bricht der Stream ab (Fehler, Ende oder 5 s ohne Ton), verbindet `schritt` neu: erst nach 1 s, dann mit
# doppelter Wartezeit bis 30 s. Der Puffer hält höchstens 2 s; was älter ist, fällt weg. Daten sind
# float32 (4 Bytes je Abtastwert), ohne numpy, damit die Datei ohne Roboter testbar bleibt.

import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

ABTASTRATE = 16000
BYTES_JE_WERT = 4
PUFFER_SEKUNDEN = 2.0
STILLE_GRENZE = 5.0  # so lange ohne Ton gilt der Stream als abgebrochen
ERSTE_WARTEZEIT, LAENGSTE_WARTEZEIT = 1.0, 30.0

log = logging.getLogger("radio.strom")


class Abbruch(Exception):
    """Die Quelle meldet Fehler oder Ende."""


class Quelle(Protocol):
    def lesen(self, wartezeit: float) -> bytes: ...
    def schliessen(self) -> None: ...


class _GstQuelle:
    def __init__(self, adresse: str) -> None:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        self._gst = Gst
        self._strang = Gst.parse_launch(
            f'uridecodebin uri="{adresse}" ! audioconvert ! audioresample ! '
            f"audio/x-raw,format=F32LE,channels=1,rate={ABTASTRATE},layout=interleaved ! "
            "appsink name=senke sync=false max-buffers=50 drop=true"
        )
        self._senke = self._strang.get_by_name("senke")
        self._strang.set_state(Gst.State.PLAYING)

    def lesen(self, wartezeit: float) -> bytes:
        gst = self._gst
        meldung = self._strang.get_bus().pop_filtered(gst.MessageType.ERROR | gst.MessageType.EOS)
        if meldung is not None:
            grund = meldung.parse_error()[0].message if meldung.type == gst.MessageType.ERROR else "Ende des Streams"
            raise Abbruch(grund)
        probe = self._senke.emit("try-pull-sample", int(wartezeit * 1e9))
        if probe is None:
            return b""
        puffer = probe.get_buffer()
        return puffer.extract_dup(0, puffer.get_size())

    def schliessen(self) -> None:
        self._strang.set_state(self._gst.State.NULL)


def gstreamer_quelle(adresse: str) -> Quelle:
    return _GstQuelle(adresse)


# Welche GStreamer-Bausteine auf dem Roboter liegen, ist nicht gemessen; je Fähigkeit genügt einer der Bausteine.
FAEHIGKEITEN = {
    "Grundbausteine": (("uridecodebin",), ("audioconvert",), ("audioresample",), ("appsink",)),
    "Empfang über http/https": (("souphttpsrc",),),
    "MP3": (("mpg123audiodec", "avdec_mp3", "mad"),),
    "AAC": (("avdec_aac", "faad", "fdkaacdec"),),
}


def fehlende_faehigkeiten(vorhanden: Callable[[str], bool] | None = None) -> list[str]:
    """Namen der Fähigkeiten aus `FAEHIGKEITEN`, für die ein GStreamer-Baustein fehlt; leer, wenn alles da ist."""
    if vorhanden is None:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        vorhanden = lambda name: Gst.ElementFactory.find(name) is not None  # noqa: E731
    return [name for name, gruppen in FAEHIGKEITEN.items()
            if not all(any(vorhanden(b) for b in gruppe) for gruppe in gruppen)]


class Strom:
    def __init__(self, adresse: str, oeffnen: Callable[[str], Quelle] = gstreamer_quelle,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self.adresse, self._oeffnen, self._uhr = adresse, oeffnen, uhr
        self._quelle: Quelle | None = None
        self._puffer = bytearray()
        self._sperre = threading.Lock()
        self._ende = threading.Event()
        self._wartezeit = ERSTE_WARTEZEIT
        self._naechster_versuch = 0.0
        self._letzter_ton = 0.0
        self.versuche = 0

    def schritt(self) -> None:
        """Ein Arbeitsschritt: verbinden, wenn es Zeit ist, sonst lesen und Abbrüche erkennen."""
        jetzt = self._uhr()
        if self._quelle is None:
            if jetzt >= self._naechster_versuch:
                self._verbinden(jetzt)
            return
        try:
            daten = self._quelle.lesen(0.2)
        except Abbruch as fehler:
            self._trennen(f"abgebrochen ({fehler})")
            return
        if daten:
            self._letzter_ton, self._wartezeit = jetzt, ERSTE_WARTEZEIT
            with self._sperre:
                self._puffer += daten
                del self._puffer[: max(0, len(self._puffer) - int(PUFFER_SEKUNDEN * ABTASTRATE * BYTES_JE_WERT))]
        elif jetzt - self._letzter_ton > STILLE_GRENZE:
            self._trennen(f"seit {STILLE_GRENZE:g} s kein Ton")

    def _verbinden(self, jetzt: float) -> None:
        self.versuche += 1
        try:
            self._quelle = self._oeffnen(self.adresse)
            self._letzter_ton = jetzt
        except Exception as fehler:  # GStreamer wirft unterschiedliche Fehler; jeder heißt: später neu versuchen
            self._quelle = None
            self._planen(jetzt, f"nicht erreichbar ({fehler})")

    def _trennen(self, grund: str) -> None:
        if self._quelle is not None:
            self._quelle.schliessen()
        self._quelle = None
        self._planen(self._uhr(), grund)

    def _planen(self, jetzt: float, grund: str) -> None:
        log.warning("Radio: %s %s, neuer Versuch in %g s", self.adresse, grund, self._wartezeit)
        self._naechster_versuch = jetzt + self._wartezeit
        self._wartezeit = min(self._wartezeit * 2, LAENGSTE_WARTEZEIT)

    def lesen(self, anzahl_bytes: int) -> bytes:
        """Genau `anzahl_bytes`: was im Puffer liegt, der Rest Stille. Gelesenes kommt nie ein zweites Mal."""
        with self._sperre:
            daten = bytes(self._puffer[:anzahl_bytes])
            del self._puffer[:anzahl_bytes]
        return daten + bytes(anzahl_bytes - len(daten))

    def starten(self) -> None:
        threading.Thread(target=self._laufen, daemon=True, name=f"strom {self.adresse}").start()

    def beenden(self) -> None:
        """Kehrt sofort zurück; der Empfang schließt sich im eigenen Faden."""
        self._ende.set()

    def _laufen(self) -> None:
        while not self._ende.is_set():
            self.schritt()
            if self._quelle is None:
                self._ende.wait(0.1)
        if self._quelle is not None:
            self._quelle.schliessen()
