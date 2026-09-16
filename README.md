# 我的电视（newmytv）

安卓电视直播播放器。fork 自 [lizongying/my-tv-0](https://github.com/lizongying/my-tv-0)（commit `19ab99c`，tag `v1.3.9.8`），主要改动是把内置频道列表换成了一份实测可播的列表，并为凤凰卫视加了一条本地取流路由。

## 简介

上游 my-tv-0 是一个纯 m3u/txt 源播放器：Media3/ExoPlayer 播放，遥控器操作，内置一个 NanoHTTPD 本地服务（端口 34567）用于网页配置自定义源。本 fork 保留了这些能力，只替换了内置列表并做了少量代码改动，装完即可播，不需要任何配置。

- 应用名：我的电视，applicationId `com.lizongying.newmytv`
- minSdk 21，compileSdk 35
- 与上游的代码差异很小（详见[与上游的差异](#与上游的差异)），主要是内置频道、凤凰路由和设置页、去上游联网/上报、简体化

## 功能与分组

- 开箱即用：内置 121 个实测频道，安装后直接播放
- 遥控器操作：上下键换台、数字键输入频道号、OK 键打开频道列表
- 仍支持上游的全部源格式（m3u / txt / json）、按频道自定义 header、多 URI 回退、HLS/DASH/RTSP/RTMP
- 本地网页配置页 `http://<电视IP>:34567`，可导入自己的 m3u/txt（上游功能）

内置列表分组（共 121 个）：

| 分组 | 频道数 |
| --- | --- |
| 央视 | 20 |
| 凤凰 | 3 |
| 港台新闻 | 5 |
| 国际新闻 | 17 |
| 体育 | 29 |
| 卫视 | 30 |
| 纪录片 | 14 |
| 港台综艺 | 3 |

## 下载安装

apk 见 [GitHub Releases](https://github.com/lswang6/my-newtv/releases)。

```shell
adb connect <电视IP>:5555
adb install <下载的 apk 文件>
```

注意：仓库没有配置 release 签名，Releases 里的 apk 是 **debug 签名**的。这意味着不同机器构建出的 apk 签名不同，升级时如果提示签名冲突，先卸载旧版再装；或者始终使用同一台机器/同一个 keystore 构建。

## 使用

- 遥控器上/下键：切换上一个/下一个频道
- 数字键：直接输入频道号（最多 3 位）
- OK 键 / 菜单键：打开频道列表
- 设置：通过屏幕上的菜单进入（时钟浮层默认关闭，可在设置里打开）
- 自定义源：浏览器打开 `http://<电视IP>:34567`，粘贴或上传自己的 m3u/txt

## 内置直播源说明

内置列表的可读版本在 [`playlists/current.m3u`](playlists/current.m3u)（和打进 apk 的 `playlists/channels.json` 是同一份，只是导出成 m3u）。

**请注意：**

- 这是 **2026-09-16 打包时**的列表。
- 它**只在一个网络出口测过**（见[测试结果与平台情况](#测试结果与平台情况)）。不同地区、不同网络环境、不同时间，可用性都不一样。
- 直播源会失效。列表过期后请自行用 [`tools/`](tools/) 里的脚本重新测试、重新生成。
- `current.m3u` 里的**凤凰卫视 3 条是 app 内部路由**（`http://127.0.0.1:34567/fh/<live_id>.flv`），只有在本 app 内才有效，复制到别的播放器里不能用。

## 直播源来源

所有候选源都来自公开的互联网列表：

| 名称 | 地址 | 贡献了什么 |
| --- | --- | --- |
| iptv-org/iptv | `https://iptv-org.github.io/iptv/categories/news.m3u`、`/categories/sports.m3u`、`/categories/documentary.m3u`、`/countries/hk.m3u`、`/countries/tw.m3u`、`/countries/uk.m3u`、`/countries/us.m3u`、`/countries/cn.m3u` | 国际新闻、体育、纪录片、港台频道的主力来源 |
| Free-TV/IPTV | `https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8` | 质量优先的补充源，国际新闻/体育 |
| Guovin/iptv-api | `https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u` | 聚合的国内列表，CCTV / 卫视 / 凤凰候选 |
| fanmingming/live | `https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/itv.m3u` | CCTV / 卫视候选 |
| lizongying/my-tv-0 内置列表 | `app/src/main/res/raw/channels.txt`、`mobile.txt`、`sources.txt`（gua64 解码后） | 中国移动 CDN 的 CCTV 源；`sources.txt` 还列出了 29 个社区列表（joevess/IPTV、YueChan/Live、vbskycn/iptv、zbefine/iptv、BurningC4/Chinese-IPTV 等） |
| fengshows 官方 API | `https://m.fengshows.com/api/v3/hub/live/auth-url?live_id=<id>&live_qa=HD` | 凤凰卫视资讯台/中文台/香港台的签名流地址 |

几点说明：

- iptv-org 的**网站频道数据库和它的 playlist 不是一回事**，网站上能查到的频道不一定在 m3u 里；CNN 在 iptv-org 的 blocklist 上，拿不到。
- Free-TV 里的 CNN 条目指向的是 `cnn_slate` 待机卡片（一张静止画面），已排除。
- fanmingming 的 `ipv6.m3u` 没用，测试用的电视没有 IPv6 路由。
- my-tv-0 内置的中国移动 CDN 源基本都是 IPv6-only，在这台电视上全是死链。
- 实际能播的 CCTV 源**全部来自 Guovin / iptv-org 列表里的境外镜像主机**；所有 China Mobile / cmvideo CDN 的地址在我们的出口上不是超时就是 403。
- [`https://www.fengshows.com/live`](https://www.fengshows.com/live) 是凤凰官方网页播放器，用来确认某个镜像放的是不是对的台。

## 测试方法与步骤

完整细节在 [`tools/README.md`](tools/README.md) 和 [`playlists/report.md`](playlists/report.md)，这里只说流程。

### 1. 抓取并测试候选源

```shell
python3 tools/extract_test.py --serial <tv-ip>:5555   # 在电视上测（走 adb）
python3 tools/extract_test.py --mac                   # 在 Mac 上测（同一个网络出口）
```

可达性判定规则：

- 在电视上用静态编译的 curl（stunnel/static-curl）直接测，因为 adb shell 里普通 DNS 不工作，改用 DoH 查 `223.5.5.5`，只走 IPv4（`-4`）
- HLS：master → variant → 第一个分片，12 秒内拿到 ≥50 KB 才算通
- 非 HLS：ffprobe 必须能识别出编码
- 路由器注入的 "content is not available in your area" 是 41 字节的页面，被上面的大小规则挡掉
- 编码用 ffprobe 识别（放宽扩展名判断）
- 排除 youtube / github 域名
- 每个频道最多保留 3 个 uri，排序 h264 → 其他 → 按延迟
- 结果有缓存，重复跑不会重测

体育 / 卫视 / 纪录片 / 港台综艺 这几组是在 Mac 上测的（出口相同）。

### 2. 合并生成列表并重新构建

```shell
python3 tools/merge.py                 # 读取 playlists/channels.json，加入凤凰卫视本地路由，gua64 编码写入 app/src/main/res/raw/channels.txt
JAVA_HOME=<jdk21> ANDROID_HOME=<sdk> ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`tools/gua64.py` 是 gua64 编解码库和命令行工具，`tools/export_m3u.py` 把同一份列表导出为 `playlists/current.m3u`。各脚本确切的输入输出和参数见 [`tools/README.md`](tools/README.md)。

### 3. 在电视上验证真实播放

```shell
python3 tools/verify_playback.py --serial <tv-ip>:5555 --only 1,21,29   # 频道序号，逗号分隔；--count N 则顺序测前 N 台
```

这个脚本通过 adb 驱动遥控器切台，再从 logcat 里读 app 打的 `<title> playing` / `播放错误` / `retry`。注意 app 在切台的瞬间就会乐观地打一条 `playing`，所以脚本是以 `嘗試播放` 这一对日志为锚点判定的。

抽测结果：前 45 个频道里抽了 13 个，13/13 播放成功（CCTV1/4/13、凤凰 ×3（走本地路由）、無綫新聞、翡翠台、BBC、Al Jazeera、France 24、Bloomberg、CNA）。此外用户另行确认了 HEVC 条目（ESPN8 The Ocho）和 MPEG-2 条目（NatGeo ×2）在这台电视上能播。

## 测试结果与平台情况

测试平台：

- 电视 "Smart TV Pro"，Android 9（API 28），armeabi-v7a，MStar 芯片，**没有 IPv6 路由**
- adb 走 Wi-Fi（`<tv-ip>:5555`）
- 家里路由器挂了代理，所以**电视的出口 = Mac 的出口 = 一个位于韩国的 Oracle Cloud 节点**

所以下面这些结果都是**这个出口**的结论，换个网络会不一样：

- 中国移动 / 中国电信 CDN 不可达
- 港台地区限播频道 403：HOY、TVBS新聞、東森新聞、華視、RTHK 32
- CNN 拿不到（只有待机卡片）
- Now / 有線 / 中天 / 年代 在所有源里都没有
- `hls-gateway.vpstv.net`（J2 / 明珠 / 三立 / 東森綜合）403
- 求索 / 纪实 系列仅限中国大陆

筛选结果（数据来自 `playlists/report.md`）：

| 分组 | 候选 | 可播 | 最终入选 |
| --- | --- | --- | --- |
| 央视 | 173 | — | 20 |
| 凤凰 | 16 | — | 3 |
| 港台新闻 | 37 | — | 5 |
| 国际新闻 | 72 | — | 17 |
| 体育 | 142 | 68 | 30（截断） |
| 卫视 | 38 | 35 | 30（截断） |
| 纪录片 | 32 | — | 14 |
| 港台综艺 | 14 | — | 3 |

港台新闻另有 5 个频道只在 YouTube 页面上找得到，已排除。源测试本身有 ±2 个频道的跑次间波动。

## 参考项目

**[lizongying/my-tv](https://github.com/lizongying/my-tv)** —— 最早的"我的电视"。Kotlin 源码是公开的，但 CCTV 播放要用一个预编译的闭源 `libnative.so` 给央视频（yangshipin）的 API 请求签名（`encrypt`/`hash`/`hash2`，仓库里的 `nothing.c` 只是个占位），token 还要经过作者自己的中转 `lyrics.run`，所以这条路**不可复现**。最后一次提交 2024-05-31。我们从它那里借用的是 fengshows API 的调用方式和凤凰三个台的 `live_id`。

**[lizongying/my-tv-0](https://github.com/lizongying/my-tv-0)** —— 本项目 fork 的对象，开放的 m3u/txt 源播放器：NanoHTTPD 本地服务（34567）带网页配置、gua64 编码的内置列表、按频道自定义 header、多 URI 回退、HLS/DASH/RTSP/RTMP。整体沿用。

**[zwc456baby/my-tv-webview](https://github.com/zwc456baby/my-tv-webview)** —— README 宣称有一个 WebView（GeckoView，Firefox 144）播放引擎，靠 JS 注入和自动点击播放网页源。但公开源码（`600209b`，2026-09-06）里**并没有这个引擎**：它就是 my-tv-0 的一份拷贝，外加一份配置文档（`source/README.md`、`source/cfg/*.json`）和一个闭源 apk；它内置的 CCTV 列表 25 条里有 24 条是 IPv6-only。代码不可用，那份配置文档只能当规格说明看。

**iptv-org/iptv、Free-TV/IPTV、Guovin/iptv-api、fanmingming/live** —— 直播源列表，见[直播源来源](#直播源来源)。

## 仓库结构

```
app/         Android 源码（fork 自上游）
tools/       extract_test.py  抓取并测试候选源
             gua64.py         res/raw/channels.txt 的 gua64 编解码
             merge.py         channels.json + 凤凰路由 → 编码写入 res/raw/channels.txt
             export_m3u.py    导出 current.m3u
             verify_playback.py  通过 adb + logcat 验证真实播放
             README.md
playlists/   channels.json    打进 apk 的那份实测列表
             current.m3u      同一份列表导出成 m3u（凤凰是 app 内部路由）
             candidates.csv   每个测过的 URL 及其判定结果
             report.md        测试报告
             README.md
README.md
LICENSE
```

## 构建

```shell
JAVA_HOME=<jdk21> ANDROID_HOME=<android-sdk> ./gradlew assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
```

- 需要 JDK 21 和 Android SDK（compileSdk 35）
- `versionName` 取自 `git describe --tags`，所以构建时仓库里得有 tag
- 没有配置 release 签名，只能出 debug 签名的包

安装：

```shell
adb connect <电视IP>:5555
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## 更新记录

### v2.1.2

- 修复：频道列表打开后按上下键焦点不动，按 OK 只会重选正在播放的频道，无法换台。原因是 v2.1.0 让方向键在菜单打开时也向系统报告"已处理"，系统的焦点导航因此不再执行。现在方向键只在真正换台时才拦截。
- 撤销 v2.1.1 的"重选当前频道不重播"判断：它比较的是列表光标而不是正在播放的频道，实际上是上面这个焦点问题的误诊。
- 移除频道：纬来体育。

### v2.1.1

- 修复：在频道列表里按 OK 重选正在播放的频道，会重新准备播放流（电视日志里紧接着出现第二次"尝试播放"，画面闪断）。现在只关闭菜单，仅当该频道处于出错状态时才重试。（v2.1.2 撤销：该现象实为 v2.1.0 焦点问题的误诊。）

### v2.1.0

- 修复：频道台标下载流未关闭，缓存目录里留下 0 字节坏文件，每次换台触发大量 Glide 解码报错。现在会关闭流、清理坏文件并重新下载。
- 修复：上游强制繁体中文，与简体界面混排出现"換台反轉 關閉"之类的文案。现在强制简体，远程配置网页也改为简体。
- 修复：遥控器方向键处理完后仍向系统透传（v2.1.2 撤销：这会冻结菜单里的焦点导航）；按 HOME 离开再回来时设置、菜单、节目单面板残留。
- 修复：频道和分组列表复用 item 时残留选中高亮。
- 修复：二维码弹窗改为直接显示位图，停留时间 10 秒改为 30 秒；"Star 项目"按钮被大写成 STAR。
- 移除：上游的崩溃日志上报（把堆栈和设备型号发到 lyrics.run）；`/api/sources` 改为读内置列表，不再访问上游 GitHub。
- 清理：ISP 探测、mobile.txt、未引用的 drawable、HISTORY.md、赞赏图片、issue 模板等上游遗留。

### v2.0.0

- 首个 fork 版本：内置实测频道列表、凤凰卫视本地取流路由、fork 自己的设置页。

## 与上游的差异

相对 `lizongying/my-tv-0@19ab99c`（v1.3.9.8）：

1. **`app/src/main/res/raw/channels.txt`** —— 换成我们实测过的列表（gua64 编码的 JSON；gua64 是用 64 个易经卦象字符做字母表的 base64，用的是 lizongying 的 `io.github.lizongying:gua64`）。
2. **`SimpleServer.kt`** —— 新增一条本地路由 `GET http://127.0.0.1:34567/fh/<live_id>.flv`。它去调公开的 fengshows 接口 `https://m.fengshows.com/api/v3/hub/live/auth-url?live_id=<id>&live_qa=HD`（`token` header 留空），拿到签名后的 FLV 地址再 302 过去。之所以要这么绕，是因为那个地址带 `txSecret`/`txTime`，几个小时就过期，没法直接写死在列表里。
   - 凤凰资讯台 `7c96b084-60e1-40a9-89c5-682b994fb680`
   - 凤凰中文台 `f7f48462-9b13-485b-8101-7b54716411ec`
   - 凤凰香港台 `15e02d92-1698-416c-af2f-3e9a872b4d78`
   - 画质 HD，854x480 h264。FHD 需要登录 token，没有使用。
3. **`TVModel.kt`** —— `.flv` 结尾的地址走 PROGRESSIVE source，避免先按 HLS 试一次再回退。
4. **`SP.kt`** —— `DEFAULT_TIME=false`，时钟浮层默认关闭（设置里可以打开）。
5. 新的图标和 banner。
6. `applicationId` 改为 `com.lizongying.newmytv`，`app_name` 改为"我的电视"。
7. **设置页** —— 顶部链接指向本仓库、界面文字统一简体中文、"更新应用"打开 Releases、"赞赏作者"改为"Star 项目"（显示仓库二维码），并移除了上游的应用内更新逻辑。
8. **去联网与简体化** —— 移除上游的崩溃日志上报（lyrics.run），`/api/sources` 改为读取内置列表不再联网，强制简体中文（原为繁体），远程配置网页改为简体。

另外：设置页的"更新应用"现在直接打开本仓库的 [Releases](https://github.com/lswang6/my-newtv/releases) 页面。

代码改动集中在 SimpleServer/TVModel/SP/SettingFragment，上游的应用内更新逻辑已删除、去上游联网/上报、简体化，其余是资源文件。

## 免责声明

本项目仅供学习研究使用。所有直播源均来自公开互联网，本仓库不提供、不存储、不转发任何音视频内容，版权归各电视台所有。请勿用于商业用途。如有侵权或其他问题，请联系删除。

## 许可证

MIT。上游版权声明保留：

```
Copyright (c) 2025 李宗英
```

本 fork 的改动同样以 MIT 发布。完整条款见 [LICENSE](LICENSE)。
