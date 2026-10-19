package de.moejoe.radiolola

import android.app.Activity
import android.app.AlertDialog
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

// Colours: dark background with a warm accent, matching the wooden radio in the icon.
private val BACKGROUND_TOP = Color.parseColor("#171A26")
private val BACKGROUND_BOTTOM = Color.parseColor("#2B211B")
private val CARD = Color.parseColor("#262A3A")
private val FIELD = Color.parseColor("#33384C")
private val ACCENT = Color.parseColor("#E0A458")
private val TEXT = Color.parseColor("#F4F1EC")
private val DIM = Color.parseColor("#A7ABBB")
private val GREEN = Color.parseColor("#6FCF97")
private val RED = Color.parseColor("#EB6B5E")

/** One screen: status, start/stop, volume with mute, stations to tap, add/delete, address, language. Polls. */
class MainActivity : Activity() {
    private val network = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private val preferences by lazy { getPreferences(MODE_PRIVATE) }
    private lateinit var texts: Texts
    private lateinit var address: EditText
    private lateinit var dot: View
    private lateinit var statusLine: TextView
    private lateinit var hintLine: TextView
    private lateinit var messageLine: TextView
    private lateinit var buttons: List<Button>
    private lateinit var stationList: LinearLayout
    private lateinit var addButton: Button
    private lateinit var deleteButton: Button
    private lateinit var volumeValue: TextView
    private lateinit var slider: SeekBar
    private lateinit var mute: Button
    private var visible = false
    private var asking = false
    private var status: Status? = null
    private var expected: Status? = null // status that settles the message under the buttons
    private var radio: RadioState? = null
    private var lastTouched = 0L // meanwhile the poll does not overwrite the slider, while the antenna moves

    private val poll = object : Runnable {
        override fun run() {
            if (!visible) return
            if (!asking) {
                asking = true
                val client = client()
                network.execute {
                    val situation = client.situation()
                    main.post {
                        asking = false
                        show(situation)
                    }
                }
            }
            main.postDelayed(this, 1500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        texts = Texts(preferences.getString("language", null)?.let { Language.valueOf(it) } ?: phoneLanguage())
        window.statusBarColor = BACKGROUND_TOP
        window.navigationBarColor = BACKGROUND_BOTTOM

        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(32))
        }
        column.addView(header())
        column.addView(statusCard())
        column.addView(volumeCard())
        column.addView(stationCard())
        column.addView(addressCard())

        setContentView(ScrollView(this).apply {
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, intArrayOf(BACKGROUND_TOP, BACKGROUND_BOTTOM))
            isFillViewport = true
            addView(column)
        })
        showVolume(null)
        showStations(null)
    }

    private fun header() = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        addView(ImageView(context).apply { setImageResource(R.mipmap.ic_launcher) }, LinearLayout.LayoutParams(dp(56), dp(56)))
        addView(
            text("Radio LoLa", 26f, TEXT, bold = true).apply { setPadding(dp(14), 0, 0, 0) },
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f),
        )
        for (language in Language.entries) {
            val chosen = language == texts.language
            addView(text(language.name, 14f, if (chosen) BACKGROUND_TOP else TEXT, bold = true).apply {
                background = round(if (chosen) ACCENT else FIELD, dp(14).toFloat())
                setPadding(dp(12), dp(6), dp(12), dp(6))
                if (!chosen) {
                    setOnClickListener {
                        preferences.edit().putString("language", language.name).apply()
                        recreate()
                    }
                }
            }, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                marginStart = dp(6)
            })
        }
    }

    private fun statusCard() = card().apply {
        val row = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        dot = View(context).apply { background = round(DIM, dp(6).toFloat()) }
        row.addView(dot, LinearLayout.LayoutParams(dp(12), dp(12)))
        statusLine = text(texts.asking, 22f, TEXT, bold = true).apply { setPadding(dp(12), 0, 0, 0) }
        row.addView(statusLine)
        addView(row)
        hintLine = text("", 14f, DIM).apply { setPadding(0, dp(6), 0, 0) }
        addView(hintLine)

        val start = button(texts.startRadio, ACCENT, BACKGROUND_TOP)
        val stop = button(texts.stopRadio, FIELD, TEXT)
        buttons = listOf(start, stop)
        start.setOnClickListener { act(Message.Starting) { it.start() } }
        stop.setOnClickListener { act(Message.Stopping) { it.stop() } }
        val pair = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(16), 0, 0)
        }
        pair.addView(start, LinearLayout.LayoutParams(0, dp(52), 1f).apply { marginEnd = dp(6) })
        pair.addView(stop, LinearLayout.LayoutParams(0, dp(52), 1f).apply { marginStart = dp(6) })
        addView(pair)
        messageLine = text("", 14f, ACCENT).apply {
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, 0)
        }
        addView(messageLine)
    }

    /** The slider sets the volume antenna. */
    private fun volumeCard() = card().apply {
        val top = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        top.addView(text(texts.volume, 16f, TEXT, bold = true), LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        volumeValue = text("", 16f, ACCENT, bold = true)
        top.addView(volumeValue)
        addView(top)
        slider = SeekBar(context).apply {
            max = 100
            progressTintList = ColorStateList.valueOf(ACCENT)
            thumbTintList = ColorStateList.valueOf(ACCENT)
            progressBackgroundTintList = ColorStateList.valueOf(DIM)
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, value: Int, byHand: Boolean) {
                    if (byHand) {
                        lastTouched = SystemClock.elapsedRealtime()
                        volumeValue.text = "$value %"
                    }
                }

                override fun onStartTrackingTouch(bar: SeekBar?) = Unit
                override fun onStopTrackingTouch(bar: SeekBar?) {
                    val value = progress
                    adjust { it.setVolume(value) }
                }
            })
        }
        mute = button(texts.mute, FIELD, TEXT).apply {
            setOnClickListener { radio?.let { r -> adjust(wait = false) { it.setMuted(!r.muted) } } }
        }
        val row = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(8), 0, 0)
        }
        row.addView(slider, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(mute, LinearLayout.LayoutParams(dp(110), dp(44)).apply { marginStart = dp(8) })
        addView(row)
    }

    /** Stations to tap (the tuning antenna drives there), plus add and delete. */
    private fun stationCard() = card().apply {
        addView(text(texts.stations, 16f, TEXT, bold = true))
        stationList = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(6), 0, 0)
        }
        addView(stationList)
        addButton = button(texts.add, FIELD, TEXT).apply { setOnClickListener { askForNewStation() } }
        deleteButton = button(texts.delete, FIELD, TEXT).apply { setOnClickListener { askWhichToDelete() } }
        val pair = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(14), 0, 0)
        }
        pair.addView(addButton, LinearLayout.LayoutParams(0, dp(46), 1f).apply { marginEnd = dp(6) })
        pair.addView(deleteButton, LinearLayout.LayoutParams(0, dp(46), 1f).apply { marginStart = dp(6) })
        addView(pair)
    }

    private fun addressCard() = card().apply {
        addView(text(texts.robotAddress, 13f, DIM))
        address = EditText(context).apply {
            setText(preferences.getString("address", null) ?: preferences.getString("adresse", DEFAULT_ADDRESS))
            hint = texts.addressHint
            setTextColor(TEXT)
            setHintTextColor(DIM)
            backgroundTintList = ColorStateList.valueOf(DIM)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            isSingleLine = true
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
                override fun afterTextChanged(s: Editable?) {
                    preferences.edit().putString("address", s.toString().trim()).apply()
                }
            })
        }
        addView(address)
    }

    private fun client() = DaemonClient(address.text.toString())

    private fun show(situation: Situation) {
        status = situation.display.status
        statusLine.text = texts.status(situation.display.status)
        hintLine.text = texts.hint(situation.display.hint)
        hintLine.visibility = if (hintLine.text.isEmpty()) View.GONE else View.VISIBLE
        dot.background = round(
            when (situation.display.status) {
                Status.PLAYING -> GREEN
                Status.UNREACHABLE -> RED
                Status.OFF -> DIM
            },
            dp(6).toFloat(),
        )
        if (messageSettled(expected, status)) {
            messageLine.text = ""
            expected = null
        }
        radio = situation.radio
        if (SystemClock.elapsedRealtime() - lastTouched > 4000) showVolume(situation.radio)
        showStations(situation.radio)
    }

    private fun showVolume(r: RadioState?) {
        slider.isEnabled = r != null
        mute.isEnabled = r != null
        slider.alpha = if (r == null) 0.4f else 1f
        mute.alpha = if (r == null) 0.4f else 1f
        mute.text = if (r?.muted == true) texts.soundOn else texts.mute
        mute.background = round(if (r?.muted == true) ACCENT else FIELD, dp(22).toFloat())
        mute.setTextColor(if (r?.muted == true) BACKGROUND_TOP else TEXT)
        if (r == null) {
            volumeValue.text = "–"
            return
        }
        slider.progress = r.volume
        volumeValue.text = if (r.muted) texts.muted else "${r.volume} %"
    }

    /** Stations one below the other to tap; the audible one highlighted. Without a running radio the last list. */
    private fun showStations(r: RadioState?) {
        val names = if (r != null) {
            preferences.edit().putString("stations", JSONArray(r.stations).toString()).apply()
            r.stations
        } else {
            // "sender" and "adresse" are the keys of older versions of this app
            val remembered = JSONArray(preferences.getString("stations", null) ?: preferences.getString("sender", "[]"))
            List(remembered.length()) { remembered.getString(it) }
        }
        stationList.removeAllViews()
        if (names.isEmpty()) stationList.addView(text(texts.listAppears, 14f, DIM))
        names.forEachIndexed { index, name ->
            val playing = r?.active == index
            val row = text(if (playing) "▶   $name" else name, 17f, if (playing) BACKGROUND_TOP else TEXT, bold = playing).apply {
                background = round(if (playing) ACCENT else FIELD, dp(14).toFloat())
                setPadding(dp(16), dp(14), dp(16), dp(14))
                alpha = if (r == null) 0.45f else 1f
                isClickable = r != null
                if (r != null) setOnClickListener { adjust { it.tuneTo(index) } }
            }
            stationList.addView(row, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = dp(8)
            })
        }
        for (b in listOf(addButton, deleteButton)) {
            b.isEnabled = r != null
            b.alpha = if (r == null) 0.4f else 1f
        }
    }

    private fun askForNewStation() {
        val current = radio ?: return
        if (current.stations.size >= MAX_STATIONS) {
            messageLine.text = texts.full
            return
        }
        val url = field(texts.streamUrl, InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        val name = field(texts.nameOptional, InputType.TYPE_CLASS_TEXT)
        val form = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
            addView(url)
            addView(name)
        }
        dialog().setTitle(texts.addTitle).setView(form)
            .setPositiveButton(texts.ok) { _, _ ->
                val typedName = name.text.toString()
                change(Message.Checking, { Message.Added(it.stations.lastOrNull() ?: typedName) }) {
                    it.addStation(url.text.toString(), typedName)
                }
            }
            .setNegativeButton(texts.cancel, null)
            .show()
    }

    private fun askWhichToDelete() {
        val current = radio ?: return
        if (current.stations.size <= 1) {
            messageLine.text = texts.lastOne
            return
        }
        dialog().setTitle(texts.deleteTitle).setItems(current.stations.toTypedArray()) { _, index ->
            val name = current.stations[index]
            dialog().setMessage(texts.confirmDelete(name))
                .setPositiveButton(texts.delete) { _, _ -> change(null, { Message.Removed(name) }) { it.deleteStation(index) } }
                .setNegativeButton(texts.cancel, null)
                .show()
        }.setNegativeButton(texts.cancel, null).show()
    }

    /** Adds or removes a station; shows the robot's reason if it refuses. */
    private fun change(waiting: Message?, success: (RadioState) -> Message, action: (DaemonClient) -> Change) {
        val client = client()
        messageLine.text = waiting?.let { texts.message(it) } ?: ""
        expected = null
        network.execute {
            val message = try {
                val result = action(client)
                val state = result.state
                if (state != null) {
                    main.post {
                        radio = state
                        showStations(state)
                    }
                    success(state)
                } else {
                    Message.Refused(result.refusal ?: "")
                }
            } catch (error: Exception) {
                Message.NoAnswer
            }
            main.post { messageLine.text = texts.message(message) }
        }
    }

    private fun act(waiting: Message, action: (DaemonClient) -> Outcome) {
        val client = client()
        buttons.forEach { it.isEnabled = false }
        messageLine.text = texts.message(waiting)
        expected = null
        network.execute {
            val outcome = try {
                action(client)
            } catch (error: Exception) {
                Outcome(Message.Unreachable(error.javaClass.simpleName))
            }
            main.post {
                buttons.forEach { it.isEnabled = true }
                if (messageSettled(outcome.expected, status)) {
                    messageLine.text = ""
                } else {
                    expected = outcome.expected
                    messageLine.text = texts.message(outcome.message)
                }
            }
        }
    }

    /** A wish to the radio; for station and volume an antenna then moves and the display follows it. */
    private fun adjust(wait: Boolean = true, action: (DaemonClient) -> RadioState?) {
        val client = client()
        if (wait) lastTouched = SystemClock.elapsedRealtime()
        network.execute {
            val new = try {
                action(client)
            } catch (error: Exception) {
                null
            }
            main.post {
                if (new == null) {
                    messageLine.text = texts.message(Message.NoAnswer)
                } else if (!wait) {
                    radio = new
                    showVolume(new)
                }
            }
        }
    }

    private fun dialog() = AlertDialog.Builder(this, android.R.style.Theme_Material_Dialog_Alert)

    private fun field(hintText: String, type: Int) = EditText(this).apply {
        hint = hintText
        inputType = type
        isSingleLine = true
    }

    private fun card() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = round(CARD, dp(22).toFloat())
        setPadding(dp(18), dp(16), dp(18), dp(18))
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(16)
        }
    }

    private fun button(label: String, colour: Int, textColour: Int) = Button(this).apply {
        text = label
        isAllCaps = false
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        setTypeface(typeface, Typeface.BOLD)
        setTextColor(textColour)
        background = round(colour, dp(26).toFloat())
        stateListAnimator = null
    }

    private fun round(colour: Int, radius: Float) = GradientDrawable().apply {
        setColor(colour)
        cornerRadius = radius
    }

    private fun text(content: String, size: Float, colour: Int, bold: Boolean = false) = TextView(this).apply {
        text = content
        setTextColor(colour)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, size)
        if (bold) setTypeface(typeface, Typeface.BOLD)
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    override fun onResume() {
        super.onResume()
        visible = true
        main.removeCallbacks(poll)
        main.post(poll)
    }

    override fun onPause() {
        super.onPause()
        visible = false
        main.removeCallbacks(poll)
    }

    override fun onDestroy() {
        super.onDestroy()
        network.shutdownNow()
    }
}
