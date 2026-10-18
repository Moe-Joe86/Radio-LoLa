package de.moejoe.radiolola

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

// Pfade aus dem Daemon-Code (reachy_mini 1.12.0, daemon/app/routers/apps.py) und der Pollen-Doku (SDK/apps.md):
//   GET  /api/apps/current-app-status   -> null oder {"info": {"name": …}, "state": …, "error": …}
//   POST /api/apps/start-app/{name}     -> 400 „An app is already running“, wenn schon eine App läuft
//   POST /api/apps/stop-current-app     -> wartet, bis die App beendet ist (höchstens etwa 20 s)
// Eine App im Zustand „error“ belegt den Platz weiter; erst stop-current-app gibt ihn frei.

const val APP_NAME = "radio_lola"
const val STANDARD_ADRESSE = "reachy-mini.local"

data class AppStatus(val name: String, val state: String, val error: String?)

/** Was der Bildschirm zeigt: die Hauptzeile und eine kleine Zusatzzeile. */
data class Anzeige(val text: String, val hinweis: String = "")

const val NICHT_ERREICHBAR = "Roboter nicht erreichbar"
const val RADIO_AUS = "Radio aus"
const val RADIO_LAEUFT = "Radio läuft"

private val AKTIV = setOf("starting", "running", "stopping", "error")

/** Antwort von current-app-status als AppStatus, null wenn keine App läuft. */
fun appStatusLesen(antwort: String): AppStatus? {
    val text = antwort.trim()
    if (text.isEmpty() || text == "null") return null
    val json = JSONObject(text)
    val error = if (json.isNull("error")) null else json.optString("error")
    return AppStatus(json.getJSONObject("info").getString("name"), json.getString("state"), error)
}

fun anzeigeFuer(status: AppStatus?): Anzeige = when {
    status == null || status.state == "done" -> Anzeige(RADIO_AUS)
    status.name != APP_NAME -> Anzeige(RADIO_AUS, "Gerade läuft eine andere App: ${status.name}")
    status.state == "starting" || status.state == "running" -> Anzeige(RADIO_LAEUFT)
    status.state == "stopping" -> Anzeige(RADIO_AUS, "Das Radio hält an, die Antennen fahren heim …")
    else -> Anzeige(RADIO_AUS, "Das Radio ist abgebrochen: " + letzteZeile(status.error))
}

private fun letzteZeile(text: String?): String =
    text?.lines()?.lastOrNull { it.isNotBlank() }?.trim() ?: "ohne Meldung"

/** „reachy-mini.local“, „192.168.1.50“ oder „http://…:8000/“ als Basisadresse des Daemons. */
fun basisAdresse(eingabe: String): String {
    var adresse = eingabe.trim().removePrefix("http://").trimEnd('/')
    if (adresse.isEmpty()) adresse = STANDARD_ADRESSE
    if (!adresse.substringAfterLast(']').contains(':')) adresse += ":8000"
    return "http://$adresse"
}

enum class Startplan { STARTEN, ERST_AUFRAEUMEN, ANDERE_APP_LAEUFT, LAEUFT_SCHON }

fun startplan(status: AppStatus?): Startplan = when {
    status == null || status.state == "done" -> Startplan.STARTEN
    status.name != APP_NAME -> if (status.state in AKTIV) Startplan.ANDERE_APP_LAEUFT else Startplan.STARTEN
    status.state == "error" -> Startplan.ERST_AUFRAEUMEN
    else -> Startplan.LAEUFT_SCHON
}

fun stoppenNoetig(status: AppStatus?): Boolean =
    status != null && status.name == APP_NAME && status.state in setOf("starting", "running", "error")

class Daemon(eingabe: String) {
    private val basis = basisAdresse(eingabe)

    private class Antwort(val code: Int, val text: String)

    private fun fragen(methode: String, pfad: String, leseZeit: Int): Antwort {
        val verbindung = URL(basis + pfad).openConnection() as HttpURLConnection
        try {
            verbindung.requestMethod = methode
            verbindung.connectTimeout = 3000
            verbindung.readTimeout = leseZeit
            if (methode == "POST") {
                verbindung.doOutput = true
                verbindung.setFixedLengthStreamingMode(0)
            }
            val code = verbindung.responseCode
            val strom = if (code < 400) verbindung.inputStream else verbindung.errorStream
            return Antwort(code, strom?.bufferedReader()?.use { it.readText() } ?: "")
        } finally {
            verbindung.disconnect()
        }
    }

    private fun aktuellerStatus(): AppStatus? =
        appStatusLesen(fragen("GET", "/api/apps/current-app-status", 4000).text)

    /** Anzeige für den Bildschirm; wirft nie, ein Netzfehler heißt „nicht erreichbar“. */
    fun anzeige(): Anzeige = try {
        anzeigeFuer(aktuellerStatus())
    } catch (fehler: IOException) {
        val tipp = if (basis.contains(".local")) {
            "Wenn das so bleibt: oben die IP-Adresse des Roboters eintragen, z. B. 192.168.1.50."
        } else {
            "Ist der Roboter eingeschaltet und im selben WLAN?"
        }
        Anzeige(NICHT_ERREICHBAR, tipp)
    } catch (fehler: Exception) {
        Anzeige(NICHT_ERREICHBAR, "Unerwartete Antwort: ${fehler.message}")
    }

    /** Startet das Radio; gibt eine Meldung für den Bildschirm zurück. */
    fun starten(): String {
        val status = aktuellerStatus()
        when (startplan(status)) {
            Startplan.LAEUFT_SCHON -> return "Das Radio läuft schon."
            Startplan.ANDERE_APP_LAEUFT -> return "Erst die andere App stoppen: ${status?.name}"
            Startplan.ERST_AUFRAEUMEN -> fragen("POST", "/api/apps/stop-current-app", 30000)
            Startplan.STARTEN -> Unit
        }
        val antwort = fragen("POST", "/api/apps/start-app/$APP_NAME", 15000)
        return if (antwort.code == 200) "Radio wird gestartet …" else "Start abgelehnt: ${fehlertext(antwort)}"
    }

    /** Stoppt das Radio, aber nie eine andere App. */
    fun stoppen(): String {
        if (!stoppenNoetig(aktuellerStatus())) return "Das Radio läuft nicht."
        val antwort = fragen("POST", "/api/apps/stop-current-app", 30000)
        return if (antwort.code == 200) "Radio gestoppt." else "Stopp abgelehnt: ${fehlertext(antwort)}"
    }

    private fun fehlertext(antwort: Antwort): String = try {
        JSONObject(antwort.text).optString("detail", antwort.text)
    } catch (fehler: Exception) {
        "Fehler ${antwort.code}"
    }
}
