package ru.loto645plus.app

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.InputStream
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

data class Draw(
    val n: Int,
    val date: String,
    val main: List<Int>,   // 6 чисел, отсортированы
    val plus: Int
)

data class AnalysisResult(
    val drawsCount: Int,
    val lastDraw: Draw,
    val hot: List<Int>,        // горячие (частые за последние 100)
    val overdue: List<Int>,    // давно не выпадали
    val comboMain: List<Int>,
    val comboAlt: List<Int>,
    val comboCrowd: List<Int>,
    val freqLast100: IntArray, // частоты 1..45 за последние 100
    val backtestMain: String,
    val backtestAlt: String,
    val backtestCrowd: String
)

data class PredEntry(
    val n: Int,
    val date: String,
    val draw: List<Int>,
    val plus: Int,
    val main: List<Int>?,   // основной прогноз, посчитанный ДО этого тиража
    val alt: List<Int>?,    // запасной
    val crowd: List<Int>?   // антитолпа
)

object LottoLogic {

    private const val API_BASE =
        "https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive?count=50&game="
    private const val PARTNER = "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg"

    fun fetchDraws(pages: Int = 6, game: String = "6x45plus"): List<Draw> {
        val out = ArrayList<Draw>()
        for (p in 1..pages) {
            var attempt = 0
            while (true) {
                try {
                    out.addAll(fetchPage(game, p))
                    break
                } catch (e: Exception) {
                    attempt++
                    if (attempt >= 3) throw e
                    Thread.sleep(1500)
                }
            }
        }
        return out.sortedBy { it.n }
    }

    /**
     * Докачивает все тиражи игры [game] с номерами больше [lastN] (новее встроенного архива).
     * API отдаёт тиражи от новых к старым; останавливаемся, когда дошли до уже известных.
     */
    fun fetchNew(game: String, lastN: Int, maxPages: Int = 40): List<Draw> {
        val out = ArrayList<Draw>()
        for (p in 1..maxPages) {
            var page: List<Draw>? = null
            var attempt = 0
            while (page == null) {
                try {
                    page = fetchPage(game, p)
                } catch (e: Exception) {
                    attempt++
                    if (attempt >= 3) throw e
                    Thread.sleep(1500)
                }
            }
            if (page.isEmpty()) break
            val fresh = page.filter { it.n > lastN }
            out.addAll(fresh)
            // На странице есть тиражи, которые у нас уже есть, — дальше только старые
            if (fresh.size < page.size) break
        }
        return out.sortedBy { it.n }
    }

    private fun fetchPage(game: String, page: Int): List<Draw> {
        val conn = (URL("$API_BASE$game&page=$page").openConnection() as HttpURLConnection).apply {
            connectTimeout = 15000
            readTimeout = 15000
            setRequestProperty(
                "User-Agent",
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
            )
            setRequestProperty("Gosloto-Partner", PARTNER)
            setRequestProperty("Accept", "application/json")
        }
        val code = conn.responseCode
        if (code != 200) throw Exception("HTTP $code")
        val text = conn.inputStream.readText()
        conn.disconnect()
        val root = JSONObject(text)
        val arr = root.getJSONArray("draws")
        val list = ArrayList<Draw>()
        for (i in 0 until arr.length()) {
            val d = arr.getJSONObject(i)
            val comb = d.getJSONObject("combination").getJSONArray("structured")
            val nums = IntArray(comb.length()) { comb.getInt(it) }
            val main = nums.take(6).sorted()
            val plus = if (nums.size > 6) nums[6] else 0
            list.add(Draw(d.getInt("number"), d.getString("date"), main, plus))
        }
        return list
    }

    fun loadAssetDraws(input: InputStream): List<Draw> {
        val arr = JSONArray(input.readText())
        val list = ArrayList<Draw>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val m = o.getJSONArray("main")
            val main = IntArray(m.length()) { m.getInt(it) }.sorted()
            list.add(Draw(o.getInt("n"), o.getString("date"), main, o.optInt("plus", 0)))
        }
        return list
    }

    private fun InputStream.readText(): String {
        val sb = StringBuilder()
        BufferedReader(InputStreamReader(this, Charsets.UTF_8)).forEachLine { sb.append(it) }
        return sb.toString()
    }

    fun analyze(draws: List<Draw>, archPlus: List<Draw>, archOld: List<Draw>): AnalysisResult {
        val last100 = draws.takeLast(100)
        val freq = IntArray(46)
        for (d in last100) for (x in d.main) freq[x]++

        val freqAll = IntArray(46)
        for (d in draws) for (x in d.main) freqAll[x]++

        val hot = (1..45).sortedByDescending { freq[it] }.take(10)
        val overdue = (1..45).sortedBy { freq[it] }.take(10)
        val freqTop = (1..45).sortedByDescending { freqAll[it] }.take(10)

        // Основная: 3 горячих + 2 просроченных + 1 частое за всё время
        val comboMain = ArrayList<Int>()
        comboMain.addAll(hot.take(3))
        for (x in overdue) if (comboMain.size < 5 && x !in comboMain) comboMain.add(x)
        for (x in freqTop) if (comboMain.size < 6 && x !in comboMain) comboMain.add(x)

        // Альтернативная: 3 просроченных + 3 горячих
        val comboAlt = ArrayList<Int>()
        comboAlt.addAll(overdue.take(3))
        for (x in hot) if (comboAlt.size < 6 && x !in comboAlt) comboAlt.add(x)

        // Антитолпа: наименее популярные у игроков (вшитый набор по статистике выплат)
        val comboCrowd = listOf(12, 24, 33, 39, 40, 43)

        val m = comboMain.sorted()
        val a = comboAlt.sorted()
        return AnalysisResult(
            drawsCount = draws.size,
            lastDraw = draws.last(),
            hot = hot,
            overdue = overdue,
            comboMain = m,
            comboAlt = a,
            comboCrowd = comboCrowd,
            freqLast100 = freq,
            backtestMain = backtest(m, archPlus, archOld),
            backtestAlt = backtest(a, archPlus, archOld),
            backtestCrowd = backtest(comboCrowd, archPlus, archOld)
        )
    }

    /** Три прогноза по тем же правилам, что analyze, но по произвольному срезу prior. */
    fun combosFor(prior: List<Draw>): Triple<List<Int>, List<Int>, List<Int>> {
        val last100 = prior.takeLast(100)
        val freq = IntArray(46)
        for (d in last100) for (x in d.main) freq[x]++
        val freqAll = IntArray(46)
        for (d in prior) for (x in d.main) freqAll[x]++
        val hot = (1..45).sortedByDescending { freq[it] }.take(10)
        val overdue = (1..45).sortedBy { freq[it] }.take(10)
        val freqTop = (1..45).sortedByDescending { freqAll[it] }.take(10)
        val main = ArrayList<Int>()
        main.addAll(hot.take(3))
        for (x in overdue) if (main.size < 5 && x !in main) main.add(x)
        for (x in freqTop) if (main.size < 6 && x !in main) main.add(x)
        val alt = ArrayList<Int>()
        alt.addAll(overdue.take(3))
        for (x in hot) if (alt.size < 6 && x !in alt) alt.add(x)
        return Triple(main.sorted(), alt.sorted(), listOf(12, 24, 33, 39, 40, 43))
    }

    /**
     * Журнал: для каждого из последних [keep] тиражей — прогноз, посчитанный ДО него.
     * Дозаписывает только новые тиражи, хранит в [file], возвращает последние [keep].
     */
    fun updateLog(all: List<Draw>, file: File, keep: Int = 100): List<PredEntry> {
        val existing = ArrayList<PredEntry>()
        if (file.exists()) {
            try {
                val arr = JSONArray(file.readText())
                for (i in 0 until arr.length()) {
                    val o = arr.getJSONObject(i)
                    fun nums(key: String): List<Int>? {
                        if (!o.has(key) || o.isNull(key)) return null
                        val a = o.getJSONArray(key)
                        return (0 until a.length()).map { a.getInt(it) }
                    }
                    val dm = o.getJSONArray("draw")
                    existing.add(
                        PredEntry(
                            o.getInt("n"), o.getString("date"),
                            (0 until dm.length()).map { dm.getInt(it) },
                            o.optInt("plus", 0),
                            nums("main"), nums("alt"), nums("crowd")
                        )
                    )
                }
            } catch (e: Exception) {
                existing.clear()
            }
        }
        val have = existing.map { it.n }.toSet()
        val start = maxOf(50, all.size - keep)
        val out = ArrayList(existing)
        for (i in start until all.size) {
            val d = all[i]
            if (d.n in have) continue
            val prior = all.subList(0, i)
            val preds: Triple<List<Int>?, List<Int>?, List<Int>?> =
                if (prior.size >= 100) {
                    val t = combosFor(prior)
                    Triple(t.first, t.second, t.third)
                } else Triple(null, null, null)
            out.add(PredEntry(d.n, d.date, d.main, d.plus, preds.first, preds.second, preds.third))
        }
        val kept = out.sortedBy { it.n }.takeLast(keep)
        // Сохраняем
        val arr = JSONArray()
        for (e in kept) {
            val o = JSONObject()
            o.put("n", e.n); o.put("date", e.date)
            o.put("draw", JSONArray(e.draw)); o.put("plus", e.plus)
            fun putList(key: String, v: List<Int>?) {
                if (v == null) o.put(key, JSONObject.NULL) else o.put(key, JSONArray(v))
            }
            putList("main", e.main); putList("alt", e.alt); putList("crowd", e.crowd)
            arr.put(o)
        }
        file.writeText(arr.toString())
        return kept
    }

    /** Развёрнутая ставка: комбинации, стоимость, шансы. */
    fun betCalc(n: Int, price: Double, ppl: Int = 1): String {
        fun comb(nn: Int, kk: Int): Long {
            var r = 1L
            for (i in 1..kk) r = r * (nn - kk + i) / i
            return r
        }
        val full = comb(45, 6).toDouble()
        val combos = comb(n, 6)
        val total = combos * price
        fun p(j: Int) = comb(n, j).toDouble() * comb(45 - n, 6 - j) / full
        val p6 = p(6)
        val p5 = p(5) + p6
        val p4 = p(4) + p5
        val p3 = p(3) + p4
        val oneIn = String.format("%,d", (full / combos).toLong()).replace(',', ' ')
        val totalStr = if (total == total.toLong().toDouble())
            String.format("%,d", total.toLong()).replace(',', ' ')
        else "%.0f".format(total)
        return "$n чисел = $combos комбинаций · стоимость $totalStr ₽\n" +
                "Шанс суперприза (6 из 6): 1 к $oneIn (${"%.4f".format(p6 * 100)}%)\n" +
                "Поймать 5+ чисел тиража: ${"%.2f".format(p5 * 100)}% · " +
                "4+: ${"%.1f".format(p4 * 100)}% · 3+: ${"%.1f".format(p3 * 100)}%\n" +
                (if (ppl > 1) {
                    val pp = if (total / ppl == (total / ppl).toLong().toDouble())
                        String.format("%,d", (total / ppl).toLong()).replace(',', ' ')
                    else "%.0f".format(total / ppl)
                    "Синдикат из $ppl чел.: по $pp ₽ с человека, выигрыш делится на $ppl\n"
                } else "") +
                "Честно: цена растёт пропорционально шансу — ожидание то же, что у обычных билетов."
    }

    /** Загрузка/сохранение любимых комбинаций пользователя. */
    fun loadMy(file: File): MutableList<List<Int>> {
        if (!file.exists()) return mutableListOf()
        return try {
            val arr = JSONArray(file.readText())
            val out = mutableListOf<List<Int>>()
            for (i in 0 until arr.length()) {
                val a = arr.getJSONArray(i)
                val c = (0 until a.length()).map { a.getInt(it) }.distinct().sorted()
                if (c.size == 6 && c.all { it in 1..45 }) out.add(c)
            }
            out
        } catch (e: Exception) {
            mutableListOf()
        }
    }

    fun saveMy(file: File, combos: List<List<Int>>) {
        val arr = JSONArray()
        for (c in combos) arr.put(JSONArray(c))
        file.writeText(arr.toString())
    }

    /** Случайный «антитолпа»-билет: упор на числа >31 и редко отмечаемые. */
    fun genCrowd(): List<Int> {
        val rnd = java.util.Random()
        val unpopLow = setOf(12, 24)
        while (true) {
            val pool = (1..45).toMutableList()
            val chosen = mutableListOf<Int>()
            repeat(6) {
                val weights = pool.map { if (it > 31 || it in unpopLow) 3.0 else 1.0 }
                var r = rnd.nextDouble() * weights.sum()
                var idx = weights.size - 1
                for (i in weights.indices) {
                    r -= weights[i]
                    if (r <= 0) { idx = i; break }
                }
                chosen.add(pool.removeAt(idx))
            }
            chosen.sort()
            if (chosen.count { it > 31 } < 3) continue
            var triple = false
            for (i in 0..3) if (chosen[i + 1] == chosen[i] + 1 &&
                chosen[i + 2] == chosen[i] + 2) triple = true
            if (triple) continue
            return chosen
        }
    }

    // ---------- Сравнение лотерей ----------

    private fun pmatch(n: Int, k: Int, d: Int, j: Int): Double {
        fun comb(nn: Int, kk: Int): Double {
            var r = 1.0
            for (i in 1..kk) r = r * (nn - kk + i) / i
            return r
        }
        return comb(d, j) * comb(n - d, k - j) / comb(n, k)
    }

    private data class GameInfo(val name: String, val price: Int,
                                val cats: List<Pair<Int, Double>>, val jack: Long)

    /** Рейтинг: шанс выиграть ≥ minPrize ₽ за ставку. Призы примерные. */
    fun gamesRating(minPrize: Double): List<String> {
        val games = mutableListOf<GameInfo>()
        run { // 5 из 36: 5 из 36 + 1 из 4
            fun p(j: Int) = pmatch(36, 5, 5, j)
            games.add(GameInfo("5 из 36", 75, listOf(
                75 to p(2), 750 to p(3), 7500 to p(4), 100000 to p(5) * 3 / 4), 1507968))
        }
        run { // 6 из 45 и Плюс
            fun p(j: Int) = pmatch(45, 6, 6, j)
            games.add(GameInfo("6 из 45", 50, listOf(
                50 to p(2), 400 to p(3), 2000 to p(4), 100000 to p(5)), 8145060))
            games.add(GameInfo("6 из 45 Плюс", 100, listOf(
                100 to p(2), 500 to p(3), 3000 to p(4), 100000 to p(5)), 8145060))
        }
        run { // 7 из 49
            fun p(j: Int) = pmatch(49, 7, 7, j)
            games.add(GameInfo("7 из 49", 40, listOf(
                150 to p(3), 1500 to p(4), 15000 to p(5), 1500000 to p(6)), 85900584))
        }
        run { // 4 из 20 (упрощённо по одному полю)
            fun p(j: Int) = pmatch(20, 4, 4, j)
            games.add(GameInfo("4 из 20", 250, listOf(
                250 to p(2), 1000 to p(3), 3000 to p(4)), 23474025))
        }
        run { // Рапидо: 8 из 20 + 1 из 4
            fun p(j: Int) = pmatch(20, 8, 8, j)
            games.add(GameInfo("Рапидо", 60, listOf(
                60 to p(4) * 3 / 4, 200 to p(5) * 3 / 4, 600 to p(5) / 4,
                1000 to p(6) * 3 / 4, 3000 to p(6) / 4,
                4000 to p(7) * 3 / 4, 15000 to p(7) / 4,
                60000 to p(8) * 3 / 4), 503880))
        }
        run { // Всё или ничего (12 из 24)
            fun p(j: Int) = pmatch(24, 12, 12, j) + pmatch(24, 12, 12, 12 - j)
            games.add(GameInfo("Всё или ничего", 100, listOf(
                100 to p(4), 300 to p(3), 1500 to p(2), 15000 to p(1)), 1352078))
        }
        val rows = games.map { g ->
            Pair(g, g.cats.filter { it.first >= minPrize }.sumOf { it.second } +
                    1.0 / g.jack)
        }.sortedByDescending { it.second }
        val out = mutableListOf("Шанс выиграть ≥ ${"%.0f".format(minPrize)} ₽ за ставку:")
        rows.forEachIndexed { i, row ->
            val g = row.first
            val p = row.second
            val jf = String.format("%,d", g.jack).replace(',', ' ')
            out.add("${i + 1}. ${g.name} (ставка ${g.price} ₽) — 1 к ${"%.1f".format(1 / p)}, суперприз 1 к $jf")
        }
        out.add("Суммы призов примерные, по опубликованным правилам — могут меняться.")
        return out
    }

    // ---------- Прогнозы для других лотерей ----------

    val UNPOP20 = listOf(13, 16, 17, 18, 19, 20, 14, 15)

    fun hotOverdue(seqs: List<List<Int>>, lo: Int, hi: Int,
                   window: Int = 100): Pair<List<Int>, List<Int>> {
        val freq = HashMap<Int, Int>()
        for (s in seqs.takeLast(window)) for (x in s) freq[x] = (freq[x] ?: 0) + 1
        val lastSeen = HashMap<Int, Int>()
        seqs.forEachIndexed { i, s -> for (x in s) lastSeen[x] = i }
        val range = (lo..hi).toList()
        val hot = range.sortedWith(compareBy({ -(freq[it] ?: 0) }, { it }))
        val cold = range.sortedWith(compareBy({ lastSeen[it] ?: -1 }, { it }))
        return Pair(hot, cold)
    }

    fun mix(hot: List<Int>, cold: List<Int>, k: Int,
            hotFirst: Boolean = true, primary: Int? = null): List<Int> {
        val prim = primary ?: (k / 2 + if (hotFirst) k % 2 else 0)
        val out = ArrayList<Int>()
        val a = if (hotFirst) hot else cold
        val b = if (hotFirst) cold else hot
        for (x in a) {
            if (out.size >= prim) break
            out.add(x)
        }
        for (x in b) {
            if (out.size >= k) break
            if (x !in out) out.add(x)
        }
        return out.sorted()
    }

    private fun pge(n: Int, k: Int, d: Int, jmin: Int): Double {
        var s = 0.0
        for (j in jmin..minOf(k, d)) s += pmatch(n, k, d, j)
        return s
    }

    data class RapidoPred(val main: List<Int>, val alt: List<Int>,
                          val crowd: List<Int>, val f2: Int,
                          val hot: List<Int>, val cold: List<Int>, val bt: String)

    fun predictRapido(input: InputStream): RapidoPred {
        val arr = JSONArray(input.readText2())
        val seq = ArrayList<List<Int>>()
        val f2seq = ArrayList<Int>()
        for (i in 0 until arr.length()) {
            val p = arr.getJSONObject(i).getJSONArray("p")
            if (p.length() < 9) continue
            seq.add((0 until 8).map { p.getInt(it) })
            f2seq.add(p.getInt(8))
        }
        val (hot, cold) = hotOverdue(seq, 1, 20)
        val main = mix(hot, cold, 8)
        val alt = mix(hot, cold, 8, hotFirst = false, primary = 5)
        val crowd = UNPOP20.take(8).sorted()
        val f2 = f2seq.takeLast(100).groupingBy { it }.eachCount()
            .maxByOrNull { it.value }?.key ?: 1
        var wins = 0; var total = 0; var hits = 0
        val from = maxOf(100, seq.size - 400)
        for (i in from until seq.size) {
            val (h, c) = hotOverdue(seq.subList(0, i), 1, 20)
            val combo = mix(h, c, 8)
            val a = combo.count { it in seq[i] }
            hits += a; total++
            if (a >= 5) wins++
        }
        val bt = "за $total тиражей: ср. совпадений %.2f (случайно 3.20), призовых %.1f%% (случайно ~%.1f%%)"
            .format(hits.toDouble() / maxOf(1, total),
                wins * 100.0 / maxOf(1, total), pge(20, 8, 8, 5) * 100)
        return RapidoPred(main, alt, crowd, f2, hot.take(8), cold.take(8), bt)
    }

    data class X4Pred(val main1: List<Int>, val main2: List<Int>,
                      val alt1: List<Int>, val alt2: List<Int>,
                      val crowd1: List<Int>, val crowd2: List<Int>,
                      val hot: List<Int>, val cold: List<Int>, val bt: String)

    fun predict4x20(input: InputStream): X4Pred {
        val arr = JSONArray(input.readText2())
        val sa = ArrayList<List<Int>>()
        val sb = ArrayList<List<Int>>()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            sa.add((0 until 4).map { o.getJSONArray("a").getInt(it) })
            sb.add((0 until 4).map { o.getJSONArray("b").getInt(it) })
        }
        val (ha, ca) = hotOverdue(sa, 1, 20)
        val (hb, cb) = hotOverdue(sb, 1, 20)
        val main1 = mix(ha, ca, 4); val main2 = mix(hb, cb, 4)
        val alt1 = mix(ha.drop(1), ca.drop(1), 4)
        val alt2 = mix(hb.drop(1), cb.drop(1), 4)
        val crowd1 = UNPOP20.take(4).sorted()
        val crowd2 = UNPOP20.drop(4).take(4).sorted()
        var wins = 0; var total = 0
        val from = maxOf(100, sa.size - 400)
        for (i in from until sa.size) {
            val (h1, c1) = hotOverdue(sa.subList(0, i), 1, 20)
            val (h2, c2) = hotOverdue(sb.subList(0, i), 1, 20)
            val f1 = mix(h1, c1, 4); val f2 = mix(h2, c2, 4)
            total++
            if (f1.count { it in sa[i] } >= 2 || f2.count { it in sb[i] } >= 2) wins++
        }
        val p1 = pge(20, 4, 4, 2)
        val bt = "за $total тиражей: выигрышных ставок %.1f%% (случайно ~%.1f%%)"
            .format(wins * 100.0 / maxOf(1, total), (1 - (1 - p1) * (1 - p1)) * 100)
        return X4Pred(main1, main2, alt1, alt2, crowd1, crowd2,
            ha.take(6), ca.take(6), bt)
    }

    fun bingoStats(input: InputStream, lastn: Int = 30): Pair<List<Int>, List<Int>> {
        val arr = JSONArray(input.readText2())
        val freq = HashMap<Int, Int>()
        val n = arr.length()
        for (i in maxOf(0, n - lastn) until n) {
            val o = arr.getJSONObject(i)
            val drawn = HashSet<Int>()
            if (o.has("r")) {
                val r = o.getJSONArray("r")
                for (j in 0 until r.length()) {
                    val rr = r.getJSONArray(j)
                    for (t in 0 until rr.length()) drawn.add(rr.getInt(t))
                }
            }
            if (drawn.isEmpty() && o.has("np")) {
                val np = o.getJSONArray("np")
                val skip = (0 until np.length()).map { np.getInt(it) }.toSet()
                drawn.addAll((1..90).filter { it !in skip })
            }
            for (x in drawn) freq[x] = (freq[x] ?: 0) + 1
        }
        val range = (1..90).toList()
        val hot = range.sortedWith(compareBy({ -(freq[it] ?: 0) }, { it })).take(10)
        val cold = range.sortedWith(compareBy({ freq[it] ?: 0 }, { it })).take(10)
        return Pair(hot, cold)
    }

    private fun InputStream.readText2(): String {
        val sb = StringBuilder()
        BufferedReader(InputStreamReader(this, Charsets.UTF_8)).forEachLine { sb.append(it) }
        return sb.toString()
    }

    fun backtest(combo: List<Int>, archPlus: List<Draw>, archOld: List<Draw>): String {
        fun scan(arch: List<Draw>, name: String): String {
            val hits = IntArray(7) // совпадения 0..6
            for (d in arch) {
                val c = combo.count { it in d.main }
                hits[c]++
            }
            val sb = StringBuilder(name).append(": ")
            var any = false
            for (k in 6 downTo 2) if (hits[k] > 0) {
                sb.append("$k совп. — ${hits[k]} раз; ")
                any = true
            }
            if (!any) sb.append("совпадений 2+ не было")
            return sb.toString()
        }
        return scan(archPlus, "Плюс (${archPlus.size} тир.)") + "\n" +
                scan(archOld, "Старая 6/45 (${archOld.size} тир.)")
    }
}
