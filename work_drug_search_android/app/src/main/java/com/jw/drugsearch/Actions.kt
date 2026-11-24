package com.jw.drugsearch

import android.content.ClipData
import android.content.ClipboardManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.view.PixelCopy
import android.widget.Toast
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.coroutines.resume

fun toast(context: Context, msg: String) =
    Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()

/** 현재 화면(창 전체)을 비트맵으로 캡처한다. 실패하면 null. */
suspend fun captureWindow(activity: MainActivity): Bitmap? {
    val view = activity.window.decorView
    if (view.width == 0 || view.height == 0) return null
    val bmp = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
    return suspendCancellableCoroutine { cont ->
        PixelCopy.request(activity.window, bmp, { result ->
            cont.resume(if (result == PixelCopy.SUCCESS) bmp else null)
        }, Handler(Looper.getMainLooper()))
    }
}

/** 캡처한 이미지를 클립보드(이미지)로 복사한다. */
suspend fun copyImageToClipboard(context: Context, bmp: Bitmap) {
    val uri = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "shared").apply { mkdirs() }
        val file = File(dir, "capture.png")
        file.outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    }
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newUri(context.contentResolver, "동일약품 검색 화면", uri))
}

/** 캡처한 이미지를 다운로드 폴더에 PNG로 저장한다. 저장한 파일명(실패 시 null)을 돌려준다. */
suspend fun saveImageToDownloads(context: Context, bmp: Bitmap): String? = withContext(Dispatchers.IO) {
    val name = "동일약품검색_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.KOREA).format(Date()) + ".png"
    val values = ContentValues().apply {
        put(MediaStore.Downloads.DISPLAY_NAME, name)
        put(MediaStore.Downloads.MIME_TYPE, "image/png")
        put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        put(MediaStore.Downloads.IS_PENDING, 1)
    }
    val resolver = context.contentResolver
    val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return@withContext null
    try {
        resolver.openOutputStream(uri)?.use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
            ?: return@withContext null
        values.clear()
        values.put(MediaStore.Downloads.IS_PENDING, 0)
        resolver.update(uri, values, null, null)
        name
    } catch (e: Exception) {
        resolver.delete(uri, null, null)
        null
    }
}

/** 현재 표시 항목 기준으로 검색 결과를 줄글로 만든다(공유용). 너무 길어지지 않게 최대 300건. */
fun buildShareText(version: String, keyword: String, rows: List<Row>, visible: Set<Field>): String {
    val sb = StringBuilder()
    sb.append("동일약품 검색기")
    if (version.isNotEmpty()) sb.append(" (요율표 $version)")
    sb.append("\n검색어: ").append(keyword.ifBlank { "(전체)" })
    sb.append("  / 결과 ${rows.size}건\n")
    rows.take(300).forEach { r ->
        sb.append("\n")
        sb.append(Field.entries.filter { it in visible }.mapNotNull { f ->
            r.valueOf(f)?.takeIf { it.isNotBlank() }?.let { "${f.label}: $it" }
        }.joinToString(" | "))
    }
    if (rows.size > 300) sb.append("\n\n… 외 ${rows.size - 300}건")
    return sb.toString()
}

fun shareText(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(send, "공유하기"))
}
