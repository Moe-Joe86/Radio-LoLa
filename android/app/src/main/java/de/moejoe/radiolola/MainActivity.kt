package de.moejoe.radiolola

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import org.json.JSONArray
import java.util.concurrent.Executors

/** Ein Bildschirm: Adresse, Zustand, Start/Stopp, Senderliste, Lautstärke mit Stumm, fester Hinweis. Fragt alle 3 s nach. */
class MainActivity : Activity() {
    private val netz = Executors.newSingleThreadExecutor()
    private val haupt = Handler(Looper.getMainLooper())
    private val einstellungen by lazy { getPreferences(MODE_PRIVATE) }
    private lateinit var adresse: EditText
    private lateinit var zustand: TextView
    private lateinit var hinweis: TextView
    private lateinit var meldung: TextView
    private lateinit var knoepfe: List<Button>
    private lateinit var senderListe: LinearLayout
    private lateinit var lautstaerkeText: TextView
    private lateinit var regler: SeekBar
    private lateinit var stumm: Button
    private var sichtbar = false
    private var fragtGerade = false
    private var erwartet: String? = null // Zustand, bei dem die Meldung unter den Knöpfen erledigt ist
    private var radio: RadioZustand? = null
    private var zuletztBedient = 0L // solange jemand den Regler bedient, überschreibt die Abfrage ihn nicht

    private val nachfragen = object : Runnable {
        override fun run() {
            if (!sichtbar) return
            if (!fragtGerade) {
                fragtGerade = true
                val daemon = Daemon(adresse.text.toString())
                netz.execute {
                    val lage = daemon.lage()
                    haupt.post {
                        fragtGerade = false
                        zeigen(lage)
                    }
                }
            }
            haupt.postDelayed(this, 3000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val abstand = dp(16)

        val spalte = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(abstand, abstand, abstand, abstand)
        }
        spalte.addView(text("Adresse des Roboters", 14f))
        adresse = EditText(this).apply {
            setText(einstellungen.getString("adresse", STANDARD_ADRESSE))
            hint = "$STANDARD_ADRESSE oder IP, z. B. 192.168.1.50"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            isSingleLine = true
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
                override fun afterTextChanged(s: Editable?) {
                    einstellungen.edit().putString("adresse", s.toString().trim()).apply()
                }
            })
        }
        spalte.addView(adresse)

        zustand = text("Frage den Roboter …", 28f).apply {
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(0, dp(24), 0, dp(8))
        }
        hinweis = text("", 14f).apply { gravity = Gravity.CENTER }
        spalte.addView(zustand)
        spalte.addView(hinweis)

        val starten = Button(this).apply { text = "Radio starten" }
        val stoppen = Button(this).apply { text = "Radio stoppen" }
        knoepfe = listOf(starten, stoppen)
        starten.setOnClickListener { handeln("Starte …") { it.starten() } }
        stoppen.setOnClickListener { handeln("Stoppe … (die Antennen fahren heim)") { it.stoppen() } }
        val reihe = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(16), 0, dp(8))
        }
        for (knopf in knoepfe) {
            reihe.addView(knopf, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        }
        spalte.addView(reihe)
        meldung = text("", 14f).apply { gravity = Gravity.CENTER }
        spalte.addView(meldung)

        lautstaerkeText = text("Lautstärke", 16f).apply { setPadding(0, dp(24), 0, 0) }
        spalte.addView(lautstaerkeText)
        regler = SeekBar(this).apply {
            max = 100
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, wert: Int, vonHand: Boolean) {
                    if (vonHand) {
                        zuletztBedient = SystemClock.elapsedRealtime()
                        lautstaerkeText.text = "Lautstärke $wert %"
                    }
                }

                override fun onStartTrackingTouch(bar: SeekBar?) = Unit
                override fun onStopTrackingTouch(bar: SeekBar?) {
                    val wert = progress
                    einstellen { it.lautstaerkeSetzen(wert) }
                }
            })
        }
        stumm = Button(this).apply {
            setOnClickListener { radio?.let { r -> einstellen { it.stummSetzen(!r.stumm) } } }
        }
        val reglerReihe = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        reglerReihe.addView(regler, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        reglerReihe.addView(stumm)
        spalte.addView(reglerReihe)

        spalte.addView(text("Sender", 16f).apply {
            setTypeface(typeface, Typeface.BOLD)
            setPadding(0, dp(24), 0, dp(4))
        })
        senderListe = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        spalte.addView(senderListe)

        spalte.addView(text("Nicht gleichzeitig mit LoLa benutzen.", 16f).apply {
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(0, dp(32), 0, 0)
        })

        setContentView(ScrollView(this).apply { addView(spalte) })
        reglerZeigen(null)
        senderZeigen(null)
    }

    private fun zeigen(lage: Lage) {
        zustand.text = lage.anzeige.text
        hinweis.text = lage.anzeige.hinweis
        if (meldungErledigt(erwartet, lage.anzeige.text)) {
            meldung.text = ""
            erwartet = null
        }
        radio = lage.radio
        if (SystemClock.elapsedRealtime() - zuletztBedient > 3000) reglerZeigen(lage.radio)
        senderZeigen(lage.radio)
    }

    private fun reglerZeigen(r: RadioZustand?) {
        regler.isEnabled = r != null
        stumm.isEnabled = r != null
        stumm.text = if (r?.stumm == true) "Ton an" else "Stumm"
        if (r == null) {
            lautstaerkeText.text = "Lautstärke (wenn das Radio läuft)"
            return
        }
        regler.progress = r.lautstaerke
        lautstaerkeText.text = if (r.stumm) "Lautstärke ${r.lautstaerke} % – stumm" else "Lautstärke ${r.lautstaerke} %"
    }

    /** Sender untereinander; der hörbare mit ▶. Ohne laufendes Radio die zuletzt gemeldete Liste. */
    private fun senderZeigen(r: RadioZustand?) {
        val namen = if (r != null) {
            einstellungen.edit().putString("sender", JSONArray(r.sender).toString()).apply()
            r.sender
        } else {
            val gemerkt = JSONArray(einstellungen.getString("sender", "[]"))
            List(gemerkt.length()) { gemerkt.getString(it) }
        }
        senderListe.removeAllViews()
        if (namen.isEmpty()) {
            senderListe.addView(text("Die Liste erscheint, sobald das Radio einmal gelaufen ist.", 14f))
            return
        }
        namen.forEachIndexed { index, name ->
            val spielt = r?.aktiv == index
            senderListe.addView(text(if (spielt) "▶  $name" else "    $name", 18f).apply {
                if (spielt) setTypeface(typeface, Typeface.BOLD)
                alpha = if (r == null) 0.5f else 1f
                setPadding(0, dp(4), 0, dp(4))
            })
        }
    }

    private fun handeln(warten: String, aktion: (Daemon) -> Ergebnis) {
        val daemon = Daemon(adresse.text.toString())
        knoepfe.forEach { it.isEnabled = false }
        meldung.text = warten
        erwartet = null
        netz.execute {
            val ergebnis = try {
                aktion(daemon)
            } catch (fehler: Exception) {
                Ergebnis("$NICHT_ERREICHBAR (${fehler.javaClass.simpleName})")
            }
            haupt.post {
                knoepfe.forEach { it.isEnabled = true }
                erwartet = ergebnis.erwartet
                meldung.text = if (meldungErledigt(erwartet, zustand.text.toString())) "" else ergebnis.meldung
                if (meldung.text.isEmpty()) erwartet = null
            }
        }
    }

    private fun einstellen(aktion: (Daemon) -> RadioZustand?) {
        val daemon = Daemon(adresse.text.toString())
        zuletztBedient = SystemClock.elapsedRealtime()
        netz.execute {
            val neu = try {
                aktion(daemon)
            } catch (fehler: Exception) {
                null
            }
            haupt.post {
                if (neu != null) {
                    radio = neu
                    reglerZeigen(neu)
                } else {
                    meldung.text = "Das Radio antwortet nicht."
                }
            }
        }
    }

    private fun text(inhalt: String, groesse: Float) = TextView(this).apply {
        text = inhalt
        setTextSize(TypedValue.COMPLEX_UNIT_SP, groesse)
    }

    private fun dp(wert: Int) = (wert * resources.displayMetrics.density).toInt()

    override fun onResume() {
        super.onResume()
        sichtbar = true
        haupt.removeCallbacks(nachfragen)
        haupt.post(nachfragen)
    }

    override fun onPause() {
        super.onPause()
        sichtbar = false
        haupt.removeCallbacks(nachfragen)
    }

    override fun onDestroy() {
        super.onDestroy()
        netz.shutdownNow()
    }
}
