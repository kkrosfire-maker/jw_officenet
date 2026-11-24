package com.jw.drugsearch

import android.graphics.Color as AColor
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.DisableSelection
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

// ---- 색상 (PC 검색기·시안과 같은 초록 계열) ----
private val Green900 = Color(0xFF0A4A33)
private val Green700 = Color(0xFF11704A)
private val Green600 = Color(0xFF167B3C)
private val Green100 = Color(0xFFE3F1EA)
private val Green50 = Color(0xFFEEF6F1)
private val Bg = Color(0xFFF2F5F3)
private val Line = Color(0xFFDCE3DF)
private val Muted = Color(0xFF6B7A72)
private val Ink = Color(0xFF1B2B24)
private val VersionGray = Color(0xFFAEBDB5)
private val AmberBg = Color(0xFFFFF1D6)
private val AmberText = Color(0xFF8A5A00)
private val NoteBg = Color(0xFFFFF8E8)
private val Red = Color(0xFFB3261E)
private val Burgundy = Color(0xFF8E1B3A) // 성분명 글자색
private val NoteGray = Color(0xFF7B8780) // 성분 보충설명(괄호) 글자색

private val DefaultTargets = setOf(Field.Product, Field.Ingredient, Field.Ref)
private val DefaultVisible = Field.entries.filter { it != Field.Ref }.toSet()

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 초록 헤더가 상태바 뒤까지 올라오고, 상태바 아이콘은 흰색
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(AColor.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(AColor.TRANSPARENT, AColor.TRANSPARENT),
        )
        setContent {
            MaterialTheme { DrugApp(this) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
fun DrugApp(activity: MainActivity) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val haptic = LocalHapticFeedback.current
    val listState = rememberLazyListState()

    var data by remember { mutableStateOf<RateData?>(null) }
    // 한글 조합(자모가 글자로 합쳐지는 중)을 유지하려고 String 이 아니라 TextFieldValue 로 들고 있는다.
    var query by remember { mutableStateOf(TextFieldValue("")) }
    var targets by remember { mutableStateOf(DefaultTargets) }
    var exact by remember { mutableStateOf(false) }
    var visible by remember { mutableStateOf(DefaultVisible) }
    var itemsOpen by remember { mutableStateOf(false) }
    var sortMode by remember { mutableStateOf(SortMode.Ingredient) }
    var results by remember { mutableStateOf<List<Row>?>(null) }
    var lastKeyword by remember { mutableStateOf("") }
    var targetMenu by remember { mutableStateOf(false) }
    var sortMenu by remember { mutableStateOf(false) }

    // 체크(선택) 모드: 켜져 있으면 이미지 저장·클립보드 복사·공유가 체크한 카드만 내보낸다. 꺼져 있으면 전체.
    var selectMode by remember { mutableStateOf(false) }
    var checked by remember { mutableStateOf(setOf<Int>()) }
    var notesOpen by remember { mutableStateOf(setOf<Int>()) }
    var panelRect by remember { mutableStateOf(Rect.Zero) }

    LaunchedEffect(Unit) {
        val loaded = withContext(Dispatchers.Default) { loadRates(context) }
        data = loaded
        // 개발·검증용: `adb shell am start ... --es q 검색어` 로 실행하면 그 검색어로 바로 검색한다.
        activity.intent?.getStringExtra("q")?.let { q ->
            query = TextFieldValue(q, TextRange(q.length))
            lastKeyword = q
            results = searchRows(loaded.rows, q, targets, exact)
        }
    }

    // 정렬은 결과가 있을 때 바로 적용된다
    val shown = remember(results, sortMode) { results?.let { sortRows(it, sortMode) } }

    // 새 검색이면 체크 모드를 풀고 목록 맨 위로
    LaunchedEffect(results) {
        selectMode = false
        checked = emptySet()
        notesOpen = emptySet()
        listState.scrollToItem(0)
    }

    BackHandler(enabled = selectMode) { selectMode = false; checked = emptySet() }

    fun doSearch() {
        val d = data ?: return
        results = searchRows(d.rows, query.text, targets, exact)
        lastKeyword = query.text
        keyboard?.hide()
        focus.clearFocus()
    }

    /** 내보낼 카드: 체크 모드면 체크한 것만, 아니면 전체. 내보낼 게 없으면 null(안내 토스트는 여기서). */
    fun exportRows(): List<Row>? {
        val list = shown
        if (list.isNullOrEmpty()) { toast(context, "내보낼 검색 결과가 없습니다"); return null }
        if (!selectMode) return list
        val picked = list.filter { it.id in checked }
        if (picked.isEmpty()) { toast(context, "체크한 항목이 없습니다"); return null }
        return picked
    }

    fun enterSelectMode(first: Row) {
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        selectMode = true
        checked = setOf(first.id)
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Bg)
            // 펼친 '표시할 항목' 바깥을 누르면 접는다(누른 동작 자체는 그대로 아래로 전달)
            .pointerInput(itemsOpen) {
                if (itemsOpen) {
                    awaitPointerEventScope {
                        while (true) {
                            val ev = awaitPointerEvent(PointerEventPass.Initial)
                            if (ev.type == PointerEventType.Press) {
                                val p = ev.changes.first().position
                                if (!panelRect.contains(p)) itemsOpen = false
                            }
                        }
                    }
                }
            }
    ) {
        Column(Modifier.fillMaxSize().imePadding()) {
            // ---------- 헤더 ----------
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Brush.linearGradient(listOf(Green900, Green700)))
                    .statusBarsPadding()
                    .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 22.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(Color.White.copy(alpha = .14f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(painterResource(R.drawable.ic_launcher_logo), null, tint = Color.White, modifier = Modifier.size(28.dp))
                }
                Spacer(Modifier.width(10.dp))
                Row(Modifier.weight(1f), verticalAlignment = Alignment.Bottom) {
                    Text("동일약품 검색기", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1)
                    val v = data?.version.orEmpty()
                    if (v.isNotEmpty()) {
                        Spacer(Modifier.width(6.dp))
                        Text("(요율표 $v)", color = VersionGray, fontSize = 12.sp, maxLines = 1, modifier = Modifier.padding(bottom = 3.dp))
                    }
                }
            }

            // ---------- 검색 카드 ----------
            Column(
                Modifier
                    .padding(horizontal = 12.dp)
                    .fillMaxWidth()
                    .onGloballyPositioned { panelRect = Rect(it.positionInRoot(), androidx.compose.ui.geometry.Size(it.size.width.toFloat(), it.size.height.toFloat())) }
                    .background(Color.White, RoundedCornerShape(18.dp))
                    .padding(12.dp)
            ) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(
                        Modifier
                            .weight(1f).height(44.dp)
                            .border(BorderStroke(1.5.dp, Line), RoundedCornerShape(12.dp))
                            .padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.Search, null, tint = Ink, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                            if (query.text.isEmpty()) {
                                Text("검색어 또는 초성 (ㅇㅌㄹ)", color = Color(0xFF98A39D), fontSize = 13.5.sp, maxLines = 1, overflow = TextOverflow.Clip)
                            }
                            BasicTextField(
                                value = query,
                                onValueChange = { query = it },
                                singleLine = true,
                                textStyle = TextStyle(color = Ink, fontSize = 15.sp),
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                                keyboardActions = KeyboardActions(onSearch = { doSearch() }),
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                    // 검색 버튼 + 검색 대상 드롭다운(▼)
                    Row {
                        Box(
                            Modifier
                                .width(58.dp).height(44.dp)
                                .clip(RoundedCornerShape(topStart = 12.dp, bottomStart = 12.dp))
                                .background(Green700)
                                .clickable { doSearch() },
                            contentAlignment = Alignment.Center,
                        ) { Text("검색", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp) }
                        Box {
                            Box(
                                Modifier
                                    .width(36.dp).height(44.dp)
                                    .clip(RoundedCornerShape(topEnd = 12.dp, bottomEnd = 12.dp))
                                    .background(Green900)
                                    .clickable { targetMenu = true },
                                contentAlignment = Alignment.Center,
                            ) { Icon(Icons.Default.ArrowDropDown, "검색 대상", tint = Color.White, modifier = Modifier.size(26.dp)) }
                            // 메뉴 밖을 누르면 자동으로 닫힌다(onDismissRequest)
                            DropdownMenu(
                                expanded = targetMenu,
                                onDismissRequest = { targetMenu = false },
                                containerColor = Color.White,
                                shape = RoundedCornerShape(14.dp),
                            ) {
                                Text("검색 대상", color = Muted, fontSize = 11.sp, modifier = Modifier.padding(start = 16.dp, top = 4.dp, bottom = 2.dp))
                                listOf(Field.Product, Field.Ingredient, Field.Ref).forEach { f ->
                                    DropdownMenuItem(
                                        text = { CheckRow(f.label, f in targets) },
                                        onClick = {
                                            // 최소 하나는 선택되어 있어야 한다
                                            targets = if (f in targets) {
                                                if (targets.size > 1) targets - f else targets
                                            } else targets + f
                                        },
                                    )
                                }
                                Box(Modifier.padding(horizontal = 12.dp, vertical = 2.dp).fillMaxWidth().height(1.dp).background(Line))
                                DropdownMenuItem(
                                    text = { CheckRow("정확히 일치", exact) },
                                    onClick = { exact = !exact },
                                )
                            }
                        }
                    }
                }

                // 표시할 항목 (항상 접힌 상태로 시작, 바깥을 누르면 다시 접힌다)
                Box(Modifier.padding(top = 12.dp).fillMaxWidth().height(1.dp).background(Line))
                Row(
                    Modifier.fillMaxWidth().clickable { itemsOpen = !itemsOpen }.padding(top = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("표시할 항목", fontWeight = FontWeight.ExtraBold, fontSize = 14.sp, color = Ink)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "${visible.size}/${Field.entries.size}", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = Muted,
                        modifier = Modifier.background(Green50, RoundedCornerShape(8.dp)).padding(horizontal = 7.dp, vertical = 1.dp),
                    )
                    Spacer(Modifier.weight(1f))
                    Icon(Icons.Default.KeyboardArrowDown, null, tint = Muted, modifier = Modifier.rotate(if (itemsOpen) 180f else 0f))
                }
                if (itemsOpen) {
                    FlowRow(
                        Modifier.padding(top = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        val allOn = visible.size == Field.entries.size
                        Chip("전체선택", allOn) { visible = Field.entries.toSet() }
                        Field.entries.forEach { f ->
                            Chip(f.label, f in visible) {
                                // 최소 하나는 표시되어야 한다
                                visible = if (f in visible) {
                                    if (visible.size > 1) visible - f else visible
                                } else visible + f
                            }
                        }
                    }
                }
            }

            // ---------- 결과 머리글: 건수 / (선택 버튼) 정렬 ----------
            Row(
                Modifier.fillMaxWidth().padding(start = 16.dp, end = 12.dp, top = 12.dp, bottom = 6.dp).height(36.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (selectMode) {
                    Text("${checked.size}건 선택됨", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Green900)
                    Spacer(Modifier.weight(1f))
                    HeaderChip("전체선택") { checked = shown?.map { it.id }?.toSet() ?: emptySet() }
                    Spacer(Modifier.width(6.dp))
                    HeaderChip("취소") { selectMode = false; checked = emptySet() }
                } else {
                    Text(
                        if (shown == null) "요율표 검색" else "검색 결과 ${shown.size}건",
                        fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Ink,
                    )
                    Spacer(Modifier.weight(1f))
                    if (!shown.isNullOrEmpty()) {
                        HeaderChip("선택") { selectMode = true; checked = emptySet() }
                        Spacer(Modifier.width(6.dp))
                    }
                    Box {
                        Row(
                            Modifier
                                .height(34.dp)
                                .background(Color.White, RoundedCornerShape(10.dp))
                                .border(BorderStroke(1.dp, Line), RoundedCornerShape(10.dp))
                                .clickable { sortMenu = true }
                                .padding(horizontal = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("정렬: ${sortMode.label}", fontSize = 13.sp, color = Ink)
                            Icon(Icons.Default.KeyboardArrowDown, null, tint = Ink, modifier = Modifier.size(18.dp))
                        }
                        DropdownMenu(
                            expanded = sortMenu,
                            onDismissRequest = { sortMenu = false },
                            containerColor = Color.White,
                            shape = RoundedCornerShape(14.dp),
                        ) {
                            SortMode.entries.forEach { m ->
                                DropdownMenuItem(
                                    text = {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Radio(m == sortMode)
                                            Spacer(Modifier.width(10.dp))
                                            Column {
                                                Text(m.label, fontSize = 14.sp, fontWeight = if (m == sortMode) FontWeight.Bold else FontWeight.Normal, color = Ink)
                                                Text(m.desc, fontSize = 11.sp, color = Muted)
                                            }
                                        }
                                    },
                                    onClick = { sortMode = m; sortMenu = false },
                                )
                            }
                            DropdownMenuItem(
                                enabled = false,
                                text = {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Radio(false)
                                        Spacer(Modifier.width(10.dp))
                                        Text("사용자 설정", fontSize = 14.sp, color = Color(0xFF9AA59F))
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            "준비 중", fontSize = 10.sp, color = Color(0xFF7B8780),
                                            modifier = Modifier.background(Color(0xFFEEF0EF), RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 2.dp),
                                        )
                                    }
                                },
                                onClick = {},
                            )
                        }
                    }
                }
            }

            // ---------- 결과 목록 ----------
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when {
                    data == null -> Hint("요율표를 불러오는 중…")
                    shown == null -> Hint("검색어를 입력하고 검색을 눌러 주세요.\n(전체 ${data!!.rows.size}건)")
                    shown.isEmpty() -> Hint("검색 결과가 없습니다.")
                    else -> {
                        LazyColumn(
                            state = listState,
                            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
                            verticalArrangement = Arrangement.spacedBy(9.dp),
                        ) {
                            itemsIndexed(shown, key = { _, r -> r.id }) { _, row ->
                                RowCard(
                                    row = row,
                                    visible = visible,
                                    selectMode = selectMode,
                                    isChecked = row.id in checked,
                                    noteOpen = row.id in notesOpen,
                                    onToggleCheck = {
                                        checked = if (row.id in checked) checked - row.id else checked + row.id
                                    },
                                    onEnterSelect = { enterSelectMode(row) },
                                    onToggleNote = {
                                        notesOpen = if (row.id in notesOpen) notesOpen - row.id else notesOpen + row.id
                                    },
                                )
                            }
                        }
                        // 오른쪽 빠른 스크롤바(끌어서 이동)
                        FastScrollbar(listState, Modifier.align(Alignment.CenterEnd))
                        // 아래로 내려가 있으면 '맨 위로' 버튼
                        val showTop by derivedStateOfTop(listState)
                        if (showTop) {
                            Box(
                                Modifier
                                    .align(Alignment.BottomEnd)
                                    .padding(end = 30.dp, bottom = 14.dp)
                                    .size(46.dp)
                                    .clip(CircleShape)
                                    .background(Green700)
                                    .clickable { scope.launch { listState.animateScrollToItem(0) } },
                                contentAlignment = Alignment.Center,
                            ) { Icon(Icons.Default.KeyboardArrowUp, "맨 위로", tint = Color.White, modifier = Modifier.size(28.dp)) }
                        }
                    }
                }
            }

            // ---------- 하단 고정 버튼 ----------
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Color.White)
                    .navigationBarsPadding()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ActionButton("공유하기", Modifier.weight(1f), icon = Icons.Default.Share) {
                    exportRows()?.let { rows ->
                        shareText(context, buildShareText(data?.version.orEmpty(), lastKeyword, rows, visible))
                    }
                }
                ActionButton("클립보드 복사", Modifier.weight(1f), iconRes = R.drawable.ic_copy) {
                    val rows = exportRows() ?: return@ActionButton
                    scope.launch {
                        val pages = withContext(Dispatchers.Default) {
                            CardImage.render(rows, visible, notesOpen, data?.version.orEmpty(), lastKeyword, shown?.size ?: rows.size)
                        }
                        copyImageToClipboard(context, pages.first())
                        toast(
                            context,
                            if (pages.size > 1) "${CardImage.PAGE_SIZE}건만 복사했습니다(전체 ${rows.size}건). 나머지는 '이미지 저장'을 쓰세요"
                            else "${rows.size}건을 이미지로 복사했습니다",
                        )
                    }
                }
                ActionButton("이미지 저장", Modifier.weight(1f), iconRes = R.drawable.ic_download) {
                    val rows = exportRows() ?: return@ActionButton
                    scope.launch {
                        val pages = withContext(Dispatchers.Default) {
                            CardImage.render(rows, visible, notesOpen, data?.version.orEmpty(), lastKeyword, shown?.size ?: rows.size)
                        }
                        val stamp = nowStamp()
                        var ok = 0
                        pages.forEachIndexed { i, bmp ->
                            if (saveImageToDownloads(context, bmp, stamp, i + 1, pages.size) != null) ok++
                        }
                        toast(
                            context,
                            if (ok == pages.size) "다운로드 폴더에 저장했습니다(${rows.size}건, 이미지 ${ok}장)"
                            else "이미지를 저장하지 못했습니다",
                        )
                    }
                }
            }
        }
    }
}

// ================= 작은 부품들 =================

/** 목록이 아래로 어느 정도 내려갔는지(맨 위로 버튼을 보일지). */
@Composable
private fun derivedStateOfTop(state: LazyListState) =
    remember(state) { androidx.compose.runtime.derivedStateOf { state.firstVisibleItemIndex > 3 } }

/** 오른쪽 빠른 스크롤바: 스크롤 중에 나타나 잠시 뒤 사라지고, 끌면 그 위치로 바로 이동한다. */
@Composable
private fun FastScrollbar(state: LazyListState, modifier: Modifier = Modifier) {
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current
    var dragging by remember { mutableStateOf(false) }
    var active by remember { mutableStateOf(false) }
    val total = state.layoutInfo.totalItemsCount
    val visibleCount = state.layoutInfo.visibleItemsInfo.size

    LaunchedEffect(state.isScrollInProgress, dragging) {
        if (state.isScrollInProgress || dragging) active = true
        else { delay(1400); active = false }
    }
    if (total <= visibleCount + 1) return

    BoxWithConstraints(modifier.fillMaxHeight().width(28.dp).padding(vertical = 4.dp)) {
        val trackPx = with(density) { maxHeight.toPx() }
        val thumbPx = with(density) { 56.dp.toPx() }
        val range = (total - visibleCount).coerceAtLeast(1)
        val fraction = (state.firstVisibleItemIndex.toFloat() / range).coerceIn(0f, 1f)
        val thumbY = fraction * (trackPx - thumbPx)

        if (active) {
            Box(
                Modifier
                    .fillMaxSize()
                    .pointerInput(total) {
                        detectVerticalDragGestures(
                            onDragStart = { dragging = true },
                            onDragEnd = { dragging = false },
                            onDragCancel = { dragging = false },
                        ) { change, _ ->
                            val f = ((change.position.y - thumbPx / 2) / (trackPx - thumbPx)).coerceIn(0f, 1f)
                            scope.launch { state.scrollToItem((f * range).roundToInt()) }
                            change.consume()
                        }
                    }
            ) {
                Box(
                    Modifier
                        .align(Alignment.TopEnd)
                        .offset(y = with(density) { thumbY.toDp() })
                        .padding(end = 3.dp)
                        .width(if (dragging) 9.dp else 6.dp)
                        .height(56.dp)
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (dragging) Green700 else Green700.copy(alpha = .55f))
                )
            }
        }
    }
}

@Composable
private fun Hint(text: String) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.TopCenter) {
        Text(text, color = Muted, fontSize = 14.sp, modifier = Modifier.padding(top = 40.dp), lineHeight = 22.sp)
    }
}

@Composable
private fun HeaderChip(label: String, onClick: () -> Unit) {
    Text(
        label, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Green900,
        modifier = Modifier
            .clip(RoundedCornerShape(10.dp))
            .background(Green100)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 7.dp),
    )
}

@Composable
private fun CheckBox(on: Boolean, size: Int = 18) {
    Box(
        Modifier
            .size(size.dp)
            .clip(RoundedCornerShape(5.dp))
            .background(if (on) Green600 else Color.White)
            .border(BorderStroke(1.8.dp, if (on) Green600 else Color(0xFF9CA9A2)), RoundedCornerShape(5.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (on) Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size((size - 4).dp))
    }
}

@Composable
private fun Radio(on: Boolean) {
    Box(
        Modifier.size(16.dp).border(BorderStroke(1.8.dp, if (on) Green600 else Color(0xFF9CA9A2)), CircleShape),
        contentAlignment = Alignment.Center,
    ) { if (on) Box(Modifier.size(8.dp).background(Green600, CircleShape)) }
}

@Composable
private fun CheckRow(label: String, on: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.width(150.dp).padding(vertical = 4.dp)) {
        CheckBox(on)
        Spacer(Modifier.width(10.dp))
        Text(label, fontSize = 14.5.sp, color = Ink)
    }
}

@Composable
private fun Chip(label: String, on: Boolean, onClick: () -> Unit) {
    Row(
        Modifier
            .clip(RoundedCornerShape(9.dp))
            .background(if (on) Green50 else Color(0xFFF4F5F4))
            .clickable(onClick = onClick)
            .padding(horizontal = 9.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CheckBox(on)
        Spacer(Modifier.width(5.dp))
        Text(label, fontSize = 13.sp, color = if (on) Ink else Color(0xFF7B8780))
    }
}

@Composable
private fun ActionButton(
    label: String, modifier: Modifier,
    icon: ImageVector? = null, iconRes: Int? = null, onClick: () -> Unit,
) {
    Row(
        modifier
            .height(48.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Green100)
            .clickable(onClick = onClick),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) Icon(icon, null, tint = Green900, modifier = Modifier.size(18.dp))
        if (iconRes != null) Icon(painterResource(iconRes), null, tint = Green900, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(6.dp))
        Text(label, color = Green900, fontWeight = FontWeight.Bold, fontSize = 13.sp, maxLines = 1)
    }
}

@Composable
private fun PriceBadge(text: String, bg: Color, fg: Color) {
    Text(
        text, color = fg, fontSize = 12.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1,
        modifier = Modifier.background(bg, RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/**
 * 결과 카드. 글자는 꾹 눌러 끌면 선택·복사된다(SelectionContainer).
 * 체크 모드는 카드 왼쪽 막대나 약가·요율 배지를 꾹 누르면 켜지고(글자 선택과 안 겹치게 글자 밖 영역),
 * 체크 모드에서는 카드를 눌러 체크/해제한다.
 */
@OptIn(ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
private fun RowCard(
    row: Row, visible: Set<Field>, selectMode: Boolean, isChecked: Boolean, noteOpen: Boolean,
    onToggleCheck: () -> Unit, onEnterSelect: () -> Unit, onToggleNote: () -> Unit,
) {
    // 제목은 표시 중인 항목 중 제품명 > 성분 > 대조의약품 > 제약사명 > 보험코드 순으로 첫 번째
    val titleField = row.titleField(visible)
    val title = titleField?.let { row.shown(it) }
    val hasBadges = (Field.Price in visible && row.valueOf(Field.Price) != null) ||
        (Field.Rate in visible && row.valueOf(Field.Rate) != null)

    val cardMod = Modifier
        .fillMaxWidth()
        .height(IntrinsicSize.Min)
        .clip(RoundedCornerShape(16.dp))
        .background(if (selectMode && isChecked) Color(0xFFEAF5EE) else Color.White)
        .let { if (selectMode) it.clickable(onClick = onToggleCheck) else it }

    Row(cardMod.padding(end = 12.dp)) {
        // 왼쪽 막대(체크 모드가 아닐 때 이 영역을 꾹 누르면 체크 모드)
        Box(
            Modifier
                .width(26.dp).fillMaxHeight()
                .let { if (selectMode) it else it.combinedClickable(onClick = {}, onLongClick = onEnterSelect) },
            contentAlignment = Alignment.CenterStart,
        ) {
            Box(
                Modifier.padding(vertical = 10.dp).width(4.dp).fillMaxHeight()
                    .background(Green700, RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp))
            )
        }
        if (selectMode) {
            Box(Modifier.padding(top = 12.dp, end = 8.dp)) { CheckBox(isChecked, 22) }
        }

        val body: @Composable () -> Unit = {
            Column(Modifier.padding(top = 11.dp, bottom = 11.dp)) {
                // 제목+성분을 한 묶음(왼쪽)으로, 약가·요율 배지는 그 옆(오른쪽)에 둬서
                // 배지가 높아도 성분이 제목 바로 아래에 붙어 있게 한다.
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            title ?: "",
                            fontSize = 15.5.sp, fontWeight = FontWeight.ExtraBold,
                            color = if (row.red) Red else Green900, lineHeight = 20.sp,
                        )
                        if (Field.Ingredient in visible && titleField != Field.Ingredient && !row.ingredient.isNullOrBlank()) {
                            Row(Modifier.padding(top = 3.dp)) {
                                Text("성분", color = Muted, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
                                Spacer(Modifier.width(8.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(row.ingredientMain, color = Burgundy, fontSize = 12.5.sp, lineHeight = 17.sp)
                                    // (20mg as atorvastatin) 같은 보충 설명: 원 성분명 아래, 회색, 글자 크기 80%
                                    row.ingredientNote?.let {
                                        Text(it, color = NoteGray, fontSize = 10.sp, lineHeight = 14.sp)
                                    }
                                }
                            }
                        }
                        if (Field.Ref in visible && titleField != Field.Ref && !row.ref.isNullOrBlank()) {
                            Row(Modifier.padding(top = 3.dp)) {
                                Text("대조의약품", color = Muted, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
                                Spacer(Modifier.width(8.dp))
                                Text(row.ref!!, color = Color(0xFF3C4D44), fontSize = 12.5.sp, lineHeight = 17.sp, modifier = Modifier.weight(1f))
                            }
                        }
                    }
                    if (hasBadges) {
                        // 배지(글자 선택 대상이 아님) 를 꾹 누르면 체크 모드
                        DisableSelection {
                            Column(
                                Modifier
                                    .let { if (selectMode) it else it.combinedClickable(onClick = {}, onLongClick = onEnterSelect) },
                                horizontalAlignment = Alignment.End,
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                if (Field.Price in visible && row.valueOf(Field.Price) != null)
                                    PriceBadge("약가 ${row.valueOf(Field.Price)}", Green100, Green900)
                                if (Field.Rate in visible && row.valueOf(Field.Rate) != null)
                                    PriceBadge("요율 ${row.valueOf(Field.Rate)}", AmberBg, AmberText)
                            }
                        }
                    }
                }
                val metas = buildList {
                    if (Field.Code in visible && titleField != Field.Code && !row.code.isNullOrBlank()) add(Triple("보험코드", row.code!!, Color(0xFF4F6057)))
                    if (Field.Company in visible && titleField != Field.Company && !row.company.isNullOrBlank()) add(Triple("제약사명", row.company!!, Green700))
                }
                if (metas.isNotEmpty()) {
                    FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        metas.forEach { (k, v, color) ->
                            Row {
                                Text(k, color = Muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                                Spacer(Modifier.width(4.dp))
                                Text(v, color = color, fontSize = 12.sp, fontWeight = if (color == Green700) FontWeight.SemiBold else FontWeight.Normal)
                            }
                        }
                    }
                }
                // 비고: 처음엔 접혀 있고, ▼ 를 누르면 펼쳐진다
                if (Field.Note in visible && !row.note.isNullOrBlank()) {
                    DisableSelection {
                        Row(
                            Modifier
                                .padding(top = 4.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .clickable(onClick = onToggleNote)
                                .padding(end = 6.dp, top = 2.dp, bottom = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("비고", color = AmberText, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                            Icon(
                                Icons.Default.KeyboardArrowDown, if (noteOpen) "비고 접기" else "비고 펼치기",
                                tint = AmberText, modifier = Modifier.size(20.dp).rotate(if (noteOpen) 180f else 0f),
                            )
                        }
                    }
                    if (noteOpen) {
                        Text(
                            row.note!!, color = AmberText, fontSize = 11.5.sp,
                            modifier = Modifier.padding(top = 2.dp).fillMaxWidth().background(NoteBg, RoundedCornerShape(7.dp)).padding(horizontal = 7.dp, vertical = 4.dp),
                        )
                    }
                }
            }
        }

        // 체크 모드가 아닐 때만 글자 선택(길게 눌러 끌어서 복사) 가능
        Box(Modifier.weight(1f).padding(start = if (selectMode) 0.dp else 0.dp)) {
            if (selectMode) body() else SelectionContainer { body() }
        }
    }
}
