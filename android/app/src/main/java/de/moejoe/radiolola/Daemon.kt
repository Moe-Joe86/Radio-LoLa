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
// Solange das Radio läuft, antwortet zusätzlich sein eigener Webserver auf Port 8042 (roboter_app/…/steuerung.py):
//   GET  /radio              -> {"sender": [Namen], "aktiv": Index oder null, "lautstaerke": 0…100, "stumm": …}
//   POST /radio/sender {"index": n}   POST /radio/lautstaerke {"wert": 0…100}   POST /radio/stumm {"an": true|false}
// Sender und Lautstärke sind Wünsche: Der Roboter fährt die passende Antenne dorthin, „aktiv“ und „lautstaerke“
// zeigen danach wieder, was die Antennen sagen.

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

/** Rechnername oder IP aus „reachy-mini.local“, „192.168.1.50“ oder „http://…:8000/“, ohne Port. */
fun rechner(eingabe: String): String {
    val adresse = eingabe.trim().removePrefix("http://").substringBefore('/')
    val ohnePort = if (adresse.substringAfterLast(']').contains(':')) adresse.substringBeforeLast(':') else adresse
    return ohnePort.ifEmpty { STANDARD_ADRESSE }
}

fun basisAdresse(eingabe: String): String = "http://${rechner(eingabe)}:8000"

fun radioAdresse(eingabe: String): String = "http://${rechner(eingabe)}:8042"

data class RadioZustand(val sender: List<String>, val aktiv: Int?, val lautstaerke: Int, val stumm: Boolean)

fun radioZustandLesen(antwort: String): RadioZustand {
    val json = JSONObject(antwort)
    val liste = json.getJSONArray("sender")
    return RadioZustand(
        sender = List(liste.length()) { liste.getString(it) },
        aktiv = if (json.isNull("aktiv")) null else json.getInt("aktiv"),
        lautstaerke = json.getInt("lautstaerke"),
        stumm = json.getBoolean("stumm"),
    )
}

/** Was eine Handlung meldet und welcher Zustand die Meldung erledigt (dann verschwindet sie). */
data class Ergebnis(val meldung: String, val erwartet: String? = null)

/** Die Meldung unter den Knöpfen verschwindet, sobald der Zustand eingetreten ist, auf den sie wartet. */
fun meldungErledigt(erwartet: String?, zustand: String): Boolean = erwartet != null && erwartet == zustand

/** Zustand des Roboters und, wenn das Radio läuft und schon antwortet, der Zustand des Radios. */
data class Lage(val anzeige: Anzeige, val radio: RadioZustand? = null)

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
    private val radio = radioAdresse(eingabe)

    private class Antwort(val code: Int, val text: String)

    private fun fragen(methode: String, pfad: String, leseZeit: Int, json: String? = null, ziel: String = basis): Antwort {
        val verbindung = URL(ziel + pfad).openConnection() as HttpURLConnection
        try {
            verbindung.requestMethod = methode
            verbindung.connectTimeout = 3000
            verbindung.readTimeout = leseZeit
            if (methode == "POST") {
                val inhalt = (json ?: "").toByteArray()
                verbindung.doOutput = true
                verbindung.setRequestProperty("Content-Type", "application/json")
                verbindung.setFixedLengthStreamingMode(inhalt.size)
                verbindung.outputStream.use { it.write(inhalt) }
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

    /** Lage für den Bildschirm; wirft nie, ein Netzfehler heißt „nicht erreichbar“. */
    fun lage(): Lage {
        val anzeige = anzeige()
        return if (anzeige.text == RADIO_LAEUFT) Lage(anzeige, radioZustand()) else Lage(anzeige)
    }

    /** Null, solange der Webserver des Radios noch nicht antwortet (in den ersten Sekunden nach dem Start). */
    private fun radioZustand(): RadioZustand? = try {
        val antwort = fragen("GET", "/radio", 3000, ziel = radio)
        if (antwort.code == 200) radioZustandLesen(antwort.text) else null
    } catch (fehler: Exception) {
        null
    }

    fun senderWaehlen(index: Int): RadioZustand? = einstellen("/radio/sender", "{\"index\": $index}")

    fun lautstaerkeSetzen(wert: Int): RadioZustand? = einstellen("/radio/lautstaerke", "{\"wert\": $wert}")

    fun stummSetzen(an: Boolean): RadioZustand? = einstellen("/radio/stumm", "{\"an\": $an}")

    private fun einstellen(pfad: String, json: String): RadioZustand? {
        val antwort = fragen("POST", pfad, 3000, json, radio)
        return if (antwort.code == 200) radioZustandLesen(antwort.text) else null
    }

    private fun anzeige(): Anzeige = try {
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

    /** Startet das Radio. */
    fun starten(): Ergebnis {
        val status = aktuellerStatus()
        when (startplan(status)) {
            Startplan.LAEUFT_SCHON -> return Ergebnis("Das Radio läuft schon.", RADIO_LAEUFT)
            Startplan.ANDERE_APP_LAEUFT -> return Ergebnis("Erst die andere App stoppen: ${status?.name}")
            Startplan.ERST_AUFRAEUMEN -> fragen("POST", "/api/apps/stop-current-app", 30000)
            Startplan.STARTEN -> Unit
        }
        val antwort = fragen("POST", "/api/apps/start-app/$APP_NAME", 15000)
        return if (antwort.code == 200) {
            Ergebnis("Radio wird gestartet …", RADIO_LAEUFT)
        } else {
            Ergebnis("Start abgelehnt: ${fehlertext(antwort)}")
        }
    }

    /** Stoppt das Radio, aber nie eine andere App. */
    fun stoppen(): Ergebnis {
        if (!stoppenNoetig(aktuellerStatus())) return Ergebnis("Das Radio läuft nicht.", RADIO_AUS)
        val antwort = fragen("POST", "/api/apps/stop-current-app", 30000)
        return if (antwort.code == 200) Ergebnis("Radio gestoppt.", RADIO_AUS) else Ergebnis("Stopp abgelehnt: ${fehlertext(antwort)}")
    }

    private fun fehlertext(antwort: Antwort): String = try {
        JSONObject(antwort.text).optString("detail", antwort.text)
    } catch (fehler: Exception) {
        "Fehler ${antwort.code}"
    }
}
