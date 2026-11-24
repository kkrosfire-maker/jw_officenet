package com.jw.drugsearch

import android.graphics.Color as AColor
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

    var data by remember { mutableStateOf<RateData?>(null) }
    var keyword by remember { mutableStateOf("") }
    var targets by remember { mutableStateOf(DefaultTargets) }
    var exact by remember { mutableStateOf(false) }
    var visible by remember { mutableStateOf(DefaultVisible) }
    var itemsOpen by remember { mutableStateOf(false) }
    var sortMode by remember { mutableStateOf(SortMode.Ingredient) }
    var results by remember { mutableStateOf<List<Row>?>(null) }
    var lastKeyword by remember { mutableStateOf("") }
    var targetMenu by remember { mutableStateOf(false) }
    var sortMenu by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val loaded = withContext(Dispatchers.Default) { loadRates(context) }
        data = loaded
        // 개발·검증용: `adb shell am start ... --es q 검색어` 로 실행하면 그 검색어로 바로 검색한다.
        activity.intent?.getStringExtra("q")?.let { q ->
            keyword = q
            lastKeyword = q
            results = searchRows(loaded.rows, q, targets, exact)
        }
    }

    // 정렬은 결과가 있을 때 바로 적용된다
    val shown = remember(results, sortMode) { results?.let { sortRows(it, sortMode) } }

    fun doSearch() {
        val d = data ?: return
        results = searchRows(d.rows, keyword, targets, exact)
        lastKeyword = keyword
        keyboard?.hide()
        focus.clearFocus()
    }

    Column(Modifier.fillMaxSize().background(Bg)) {
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
            Icon(
                Icons.Default.Settings, "설정", tint = Color.White,
                modifier = Modifier.size(26.dp).clickable {
                    Toast.makeText(context, "설정은 준비 중입니다", Toast.LENGTH_SHORT).show()
                },
            )
        }

        // ---------- 검색 카드 ----------
        Column(
            Modifier
                .padding(horizontal = 12.dp)
                .padding(top = 0.dp)
                .fillMaxWidth()
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
                        if (keyword.isEmpty()) {
                            Text("검색어 또는 초성 (ㅇㅌㄹ)", color = Color(0xFF98A39D), fontSize = 13.5.sp, maxLines = 1, overflow = TextOverflow.Clip)
                        }
                        BasicTextField(
                            value = keyword,
                            onValueChange = { keyword = it },
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

            // 표시할 항목 (항상 접힌 상태로 시작)
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

        // ---------- 결과 머리글 + 정렬 ----------
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 12.dp, top = 12.dp, bottom = 6.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            Column(Modifier.weight(1f)) {
                val countText = when {
                    shown == null -> "요율표 검색"
                    else -> "검색 결과 ${shown.size}건"
                }
                Text(countText, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Ink)
                Text(sortMode.desc, fontSize = 11.sp, color = Muted)
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

        // ---------- 결과 목록 ----------
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when {
                data == null -> Hint("요율표를 불러오는 중…")
                shown == null -> Hint("검색어를 입력하고 검색을 눌러 주세요.\n(전체 ${data!!.rows.size}건)")
                shown.isEmpty() -> Hint("검색 결과가 없습니다.")
                else -> LazyColumn(
                    Modifier.fillMaxSize().padding(horizontal = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(9.dp),
                ) {
                    itemsIndexed(shown, key = { i, _ -> i }) { _, row -> RowCard(row, visible) }
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
                val list = shown
                if (list.isNullOrEmpty()) toast(context, "공유할 검색 결과가 없습니다")
                else shareText(context, buildShareText(data?.version.orEmpty(), lastKeyword, list, visible))
            }
            ActionButton("클립보드 복사", Modifier.weight(1f), iconRes = R.drawable.ic_copy) {
                scope.launch {
                    val bmp = captureWindow(activity)
                    if (bmp == null) toast(context, "화면을 캡처하지 못했습니다")
                    else {
                        copyImageToClipboard(context, bmp)
                        toast(context, "현재 화면을 클립보드에 복사했습니다")
                    }
                }
            }
            ActionButton("이미지 저장", Modifier.weight(1f), iconRes = R.drawable.ic_download) {
                scope.launch {
                    val bmp = captureWindow(activity)
                    if (bmp == null) toast(context, "화면을 캡처하지 못했습니다")
                    else {
                        val name = saveImageToDownloads(context, bmp)
                        toast(context, if (name != null) "다운로드 폴더에 저장했습니다\n$name" else "이미지를 저장하지 못했습니다")
                    }
                }
            }
        }
    }
}

// ================= 작은 부품들 =================

@Composable
private fun Hint(text: String) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.TopCenter) {
        Text(text, color = Muted, fontSize = 14.sp, modifier = Modifier.padding(top = 40.dp), lineHeight = 22.sp)
    }
}

@Composable
private fun CheckBox(on: Boolean) {
    Box(
        Modifier
            .size(18.dp)
            .clip(RoundedCornerShape(5.dp))
            .background(if (on) Green600 else Color.White)
            .border(BorderStroke(1.8.dp, if (on) Green600 else Color(0xFF9CA9A2)), RoundedCornerShape(5.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (on) Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(14.dp))
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
private fun Badge(text: String, bg: Color, fg: Color) {
    Text(
        text, color = fg, fontSize = 12.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1,
        modifier = Modifier.background(bg, RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/** 결과 카드: 제목(제품명) → 성분 → 대조의약품 → 보험코드·제약사명, 오른쪽에 약가·요율 배지, 맨 아래 비고. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RowCard(row: Row, visible: Set<Field>) {
    // 제목은 표시 중인 항목 중 제품명 > 성분 > 대조의약품 > 제약사명 > 보험코드 순으로 첫 번째
    val titleField = listOf(Field.Product, Field.Ingredient, Field.Ref, Field.Company, Field.Code)
        .firstOrNull { it in visible && !row.valueOf(it).isNullOrBlank() }
    val title = titleField?.let { row.valueOf(it) }

    Row(
        Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .background(Color.White, RoundedCornerShape(16.dp))
            .padding(end = 12.dp),
    ) {
        Box(
            Modifier.padding(vertical = 10.dp).width(4.dp).fillMaxHeight()
                .background(Green700, RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp))
        )
        Column(Modifier.weight(1f).padding(start = 10.dp, top = 11.dp, bottom = 11.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    title ?: "", Modifier.weight(1f),
                    fontSize = 15.5.sp, fontWeight = FontWeight.ExtraBold,
                    color = if (row.red) Red else Green900, lineHeight = 20.sp,
                )
                Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (Field.Price in visible && row.valueOf(Field.Price) != null)
                        Badge("약가 ${row.valueOf(Field.Price)}", Green100, Green900)
                    if (Field.Rate in visible && row.valueOf(Field.Rate) != null)
                        Badge("요율 ${row.valueOf(Field.Rate)}", AmberBg, AmberText)
                }
            }
            if (Field.Ingredient in visible && titleField != Field.Ingredient && !row.ingredient.isNullOrBlank()) {
                LabeledLine("성분", row.ingredient!!, Modifier.padding(top = 6.dp))
            }
            if (Field.Ref in visible && titleField != Field.Ref && !row.ref.isNullOrBlank()) {
                LabeledLine("대조의약품", row.ref!!, Modifier.padding(top = 4.dp))
            }
            val metas = buildList {
                if (Field.Code in visible && titleField != Field.Code && !row.code.isNullOrBlank()) add("보험코드" to row.code!!)
                if (Field.Company in visible && titleField != Field.Company && !row.company.isNullOrBlank()) add("제약사명" to row.company!!)
            }
            if (metas.isNotEmpty()) {
                FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    metas.forEach { (k, v) ->
                        Row {
                            Text(k, color = Muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.width(4.dp))
                            Text(v, color = Color(0xFF4F6057), fontSize = 12.sp)
                        }
                    }
                }
            }
            if (Field.Note in visible && !row.note.isNullOrBlank()) {
                Text(
                    "비고: ${row.note}", color = AmberText, fontSize = 11.5.sp,
                    modifier = Modifier.padding(top = 6.dp).fillMaxWidth().background(NoteBg, RoundedCornerShape(7.dp)).padding(horizontal = 7.dp, vertical = 4.dp),
                )
            }
        }
    }
}

@Composable
private fun LabeledLine(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier) {
        Text(label, color = Muted, fontSize = 12.5.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.width(8.dp))
        Text(value, color = Color(0xFF3C4D44), fontSize = 12.5.sp, lineHeight = 17.sp, modifier = Modifier.weight(1f))
    }
}
