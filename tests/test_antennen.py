import pytest

from radio_lola.antennen import (
    LINKS,
    RECHTS,
    bester_weg,
    dauer,
    faehrt_hinein,
    heimweg,
    nach_oben,
    zeigt_nach_innen,
    zuege,
)


@pytest.mark.parametrize(("index", "roh", "innen"), [
    (RECHTS, 90, True), (RECHTS, 10, True), (RECHTS, -10, False), (RECHTS, 270, False), (RECHTS, 0, False),
    (RECHTS, 1080, False), (RECHTS, 1086, True), (RECHTS, 450, True),
    (LINKS, 270, True), (LINKS, -10, True), (LINKS, 10, False), (LINKS, 90, False),
    (LINKS, -1440, False), (LINKS, -1444, True),
])
def test_innen_heisst_zur_anderen_antenne(index, roh, innen):
    assert zeigt_nach_innen(index, roh) is innen


@pytest.mark.parametrize(("index", "roh", "ziel"), [
    (RECHTS, 45, 0), (RECHTS, 135, 360), (RECHTS, 270, 360), (RECHTS, 1086, 1080), (RECHTS, 720, 720),
    (LINKS, 315, 360), (LINKS, 225, 0), (LINKS, 90, 0), (LINKS, -1444, -1440),
])
def test_nach_oben_verlaesst_die_innere_haelfte_auf_kurzem_weg(index, roh, ziel):
    assert nach_oben(index, roh) == ziel


def test_nie_beide_gleichzeitig():
    vorher = (1086.0, -1444.0)
    for ziel in heimweg(*vorher):
        assert sum(a != b for a, b in zip(vorher, ziel, strict=True)) == 1
        vorher = ziel


def test_innere_antenne_parkt_zuerst_dann_die_andere_ganz_dann_die_erste():
    """Rechts zeigt nach innen (45°), links nach außen (90°): rechts parkt oben, links dreht heim, dann rechts."""
    assert heimweg(45.0, 90.0) == [(0.0, 90.0), (0.0, 0.0)]
    assert heimweg(405.0, 450.0) == [(360.0, 450.0), (360.0, 0.0), (0.0, 0.0)]


def test_messwerte_vom_15_oktober():
    """+1086° und −1444°: beide fast oben, je 4 bis 6° nach innen; links parkt, rechts dreht heim, dann links."""
    assert heimweg(1086.3, -1443.6) == [(1086.3, -1440.0), (0.0, -1440.0), (0.0, 0.0)]


def test_beide_innen_links_parkt_zuerst():
    assert heimweg(90.0, 270.0) == [(90.0, 0.0), (0.0, 0.0)]


def test_schon_daheim_nichts_zu_tun():
    assert heimweg(0.0, 0.0) == []


def test_dauer_hoechstens_eine_runde_je_sekunde():
    assert dauer((1086.0, 0.0), (0.0, 0.0)) == pytest.approx(1086 / 360)
    assert dauer((0.0, 0.0), (0.0, 10.0)) == 0.3


@pytest.mark.parametrize(("index", "von", "nach", "hinein"), [
    (RECHTS, 270, 350, False), (RECHTS, 350, 370, True), (RECHTS, 90, 200, False), (RECHTS, 200, 900, True),
    (RECHTS, 10, 30, True), (LINKS, 10, 170, False), (LINKS, 170, 190, True), (LINKS, 270, 90, False),
    (LINKS, 360, 540, False),
])
def test_faehrt_hinein_nur_hinausfahren_ist_harmlos(index, von, nach, hinein):
    assert faehrt_hinein(index, von, nach) is hinein


def test_fahrt_ohne_gefahr_bewegt_nur_die_eine_antenne():
    assert zuege(RECHTS, 225.0, 10.0, 30.0) == [(RECHTS, 225.0)]
    assert zuege(LINKS, 270.0, 300.0, 90.0) == [(LINKS, 270.0)]
    assert zuege(LINKS, 90.0, 300.0, 90.0) == []


def test_fahrt_nach_innen_parkt_die_innere_andere_antenne():
    """Rechts soll in seine innere Hälfte, links zeigt nach innen: links parkt, rechts fährt, links kehrt zurück."""
    assert zuege(RECHTS, 405.0, 300.0, 270.0) == [(LINKS, 0.0), (RECHTS, 405.0), (LINKS, 270.0)]


def test_bester_weg_nimmt_den_umweg_aussen_herum():
    # Von 200° nach 340° (außen) direkt wäre außen; rückwärts über innen hieße parken
    assert bester_weg(RECHTS, [340.0, -20.0], 200.0, 270.0) == [(RECHTS, 340.0)]
    # Von 350° nach 190°: kurz vorwärts über 0° ginge durch innen, außen herum rückwärts ohne Parken
    assert bester_weg(RECHTS, [550.0, 190.0], 350.0, 270.0) == [(RECHTS, 190.0)]
