package de.moejoe.radiolola

import java.util.Locale

enum class Language { DE, EN }

/** The language the app starts with before anyone switches: German on German phones, otherwise English. */
fun phoneLanguage(locale: Locale = Locale.getDefault()): Language =
    if (locale.language == "de") Language.DE else Language.EN

/** Every text on the screen in German and English. Details from the robot or the daemon stay as they come. */
class Texts(val language: Language) {
    private fun t(de: String, en: String) = if (language == Language.DE) de else en

    val robotAddress = t("Adresse des Roboters", "Robot address")
    val addressHint = t("$DEFAULT_ADDRESS oder IP, z. B. 192.168.1.50", "$DEFAULT_ADDRESS or IP, e.g. 192.168.1.50")
    val asking = t("Frage den Roboter …", "Asking the robot …")
    val startRadio = t("Radio starten", "Start radio")
    val stopRadio = t("Radio stoppen", "Stop radio")
    val volume = t("Lautstärke", "Volume")
    val mute = t("Stumm", "Mute")
    val soundOn = t("Ton an", "Sound on")
    val muted = t("stumm", "muted")
    val stations = t("Sender", "Stations")
    val listAppears = t(
        "Die Liste erscheint, sobald das Radio einmal gelaufen ist.",
        "The list appears once the radio has been running.",
    )
    val add = t("Hinzufügen", "Add")
    val delete = t("Entfernen", "Delete")
    val addTitle = t("Sender hinzufügen", "Add station")
    val streamUrl = t("Stream-Adresse (http://… oder https://…)", "Stream address (http://… or https://…)")
    val nameOptional = t("Name (freiwillig, sonst vom Sender)", "Name (optional, otherwise from the station)")
    val ok = "OK"
    val cancel = t("Abbrechen", "Cancel")
    val deleteTitle = t("Welchen Sender entfernen?", "Which station should be removed?")
    val full = t("Höchstens $MAX_STATIONS Sender. Bitte erst einen entfernen.", "At most $MAX_STATIONS stations. Please remove one first.")
    val lastOne = t("Der letzte Sender bleibt.", "The last station stays.")

    fun confirmDelete(name: String) = t("„$name“ entfernen?", "Remove “$name”?")

    fun status(status: Status) = when (status) {
        Status.UNREACHABLE -> t("Roboter nicht erreichbar", "Robot not reachable")
        Status.OFF -> t("Radio aus", "Radio off")
        Status.PLAYING -> t("Radio läuft", "Radio playing")
    }

    fun hint(hint: Hint) = when (hint) {
        Hint.None -> ""
        is Hint.OtherApp -> t("Gerade läuft eine andere App: ${hint.name}", "Another app is running: ${hint.name}")
        Hint.Stopping -> t("Das Radio hält an, die Antennen fahren heim …", "The radio is stopping, the antennas go home …")
        is Hint.Aborted -> t("Das Radio ist abgebrochen: ", "The radio stopped with an error: ") +
            hint.reason.ifEmpty { t("ohne Meldung", "no message") }
        Hint.UseIp -> t(
            "Wenn das so bleibt: unten die IP-Adresse des Roboters eintragen, z. B. 192.168.1.50.",
            "If this persists: enter the robot's IP address below, e.g. 192.168.1.50.",
        )
        Hint.SameNetwork -> t("Ist der Roboter eingeschaltet und im selben WLAN?", "Is the robot switched on and on the same Wi-Fi?")
        is Hint.Unexpected -> t("Unerwartete Antwort: ", "Unexpected answer: ") + hint.detail
    }

    fun message(message: Message) = when (message) {
        Message.Starting -> t("Starte …", "Starting …")
        Message.Stopping -> t("Stoppe … die Antennen fahren heim", "Stopping … the antennas go home")
        Message.StartingRadio -> t("Radio wird gestartet …", "Radio is starting …")
        Message.AlreadyRunning -> t("Das Radio läuft schon.", "The radio is already playing.")
        is Message.StopOtherAppFirst -> t("Erst die andere App stoppen: ", "Stop the other app first: ") + message.name
        is Message.StartRejected -> t("Start abgelehnt: ", "Start refused: ") + message.detail
        Message.Stopped -> t("Radio gestoppt.", "Radio stopped.")
        Message.NotRunning -> t("Das Radio läuft nicht.", "The radio is not playing.")
        is Message.StopRejected -> t("Stopp abgelehnt: ", "Stop refused: ") + message.detail
        is Message.Unreachable -> t("Roboter nicht erreichbar", "Robot not reachable") + " (${message.kind})"
        Message.NoAnswer -> t("Das Radio antwortet nicht.", "The radio does not answer.")
        Message.Checking -> t("Prüfe den Stream …", "Checking the stream …")
        is Message.Added -> t("„${message.name}“ hinzugefügt.", "“${message.name}” added.")
        is Message.Removed -> t("„${message.name}“ entfernt.", "“${message.name}” removed.")
        is Message.Refused -> t("Nicht möglich: ", "Not possible: ") + message.detail
    }
}
