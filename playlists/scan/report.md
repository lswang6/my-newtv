# 批量扫描报告

- 生成时间：2026-09-17 21:05。
- 测试位置：这台 Mac，协议与 `tools/extract_test.py --mac` 相同，**不是电视**。出口是路由器代理，落在韩国的 Oracle Cloud 节点，只有 IPv4；结果说明的是这个出口能连上什么，不代表国内家庭宽带或港台线路。
- 源：26 个地址，其中 12 与 02 完全相同，只下载一次。
- 去重后共 18664 条 url（url 加请求头算一条）：可测 17965，已测 17965，通过 10029（55.8%）。
- IPv6 字面量 460 条、rtmp/rtsp 等 33 条没测：这台 Mac 和电视都没有 IPv6 路由，curl 也测不了 rtmp。
- 结果：`merged.m3u` 8822 个频道、10029 条 uri（能播的全部），`available.m3u` 每个频道最多 3 条、共 9750 条；每个频道的明细在 `channels.csv`，每条 url 的在 `results.csv`。
- freetv.fun（stream1 和 t 两个子域）的 2566 条 url 已从源中删除：该主机约 20 秒才响应，超过测试协议的 10 秒超时；删除前实测 1125 条，通过 0 条。源 04、05、06、07、09、10（epg.pw 各地区列表）的地址几乎全在这个主机上，删除后分别只剩 18、0、0、14、0、0 个条目，所以基本没有贡献频道。
- 测试记录时间跨度 09-17 15:20 到 09-17 18:50，平均 85 条/分钟（含 ffprobe）。

## 合并

能播的 url 按名字合并成频道：名字去掉画质、编码、[BD]、「HK」、（备用）这类标记后，只按字母（任何文字）和数字比，简繁、大小写不分，`+` 记作 plus。一个频道只有一个分组，取它各条 url 里最具体的那个；拉丁字母名字的 url 若来自两个以上国家（tvg-id 后缀），按国家拆开并在名字后加 (国家码)。现有列表里的频道（按名字，对不上再按 url）沿用现有的名字和分组；名字按国家拆开了的，取装着它的 url 最多的那一份。

- 通过的 url 10029 条。按旧键（分组 + 只留 ASCII 字母数字和汉字的名字）算是 8537 个频道；按新规则合并成 8478 个名字，再按国家拆开，最后 8822 个。旧键把没有拉丁字母和数字的俄文、阿拉伯文等名字全算成同一个，所以旧数偏少。
- 有 ≥2 条 uri 的频道 679 个。每个频道的 uri 数：1 条 8143 个，2 条 430 个，3 条 157 个，4–5 条 47 个，6–10 条 42 个，>10 条 3 个。
- 按国家拆开的名字 252 个，拆成 596 个频道。
- 同一条 url 在不同源里叫不同名字的 270 条（涉及 266 个频道）：按最具体的分组取一个名字，其余记在 channels.csv 的 conflict 列。
- 不带请求头的 uri 排在前面；仍有 72 个频道里的 75 条 uri 需要的请求头和第一条不同：v2.1.3 及以前的 app 整个频道只用第一条的请求头，这些 uri 会带错或不带。
- 现有列表里的频道把 apk 列表中（在电视上真播过）的 uri 排到最前：67 个频道的顺序因此变了。
- 精简版 `merged-lite.m3u`：349 个频道、836 条 uri。apk 内置频道全部保留；海外·*、国际新闻、体育、纪录片只留 `PICKS` 按名字挑的；地方只留省级和主要城市的电视台，不要广播、景区直播和点播；其余分组去掉 `DROP` 里的重复、宗教和购物频道；不要 4K/8K 副本。
- 现有列表 119 个频道中 116 个在新列表里、分组一致 116 个（不靠现有列表覆盖、分类器自己就一致的 114 个）；没找到：Setanta Sports、Star Sports 2、龍祥時代電影台。

### 分组

「新建」是现有列表里没有的分组。

| 分组 | 新建 | 频道 | uri（merged.m3u） | uri（available.m3u） |
| --- | --- | --- | --- | --- |
| 央视 |  | 55 | 188 | 101 |
| 凤凰 |  | 4 | 18 | 10 |
| 港台新闻 |  | 17 | 55 | 32 |
| 国际新闻 |  | 704 | 767 | 749 |
| 体育 |  | 236 | 260 | 254 |
| 卫视 |  | 45 | 211 | 120 |
| 纪录片 |  | 168 | 193 | 193 |
| 港台综艺 |  | 16 | 31 | 24 |
| 港澳台 | 是 | 31 | 36 | 36 |
| 新马 | 是 | 8 | 8 | 8 |
| 日本 | 是 | 14 | 15 | 15 |
| 数字频道 | 是 | 11 | 22 | 19 |
| 地方 | 是 | 943 | 1094 | 1073 |
| 海外·剧集 | 是 | 297 | 386 | 386 |
| 海外·宗教 | 是 | 560 | 569 | 569 |
| 海外·少儿 | 是 | 279 | 330 | 326 |
| 海外·教育 | 是 | 121 | 131 | 131 |
| 海外·电影 | 是 | 494 | 581 | 576 |
| 海外·综合 | 是 | 3609 | 3765 | 3761 |
| 海外·综艺 | 是 | 679 | 813 | 812 |
| 海外·音乐 | 是 | 531 | 556 | 555 |

### uri 最多的 30 个频道

| 分组 | 频道 | uri | 合并进来的原名 |
| --- | --- | --- | --- |
| 港台新闻 | 翡翠台 | 19 | 翡翠台、Jade (1080p)、「HK」翡翠台、翡翠台「字幕」、翡翠台北美版、TVB翡翠台（备用）、华丽翡翠台「新加坡」、华丽翡翠台、华丽翡翠台「硬字幕」、TVB翡翠台 1080P、TVB翡翠台 4K、翡翠台「WebVTT字幕」 |
| 国际新闻 | Bloomberg TV | 14 | Bloomberg TV Europe (720p)、Bloomberg TV、Bloomberg Television (Europe)、Bloomberg TV+、Bloomberg、Bloomberg Television (US)、Bloomberg News Asia、Bloomberg TV Asia (720p)、Bloomberg TV Asia Live Event (720p)、Bloomberg TV Australia (270p)、Bloomberg TV Asia Live Event、Bloomberg TV Asia (Live)、Bloomberg TV US Politics Live Event (720p)、Bloomberg TV EMEA Live Event (720p)、Bloomberg TV (1080p)、Bloomberg TV US Live Event (720p)、Bloomberg TV+ (2160p) |
| 卫视 | 浙江卫视 | 12 | 浙江卫视 |
| 央视 | CCTV2 财经 | 9 | CCTV-2 (720p)、CCTV-2 财经、CCTV-2、CCTV2 |
| 央视 | CCTV5 体育 | 9 | CCTV-5、CCTV5 |
| 央视 | CCTV9 纪录 | 9 | CCTV-9 (576i)、CCTV-9、CCTV9、CCTV-9 纪录 |
| 央视 | CCTV11 戏曲 | 9 | CCTV-11 (720p)、CCTV-11 戏曲、CCTV-11、CCTV11 |
| 央视 | CCTV12 社会与法 | 9 | CCTV-12 (720p)、CCTV-12 社会与法、CCTV-12、CCTV12 |
| 央视 | CCTV14 少儿 | 9 | CCTV-14、CCTV-14 (1080p)、CCTV-14 少儿、CCTV14 |
| 卫视 | 湖南卫视 | 9 | 湖南卫视、Hunan TV (2160p) |
| 卫视 | 东方卫视 | 9 | 东方卫视、新纪实 |
| 央视 | CCTV3 综艺 | 8 | CCTV-3、CCTV3、CCTV-3 (720p)、CCTV-3 综艺 |
| 央视 | CCTV6 电影 | 8 | CCTV-6、CCTV-6 (1080p)、CCTV-6 电影、CCTV6 |
| 央视 | CCTV7 国防军事 | 8 | CCTV-7、CCTV-7 (720p)、CCTV-7 国防军事、CCTV7 |
| 央视 | CCTV8 电视剧 | 8 | CCTV-8、CCTV8、CCTV-8 (720p)、CCTV-8 电视剧 |
| 央视 | CCTV10 科教 | 8 | CCTV-10、CCTV10、CCTV-10 (720p)、CCTV-10 科教 |
| 央视 | CCTV13 新闻 | 8 | CCTV-13 (720p)、CCTV-13 新闻、CCTV-13、CCTV13 |
| 央视 | CCTV15 音乐 | 8 | CCTV-15、CCTV-15 音乐、CCTV15、CCTV-15 (1080p) |
| 卫视 | 黑龙江卫视 | 8 | 黑龙江卫视 |
| 央视 | CCTV1 综合 | 7 | CCTV-1 (720p)、CCTV-1 综合、CCTV-1、CCTV1 |
| 央视 | CCTV4 中文国际 | 7 | CCTV-4、CCTV-4 Asia (720p)、CCTV-4 中文国际（亚）、CCTV4 |
| 央视 | CCTV17 农业农村 | 7 | CCTV-17、CCTV-17 (1080p)、CCTV-17 农业农村、CCTV17 |
| 凤凰 | 凤凰卫视中文台 | 7 | 凤凰中文、凤凰卫视、凤凰中文高清、凤凰卫视台、凤凰中文台 |
| 港台新闻 | 無綫新聞台 | 7 | 无线新闻、无线新闻台、無綫新聞台、無綫新聞台國際版 |
| 国际新闻 | Arirang | 7 | Arirang TV (1080p)、ArirangTV FHD、Arirang World、Arirang、ArirangTV HD、Arirang 阿里郎、Arirang TV HD (720p) |
| 卫视 | 江西卫视 | 7 | 江西卫视 |
| 卫视 | 贵州卫视 | 7 | 贵州卫视 |
| 卫视 | 广西卫视 | 7 | 广西卫视 |
| 地方 | 广州综合 | 7 | 广州综合、Guangzhou TV |
| 体育 | 广东体育 | 6 | 广东体育 |

## 各源情况

「独有频道」是 merged.m3u 里只有这一个源提供了可用 url 的频道数。

| # | 地址 | 下载 | 条目 | 去重 url | 已测 | 通过 | 通过率 | 独有频道 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | https://php.946985.filegear-sg.me/jackTV.m3u | ok | 211 | 211 | 211 | 104 | 49% | 37 |
| 02 | https://iptv-org.github.io/iptv/index.m3u | ok | 11039 | 11039 | 11007 | 7675 | 70% | 6483 |
| 03 | https://web.utako.moe/jp.m3u | 失败（LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to web），无缓存 | — | 0 | 0 | 0 | — | 0 |
| 04 | https://epg.pw/test_channels.m3u | ok | 18 | 15 | 0 | 0 | — | 0 |
| 05 | https://epg.pw/test_channels_hong_kong.m3u | ok | 0 | 0 | 0 | 0 | — | 0 |
| 06 | https://epg.pw/test_channels_macau.m3u | ok | 0 | 0 | 0 | 0 | — | 0 |
| 07 | https://epg.pw/test_channels_taiwan.m3u | ok | 14 | 11 | 0 | 0 | — | 0 |
| 08 | https://iptv-org.github.io/iptv/countries/tw.m3u | ok | 26 | 26 | 25 | 7 | 28% | 0 |
| 09 | https://epg.pw/test_channels_singapore.m3u | ok | 0 | 0 | 0 | 0 | — | 0 |
| 10 | https://epg.pw/test_channels_malaysia.m3u | ok | 0 | 0 | 0 | 0 | — | 0 |
| 11 | https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8 | ok | 2074 | 2053 | 1912 | 1151 | 60% | 471 |
| 12 | https://iptv-org.github.io/iptv/index.m3u | 同 02，不重复下载 | — | 0 | 0 | 0 | — | 0 |
| 13 | https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u | ok | 120 | 118 | 117 | 82 | 70% | 20 |
| 14 | https://raw.githubusercontent.com/BigBigGrandG/IPTV-URL/release/Gather.m3u | ok | 1955 | 1926 | 1662 | 433 | 26% | 363 |
| 15 | https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u | ok | 123 | 123 | 123 | 0 | 0% | 0 |
| 16 | https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.txt | 失败（HTTP 404），无缓存 | — | 0 | 0 | 0 | — | 0 |
| 17 | https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.m3u | 失败（HTTP 404），无缓存 | — | 0 | 0 | 0 | — | 0 |
| 18 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u | ok | 1234 | 1194 | 1098 | 591 | 54% | 0 |
| 19 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u | ok | 472 | 468 | 465 | 397 | 85% | 0 |
| 20 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u | ok | 918 | 881 | 743 | 210 | 28% | 0 |
| 21 | https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u | ok | 1217 | 1194 | 1142 | 351 | 31% | 85 |
| 22 | https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv6.m3u | ok | 850 | 838 | 712 | 78 | 11% | 9 |
| 23 | https://live.zbds.top/tv/iptv4.txt | ok | 704 | 689 | 683 | 650 | 95% | 0 |
| 24 | https://live.zbds.top/tv/iptv4.m3u | ok | 545 | 544 | 541 | 523 | 97% | 0 |
| 25 | https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/TV-IPV4.m3u | ok | 58 | 58 | 58 | 0 | 0% | 0 |
| 26 | https://raw.githubusercontent.com/vamoschuck/TV/main/M3U | ok | 788 | 784 | 784 | 75 | 10% | 20 |

## 状态分布

| 状态 | url 数 |
| --- | --- |
| ok | 9848 |
| no-response | 3176 |
| http-403 | 1618 |
| http-404 | 1384 |
| ipv6 | 460 |
| short-body | 257 |
| excluded-host | 205 |
| http-490 | 192 |
| ok-small | 181 |
| seg-http-404 | 155 |
| variant-http-404 | 134 |
| not-video | 87 |
| seg-http-403 | 87 |
| http-302 | 86 |
| http-502 | 86 |
| http-500 | 65 |
| variant-http-0 | 60 |
| http-429 | 58 |
| seg-http-0 | 53 |
| http-503 | 52 |
| http-400 | 47 |
| no-segment | 36 |
| variant-http-403 | 34 |
| untested-protocol | 33 |
| http-204 | 25 |
| http-401 | 24 |
| http-504 | 21 |
| excluded-slate | 19 |
| http-200 | 18 |
| http-418 | 17 |
| http-416 | 15 |
| http-410 | 14 |
| http-530 | 13 |
| http-409 | 9 |
| http-406 | 9 |
| variant-http-200 | 7 |
| http-451 | 7 |
| http-512 | 6 |
| http-523 | 6 |
| variant-http-400 | 6 |
| seg-http-503 | 5 |
| seg-http-200 | 5 |
| seg-http-206 | 5 |
| http-301 | 5 |
| variant-http-206 | 4 |
| http-511 | 3 |
| variant-http-416 | 3 |
| http-521 | 3 |
| http-218 | 2 |
| variant-http-504 | 2 |
| seg-http-416 | 1 |
| http-307 | 1 |
| http-421 | 1 |
| http-574 | 1 |
| http-407 | 1 |
| http-461 | 1 |
| http-408 | 1 |
| http-412 | 1 |
| seg-http-400 | 1 |
| variant-http-453 | 1 |
| http-405 | 1 |
| http-402 | 1 |
| http-308 | 1 |
| variant-http-410 | 1 |
| variant-http-503 | 1 |
| http-304 | 1 |
| variant-http-500 | 1 |

## 与现有列表对比

### 源列表

对照 README「直播源来源」表，也就是 `tools/extract_test.py` 实际下载的 11 个源。

| # | 地址 | 关系 |
| --- | --- | --- |
| 01 | https://php.946985.filegear-sg.me/jackTV.m3u | 此前未用 |
| 02 | https://iptv-org.github.io/iptv/index.m3u | 同项目（iptv-org/iptv）不同文件 |
| 03 | https://web.utako.moe/jp.m3u | 此前未用 |
| 04 | https://epg.pw/test_channels.m3u | 此前未用 |
| 05 | https://epg.pw/test_channels_hong_kong.m3u | 此前未用 |
| 06 | https://epg.pw/test_channels_macau.m3u | 此前未用 |
| 07 | https://epg.pw/test_channels_taiwan.m3u | 此前未用 |
| 08 | https://iptv-org.github.io/iptv/countries/tw.m3u | 完全相同 |
| 09 | https://epg.pw/test_channels_singapore.m3u | 此前未用 |
| 10 | https://epg.pw/test_channels_malaysia.m3u | 此前未用 |
| 11 | https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8 | 完全相同 |
| 12 | https://iptv-org.github.io/iptv/index.m3u | 同项目（iptv-org/iptv）不同文件 |
| 13 | https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u | 此前未用 |
| 14 | https://raw.githubusercontent.com/BigBigGrandG/IPTV-URL/release/Gather.m3u | 此前未用 |
| 15 | https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u | 此前未用 |
| 16 | https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.txt | 此前未用 |
| 17 | https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.m3u | 此前未用 |
| 18 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u | 完全相同 |
| 19 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u | 同项目（Guovin/iptv-api）不同文件 |
| 20 | https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u | 同项目（Guovin/iptv-api）不同文件 |
| 21 | https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u | 此前未用 |
| 22 | https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv6.m3u | 此前未用 |
| 23 | https://live.zbds.top/tv/iptv4.txt | 此前未用 |
| 24 | https://live.zbds.top/tv/iptv4.m3u | 此前未用 |
| 25 | https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/TV-IPV4.m3u | README 提到过（上游 sources.txt 列的社区列表），但没用过 |
| 26 | https://raw.githubusercontent.com/vamoschuck/TV/main/M3U | 此前未用 |

README 里用过、这次的 26 个地址里没有的：

- https://iptv-org.github.io/iptv/categories/news.m3u
- https://iptv-org.github.io/iptv/countries/hk.m3u
- https://iptv-org.github.io/iptv/countries/uk.m3u
- https://iptv-org.github.io/iptv/countries/cn.m3u
- https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/itv.m3u
- https://iptv-org.github.io/iptv/categories/sports.m3u
- https://iptv-org.github.io/iptv/countries/us.m3u
- https://iptv-org.github.io/iptv/categories/documentary.m3u
- 上游 lizongying/my-tv-0 的内置列表（`playlists/upstream/`，gua64 解码后）
- fengshows 官方 API（凤凰卫视三个台的签名 FLV 地址，app 内部路由用）

### 频道

现有列表是 apk 实际播的那份（`playlists/channels.json` 经 `merge.py` 处理，和 `res/raw/channels.txt` 一致），119 个频道、249 条 uri。凤凰卫视三个台的第一条 uri 是 app 内部的本地转发 `http://127.0.0.1:34567/fh/<id>.flv`，只在 app 里有效，从不测试。

- 按频道名对上 available.m3u：uri 完全相同 99，有重叠 17，完全不同 0，新列表里没有 3。
- 除凤凰的本地路由外 246 条 uri，在这 26 个源里找得到 246 条；今天测过 246 条，通过 240 条。

| 分组 | 频道 | 对比 | uri | 出现在哪些源 | 今天的状态 |
| --- | --- | --- | --- | --- | --- |
| 央视 | CCTV1 综合 | 相同 | http://74.91.26.218:82/live/cctv1hd.m3u8 | 02, 11, 18, 19, 23, 24 | ok |
|  |  |  | http://198.204.228.26/live/cctv1hd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqbv/cctv1hd.m3u8?auth=test20251009 | 18, 19 | ok |
| 央视 | CCTV2 财经 | 相同 | http://74.91.26.218:82/live/cctv2hd.m3u8 | 02, 11 | ok |
|  |  |  | http://198.204.228.26/live/cctv2hd.m3u8 | 18, 19 | ok |
|  |  |  | http://204.12.221.218:8181/3m1080p/cctv2.m3u8 | 18, 19 | ok |
| 央视 | CCTV3 综艺 | 相同 | http://112.30.73.119:229/tsfile/live/0003_2.m3u8?key=txiptv&playlive=0&authid=0 | 18, 19, 23, 24 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv3hd.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/cctv3hd.m3u8 | 18, 19 | ok |
| 央视 | CCTV4 中文国际 | 相同 | http://107.150.60.122/live/cctv4hd.m3u8 | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv4hd.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://173.208.212.130:8181/1080p/cctv4.m3u8 | 18, 19 | ok |
| 央视 | CCTV4 欧洲 | 相同 | https://dash2.antik.sk/live/test_cctv_tizen/playlist.m3u8 | 02, 11 | ok |
| 央视 | CCTV5 体育 | 相同 | http://112.30.73.119:9901/tsfile/live/0005_2.m3u8?key=txiptv&playlive=0&authid=0 | 18, 19, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/cctv5hd.m3u8 | 18, 19 | ok |
|  |  |  | http://173.208.212.130:8181/720p/cctv5.m3u8 | 18, 19 | ok |
| 央视 | CCTV5+ 体育赛事 | 重叠 | https://myip.pdtvhd.com/Sports/streams/CCTV5pul.m3u8 | 02, 18, 19, 23, 24 | http-404 |
|  |  |  | http://223.78.65.165:9901/tsfile/live/0006_1.m3u8?key=txiptv&playlive=1&authid=0 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqbv/cctv5p.m3u8?auth=test20251009 | 18, 19 | ok |
| 央视 | CCTV6 电影 | 相同 | http://198.204.240.250:82/live/cctv6.m3u8 | 18, 19 | ok |
|  |  |  | http://69.30.245.50/live/cctv6.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv6hd.m3u8 | 18, 19 | ok |
| 央视 | CCTV7 国防军事 | 相同 | http://107.150.60.122/live/cctv7hd.m3u8 | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv7hd.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://207.56.13.146:81/cdnlive/cctv7.m3u8 | 18, 19 | ok |
| 央视 | CCTV8 电视剧 | 相同 | http://69.30.245.50/live/cctv8.m3u8 | 18, 19 | ok |
|  |  |  | http://bztv.tvbus.cc:8081/cdnlive/cctv8.m3u8 | 18, 19 | ok |
|  |  |  | http://207.56.13.146:81/cdnlive/cctv8.m3u8 | 18, 19 | ok |
| 央视 | CCTV9 纪录 | 相同 | https://xykt-fix.github.io/Y77.m3u8 | 02, 20 | ok |
|  |  |  | http://192.151.150.154/live/cctv9hd.m3u8 | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/cctv9hd.m3u8 | 18, 19 | ok |
| 央视 | CCTV10 科教 | 相同 | http://38.75.136.137:98/gslb/dsdqbv/cctv10hd.m3u8?auth=test20251009 | 18, 19 | ok |
|  |  |  | http://bztv.tvbus.cc:8081/cdnlive/cctv10.m3u8 | 18, 19 | ok |
|  |  |  | http://204.12.221.218:8181/3m1080p/cctv10.m3u8 | 18, 19 | ok |
| 央视 | CCTV11 戏曲 | 相同 | http://74.91.26.218:82/live/cctv11hd.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/cctv11hd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqbv/cctv11hd.m3u8?auth=test20251009 | 18, 19 | ok |
| 央视 | CCTV12 社会与法 | 相同 | http://74.91.26.218:82/live/cctv12hd.m3u8 | 02, 11, 18, 19, 23, 24 | ok |
|  |  |  | http://204.12.221.218:8181/3m1080p/cctv12.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/cctv12hd.m3u8?auth=testpub | 18, 19 | ok |
| 央视 | CCTV13 新闻 | 相同 | http://74.91.26.218:82/live/cctv13hd.m3u8 | 02, 11, 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cctv13hd | 18, 19 | ok |
|  |  |  | http://bztv.tvbus.cc:8081/cdnlive/cctv13.m3u8 | 18, 19 | ok |
| 央视 | CCTV14 少儿 | 相同 | http://204.12.221.218:8181/3m1080p/cctv14.m3u8 | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/cctv14hd.m3u8 | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv14hd.m3u8 | 02, 11, 18, 19 | ok |
| 央视 | CCTV15 音乐 | 相同 | http://198.204.228.26/live/cctv15hd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cctv15hd | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv15hd.m3u8 | 11, 18, 19 | ok |
| 央视 | CCTV16 奥林匹克 | 相同 | http://38.75.136.137:98/gslb/dsdqpub/cctv16hd.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://207.56.13.146:81/cdnlive/cctv16.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqbv/cctv16hd.m3u8?auth=test20251009 | 18, 19 | ok |
| 央视 | CCTV17 农业农村 | 相同 | http://38.75.136.137:98/gslb/dsdqbv/cctv17hd.m3u8?auth=test20251009 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cctv17hd | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/cctv17hd.m3u8 | 02, 11, 18, 19 | ok |
| 央视 | CGTN | 重叠 | https://amg00405-rakutentv-cgtn-rakuten-i9tar.amagi.tv/master.m3u8 | 02 | ok |
| 凤凰 | 凤凰卫视资讯台 | 重叠 | http://127.0.0.1:34567/fh/7c96b084-60e1-40a9-89c5-682b994fb680.flv | — | app 内部路由，不测 |
|  |  |  | http://r.jdshipin.com/0Rp07 | 18, 20, 21 | ok |
|  |  |  | http://php.jdshipin.com/TVOD/iptv.php?id=fhzx | 18, 20, 21 | ok |
| 凤凰 | 凤凰卫视中文台 | 重叠 | http://127.0.0.1:34567/fh/f7f48462-9b13-485b-8101-7b54716411ec.flv | — | app 内部路由，不测 |
|  |  |  | https://7612-5516-affc-d88b.kylintv.tv/live/pxinhd_iphone.m3u8 | 18, 20 | ok |
| 凤凰 | 凤凰卫视香港台 | 重叠 | http://127.0.0.1:34567/fh/15e02d92-1698-416c-af2f-3e9a872b4d78.flv | — | app 内部路由，不测 |
|  |  |  | http://r.jdshipin.com/NfC0f | 18, 20, 21 | ok |
|  |  |  | http://r.jdshipin.com/yDoTN | 18, 20, 21 | ok |
| 港台新闻 | 無綫新聞台 | 相同 | http://php.jdshipin.com/TVOD/iptv.php?id=wxxw | 18, 20, 21 | ok |
|  |  |  | https://h5cdn3.kylintv.tv/live/tvbnews_iphone.m3u8 | 18, 19 | ok |
|  |  |  | http://r.jdshipin.com/CkuBd | 18, 20, 21 | ok |
| 港台新闻 | 翡翠台 | 相同 | http://r.jdshipin.com/GeWKr | 18, 20, 21 | ok |
|  |  |  | http://103.172.187.30:12000/stream/mytv/null-1/master.m3u8 | 02 | ok |
|  |  |  | http://r.jdshipin.com/n90gt | 14, 18, 20, 21 | ok |
| 港台新闻 | ViuTV | 相同 | http://php.jdshipin.com/TVOD/iptv.php?id=viutv2 | 18, 20, 21 | ok |
|  |  |  | http://r.jdshipin.com/TcKr2 | 18, 20, 21 | ok |
|  |  |  | http://r.jdshipin.com/vSJvl | 14, 18, 20, 21 | ok |
| 港台新闻 | RTHK 31 | 重叠 | https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8 | 02, 11 | ok |
| 港台新闻 | TVBS | 相同 | http://38.64.72.148/hls/modn/list/4005/playlist.m3u8 | 02, 08 | ok |
| 国际新闻 | BBC News | 相同 | http://23.237.104.106:8080/USA_BBC_NEWS/index.m3u8 | 02 | ok |
|  |  |  | http://46.32.176.50/bbcworld/index.m3u8 | 02 | ok |
|  |  |  | http://138.121.15.230:9002/BBC-NEWS/index.m3u8 | 02 | ok |
| 国际新闻 | Al Jazeera English | 相同 | https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8 | 02, 11 | ok |
|  |  |  | http://stream.mcquack.net/131/index.m3u8 | 02 | ok |
|  |  |  | https://live-hls-web-aja2-gcp.thehlive.com/AJA2/index.m3u8 | 02, 11 | ok |
| 国际新闻 | Sky News | 重叠 | https://xemzi.short.gy/1000018 | 02 | ok |
| 国际新闻 | France 24 English | 重叠 | http://nmk.ioapk.com:5050/4gtv-live146/index.m3u8 | 02 | http-500 |
|  |  |  | https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8 | 02 | ok |
| 国际新闻 | DW English | 相同 | https://amg01644-amg01644c1-amgplt0343.playout.now3.amagi.tv/ts-eu-w1-n2/playlist/amg01644-amg01644c1-amgplt0343/playlist.m3u8 | 02 | ok |
|  |  |  | https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/index.m3u8 | 11 | ok |
| 国际新闻 | NHK World-Japan | 重叠 | https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8 | 02 | ok |
|  |  |  | http://nmk.ioapk.com:5050/4gtv-live168/index.m3u8 | 02 | http-500 |
| 国际新闻 | Euronews English | 重叠 | https://cdn-euronews.akamaized.net/live/eds/euronews-pl/26382/index.m3u8 | 02 | ok |
|  |  |  | https://dash4.antik.sk/live/test_euronews/playlist.m3u8 | 02 | ok |
| 国际新闻 | Bloomberg TV | 相同 | https://bloomberg.com/media-manifest/streams/eu.m3u8 | 02, 11 | ok |
|  |  |  | https://bloomberg.com/media-manifest/streams/phoenix-us.m3u8 | 11 | ok |
|  |  |  | https://bloomberg.com/media-manifest/streams/us.m3u8 | 11 | ok |
| 国际新闻 | CNBC | 相同 | https://amg01079-nbcuuk-amg01079c2-samsung-gb-1258.playouts.now.amagi.tv/playlist.m3u8 | 02 | ok |
| 国际新闻 | CNA | 重叠 | https://d2e1asnsl7br7b.cloudfront.net/7782e205e72f43aeb4a48ec97f66ebbe/index.m3u8 | 02, 26 | ok |
|  |  |  | https://mumt05.tangotv.in/87NeALx2CNA/index.m3u8 | 02 | ok |
|  |  |  | https://live1.mediadesk.al/cnatvlive.m3u8 | 02, 11 | ok |
| 国际新闻 | Arirang | 重叠 | https://amdlive-ch02-ctnd-com.akamaized.net/arirang_2ch/smil:arirang_2ch.smil/playlist.m3u8 | 02 | ok |
|  |  |  | http://amdlive-ch01.ctnd.com.edgesuite.net/arirang_1ch/smil:arirang_1ch.smil/playlist.m3u8 | 02, 26 | ok |
|  |  |  | http://amdlive.ctnd.com.edgesuite.net/arirang_1ch/smil:arirang_1ch.smil/chunklist_b2256000_sleng.m3u8 | 11 | ok |
| 国际新闻 | TRT World | 相同 | https://tv-trtworld.medya.trt.com.tr/master.m3u8 | 02, 11 | ok |
|  |  |  | https://dash2.antik.sk/live/test_trt_world_atktv/playlist.m3u8 | 02, 11 | ok |
| 国际新闻 | ABC News Australia | 相同 | https://c.mjh.nz/abc-news.m3u8 | 11 | ok |
|  |  |  | https://abc-news-dmd-streams-1.akamaized.net/out/v1/701126012d044971b3fa89406a440133/index.m3u8 | 02 | ok |
| 国际新闻 | CBS News | 重叠 | https://dai.google.com/linear/hls/event/Sid4xiTQTkCT1SLu6rjUSQ/master.m3u8 | 11 | ok |
| 国际新闻 | NBC News Now | 相同 | https://d1si3n1st4nkgb.cloudfront.net/10502/88896001/hls/master.m3u8?ads.xumo_channelId=88896001 | 02, 11 | ok |
|  |  |  | https://d1bl6tskrpq9ze.cloudfront.net/hls/master.m3u8?ads.xumo_channelId=99984003 | 11 | ok |
| 国际新闻 | Fox News | 相同 | http://138.121.15.230:9002/FOX-NEWS/index.m3u8 | 02 | ok |
| 国际新闻 | Reuters TV | 相同 | https://amg00453-reuters-amg00453c1-rakuten-uk-2110.playouts.now.amagi.tv/playlist/amg00453-reuters-reuters-rakutenuk/playlist.m3u8 | 02, 11 | ok |
| 体育 | 广东体育 | 相同 | http://php.jdshipin.com/PLTV/iptv.php?id=gdty | 18, 20 | ok |
|  |  |  | http://php.jdshipin.com/TVOD/iptv.php?id=gdty | 18, 20 | ok |
|  |  |  | https://epg.pw/stream/7b470f9fc5c305db0c8622117b7b25ca00eb35ba3e93e865cf0ff9df5c736681.m3u8 | 18, 20 | ok |
| 体育 | 风云足球 | 重叠 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=fyzq | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/fyzq.m3u8?auth=testpub | 02, 18, 19 | ok |
| 体育 | 江苏体育 | 相同 | https://live.chinacert.cftest5.cn/cnmg/live/626064707 | 18, 20 | ok |
| 体育 | 天津体育 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=tjtv5 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/tjtv5.m3u8?auth=testpub | 18, 19 | ok |
| 体育 | ESPN | 相同 | http://181.78.197.59:8000/play/a07z/index.m3u8 | 02 | ok-small |
| 体育 | ESPN 4 | 相同 | http://181.78.197.59:8000/play/a07n/index.m3u8 | 02 | ok |
| 体育 | beIN SPORTS XTRA | 相同 | https://bein-xtra-bein.amagi.tv/playlist.m3u8 | 02 | ok |
| 体育 | NBA TV | 相同 | https://cdn1.ayitistream.com/NBATV/index.m3u8 | 02 | ok |
| 体育 | Tennis Channel | 相同 | https://cdn-ue1-prod.tsv2.amagi.tv/linear/amg01444-tennischannelth-tennischannelnl-samsungnl/playlist.m3u8 | 02 | ok |
| 体育 | Golf Channel | 相同 | https://dash4.antik.sk/live/test_golf_channel/playlist.m3u8 | 02 | ok |
| 体育 | Fox Sports 1 | 相同 | http://85.237.89.160:9590/usa-s/FOX-SPORTS-1/index.m3u8 | 02 | ok |
| 体育 | Setanta Sports | 新列表里没有 | http://sewv654wfcsdwfi87fwvgbngh.siauliairsavlt.pw/iptv/8P7MBSH7RRPL53/20074/index.m3u8 | 02 | no-segment |
| 体育 | MLB Strike Zone | 相同 | http://23.237.104.106:8080/USA_MLB_STRIKE_ZONE/index.m3u8 | 02 | ok |
| 体育 | NHL Network | 相同 | https://nhl-firetv.amagi.tv/playlist.m3u8 | 02 | ok |
| 体育 | Star Sports Select 2 | 相同 | http://tvsen7.aynascope.net/ssport2hd/index.m3u8 | 02 | ok |
| 体育 | Star Sports 2 | 新列表里没有 | http://tvsen5.aynascope.net/cXPB2LKkErN9/index.m3u8 | 02 | seg-http-404 |
| 体育 | FIFA+ United States | 相同 | https://d2w9q46ikgrcwx.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-of5cbk3sav3w5/v1/sysdata_s_p_a_fifa_7/samsungheadend_us/latest/main/hls/playlist.m3u8 | 02 | ok |
| 体育 | TSN The Ocho | 相同 | https://d3pnbvng3bx2nj.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-rds8g35qfqrnv/TSN_The_Ocho.m3u8 | 02 | ok |
| 体育 | ESPN8 The Ocho | 相同 | https://d3b6q2ou5kp8ke.cloudfront.net/ESPNTheOcho.m3u8 | 02 | ok |
| 体育 | Women's Sports Network | 相同 | https://d39accvx65hq9o.cloudfront.net/Womens_Sports_Network.m3u8 | 02 | ok |
| 体育 | PGA Tour | 相同 | https://d11k1mnrgfposz.cloudfront.net/playlist.m3u8 | 02 | ok |
| 体育 | MSG | 相同 | http://23.237.104.106:8080/USA_MSG/index.m3u8 | 02 | ok |
| 体育 | DD Sports | 相同 | https://d3qs3d2rkhfqrt.cloudfront.net/out/v1/b17adfe543354fdd8d189b110617cddd/index.m3u8 | 02 | ok |
| 体育 | FIFA+ Women | 相同 | https://cffda8ff.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/U2Ftc3VuZy1nYl9GSUZBUGx1c3dvbWVuX0hMUw/playlist.m3u8 | 02 | ok |
| 体育 | FITE 24/7 | 相同 | https://d3d85c7qkywguj.cloudfront.net/scheduler/scheduleMaster/263.m3u8 | 02 | ok |
| 体育 | Sky Racing 1 | 相同 | https://636ffd31f0e12.streamlock.net/RacingStream1/RacingStream1/playlist.m3u8 | 02 | ok |
| 体育 | NBC Sports NOW | 相同 | https://d4whmvwm0rdvi.cloudfront.net/10007/99993008/hls/master.m3u8?ads.xumo_channelId=99993008 | 02 | ok |
| 卫视 | 湖南卫视 | 相同 | https://txmov2.a.kwimgs.com/bs3/video-hls/5199687338554291078_hlsb.m3u8 | 18, 19, 23 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=hnwshd | 18, 19 | ok |
|  |  |  | http://74.91.26.218:82/live/hnwshd.m3u8 | 18, 19 | ok |
| 卫视 | 浙江卫视 | 相同 | http://ali-m-l.cztv.com/channels/lantian/channel01/1080p.m3u8 | 18, 19 | ok |
|  |  |  | https://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8 | 18, 19, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/zjwshd.m3u8 | 18, 19 | ok |
| 卫视 | 江苏卫视 | 相同 | http://38.75.136.137:98/gslb/dsdqbv/jswshd.m3u8?auth=test20251009 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=jswshd | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/jswshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 东方卫视 | 相同 | https://txmov2.a.kwimgs.com/bs3/video-hls/5219953535631090825_hlsb.m3u8 | 18, 19, 23, 24 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=dfwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/dfwshd.m3u8 | 18, 19 | ok |
| 卫视 | 北京卫视 | 相同 | http://38.75.136.137:98/gslb/dsdqbv/bjwshd.m3u8?auth=test20251009 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=bjwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/bjwshd.m3u8 | 18, 19 | ok |
| 卫视 | 安徽卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=ahwshd | 18, 19 | ok |
|  |  |  | http://204.12.221.218:8181/3m1080p/ahws.m3u8 | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/ahwshd.m3u8 | 18, 19 | ok |
| 卫视 | 山东卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=sdwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/sdwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/sdwshd.m3u8 | 18, 19 | ok |
| 卫视 | 天津卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=tjwshd | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/tjwshd.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/tjwshd.m3u8 | 18, 19 | ok |
| 卫视 | 深圳卫视 | 相同 | http://38.64.72.148:80/hls/modn/list/4007/playlist.m3u8 | 18, 19, 23, 24 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/szwshd.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/szwshd.m3u8 | 18, 19 | ok |
| 卫视 | 广东卫视 | 相同 | https://txmov2.a.kwimgs.com/upic/2023/01/26/09/BMjAyMzAxMjYwOTE3NDVfNzM5MzQzNzIyXzk0NjI1OTUwNTA3XzBfMw==_b_B81ddda927d33445d544befd008e60109.mp4 | 18, 19, 23, 24 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=gdwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/gdwshd.m3u8 | 18, 19 | ok |
| 卫视 | 湖北卫视 | 重叠 | http://107.150.60.122/live/hbwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=hbwshd | 18, 19 | ok |
| 卫视 | 四川卫视 | 相同 | http://107.150.60.122/live/scwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=scwshd | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/scwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 重庆卫视 | 重叠 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cqwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/cqwshd.m3u8 | 18, 19 | ok |
| 卫视 | 江西卫视 | 相同 | http://112.27.5.218:9901/tsfile/live/faacts/0138_1.m3u8?key=txiptv&playlive=1&authid=0 | 18, 19, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/jxwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/jxwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 河南卫视 | 相同 | http://111.59.139.82:11888/tsfile/live/0139_1.m3u8?key=txiptv&playlive=1&authid=0 | 18, 19, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/hawshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/hawshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 河北卫视 | 相同 | https://event.pull.hebtv.com/live/live101.m3u8 | 02, 18, 20 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=hewshd | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/hewshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 辽宁卫视 | 相同 | http://204.12.221.218:8181/3m1080p/lnws.m3u8 | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/lnwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/lnwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 黑龙江卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=hljwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/hljwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/hljwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 吉林卫视 | 相同 | http://221.7.175.154:8445/tsfile/live/1014_1.m3u8?key=txiptv&playlive=1&authid=0 | 18, 19, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/jlwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/jlwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 东南卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=dnwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/dnwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/dnwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 贵州卫视 | 相同 | http://204.12.221.218:8181/3m1080p/gzws.m3u8 | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/gzwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/gzwshd.m3u8?auth=testpub | 18, 19 | ok |
| 卫视 | 云南卫视 | 相同 | http://192.151.150.154/live/ynwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/ynwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=ynwshd | 18, 19 | ok |
| 卫视 | 广西卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=gxwshd | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/gxwshd.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/gxwshd.m3u8 | 18, 19 | ok |
| 卫视 | 陕西卫视 | 相同 | http://192.151.150.154/live/snwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=snwshd | 18, 19 | ok |
|  |  |  | http://107.150.60.122/live/snwshd.m3u8 | 18, 19 | ok |
| 卫视 | 山西卫视 | 相同 | http://107.150.60.122/live/sxwshd.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=sxwshd | 18, 19 | ok |
|  |  |  | http://204.12.221.218:8181/3m1080p/sxws.m3u8 | 18, 19 | ok |
| 卫视 | 甘肃卫视 | 重叠 | http://38.75.136.137:98/gslb/dsdqpub/gswshd.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=gswshd | 18, 19 | ok |
| 卫视 | 宁夏卫视 | 相同 | http://107.150.60.122/live/nxws.m3u8 | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/nxws.m3u8 | 18, 19 | ok |
|  |  |  | https://live.264788.xyz/channel/ningxiaweishi?streamid=e1236348f815c36a0429357e5b5c5f10&livekey=01WgOR41rriMmMkzNsd0UoaxJRwetZdxIvtVk | 18, 19, 23 | ok |
| 卫视 | 青海卫视 | 相同 | https://hls-qhmh.lanzhousobey.cn/qhmh/mhds.m3u8 | 18, 20, 23, 24 | ok |
|  |  |  | http://107.150.60.122/live/qhws.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=qhws | 18, 19 | ok |
| 卫视 | 新疆卫视 | 相同 | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=xjws | 18, 19 | ok |
|  |  |  | http://38.75.136.137:98/gslb/dsdqpub/xjws.m3u8?auth=testpub | 18, 19 | ok |
|  |  |  | http://198.204.228.26/live/xjws.m3u8 | 18, 19 | ok |
| 卫视 | 西藏卫视 | 相同 | http://107.150.60.122/live/xzws.m3u8 | 18, 19 | ok |
|  |  |  | http://63.141.230.178:82/gslb/zbdq5.m3u8?id=xzws | 18, 19 | ok |
|  |  |  | https://live.264788.xyz/channel/xizangweishi?streamid=4b4e8ea919f1cfd5e43deed1d1675251&livekey=01WgOR41rriMmMkzNsd0UoaxJRwetZdxIvtVk | 18, 19, 23 | ok |
| 纪录片 | 之江纪录 | 相同 | http://ali-m-l.cztv.com/channels/lantian/channel012/1080p.m3u8 | 18, 19, 23 | ok |
|  |  |  | https://ali-m-l.cztv.com/channels/lantian/channel012/1080p.m3u8 | 21, 22, 23, 24 | ok |
|  |  |  | https://ali-m-l.cztv.com/channels/lantian/channel12/720p.m3u8 | 18, 19, 23 | ok |
| 纪录片 | National Geographic Wild HD East | 相同 | http://198.58.104.90:8989/natgeowild/index.m3u8 | 02 | ok |
| 纪录片 | National Geographic HD East | 相同 | http://198.58.104.90:8989/natgeo/index.m3u8 | 02 | ok |
| 纪录片 | BBC Earth | 相同 | https://amg00793-amg00793c6-xumo-us-2669.playouts.now.amagi.tv/BBCStudios-BBCEarthA-hls/playlist.m3u8 | 02 | ok |
| 纪录片 | True History | 相同 | https://linear-188.frequency.stream/dist/glewedtv/188/hls/master/playlist.m3u8 | 02 | ok |
| 纪录片 | History Asia | 相同 | https://freem3u.xyz/api/live/play.m3u8?vid=9856 | 02 | ok |
| 纪录片 | History Hit | 相同 | https://lds-timeline-rakuten.amagi.tv/playlist.m3u8 | 02 | ok |
| 纪录片 | Pluto TV History | 相同 | https://jmp2.uk/plu-5a4d35dfa5c02e717a234f86.m3u8 | 02 | ok |
| 纪录片 | TVS Hollywood History | 相同 | https://rpn.bozztv.com/gusa/gusa-tvshollywoohistory/index.m3u8 | 02 | ok |
| 纪录片 | Smithsonian Channel Pluto TV | 相同 | https://jmp2.uk/plu-6298bd10d88ef000073f16b7.m3u8 | 02 | ok |
|  |  |  | https://jmp2.uk/plu-63a084934734f30007457b2c.m3u8 | 02 | ok |
| 纪录片 | Smithsonian Channel Selects | 相同 | https://jmp2.uk/plu-5f21ea08007a49000762d349.m3u8 | 02 | ok |
| 纪录片 | Documentary+ | 相同 | https://ef79b15c8c7c46c7a9de9d33001dbd07.mediatailor.us-west-2.amazonaws.com/v1/master/ba62fe743df0fe93366eba3a257d792884136c7f/LINEAR-859-DOCUMENTARYPLUS-DOCUMENTARYPLUS/mt/documentaryplus/859/hls/master/playlist.m3u8 | 02 | ok |
| 纪录片 | Documentary+ International | 相同 | https://1d153317c8db4250b3789601274e2402.mediatailor.us-west-2.amazonaws.com/v1/master/ba62fe743df0fe93366eba3a257d792884136c7f/LINEAR-887-DOCUMENTARYINTERNATIONAL-DOCUMENTARYPLUS/mt/documentaryplus/887/hls/master/playlist.m3u8 | 02 | ok |
| 纪录片 | DocuBay TV | 相同 | https://cc-mgr91yrk4pehy.akamaized.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-mgr91yrk4pehy/playlist.m3u8 | 02 | ok |
| 港台综艺 | 星河頻道 | 相同 | http://r.jdshipin.com/sXuuD | 18, 20, 21 | ok |
|  |  |  | http://r.jdshipin.com/Voac4 | 18, 20, 21 | ok |
|  |  |  | http://php.jdshipin.com/TVOD/iptv.php?id=xinghe | 18, 20, 21 | ok |
| 港台综艺 | 東森洋片台 | 相同 | http://31.43.191.125:8080/vip6821768502490/6c17bae55394/34904 | 18, 19, 23, 24 | ok |
| 港台综艺 | 龍祥時代電影台 | 新列表里没有 | http://31.43.191.125:8080/vip6821768502490/6c17bae55394/34825 | 18, 19 | http-403 |
