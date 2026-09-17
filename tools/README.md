# tools

维护频道列表的五个脚本，外加一个 gua64 编解码器。全部是 python3 标准库，没有第三方依赖。

## 前置条件

- **python3** —— 系统自带的就行，不需要装任何包。
- **ffprobe** —— 只有 `extract_test.py` 用，用来确认一条 url 里到底有没有视频流。
  `brew install ffmpeg`。
- **adb** —— `extract_test.py --serial` 和 `verify_playback.py` 需要，用来连电视。
  电视先打开「网络调试」，然后 `adb connect <tv-ip>:5555`。
- **电视上的静态 curl** —— 只有在电视上做连通性测试时需要。安卓自带的 `/system/bin/curl`
  要么没有要么太老，从 <https://github.com/stunnel/static-curl> 下对应架构的（这台机器是
  armv7）推到电视上：

      adb -s <tv-ip>:5555 push curl /data/local/tmp/curl
      adb -s <tv-ip>:5555 shell chmod 755 /data/local/tmp/curl

  脚本调用它时会带上 `--doh-url https://223.5.5.5/dns-query`，用 DNS over HTTPS 绕开
  电视上那个经常解析失败的 DNS。

## 脚本

### extract_test.py

从十几个公开 m3u 源把频道抓下来、按名字筛出我们要的那些、逐条 url 实测能不能播，最后写出
`playlists/channels.json`、`candidates.csv` 和 `report.md`。连通性由电视说了算 —— 电视和
Mac 的网络路径不一样，Mac 能连的电视未必能连，所以判定必须在电视上做。

    python3 extract_test.py --selftest             # 只跑解析器和归一化的自检，不联网
    python3 extract_test.py --serial <tv-ip>:5555  # 完整跑一遍，电视当裁判
    python3 extract_test.py --mac                  # 同样的流程，但改在 Mac 上测
    python3 extract_test.py --retest               # 忽略连通性缓存，重新测
    python3 extract_test.py --reprobe              # 忽略 codec 缓存，重新 ffprobe
    python3 extract_test.py --out DIR              # 三个输出文件写到别处

### merge.py

把 `playlists/channels.json` 编码成 apk 内置的 `app/src/main/res/raw/channels.txt`。
顺手干两件测试脚本干不了的事：给凤凰卫视三个频道插上 app 内部的本地转发地址
`http://127.0.0.1:34567/fh/<id>.flv` 作为第一个 uri（这是 app 自己起的 fengshows 代理，
只有 app 里能用），以及把分组按 app 里显示的顺序排好。改完列表必须重新打包 apk 才生效。

    python3 merge.py                     # 默认路径：playlists/channels.json -> app/.../raw/channels.txt
    python3 merge.py in.json out.txt     # 指定路径
    python3 merge.py --selftest          # 只跑自检，不写文件

### export_m3u.py

生成 `playlists/current.m3u`。走的是 `merge.py` 的 `merge()`，所以导出来的和 apk 实际播的
一模一样，包括凤凰那三条本地地址。一个频道有几个 uri 就连着出几条 `#EXTINF`，标题相同；
带 header 的频道会在 url 前面加上 `#EXTVLCOPT:http-user-agent=` / `http-referrer=`。

    python3 export_m3u.py [out.m3u]

### verify_playback.py

装完 apk 之后在电视上真播一遍。用数字键切到第 N 个频道，然后读 app 自己打的 logcat 判断
到底播起来没有。注意 app 每次切台都会先打一条假的 `<title> playing`，紧跟着一条
`<title> 尝试播放`（v2.1.0 以前的版本打繁体「嘗試播放」，脚本两种都认）—— 只有后面没跟「尝试播放」的那条 playing 才是真的播起来了，脚本的
`classify()` 就是在处理这件事，自检覆盖的也是它。

    python3 verify_playback.py --serial <tv-ip>:5555 --count 10
    python3 verify_playback.py --serial <tv-ip>:5555 --only 3,17,42
    python3 verify_playback.py --selftest    # 纯日志分类的自检，不碰电视

`--serial` 必填，没有默认值。`--pkg` 默认 `com.lizongying.newmytv`。失败的频道会把整段
logcat 存成 `log_NNN.txt`，结果汇总进 `results.csv`。

### scan_sources.py

批量扫一批公开直播源（脚本里写死的 26 个地址），看哪些频道在这台 Mac 上能播。测法直接调
`extract_test.py` 的 `test_twice()` / `probe_codec()`，走它的 Mac 模式，所以判定规则和上面完全
一样；不同的是不按名单筛，所有 url 都测，测完再按规则自动分组（央视、凤凰、卫视、港澳台、新马、
日本、体育、纪录片、国际新闻、数字频道、地方、海外·<类型>）。同一个 url 出现在几个源里只测一次。

    python3 scan_sources.py --selftest      # txt 解析、垃圾条目过滤、分类器、按名合并的自检，不联网
    python3 scan_sources.py --limit 300     # 试跑：从各个源轮流挑 300 条没测过的
    python3 scan_sources.py --workers 48    # 全量跑，默认就是 48 并发
    python3 scan_sources.py --report-only   # 不下载不测试，用缓存重新生成全部输出文件

- 源列表下到 `tools/.cache/scan_src/`，下不下来就用上次的副本。
- 每测完一条就往 `tools/.cache/scan_results.jsonl` 追加一行，全量要跑好几个小时，中断了直接重跑，
  已经测过的会跳过。想重测就删掉这个文件。和 `extract_test.py` 的 `tvtest.json` 不共用：那个缓存
  不区分是电视测的还是 Mac 测的。
- 同一个 host 最多同时测 3 条。IPv6 字面量、rtmp 之类、局域网地址、youtube/github 不测，状态分别记
  `ipv6`、`untested-protocol`、`excluded-lan`、`excluded-host`；还没轮到测的记 `untested`。
- stream1/t.freetv.fun 的 2566 条地址读源时直接丢掉：这个主机约 20 秒才响应，超过测试协议的 10 秒超时，
  删掉前测过的 1125 条一条都没通过。
- 能播的 url 按名字合并成频道：去掉画质、编码、[BD]、「HK」、（备用）这类标记后按任何文字的字母和
  数字比（简繁、大小写、重音不分，`+` 记作 plus，CCTV5+ 和 CCTV5、CCTV4K 和 CCTV4 仍是两个）。一个
  频道只有一个分组，取各条 url 里最具体的；拉丁字母名字的 url 来自两个以上国家时按国家拆开，名字后加
  `(国家码)`。apk 现有列表里的频道（按名字，对不上再按 url）沿用现有的名字和分组。港澳台频道按新闻 /
  综艺表 / 其余分到 港台新闻、港台综艺、港澳台。
- 频道内 uri 的顺序：apk 现有列表里有的频道，把现有列表里的 uri（在电视上真播过）放最前；其余按不带
  请求头的优先（v2.1.3 及以前的 app 整个频道只用第一条的请求头），再 h264 优先，再按分片延迟从小到大。
- 输出在 `playlists/scan/`：`merged.m3u`（每个频道能播的 uri 全部列出，同名条目连在一起，app 会把它们
  合成一个频道、后面几条当备用）、`merged-lite.m3u`（同上的精简版，349 个频道：apk 内置频道全部保留；海外·*、国际新闻、体育、纪录片只留 `PICKS` 按名字挑的；地方只留省级和主要城市的电视台（`LOCAL_PREFIX`），用 `LOCAL_DENY` 去掉广播、景区直播和点播；其余小分组去掉 `DROP` 里的重复、宗教和购物频道；不要 4K/8K 副本。名单里有没对上的会写进 report.md；同时复制一份到 `app/src/main/res/raw/lite.m3u`，即 app 设置里的「切换到全球精简版」）、`available.m3u`（同样的频道，每个最多 3 个 uri）、`channels.csv`
  （每个频道一行：分组、是否新建分组、国家、uri 数、在现有列表里叫什么、合并进来的原名、源、同一 url
  的其他叫法）、`results.csv`（每条 url 一行，名字和分组是它最后所在的频道，列和 `candidates.csv`
  类似，多一列 `sources`）、`report.md`（合并统计、分组、各源通过率、状态分布，以及和 apk 内置列表
  逐频道的对比）。

### gua64.py

`channels.txt` 用的那套编码：base64 的变体，字母表换成了 64 个易经卦象字符。
`merge.py` 依赖它，也可以单独拿来看上游的列表里到底有什么。

    python3 gua64.py                        # 自检
    python3 gua64.py encode in.json out.txt
    python3 gua64.py decode in.txt

## 测试流程

`extract_test.py` 完整跑一遍是这么走的：

1. **下载源列表。** iptv-org 的 news / hk / uk / tw / cn / sports / us / documentary 分类，
   加上 Free-TV、Guovin、fanmingming 三个仓库的 playlist，一共十一个。每次都重新下（这些
   列表天天在变），下不下来就用 `tools/.cache/` 里上一次的副本。再加上 `playlists/upstream/`
   里上游 my-tv-0 的两份内置列表。sports / us / documentary 这三个是后加的，只喂给按模式
   匹配的那几个分组，不会流进已经测好的四个新闻类分组。

2. **按名字筛。** 央视、凤凰、港台新闻、国际新闻这四组是写死的名单，靠正则把各家五花八门的
   写法（`CCTV-13 新闻`、`CCTV13.cn@SD`、`Phoenix InfoNews Channel`）归一到同一个规范名。
   体育、卫视、纪录片、港台综艺这四组没法列名单，改成按模式匹配再排序取前 N 个。非英语频道
   一律排除 —— 语言标记经常不在匹配上的那个字段里（`tvg-id="DW.de@Russian"` 而显示名就是
   `DW`），所以是拿三个字段拼起来一起判的。IPv6 字面量地址直接扔掉，电视没有 IPv6 路由。
   每个频道最多测 8 条 url，同一个 host 最多 3 条，避免一个 CDN 挂了就整条链全军覆没。

3. **逐条 url 实测。** 在电视上用静态 curl 发请求，8 条并发，并且按 host 轮转打散 ——
   CCTV 那个小镜像农场同时拉好几个频道就会限流，表现成超时和莫名其妙的 302。全程 `-4`，
   因为电视没有 IPv6 路由，只有 AAAA 记录的 host 在这里就该失败。youtube / github 这两类
   host 直接拒绝：它们答 200 而且体积不小，但 ExoPlayer 根本打不开。判定规则：

   - **HLS**（body 以 `#EXTM3U` 开头）：master → 取第一个变体 → 变体里取第一个分片，
     分片必须在 12 秒内回来至少 50 KB 才算过。
   - **非 HLS**：只证明有字节回来了是不够的，必须 ffprobe 能认出视频编码才算数。
   - **代理注入的拦截页**正是靠分片大小这条规则抓出来的。路由器代理会对某些目的地回一个
     41 字节的「the content is not available in your area」，有时候盖着 200，有时候盖着
     一个指向自己的 301。光看状态码会全部放行。
   - 失败分两种：结构性失败（没有变体、没有分片）一次定生死；看起来像临时抽风的
     （无响应、分片 404、408/429/5xx）再试一次 —— 直播列表在滚动，两次请求之间分片过期
     导致 404 是很正常的事。

4. **ffprobe 探编码。** 只对连通的 url 探，拿到的 codec / 分辨率用来排序。命令里必须带上

       -extension_picky 0 -allowed_extensions ALL -allowed_segment_extensions ALL

   因为好几家 CDN 把 HLS 分片命名成 `.jpg` 或者干脆不带扩展名来躲过滤，ffmpeg 默认会拒绝
   打开这种文件、然后报告「没有流」，看上去就像不是视频。加上这三个选项之后同样的 url 会
   老老实实解析成 h264 —— 凤凰、無綫新聞台、翡翠台、ViuTV 背后那几个 jdshipin 跳转就是这么
   救回来的，否则会被当成死链丢掉。ffprobe 没有 `-4`，不过 Mac 本来也没有公网 IPv6。

5. **缓存。** 连通性结果按 url 缓存进 `tools/.cache/tvtest.json`，codec 缓存进
   `codec.json`，`.cache/` 已经 gitignore 掉了。codec 只缓存成功的结果：ffprobe 对裸
   mpegts 的 url 偶尔会抽风，而「认不出编码的非 HLS url」会被判成不是视频，一次抽风就能
   让一个频道在两次原本一样的运行之间凭空消失。`--retest` / `--reprobe` 分别绕开这两个缓存。

6. **排序和取舍。** 同一个频道的多条可用 url 按这个顺序排，最多留 3 条：ffprobe 确实认出
   h264 的在最前，然后是靠下载分片证明过的 playlist，再然后是认不出编码的，hevc 和 mpeg2
   排最后 —— 这台 armeabi-v7a 的安卓 9 盒子这两种都解不利索。同一档之内，分片回来得快的
   在前。按模式匹配的四个分组（体育 30、卫视 30、纪录片 20、港台综艺 25）先按名气排序再截断。

## 怎么读 candidates.csv

每行是一条候选 url，不管测没测过都在里面。

| 列 | 含义 |
| --- | --- |
| `canonical_name` | 归一之后的频道名，多个源的不同写法会落到同一个名字上 |
| `group` | 所属分组 |
| `url` | 候选地址 |
| `source` | 来自哪个源列表（`guovin`、`hk`、`builtin-json` 等） |
| `headers_json` | 这条 url 需要的请求头，通常是 `{}` |
| `tv_status` | 测试结果，见下 |
| `tv_playlist_ms` | 拉 playlist 花的毫秒数（HLS 的话是 master + 变体两段之和） |
| `tv_segment_ms` | 拉第一个媒体分片花的毫秒数，排序主要看这个 |
| `seg_bytes` | 分片大小，`< 50000` 基本就是拦截页或者空壳 |
| `codec` / `width` / `height` | ffprobe 的结果，`unknown` 表示探不出来 |
| `verdict` | `pass` / `fail` / `skipped` / `excluded` 四选一 |

`tv_status` 的取值：

- `ok` —— 过了，playlist 是真的而且分片够大，或者 ffprobe 认出了视频
- `ok-small` —— 分片回来了但不到 50 KB，也算通过；排序不看这个，只看编码和延迟
- `short-body` —— 非 HLS，回来的字节太少
- `not-video` —— 非 HLS，字节够多但 ffprobe 认不出编码，多半是网页或文本
- `no-response` / `http-N` —— 连不上，或者 HTTP 错误码
- `variant-http-N` / `no-variant` / `no-segment` / `seg-http-N` —— HLS 链条在哪一环断的
- `untested-protocol` —— rtmp / rtsp / udp，curl 测不了
- `excluded-host` —— youtube / github 这类 host，直接拒绝
- `excluded-slate` —— CNN 的备播卡，或者 epg.pw 源站离线时塞进来的「无信号」垫片（master 里唯一的变体指向
  `nosignal_h264`，带二维码广告），画面完美但没有节目，不要
- `skipped-cap` —— 这个频道的名额已经满了（每频道 8 条、每 host 3 条），没轮到测
