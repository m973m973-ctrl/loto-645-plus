package ru.loto645plus.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View

class FreqChartView(context: Context) : View(context) {

    private var freq: IntArray = IntArray(46)

    private val barPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#5B8CFF") }
    private val hotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#FF7A59") }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#9AA3B8")
        textSize = 22f
        textAlign = Paint.Align.CENTER
    }

    fun setData(freqLast100: IntArray) {
        freq = freqLast100
        invalidate()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        setMeasuredDimension(w, 480)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val maxV = freq.maxOrNull() ?: return
        if (maxV <= 0) return
        val topHot = (1..45).sortedByDescending { freq[it] }.take(10).toSet()
        val n = 45
        val left = 8f
        val right = width - 8f
        val bottom = height - 40f
        val topPad = 30f
        val bw = (right - left) / n
        for (i in 1..n) {
            val h = (bottom - topPad) * freq[i] / maxV
            val x0 = left + (i - 1) * bw + 2
            val x1 = left + i * bw - 2
            canvas.drawRect(x0, bottom - h, x1, bottom, if (i in topHot) hotPaint else barPaint)
            if (i % 3 == 1 || n <= 45 && bw > 26f) {
                canvas.drawText(i.toString(), (x0 + x1) / 2, bottom + 30f, textPaint)
            }
        }
    }
}
