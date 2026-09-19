[English](README.md)

# 我的电视（newmytv）

“我的电视”是一款 Android TV 直播播放器，希望让用户通过世界各地的新闻、文化、体育、纪录片和公共资讯电视获取知识。项目基于 [lizongying/my-tv-0](https://github.com/lizongying/my-tv-0) 做了克制的改造，加入经过测试的内置频道列表、凤凰卫视取流、本地列表维护工具和电视端实用修复。

创作者动机：其他电视应用中的广告和跟踪链接带来的困扰，促使创作者维护这个小而透明的 fork，让用户更直接地观看和了解世界各地的电视内容。

应用本身不注入广告，也不包含分析或跟踪 SDK；不会向本项目运营者发送观看历史、崩溃报告或设备标识。播放、节目单、台标、校时、用户添加的源及凤凰取流仍会访问各自的第三方服务。电视台或直播源提供方可能在节目中包含或插入广告，本项目无法移除这些广告，也不承诺第三方直播无广告。

## 功能

- Android TV 遥控器操作：上/下键换台，数字键选台，中键/Enter 打开频道列表，菜单键/右键打开设置，左键打开 EPG。
- 使用 Media3/ExoPlayer 播放 HLS、DASH、RTSP、RTMP 和普通渐进式媒体。
- 支持 M3U、TXT、JSON 源、每条 URI 独立请求头、多 URI 回退、收藏和 EPG。
- 内置 119 个频道的默认列表和 349 个频道的全球精简版；两个列表分别保存收藏。
- 可通过局域网中的浏览器导入自定义 M3U/TXT。
- 通过本地凤凰卫视路由调用公开的 fengshows API，获取短时有效的签名播放地址。
- `minSdk 21`、`targetSdk 35`。

## v2.3.0 发布版本

v2.3.0 提供两个可以独立安装的优化版 APK：

| 发布版本 | 文件名 | 本地化范围 | application ID | 本地网页服务 |
| --- | --- | --- | --- | --- |
| [`v2.3.0-zh`](https://github.com/lswang6/my-newtv/releases/tag/v2.3.0-zh) | `my-newtv-v2.3.0-zh.apk` | 简体中文界面；内置频道标签保留电视台或来源使用的原生名称 | `com.lizongying.newmytv` | `http://<电视IP>:34567` |
| [`v2.3.0-en`](https://github.com/lswang6/my-newtv/releases/tag/v2.3.0-en) | `my-newtv-v2.3.0-en.apk` | 英文界面；内置频道和分组标签使用英文 | `com.lizongying.newmytv.en` | `http://<电视IP>:34568` |

中文版保留现有包名和签名身份，可以覆盖升级旧版；英文版使用 `.en` 包名后缀和独立端口，因此两个版本可以同时安装在同一台电视上。

本地化只覆盖应用界面和内置频道标签。用户导入的自定义源标签会按原文保留；EPG 节目标题和简介按数据源原样显示，不会自动翻译。

打包的频道数据仍把凤凰内部地址统一写成 `http://127.0.0.1:34567/fh/…`。运行时，各版本会自动映射到自己的服务端口，因此用户和列表维护工具不需要保存两套频道数据。

## 安装与使用

下载需要的语言版本后，可用 ADB 或电视文件管理器安装：

```shell
adb connect <电视IP>:5555
adb install -r my-newtv-v2.3.0-zh.apk
adb install -r my-newtv-v2.3.0-en.apk
```

两个版本可以同时安装。如果更新中文版时 Android 提示签名冲突，说明电视里已有 APK 使用了不同的签名密钥。

不同遥控器的按键名称可能略有差异，标准操作如下：

- 上/下键：上一个或下一个频道。
- 数字键：输入频道号，最多四位。
- 中键/Enter：打开频道和分组列表。
- 菜单键/右键：打开设置，可选择内置列表、调整播放选项，或查看当前版本的本地网页管理地址。
- 左键：打开 EPG。

## 频道列表与可用性

默认列表的可读版本是 [`playlists/current.m3u`](playlists/current.m3u)，内容与打包进 APK 的 `channels.txt` 一致。三个凤凰卫视频道使用应用内部地址，因此不能复制到其他播放器中使用。

公开直播地址经常变化，也可能受国家或地区、运营商、IPv4/IPv6 和时间限制。一次测试通过不代表以后始终可播，Mac 可以访问也不等于电视一定可以播放。仓库中的报告只证明报告所写日期和网络出口下的结果，不保证全球可用。

## 来源与沿革

本仓库 fork 自 [lizongying/my-tv-0](https://github.com/lizongying/my-tv-0) 的 commit `19ab99c`、tag `v1.3.9.8`，保留了上游开放的 M3U/TXT 播放器、NanoHTTPD 配置服务、gua64 列表编码、自定义请求头、多 URI 回退和多种播放格式支持。

候选频道全部来自公开互联网列表，主要包括 [iptv-org/iptv](https://github.com/iptv-org/iptv)、[Free-TV/IPTV](https://github.com/Free-TV/IPTV)、[Guovin/iptv-api](https://github.com/Guovin/iptv-api)、[fanmingming/live](https://github.com/fanmingming/live)，以及上游收录的社区列表。凤凰取流沿用了 [lizongying/my-tv](https://github.com/lizongying/my-tv) 曾使用的公开 fengshows 调用方式和频道 live ID。

详细到 URL 的来源和测试结果保留在以下文件中：

- [`playlists/report.md`](playlists/report.md)：APK 内置列表报告。
- [`playlists/scan/report.md`](playlists/scan/report.md)：更大范围的公开列表扫描报告。
- [`playlists/README.md`](playlists/README.md)：各文件含义和测试边界。
- [`tools/README.md`](tools/README.md)：可复现的抓取、筛选、生成与验证流程。

本仓库不托管或转发第三方音视频。凤凰路由只把播放器重定向到上游签名地址。

## 构建并签名发布 APK

需要 JDK 21、Android SDK 35，以及包含 `apksigner` 的 Android SDK Build Tools。

```shell
JAVA_HOME=<jdk21> ANDROID_HOME=<android-sdk> \
  ./gradlew assembleZhRelease assembleEnRelease

apksigner sign --ks <现有本地-debug-keystore> \
  --out my-newtv-v2.3.0-zh.apk <zh-release-unsigned-apk>
apksigner sign --ks <现有本地-debug-keystore> \
  --out my-newtv-v2.3.0-en.apk <en-release-unsigned-apk>

apksigner verify --print-certs my-newtv-v2.3.0-zh.apk
apksigner verify --print-certs my-newtv-v2.3.0-en.apk
```

release 构建会启用压缩和优化，之后使用旧 APK 对应的现有本地 Android debug key 手工签名。已确认的证书 SHA-256 指纹为：

```text
ea5d8f8fa6b523030c15f2eb903a0859a79bb088562a834b83171d8f326135a0
```

keystore 及其凭据只保存在本地，不得提交到仓库或写入文档。中文版要覆盖升级旧版，必须继续使用这个签名身份。

## 维护与验证频道列表

脚本只依赖 Python 3 标准库。电视端探测还需要 ADB 和兼容的静态 `curl`，详见 [`tools/README.md`](tools/README.md)。

```shell
# 在电视或 Mac 上测试候选源
python3 tools/probe/extract_test.py --serial <电视IP>:5555
python3 tools/probe/extract_test.py --mac

# 重新生成 APK 内置列表、可读导出和英文显示标签
python3 tools/build/merge.py
python3 tools/build/export_m3u.py
python3 tools/build/localize_en.py
python3 tools/build/localize_en.py --check

# 安装后验证真机播放
python3 tools/device/verify_playback.py --serial <电视IP>:5555 --only 1,21,29

# 不联网检查大列表解析器
python3 tools/probe/scan_sources.py --selftest
```

`localize_en.py` 会为默认版 119 个频道和精简版 349 个频道生成英文显示标签。任何必需标签缺失时脚本都会直接失败，避免列表更新后英文版悄悄残留中文；`--check` 用于确认生成的英文资源完整且与当前列表一致。

仓库主要分为三部分：`app/` 是 Android 应用，`playlists/` 保存频道数据和报告，`tools/` 负责探测、生成和真机验证。

## 相对上游的改动

相对记录的上游基线，本 fork 替换了内置列表，加入凤凰签名地址路由，让 FLV 直接按普通媒体播放，支持大列表导入和每条 URI 独立请求头，按列表保存收藏，使用本项目的品牌与仓库链接，并移除了上游的应用内更新和崩溃报告上传。其他部分有意保持接近上游。

## 免责声明与许可证

本项目仅供学习研究。公开列表可能失效、标注错误，或在用户所在地无法使用。用户应自行遵守当地法律和各内容提供方的条款。各直播节目的版权归相应权利人所有；如有权利问题，请联系仓库维护者处理。

项目采用 [MIT License](LICENSE)，并保留上游版权声明：

```text
Copyright (c) 2025 李宗英
```
