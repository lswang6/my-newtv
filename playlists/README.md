# playlists

apk 内置频道列表，以及生成它的那次测试留下的全部原始记录。按类型分三组：

- 根目录 —— 内置列表的数据与测试记录：`channels.json`、`current.m3u`、`candidates.csv`、`report.md`
  （`tools/probe/extract_test.py` 和 `tools/build/` 下的脚本生成）。
- `upstream/` —— 上游原始列表。
- `scan/` —— 批量扫描结果（`tools/probe/scan_sources.py` 生成）。

## 文件

- `channels.json` — 测试通过的频道列表，119 个频道。这是 apk 内置源的真身：`tools/build/merge.py`
  把它编码成 `app/src/main/res/raw/channels.txt`。每个频道最多保留 3 个 uri，排序是
  ffprobe 认出 h264 的优先，其次按分片延迟从小到大。
- `current.m3u` — 上面这份列表的标准 m3u 形式，方便丢进 VLC、PotPlayer 之类的播放器里看。
  由 `tools/build/export_m3u.py` 生成，内容和 apk 实际播的完全一致（包括凤凰的本地转发地址）。
- `candidates.csv` — 所有被匹配到并测试过的候选 url，873 行，带每条的判定结果。
  列的含义见 `tools/README.md`。没进最终列表的频道为什么没进，答案在这里。
- `report.md` — 那次构建的测试报告：每个分组匹配到多少、通过多少、哪些频道找到了却连不上、
  哪些源列表里根本没有，以及过程中踩到的坑。
- `upstream/` — 上游 my-tv-0 内置列表的解码副本，`extract_test.py` 会把它们和网上下载的
  playlist 一起当作候选来源。
- `scan/` — `tools/probe/scan_sources.py` 批量扫描 26 个公开列表的输出，只作参考，不影响 apk 内置列表。
  2026-09-17 在 Mac 上测的，走的也是下面那个韩国出口，没有在电视上测。
  - `merged.m3u` — 能播的频道全部列出，8822 个频道、10029 条 uri，同名条目连在一起；排序规则见 `tools/README.md`。
  - `merged-lite.m3u` — 同上的精简版，349 个频道、836 条 uri。apk 内置频道全部保留；海外·*、国际新闻、体育、纪录片只留
    `tools/probe/scan_sources.py` 里 `PICKS` 按名字挑的；地方只留省级和主要城市的电视台，不要广播、景区直播和点播；其余小分组
    去掉重复、宗教和购物频道；不要 4K/8K 副本。
  - `available.m3u` — 和 `merged.m3u` 同样的频道，每个最多 3 条 uri，共 9750 条。
  - `channels.csv` — 每个频道一行：分组、国家、uri 数、合并进来的原名、来源等。
  - `results.csv` — 每条 url 一行，带判定结果，列和 `candidates.csv` 类似，多一列 `sources`。
  - `report.md` — 扫描报告：各源通过率、状态分布、合并统计，以及和 apk 内置列表逐频道的对比。

## 免责声明

这份列表截至 2026-09-16，而且只从一个网络位置测过：路由器代理的出口在韩国（Oracle Cloud
节点），只有 IPv4。同一条 url 换个地区、换个网络、换个时间，结果可能完全不同 —— 这里标着
能播的，你那边未必能播；这里标着不能播的（尤其是港台那些 403 的），在香港或台湾的线路上
大概率是好的。真要依赖，先自己重测一遍。

凤凰卫视的三个频道用的是 app 内部的本地转发地址 `http://127.0.0.1:34567/fh/<id>.flv`，
只有在 app 里才有效，别的播放器打不开。`current.m3u` 里每个凤凰频道前面注明了原始的
fengshows `live_id`，想自己解出真实地址的话：

    GET https://m.fengshows.com/api/v3/hub/live/auth-url?live_id=<id>&live_qa=HD

请求头带一个空的 `token`，返回的就是签名过的 FLV 播放地址。

## 重新生成

    python3 tools/probe/extract_test.py --serial <tv-ip>:5555   # 重测，刷新本目录三个文件
    python3 tools/build/merge.py                                # 写回 app/.../raw/channels.txt
    python3 tools/build/export_m3u.py                           # 刷新 current.m3u
    ./gradlew assembleDebug                                     # 重新打包（debug 签名，仓库没配 release 签名）

只想改列表不想重测的话，直接手改 `channels.json` 再跑后面三步就行。
细节和前置条件见 `tools/README.md`。
