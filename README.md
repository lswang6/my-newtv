[简体中文](README.zh-CN.md)

# My TV (newmytv)

My TV is an Android TV live-stream player built for learning from news, culture, sport, documentaries, and public-interest television around the world. It is a focused fork of [lizongying/my-tv-0](https://github.com/lizongying/my-tv-0) with tested built-in channel lists, a Phoenix TV resolver, list-maintenance tools, and practical TV fixes.

Creator motivation: Frustration with advertising and tracking links in other TV apps led to this fork—a small, auditable player focused on direct access to television from around the world.

The app itself injects no advertising and includes no analytics or tracking SDK. It does not send viewing history, crash reports, or device identifiers to this project's operator. Playback, programme guides, logos, time lookup, and user-added sources still contact their respective third-party services. Broadcasters and stream providers may include or insert advertising in their programmes; this project cannot remove or promise the absence of those ads.

## Features

- Android TV remote control: Up/Down changes channel, number keys select a channel, D-pad Center/Enter opens the channel list, Menu/Right opens Settings, and Left opens EPG.
- Media3/ExoPlayer playback for HLS, DASH, RTSP, RTMP, and progressive streams.
- M3U, TXT, and JSON sources, per-URI request headers, multiple fallback URIs, favourites, and EPG support.
- A bundled 119-channel default list and a 349-channel worldwide lite list. Each list keeps its own favourites.
- Local browser management for importing a custom M3U/TXT list.
- A local Phoenix TV route that obtains short-lived signed playback URLs from the public fengshows API.
- `minSdk 21` and `targetSdk 35`.

## v2.3.0 release editions

v2.3.0 is published as two independently installable, optimized APKs:

| Release | Filename | Localization | Application ID | Local web server |
| --- | --- | --- | --- | --- |
| [`v2.3.0-zh`](https://github.com/lswang6/my-newtv/releases/tag/v2.3.0-zh) | `my-newtv-v2.3.0-zh.apk` | Simplified Chinese UI; bundled channel labels retain native broadcaster/source names | `com.lizongying.newmytv` | `http://<TV-IP>:34567` |
| [`v2.3.0-en`](https://github.com/lswang6/my-newtv/releases/tag/v2.3.0-en) | `my-newtv-v2.3.0-en.apk` | English UI; bundled channel and group labels in English | `com.lizongying.newmytv.en` | `http://<TV-IP>:34568` |

The Chinese edition keeps the existing package ID and signing identity, so it can update the previous app in place. The `.en` package suffix and separate server port let the English edition coexist on the same TV.

Localization applies to the app UI and bundled channel labels only. Labels in custom user-imported sources are preserved as provided. EPG programme titles and descriptions are displayed as received and are not automatically translated.

The bundled playlist keeps Phoenix's canonical internal URLs at `http://127.0.0.1:34567/fh/…`. At runtime each edition maps those URLs to its own server port, so users and list-maintenance tools do not need edition-specific playlist data.

## Install and use

Download the APK for the language you want, then install it with ADB or a TV file manager:

```shell
adb connect <TV-IP>:5555
adb install -r my-newtv-v2.3.0-zh.apk
adb install -r my-newtv-v2.3.0-en.apk
```

Both editions may be installed together. If Android reports a signature conflict while updating the Chinese edition, the installed APK was signed with a different key.

Remote controls vary, but the standard controls are:

- Up/Down: previous or next channel.
- Number keys: enter a channel number, up to four digits.
- D-pad Center/Enter: open the channel and group list.
- Menu/Right: open Settings to choose a bundled list, configure playback, or show the edition's local browser-management address.
- Left: open EPG.

## Channel lists and availability

The readable export of the default list is [`playlists/current.m3u`](playlists/current.m3u). It matches the bundled `channels.txt`; the three Phoenix entries use app-local URLs and therefore will not work in another player.

Public live URLs are volatile and often restricted by country, ISP, IP version, or time. A stream that passed one test can later fail, and Mac reachability does not prove playback on a TV. The checked-in reports describe their exact test location and date; they are evidence for that run, not a global availability guarantee.

## Source provenance

This repository is based on [lizongying/my-tv-0](https://github.com/lizongying/my-tv-0) commit `19ab99c`, tag `v1.3.9.8`. It retains that project's open M3U/TXT player, NanoHTTPD configuration server, gua64 list encoding, request headers, fallback URIs, and playback-format support.

Candidate channels come from public Internet playlists, principally [iptv-org/iptv](https://github.com/iptv-org/iptv), [Free-TV/IPTV](https://github.com/Free-TV/IPTV), [Guovin/iptv-api](https://github.com/Guovin/iptv-api), [fanmingming/live](https://github.com/fanmingming/live), and the community lists referenced by upstream. Phoenix handling follows the public fengshows method and live IDs previously used by [lizongying/my-tv](https://github.com/lizongying/my-tv).

Detailed, URL-level provenance and test outcomes are preserved in:

- [`playlists/report.md`](playlists/report.md) for the bundled list.
- [`playlists/scan/report.md`](playlists/scan/report.md) for the wider public-list scan.
- [`playlists/README.md`](playlists/README.md) for file meanings and test limits.
- [`tools/README.md`](tools/README.md) for the reproducible collection, filtering, and verification process.

This repository does not host or relay third-party audio or video. The Phoenix route only redirects the player to a signed upstream URL.

## Build and sign the release APKs

Requirements: JDK 21, Android SDK 35, and Android SDK Build Tools containing `apksigner`.

```shell
JAVA_HOME=<jdk21> ANDROID_HOME=<android-sdk> \
  ./gradlew assembleZhRelease assembleEnRelease

apksigner sign --ks <existing-local-debug-keystore> \
  --out my-newtv-v2.3.0-zh.apk <zh-release-unsigned-apk>
apksigner sign --ks <existing-local-debug-keystore> \
  --out my-newtv-v2.3.0-en.apk <en-release-unsigned-apk>

apksigner verify --print-certs my-newtv-v2.3.0-zh.apk
apksigner verify --print-certs my-newtv-v2.3.0-en.apk
```

The release builds are minified and optimized, then manually signed with the same existing local Android debug key used by the old APK. Its confirmed SHA-256 certificate fingerprint is:

```text
ea5d8f8fa6b523030c15f2eb903a0859a79bb088562a834b83171d8f326135a0
```

The keystore and its credentials are local and must not be committed or written into documentation. Using this same signing identity is required for Chinese-edition in-place upgrades.

## Maintain and verify the lists

The scripts use the Python 3 standard library. Device probing also requires ADB and a compatible static `curl` on the TV; see [`tools/README.md`](tools/README.md).

```shell
# Test selected candidates on the TV or Mac
python3 tools/probe/extract_test.py --serial <TV-IP>:5555
python3 tools/probe/extract_test.py --mac

# Regenerate the bundled list, readable export, and English display labels
python3 tools/build/merge.py
python3 tools/build/export_m3u.py
python3 tools/build/localize_en.py
python3 tools/build/localize_en.py --check

# Verify real playback after installation
python3 tools/device/verify_playback.py --serial <TV-IP>:5555 --only 1,21,29

# Validate the wider-list parser without network access
python3 tools/probe/scan_sources.py --selftest
```

`localize_en.py` maps display labels for both the 119-channel default list and the 349-channel lite list. It fails closed when any required label is missing, so a list update cannot silently leave Chinese labels in the English edition; `--check` verifies that the generated English resources are complete and current.

The primary repository areas are `app/` for the Android application, `playlists/` for list data and reports, and `tools/` for probing, generation, and device verification.

## Fork changes

Compared with the recorded upstream base, this fork replaces the bundled list, adds the Phoenix signed-URL route, treats FLV as progressive media, supports larger imports and per-URI headers, keeps favourites per list, uses its own branding and repository links, and removes upstream in-app updating and crash-report upload. The rest remains intentionally close to upstream.

## Disclaimer and license

This project is for learning and research. Public playlist entries may disappear, be inaccurate, or be unavailable in your jurisdiction. Users are responsible for complying with local law and the terms of each content provider. Copyright in each broadcast remains with its owner; contact the repository maintainer to report a rights issue.

Licensed under the [MIT License](LICENSE). The upstream copyright notice is retained:

```text
Copyright (c) 2025 李宗英
```
