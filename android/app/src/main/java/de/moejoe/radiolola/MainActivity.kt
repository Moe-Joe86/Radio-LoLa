package de.moejoe.radiolola

import android.app.Activity
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import org.json.JSONArray
import java.util.concurrent.Executors

// Farben: dunkler Grund mit warmem Akzent, passend zum Holzradio im Symbol.
private val GRUND_OBEN = Color.parseColor("#171A26")
private val GRUND_UNTEN = Color.parseColor("#2B211B")
private val KARTE = Color.parseColor("#262A3A")
private val FELD = Color.parseColor("#33384C")
private val AKZENT = Color.parseColor("#E0A458")
private val SCHRIFT = Color.parseColor("#F4F1EC")
private val LEISE = Color.parseColor("#A7ABBB")
private val GRUEN = Color.parseColor("#6FCF97")
private val ROT = Color.parseColor("#EB6B5E")

/** Ein Bildschirm: Zustand, Start/Stopp, Lautstärke mit Stumm, Sender zum Antippen, Adresse. Fragt laufend nach. */
class MainActivity : Activity() {
    private val netz = Executors.newSingleThreadExecutor()
    private val haupt = Handler(Looper.getMainLooper())
    private val einstellungen by lazy { getPreferences(MODE_PRIVATE) }
    private lateinit var adresse: EditText
    private lateinit var punkt: View
    private lateinit var zustand: TextView
    private lateinit var hinweis: TextView
    private lateinit var meldung: TextView
    private lateinit var knoepfe: List<Button>
    private lateinit var senderListe: LinearLayout
    private lateinit var lautstaerkeWert: TextView
    private lateinit var regler: SeekBar
    private lateinit var stumm: Button
    private var sichtbar = false
    private var fragtGerade = false
    private var erwartet: String? = null // Zustand, bei dem die Meldung unter den Knöpfen erledigt ist
    private var radio: RadioZustand? = null
    private var zuletztBedient = 0L // so lange überschreibt die Abfrage den Regler nicht, während die Antenne fährt

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
            haupt.postDelayed(this, 1500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = GRUND_OBEN
        window.navigationBarColor = GRUND_UNTEN

        val spalte = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(32))
        }

        // Kopf: Symbol und Name
        val kopf = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        kopf.addView(ImageView(this).apply { setImageResource(R.mipmap.ic_launcher) }, LinearLayout.LayoutParams(dp(56), dp(56)))
        kopf.addView(text("Radio LoLa", 26f, SCHRIFT, fett = true).apply { setPadding(dp(14), 0, 0, 0) })
        spalte.addView(kopf)

        // Zustand
        val zustandKarte = karte()
        val zeile = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        punkt = View(this).apply { background = rund(LEISE, dp(6).toFloat()) }
        zeile.addView(punkt, LinearLayout.LayoutParams(dp(12), dp(12)))
        zustand = text("Frage den Roboter …", 22f, SCHRIFT, fett = true).apply { setPadding(dp(12), 0, 0, 0) }
        zeile.addView(zustand)
        zustandKarte.addView(zeile)
        hinweis = text("", 14f, LEISE).apply { setPadding(0, dp(6), 0, 0) }
        zustandKarte.addView(hinweis)

        val starten = knopf("Radio starten", AKZENT, GRUND_OBEN)
        val stoppen = knopf("Radio stoppen", FELD, SCHRIFT)
        knoepfe = listOf(starten, stoppen)
        starten.setOnClickListener { handeln("Starte …") { it.starten() } }
        stoppen.setOnClickListener { handeln("Stoppe … die Antennen fahren heim") { it.stoppen() } }
        val reihe = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(16), 0, 0)
        }
        reihe.addView(starten, LinearLayout.LayoutParams(0, dp(52), 1f).apply { marginEnd = dp(6) })
        reihe.addView(stoppen, LinearLayout.LayoutParams(0, dp(52), 1f).apply { marginStart = dp(6) })
        zustandKarte.addView(reihe)
        meldung = text("", 14f, AKZENT).apply {
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, 0)
        }
        zustandKarte.addView(meldung)
        spalte.addView(zustandKarte)

        // Lautstärke: der Regler stellt die Lautstärke-Antenne
        val lautKarte = karte()
        val lautKopf = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        lautKopf.addView(text("Lautstärke", 16f, SCHRIFT, fett = true), LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        lautstaerkeWert = text("", 16f, AKZENT, fett = true)
        lautKopf.addView(lautstaerkeWert)
        lautKarte.addView(lautKopf)
        regler = SeekBar(this).apply {
            max = 100
            progressTintList = ColorStateList.valueOf(AKZENT)
            thumbTintList = ColorStateList.valueOf(AKZENT)
            progressBackgroundTintList = ColorStateList.valueOf(LEISE)
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, wert: Int, vonHand: Boolean) {
                    if (vonHand) {
                        zuletztBedient = SystemClock.elapsedRealtime()
                        lautstaerkeWert.text = "$wert %"
                    }
                }

                override fun onStartTrackingTouch(bar: SeekBar?) = Unit
                override fun onStopTrackingTouch(bar: SeekBar?) {
                    val wert = progress
                    einstellen { it.lautstaerkeSetzen(wert) }
                }
            })
        }
        stumm = knopf("Stumm", FELD, SCHRIFT).apply {
            setOnClickListener { radio?.let { r -> einstellen(warten = false) { it.stummSetzen(!r.stumm) } } }
        }
        val reglerReihe = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(8), 0, 0)
        }
        reglerReihe.addView(regler, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        reglerReihe.addView(stumm, LinearLayout.LayoutParams(dp(110), dp(44)).apply { marginStart = dp(8) })
        lautKarte.addView(reglerReihe)
        spalte.addView(lautKarte)

        // Sender zum Antippen: die Sender-Antenne fährt hin
        val senderKarte = karte()
        senderKarte.addView(text("Sender", 16f, SCHRIFT, fett = true))
        senderListe = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(6), 0, 0)
        }
        senderKarte.addView(senderListe)
        spalte.addView(senderKarte)

        // Adresse
        val adressKarte = karte()
        adressKarte.addView(text("Adresse des Roboters", 13f, LEISE))
        adresse = EditText(this).apply {
            setText(einstellungen.getString("adresse", STANDARD_ADRESSE))
            hint = "$STANDARD_ADRESSE oder IP, z. B. 192.168.1.50"
            setTextColor(SCHRIFT)
            setHintTextColor(LEISE)
            backgroundTintList = ColorStateList.valueOf(LEISE)
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
        adressKarte.addView(adresse)
        spalte.addView(adressKarte)

        setContentView(ScrollView(this).apply {
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, intArrayOf(GRUND_OBEN, GRUND_UNTEN))
            isFillViewport = true
            addView(spalte)
        })
        reglerZeigen(null)
        senderZeigen(null)
    }

    private fun zeigen(lage: Lage) {
        zustand.text = lage.anzeige.text
        hinweis.text = lage.anzeige.hinweis
        hinweis.visibility = if (lage.anzeige.hinweis.isEmpty()) View.GONE else View.VISIBLE
        punkt.background = rund(
            when (lage.anzeige.text) {
                RADIO_LAEUFT -> GRUEN
                NICHT_ERREICHBAR -> ROT
                else -> LEISE
            },
            dp(6).toFloat(),
        )
        if (meldungErledigt(erwartet, lage.anzeige.text)) {
            meldung.text = ""
            erwartet = null
        }
        radio = lage.radio
        if (SystemClock.elapsedRealtime() - zuletztBedient > 4000) reglerZeigen(lage.radio)
        senderZeigen(lage.radio)
    }

    private fun reglerZeigen(r: RadioZustand?) {
        regler.isEnabled = r != null
        stumm.isEnabled = r != null
        regler.alpha = if (r == null) 0.4f else 1f
        stumm.alpha = if (r == null) 0.4f else 1f
        stumm.text = if (r?.stumm == true) "Ton an" else "Stumm"
        stumm.background = rund(if (r?.stumm == true) AKZENT else FELD, dp(22).toFloat())
        stumm.setTextColor(if (r?.stumm == true) GRUND_OBEN else SCHRIFT)
        if (r == null) {
            lautstaerkeWert.text = "–"
            return
        }
        regler.progress = r.lautstaerke
        lautstaerkeWert.text = if (r.stumm) "stumm" else "${r.lautstaerke} %"
    }

    /** Sender untereinander zum Antippen; der hörbare hervorgehoben. Ohne laufendes Radio die zuletzt gemeldete Liste. */
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
            senderListe.addView(text("Die Liste erscheint, sobald das Radio einmal gelaufen ist.", 14f, LEISE))
            return
        }
        namen.forEachIndexed { index, name ->
            val spielt = r?.aktiv == index
            val zeile = text(if (spielt) "▶   $name" else name, 17f, if (spielt) GRUND_OBEN else SCHRIFT, fett = spielt).apply {
                background = rund(if (spielt) AKZENT else FELD, dp(14).toFloat())
                setPadding(dp(16), dp(14), dp(16), dp(14))
                alpha = if (r == null) 0.45f else 1f
                isClickable = r != null
                if (r != null) setOnClickListener { einstellen { it.senderWaehlen(index) } }
            }
            senderListe.addView(zeile, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = dp(8)
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

    /** Wunsch ans Radio; bei Sender und Lautstärke fährt danach eine Antenne, die Anzeige folgt ihr. */
    private fun einstellen(warten: Boolean = true, aktion: (Daemon) -> RadioZustand?) {
        val daemon = Daemon(adresse.text.toString())
        if (warten) zuletztBedient = SystemClock.elapsedRealtime()
        netz.execute {
            val neu = try {
                aktion(daemon)
            } catch (fehler: Exception) {
                null
            }
            haupt.post {
                if (neu == null) {
                    meldung.text = "Das Radio antwortet nicht."
                } else if (!warten) {
                    radio = neu
                    reglerZeigen(neu)
                }
            }
        }
    }

    private fun karte() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = rund(KARTE, dp(22).toFloat())
        setPadding(dp(18), dp(16), dp(18), dp(18))
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(16)
        }
    }

    private fun knopf(beschriftung: String, farbe: Int, schrift: Int) = Button(this).apply {
        text = beschriftung
        isAllCaps = false
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        setTypeface(typeface, Typeface.BOLD)
        setTextColor(schrift)
        background = rund(farbe, dp(26).toFloat())
        stateListAnimator = null
    }

    private fun rund(farbe: Int, radius: Float) = GradientDrawable().apply {
        setColor(farbe)
        cornerRadius = radius
    }

    private fun text(inhalt: String, groesse: Float, farbe: Int, fett: Boolean = false) = TextView(this).apply {
        text = inhalt
        setTextColor(farbe)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, groesse)
        if (fett) setTypeface(typeface, Typeface.BOLD)
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
