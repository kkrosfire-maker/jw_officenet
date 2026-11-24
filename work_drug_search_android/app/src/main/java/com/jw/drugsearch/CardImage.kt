package com.jw.drugsearch

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Layout
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.StaticLayout
import android.text.TextPaint
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan

/**
 * 결과 카드를 앱 화면과 비슷한 모양의 이미지로 그린다(화면 캡처가 아니라 카드만 그려서 만든다).
 * 한 장에 카드를 너무 많이 넣으면 이미지가 커지므로 PAGE_SIZE 건씩 나눠서 여러 장을 돌려준다.
 */
object CardImage {
    const val PAGE_SIZE = 40

    private const val W = 1080
    private const val M = 36f          // 바깥 여백
    private const val U = 3f           // dp → px (3배 해상도)

    private val Green900 = Color.parseColor("#0A4A33")
    private val Green700 = Color.parseColor("#11704A")
    private val Green100 = Color.parseColor("#E3F1EA")
    private val Bg = Color.parseColor("#F2F5F3")
    private val Muted = Color.parseColor("#6B7A72")
    private val Burgundy = Color.parseColor("#8E1B3A")
    private val Red = Color.parseColor("#B3261E")
    private val AmberBg = Color.parseColor("#FFF1D6")
    private val AmberText = Color.parseColor("#8A5A00")
    private val NoteBg = Color.parseColor("#FFF8E8")
    private val Gray = Color.parseColor("#7B8780")
    private val Ink = Color.parseColor("#3C4D44")

    private fun paint(sizeDp: Float, color: Int, bold: Boolean = false) = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = sizeDp * U
        this.color = color
        typeface = if (bold) Typeface.create(Typeface.DEFAULT, Typeface.BOLD) else Typeface.DEFAULT
    }

    private fun layout(text: CharSequence, p: TextPaint, width: Float): StaticLayout =
        StaticLayout.Builder.obtain(text, 0, text.length, p, width.toInt().coerceAtLeast(10))
            .setAlignment(Layout.Alignment.ALIGN_NORMAL)
            .setLineSpacing(0f, 1.12f)
            .build()

    /** rows 를 PAGE_SIZE 건씩 나눠 그린 이미지 목록. notesOpen 에 든 카드만 비고를 함께 그린다. */
    fun render(
        rows: List<Row>, visible: Set<Field>, notesOpen: Set<Int>,
        version: String, keyword: String, matchCount: Int,
    ): List<Bitmap> {
        val pages = rows.chunked(PAGE_SIZE)
        return pages.mapIndexed { i, chunk ->
            renderPage(chunk, visible, notesOpen, version, keyword, matchCount, i + 1, pages.size, rows.size)
        }
    }

    private fun renderPage(
        rows: List<Row>, visible: Set<Field>, notesOpen: Set<Int>,
        version: String, keyword: String, matchCount: Int,
        page: Int, pageCount: Int, exportCount: Int,
    ): Bitmap {
        val headerH = 210f
        val gap = 24f
        // 1) 높이 계산(그리지 않고 측정만)
        var total = headerH + 24f
        val heights = rows.map { r ->
            val h = drawCard(null, r, visible, r.id in notesOpen, 0f)
            total += h + gap
            h
        }
        total += M

        val bmp = Bitmap.createBitmap(W, total.toInt(), Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        c.drawColor(Bg)

        // 2) 머리글
        val hp = Paint().apply { shader = LinearGradient(0f, 0f, W.toFloat(), headerH, Green900, Green700, Shader.TileMode.CLAMP) }
        c.drawRect(0f, 0f, W.toFloat(), headerH, hp)
        val titleP = paint(24f, Color.WHITE, true)
        c.drawText("동일약품 검색기", M + 12f, 96f, titleP)
        val verP = paint(12f, Color.parseColor("#AEBDB5"))
        if (version.isNotEmpty()) c.drawText("(요율표 $version)", M + 12f + titleP.measureText("동일약품 검색기") + 18f, 96f, verP)
        val subP = paint(13f, Color.parseColor("#DDE9E2"))
        val kw = keyword.ifBlank { "(전체)" }
        val countText = if (exportCount == matchCount) "${matchCount}건" else "${exportCount}건 선택 (검색 ${matchCount}건 중)"
        val pageText = if (pageCount > 1) "  ·  $page/$pageCount" else ""
        c.drawText("검색어: $kw  ·  $countText$pageText", M + 12f, 156f, subP)

        // 3) 카드
        var y = headerH + 24f
        rows.forEachIndexed { i, r ->
            drawCard(c, r, visible, r.id in notesOpen, y)
            y += heights[i] + gap
        }
        return bmp
    }

    /** canvas 가 null 이면 높이만 계산한다. 카드 높이를 돌려준다. */
    private fun drawCard(canvas: Canvas?, row: Row, visible: Set<Field>, noteOpen: Boolean, top: Float): Float {
        val left = M
        val cardW = W - 2 * M
        val padL = 38f
        val padR = 30f
        val padV = 30f
        val innerW = cardW - padL - padR

        val titleField = row.titleField(visible)
        val title = titleField?.let { row.shown(it) } ?: ""

        // 오른쪽 배지(약가·요율)
        val badgeP = paint(12f, Green900, true)
        val badges = ArrayList<Triple<String, Int, Int>>()
        if (Field.Price in visible && row.valueOf(Field.Price) != null) badges.add(Triple("약가 ${row.valueOf(Field.Price)}", Green100, Green900))
        if (Field.Rate in visible && row.valueOf(Field.Rate) != null) badges.add(Triple("요율 ${row.valueOf(Field.Rate)}", AmberBg, AmberText))
        val badgeH = 64f
        val badgePad = 24f
        val badgeColW = badges.maxOfOrNull { badgeP.measureText(it.first) + 2 * badgePad } ?: 0f
        val textW = innerW - if (badges.isEmpty()) 0f else badgeColW + 24f

        // 왼쪽 묶음: 제목 → 성분(버건디) → 성분 보충(회색 작게) → 대조의약품
        var leftH = 0f
        val titleL = layout(title, paint(15.5f, if (row.red) Red else Green900, true), textW)
        leftH += titleL.height
        var ingL: StaticLayout? = null
        var ingNoteL: StaticLayout? = null
        if (Field.Ingredient in visible && titleField != Field.Ingredient && !row.ingredient.isNullOrBlank()) {
            ingL = layout("성분  " + row.ingredientMain, paint(12.5f, Burgundy), textW)
            leftH += 9f + ingL.height
            row.ingredientNote?.let {
                ingNoteL = layout(it, paint(10f, Gray), textW - 66f)
                leftH += 3f + ingNoteL!!.height
            }
        }
        var refL: StaticLayout? = null
        if (Field.Ref in visible && titleField != Field.Ref && !row.ref.isNullOrBlank()) {
            refL = layout("대조의약품  " + row.ref, paint(12.5f, Ink), textW)
            leftH += 9f + refL.height
        }
        val badgesH = if (badges.isEmpty()) 0f else badges.size * badgeH + (badges.size - 1) * 12f
        var y = top + padV
        val blockH = maxOf(leftH, badgesH)

        // 보험코드·제약사명
        val metaSb = SpannableStringBuilder()
        fun addMeta(label: String, value: String, color: Int, bold: Boolean) {
            if (metaSb.isNotEmpty()) metaSb.append("      ")
            val s = metaSb.length
            metaSb.append(label)
            metaSb.setSpan(ForegroundColorSpan(Muted), s, metaSb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            metaSb.setSpan(StyleSpan(Typeface.BOLD), s, metaSb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            metaSb.append("  ")
            val v = metaSb.length
            metaSb.append(value)
            metaSb.setSpan(ForegroundColorSpan(color), v, metaSb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (bold) metaSb.setSpan(StyleSpan(Typeface.BOLD), v, metaSb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        if (Field.Code in visible && titleField != Field.Code && !row.code.isNullOrBlank()) addMeta("보험코드", row.code!!, Ink, false)
        if (Field.Company in visible && titleField != Field.Company && !row.company.isNullOrBlank()) addMeta("제약사명", row.company!!, Green700, true)
        val metaL = if (metaSb.isNotEmpty()) layout(metaSb, paint(12f, Ink), innerW) else null

        // 비고(펼친 카드만)
        val noteL = if (noteOpen && Field.Note in visible && !row.note.isNullOrBlank())
            layout("비고: ${row.note}", paint(11.5f, AmberText), innerW - 28f) else null

        var h = padV + blockH
        if (metaL != null) h += 18f + metaL.height
        if (noteL != null) h += 18f + noteL.height + 24f
        h += padV

        if (canvas != null) {
            // 카드 바탕·왼쪽 막대
            val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
            canvas.drawRoundRect(RectF(left, top, left + cardW, top + h), 48f, 48f, bg)
            val bar = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Green700 }
            canvas.drawRoundRect(RectF(left, top + 30f, left + 12f, top + h - 30f), 6f, 6f, bar)

            val x = left + padL
            var yy = y
            canvas.save(); canvas.translate(x, yy); titleL.draw(canvas); canvas.restore()
            yy += titleL.height
            ingL?.let { yy += 9f; canvas.save(); canvas.translate(x, yy); it.draw(canvas); canvas.restore(); yy += it.height }
            ingNoteL?.let { yy += 3f; canvas.save(); canvas.translate(x + 66f, yy); it.draw(canvas); canvas.restore(); yy += it.height }
            refL?.let { yy += 9f; canvas.save(); canvas.translate(x, yy); it.draw(canvas); canvas.restore(); yy += it.height }

            // 배지
            var by = y
            badges.forEach { (text, bgC, fgC) ->
                val bw = badgeP.measureText(text) + 2 * badgePad
                val bx = left + cardW - padR - bw
                val bp = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = bgC }
                canvas.drawRoundRect(RectF(bx, by, bx + bw, by + badgeH), 24f, 24f, bp)
                val tp = paint(12f, fgC, true)
                canvas.drawText(text, bx + badgePad, by + badgeH / 2 + tp.textSize * 0.35f, tp)
                by += badgeH + 12f
            }

            var my = y + blockH
            metaL?.let { my += 18f; canvas.save(); canvas.translate(x, my); it.draw(canvas); canvas.restore(); my += it.height }
            noteL?.let {
                my += 18f
                val nb = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = NoteBg }
                canvas.drawRoundRect(RectF(x, my, x + innerW, my + it.height + 24f), 21f, 21f, nb)
                canvas.save(); canvas.translate(x + 14f, my + 12f); it.draw(canvas); canvas.restore()
            }
        }
        return h
    }
}
