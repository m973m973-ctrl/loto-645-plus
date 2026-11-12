package ru.loto645plus.app

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import java.io.File
import kotlin.concurrent.thread

class MainActivity : Activity() {

    private val bg = Color.parseColor("#12141C")
    private val card = Color.parseColor("#1E2230")
    private val accent = Color.parseColor("#5B8CFF")
    private val hot = Color.parseColor("#FF7A59")
    private val gold = Color.parseColor("#E8B23F")
    private val green = Color.parseColor("#3FAE6A")
    private val textPrimary = Color.parseColor("#F2F4FA")
    private val textSecondary = Color.parseColor("#9AA3B8")

    private lateinit var root: LinearLayout
    private lateinit var status: TextView
    private lateinit var progress: ProgressBar
    private lateinit var chart: FreqChartView

    private var archPlus: List<Draw>? = null
    private var logData: List<PredEntry> = emptyList()
    private var logBox: LinearLayout? = null
    private var logFilter2plus = true
    private var myLastDraw: List<Int>? = null
    private var myListBox: LinearLayout? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = bg
        window.navigationBarColor = bg

        val scroll = ScrollView(this).apply { setBackgroundColor(bg) }
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 48)
        }
        scroll.addView(root)
        setContentView(scroll)

        root.addView(title("Лото 6 из 45 Плюс — анализ"))
        status = label("Загрузка архива Плюс…")
        root.addView(status)

        progress = ProgressBar(this).apply { visibility = View.GONE }
        root.addView(progress)

        thread {
            try {
                archPlus = LottoLogic.loadAssetDraws(assets.open("archive_full.json"))
                runOnUiThread { refresh() }
            } catch (e: Exception) {
                runOnUiThread { status.text = "Ошибка чтения архива Плюс: ${e.message}" }
            }
        }
    }

    private fun refresh() {
        progress.visibility = View.VISIBLE
        status.text = "Проверяю новые тиражи Плюс на сайте Столото…"
        thread {
            try {
                // Докачиваем только тиражи Плюс; обычная 6 из 45 — другая игра.
                val newPlus = LottoLogic.fetchNew("6x45plus", archPlus!!.maxOf { it.n })
                val plus = archPlus!! + newPlus
                // Анализ и бэктест используют один и тот же архив Плюс.
                val result = LottoLogic.analyze(plus.takeLast(300), plus)
                // Журнал: прогнозы прошлых тиражей против реально выпавших чисел
                val log = try {
                    LottoLogic.updateLog(plus, File(filesDir, "predictions_log.json"))
                } catch (e: Exception) { emptyList() }
                logData = log
                runOnUiThread {
                    progress.visibility = View.GONE
                    render(result, newPlus.size)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    progress.visibility = View.GONE
                    status.text = "Не удалось загрузить тиражи: ${e.message}\nПроверьте интернет и обновите."
                    addRefreshButton()
                }
            }
        }
    }

    private fun render(r: AnalysisResult, newPlus: Int) {
        root.removeAllViews()
        root.addView(title("Лото 6 из 45 Плюс — анализ"))

        val last = r.lastDraw
        myLastDraw = last.main
        root.addView(cardView("Последний тираж №${last.n} (${last.date.take(10)})",
            ballsRow(last.main, last.plus)))

        addMyCard()

        val news = if (newPlus > 0) " • докачано новых: +$newPlus" else " • архив актуален"
        root.addView(info("Архив «6 из 45 Плюс»: ${archPlus!!.size + newPlus} тир.$news\n" +
                "Тиражи обычной «6 из 45» в прогнозы и проверку не входят."))

        root.addView(comboCard("🎯 Основная комбинация", "3 горячих + 2 давно не выпадавших + 1 частое",
            r.comboMain, r.backtestMain))
        root.addView(comboCard("🔄 Альтернативная", "3 просроченных + 3 горячих",
            r.comboAlt, r.backtestAlt))
        root.addView(comboCard("🕵️ Антитолпа", "Самые редко выбираемые игроками числа — при выигрыше делить джекпот придётся с меньшим числом людей",
            r.comboCrowd, r.backtestCrowd))

        root.addView(info("Горячие (100 тиражей): " + r.hot.joinToString(" ") + "\n" +
                "Давно не выпадали: " + r.overdue.joinToString(" ")))

        if (logData.isNotEmpty()) addLogCard()

        addBetCard()
        addGamesCard()
        addRapidoCard()
        add4x20Card()
        addBingoCard("archive_ruslotto.json", "Русское лото")
        addBingoCard("archive_gzhl.json", "Жилищная лотерея")

        root.addView(sectionLabel("Частоты чисел за последние 100 тиражей"))
        chart = FreqChartView(this)
        chart.setData(r.freqLast100)
        root.addView(chart)

        root.addView(info("Правила именно Плюс: 6 чисел из 45 + 1 число из 4. " +
                "Шанс угадать основную шестёрку — 1 : 8 145 060; суперприз за 6+1 — " +
                "1 : 32 580 240; 6+0 — отдельный приз. Все комбинации равновероятны, " +
                "статистика не повышает шанс выигрыша. «Антитолпа» помогает только " +
                "уменьшить вероятный делёж приза."))

        val version = packageManager.getPackageInfo(packageName, 0).versionName
        root.addView(info("Лото 6/45+ Анализ, версия $version\nРазработчик: Сергей Коп\nПриложение не является азартной игрой, не принимает ставки и не связано с оператором лотереи. Используются только открытые опубликованные результаты тиражей."))

        addRefreshButton()

        // Обновляем виджет рабочего стола
        LotoWidgetProvider.updateAll(this)
    }

    // ---------- Сравнение лотерей ----------

    private fun addGamesCard() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel("Сравнение лотерей"))
        box.addView(label("Рейтинг по шансу выиграть не меньше указанной суммы — мелкие призы ниже порога не считаются"))

        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        row.addView(label("мин. выигрыш, ₽:"))
        val minInput = android.widget.EditText(this).apply {
            setText("100")
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setTextColor(textPrimary)
            setBackgroundColor(bg)
            setPadding(16, 4, 16, 4)
            setEms(5)
        }
        row.addView(minInput)
        box.addView(row)

        val out = TextView(this).apply {
            setTextColor(textSecondary)
            textSize = 13f
            setPadding(0, 12, 0, 0)
        }
        val btn = Button(this).apply {
            text = "Показать рейтинг"
            setTextColor(Color.WHITE)
            setBackgroundColor(accent)
            setOnClickListener {
                val mp = minInput.text.toString().toDoubleOrNull()
                if (mp == null || mp <= 0) {
                    out.text = "Введите сумму числом, например 100"
                } else {
                    out.text = LottoLogic.gamesRating(mp).joinToString("\n")
                }
            }
        }
        box.addView(btn)
        box.addView(out)

        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        root.addView(box, lp)
    }

    // ---------- Прогнозы других лотерей ----------

    private fun newCard(): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
    }

    private fun attachCard(box: LinearLayout) {
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        root.addView(box, lp)
    }

    private fun addRapidoCard() {
        val p = try {
            LottoLogic.predictRapido(assets.open("archive_rapido.json"))
        } catch (e: Exception) { return }
        val box = newCard()
        box.addView(sectionLabel("Рапидо — прогнозы"))
        box.addView(label("Поле 1: 8 чисел из 20 · поле 2: 1 из 4 · тиражи каждые 15 минут"))
        box.addView(label("🎯 Основная (4 горячих + 4 давних) + поле 2: ${p.f2}"))
        box.addView(ballsRow(p.main))
        box.addView(label("🔄 Запасная (5 давних + 3 горячих)"))
        box.addView(ballsRow(p.alt, null, gold))
        box.addView(label("🕵️ Антитолпа"))
        box.addView(ballsRow(p.crowd, null, green))
        box.addView(label("Горячие: ${p.hot.joinToString(" ")}\nДавно не выпадали: ${p.cold.joinToString(" ")}"))
        box.addView(label("Честный бэктест: ${p.bt}"))
        attachCard(box)
    }

    private fun add4x20Card() {
        val p = try {
            LottoLogic.predict4x20(assets.open("archive_4x20.json"))
        } catch (e: Exception) { return }
        val box = newCard()
        box.addView(sectionLabel("4 из 20 — прогнозы"))
        box.addView(label("4 числа в каждом из двух полей · суперприз за 4+4"))
        box.addView(label("🎯 Основная (поле 1 | поле 2)"))
        box.addView(ballsRow(p.main1))
        box.addView(ballsRow(p.main2))
        box.addView(label("🔄 Запасная"))
        box.addView(ballsRow(p.alt1, null, gold))
        box.addView(ballsRow(p.alt2, null, gold))
        box.addView(label("🕵️ Антитолпа"))
        box.addView(ballsRow(p.crowd1, null, green))
        box.addView(ballsRow(p.crowd2, null, green))
        box.addView(label("Горячие: ${p.hot.joinToString(" ")} · давно не выпадали: ${p.cold.joinToString(" ")}"))
        box.addView(label("Честный бэктест: ${p.bt}"))
        attachCard(box)
    }

    private fun addBingoCard(asset: String, title: String) {
        val (hot, cold) = try {
            LottoLogic.bingoStats(assets.open(asset))
        } catch (e: Exception) { return }
        val box = newCard()
        box.addView(sectionLabel("$title — статистика бочонков"))
        box.addView(label("Тиражи по воскресеньям · числа в билете напечатаны заранее"))
        box.addView(label("Горячие бочонки (30 тиражей):"))
        box.addView(ballsRow(hot.take(5)))
        box.addView(ballsRow(hot.drop(5)))
        box.addView(label("Редко выпадавшие:"))
        box.addView(ballsRow(cold.take(5), null, gold))
        box.addView(ballsRow(cold.drop(5), null, gold))
        box.addView(label("Как выбрать билет: числа равномерно по всем десяткам, без «красивых» узоров — так приз реже придётся делить. Частота прошлых тиражей на будущее не влияет."))
        attachCard(box)
    }

    // ---------- Мои комбинации ----------

    private val myFile get() = File(filesDir, "my_combos.json")

    private fun addMyCard() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel("Мои комбинации"))
        box.addView(label("Приложение проверит их по каждому новому тиражу и подсветит совпадения"))

        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val input = android.widget.EditText(this).apply {
            hint = "6 чисел через пробел"
            setHintTextColor(textSecondary)
            setTextColor(textPrimary)
            setBackgroundColor(bg)
            setPadding(16, 4, 16, 4)
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
        }
        row.addView(input, LinearLayout.LayoutParams(0,
            LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val add = Button(this).apply {
            text = "Добавить"
            setTextColor(Color.WHITE)
            setBackgroundColor(accent)
            setOnClickListener {
                val nums = Regex("\\d+").findAll(input.text.toString())
                    .map { it.value.toInt() }.toList()
                val c = nums.distinct().sorted()
                if (c.size != 6 || c.any { it !in 1..45 }) {
                    status.text = "Нужно ровно 6 разных чисел от 1 до 45"
                    return@setOnClickListener
                }
                val combos = LottoLogic.loadMy(myFile)
                if (c !in combos) {
                    combos.add(c)
                    LottoLogic.saveMy(myFile, combos)
                }
                input.text.clear()
                fillMyList()
            }
        }
        row.addView(add)
        val gen = Button(this).apply {
            text = "🎲"
            setTextColor(green)
            setBackgroundColor(Color.TRANSPARENT)
            setOnClickListener {
                val combos = LottoLogic.loadMy(myFile)
                val c = LottoLogic.genCrowd()
                if (c !in combos) {
                    combos.add(c)
                    LottoLogic.saveMy(myFile, combos)
                }
                fillMyList()
            }
        }
        row.addView(gen)
        box.addView(row)

        val listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(listBox)
        myListBox = listBox

        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        root.addView(box, lp)
        fillMyList()
    }

    private fun fillMyList() {
        val box = myListBox ?: return
        box.removeAllViews()
        val combos = LottoLogic.loadMy(myFile)
        if (combos.isEmpty()) {
            box.addView(label("Пока пусто — добавьте свои числа"))
            return
        }
        val last = myLastDraw
        for (c in combos) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val hits = if (last != null) c.filter { it in last }.toSet() else emptySet()
            // числа строкой с подсветкой совпавших
            val ssb = SpannableStringBuilder()
            c.forEachIndexed { i, x ->
                val s = ssb.length
                ssb.append(x.toString().padStart(2))
                val hit = x in hits
                ssb.setSpan(ForegroundColorSpan(if (hit) green else textPrimary),
                    s, ssb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                if (hit) ssb.setSpan(StyleSpan(Typeface.BOLD), s, ssb.length,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                if (i < 5) ssb.append("  ")
            }
            if (last != null) {
                val k = hits.size
                val s = ssb.length
                ssb.append("   совпало: $k" + if (k >= 3) " 🎉" else "")
                ssb.setSpan(ForegroundColorSpan(if (k >= 3) green else textSecondary),
                    s, ssb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if (logData.isNotEmpty()) {
                val n3 = logData.count { e -> c.count { it in e.draw } >= 3 }
                val s = ssb.length
                ssb.append("   3+ за 100 тир.: $n3")
                ssb.setSpan(ForegroundColorSpan(textSecondary), s, ssb.length,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            row.addView(TextView(this).apply {
                text = ssb
                textSize = 16f
                setPadding(0, 10, 0, 10)
            }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(Button(this).apply {
                text = "✕"
                setTextColor(hot)
                setBackgroundColor(Color.TRANSPARENT)
                setOnClickListener {
                    LottoLogic.saveMy(myFile, combos.filter { it != c })
                    fillMyList()
                }
            })
            box.addView(row)
        }
    }

    // ---------- Калькулятор развёрнутой ставки ----------

    private fun addBetCard() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel("Развёрнутая ставка"))

        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        row.addView(label("чисел:"))
        val nInput = android.widget.EditText(this).apply {
            setText("10")
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setTextColor(textPrimary)
            setBackgroundColor(bg)
            setPadding(16, 4, 16, 4)
            setEms(3)
        }
        row.addView(nInput)
        row.addView(label("   цена комбинации, ₽:"))
        val priceInput = android.widget.EditText(this).apply {
            setText("100")
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setTextColor(textPrimary)
            setBackgroundColor(bg)
            setPadding(16, 4, 16, 4)
            setEms(4)
        }
        row.addView(priceInput)
        row.addView(label("   человек:"))
        val pplInput = android.widget.EditText(this).apply {
            setText("1")
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setTextColor(textPrimary)
            setBackgroundColor(bg)
            setPadding(16, 4, 16, 4)
            setEms(3)
        }
        row.addView(pplInput)
        box.addView(row)

        val out = TextView(this).apply {
            setTextColor(textSecondary)
            textSize = 14f
            setPadding(0, 12, 0, 0)
        }
        val calc = Button(this).apply {
            text = "Посчитать"
            setTextColor(Color.WHITE)
            setBackgroundColor(accent)
            setOnClickListener {
                val n = nInput.text.toString().toIntOrNull()?.coerceIn(7, 19)
                val price = priceInput.text.toString().toDoubleOrNull()
                val ppl = pplInput.text.toString().toIntOrNull()?.coerceAtLeast(1) ?: 1
                if (n == null || price == null) {
                    out.text = "Введите число от 7 до 19 и цену числом"
                    return@setOnClickListener
                }
                out.text = LottoLogic.betCalc(n, price, ppl)
            }
        }
        box.addView(calc)
        box.addView(out)

        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        root.addView(box, lp)
    }

    // ---------- Журнал прогнозов ----------

    private fun addLogCard() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel("Проверка прогнозов (последние ${logData.size} тиражей)"))

        // Сводка
        fun hits(pred: List<Int>?, draw: List<Int>) = pred?.count { it in draw } ?: 0
        fun summary(pick: (PredEntry) -> List<Int>?): String {
            val hs = logData.map { hits(pick(it), it.draw) }
            return "2+: ${hs.count { it >= 2 }} • 3+: ${hs.count { it >= 3 }} • 4+: ${hs.count { it >= 4 }}"
        }
        val sum = TextView(this).apply {
            text = "Тиражей, где прогноз дал совпадения:\n" +
                    "Прогноз: " + summary { it.main } + "\n" +
                    "Запасной: " + summary { it.alt } + "\n" +
                    "Антитолпа: " + summary { it.crowd }
            setTextColor(textSecondary)
            textSize = 14f
            setPadding(0, 4, 0, 12)
        }
        box.addView(sum)

        val cb = CheckBox(this).apply {
            text = "Только тиражи с 2+ совпадениями"
            isChecked = logFilter2plus
            setTextColor(textPrimary)
            setOnCheckedChangeListener { _, checked ->
                logFilter2plus = checked
                fillLogRows()
            }
        }
        box.addView(cb)

        val rows = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(rows)
        logBox = rows

        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        root.addView(box, lp)
        fillLogRows()
    }

    private fun fillLogRows() {
        val rows = logBox ?: return
        rows.removeAllViews()
        val shown = logData.asReversed().filter { e ->
            if (!logFilter2plus) true
            else {
                val h1 = e.main?.count { it in e.draw } ?: 0
                val h2 = e.alt?.count { it in e.draw } ?: 0
                val h3 = e.crowd?.count { it in e.draw } ?: 0
                maxOf(h1, h2, h3) >= 2
            }
        }
        if (shown.isEmpty()) {
            rows.addView(label("Тиражей с 2+ совпадениями нет — снимите галочку, чтобы увидеть все."))
            return
        }
        for (e in shown) {
            val line = SpannableStringBuilder()
            appendNums(line, "№${e.n}: ", e.draw, e.draw, textPrimary) // выпавшие — белые
            line.append("\n")
            appendNums(line, "П: ", e.main, e.draw, accent)
            line.append("   ")
            appendNums(line, "З: ", e.alt, e.draw, gold)
            line.append("   ")
            appendNums(line, "А: ", e.crowd, e.draw, green)
            val tv = TextView(this).apply {
                text = line
                textSize = 14f
                setPadding(0, 10, 0, 10)
            }
            rows.addView(tv)
        }
    }

    /** Добавляет "prefix n n n" в ssb; числа из [pred], совпавшие с [draw] — жирные цветные. */
    private fun appendNums(ssb: SpannableStringBuilder, prefix: String,
                           pred: List<Int>?, draw: List<Int>, hitColor: Int) {
        val ps = ssb.length
        ssb.append(prefix)
        ssb.setSpan(ForegroundColorSpan(textSecondary), ps, ssb.length,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        if (pred == null) {
            ssb.append("—")
            return
        }
        pred.forEachIndexed { i, x ->
            val s = ssb.length
            ssb.append(x.toString())
            val hit = x in draw
            ssb.setSpan(ForegroundColorSpan(if (hit) hitColor else textSecondary),
                s, ssb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (hit) ssb.setSpan(StyleSpan(Typeface.BOLD), s, ssb.length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (i < pred.size - 1) ssb.append(" ")
        }
    }

    private fun addRefreshButton() {        val btn = Button(this).apply {
            text = "Обновить данные"
            setTextColor(Color.WHITE)
            setBackgroundColor(accent)
            setOnClickListener {
                root.removeAllViews()
                root.addView(title("Лото 6 из 45 Плюс — анализ"))
                root.addView(status)
                root.addView(progress)
                refresh()
            }
        }
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.topMargin = 32
        root.addView(btn, lp)
    }

    private fun title(text: String) = TextView(this).apply {
        this.text = text
        setTextColor(textPrimary)
        textSize = 22f
        setTypeface(typeface, Typeface.BOLD)
        setPadding(0, 0, 0, 16)
    }

    private fun label(text: String) = TextView(this).apply {
        this.text = text
        setTextColor(textSecondary)
        textSize = 15f
        setPadding(0, 8, 0, 8)
    }

    private fun info(text: String) = TextView(this).apply {
        this.text = text
        setTextColor(textSecondary)
        textSize = 14f
        setPadding(8, 16, 8, 16)
    }

    private fun sectionLabel(text: String) = TextView(this).apply {
        this.text = text
        setTextColor(textPrimary)
        textSize = 16f
        setTypeface(typeface, Typeface.BOLD)
        setPadding(0, 24, 0, 8)
    }

    private fun ballsRow(main: List<Int>, plus: Int? = null, color: Int = accent): LinearLayout {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        for (n in main) row.addView(ball(n, color))
        if (plus != null) row.addView(ball(plus, hot))
        return row
    }

    private fun ball(n: Int, color: Int): TextView {
        val d = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(color)
        }
        val tv = TextView(this).apply {
            text = n.toString()
            setTextColor(Color.WHITE)
            textSize = 15f
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            background = d
        }
        val lp = LinearLayout.LayoutParams(76, 76)
        lp.setMargins(6, 6, 6, 6)
        tv.layoutParams = lp
        return tv
    }

    private fun cardView(caption: String, content: View): LinearLayout {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel(caption))
        box.addView(content)
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        box.layoutParams = lp
        return box
    }

    private fun comboCard(titleText: String, desc: String, combo: List<Int>, backtest: String): LinearLayout {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 24f
            }
            setPadding(24, 20, 24, 20)
        }
        box.addView(sectionLabel(titleText))
        box.addView(label(desc))
        box.addView(ballsRow(combo))
        val bt = TextView(this).apply {
            text = "Бэктест:\n$backtest"
            setTextColor(textSecondary)
            textSize = 13f
            setPadding(0, 12, 0, 0)
        }
        box.addView(bt)
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.setMargins(0, 12, 0, 12)
        box.layoutParams = lp
        return box
    }
}
