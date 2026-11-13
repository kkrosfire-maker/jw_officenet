package com.jw.weeklytodo

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.temporal.TemporalAdjusters
import java.util.UUID

data class Todo(
    val id: String = UUID.randomUUID().toString(),
    val date: LocalDate,
    val text: String,
    val done: Boolean = false,
)

fun weekStartOf(date: LocalDate): LocalDate =
    date.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))

val DAY_NAMES = listOf("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")

/** 앱 내부 저장소(SharedPreferences)에 JSON 하나로 보관한다. 리스트 순서가 곧 표시 순서. */
object TodoStore {
    private const val PREFS = "weekly_todo"
    private const val KEY = "items"

    fun load(context: Context): List<Todo> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
            ?: return emptyList()
        val arr = JSONArray(raw)
        return (0 until arr.length()).map {
            val o = arr.getJSONObject(it)
            Todo(
                id = o.getString("id"),
                date = LocalDate.parse(o.getString("date")),
                text = o.getString("text"),
                done = o.optBoolean("done", false),
            )
        }
    }

    fun save(context: Context, todos: List<Todo>) {
        val arr = JSONArray()
        todos.forEach {
            arr.put(
                JSONObject()
                    .put("id", it.id)
                    .put("date", it.date.toString())
                    .put("text", it.text)
                    .put("done", it.done)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, arr.toString()).apply()
    }
}
