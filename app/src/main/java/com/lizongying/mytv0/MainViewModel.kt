import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.core.net.toFile
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.JsonSyntaxException
import com.lizongying.mytv0.BuildConfig
import com.lizongying.mytv0.ImageHelper
import com.lizongying.mytv0.MyTVApplication
import com.lizongying.mytv0.R
import com.lizongying.mytv0.SP
import com.lizongying.mytv0.Utils.getDateFormat
import com.lizongying.mytv0.Utils.getUrls
import com.lizongying.mytv0.bodyAlias
import com.lizongying.mytv0.codeAlias
import com.lizongying.mytv0.data.EPG
import com.lizongying.mytv0.data.Global.gson
import com.lizongying.mytv0.data.Global.typeEPGMap
import com.lizongying.mytv0.data.Global.typeTvList
import com.lizongying.mytv0.data.Source
import com.lizongying.mytv0.data.SourceType
import com.lizongying.mytv0.data.TV
import com.lizongying.mytv0.models.EPGXmlParser
import com.lizongying.mytv0.models.Sources
import com.lizongying.mytv0.models.TVGroupModel
import com.lizongying.mytv0.models.TVListModel
import com.lizongying.mytv0.models.TVModel
import com.lizongying.mytv0.requests.HttpClient
import com.lizongying.mytv0.showToast
import io.github.lizongying.Gua
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.io.InputStream


class MainViewModel : ViewModel() {
    private var timeFormat = if (SP.displaySeconds) "HH:mm:ss" else "HH:mm"

    private lateinit var appDirectory: File
    var listModel: List<TVModel> = emptyList()
    val groupModel = TVGroupModel()
    private var cacheFile: File? = null
    private var cacheChannels = ""
    private var initialized = false
    private val channelsMutex = Mutex()

    private lateinit var cacheEPG: File
    private var epgUrl = SP.epg

    private lateinit var imageHelper: ImageHelper

    val sources = Sources()

    private val _channelsOk = MutableLiveData<Boolean>()
    val channelsOk: LiveData<Boolean>
        get() = _channelsOk

    fun setDisplaySeconds(displaySeconds: Boolean) {
        timeFormat = if (displaySeconds) "HH:mm:ss" else "HH:mm"
        SP.displaySeconds = displaySeconds
    }

    fun getTime(): String {
        return getDateFormat(timeFormat)
    }

    fun updateEPG() {
        viewModelScope.launch {
            var success = false
            if (!epgUrl.isNullOrEmpty()) {
                success = updateEPG(epgUrl!!)
            }
            if (!success && !SP.epg.isNullOrEmpty()) {
                updateEPG(SP.epg!!)
            }
        }
    }

    fun updateConfig() {
        if (SP.configAutoLoad) {
            SP.configUrl?.let {
                if (it.startsWith("http")) {
                    viewModelScope.launch {
                        Log.i(TAG, "update config url: $it")
                        importFromUrl(it)
                        updateEPG()
                    }
                }
            }
        }
    }

    private fun getCache(): String {
        return if (cacheFile!!.exists()) {
            cacheFile!!.readText()
        } else {
            ""
        }
    }

    fun init(context: Context) {
        val application = context.applicationContext as MyTVApplication
        imageHelper = application.imageHelper

        groupModel.addTVListModel(TVListModel("我的收藏", 0))
        groupModel.addTVListModel(TVListModel("全部頻道", 1))

        appDirectory = context.filesDir
        cacheFile = File(appDirectory, CACHE_FILE_NAME)
        if (!cacheFile!!.exists()) {
            cacheFile!!.createNewFile()
        }

        cacheChannels = getCache()

        // ≤2.2.0 did not store which list is loaded; work it out from the cache until one is applied
        val listKey = SP.listKey ?: when {
            cacheChannels.isEmpty() -> "default"
            cacheChannels == context.resources.openRawResource(R.raw.lite).bufferedReader()
                .use { it.readText() } -> "lite"

            !SP.configUrl.isNullOrEmpty() -> "url:${SP.configUrl}"
            else -> "text"
        }

        if (cacheChannels.isEmpty()) {
            Log.i(TAG, "cacheChannels isEmpty")
            cacheChannels =
                context.resources.openRawResource(DEFAULT_CHANNELS_FILE).bufferedReader()
                    .use { it.readText() }
        }

        Log.i(TAG, "cacheChannels $cacheFile ${cacheChannels.length}")

        cacheEPG = File(appDirectory, CACHE_EPG)

        viewModelScope.launch {
            channelsMutex.withLock {
                try {
                    str2Channels(cacheChannels, listKey)
                } catch (e: Exception) {
                    Log.e(TAG, "init", e)
                    cacheFile!!.deleteOnExit()
                    R.string.channel_read_error.showToast()
                }

                initialized = true

                _channelsOk.value = true
            }

            if (!cacheEPG.exists()) {
                cacheEPG.createNewFile()
            } else {
                Log.i(TAG, "cacheEPG exists")
                if (readEPG(withContext(Dispatchers.IO) { cacheEPG.readText() })) {
                    Log.i(TAG, "cacheEPG success")
                } else {
                    Log.i(TAG, "cacheEPG failure")
                }
            }
        }
    }

    suspend fun preloadLogo() {
        if (!this::imageHelper.isInitialized) {
            Log.w(TAG, "imageHelper is not initialized")
            return
        }

        // ponytail: big lists skip the sequential preload (up to 3 requests per channel)
        // and rely on bind-time loading of tv.logo; bound/parallelise it if logos matter there
        if (listModel.size > PRELOAD_LOGO_MAX) {
            Log.i(TAG, "skip preloadLogo ${listModel.size}")
            return
        }

        for (tvModel in listModel) {
            var name = tvModel.tv.name
            if (name.isEmpty()) {
                name = tvModel.tv.title
            }
            val url = tvModel.tv.logo
            var urls =
                listOf(
                    "https://live.fanmingming.cn/tv/$name.png"
                ) + getUrls("https://raw.githubusercontent.com/fanmingming/live/main/tv/$name.png")
            if (url.isNotEmpty()) {
                urls = (getUrls(url) + urls).distinct()
            }

            imageHelper.preloadImage(
                name,
                urls,
            )
        }
    }

    suspend fun readEPG(input: InputStream): Boolean = withContext(Dispatchers.IO) {
        try {
            val res = EPGXmlParser().parse(input)

            // match off the main thread (channels x EPG names), then set all EPGs in one main pass
            val models = withContext(Dispatchers.Main) { listModel }
            val matched = mutableListOf<Pair<TVModel, List<EPG>>>()
            val e1 = mutableMapOf<String, List<EPG>>()
            for (m in models) {
                val name = m.tv.name.ifEmpty { m.tv.title }.lowercase()
                if (name.isEmpty()) {
                    continue
                }

                for ((n, epg) in res) {
                    if (name.contains(n, ignoreCase = true)) {
                        matched.add(m to epg)
                        e1[name] = epg
                        break
                    }
                }
            }
            withContext(Dispatchers.Main) {
                for ((m, epg) in matched) {
                    m.setEpg(epg)
                }
            }
            cacheEPG.writeText(gson.toJson(e1))
            Log.i(TAG, "readEPG success")
            true
        } catch (e: Exception) {
            Log.e(TAG, "readEPG", e)
            false
        }
    }

    private suspend fun readEPG(str: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val res: Map<String, List<EPG>> = gson.fromJson(str, typeEPGMap)

            val models = withContext(Dispatchers.Main) { listModel }
            val matched = mutableListOf<Pair<TVModel, List<EPG>>>()
            for (m in models) {
                val name = m.tv.name.ifEmpty { m.tv.title }.lowercase()
                if (name.isEmpty()) {
                    continue
                }

                val epg = res[name]
                if (epg != null) {
                    matched.add(m to epg)
                }
            }
            withContext(Dispatchers.Main) {
                for ((m, epg) in matched) {
                    m.setEpg(epg)
                }
            }
            Log.i(TAG, "readEPG success")
            true
        } catch (e: Exception) {
            Log.e(TAG, "readEPG", e)
            false
        }
    }

    private suspend fun updateEPG(url: String): Boolean {
        val urls = url.split(",").flatMap { u -> getUrls(u) }

        var success = false
        for (a in urls) {
            Log.i(TAG, "request $a")
            withContext(Dispatchers.IO) {
                try {
                    val request = okhttp3.Request.Builder().url(a).build()
                    val response = HttpClient.okHttpClient.newCall(request).execute()

                    if (response.isSuccessful) {
                        if (readEPG(response.bodyAlias()!!.byteStream())) {
                            Log.i(TAG, "EPG $a success")
                            success = true
                        }
                    } else {
                        Log.e(TAG, "EPG $a ${response.codeAlias()}")
                    }
                } catch (e: Exception) {
//                    Log.e(TAG, "EPG $a error", e)
                    Log.e(TAG, "EPG $a error")
                }
            }

            if (success) {
                break
            }
        }

        return success
    }

    private suspend fun importFromUrl(url: String, id: String = "") {
        val urls = getUrls(url).map { Pair(it, url) }

        var err = 0
        var shouldBreak = false
        for ((a, b) in urls) {
            Log.i(TAG, "request $a")
            withContext(Dispatchers.IO) {
                try {
                    val request = okhttp3.Request.Builder().url(a).build()
                    val response = HttpClient.okHttpClient.newCall(request).execute()

                    if (response.isSuccessful) {
                        val str = response.bodyAlias()?.string() ?: ""
                        withContext(Dispatchers.Main) {
                            tryStr2Channels(str, null, b, id)
                        }
                        err = 0
                        shouldBreak = true
                    } else {
                        Log.e(TAG, "Request status ${response.codeAlias()}")
                        err = R.string.channel_status_error
                    }
                } catch (e: JsonSyntaxException) {
                    e.printStackTrace()
                    Log.e(TAG, "JSON Parse Error", e)
                    err = R.string.channel_format_error
                    shouldBreak = true
                } catch (e: NullPointerException) {
                    e.printStackTrace()
                    Log.e(TAG, "Null Pointer Error", e)
                    err = R.string.channel_read_error
                } catch (e: Exception) {
                    e.printStackTrace()
                    Log.e(TAG, "Request error $e")
                    err = R.string.channel_request_error
                }
            }
            if (shouldBreak) break
        }

        if (err != 0) {
            err.showToast()
        }
    }

    fun reset(context: Context, rawId: Int = DEFAULT_CHANNELS_FILE) {
        val str = context.resources.openRawResource(rawId).bufferedReader()
            .use { it.readText() }

        try {
            // built-in lists are small, and SettingFragment uses the new list right after reset()
            val listKey = if (rawId == DEFAULT_CHANNELS_FILE) "default" else "lite"
            if (runBlocking { str2Channels(str, listKey) }) {
                // str2Channels skips a list equal to cacheChannels, so it must track what is loaded
                cacheChannels = str
                // the default list is the fallback when there is no cache; any other must be cached
                if (rawId != DEFAULT_CHANNELS_FILE) {
                    cacheFile!!.writeText(str)
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
            R.string.channel_read_error.showToast()
        }
    }

    fun importFromUri(uri: Uri, id: String = "") {
        if (uri.scheme == "file") {
            val file = uri.toFile()
            Log.i(TAG, "file $file")
            val str = if (file.exists()) {
                file.readText()
            } else {
                R.string.file_not_exist.showToast()
                return
            }

            tryStr2Channels(str, file, uri.toString(), id)
        } else {
            viewModelScope.launch {
                importFromUrl(uri.toString(), id)
            }
        }
    }

    fun tryStr2Channels(str: String, file: File?, url: String, id: String = "") {
        viewModelScope.launch {
            channelsMutex.withLock {
                try {
                    if (str2Channels(str, if (url.isNotEmpty()) "url:$url" else "text")) {
                        Log.i(TAG, "write to cacheFile $cacheFile ${str.length}")
                        withContext(Dispatchers.IO) { cacheFile!!.writeText(str) }
                        cacheChannels = str
                        if (url.isNotEmpty()) {
                            SP.configUrl = url
                            val source = Source(
                                id = id,
                                uri = url
                            )
                            sources.addSource(
                                source
                            )
                        }
                        _channelsOk.value = true
                        R.string.channel_import_success.showToast()
                        Log.i(TAG, "channel import success")
                    } else {
                        R.string.channel_import_error.showToast()
                        Log.w(TAG, "channel import error")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "tryStr2Channels", e)
                    file?.deleteOnExit()
                    R.string.channel_read_error.showToast()
                }
            }
        }
    }

    // Decoding and parsing run on Dispatchers.Default; the models (LiveData) are built back on the
    // calling main thread
    private suspend fun str2Channels(str: String, listKey: String): Boolean {
        if (initialized && str == cacheChannels) {
            Log.w(TAG, "same channels")
            return true
        }

        val g = Gua()
        val string = withContext(Dispatchers.Default) {
            if (g.verify(str)) g.decode(str) else str
        }

        if (string.isEmpty()) {
            Log.w(TAG, "channels is empty")
            return false
        }

        if (initialized && string == cacheChannels) {
            Log.w(TAG, "same channels")
            return true
        }

        var isNew = false
        val list = withContext(Dispatchers.Default) {
            isNew = string != cacheChannels && g.encode(string) != cacheChannels
            parseChannels(string)
        } ?: return false

        applyChannels(list, isNew, listKey)
        return true
    }

    private fun parseChannels(string: String): List<TV>? {
        val list: List<TV>

        when (string[0]) {
            '[' -> {
                try {
                    list = gson.fromJson(string, typeTvList)
                    Log.i(TAG, "导入频道 ${list.size}")
                } catch (e: Exception) {
                    Log.e(TAG, "str2Channels", e)
                    return null
                }
            }

            '#' -> {
                val lines = string.lines()
                val nameRegex = Regex("""tvg-name="([^"]+)"""")
                val logRegex = Regex("""tvg-logo="([^"]+)"""")
                val numRegex = Regex("""tvg-chno="([^"]+)"""")
                val epgRegex = Regex("""x-tvg-url="([^"]+)"""")
                val groupRegex = Regex("""group-title="([^"]+)"""")

                val l = mutableListOf<TV>()
                val tvMap = mutableMapOf<String, MutableList<TV>>()

                var tv = TV()
                var tvUris = mutableListOf<String>()
                for (line in lines) {
                    val trimmedLine = line.trim()
                    if (trimmedLine.isEmpty()) {
                        continue
                    }
                    if (trimmedLine.startsWith("#EXTM3U")) {
                        epgUrl = epgRegex.find(trimmedLine)?.groupValues?.get(1)?.trim()
                    } else if (trimmedLine.startsWith("#EXTINF")) {
                        val key = tv.group + tv.name
                        if (key.isNotEmpty()) {
                            tvMap.getOrPut(key) { mutableListOf() }.add(tv)
                        }
                        tv = TV()
                        tvUris = mutableListOf()
                        val info = trimmedLine.split(",")
                        tv.title = info.last().trim()
                        var name = nameRegex.find(info.first())?.groupValues?.get(1)?.trim()
                        tv.name = if (name.isNullOrEmpty()) tv.title else name
                        tv.logo = logRegex.find(info.first())?.groupValues?.get(1)?.trim() ?: ""
                        tv.number =
                            numRegex.find(info.first())?.groupValues?.get(1)?.trim()?.toInt() ?: -1
                        tv.group = groupRegex.find(info.first())?.groupValues?.get(1)?.trim() ?: ""
                    } else if (trimmedLine.startsWith("#EXTVLCOPT:http-")) {
                        val keyValue =
                            trimmedLine.substringAfter("#EXTVLCOPT:http-").split("=", limit = 2)
                        if (keyValue.size == 2) {
                            // VLC sends http-referrer as the Referer header
                            val header = if (keyValue[0] == "referrer") "Referer" else keyValue[0]
                            tv.headers = if (tv.headers == null) {
                                mapOf<String, String>(header to keyValue[1])
                            } else {
                                tv.headers!!.toMutableMap().apply {
                                    this[header] = keyValue[1]
                                }
                            }
                        }
                    } else if (!trimmedLine.startsWith("#")) {
                        tvUris.add(trimmedLine)
                        tv.uris = tvUris
                    }
                }
                val key = tv.group + tv.name
                if (key.isNotEmpty()) {
                    tvMap.getOrPut(key) { mutableListOf() }.add(tv)
                }
                for ((_, tv) in tvMap) {
                    val uris = tv.map { t -> t.uris }.flatten()
                    // one entry per uri, from the entry it came from (not t0)
                    val uriHeaders = tv.flatMap { t -> t.uris.map { t.headers } }
                    val t0 = tv[0]
                    val t1 = TV(
                        -1,
                        t0.name,
                        t0.title,
                        "",
                        t0.logo,
                        "",
                        uris,
                        0,
                        t0.headers,
                        t0.group,
                        SourceType.UNKNOWN,
                        t0.number,
                        emptyList(),
                        uriHeaders,
                    )
                    l.add(t1)
                }
                list = l
                Log.i(TAG, "导入频道 ${list.size}")
            }

            else -> {
                val lines = string.lines()
                var group = ""
                val l = mutableListOf<TV>()
                val tvMap = mutableMapOf<String, MutableList<String>>()
                for (line in lines) {
                    val trimmedLine = line.trim()
                    if (trimmedLine.isNotEmpty()) {
                        if (trimmedLine.contains("#genre#")) {
                            group = trimmedLine.split(',', limit = 2)[0].trim()
                        } else {
                            if (!trimmedLine.contains(",")) {
                                continue
                            }
                            val arr = trimmedLine.split(',').map { it.trim() }
                            val title = arr.first().trim()
                            val uris = arr.drop(1)

                            val key = group + title
                            tvMap.getOrPut(key) { mutableListOf(group) }.addAll(uris)
                        }
                    }
                }
                for ((title, uris) in tvMap) {
                    val channelGroup = uris.first();
                    val tv = TV(
                        -1,
                        "",
                        title.removePrefix(channelGroup),
                        "",
                        "",
                        "",
                        uris.drop(1),
                        0,
                        emptyMap(),
                        channelGroup,
                        SourceType.UNKNOWN,
                        -1,
                        emptyList(),
                    )

                    l.add(tv)
                }
                list = l
                Log.i(TAG, "导入频道 ${list.size}")
            }
        }

        return list
    }

    private fun applyChannels(list: List<TV>, isNew: Boolean, listKey: String) {
        // before any like is read or written (watch() replays them into this list on setChange)
        SP.listKey = listKey
        // ≤2.2.0 ids refer to this first load, the list they were saved with
        val legacyLike = SP.takeLegacyLike()

        // also empties 收藏, which watch() refills from the new list
        groupModel.initTVGroup()

        val map: MutableMap<String, MutableList<TVModel>> = mutableMapOf()
        for (v in list) {
            v.uris = v.uris.map(::rewritePhoenixProxyPort)
            if (v.group !in map) {
                map[v.group] = mutableListOf()
            }
            map[v.group]?.add(TVModel(v))
        }

        val listModelNew: MutableList<TVModel> = mutableListOf()
        var groupIndex = 2
        var id = 0
        for ((k, v) in map) {
            val listTVModel = TVListModel(k.ifEmpty { "未知" }, groupIndex)
            for ((listIndex, v1) in v.withIndex()) {
                v1.tv.id = id
                if (legacyLike?.contains(id.toString()) == true) {
                    SP.setLike(v1.tv, true)
                }
                v1.setLike(SP.getLike(v1.tv))
                v1.setGroupIndex(groupIndex)
                v1.listIndex = listIndex
                listModelNew.add(v1)
                id++
            }
            listTVModel.setTVListModel(v)
            groupModel.addTVListModel(listTVModel)
            groupIndex++
        }

        listModel = listModelNew

        // 全部频道
        groupModel.tvGroupValue[1].setTVListModel(listModel)

        if (isNew) {
            groupModel.initPosition()
        }

        groupModel.setChange()

        viewModelScope.launch {
            preloadLogo()
        }
    }

    private fun rewritePhoenixProxyPort(uri: String): String {
        if (!uri.startsWith(PHOENIX_PROXY_PREFIX)) return uri
        return "http://127.0.0.1:${BuildConfig.SERVER_PORT}/fh/" +
                uri.removePrefix(PHOENIX_PROXY_PREFIX)
    }

    companion object {
        private const val TAG = "MainViewModel"
        const val CACHE_FILE_NAME = "channels.txt"
        const val CACHE_EPG = "epg.xml"
        private const val PHOENIX_PROXY_PREFIX = "http://127.0.0.1:34567/fh/"
        private const val PRELOAD_LOGO_MAX = 500
        val DEFAULT_CHANNELS_FILE = R.raw.channels
    }
}
