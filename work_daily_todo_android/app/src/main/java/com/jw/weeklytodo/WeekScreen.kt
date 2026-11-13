package com.jw.weeklytodo

import android.widget.Toast
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import java.time.LocalDate
import kotlin.math.roundToInt

val Green = Color(0xFF0D4A32)
val GreenTint = Color(0xFF5E8168)
val Border = Color(0xFFC6D3CC)
val Hover = Color(0xFFEAF1ED)
val Ink = Color(0xFF1F2A24)
val Late = Color(0xFFB3261E)

private val Colors = lightColorScheme(
    primary = Green,
    onPrimary = Color.White,
    surface = Color.White,
    background = Color.White,
    onSurface = Ink,
)

@Composable
fun WeekScreen(state: TodoState, jump: Jump? = null) {
    MaterialTheme(colorScheme = Colors) {
        val context = LocalContext.current
        val focusManager = LocalFocusManager.current
        val today = LocalDate.now()
        var weekStart by rememberSaveable { mutableStateOf(weekStartOf(today).toString()) }
        val start = LocalDate.parse(weekStart)

        var openInput by rememberSaveable { mutableStateOf<String?>(null) } // 입력창이 열린 날짜
        var draft by rememberSaveable { mutableStateOf("") } // 입력창에 쓰는 중인 글
        var selectedId by rememberSaveable { mutableStateOf<String?>(null) } // 꾹 눌러 버튼이 보이는 항목
        var editingId by rememberSaveable { mutableStateOf<String?>(null) }
        var editText by rememberSaveable { mutableStateOf("") }

        val scroll = rememberScrollState()
        val dayTops = remember { mutableStateMapOf<Int, Float>() } // 요일별 화면상 위치(px)
        var containerTop by remember { mutableFloatStateOf(0f) }

        fun closeEditors() {
            openInput = null; draft = ""; selectedId = null; editingId = null
        }

        fun goWeek(d: LocalDate) {
            weekStart = d.toString()
            closeEditors()
        }

        // 위젯에서 요일을 눌러 들어오면 그 주로 옮기고 그 요일이 화면 맨 위에 오도록 스크롤
        LaunchedEffect(jump) {
            if (jump == null) return@LaunchedEffect
            goWeek(weekStartOf(jump.date))
            delay(300) // 새 주가 그려진 뒤에 위치를 읽는다
            val idx = jump.date.dayOfWeek.value - 1
            val top = dayTops[idx] ?: return@LaunchedEffect
            scroll.animateScrollTo((scroll.value + top - containerTop).roundToInt().coerceAtLeast(0))
        }

        fun saveAll() {
            // 쓰던 입력/수정 중인 글이 있으면 같이 확정한다
            val editing = editingId
            val input = openInput
            if (editing != null) {
                if (editText.isNotBlank()) state.edit(editing, editText.trim())
                editingId = null
            } else if (input != null && draft.isNotBlank()) {
                state.add(LocalDate.parse(input), draft.trim())
                draft = ""
            }
            state.save()
            selectedId = null
            focusManager.clearFocus()
            Toast.makeText(context, "저장했어요", Toast.LENGTH_SHORT).show()
        }

        Column(
            Modifier
                .fillMaxSize()
                .background(Color.White)
                .statusBarsPadding() // 시계·배터리 영역은 시스템 몫, 앱은 그 아래부터
                .navigationBarsPadding()
                .imePadding()
        ) {
            // 상단 고정 바: 지난 주 / 이번 주 범위 / 다음 주 / 저장
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Green)
                    .padding(horizontal = 4.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextButton(onClick = { goWeek(start.minusWeeks(1)) }) {
                    Text("‹", color = Color.White, fontSize = 26.sp)
                }
                Column(
                    Modifier
                        .weight(1f)
                        .clickable { goWeek(weekStartOf(today)) },
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        "${start.monthValue}/${start.dayOfMonth} ~ " +
                            "${start.plusDays(6).monthValue}/${start.plusDays(6).dayOfMonth}",
                        color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold
                    )
                    Text(
                        if (start == weekStartOf(today)) "이번 주" else "탭하면 이번 주로 이동",
                        color = Color.White.copy(alpha = 0.75f), fontSize = 12.sp
                    )
                }
                TextButton(onClick = { goWeek(start.plusWeeks(1)) }) {
                    Text("›", color = Color.White, fontSize = 26.sp)
                }
                Text(
                    "저장",
                    color = Green,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .padding(start = 2.dp, end = 6.dp)
                        .background(Color.White, RoundedCornerShape(16.dp))
                        .clickable { saveAll() }
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                )
            }

            Column(
                Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .onGloballyPositioned { containerTop = it.positionInRoot().y }
                    .pointerInput(Unit) { detectTapGestures { selectedId = null } }
                    .verticalScroll(scroll)
                    .padding(horizontal = 14.dp, vertical = 8.dp)
            ) {
                for (i in 0 until 7) {
                    val date = start.plusDays(i.toLong())
                    DaySection(
                        modifier = Modifier.onGloballyPositioned { dayTops[i] = it.positionInRoot().y },
                        date = date,
                        name = DAY_NAMES[i],
                        isToday = date == today,
                        todos = state.items.filter { it.date == date },
                        inputOpen = openInput == date.toString(),
                        draft = draft,
                        onDraft = { draft = it },
                        selectedId = selectedId,
                        editingId = editingId,
                        editText = editText,
                        onEditText = { editText = it },
                        onHeaderClick = {
                            openInput = if (openInput == date.toString()) null else date.toString()
                            draft = ""; selectedId = null; editingId = null
                        },
                        onAdd = { state.add(date, it) },
                        onToggle = { state.toggle(it) },
                        onSelect = { selectedId = it },
                        onStartEdit = { id, text -> editingId = id; editText = text; selectedId = null },
                        onEditDone = { id, text ->
                            if (text.isNotBlank()) state.edit(id, text.trim())
                            editingId = null
                        },
                        onDelete = { state.delete(it); selectedId = null },
                        onMove = { id, dir -> state.move(id, dir) },
                    )
                }
                // 마지막 요일도 화면 맨 위까지 스크롤될 수 있도록 여유 공간
                Spacer(Modifier.height((LocalConfiguration.current.screenHeightDp * 1.0f).dp))
            }
        }
    }
}

@Composable
private fun DaySection(
    modifier: Modifier,
    date: LocalDate,
    name: String,
    isToday: Boolean,
    todos: List<Todo>,
    inputOpen: Boolean,
    draft: String,
    onDraft: (String) -> Unit,
    selectedId: String?,
    editingId: String?,
    editText: String,
    onEditText: (String) -> Unit,
    onHeaderClick: () -> Unit,
    onAdd: (String) -> Unit,
    onToggle: (String) -> Unit,
    onSelect: (String?) -> Unit,
    onStartEdit: (String, String) -> Unit,
    onEditDone: (String, String) -> Unit,
    onDelete: (String) -> Unit,
    onMove: (String, Int) -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(if (isToday) Hover else Color.White)
    ) {
        // 요일 제목 (누르면 입력창 열기/닫기)
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onHeaderClick)
                .padding(vertical = 8.dp, horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                Modifier
                    .width(4.dp)
                    .height(20.dp)
                    .background(Green, RoundedCornerShape(2.dp))
            )
            Spacer(Modifier.width(8.dp))
            Text(name, fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Green)
            Spacer(Modifier.width(8.dp))
            Text("${date.monthValue}/${date.dayOfMonth}", fontSize = 13.sp, color = GreenTint)
            if (isToday) {
                Spacer(Modifier.width(8.dp))
                Text(
                    "오늘",
                    fontSize = 11.sp,
                    color = Color.White,
                    modifier = Modifier
                        .background(Green, RoundedCornerShape(8.dp))
                        .padding(horizontal = 8.dp, vertical = 2.dp)
                )
            }
            Spacer(Modifier.weight(1f))
            Text(if (inputOpen) "–" else "+", fontSize = 20.sp, color = GreenTint)
            Spacer(Modifier.width(6.dp))
        }
        HorizontalDivider(color = Border)

        todos.forEachIndexed { index, todo ->
            key(todo.id) {
                TodoRow(
                    todo = todo,
                    canMoveUp = index > 0,
                    canMoveDown = index < todos.lastIndex,
                    selected = selectedId == todo.id,
                    editing = editingId == todo.id,
                    editText = editText,
                    onEditText = onEditText,
                    onToggle = { onToggle(todo.id) },
                    onSelect = { onSelect(todo.id) },
                    onStartEdit = { onStartEdit(todo.id, todo.text) },
                    onEditDone = { onEditDone(todo.id, it) },
                    onDelete = { onDelete(todo.id) },
                    onMove = { onMove(todo.id, it) },
                )
            }
            HorizontalDivider(color = Border.copy(alpha = 0.6f))
        }

        if (inputOpen) {
            NewItemInput(draft, onDraft, onAdd)
        } else if (todos.isEmpty()) {
            Text(
                "눌러서 할 일 추가",
                fontSize = 13.sp, color = GreenTint.copy(alpha = 0.6f),
                modifier = Modifier
                    .clickable(onClick = onHeaderClick)
                    .padding(horizontal = 16.dp, vertical = 10.dp)
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun NewItemInput(text: String, onText: (String) -> Unit, onAdd: (String) -> Unit) {
    val focus = remember { FocusRequester() }
    val bring = remember { BringIntoViewRequester() }
    LaunchedEffect(Unit) {
        focus.requestFocus()
        delay(400) // 키보드가 올라와 화면이 줄어든 뒤에 입력창을 보이게 스크롤
        bring.bringIntoView()
    }
    OutlinedTextField(
        value = text,
        onValueChange = onText,
        placeholder = { Text("할 일을 입력하고 완료(✓)") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = {
            if (text.isNotBlank()) {
                onAdd(text.trim())
                onText("") // 입력창은 열어 둔 채 계속 추가
            }
        }),
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp)
            .bringIntoViewRequester(bring)
            .focusRequester(focus)
    )
}

@Composable
private fun TodoRow(
    todo: Todo,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    selected: Boolean,
    editing: Boolean,
    editText: String,
    onEditText: (String) -> Unit,
    onToggle: () -> Unit,
    onSelect: () -> Unit,
    onStartEdit: () -> Unit,
    onEditDone: (String) -> Unit,
    onDelete: () -> Unit,
    onMove: (Int) -> Unit,
) {
    var dragY by remember { mutableFloatStateOf(0f) }
    var dragging by remember { mutableStateOf(false) }
    // 드래그 도중 람다가 바뀌어도 제스처가 끊기지 않도록 최신 값을 참조
    val up by rememberUpdatedState(canMoveUp)
    val down by rememberUpdatedState(canMoveDown)
    val move by rememberUpdatedState(onMove)
    val select by rememberUpdatedState(onSelect)

    Row(
        Modifier
            .fillMaxWidth()
            .offset { IntOffset(0, dragY.roundToInt()) }
            .then(if (dragging) Modifier.shadow(6.dp) else Modifier)
            .background(if (selected) Hover else Color.Transparent)
            .pointerInput(todo.id) {
                // 꾹 누르면 수정/삭제 버튼이 나타나고, 그대로 위아래로 끌면 순서가 바뀐다
                detectDragGesturesAfterLongPress(
                    onDragStart = { select(); dragging = true },
                    onDrag = { change, amount ->
                        change.consume()
                        dragY += amount.y
                        val h = size.height
                        if (dragY > h * 0.6f && down) { move(1); dragY -= h }
                        else if (dragY < -h * 0.6f && up) { move(-1); dragY += h }
                    },
                    onDragEnd = { dragY = 0f; dragging = false },
                    onDragCancel = { dragY = 0f; dragging = false },
                )
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(
            checked = todo.done,
            onCheckedChange = { onToggle() },
            colors = CheckboxDefaults.colors(checkedColor = Green, uncheckedColor = GreenTint)
        )
        if (editing) {
            OutlinedTextField(
                value = editText,
                onValueChange = onEditText,
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onEditDone(editText) }),
                modifier = Modifier
                    .weight(1f)
                    .padding(vertical = 4.dp)
            )
            TextButton(onClick = { onEditDone(editText) }) { Text("확인", color = Green) }
        } else {
            Text(
                todo.text,
                modifier = Modifier
                    .weight(1f)
                    .padding(vertical = 10.dp),
                fontSize = 16.sp,
                color = if (todo.done) GreenTint else Ink,
                textDecoration = if (todo.done) TextDecoration.LineThrough else null,
            )
            if (selected) {
                TextButton(onClick = onStartEdit) { Text("수정", color = Green) }
                TextButton(onClick = onDelete) { Text("삭제", color = Late) }
            }
        }
    }
}
