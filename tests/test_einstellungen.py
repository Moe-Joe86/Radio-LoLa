import pytest

from radio_lola.einstellungen import DATEI, laden, sender_lesen


def test_standardwerte_ohne_datei(tmp_path):
    e = laden(tmp_path / "fehlt.toml")
    assert (e.sender, e.lautstaerke, e.bereich, e.richtung, e.ueberblendung) == ([], 0.6, 360.0, 1, 6.0)


def test_mitgelieferte_datei_ist_gueltig():
    e = laden(DATEI)
    assert len(e.sender) >= 1
    assert all(adresse.startswith("https://") for _, adresse in e.sender)
    assert (e.lautstaerke, e.bereich, e.richtung, e.ueberblendung) == (0.6, 360.0, 1, 6.0)


def test_werte_aus_der_datei(tmp_path):
    datei = tmp_path / "einstellungen.toml"
    datei.write_text(
        "lautstaerke = 80\nbereich_grad = 270\nrichtung = -1\nueberblendung_grad = 4.5\n"
        '[[sender]]\nname = "Eins"\nadresse = "https://eins.example/stream.mp3"\n'
        '[[sender]]\nname = " Zwei "\nadresse = "http://zwei.example/a.aac"\n',
        encoding="utf-8",
    )
    e = laden(datei)
    assert e.sender == [("Eins", "https://eins.example/stream.mp3"), ("Zwei", "http://zwei.example/a.aac")]
    assert (e.lautstaerke, e.bereich, e.richtung, e.ueberblendung) == (0.8, 270.0, -1, 4.5)


@pytest.mark.parametrize(("eintraege", "meldung"), [
    ([{"name": "Eins"}], "adresse"), ([{"name": "Eins", "adresse": "ftp://x"}], "adresse"),
    ([{"adresse": "https://x"}], "name fehlt"), ([{"name": "  ", "adresse": "https://x"}], "name fehlt"),
    ([{"name": "Eins", "adresse": "https://x", "url": "y"}], "unbekannt ist url"), ("Eins|https://x", "Block"),
])
def test_fehlerhafter_sender_bricht_ab(eintraege, meldung):
    with pytest.raises(ValueError, match=meldung):
        sender_lesen(eintraege)


@pytest.mark.parametrize(("zeile", "name"), [
    ("lautstaerke = 120", "lautstaerke"), ('lautstaerke = "laut"', "lautstaerke"),
    ("bereich_grad = 400", "bereich_grad"),
    ("richtung = 2", "richtung"), ("ueberblendung_grad = -1", "ueberblendung_grad"), ("volume = 50", "unbekannt"),
    ("lautstaerke = ", "Schreibfehler"), ("richtung = true", "richtung"),
])
def test_fehlerhafte_werte_brechen_mit_namen_ab(tmp_path, zeile, name):
    datei = tmp_path / "einstellungen.toml"
    datei.write_text(zeile + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=name):
        laden(datei)
