package de.moejoe.radiolola

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

// Paths from the daemon code (reachy_mini 1.12.0, daemon/app/routers/apps.py) and Pollen's docs (SDK/apps.md):
//   GET  /api/apps/current-app-status   -> null or {"info": {"name": …}, "state": …, "error": …}
//   POST /api/apps/start-app/{name}     -> 400 "An app is already running" if an app runs already
//   POST /api/apps/stop-current-app     -> waits until the app has ended (at most about 20 s)
// An app in state "error" still occupies the slot; only stop-current-app frees it.
// While the radio runs, its own web server answers on port 8042 as well (robot_app/radio_lola/control.py):
//   GET  /radio  -> {"stations": [names], "active": index or null, "volume": 0…100, "muted": …}
//   POST /radio/station {"index"}  /radio/volume {"value": 0…100}  /radio/mute {"on"}
//   POST /radio/stations/add {"url", "name"?}  /radio/stations/delete {"index"}  -> 422 {"detail": reason}
// Station and volume are wishes: the robot drives the matching antenna there, and "active" and "volume" then show
// again what the antennas say. This file holds no texts; `Texts.kt` turns the results into German or English.

const val APP_NAME = "radio_lola"
const val DEFAULT_ADDRESS = "reachy-mini.local"
const val MAX_STATIONS = 8

data class AppStatus(val name: String, val state: String, val error: String?)

enum class Status { UNREACHABLE, OFF, PLAYING }

/** The small extra line under the status. */
sealed interface Hint {
    data object None : Hint
    data class OtherApp(val name: String) : Hint
    data object Stopping : Hint
    data class Aborted(val reason: String) : Hint
    data object UseIp : Hint
    data object SameNetwork : Hint
    data class Unexpected(val detail: String) : Hint
}

data class Display(val status: Status, val hint: Hint = Hint.None)

data class RadioState(val stations: List<String>, val active: Int?, val volume: Int, val muted: Boolean)

/** The message under the buttons. Details coming from the robot or the daemon stay in English. */
sealed interface Message {
    data object Starting : Message
    data object Stopping : Message
    data object StartingRadio : Message
    data object AlreadyRunning : Message
    data class StopOtherAppFirst(val name: String) : Message
    data class StartRejected(val detail: String) : Message
    data object Stopped : Message
    data object NotRunning : Message
    data class StopRejected(val detail: String) : Message
    data class Unreachable(val kind: String) : Message
    data object NoAnswer : Message
    data object Checking : Message
    data class Added(val name: String) : Message
    data class Removed(val name: String) : Message
    data class Refused(val detail: String) : Message
}

/** What an action reports, and which status settles the message (then it disappears). */
data class Outcome(val message: Message, val expected: Status? = null)

/** Result of adding or removing a station: the new state, or the robot's reason for refusing. */
data class Change(val state: RadioState?, val refusal: String?)

/** Status of the robot and, if the radio runs and already answers, the state of the radio. */
data class Situation(val display: Display, val radio: RadioState? = null)

private val OCCUPYING = setOf("starting", "running", "stopping", "error")

/** Answer of current-app-status as AppStatus, null when no app runs. */
fun readAppStatus(answer: String): AppStatus? {
    val text = answer.trim()
    if (text.isEmpty() || text == "null") return null
    val json = JSONObject(text)
    val error = if (json.isNull("error")) null else json.optString("error")
    return AppStatus(json.getJSONObject("info").getString("name"), json.getString("state"), error)
}

fun displayFor(status: AppStatus?): Display = when {
    status == null || status.state == "done" -> Display(Status.OFF)
    status.name != APP_NAME -> Display(Status.OFF, Hint.OtherApp(status.name))
    status.state == "starting" || status.state == "running" -> Display(Status.PLAYING)
    status.state == "stopping" -> Display(Status.OFF, Hint.Stopping)
    else -> Display(Status.OFF, Hint.Aborted(lastLine(status.error)))
}

private fun lastLine(text: String?): String = text?.lines()?.lastOrNull { it.isNotBlank() }?.trim() ?: ""

/** Host name or IP from "reachy-mini.local", "192.168.1.50" or "http://…:8000/", without port. */
fun host(input: String): String {
    val address = input.trim().removePrefix("http://").substringBefore('/')
    val withoutPort = if (address.substringAfterLast(']').contains(':')) address.substringBeforeLast(':') else address
    return withoutPort.ifEmpty { DEFAULT_ADDRESS }
}

fun daemonAddress(input: String): String = "http://${host(input)}:8000"

fun radioAddress(input: String): String = "http://${host(input)}:8042"

fun readRadioState(answer: String): RadioState {
    val json = JSONObject(answer)
    val list = json.getJSONArray("stations")
    return RadioState(
        stations = List(list.length()) { list.getString(it) },
        active = if (json.isNull("active")) null else json.getInt("active"),
        volume = json.getInt("volume"),
        muted = json.getBoolean("muted"),
    )
}

/** The message under the buttons disappears as soon as the status it waits for has arrived. */
fun messageSettled(expected: Status?, status: Status?): Boolean = expected != null && expected == status

enum class StartPlan { START, CLEAN_UP_FIRST, OTHER_APP_RUNNING, ALREADY_RUNNING }

fun startPlan(status: AppStatus?): StartPlan = when {
    status == null || status.state == "done" -> StartPlan.START
    status.name != APP_NAME -> if (status.state in OCCUPYING) StartPlan.OTHER_APP_RUNNING else StartPlan.START
    status.state == "error" -> StartPlan.CLEAN_UP_FIRST
    else -> StartPlan.ALREADY_RUNNING
}

fun stopNeeded(status: AppStatus?): Boolean =
    status != null && status.name == APP_NAME && status.state in setOf("starting", "running", "error")

/** A string as JSON value, quotes and backslashes escaped. */
fun jsonText(text: String): String = JSONObject.quote(text)

class DaemonClient(input: String) {
    private val daemon = daemonAddress(input)
    private val radio = radioAddress(input)

    private class Answer(val code: Int, val text: String)

    private fun ask(method: String, path: String, readTime: Int, json: String? = null, base: String = daemon): Answer {
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 3000
            connection.readTimeout = readTime
            if (method == "POST") {
                val body = (json ?: "").toByteArray()
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setFixedLengthStreamingMode(body.size)
                connection.outputStream.use { it.write(body) }
            }
            val code = connection.responseCode
            val stream = if (code < 400) connection.inputStream else connection.errorStream
            return Answer(code, stream?.bufferedReader()?.use { it.readText() } ?: "")
        } finally {
            connection.disconnect()
        }
    }

    private fun currentStatus(): AppStatus? = readAppStatus(ask("GET", "/api/apps/current-app-status", 4000).text)

    /** Situation for the screen; never throws, a network error means "unreachable". */
    fun situation(): Situation {
        val display = display()
        return if (display.status == Status.PLAYING) Situation(display, radioState()) else Situation(display)
    }

    /** Null while the radio's web server does not answer yet (in the first seconds after the start). */
    private fun radioState(): RadioState? = try {
        val answer = ask("GET", "/radio", 3000, base = radio)
        if (answer.code == 200) readRadioState(answer.text) else null
    } catch (error: Exception) {
        null
    }

    fun tuneTo(index: Int): RadioState? = adjust("/radio/station", "{\"index\": $index}")

    fun setVolume(value: Int): RadioState? = adjust("/radio/volume", "{\"value\": $value}")

    fun setMuted(on: Boolean): RadioState? = adjust("/radio/mute", "{\"on\": $on}")

    private fun adjust(path: String, json: String): RadioState? {
        val answer = ask("POST", path, 3000, json, radio)
        return if (answer.code == 200) readRadioState(answer.text) else null
    }

    /** Checking a new stream can take a few seconds on the robot. */
    fun addStation(url: String, name: String): Change {
        val json = "{\"url\": ${jsonText(url.trim())}, \"name\": ${jsonText(name.trim())}}"
        return change(ask("POST", "/radio/stations/add", 20000, json, radio))
    }

    fun deleteStation(index: Int): Change = change(ask("POST", "/radio/stations/delete", 5000, "{\"index\": $index}", radio))

    private fun change(answer: Answer): Change =
        if (answer.code == 200) Change(readRadioState(answer.text), null) else Change(null, errorText(answer))

    private fun display(): Display = try {
        displayFor(currentStatus())
    } catch (error: IOException) {
        Display(Status.UNREACHABLE, if (daemon.contains(".local")) Hint.UseIp else Hint.SameNetwork)
    } catch (error: Exception) {
        Display(Status.UNREACHABLE, Hint.Unexpected(error.message ?: ""))
    }

    fun start(): Outcome {
        val status = currentStatus()
        when (startPlan(status)) {
            StartPlan.ALREADY_RUNNING -> return Outcome(Message.AlreadyRunning, Status.PLAYING)
            StartPlan.OTHER_APP_RUNNING -> return Outcome(Message.StopOtherAppFirst(status?.name ?: ""))
            StartPlan.CLEAN_UP_FIRST -> ask("POST", "/api/apps/stop-current-app", 30000)
            StartPlan.START -> Unit
        }
        val answer = ask("POST", "/api/apps/start-app/$APP_NAME", 15000)
        return if (answer.code == 200) {
            Outcome(Message.StartingRadio, Status.PLAYING)
        } else {
            Outcome(Message.StartRejected(errorText(answer)))
        }
    }

    /** Stops the radio, but never another app. */
    fun stop(): Outcome {
        if (!stopNeeded(currentStatus())) return Outcome(Message.NotRunning, Status.OFF)
        val answer = ask("POST", "/api/apps/stop-current-app", 30000)
        return if (answer.code == 200) Outcome(Message.Stopped, Status.OFF) else Outcome(Message.StopRejected(errorText(answer)))
    }

    private fun errorText(answer: Answer): String = try {
        JSONObject(answer.text).optString("detail", answer.text)
    } catch (error: Exception) {
        "error ${answer.code}"
    }
}
