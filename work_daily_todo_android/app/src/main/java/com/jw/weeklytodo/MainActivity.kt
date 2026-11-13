package com.jw.weeklytodo

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateListOf
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** 화면이 들고 있는 할 일 목록. 바뀔 때마다 저장하고 위젯을 갱신한다. */
class TodoState(private val context: Context) {
    val items = mutableStateListOf<Todo>().apply { addAll(TodoStore.load(context)) }

    private fun persist() {
        TodoStore.save(context, items.toList())
        CoroutineScope(Dispatchers.Default).launch { TodoWidget.refresh(context) }
    }

    fun add(date: java.time.LocalDate, text: String) {
        items.add(Todo(date = date, text = text))
        persist()
    }

    fun toggle(id: String) = update(id) { it.copy(done = !it.done) }

    fun edit(id: String, text: String) = update(id) { it.copy(text = text) }

    fun delete(id: String) {
        items.removeAll { it.id == id }
        persist()
    }

    /** 같은 날짜 안에서 위(-1)/아래(+1) 이웃과 자리를 바꾼다. */
    fun move(id: String, dir: Int) {
        val i = items.indexOfFirst { it.id == id }
        if (i < 0) return
        val day = items[i].date
        var j = i + dir
        while (j in items.indices && items[j].date != day) j += dir
        if (j !in items.indices) return
        val tmp = items[i]
        items[i] = items[j]
        items[j] = tmp
        persist()
    }

    /** 저장 버튼: 지금 상태를 확정 저장하고 위젯을 바로 갱신한다. */
    fun save() = persist()

    private fun update(id: String, f: (Todo) -> Todo) {
        val i = items.indexOfFirst { it.id == id }
        if (i < 0) return
        items[i] = f(items[i])
        persist()
    }
}

/** 위젯에서 요일을 눌러 들어왔을 때 그 날짜로 이동하라는 요청. n은 같은 날짜를 다시 눌러도 반응하게 하는 번호. */
data class Jump(val date: java.time.LocalDate, val n: Int)

class MainActivity : ComponentActivity() {
    private var jump by mutableStateOf<Jump?>(null)
    private var jumpCount = 0

    private fun readJump(intent: android.content.Intent?) {
        val d = intent?.data?.lastPathSegment ?: return
        runCatching { java.time.LocalDate.parse(d) }.getOrNull()?.let { jump = Jump(it, ++jumpCount) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 상태바·시계·배터리 영역은 시스템에 맡긴다(투명 + 어두운 아이콘, 앱 화면은 그 아래부터)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
        if (savedInstanceState == null) readJump(intent)
        val state = TodoState(applicationContext)
        setContent { WeekScreen(state, jump) }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        readJump(intent)
    }
}
