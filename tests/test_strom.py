from radio_lola.strom import BYTES_JE_WERT, Abbruch, Strom


class Uhr:
    def __init__(self) -> None:
        self.jetzt = 0.0

    def __call__(self) -> float:
        return self.jetzt


class Quelle:
    """Attrappe: liefert der Reihe nach Daten, leere Antworten oder einen Abbruch."""

    def __init__(self, folge: list) -> None:
        self.folge, self.geschlossen = list(folge), False

    def lesen(self, wartezeit: float) -> bytes:
        teil = self.folge.pop(0) if self.folge else b""
        if isinstance(teil, Exception):
            raise teil
        return teil

    def schliessen(self) -> None:
        self.geschlossen = True


def strom_mit(*quellen):
    geoeffnet, uhr = [], Uhr()

    def oeffnen(adresse):
        if not quellen[len(geoeffnet)]:
            geoeffnet.append(None)
            raise OSError("nicht erreichbar")
        geoeffnet.append(quellen[len(geoeffnet)])
        return geoeffnet[-1]

    return Strom("http://sender.example/", oeffnen, uhr), uhr, geoeffnet


def test_liefert_gepufferten_ton_dann_stille_ohne_wiederholung():
    strom, _, _ = strom_mit(Quelle([b"\x01" * 8]))
    strom.schritt()  # verbinden
    strom.schritt()  # lesen
    assert strom.lesen(12) == b"\x01" * 8 + bytes(4)
    assert strom.lesen(8) == bytes(8)


def test_verbindet_nach_abbruch_neu():
    erste, zweite = Quelle([b"\x01" * 4, Abbruch("Ende des Streams")]), Quelle([b"\x02" * 4])
    strom, uhr, geoeffnet = strom_mit(erste, zweite)
    for _ in range(3):
        strom.schritt()
    assert erste.geschlossen and len(geoeffnet) == 1
    strom.schritt()  # zu früh: wartet 1 s
    assert len(geoeffnet) == 1
    uhr.jetzt = 1.0
    strom.schritt()
    strom.schritt()
    assert len(geoeffnet) == 2
    assert strom.lesen(8) == b"\x01" * 4 + b"\x02" * 4


def test_fuenf_sekunden_ohne_ton_gelten_als_abbruch():
    erste = Quelle([])
    strom, uhr, geoeffnet = strom_mit(erste, Quelle([]))
    strom.schritt()
    uhr.jetzt = 5.5
    strom.schritt()
    assert erste.geschlossen
    uhr.jetzt = 6.5
    strom.schritt()
    assert len(geoeffnet) == 2


def test_wartezeit_verdoppelt_sich_bis_30_sekunden():
    strom, uhr, geoeffnet = strom_mit(*([None] * 8))
    zeiten = []
    while len(zeiten) < 7:
        anzahl = len(geoeffnet)
        strom.schritt()
        if len(geoeffnet) > anzahl:
            zeiten.append(uhr.jetzt)
        uhr.jetzt += 0.5
    assert [b - a for a, b in zip(zeiten, zeiten[1:], strict=False)] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]


def test_puffer_haelt_hoechstens_zwei_sekunden():
    block = b"\x03" * 16000 * BYTES_JE_WERT  # eine Sekunde
    strom, _, _ = strom_mit(Quelle([block, block, block, b"\x04" * 4]))
    for _ in range(5):
        strom.schritt()
    daten = strom.lesen(3 * len(block))
    assert daten[: 2 * len(block) - 4] == b"\x03" * (2 * len(block) - 4)
    assert daten[2 * len(block) - 4: 2 * len(block)] == b"\x04" * 4
    assert daten[2 * len(block):] == bytes(len(block))


def test_fehlende_faehigkeiten_nennt_was_gstreamer_nicht_kann():
    from radio_lola.strom import fehlende_faehigkeiten

    alles = {"uridecodebin", "audioconvert", "audioresample", "appsink", "souphttpsrc", "mpg123audiodec", "faad"}
    assert fehlende_faehigkeiten(alles.__contains__) == []
    assert fehlende_faehigkeiten((alles - {"faad"}).__contains__) == ["AAC"]
    assert fehlende_faehigkeiten((alles - {"souphttpsrc", "appsink"}).__contains__) == [
        "Grundbausteine", "Empfang über http/https"]
