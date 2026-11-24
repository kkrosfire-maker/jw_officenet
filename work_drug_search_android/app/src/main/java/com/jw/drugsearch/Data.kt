package com.jw.drugsearch

import android.content.Context
import org.json.JSONObject

/** 요율표 한 행. 약가/요율은 숫자면 num, 숫자가 아니면('-', '미정' 등) 원문 text. */
class Row(
    val id: Int,               // 원본 엑셀에서의 순번(체크·비고 펼침 상태를 기억하는 열쇠)
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

    /** 화면·복사·공유에 쓰는 제품명: 뒤에 붙은 성분명 괄호 `(아토르바스타틴)` 은 뺀다. 검색은 원본(product)을 쓴다. */
    val displayProduct: String by lazy { cleanProductName(product) }

    /** 화면용 성분: 괄호 밖 원래 성분명 / 괄호 안 `(20mg as atorvastatin)` 같은 보충 설명(성분명 아래 회색 작은 글씨). */
    val ingredientMain: String
    val ingredientNote: String?

    init {
        val ing = ingredient
        var main = ing ?: ""
        var note: String? = null
        if (ing != null) {
            val groups = PAREN_RE.findAll(ing).map { it.value }.toList()
            if (groups.isNotEmpty()) {
                val stripped = PAREN_RE.replace(ing, " ").replace(Regex("\\s{2,}"), " ").trim()
                // 괄호를 빼고 나면 알파벳/한글이 없는 이상한 경우는 원문 그대로 둔다
                if (stripped.any { it.isLetter() }) {
                    main = stripped
                    note = groups.joinToString(" ")
                }
            }
        }
        ingredientMain = main
        ingredientNote = note

        val comps = splitComponents(ingredient)
        isCombo = comps.size > 1
        val n = ArrayList<String>(comps.size)
        val s = ArrayList<Double>(comps.size)
        for (c in comps) {
            val noParen = PAREN_RE.replace(c, " ")
            val base = if (noParen.isBlank()) c.replace("(", " ").replace(")", " ") else noParen
            val m = NUM_RE.find(base)
            val salt = m?.value?.toDouble() ?: 0.0
            // 괄호 안 "(20mg as atorvastatin)" 은 염을 뺀 실제 함량 → 이 값으로 규격을 묶는다.
            // 염 무게보다 큰 값은 오타(예: 10.85mg 인데 12mg)라서 염 무게의 정수부로 맞춘다.
            val declared = AS_RE.find(c)?.groupValues?.get(1)?.toDouble()
            s.add(
                when {
                    declared == null -> salt
                    declared <= salt + 1e-9 -> declared
                    else -> Math.floor(salt)
                }
            )
            val head = base.substring(0, m?.range?.first ?: base.length).trim().lowercase()
            n.add(head.split(Regex("\\s+")).firstOrNull() ?: "")
        }
        names = n
        strengths = s
    }

    companion object {
        private val PAREN_RE = Regex("\\([^)]*\\)")
        private val NUM_RE = Regex("\\d+(?:\\.\\d+)?")
        private val AS_RE = Regex("\\((\\d+(?:\\.\\d+)?)\\s*[A-Za-zμµ]+\\s+as\\s+[^)]*\\)", RegexOption.IGNORE_CASE)

        // "mg/g", "mg/ml", "50μg/ml" 처럼 슬래시 뒤가 단위면 복합제 구분이 아니라 농도 표기다.
        private val UNIT_START = Regex("^\\s*\\d*(?:\\.\\d+)?\\s*(?:mg|g|ml|mL|ML|l|L|회|μg|µg|ug|%|kg|cc|IU|iu)(?![A-Za-z가-힣])")

        /** 괄호 밖의 `/` 로 나누되, 뒤가 단위인 조각은 앞 조각에 붙인다. */
        private fun splitComponents(ingredient: String?): List<String> {
            val s = ingredient ?: return emptyList()
            val pieces = ArrayList<String>()
            var depth = 0
            val cur = StringBuilder()
            for (ch in s) {
                when (ch) {
                    '(' -> depth++
                    ')' -> if (depth > 0) depth--
                }
                if (ch == '/' && depth == 0) {
                    pieces.add(cur.toString()); cur.setLength(0)
                } else cur.append(ch)
            }
            pieces.add(cur.toString())
            val merged = ArrayList<String>()
            for (p in pieces) {
                if (merged.isNotEmpty() && UNIT_START.containsMatchIn(p)) {
                    merged[merged.size - 1] = merged.last() + "/" + p
                } else merged.add(p)
            }
            return merged.map { it.trim() }.filter { it.isNotEmpty() }
        }

        // 제품명 뒤 괄호 중 남길 것: 숫자로 시작((2:1), (1회용)…)하거나 용도 표시인 것
        private val KEEP_TAGS = setOf("비만", "피임", "일회용", "다회용", "SR", "ECA")
        private val NAME_PAREN_RE = Regex("\\s*\\(([^()]*)\\)")

        fun cleanProductName(name: String?): String {
            if (name.isNullOrBlank()) return name ?: ""
            val cleaned = NAME_PAREN_RE.replace(name) { m ->
                val inner = m.groupValues[1].trim()
                if (inner.isEmpty() || inner[0].isDigit() || inner in KEEP_TAGS) m.value else ""
            }.replace(Regex("\\s{2,}"), " ").trim()
            return cleaned.ifBlank { name.trim() }
        }
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
                id = i,
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
