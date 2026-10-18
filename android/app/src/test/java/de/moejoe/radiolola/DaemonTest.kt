package de.moejoe.radiolola

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DaemonTest {
    private fun status(name: String, state: String, error: String? = null) = AppStatus(name, state, error)

    @Test
    fun keineAppHeisstRadioAus() {
        assertNull(appStatusLesen("null"))
        assertNull(appStatusLesen(" "))
        assertEquals(Anzeige(RADIO_AUS), anzeigeFuer(null))
    }

    @Test
    fun antwortDesDaemonsWirdGelesen() {
        val antwort = """{"info": {"name": "radio_lola", "source_kind": "installed", "description": "",
            "url": null, "extra": {}}, "state": "running", "error": null}"""
        assertEquals(status("radio_lola", "running"), appStatusLesen(antwort))
        val fehler = """{"info": {"name": "radio_lola", "source_kind": "installed"}, "state": "error",
            "error": "Process exited with code 1\nValueError: richtung: 3"}"""
        assertEquals("Process exited with code 1\nValueError: richtung: 3", appStatusLesen(fehler)?.error)
    }

    @Test
    fun anzeigeJeZustand() {
        assertEquals(RADIO_LAEUFT, anzeigeFuer(status(APP_NAME, "starting")).text)
        assertEquals(RADIO_LAEUFT, anzeigeFuer(status(APP_NAME, "running")).text)
        assertEquals(Anzeige(RADIO_AUS), anzeigeFuer(status(APP_NAME, "done")))
        assertEquals(RADIO_AUS, anzeigeFuer(status(APP_NAME, "stopping")).text)
        assertEquals(
            Anzeige(RADIO_AUS, "Das Radio ist abgebrochen: ValueError: richtung: 3"),
            anzeigeFuer(status(APP_NAME, "error", "Process exited with code 1\nValueError: richtung: 3\n")),
        )
        assertEquals(
            Anzeige(RADIO_AUS, "Gerade läuft eine andere App: reachy_mini_conversation_app"),
            anzeigeFuer(status("reachy_mini_conversation_app", "running")),
        )
    }

    @Test
    fun adresseWirdErgaenzt() {
        assertEquals("http://reachy-mini.local:8000", basisAdresse("reachy-mini.local"))
        assertEquals("http://reachy-mini.local:8000", basisAdresse(""))
        assertEquals("http://192.168.1.50:8000", basisAdresse(" 192.168.1.50 "))
        assertEquals("http://192.168.1.50:8000", basisAdresse("http://192.168.1.50:8000/"))
        assertEquals("http://[fe80::1]:8000", basisAdresse("[fe80::1]"))
        assertEquals("http://192.168.1.50:8042", radioAdresse("http://192.168.1.50:8000/"))
        assertEquals("http://reachy-mini.local:8042", radioAdresse(" reachy-mini.local "))
    }

    @Test
    fun radioZustandWirdGelesen() {
        val antwort = """{"sender": ["Deutschlandfunk", "WDR 2"], "aktiv": 1, "lautstaerke": 40, "stumm": true}"""
        assertEquals(RadioZustand(listOf("Deutschlandfunk", "WDR 2"), 1, 40, true), radioZustandLesen(antwort))
        val rauschen = """{"sender": [], "aktiv": null, "lautstaerke": 100, "stumm": false}"""
        assertNull(radioZustandLesen(rauschen).aktiv)
    }

    @Test
    fun meldungVerschwindetSobaldDerZustandDaIst() {
        assertTrue(meldungErledigt(RADIO_LAEUFT, RADIO_LAEUFT))
        assertFalse(meldungErledigt(RADIO_LAEUFT, RADIO_AUS))
        assertFalse(meldungErledigt(null, RADIO_AUS))
    }

    @Test
    fun startNurWennDerPlatzFreiIst() {
        assertEquals(Startplan.STARTEN, startplan(null))
        assertEquals(Startplan.STARTEN, startplan(status(APP_NAME, "done")))
        assertEquals(Startplan.STARTEN, startplan(status("andere", "done")))
        assertEquals(Startplan.ERST_AUFRAEUMEN, startplan(status(APP_NAME, "error")))
        assertEquals(Startplan.LAEUFT_SCHON, startplan(status(APP_NAME, "running")))
        assertEquals(Startplan.ANDERE_APP_LAEUFT, startplan(status("andere", "running")))
        assertEquals(Startplan.ANDERE_APP_LAEUFT, startplan(status("andere", "error")))
    }

    @Test
    fun stoppStopptNurDasRadio() {
        assertTrue(stoppenNoetig(status(APP_NAME, "running")))
        assertTrue(stoppenNoetig(status(APP_NAME, "error")))
        assertFalse(stoppenNoetig(status(APP_NAME, "done")))
        assertFalse(stoppenNoetig(status(APP_NAME, "stopping")))
        assertFalse(stoppenNoetig(status("andere", "running")))
        assertFalse(stoppenNoetig(null))
    }
}
