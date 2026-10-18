import pytest

from radio_lola.abstimmung import (
    HOECHSTE,
    angleichen,
    feld,
    gerichtet,
    lautstaerke,
    pegel,
    ziel_lautstaerke,
    ziel_sender,
)

SENDER, RAUSCHEN = "sender", ("rauschen", None)


def test_ein_sender_halber_kreis_sender_halber_rauschen():
    assert feld(0, 1) == (SENDER, 0)
    assert feld(179.9, 1) == (SENDER, 0)
    assert feld(180, 1) == RAUSCHEN
    assert feld(359.9, 1) == RAUSCHEN


@pytest.mark.parametrize(("winkel", "erwartet"), [
    (0, (SENDER, 0)), (44.9, (SENDER, 0)), (45, RAUSCHEN), (89.9, RAUSCHEN),
    (90, (SENDER, 1)), (135, RAUSCHEN), (180, (SENDER, 2)), (225, RAUSCHEN),
    (270, (SENDER, 3)), (314.9, (SENDER, 3)), (315, RAUSCHEN), (359.9, RAUSCHEN),
])
def test_vier_sender_in_felder_zu_je_45_grad(winkel, erwartet):
    """Der Anfang gehört zum Feld, das Ende nicht."""
    assert feld(winkel, 4) == erwartet


@pytest.mark.parametrize(("winkel", "gleich"), [(360, 0), (405, 45), (450, 90), (720 + 100, 100), (-45, 315),
                                                (-90, 270), (-360, 0), (-1, 359)])
def test_winkel_ueber_360_oder_negativ(winkel, gleich):
    assert feld(winkel, 4) == feld(gleich, 4)
    assert pegel(winkel, 4, ueberblendung=6) == pegel(gleich, 4, ueberblendung=6)


def test_zaehlrichtung_dreht_den_winkel_um():
    assert gerichtet(30, 1) == 30
    assert gerichtet(30, -1) == 330
    assert gerichtet(-400, 1) == 320


def test_begrenzter_bereich_teilt_nur_diesen_bereich():
    """270° für 3 Sender: Felder zu je 45°, alles ab 270° ist Rauschen."""
    assert feld(0, 3, 270) == (SENDER, 0)
    assert feld(45, 3, 270) == RAUSCHEN
    assert feld(90, 3, 270) == (SENDER, 1)
    assert feld(180, 3, 270) == (SENDER, 2)
    assert feld(225, 3, 270) == RAUSCHEN
    assert feld(270, 3, 270) == RAUSCHEN
    assert feld(300, 3, 270) == RAUSCHEN


def test_ohne_sender_nur_rauschen():
    assert feld(10, 0) == RAUSCHEN
    assert pegel(10, 0, ueberblendung=6) == (None, 0.0)


def test_ohne_ueberblendung_hart_wie_die_felder():
    for zehntel in range(3600):
        winkel = zehntel / 10
        art, index = feld(winkel, 4)
        sender, anteil = pegel(winkel, 4)
        assert anteil == (1.0 if art == SENDER else 0.0), winkel
        if art == SENDER:
            assert sender == index


@pytest.mark.parametrize(("winkel", "erwartet"), [
    (45, (0, 0.5)), (42, (0, 1.0)), (43.5, (0, 0.75)), (46.5, (0, 0.25)), (48, (0, 0.0)), (67, (0, 0.0)),
    (90, (1, 0.5)), (88.5, (1, 0.25)), (91.5, (1, 0.75)), (0, (0, 0.5)), (358.5, (0, 0.25)), (1.5, (0, 0.75)),
])
def test_ueberblendung_an_den_feldraendern(winkel, erwartet):
    """6° Überblendung: am Rand halb und halb, 3° weiter innen nur Sender, 3° weiter außen nur Rauschen."""
    sender, anteil = pegel(winkel, 4, ueberblendung=6)
    assert (sender, round(anteil, 6)) == erwartet


def test_ueberblendung_springt_nicht_beim_zittern():
    """Kleine Bewegung am Rand ändert den Anteil nur wenig."""
    vorher = pegel(44.8, 4, ueberblendung=6)[1]
    nachher = pegel(45.2, 4, ueberblendung=6)[1]
    assert abs(vorher - nachher) < 0.1


def test_begrenzter_bereich_blendet_auch_ueber_null():
    """Bei 270° liegt vor 0° Rauschen außerhalb des Bereichs; Sender 0 blendet trotzdem weich ein."""
    assert pegel(359, 3, 270, 6) == (0, pytest.approx(1 / 3))
    assert pegel(280, 3, 270, 6) == (2, 0.0)


@pytest.mark.parametrize(("roh", "anteil"), [
    (0, 0.0), (-90, 0.25), (-180, 0.5), (-270, 0.75), (1, 359 / 360), (360, 0.0), (-450, 0.25), (90, 0.75),
])
def test_lautstaerke_steigt_gegen_den_uhrzeigersinn_sprung_oben(roh, anteil):
    assert lautstaerke(roh) == pytest.approx(anteil)


def test_lautstaerke_folgt_weich():
    stufen = [0.0]
    for _ in range(25):
        stufen.append(angleichen(stufen[-1], 1.0))
    assert all(abs(b - a) <= 0.05 + 1e-9 for a, b in zip(stufen, stufen[1:], strict=False))
    assert stufen[-1] == pytest.approx(1.0)
    assert angleichen(0.5, 0.52) == pytest.approx(0.52)
    assert angleichen(0.5, 0.0) == pytest.approx(0.45)


@pytest.mark.parametrize(("index", "jetzt", "ziel"), [(0, 0, 22.5), (1, 0, 112.5), (3, 0, -67.5), (2, 1000, 922.5),
                                                     (0, -700, -697.5)])
def test_ziel_sender_ist_die_feldmitte_auf_kurzem_weg(index, jetzt, ziel):
    assert ziel_sender(index, 4, jetzt) == pytest.approx(ziel)
    assert feld(ziel_sender(index, 4, jetzt), 4) == ("sender", index)
    assert pegel(ziel_sender(index, 4, jetzt), 4, ueberblendung=6) == (index, 1.0)


def test_ziel_sender_mit_zaehlrichtung_und_bereich():
    roh = ziel_sender(1, 3, 0, bereich=270, richtung=-1)
    assert pegel(gerichtet(roh, -1), 3, 270, 6) == (1, 1.0)


@pytest.mark.parametrize(("anteil", "jetzt"), [(0.25, 90), (0.9, -10), (0.0, -300), (1.0, -20), (0.5, 1000)])
def test_ziel_lautstaerke_trifft_ohne_ueber_den_sprung_zu_fahren(anteil, jetzt):
    ziel = ziel_lautstaerke(anteil, jetzt)
    assert lautstaerke(ziel) == pytest.approx(min(anteil, HOECHSTE))
    zwischen = [lautstaerke(jetzt + (ziel - jetzt) * k / 20) for k in range(21)]
    assert zwischen == sorted(zwischen) or zwischen == sorted(zwischen, reverse=True)
