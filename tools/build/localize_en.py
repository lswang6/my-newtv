#!/usr/bin/env python3
"""Generate and verify English bundled channel resources.

Only display labels are localized. M3U identity metadata (including tvg-name,
tvg-id, and tvg-logo), stream URLs, headers, order, and counts stay unchanged.

    python3 tools/build/localize_en.py
    python3 tools/build/localize_en.py --check
"""

import copy
import json
import os
import re
import sys

from gua64 import decode, encode


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
MAIN_RAW = os.path.join(REPO, "app", "src", "main", "res", "raw")
EN_RAW = os.path.join(REPO, "app", "src", "en", "res", "raw")
LABELS = os.path.join(HERE, "en_labels.json")

MAIN_CHANNELS = os.path.join(MAIN_RAW, "channels.txt")
MAIN_LITE = os.path.join(MAIN_RAW, "lite.m3u")
MAIN_SOURCES = os.path.join(MAIN_RAW, "sources.txt")
EN_CHANNELS = os.path.join(EN_RAW, "channels.txt")
EN_LITE = os.path.join(EN_RAW, "lite.m3u")

NON_ENGLISH_SCRIPT = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
GROUP_RE = re.compile(r'group-title="([^"]*)"')
IDENTITY_ATTRS = ("tvg-id", "tvg-name", "tvg-logo")


def read_text(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def load_labels():
    data = json.loads(read_text(LABELS))
    if set(data) != {"groups", "titles"}:
        raise AssertionError("en_labels.json must contain groups and titles")
    return data["groups"], data["titles"]


def translate(label, labels, kind):
    if NON_ENGLISH_SCRIPT.search(label):
        if label not in labels:
            raise AssertionError(f"missing English {kind} mapping: {label!r}")
        translated = labels[label]
        if NON_ENGLISH_SCRIPT.search(translated):
            raise AssertionError(f"non-English script remains in {kind}: {label!r} -> {translated!r}")
        if kind == "title" and "," in translated:
            raise AssertionError(f"comma would change the app's #EXTINF title parsing: {translated!r}")
        return translated
    return label


def load_main_channels():
    return json.loads(decode(read_text(MAIN_CHANNELS)).strip())


def localized_channels(groups, titles):
    output = []
    for source in load_main_channels():
        channel = copy.deepcopy(source)
        channel["group"] = translate(source.get("group", ""), groups, "group")
        channel["title"] = translate(source.get("title", ""), titles, "title")
        # The canonical JSON omits TV.name. Once title is localized, leaving name empty
        # would make EPG, logo, and favorite identity fall back to the English display
        # title. Keep the canonical title as the identity-only name.
        if not channel.get("name"):
            channel["name"] = source.get("title", "")
        output.append(channel)
    return output


def split_title(line):
    ending = "\n" if line.endswith("\n") else ""
    body = line[:-1] if ending else line
    if body.endswith("\r"):
        body, ending = body[:-1], "\r" + ending
    comma = body.rfind(",")
    if comma < 0:
        raise AssertionError(f"#EXTINF line has no title delimiter: {body!r}")
    value = body[comma + 1:]
    leading = value[:len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()):]
    return body[:comma + 1], value.strip(), leading, trailing, ending


def localized_lite(groups, titles):
    output = []
    for line in read_text(MAIN_LITE).splitlines(keepends=True):
        if not line.startswith("#EXTINF"):
            output.append(line)
            continue
        prefix, title, leading, trailing, ending = split_title(line)
        matches = list(GROUP_RE.finditer(prefix))
        if len(matches) != 1:
            raise AssertionError(f"expected one group-title on #EXTINF line: {line!r}")
        source_group = matches[0].group(1)
        target_group = translate(source_group, groups, "group")
        prefix = GROUP_RE.sub(f'group-title="{target_group}"', prefix, count=1)
        target_title = translate(title, titles, "title")
        output.append(prefix + leading + target_title + trailing + ending)
    return "".join(output)


def expected_outputs():
    groups, titles = load_labels()
    channel_text = encode(json.dumps(
        localized_channels(groups, titles), ensure_ascii=False, separators=(",", ":")
    ))
    return channel_text, localized_lite(groups, titles)


def write_outputs():
    channel_text, lite_text = expected_outputs()
    os.makedirs(EN_RAW, exist_ok=True)
    with open(EN_CHANNELS, "w", encoding="utf-8") as stream:
        stream.write(channel_text)
    with open(EN_LITE, "w", encoding="utf-8") as stream:
        stream.write(lite_text)


def attr(line, name):
    match = re.search(rf'{re.escape(name)}="([^"]*)"', line)
    return match.group(1) if match else None


def neutralize_extinf(line):
    prefix, _title, leading, trailing, ending = split_title(line)
    prefix = GROUP_RE.sub('group-title="<DISPLAY-GROUP>"', prefix, count=1)
    return prefix + leading + "<DISPLAY-TITLE>" + trailing + ending


def extinf_records(text):
    records = []
    for line in text.splitlines(keepends=True):
        if line.startswith("#EXTINF"):
            _prefix, title, _leading, _trailing, _ending = split_title(line)
            group = attr(line, "group-title")
            if group is None:
                raise AssertionError(f"missing group-title: {line!r}")
            records.append((line, group, title))
    return records


def verify_mapping_coverage(groups, titles, main_channels, main_lite):
    used_groups = {item.get("group", "") for item in main_channels}
    used_titles = {item.get("title", "") for item in main_channels}
    for _line, group, title in extinf_records(main_lite):
        used_groups.add(group)
        used_titles.add(title)

    needed_groups = {label for label in used_groups if NON_ENGLISH_SCRIPT.search(label)}
    needed_titles = {label for label in used_titles if NON_ENGLISH_SCRIPT.search(label)}
    if needed_groups != set(groups):
        raise AssertionError(
            f"group mappings differ from source; missing={sorted(needed_groups - set(groups))}, "
            f"unused={sorted(set(groups) - needed_groups)}"
        )
    if needed_titles != set(titles):
        raise AssertionError(
            f"title mappings differ from source; missing={sorted(needed_titles - set(titles))}, "
            f"unused={sorted(set(titles) - needed_titles)}"
        )


def check():
    groups, titles = load_labels()
    expected_channels, expected_lite = expected_outputs()
    actual_channels_text = read_text(EN_CHANNELS)
    actual_lite = read_text(EN_LITE)
    if actual_channels_text != expected_channels:
        raise AssertionError("English channels.txt is stale; run tools/build/localize_en.py")
    if actual_lite != expected_lite:
        raise AssertionError("English lite.m3u is stale; run tools/build/localize_en.py")

    main_channels = load_main_channels()
    en_channels = json.loads(decode(actual_channels_text).strip())
    if len(main_channels) != 119 or len(en_channels) != 119:
        raise AssertionError(f"default channel count changed: {len(main_channels)} -> {len(en_channels)}")
    for index, (source, localized) in enumerate(zip(main_channels, en_channels), 1):
        expected = copy.deepcopy(source)
        expected["group"] = translate(source.get("group", ""), groups, "group")
        expected["title"] = translate(source.get("title", ""), titles, "title")
        expected["name"] = source.get("name") or source.get("title", "")
        if localized != expected:
            raise AssertionError(f"default channel {index} differs beyond localized labels")
        for field in set(source) - {"group", "title"}:
            if localized[field] != source[field]:
                raise AssertionError(f"default channel {index} changed identity/stream field {field}")
        if localized["name"] != (source.get("name") or source.get("title", "")):
            raise AssertionError(f"default channel {index} does not retain its canonical identity name")
        if NON_ENGLISH_SCRIPT.search(localized["group"] + localized["title"]):
            raise AssertionError(f"default channel {index} retains a non-English display label")

    main_lite = read_text(MAIN_LITE)
    main_lines = main_lite.splitlines(keepends=True)
    en_lines = actual_lite.splitlines(keepends=True)
    if len(main_lines) != len(en_lines):
        raise AssertionError(f"lite line count changed: {len(main_lines)} -> {len(en_lines)}")
    for number, (source, localized) in enumerate(zip(main_lines, en_lines), 1):
        if source.startswith("#EXTINF"):
            if not localized.startswith("#EXTINF"):
                raise AssertionError(f"lite line {number} is no longer #EXTINF")
            if neutralize_extinf(source) != neutralize_extinf(localized):
                raise AssertionError(f"lite line {number} changed identity metadata")
            for name in IDENTITY_ATTRS:
                if attr(source, name) != attr(localized, name):
                    raise AssertionError(f"lite line {number} changed {name}")
        elif source != localized:
            raise AssertionError(f"lite line {number} changed URL/header/comment data")

    main_records = extinf_records(main_lite)
    en_records = extinf_records(actual_lite)
    if len(main_records) != 836 or len(en_records) != 836:
        raise AssertionError(f"lite stream-entry count changed: {len(main_records)} -> {len(en_records)}")
    main_channels_count = len({(group, attr(line, "tvg-name")) for line, group, _ in main_records})
    en_channels_count = len({(group, attr(line, "tvg-name")) for line, group, _ in en_records})
    if main_channels_count != 349 or en_channels_count != 349:
        raise AssertionError(
            f"lite grouped-channel count changed: {main_channels_count} -> {en_channels_count}"
        )
    for index, (_line, group, title) in enumerate(en_records, 1):
        if NON_ENGLISH_SCRIPT.search(group + title):
            raise AssertionError(f"lite entry {index} retains a non-English display label")

    main_urls = [line for line in main_lines if line.strip() and not line.startswith("#")]
    en_urls = [line for line in en_lines if line.strip() and not line.startswith("#")]
    if main_urls != en_urls:
        raise AssertionError("lite stream URL order/content changed")

    verify_mapping_coverage(groups, titles, main_channels, main_lite)
    source_count = len(decode(read_text(MAIN_SOURCES)).strip().splitlines())
    filled_names = sum(not item.get("name") for item in main_channels)
    print(
        f"OK default: {len(en_channels)} channels; streams/order match and "
        f"{filled_names} missing identity names use canonical titles"
    )
    print(
        f"OK lite: {en_channels_count} grouped channels, {len(en_records)} stream entries; "
        "tvg identity, URLs, headers, and order match"
    )
    print(f"OK labels: {len(groups)} groups and {len(titles)} channel titles mapped; no Han/Kana remains in display labels")
    print(f"OK sources: {source_count} URL-only entries; no localized override generated")


def main():
    if sys.argv[1:] == ["--check"]:
        check()
        return
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    write_outputs()
    check()


if __name__ == "__main__":
    main()
