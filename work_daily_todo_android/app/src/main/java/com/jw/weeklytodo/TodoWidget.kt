package com.jw.weeklytodo

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.currentState
import androidx.glance.LocalContext
import androidx.glance.LocalSize
import androidx.glance.action.Action
import androidx.glance.action.actionStartActivity
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetManager
import androidx.glance.appwidget.SizeMode
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.state.updateAppWidgetState
import androidx.glance.appwidget.cornerRadius
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.layout.Box
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.fillMaxHeight
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.height
import androidx.glance.layout.padding
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextDecoration
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import java.time.LocalDate

/** 이번 주(월~일) 할 일을 보여 주는 확인 전용 위젯. 요일을 누르면 앱이 열리며 그 요일로 스크롤된다. */
class TodoWidget : GlanceAppWidget() {
    override val sizeMode: SizeMode = SizeMode.Exact

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent {
            // 갱신 신호(stamp)가 바뀔 때마다 저장소를 다시 읽는다. (미리 읽어 두면 앱에서 바꿔도 위젯이 안 바뀐다)
            val stamp = currentState(STAMP) ?: 0L
            val ctx = LocalContext.current
            val todos = remember(stamp) { TodoStore.load(ctx) }
            WidgetContent(todos)
        }
    }

    companion object {
        private val STAMP = longPreferencesKey("stamp")

        /** 배치된 모든 위젯을 지금 데이터로 즉시 다시 그린다. */
        suspend fun refresh(context: Context) {
            val ids = GlanceAppWidgetManager(context).getGlanceIds(TodoWidget::class.java)
            for (id in ids) {
                updateAppWidgetState(context, id) { it[STAMP] = System.nanoTime() }
                TodoWidget().update(context, id)
            }
        }
    }
}

class TodoWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = TodoWidget()
}

private sealed interface Line {
    val date: LocalDate

    data class Header(override val date: LocalDate, val label: String, val isToday: Boolean) : Line
    data class Item(override val date: LocalDate, val text: String, val done: Boolean) : Line
    data class Empty(override val date: LocalDate) : Line
}

private fun linesFor(dayIndex: Int, start: LocalDate, today: LocalDate, todos: List<Todo>): List<Line> =
    buildList {
        val d = start.plusDays(dayIndex.toLong())
        add(Line.Header(d, "${DAY_NAMES[dayIndex].take(1)} ${d.monthValue}/${d.dayOfMonth}", d == today))
        val day = todos.filter { it.date == d }
        if (day.isEmpty()) add(Line.Empty(d)) else day.forEach { add(Line.Item(d, it.text, it.done)) }
    }

/** 앱을 열면서 해당 날짜를 알려 주는 동작. 날짜마다 data가 달라 PendingIntent가 섞이지 않는다. */
@Composable
private fun openDay(date: LocalDate): Action {
    val context = LocalContext.current
    val intent = Intent(context, MainActivity::class.java).apply {
        data = Uri.parse("weeklytodo://day/$date")
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    return actionStartActivity(intent)
}

@Composable
private fun WidgetContent(todos: List<Todo>) {
    val today = LocalDate.now()
    val start = weekStartOf(today)
    val white = ColorProvider(Color.White)
    // 카드 한 칸에 들어가는 줄 수(제목 포함). 넘치면 "+N개 더"로 줄인다.
    val cardH = (LocalSize.current.height.value - 16f - 24f) / 2f - 6f
    fun capFor(h: Float) = ((h - 20f) / 17f).toInt().coerceAtLeast(2)

    Column(
        GlanceModifier
            .fillMaxSize()
            .background(Green)
            .cornerRadius(18.dp)
            .padding(8.dp)
            .clickable(actionStartActivity<MainActivity>())
    ) {
        Text(
            "이번 주  ${start.monthValue}/${start.dayOfMonth} ~ ${start.plusDays(6).monthValue}/${start.plusDays(6).dayOfMonth}",
            style = TextStyle(color = white, fontSize = 14.sp, fontWeight = FontWeight.Bold),
            modifier = GlanceModifier.padding(start = 4.dp, bottom = 4.dp)
        )
        for (row in 0 until 2) {
            Row(GlanceModifier.fillMaxWidth().defaultWeight()) {
                for (col in 0 until 3) {
                    val cell = row * 3 + col // 0..5, 마지막(5)은 토+일을 절반씩
                    Box(GlanceModifier.defaultWeight().fillMaxHeight().padding(3.dp)) {
                        Box(
                            GlanceModifier
                                .fillMaxSize()
                                .background(Color.White)
                                .cornerRadius(12.dp)
                        ) {
                            if (cell < 5) {
                                DayList(linesFor(cell, start, today, todos), capFor(cardH))
                            } else {
                                Column(GlanceModifier.fillMaxSize()) {
                                    Box(GlanceModifier.fillMaxWidth().defaultWeight()) {
                                        DayList(linesFor(5, start, today, todos), capFor(cardH / 2f))
                                    }
                                    Box(
                                        GlanceModifier
                                            .fillMaxWidth()
                                            .height(1.dp)
                                            .background(Border)
                                    ) {}
                                    Box(GlanceModifier.fillMaxWidth().defaultWeight()) {
                                        DayList(linesFor(6, start, today, todos), capFor(cardH / 2f))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DayList(lines: List<Line>, capacity: Int) {
    val green = ColorProvider(Green)
    val open = openDay(lines.first().date)
    val items = lines.drop(1) // lines[0]은 요일 제목
    val room = capacity - 1 // 제목을 뺀 나머지 줄
    val shown: List<Line>
    val more: Int
    if (items.size > room) {
        shown = items.take((room - 1).coerceAtLeast(0))
        more = items.size - shown.size
    } else {
        shown = items
        more = 0
    }
    val header = lines.first() as Line.Header

    // 카드 전체(빈 곳 포함)가 눌리도록 바깥 Box에 클릭을 건다
    Box(GlanceModifier.fillMaxSize().clickable(open)) {
        Column(GlanceModifier.fillMaxSize().padding(6.dp)) {
            Row(
                GlanceModifier
                    .fillMaxWidth()
                    .padding(vertical = 2.dp, horizontal = 2.dp)
                    .background(if (header.isToday) Hover else Color.White)
            ) {
                Text(
                    header.label + if (header.isToday) " · 오늘" else "",
                    style = TextStyle(color = green, fontSize = 12.sp, fontWeight = FontWeight.Bold),
                    maxLines = 1
                )
            }
            shown.forEach { line ->
                when (line) {
                    is Line.Item -> Text(
                        (if (line.done) "☑ " else "☐ ") + line.text,
                        style = TextStyle(
                            color = ColorProvider(if (line.done) GreenTint else Ink),
                            fontSize = 11.sp,
                            textDecoration = if (line.done) TextDecoration.LineThrough else null
                        ),
                        maxLines = 1,
                        modifier = GlanceModifier.padding(start = 2.dp, top = 1.dp)
                    )
                    is Line.Empty -> Text(
                        "—",
                        style = TextStyle(color = ColorProvider(Border), fontSize = 11.sp),
                        modifier = GlanceModifier.padding(start = 2.dp)
                    )
                    is Line.Header -> {}
                }
            }
            if (more > 0) {
                Text(
                    "+${more}개 더",
                    style = TextStyle(color = green, fontSize = 11.sp, fontWeight = FontWeight.Bold),
                    maxLines = 1,
                    modifier = GlanceModifier.padding(start = 2.dp, top = 1.dp)
                )
            }
        }
    }
}
