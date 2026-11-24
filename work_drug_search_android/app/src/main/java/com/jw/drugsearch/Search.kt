package com.jw.drugsearch

enum class Field(val label: String) {
    Ingredient("성분"),
    Code("보험코드"),
    Company("제약사명"),
    Product("제품명"),
    Ref("대조의약품"),
    Price("약가"),
    Rate("요율"),
    Note("비고"),
}

enum class SortMode(val label: String, val desc: String) {
    Ingredient("성분순", "성분 → 약가↑ → 요율↓"),
    Price("약가순", "약가 낮은 순"),
    Rate("요율순", "요율 높은 순"),
}

fun Row.valueOf(f: Field): String? = when (f) {
    Field.Ingredient -> ingredient
    Field.Code -> code
    Field.Company -> company
    Field.Product -> product
    Field.Ref -> ref
    Field.Price -> price?.let { formatPrice(it) } ?: priceText
    Field.Rate -> rate?.let { formatRate(it) } ?: rateText
    Field.Note -> note
}

fun formatPrice(v: Double): String =
    if (v == Math.floor(v)) "%,d".format(v.toLong()) else "%,.2f".format(v)

fun formatRate(v: Double): String {
    // 0.5299999999 같은 부동소수 오차를 없애려고 소수 1자리로 반올림
    val pct = Math.round(v * 1000.0) / 10.0
    return if (pct == Math.floor(pct)) "${pct.toLong()}%" else "$pct%"
}

// ---------------- 검색 ----------------

/** 한글 음절의 초성. 초성 자음(ㄱ~ㅎ) 자체거나 한글이 아니면 null. */
private val CHOSUNG = charArrayOf(
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ',
    'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ',
)

private fun chosungOf(c: Char): Char? {
    if (c in '가'..'힣') return CHOSUNG[(c - '가') / 588]
    return null
}

private fun isJamoInitial(c: Char): Boolean = c in CHOSUNG

/** 검색어 글자 q 가 본문 글자 t 와 맞는지: 초성 자음이면 t 의 초성과, 아니면 글자 그대로 비교. */
private fun charMatches(q: Char, t: Char): Boolean =
    if (isJamoInitial(q)) chosungOf(t) == q else q == t

/** term 이 text 안에 있는지(exact 면 전체 일치). 초성 자음이 섞인 검색어도 처리. */
private fun termMatches(text: String, term: String, hasJamo: Boolean, exact: Boolean): Boolean {
    if (!hasJamo) {
        return if (exact) text.trim().equals(term, ignoreCase = true)
        else text.contains(term, ignoreCase = true)
    }
    val t = text.trim()
    val n = t.length
    val m = term.length
    if (exact) {
        if (n != m) return false
        for (i in 0 until m) if (!charMatches(term[i], t[i])) return false
        return true
    }
    if (m > n) return false
    for (start in 0..(n - m)) {
        var ok = true
        for (i in 0 until m) {
            if (!charMatches(term[i], t[start + i])) { ok = false; break }
        }
        if (ok) return true
    }
    return false
}

/**
 * 쉼표(,)로 나눈 단어 중 하나라도 선택한 검색 대상에 맞으면 포함(OR). 초성 검색 지원.
 * 검색어가 비어 있으면 전체.
 */
fun searchRows(rows: List<Row>, keyword: String, targets: Set<Field>, exact: Boolean): List<Row> {
    val terms = keyword.split(",").map { it.trim() }.filter { it.isNotEmpty() }
    if (terms.isEmpty()) return rows
    val jamo = terms.map { t -> t.any { isJamoInitial(it) } }
    return rows.filter { row ->
        targets.any { f ->
            val v = row.valueOf(f) ?: return@any false
            terms.indices.any { i -> termMatches(v, terms[i], jamo[i], exact) }
        }
    }
}

// ---------------- 정렬 ----------------

private fun <T : Comparable<T>> compareLists(a: List<T>, b: List<T>): Int {
    val n = minOf(a.size, b.size)
    for (i in 0 until n) {
        val c = a[i].compareTo(b[i])
        if (c != 0) return c
    }
    return a.size.compareTo(b.size)
}

private fun priceKey(r: Row): Double = r.price ?: Double.POSITIVE_INFINITY
/** 요율은 높은 순이므로 부호를 뒤집어 비교한다. 값이 없으면 맨 뒤. */
private fun rateKey(r: Row): Double = r.rate?.let { -it } ?: Double.POSITIVE_INFINITY

/** 기본 정렬: 성분(단일제→복합제, 성분명, 함량) → 약가↑ → 요율↓ → 제품명 */
val DefaultComparator = Comparator<Row> { a, b ->
    var c = a.isCombo.compareTo(b.isCombo)
    if (c != 0) return@Comparator c
    c = compareLists(a.names, b.names)
    if (c != 0) return@Comparator c
    c = compareLists(a.strengths, b.strengths)
    if (c != 0) return@Comparator c
    c = priceKey(a).compareTo(priceKey(b))
    if (c != 0) return@Comparator c
    c = rateKey(a).compareTo(rateKey(b))
    if (c != 0) return@Comparator c
    (a.product ?: "").compareTo(b.product ?: "")
}

fun sortRows(rows: List<Row>, mode: SortMode): List<Row> = when (mode) {
    SortMode.Ingredient -> rows.sortedWith(DefaultComparator)
    // 약가순/요율순: 값이 없는 행은 맨 아래, 같은 값끼리는 기본 정렬 순서
    SortMode.Price -> rows.sortedWith(compareBy<Row> { priceKey(it) }.then(DefaultComparator))
    SortMode.Rate -> rows.sortedWith(compareBy<Row> { rateKey(it) }.then(DefaultComparator))
}
