package com.lizongying.mytv0

import android.content.Context
import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.util.Log
import com.bumptech.glide.Glide
import com.lizongying.mytv0.requests.HttpClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.concurrent.ConcurrentHashMap


class ImageHelper(private val context: Context) {
    private val cacheDir = context.cacheDir

    private var dir: File = File(cacheDir, LOGO)
    private val files = ConcurrentHashMap<String, File>()

    init {
        if (!dir.exists()) {
            dir.mkdir()
        }
        dir.listFiles()?.forEach { file ->
            // ponytail: mirrors used to return 200 + HTML landing pages that got cached as logos
            if (file.length() == 0L || file.inputStream().use { it.read() } == '<'.code) {
                file.delete()
            } else {
                files[file.name] = file
            }
        }
    }

    private suspend fun downloadImage(url: String, file: File): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val request = okhttp3.Request.Builder()
                    .url(url)
                    .build()

                HttpClient.okHttpClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@withContext false
                    if (response.header("Content-Type")?.startsWith("image/") != true) return@withContext false
                    file.outputStream().use { out ->
                        response.bodyAlias()!!.byteStream().copyTo(out)
                    }
                    if (file.length() == 0L) {
                        file.delete()
                        return@withContext false
                    }
                    true
                }
            } catch (e: Exception) {
                Log.e(TAG, "downloadImage error $url", e)
                file.delete()
                false
            }
        }
    }

    suspend fun preloadImage(
        key: String,
        urlList: List<String>,
    ) {
        val file = files[key]
        if (file != null) {
            Log.d(TAG, "image exists ${file.absolutePath}")
            return
        }

        if (urlList.isEmpty()) {
            return
        }

        for (url in urlList) {
            val file = File(cacheDir, "$LOGO/$key")
            if (downloadImage(url, file)) {
                files[file.name] = file
                Log.d(TAG, "downloadImage success $url ${file.absolutePath}")
                break
            }
        }
    }

    fun loadImage(
        key: String,
        imageView: androidx.appcompat.widget.AppCompatImageView,
        bitmap: Bitmap,
        url: String,
    ) {
        val file = files[key]
        if (file != null) {
            Log.d(TAG, "image exists ${file.absolutePath}")
            Glide.with(context)
                .load(file)
                .fitCenter()
                .into(imageView)
            return
        }

        if (url.isEmpty()) {
            Log.i(TAG, "$key image bitmap")
            Glide.with(context)
                .load(bitmap)
                .fitCenter()
                .into(imageView)
        } else {
            Log.i(TAG, "$key image $url")
            Glide.with(context)
                .load(url)
                .placeholder(BitmapDrawable(context.resources, bitmap))
                .fitCenter()
                .into(imageView)
        }
    }

    fun clearImage() {
        val dir = File(cacheDir, LOGO)
        if (dir.exists()) {
            dir.deleteRecursively()
        }
    }

    companion object {
        const val TAG = "ImageHelper"
        const val LOGO = "logo"
    }
}
