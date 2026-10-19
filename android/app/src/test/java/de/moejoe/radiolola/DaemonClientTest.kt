package de.moejoe.radiolola

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

class DaemonClientTest {
    private fun status(name: String, state: String, error: String? = null) = AppStatus(name, state, error)

    @Test
    fun noAppMeansRadioOff() {
        assertNull(readAppStatus("null"))
        assertNull(readAppStatus(" "))
        assertEquals(Display(Status.OFF), displayFor(null))
    }

    @Test
    fun readsTheDaemonsAnswer() {
        val answer = """{"info": {"name": "radio_lola", "source_kind": "installed", "description": "",
            "url": null, "extra": {}}, "state": "running", "error": null}"""
        assertEquals(status("radio_lola", "running"), readAppStatus(answer))
        val failed = """{"info": {"name": "radio_lola", "source_kind": "installed"}, "state": "error",
            "error": "Process exited with code 1\nValueError: direction: 3"}"""
        assertEquals("Process exited with code 1\nValueError: direction: 3", readAppStatus(failed)?.error)
    }

    @Test
    fun displayPerState() {
        assertEquals(Status.PLAYING, displayFor(status(APP_NAME, "starting")).status)
        assertEquals(Status.PLAYING, displayFor(status(APP_NAME, "running")).status)
        assertEquals(Display(Status.OFF), displayFor(status(APP_NAME, "done")))
        assertEquals(Display(Status.OFF, Hint.Stopping), displayFor(status(APP_NAME, "stopping")))
        assertEquals(
            Display(Status.OFF, Hint.Aborted("ValueError: direction: 3")),
            displayFor(status(APP_NAME, "error", "Process exited with code 1\nValueError: direction: 3\n")),
        )
        assertEquals(
            Display(Status.OFF, Hint.OtherApp("reachy_mini_conversation_app")),
            displayFor(status("reachy_mini_conversation_app", "running")),
        )
    }

    @Test
    fun addressIsCompleted() {
        assertEquals("http://reachy-mini.local:8000", daemonAddress("reachy-mini.local"))
        assertEquals("http://reachy-mini.local:8000", daemonAddress(""))
        assertEquals("http://192.168.1.50:8000", daemonAddress(" 192.168.1.50 "))
        assertEquals("http://192.168.1.50:8000", daemonAddress("http://192.168.1.50:8000/"))
        assertEquals("http://[fe80::1]:8000", daemonAddress("[fe80::1]"))
        assertEquals("http://192.168.1.50:8042", radioAddress("http://192.168.1.50:8000/"))
        assertEquals("http://reachy-mini.local:8042", radioAddress(" reachy-mini.local "))
    }

    @Test
    fun readsTheRadioState() {
        val answer = """{"stations": ["WDR 2", "1LIVE"], "active": 1, "volume": 40, "muted": true}"""
        assertEquals(RadioState(listOf("WDR 2", "1LIVE"), 1, 40, true), readRadioState(answer))
        val noise = """{"stations": [], "active": null, "volume": 100, "muted": false}"""
        assertNull(readRadioState(noise).active)
    }

    @Test
    fun messageDisappearsOnceTheStatusIsThere() {
        assertTrue(messageSettled(Status.PLAYING, Status.PLAYING))
        assertFalse(messageSettled(Status.PLAYING, Status.OFF))
        assertFalse(messageSettled(null, Status.OFF))
    }

    @Test
    fun startOnlyWhenTheSlotIsFree() {
        assertEquals(StartPlan.START, startPlan(null))
        assertEquals(StartPlan.START, startPlan(status(APP_NAME, "done")))
        assertEquals(StartPlan.START, startPlan(status("other", "done")))
        assertEquals(StartPlan.CLEAN_UP_FIRST, startPlan(status(APP_NAME, "error")))
        assertEquals(StartPlan.ALREADY_RUNNING, startPlan(status(APP_NAME, "running")))
        assertEquals(StartPlan.OTHER_APP_RUNNING, startPlan(status("other", "running")))
        assertEquals(StartPlan.OTHER_APP_RUNNING, startPlan(status("other", "error")))
    }

    @Test
    fun stopOnlyStopsTheRadio() {
        assertTrue(stopNeeded(status(APP_NAME, "running")))
        assertTrue(stopNeeded(status(APP_NAME, "error")))
        assertFalse(stopNeeded(status(APP_NAME, "done")))
        assertFalse(stopNeeded(status(APP_NAME, "stopping")))
        assertFalse(stopNeeded(status("other", "running")))
        assertFalse(stopNeeded(null))
    }

    @Test
    fun namesAndUrlsAreEscapedForJson() {
        assertEquals("\"Radio \\\"Eins\\\"\"", jsonText("Radio \"Eins\""))
    }

    @Test
    fun startsInThePhonesLanguage() {
        assertEquals(Language.DE, phoneLanguage(Locale.GERMANY))
        assertEquals(Language.EN, phoneLanguage(Locale.US))
        assertEquals(Language.EN, phoneLanguage(Locale.FRANCE))
    }

    @Test
    fun everyTextExistsInBothLanguages() {
        val de = Texts(Language.DE)
        val en = Texts(Language.EN)
        assertEquals("Radio läuft", de.status(Status.PLAYING))
        assertEquals("Radio playing", en.status(Status.PLAYING))
        assertEquals("Hinzufügen", de.add)
        assertEquals("Delete", en.delete)
        val messages = listOf(
            Message.Starting, Message.Stopping, Message.StartingRadio, Message.AlreadyRunning,
            Message.StopOtherAppFirst("x"), Message.StartRejected("x"), Message.Stopped, Message.NotRunning,
            Message.StopRejected("x"), Message.Unreachable("x"), Message.NoAnswer, Message.Checking,
            Message.Added("x"), Message.Removed("x"), Message.Refused("x"),
        )
        for (message in messages) {
            assertNotEquals(message.toString(), de.message(message), en.message(message))
        }
        val hints = listOf(Hint.OtherApp("x"), Hint.Stopping, Hint.Aborted("x"), Hint.UseIp, Hint.SameNetwork, Hint.Unexpected("x"))
        for (hint in hints) {
            assertNotEquals(hint.toString(), de.hint(hint), en.hint(hint))
        }
    }
}
