package de.moejoe.radiolola

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.util.concurrent.Executors

/** Ein Bildschirm: Adresse, Zustand, zwei Knöpfe, fester Hinweis. Fragt alle 3 s beim Daemon nach. */
class MainActivity : Activity() {
    private val netz = Executors.newSingleThreadExecutor()
    private val haupt = Handler(Looper.getMainLooper())
    private lateinit var adresse: EditText
    private lateinit var zustand: TextView
    private lateinit var hinweis: TextView
    private lateinit var meldung: TextView
    private lateinit var knoepfe: List<Button>
    private var sichtbar = false
    private var fragtGerade = false

    private val nachfragen = object : Runnable {
        override fun run() {
            if (!sichtbar) return
            if (!fragtGerade) {
                fragtGerade = true
                val daemon = Daemon(adresse.text.toString())
                netz.execute {
                    val anzeige = daemon.anzeige()
                    haupt.post {
                        fragtGerade = false
                        zustand.text = anzeige.text
                        hinweis.text = anzeige.hinweis
                    }
                }
            }
            haupt.postDelayed(this, 3000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val einstellungen = getPreferences(MODE_PRIVATE)
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
            setPadding(0, dp(32), 0, dp(8))
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
            setPadding(0, dp(24), 0, dp(8))
        }
        for (knopf in knoepfe) {
            reihe.addView(knopf, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        }
        spalte.addView(reihe)
        meldung = text("", 14f).apply { gravity = Gravity.CENTER }
        spalte.addView(meldung)

        spalte.addView(text("Nicht gleichzeitig mit LoLa benutzen.", 16f).apply {
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(0, dp(40), 0, 0)
        })

        setContentView(ScrollView(this).apply { addView(spalte) })
    }

    private fun handeln(warten: String, aktion: (Daemon) -> String) {
        val daemon = Daemon(adresse.text.toString())
        knoepfe.forEach { it.isEnabled = false }
        meldung.text = warten
        netz.execute {
            val text = try {
                aktion(daemon)
            } catch (fehler: Exception) {
                "$NICHT_ERREICHBAR (${fehler.javaClass.simpleName})"
            }
            haupt.post {
                meldung.text = text
                knoepfe.forEach { it.isEnabled = true }
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
