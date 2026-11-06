package ru.loto645plus.app

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/** Виджет рабочего стола: последний тираж и совпадения моих комбинаций. */
class LotoWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        for (id in ids) {
            val pending = goAsync()
            thread {
                try {
                    updateOne(context, mgr, id)
                } finally {
                    pending.finish()
                }
            }
        }
    }

    companion object {
        fun updateAll(context: Context) {
            val mgr = AppWidgetManager.getInstance(context)
            val ids = mgr.getAppWidgetIds(
                android.content.ComponentName(context, LotoWidgetProvider::class.java))
            if (ids.isNotEmpty()) {
                val intent = Intent(context, LotoWidgetProvider::class.java).apply {
                    action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                    putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
                }
                context.sendBroadcast(intent)
            }
        }

        fun updateOne(context: Context, mgr: AppWidgetManager, id: Int) {
            val stateFile = File(context.filesDir, "widget_state.json")

            // 1. Пытаемся взять свежий тираж из сети
            var last: Draw? = try {
                LottoLogic.fetchDraws(pages = 1, game = "6x45plus").maxByOrNull { it.n }
            } catch (e: Exception) {
                null
            }
            if (last != null) {
                stateFile.writeText(JSONObject().apply {
                    put("n", last.n); put("date", last.date)
                    put("main", org.json.JSONArray(last.main)); put("plus", last.plus)
                }.toString())
            } else if (stateFile.exists()) {
                // 2. Нет сети — берём сохранённый
                last = try {
                    val o = JSONObject(stateFile.readText())
                    val m = o.getJSONArray("main")
                    Draw(o.getInt("n"), o.getString("date"),
                        (0 until m.length()).map { m.getInt(it) }, o.optInt("plus", 0))
                } catch (e: Exception) { null }
            }

            val views = RemoteViews(context.packageName, R.layout.widget_loto)
            if (last == null) {
                views.setTextViewText(R.id.widget_last, "Нет данных — откройте приложение")
                views.setTextViewText(R.id.widget_my, "")
            } else {
                views.setTextViewText(
                    R.id.widget_last,
                    "№${last.n}: " + last.main.joinToString(" ") +
                            if (last.plus > 0) " +${last.plus}" else "")
                // Совпадения моих комбинаций
                val combos = LottoLogic.loadMy(File(context.filesDir, "my_combos.json"))
                if (combos.isEmpty()) {
                    views.setTextViewText(R.id.widget_my, "Мои комбинации не заданы")
                } else {
                    val lines = combos.map { c ->
                        val k = c.count { it in last.main }
                        "• ${c.joinToString(" ")} — $k" + if (k >= 3) " 🎉" else ""
                    }
                    views.setTextViewText(R.id.widget_my, lines.joinToString("\n"))
                }
            }
            val now = SimpleDateFormat("dd.MM HH:mm", Locale.getDefault()).format(Date())
            views.setTextViewText(R.id.widget_updated, "обновлено $now")

            // Клик по виджету открывает приложение
            val pi = PendingIntent.getActivity(
                context, 0,
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            views.setOnClickPendingIntent(R.id.widget_root, pi)

            mgr.updateAppWidget(id, views)
        }
    }
}
