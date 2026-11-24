package com.jw.drugsearch

import android.content.Context
import org.json.JSONObject

/** 요율표 한 행. 약가/요율은 숫자면 num, 숫자가 아니면('-', '미정' 등) 원문 text. */
class Row(
    val ingredient: String?,   // 성분
    val code: String?,         // 보험코드
    val company: String?,      // 제약사명
    val product: String?,      // 제품명
    val ref: String?,          // 대조의약품
    val price: Double?,        // 약가(숫자)
    val priceText: String?,    // 약가(숫자가 아닌 원문)
    val rate: Double?,         // 요율(0.35 = 35%)
    val rateText: String?,
    val note: String?,         // 비고
    val red: Boolean,          // 엑셀에서 빨간 글씨였던 행(정산불가 등)
) {
    // 기본 정렬용 키: 로드할 때 한 번만 계산해 둔다.
    val isCombo: Boolean
    val names: List<String>
    val strengths: List<Double>

    init {
        val comps = splitComponents(ingredient)
        isCombo = comps.size > 1
        val n = ArrayList<String>(comps.size)
        val s = ArrayList<Double>(comps.size)
        for (c in comps) {
            val m = NUM_RE.find(c)
            s.add(m?.value?.toDouble() ?: 0.0)
            val head = c.substring(0, m?.range?.first ?: c.length).trim().lowercase()
            n.add(head.split(Regex("\\s+")).firstOrNull() ?: "")
        }
        names = n
        strengths = s
    }

    companion object {
        private val PAREN_RE = Regex("\\([^)]*\\)")
        private val NUM_RE = Regex("\\d+(?:\\.\\d+)?")

        private fun splitComponents(ingredient: String?): List<String> =
            PAREN_RE.replace(ingredient ?: "", " ")
                .split("/")
                .map { it.trim() }
                .filter { it.isNotEmpty() }
    }
}

class RateData(val version: String, val rows: List<Row>)

fun loadRates(context: Context): RateData {
    val text = context.assets.open("rates.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
    val root = JSONObject(text)
    val arr = root.getJSONArray("rows")
    val rows = ArrayList<Row>(arr.length())
    for (i in 0 until arr.length()) {
        val o = arr.getJSONObject(i)
        fun str(k: String): String? = if (o.has(k)) o.getString(k) else null
        fun numOrText(k: String): Pair<Double?, String?> {
            if (!o.has(k)) return null to null
            val v = o.get(k)
            return if (v is Number) v.toDouble() to null else null to v.toString()
        }
        val (price, priceText) = numOrText("a")
        val (rate, rateText) = numOrText("t")
        rows.add(
            Row(
                ingredient = str("g"), code = str("k"), company = str("m"),
                product = str("p"), ref = str("r"),
                price = price, priceText = priceText,
                rate = rate, rateText = rateText,
                note = str("n"), red = o.has("x"),
            )
        )
    }
    return RateData(root.optString("version", ""), rows)
}
