#!/usr/bin/env python3
"""Scan a batch of public playlists for channels that play from this Mac.

Every distinct url across the sources is tested once with extract_test's own protocol in
its Mac mode, the passing ones are merged into channels by name, and playlists/scan/ gets
merged.m3u (every passing url), available.m3u (3 per channel), channels.csv, results.csv and
report.md (which also holds the comparison with the list the apk ships).

    python3 scan_sources.py --selftest       # parsers, junk filter, classifier, merging; no network
    python3 scan_sources.py --limit 300      # pilot: 300 untested urls spread across the sources
    python3 scan_sources.py --workers 48     # full run; resumes from tools/.cache/scan_results.jsonl
    python3 scan_sources.py --report-only    # rebuild the output files from the caches, no network
"""
import csv, ipaddress, json, os, re, subprocess, sys, threading, time, unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import extract_test as et
from merge import FH, ORDER, merge

et.USE_TV = False  # extract_test reads --mac from its own argv at import time; this is the Mac path

SRC_DIR = os.path.join(et.CACHE, "scan_src")
STATUS = os.path.join(SRC_DIR, "status.json")
JSONL = os.path.join(et.CACHE, "scan_results.jsonl")
OUT = os.path.join(et.DATA, "scan")
REPO = os.path.dirname(et.DATA)
arg = lambda flag, d: int(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else d
WORKERS, LIMIT = arg("--workers", 48), arg("--limit", 0)

SOURCES = [
    (1, "https://php.946985.filegear-sg.me/jackTV.m3u"),
    (2, "https://iptv-org.github.io/iptv/index.m3u"),
    (3, "https://web.utako.moe/jp.m3u"),
    (4, "https://epg.pw/test_channels.m3u"),
    (5, "https://epg.pw/test_channels_hong_kong.m3u"),
    (6, "https://epg.pw/test_channels_macau.m3u"),
    (7, "https://epg.pw/test_channels_taiwan.m3u"),
    (8, "https://iptv-org.github.io/iptv/countries/tw.m3u"),
    (9, "https://epg.pw/test_channels_singapore.m3u"),
    (10, "https://epg.pw/test_channels_malaysia.m3u"),
    (11, "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    (12, "https://iptv-org.github.io/iptv/index.m3u"),
    (13, "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u"),
    (14, "https://raw.githubusercontent.com/BigBigGrandG/IPTV-URL/release/Gather.m3u"),
    (15, "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u"),
    (16, "https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.txt"),
    (17, "https://raw.githubusercontent.com/PizazzGY/TV/master/output/user_result.m3u"),
    (18, "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
    (19, "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u"),
    (20, "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u"),
    (21, "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u"),
    (22, "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv6.m3u"),
    (23, "https://live.zbds.top/tv/iptv4.txt"),
    (24, "https://live.zbds.top/tv/iptv4.m3u"),
    (25, "https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/TV-IPV4.m3u"),
    (26, "https://raw.githubusercontent.com/vamoschuck/TV/main/M3U"),
]
SRC_URL = dict(SOURCES)
TIER2 = {2, 11}  # the two big international lists wait until every other source is done
EPG = {4, 5, 6, 7, 9, 10}
SRC_CC = {3: "jp", 5: "hk", 6: "mo", 7: "tw", 8: "tw", 9: "sg", 10: "my"}
# Most specific first: a url or channel several rules claim takes the earliest. Output order is SHOW.
GROUPS = ["央视", "凤凰", "卫视", "港台新闻", "港台综艺", "港澳台", "新马", "日本", "体育", "纪录片", "国际新闻",
          "数字频道", "地方"]
SHOW = ORDER + ["港澳台", "新马", "日本", "数字频道", "地方"]  # then the 海外·* groups
# merged-lite.m3u. Titles are exact (casefolded), since source country codes are unreliable ("AXN Black Poland" is tagged US).
# PICKS: the only channels of 海外·* and PICK_GROUPS kept besides the apk's own.
PICK_GROUPS = ("国际新闻", "体育", "纪录片")
PICKS = {t.casefold(): t for t in (
    # 海外·*: well-known English/Korean/Thai channels
    "HBO Hits East", "HBO Movies", "Cinemax Hits", "Cinemax Classics", "Starz Cinema", "AMC (US)", "IFC",
    "Paramount Network", "Paramount Movie Channel", "Hallmark Movies & More",
    "Nickelodeon (US)", "Nick Jr. Club (US)", "NickToons (US)", "Disney Channel East", "Disney Junior (US)",
    "Disney XD (US)", "PBS Kids", "CBeebies Asia", "Crunchyroll", "Toonami Aftermath East", "Tiny Pop", "EBS kids",
    "Comedy Central (US)", "MTV (US)", "A&E", "Lifetime", "Oxygen", "Crime + Investigation", "Game Show Network East",
    "KBS Joy",
    "MTV Live", "MTV Biggest Pop", "VH1", "CMT", "Qello Concerts by Stingray", "Stingray Hit List",
    "Stingray Greatest Hits", "Stingray Classic Rock", "Stingray Smooth Jazz", "Stingray Classica",
    "Stingray Today's KPOP", "Trace UK",
    "KBS World", "SBS", "TV Chosun", "Thai PBS", "Showtime", "Freeform", "Bravo", "Outdoor Channel", "Tastemade",
    "Fox Weather", "HGTV",
    "EBS 1", "BBC Drama",
    # 国际新闻
    "ABC News Live",
    # 体育
    "五星体育", "辽宁体育", "Red Bull TV", "CBS Sports HQ", "ESPNews", "NFL Channel",
    # 纪录片
    "Bloomberg Originals", "Love Nature", "WildEarth", "MagellanTV Now", "Discovering China", "China Travel",
    "Terra Mater WILD English", "WaterBear")}
# DROP: every group but the picked ones loses these; 地方 then also has to pass LOCAL_PREFIX and LOCAL_DENY.
DROP = {t.casefold(): t for t in (
    # 央视: English aliases of channels already there under their Chinese names
    "CCTV-Nostalgia Theater", "CCTV-The First Theater", "CCTV-Storm Theater", "CCTV-Storm Football", "CCTV-Storm Music",
    "CCTV-World Geography", "CCTV-Billiards", "CCTV-Golf & Tennis", "CCTV-Women's Fashion", "CCTV-Culture of Quality",
    "CGTN French", "CGTN Arabic", "CGTN记录",
    "海峡卫视", "澳門衛星",  # = 福建海峡卫视, 澳视卫星
    # strays, religious, shopping
    "广西玉林大容山莲花山顶", "Supreme Master TV", "CGNTV Chinese", "人间卫视", "唯心電視", "IasiTV Life", "Shop Channel",
    "QVC (JP)", "GSTV", "CGNTV Japan", "KCM", "Zoo Moo (Australia)", "Maah TV",
    # 地方: only radio urls (cnr.cn, qingting.fm, radio.pull.hebtv.com), or a qingting radio stream first (辽宁都市)
    "北京新闻", "吉林乡村", "福建新闻", "福建经济", "山东生活", "武汉一台新闻综合", "长沙新闻综合", "陕西公共", "黑龙江少儿",
    "黑龙江新闻", "河北都市", "浙江生活", "辽宁都市",
    # 地方: not a station (a guide loop; a bare php.jdshipin.com/iptv.php with no channel id), a county station
    "安徽导视", "湖南电影", "浙江遂昌",
    # 地方: the same stream under another name (cztv channel id, hrbtv path), kept as 浙江钱江, 浙江经济生活, 浙江教科影视,
    # 浙江民生, 浙江新闻, 哈尔滨资讯 and 数字频道's 南国都市
    "浙江钱江都市", "浙江钱江频道", "浙江经济", "浙江经视", "浙江教科", "浙江教育", "浙江民生休闲", "浙江休闲台",
    "浙江公共新闻", "哈尔滨都市咨询", "广州南国都市")}
# 地方 keeps province-level and major-city stations, minus radio, scenic webcams, karaoke, galas and VOD.
LOCAL_PREFIX = (
    "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西",
    "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西",
    "西藏", "宁夏", "新疆",
    "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "苏州", "郑州", "长沙", "沈阳", "青岛", "宁波", "东莞", "佛山",
    "合肥", "济南", "福州", "厦门", "大连", "哈尔滨", "长春", "昆明", "南昌", "南宁", "石家庄", "太原", "贵阳", "兰州",
    "乌鲁木齐", "呼和浩特", "海口", "银川", "西宁", "拉萨", "无锡", "温州", "珠海")
LOCAL_DENY = re.compile(r"广播|电台|FM|调频|之声|音乐台|动听|\d{3}$|\d\.\d$"  # radio
                        r"|景区|景$|远眺|雪山|山顶|峰|湖畔|公园|沙滩|山$|岛$|丽江|峨眉|四姑娘山|张家界|崂山|黟县|鼓浪屿|洋县"  # webcams
                        r"|「|DJ|第.部|春晚|晚会|演唱会|^\d{4}年")  # karaoke, galas, VOD


def lite(c):
    if c.get("cur"):  # the apk's own channels, played on the TV, always stay
        return True
    t, g = c["title"], c["group"]
    if re.search(r"(?<!\d)[48]K\b", t):  # 4K/8K copies
        return False
    if g.startswith("海外·") or g in PICK_GROUPS:
        return t.casefold() in PICKS
    if t.casefold() in DROP:
        return False
    return g != "地方" or (t.startswith(LOCAL_PREFIX) and not LOCAL_DENY.search(t))

# ---------------------------------------------------------------- sources

def src_path(i):
    return os.path.join(SRC_DIR, "%02d_%s" % (i, os.path.basename(urlparse(SRC_URL[i]).path)))


def download():
    os.makedirs(SRC_DIR, exist_ok=True)
    status, first = {}, {}
    for i, url in SOURCES:
        if url in first:
            status[i] = "同 %02d，不重复下载" % first[url]
            continue
        first[url], p = i, src_path(i)
        for attempt in range(2):
            r = subprocess.run(["curl", "-sSL", "--max-time", "90", "-A", "Mozilla/5.0", "-o", p + ".part",
                                "-w", "%{http_code}", url], capture_output=True, text=True)
            if r.stdout == "200" and os.path.exists(p + ".part") and os.path.getsize(p + ".part"):
                break
        if r.stdout == "200" and os.path.exists(p + ".part") and os.path.getsize(p + ".part"):
            os.replace(p + ".part", p)
            status[i] = "ok"
        else:
            if os.path.exists(p + ".part"):
                os.remove(p + ".part")
            why = "HTTP " + r.stdout if r.stdout not in ("", "000") else r.stderr.strip().split(") ")[-1][:60]
            status[i] = "失败（%s），%s" % (why, "用上次的缓存" if os.path.exists(p) else "无缓存")
        print("  %02d %s" % (i, status[i]))
    json.dump(status, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False)


def parse_txt(text, src):
    """The `genre,#genre#` / `name,url` format; one line can carry several urls joined by #."""
    out, genre = [], ""
    for line in text.splitlines():
        name, sep, rest = line.strip().partition(",")
        if not sep:
            continue
        if rest.strip() == "#genre#":
            genre = name.strip()
            continue
        for u in re.split(r"#(?=[A-Za-z][\w+.-]*://)", rest.strip()):
            u = u.split("$")[0].strip()  # `$label` is a player-side caption, not part of the url
            if u:
                out.append({"name": name.strip(), "tvg_id": "", "tvg_name": "", "logo": "",
                            "group_title": genre, "source": src, "url": u, "headers": {}})
    return out


# Guovin and zbds file a timestamp as a channel under 更新时间 (the marker sits in group-title
# or tvg-id, not the name); YanG files its notices under 温馨「提示」.
JUNK = re.compile(r"更新时间|温馨「提示」")


def slow(e):
    # stream1.freetv.fun (and t.freetv.fun) answer after ~20 s, a Cloudflare 522 or a 200 at ~19.8 s,
    # past fetch()'s 10 s protocol timeout, so every url on them fails: they are dropped as they load.
    return bool(re.match(r"[A-Za-z][\w+.-]*://([^/?#@]*@)?([^/?#:]*\.)?freetv\.fun([:/?#]|$)", e["url"]))


def keep(e):
    # The url must have a scheme: Free-TV writes "[NO PUBLIC STREAM]" in its place, and one
    # entry in 26 has a newline inside group-title that leaves half an #EXTINF where the url goes.
    return bool(re.match(r"[A-Za-z][\w+.-]*://", e["url"])) and not (
        JUNK.search(" | ".join([e["group_title"], e["tvg_id"], e["tvg_name"]]))
        or re.match(r"(维护|公告|请勿|免费订阅)", e["name"]) or slow(e))


def ukey(e):
    return e["url"] + "|" + json.dumps(e["headers"], sort_keys=True)


def load():
    """(entries, entries kept per source, {url key: sources} of the freetv.fun urls dropped)."""
    entries, counts, gone = [], {}, {}
    for i, _ in SOURCES:
        if not os.path.exists(src_path(i)) or SRC_URL[i] in [u for j, u in SOURCES if j < i]:
            continue
        text = open(src_path(i), encoding="utf-8", errors="replace").read()
        es = (et.parse_m3u if "#EXTINF" in text else parse_txt)(text, i)
        for e in filter(slow, es):
            gone.setdefault(ukey(e), set()).add(i)
        es = [e for e in es if keep(e)]
        counts[i] = len(es)
        entries += es
    return entries, counts, gone


def pre_status(url):
    """The status of a url that is never dialled, or None when it should be tested."""
    if "[" in url:
        return "ipv6"  # neither this Mac nor the TV has an IPv6 route
    if not url.lower().startswith(("http://", "https://")):
        return "untested-protocol"
    h = urlparse(url).hostname or ""
    try:
        if h == "localhost" or ipaddress.ip_address(h).is_private:
            return "excluded-lan"
    except ValueError:
        pass
    if et.BADHOST.search(h):
        return "excluded-host"
    if "slate" in url.lower():
        return "excluded-slate"
    return None

# ---------------------------------------------------------------- classify

HKMOTW = re.compile(r"TVB|翡翠(?!湾|灣)|無綫|無線|无线新闻|ViuTV|有線|HOY|RTHK|港台電視|港台电视|台視|台视|中視|中视|華視|华视|民視|民视|"
                    r"公視|公视|三立|東森|东森|中天|年代MUCH|年代新聞|非凡新聞|寰宇|緯來|纬来|八大|龍華|龙华|澳門|澳门|"
                    r"澳視|澳视|澳亚|澳亞|TDM|美亞|美亚|衛視中文|卫视中文|人间卫视|人間衛視|蓮花|莲花|香港卫视|香港衛視", re.I)
GENRE = [("电影", r"movie|film|cinema|电影|電影"), ("剧集", r"series|drama|剧|劇"),
         ("综艺", r"entertainment|comedy|综艺|綜藝"), ("音乐", r"music|音乐|音樂"),
         ("少儿", r"kids|animation|children|少儿|兒童|儿童|动画|卡通"), ("宗教", r"religi"),
         ("教育", r"education|教育")]


# Tags playlists bolt onto a name, wherever they sit. An allowlist on purpose: other bracketed words
# name a different feed (半岛新闻「阿拉伯」, Sky News Arabia (Portrait)) and stay. Not 4K/8K either:
# CCTV4K is a different channel from CCTV4. A letter or digit next to HD keeps it (3HD, Caracol HD2).
NOISE = re.compile(r"(?i)(?<![a-z\d])([FU]?HD|SD|HEVC|H\.?26[45]|\d{2,3}\s?FPS|\d+(\.\d+)?\s?Mbps|"
                   r"(480|576|720|1080|1440|2160)[pi])(?![a-z\d])|超高清|高清|超清|标清|標清|蓝光|藍光|备用|備用|"
                   r"[(（]\s*(备|備|测试|測試)\s*[)）]|「[A-Z]{1,2}」|[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


def tidy(s):
    s = NOISE.sub(" ", et.strip_deco(s))
    s = re.sub(r"(?i)([a-z]-?\d{1,2})[FU]?HD(?![a-z\d])", r"\1", s)  # CCTV-1HD, CETV-1HD
    return re.sub(r"\s+", " ", re.sub(r"[(（\[「]\s*[)）\]」]", " ", s)).strip(" -_|")


def ident(title):
    """Letters of every script and digits, with case, Latin accents, width and 繁/简 folded; + is kept as a
    word (CCTV5+, ETV Plus). Only the combining accents are dropped, so ガ stays apart from カ."""
    t = unicodedata.normalize("NFC", re.sub("[\u0300-\u036f]", "", unicodedata.normalize("NFKD", et.simp(title))))
    return re.sub(r"[\W_]+", "", t.replace("+", "plus").casefold())


nk = lambda t: ident(tidy(t)).replace("卫视", "")  # merge.py titles 凤凰 "凤凰卫视资讯台", the matcher says "凤凰资讯台"


def _classify(e, src, name, tname, tid, gt, cc, title):
    names = name + " | " + tname
    x = dict(e, tvg_name=tname)
    c = et.canon(name, tid, tname, {5: "hk", 7: "tw", 8: "tw"}.get(src, ""))
    g = et.GROUP_OF.get(c)
    if g == "央视" or re.search(r"CCTV|CGTN|(?<![a-z])CETV|中国教育", names, re.I):
        return "央视", c or title
    if g == "凤凰" or re.search(r"(?<!火)(凤凰|鳳凰)(?!传奇|傳奇)", names):  # "Phoenix" alone is mostly Arizona
        return "凤凰", c or title
    sat = et.canon_satellite(x, title, names)
    if sat:
        return "卫视", sat[1]
    hk = et.canon_hktv(x, title, names)
    if src in (5, 6, 7, 8) or cc in ("hk", "mo", "tw") or g == "港台新闻" or hk or HKMOTW.search(names):
        if g == "港台新闻" or re.search(r"新闻|新聞|News", title, re.I):
            return "港台新闻", c or title
        return ("港台综艺", hk[1]) if hk else ("港澳台", c or title)  # 澳门卫视 and 人间卫视 land here, not in 卫视
    if re.search(r"(卫视|衛視)$", title):
        return "卫视", et.simp(title)
    if src in (9, 10) or cc in ("sg", "my"):
        return "新马", title
    if src == 3 or cc == "jp" or re.search(r"[぀-ヿ]", names):
        return "日本", title
    # Chinese lists misfile freely (zbds puts Jilin county news under 纪录频道), so a CJK name has
    # to say sport or documentary itself; group-title alone only counts for the rest.
    latin = not et.CJK.search(title)
    sp = et.canon_sport(x)
    if sp or latin and re.search(r"sport|體育|運動", gt, re.I):
        return "体育", sp[0] if sp else title
    d = et.canon_doc(x, title, " | ".join([names, tid, gt]))
    if d or latin and re.search(r"documentar|紀錄|紀實", gt, re.I):
        return "纪录片", d[1] if d else title
    if g == "国际新闻" or latin and re.search(r"news|新闻|新聞", gt + " | " + title, re.I):
        return "国际新闻", c or title
    if re.search(r"NewTV|iHOT|CHC|求索|咪咕|SiTV|黑莓|数字", names + " | " + gt, re.I):
        return "数字频道", title
    if et.CJK.search(title):
        return "地方", title
    return "海外·" + next((n for n, pat in GENRE if re.search(pat, gt, re.I)), "综合"), title


# extract_test's tables fold a family onto one name, which is fine for picking one stream per name but here
# would make these different channels backup urls of each other; they keep their own names.
SIBLING = re.compile(r"CGTN\s*(西语|阿语|法语|俄语|记录|Global)|Arirang\s*(Radio|TV\s*UN)|CNBC\s*Bajar|Bloomberg\s*HT|"
                     r"(龍|龙)(華|华)(?!(戲劇|戏剧))|永夜星河", re.I)


def classify(e):
    """(group, title, country) for one playlist entry. The first rule that matches wins."""
    src, name, tid, gt, tname = e["source"], e["name"], e["tvg_id"], e["group_title"], e["tvg_name"]
    # epg.pw's tvg-name is its own guess at which channel a stream is and is often another one
    # entirely (tvg-name "Animax(HK)" on a cctv-5 feed); the display name is the stream's own.
    if src in EPG and ident(tidy(name)) not in ident(tname):
        tname = ""
    cc = ccode(e)
    title = (tidy(tname) if src in EPG else "") or tidy(name) or tidy(tname) or tid
    g, t = _classify(e, src, name, tname, tid, gt, cc, title)
    if SIBLING.search(title):
        t = title
    k = re.search(r"[48]K\b", title, re.I)
    if k and k.group().upper() not in t.upper():  # the canonical names drop the 4K/8K marker
        t += " " + k.group().upper()
    return g, tidy(t), cc


def ccode(e):
    m = re.search(r"\.([a-z]{2})(?:@|$)", e["tvg_id"], re.I)
    return m.group(1).lower() if m else SRC_CC.get(e["source"], "")


def grank(g):
    return GROUPS.index(g) if g in GROUPS else len(GROUPS)

# ---------------------------------------------------------------- test

def load_results():
    res = {}
    if os.path.exists(JSONL):
        for line in open(JSONL, encoding="utf-8"):
            try:
                r = json.loads(line)
                res[r["key"]] = r
            except ValueError:
                pass  # a run killed mid-write leaves a torn last line
    return res


def pick(urls, tested):
    """What to test this run, tier 1 first, each tier round-robined across hosts."""
    todo = [u for u in urls.values() if u["pre"] is None and u["key"] not in tested]
    if LIMIT:
        per = [et.interleave([u for u in todo if s in u["sources"]], lambda u: u["host"]) for s, _ in SOURCES]
        chosen = {}
        while len(chosen) < LIMIT and any(per):
            for lst in per:
                while lst and lst[0]["key"] in chosen:
                    lst.pop(0)
                if lst and len(chosen) < LIMIT:
                    u = lst.pop(0)
                    chosen[u["key"]] = u
        todo = list(chosen.values())
    return [u for t in (1, 2) for u in et.interleave([u for u in todo if u["tier"] == t], lambda u: u["host"])]


def scan(todo):
    lock, t0, n = threading.Lock(), time.time(), {"done": 0, "ok": 0}
    os.makedirs(et.CACHE, exist_ok=True)
    f = open(JSONL, "a+", encoding="utf-8")
    f.seek(0, 2)
    if f.tell():
        f.seek(f.tell() - 1)
        if f.read(1) != "\n":
            f.write("\n")  # so the next record does not glue onto a torn one

    def write(u, st, pl, seg, sb, hls, codec="", w="", h=""):
        rec = {"key": u["key"], "status": st, "pl_ms": pl, "seg_ms": seg, "seg_bytes": sb, "hls": hls,
               "codec": codec, "w": w, "h": h, "ts": int(time.time())}
        with lock:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n["done"] += 1
            n["ok"] += st.startswith("ok")
            if n["done"] % 200 == 0 or n["done"] == len(todo):
                rate = n["done"] / max(time.time() - t0, 1) * 60
                print("%d/%d tested, %d pass, %.0f urls/min, ETA %.0f min"
                      % (n["done"], len(todo), n["ok"], rate, (len(todo) - n["done"]) / rate), flush=True)

    def probe(u, r):
        try:
            codec, w, h = et.probe_codec(u["url"], u["headers"])
        except Exception as exc:  # left out of the jsonl, so the next run retries it
            return print("  error probing %s: %r" % (u["url"], exc), flush=True)
        st = r[0] if r[4] or codec != "unknown" else "not-video"  # extract_test main()'s rule for non-HLS bytes
        write(u, st, *r[1:], codec, w, h)

    def lane(items):
        for u in items:
            try:
                r = et.test_twice(u)
            except Exception as exc:
                print("  error on %s: %r" % (u["url"], exc), flush=True)
                continue
            if r[0].startswith("ok"):
                probes.submit(probe, u, r)  # ffprobe runs off the lane, so it does not hold one of the host's slots
            else:
                write(u, *r)

    # Three lanes per host, each walking its share of that host's urls: never more than three
    # requests to one host, and no worker parked on a busy one. A per-host semaphore did park
    # them: in the pilot the ~20 s freetv.fun urls at the end of tier 1 took 45 of 48 workers
    # and tier 2 did not start for four minutes.
    by = {}
    for u in todo:
        by.setdefault(u["host"], []).append(u)
    lanes = sorted((lst[i::3] for lst in by.values() for i in range(3) if lst[i::3]), key=lambda l: l[0]["tier"])
    print("testing %d urls on %d hosts with %d workers" % (len(todo), len(by), WORKERS), flush=True)
    with ThreadPoolExecutor(16) as probes:
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(lane, lanes))
    f.close()

# ---------------------------------------------------------------- outputs

def collect(entries, results):
    urls = {}
    for e in entries:
        k = ukey(e)
        u = urls.setdefault(k, {"key": k, "url": e["url"], "headers": e["headers"], "entries": [], "sources": [],
                                "pre": pre_status(e["url"]), "host": urlparse(e["url"]).hostname or ""})
        u["entries"].append(e)
        if e["source"] not in u["sources"]:
            u["sources"].append(e["source"])
    for u in urls.values():
        u["tier"] = 1 if set(u["sources"]) - TIER2 else 2
        r = results.get(u["key"], {})
        u.update(r, status=u["pre"] or r.get("status", "untested"))
        # A url listed under several names takes the most specific group any source gives it; the
        # names that disagree with that pick are kept for channels.csv, not resolved.
        cls = [classify(e) for e in u["entries"]]
        u["cls"] = min(cls, key=lambda c: grank(c[0]))
        u["other"] = [t for t in dict.fromkeys(t for _, t, _ in cls) if ident(t) != ident(u["cls"][1])]
        u["cc"] = u["cls"][2] or next((cc for _, _, cc in cls if cc), "")
    return urls


def verdict(st):
    return ("pass" if st.startswith("ok") else "excluded" if st.startswith("excluded-") else
            "untested" if st in ("untested", "untested-protocol", "ipv6") else "fail")


def channels(urls, cur=()):
    """The passing urls as channels: one per ident, in the group the most specific url gives it. A channel
    of cur (the list the apk ships) matched by name, else by a shared url, takes its title and group."""
    ok = [u for u in urls.values() if u["status"].startswith("ok")]
    # Free-TV files most channels under a country name; its code is whatever .cc that group's tvg-ids agree on.
    seen = {}
    for u in urls.values():
        for e in u["entries"]:
            if e["source"] == 11 and ccode(e):
                seen.setdefault(e["group_title"], Counter())[ccode(e)] += 1
    ftv = {g: n.most_common(1)[0][0] for g, n in seen.items() if n.most_common(1)[0][1] >= 0.9 * sum(n.values())}
    cc = {u["key"]: u["cc"] or next((ftv[e["group_title"]] for e in u["entries"]
                                     if e["source"] == 11 and e["group_title"] in ftv), "") for u in urls.values()}
    by, chs = {}, {}
    for u in ok:
        by.setdefault(ident(u["cls"][1]), []).append(u)
    for k, us in by.items():
        # Latin names like Nickelodeon or ATV are different channels in different countries: split when the
        # urls name two or more, the ones with no country joining the biggest. CJK names are never split.
        parts = {}
        for u in us:
            parts.setdefault(cc[u["key"]], []).append(u)
        known = sorted((p for c, p in parts.items() if c), key=len, reverse=True)
        split = len(known) > 1 and not et.CJK.search(Counter(u["cls"][1] for u in us).most_common(1)[0][0])
        if split:
            known[0] += parts.get("", [])
        for p in known if split else [us]:
            g = min((u["cls"][0] for u in p), key=grank)
            ccs = Counter(cc[u["key"]] for u in p if cc[u["key"]]).most_common(1)
            # The app merges same-name entries into one channel with the FIRST entry's headers, so header-less urls
            # lead; then extract_test's order: h264 ffprobe saw, other known codecs, unknown, hevc/mpeg2; quickest segment
            p.sort(key=lambda u: (bool(u["headers"]), 0 if u.get("codec", "").startswith("h264") else
                                  3 if u.get("codec") in ("hevc", "mpeg2video") else
                                  2 if u.get("codec", "unknown") == "unknown" else 1, u.get("seg_ms", 99999)))
            c = {"group": g, "was": g, "title": Counter(u["cls"][1] for u in p if u["cls"][0] == g).most_common(1)[0][0],
                 "cc": ccs[0][0] if ccs else "", "cur": "", "key": k, "split": split, "all": p, "uris": p[:3],
                 "logo": next((e["logo"] for u in p for e in u["entries"] if e["logo"]), ""),
                 "conflict": list(dict.fromkeys(t for u in p for t in u["other"]))}
            if split:
                c["title"] += " (%s)" % c["cc"].upper()
            chs.setdefault(k, []).append(c)
    bynk, byurl, at, done = {}, {u["url"]: k for k, us in by.items() for u in us}, {}, set()
    for k in by:
        bynk.setdefault(k.replace("卫视", ""), k)
    for u in urls.values():
        at.setdefault(u["url"], []).append(u)
    for find in (lambda c: ident(tidy(c["title"])), lambda c: bynk.get(nk(c["title"])),
                 lambda c: next((byurl[x] for x in c["uris"] if x in byurl), None)):
        for c in cur:  # all name matches before any url match, so a shared url cannot steal a named channel
            free = [ch for ch in chs.get(find(c), []) if not ch["cur"]]
            if c["title"] in done or not free:
                continue
            # Of a name split by country: the part holding most of its urls, then the one in its urls' country, then the biggest.
            mine = Counter(cc[u["key"]] for x in c["uris"] for u in at.get(x, []) if cc[u["key"]])
            ch = max(free, key=lambda ch: (sum(u["url"] in c["uris"] for u in ch["all"]), mine[ch["cc"]], len(ch["all"])))
            ch.update(group=c["group"], title=c["title"], cur=c["title"])
            # The current list's urls were played on the TV; a url that merely passes here can still be the wrong
            # programme (a jdshipin CCTV1 showed a shopping ad), so the verified ones lead, in the list's order.
            old = list(ch["all"])
            ch["all"].sort(key=lambda u: c["uris"].index(u["url"]) if u["url"] in c["uris"] else len(c["uris"]))
            ch.update(uris=ch["all"][:3], moved=ch["all"] != old)
            done.add(c["title"])
    chs = [c for cs in chs.values() for c in cs]
    pos = lambda t: (et.ORDER.index(t) if t in et.ORDER else
                     et.WEISHI.index(t[:-2]) if t.endswith("卫视") and t[:-2] in et.WEISHI else 999)
    return sorted(chs, key=lambda c: (show(c["group"]), c["group"], pos(c["title"]), -len(c["all"]), c["title"]))


def show(g):
    return SHOW.index(g) if g in SHOW else len(SHOW)


def write_m3u(chs, urls, stamp, name, cap=None):
    testable = sum(1 for u in urls.values() if u["pre"] is None)
    tested = sum(1 for u in urls.values() if u["pre"] is None and u["status"] != "untested")
    L = ["#EXTM3U",
         "# 从 26 个公开直播源里批量扫出来、在这台 Mac 上测得能播的频道，生成于 %s。" % stamp,
         "# 测法和 tools/extract_test.py --mac 相同：HLS 要拿到 ≥50 KB 的分片，非 HLS 要 ffprobe 认出编码。",
         "# 只在 Mac 上测过，没在电视上测。出口是路由器代理，落在韩国的 Oracle Cloud 节点，仅 IPv4。",
         "# 源里的 IPv6 地址一条都没测（Mac 和电视都没有 IPv6 路由），所以这里没有它们。",
         "# 能不能播随地区、网络和时间变化，依赖之前请自己重测。",
         "# 同名的相邻条目是同一个频道，后面几条是它的备用地址（%s）。" % ("每个频道最多 %d 条" % cap if cap else "能播的全部列出")]
    if name == "merged-lite.m3u":
        L.append("# 精简版：merged.m3u 里挑出的 %d 个频道。apk 内置频道全部保留；海外·*、国际新闻、体育、纪录片按名单挑；"
                 "地方只留省级和主要城市的电视台，不要广播、景区直播和点播；其余小分组去掉重复、宗教和购物频道；不要 4K/8K 副本。"
                 % len(chs))
    if tested < testable:
        L.append("# 本次只测了 %d / %d 条可测 url，列表不完整。" % (tested, testable))
    for c in chs:
        t = c["title"].replace('"', "'")
        for u in c["all"][:cap]:
            L.append('#EXTINF:-1 tvg-name="%s"%s tvg-logo="%s" group-title="%s",%s'
                     % (t, ' tvg-country="%s"' % c["cc"].upper() if c["cc"] else "", c["logo"], c["group"], t))
            for k, opt in (("User-Agent", "http-user-agent"), ("Referer", "http-referrer")):
                if u["headers"].get(k):
                    L.append("#EXTVLCOPT:%s=%s" % (opt, u["headers"][k]))
            L.append(u["url"])
    open(os.path.join(OUT, name), "w", encoding="utf-8").write("\n".join(L) + "\n")


def write_csv(urls, chs):
    where = {u["key"]: (c["title"], c["group"]) for c in chs for u in c["all"]}
    with open(os.path.join(OUT, "channels.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "new_group", "title", "country", "n_uris", "in_current_list", "merged_variants",
                    "sources", "conflict"])
        for c in chs:
            w.writerow([c["group"], "no" if c["group"] in ORDER else "yes", c["title"], c["cc"].upper(), len(c["all"]),
                        c["cur"], ";".join(dict.fromkeys(e["name"] for u in c["all"] for e in u["entries"])),
                        ";".join("%02d" % s for s in sorted({s for u in c["all"] for s in u["sources"]})),
                        ";".join(c["conflict"])])
    with open(os.path.join(OUT, "results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "group", "url", "sources", "headers_json", "status", "pl_ms", "seg_ms", "seg_bytes",
                    "codec", "w", "h", "verdict"])
        for u in urls.values():
            w.writerow([*where.get(u["key"], (u["cls"][1], u["cls"][0])), u["url"], ";".join("%02d" % s for s in sorted(u["sources"])),
                        json.dumps(u["headers"], ensure_ascii=False), u["status"], u.get("pl_ms", ""),
                        u.get("seg_ms", ""), u.get("seg_bytes", ""), u.get("codec", ""), u.get("w", ""),
                        u.get("h", ""), verdict(u["status"])])


def project(url):
    p = urlparse(url)
    parts = p.path.strip("/").split("/")
    if p.hostname == "raw.githubusercontent.com":
        return "/".join(parts[:2])
    if (p.hostname or "").endswith(".github.io"):
        return p.hostname.split(".")[0] + "/" + parts[0]
    return p.hostname or ""


def write_report(urls, chs, counts, stamp, cur, gone, results):
    dl = json.load(open(STATUS, encoding="utf-8")) if os.path.exists(STATUS) else {}
    vals = list(urls.values())
    testable = [u for u in vals if u["pre"] is None]
    tested = [u for u in testable if u["status"] != "untested"]
    ok = [u for u in tested if u["status"].startswith("ok")]
    ts = sorted(u["ts"] for u in tested if u.get("ts"))
    L = ["# 批量扫描报告", "",
         "- 生成时间：%s。" % stamp,
         "- 测试位置：这台 Mac，协议与 `tools/extract_test.py --mac` 相同，**不是电视**。出口是路由器代理，落在韩国的 "
         "Oracle Cloud 节点，只有 IPv4；结果说明的是这个出口能连上什么，不代表国内家庭宽带或港台线路。",
         "- 源：%d 个地址，其中 12 与 02 完全相同，只下载一次。" % len(SOURCES),
         "- 去重后共 %d 条 url（url 加请求头算一条）：可测 %d，已测 %d，通过 %d%s。"
         % (len(vals), len(testable), len(tested), len(ok),
            "（%.1f%%）" % (100.0 * len(ok) / len(tested)) if tested else ""),
         "- IPv6 字面量 %d 条、rtmp/rtsp 等 %d 条没测：这台 Mac 和电视都没有 IPv6 路由，curl 也测不了 rtmp。"
         % (sum(u["status"] == "ipv6" for u in vals), sum(u["status"] == "untested-protocol" for u in vals)),
         "- 结果：`merged.m3u` %d 个频道、%d 条 uri（能播的全部），`available.m3u` 每个频道最多 3 条、共 %d 条；"
         "每个频道的明细在 `channels.csv`，每条 url 的在 `results.csv`。"
         % (len(chs), sum(len(c["all"]) for c in chs), sum(len(c["uris"]) for c in chs))]
    drop = Counter(s for ss in gone.values() for s in ss)
    most = [i for i in sorted(drop) if drop[i] > counts.get(i, 0)]
    L.append("- freetv.fun（stream1 和 t 两个子域）的 %d 条 url 已从源中删除：该主机约 20 秒才响应，超过测试协议的 10 秒超时；"
             "删除前实测 %d 条，通过 %d 条。源 %s%s的地址几乎全在这个主机上，删除后分别只剩 %s 个条目，所以基本没有贡献频道。"
             % (len(gone), sum(k in results for k in gone), sum(results[k]["status"].startswith("ok") for k in gone if k in results),
                "、".join("%02d" % i for i in most), "（epg.pw 各地区列表）" if set(most) <= EPG else "",
                "、".join(str(counts.get(i, 0)) for i in most)))
    if ts:
        span = max(ts[-1] - ts[0], 1)
        L.append("- 测试记录时间跨度 %s 到 %s，平均 %.0f 条/分钟（含 ffprobe）。"
                 % (time.strftime("%m-%d %H:%M", time.localtime(ts[0])), time.strftime("%m-%d %H:%M", time.localtime(ts[-1])),
                    len(ts) * 60.0 / span))
    if len(tested) < len(testable):
        L.append("- **还有 %d 条没测，下面所有数字只反映已测的部分。**" % (len(testable) - len(tested)))

    # ------------------------------------------- merging
    passing = [u for u in vals if u["status"].startswith("ok")]
    hit = {(c["group"].startswith("海外·") or c["group"] in PICK_GROUPS, c["title"].casefold()) for c in chs}
    miss = sorted(t for k, t in PICKS.items() if (True, k) not in hit) + sorted(t for k, t in DROP.items() if (False, k) not in hit)
    if miss:
        print("PICKS/DROP titles with no channel in their groups: " + ", ".join(miss), file=sys.stderr)
    mc = {c["cur"]: c for c in chs if c["cur"]}
    n = Counter(len(c["all"]) for c in chs)
    L += ["", "## 合并", "",
          "能播的 url 按名字合并成频道：名字去掉画质、编码、[BD]、「HK」、（备用）这类标记后，只按字母（任何文字）和数字比，"
          "简繁、大小写不分，`+` 记作 plus。一个频道只有一个分组，取它各条 url 里最具体的那个；拉丁字母名字的 url "
          "若来自两个以上国家（tvg-id 后缀），按国家拆开并在名字后加 (国家码)。现有列表里的频道（按名字，对不上再按 url）"
          "沿用现有的名字和分组；名字按国家拆开了的，取装着它的 url 最多的那一份。", "",
          "- 通过的 url %d 条。按旧键（分组 + 只留 ASCII 字母数字和汉字的名字）算是 %d 个频道；按新规则合并成 %d 个名字，"
          "再按国家拆开，最后 %d 个。旧键把没有拉丁字母和数字的俄文、阿拉伯文等名字全算成同一个，所以旧数偏少。"
          % (len(passing), len({(u["cls"][0], et.merge_key(et.simp(u["cls"][1]))) for u in passing}),
             len({c["key"] for c in chs}), len(chs)),
          "- 有 ≥2 条 uri 的频道 %d 个。每个频道的 uri 数：%s。"
          % (sum(len(c["all"]) > 1 for c in chs), "，".join("%s 条 %d 个" % (lab, sum(v for k, v in n.items() if lo <= k <= hi))
                                                         for lab, lo, hi in (("1", 1, 1), ("2", 2, 2), ("3", 3, 3), ("4–5", 4, 5),
                                                                             ("6–10", 6, 10), (">10", 11, 1 << 30)))),
          "- 按国家拆开的名字 %d 个，拆成 %d 个频道。"
          % (len({c["key"] for c in chs if c["split"]}), sum(c["split"] for c in chs)),
          "- 同一条 url 在不同源里叫不同名字的 %d 条（涉及 %d 个频道）：按最具体的分组取一个名字，其余记在 channels.csv 的 conflict 列。"
          % (sum(bool(u["other"]) for u in passing), sum(bool(c["conflict"]) for c in chs)),
          "- 不带请求头的 uri 排在前面；仍有 %d 个频道里的 %d 条 uri "
          "需要的请求头和第一条不同：v2.1.3 及以前的 app 整个频道只用第一条的请求头，这些 uri 会带错或不带。"
          % (sum(any(u["headers"] != c["all"][0]["headers"] for u in c["all"]) for c in chs),
             sum(u["headers"] != c["all"][0]["headers"] for c in chs for u in c["all"])),
          "- 现有列表里的频道把 apk 列表中（在电视上真播过）的 uri 排到最前：%d 个频道的顺序因此变了。"
          % sum(bool(c.get("moved")) for c in chs),
          "- 精简版 `merged-lite.m3u`：%d 个频道、%d 条 uri。apk 内置频道全部保留；海外·*、国际新闻、体育、纪录片只留 `PICKS` "
          "按名字挑的；地方只留省级和主要城市的电视台，不要广播、景区直播和点播；其余分组去掉 `DROP` 里的重复、宗教和购物频道；"
          "不要 4K/8K 副本%s。"
          % (sum(map(lite, chs)), sum(len(c["all"]) for c in chs if lite(c)), "。名单里没对上的：" + "、".join(miss) if miss else ""),
          "- 现有列表 %d 个频道中 %d 个在新列表里、分组一致 %d 个（不靠现有列表覆盖、分类器自己就一致的 %d 个）%s。"
          % (len(cur), sum(c["title"] in mc for c in cur), sum(mc[c["title"]]["group"] == c["group"] for c in cur if c["title"] in mc),
             sum(mc[c["title"]]["was"] == c["group"] for c in cur if c["title"] in mc),
             "；没找到：" + "、".join(c["title"] for c in cur if c["title"] not in mc) if len(mc) < len(cur) else ""),
          "", "### 分组", "", "「新建」是现有列表里没有的分组。", "",
          "| 分组 | 新建 | 频道 | uri（merged.m3u） | uri（available.m3u） |", "| --- | --- | --- | --- | --- |"]
    for g in sorted({c["group"] for c in chs}, key=lambda g: (show(g), g)):
        cs = [c for c in chs if c["group"] == g]
        L.append("| %s | %s | %d | %d | %d |" % (g, "" if g in ORDER else "是", len(cs), sum(len(c["all"]) for c in cs),
                                              sum(len(c["uris"]) for c in cs)))
    L += ["", "### uri 最多的 30 个频道", "", "| 分组 | 频道 | uri | 合并进来的原名 |", "| --- | --- | --- | --- |"]
    for c in sorted(chs, key=lambda c: -len(c["all"]))[:30]:
        L.append("| %s | %s | %d | %s |" % (c["group"], c["title"], len(c["all"]),
                                           "、".join(dict.fromkeys(e["name"] for u in c["all"] for e in u["entries"]))))

    only = {}
    for c in chs:
        srcs = {s for u in c["all"] for s in u["sources"]}
        if len(srcs) == 1:
            s = srcs.pop()
            only[s] = only.get(s, 0) + 1
    L += ["", "## 各源情况", "",
          "「独有频道」是 merged.m3u 里只有这一个源提供了可用 url 的频道数。", "",
          "| # | 地址 | 下载 | 条目 | 去重 url | 已测 | 通过 | 通过率 | 独有频道 |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, url in SOURCES:
        mine = [u for u in vals if i in u["sources"]]
        t = [u for u in mine if u["pre"] is None and u["status"] != "untested"]
        p = sum(u["status"].startswith("ok") for u in t)
        L.append("| %02d | %s | %s | %s | %d | %d | %d | %s | %d |"
                 % (i, url, dl.get(str(i), "未记录"), counts.get(i, "—"), len(mine), len(t), p,
                    "%.0f%%" % (100.0 * p / len(t)) if t else "—", only.get(i, 0)))

    L += ["", "## 状态分布", "", "| 状态 | url 数 |", "| --- | --- |"]
    tally = {}
    for u in vals:
        tally[u["status"]] = tally.get(u["status"], 0) + 1
    L += ["| %s | %d |" % kv for kv in sorted(tally.items(), key=lambda kv: -kv[1])]

    # ------------------------------------------- comparison with the list the apk ships
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read().split("## 直播源来源")[1].split("\n## ")[0]
    used = [u for _, u in et.SOURCES]
    L += ["", "## 与现有列表对比", "", "### 源列表", "",
          "对照 README「直播源来源」表，也就是 `tools/extract_test.py` 实际下载的 %d 个源。" % len(used), "",
          "| # | 地址 | 关系 |", "| --- | --- | --- |"]
    for i, url in SOURCES:
        rel = ("完全相同" if url in used else
               "同项目（%s）不同文件" % project(url) if project(url) in {project(u) for u in used} else
               "README 提到过（上游 sources.txt 列的社区列表），但没用过" if project(url) in readme else "此前未用")
        L.append("| %02d | %s | %s |" % (i, url, rel))
    mine = set(SRC_URL.values())
    L += ["", "README 里用过、这次的 26 个地址里没有的：", ""]
    L += ["- %s" % u for u in used if u not in mine]
    L += ["- 上游 lizongying/my-tv-0 的内置列表（`playlists/upstream/`，gua64 解码后）",
          "- fengshows 官方 API（凤凰卫视三个台的签名 FLV 地址，app 内部路由用）"]

    by_url = {}
    for u in vals:
        by_url.setdefault(u["url"], []).append(u)
    new = {}
    for c in chs:
        new.setdefault(nk(c["title"]), set()).update(u["url"] for u in c["uris"])
    rows, summ, curls = [], {"相同": 0, "重叠": 0, "不同": 0, "新列表里没有": 0}, []
    for c in cur:
        mineu = [x for x in c["uris"] if not x.startswith(FH.split("%s")[0])]
        got = new.get(nk(c["title"]))
        rel = ("新列表里没有" if got is None else "相同" if got == set(mineu) else
               "重叠" if got & set(mineu) else "不同")
        summ[rel] += 1
        for j, x in enumerate(c["uris"]):
            if x.startswith(FH.split("%s")[0]):
                where, today = "—", "app 内部路由，不测"
            else:
                us = by_url.get(x, [])
                where = ", ".join("%02d" % s for s in sorted({s for u in us for s in u["sources"]})) or "都没有"
                today = next((u["status"] for u in us if u["status"].startswith("ok")), us[0]["status"] if us else "—")
                curls.append((bool(us), today))
            rows.append("| %s | %s | %s | %s | %s | %s |" % (c["group"] if not j else "", c["title"] if not j else "",
                                                          rel if not j else "", x, where, today))
    L += ["", "### 频道", "",
          "现有列表是 apk 实际播的那份（`playlists/channels.json` 经 `merge.py` 处理，和 `res/raw/channels.txt` 一致），"
          "%d 个频道、%d 条 uri。凤凰卫视三个台的第一条 uri 是 app 内部的本地转发 `http://127.0.0.1:34567/fh/<id>.flv`，"
          "只在 app 里有效，从不测试。" % (len(cur), sum(len(c["uris"]) for c in cur)), "",
          "- 按频道名对上 available.m3u：uri 完全相同 %d，有重叠 %d，完全不同 %d，新列表里没有 %d。"
          % (summ["相同"], summ["重叠"], summ["不同"], summ["新列表里没有"]),
          "- 除凤凰的本地路由外 %d 条 uri，在这 26 个源里找得到 %d 条；今天测过 %d 条，通过 %d 条。"
          % (len(curls), sum(f for f, _ in curls), sum(t not in ("untested", "—") for _, t in curls),
             sum(t.startswith("ok") for _, t in curls)), "",
          "| 分组 | 频道 | 对比 | uri | 出现在哪些源 | 今天的状态 |", "| --- | --- | --- | --- | --- | --- |"] + rows
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    if "--report-only" not in sys.argv:
        download()
    entries, counts, gone = load()
    results = load_results()
    urls = collect(entries, results)
    if "--report-only" not in sys.argv:
        todo = pick(urls, results)
        print("%d distinct urls, %d testable, %d already in the jsonl"
              % (len(urls), sum(u["pre"] is None for u in urls.values()), len(results)), flush=True)
        scan(todo)
        results = load_results()
        urls = collect(entries, results)
    os.makedirs(OUT, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    cur = merge(json.load(open(os.path.join(et.DATA, "channels.json"), encoding="utf-8")))
    chs = channels(urls, cur)
    write_m3u(chs, urls, stamp, "merged.m3u")
    write_m3u([c for c in chs if lite(c)], urls, stamp, "merged-lite.m3u")
    write_m3u(chs, urls, stamp, "available.m3u", 3)
    write_csv(urls, chs)
    write_report(urls, chs, counts, stamp, cur, gone, results)
    print("%d channels, %d uris -> %s" % (len(chs), sum(len(c["all"]) for c in chs), OUT))

# ------------------------------------------------------------------ selftest

def selftest():
    t = parse_txt("央视频道,#genre#\nCCTV1,http://a/1.m3u8\n\n"
                  "嵊州新闻,http://b/x.m3u8?zz#http://b/y.m3u8$备用\n"
                  "更新时间,#genre#\n2026-09-17 12:26:35,https://v/x.mp4\n", 23)
    assert [(e["name"], e["group_title"], e["url"]) for e in t] == [
        ("CCTV1", "央视频道", "http://a/1.m3u8"), ("嵊州新闻", "央视频道", "http://b/x.m3u8?zz"),
        ("嵊州新闻", "央视频道", "http://b/y.m3u8"), ("2026-09-17 12:26:35", "更新时间", "https://v/x.mp4")], t
    assert [keep(e) for e in t] == [True, True, True, False]
    ent = lambda name, url="http://h/a.m3u8", tid="", tn="", gt="", src=18: {
        "name": name, "tvg_id": tid, "tvg_name": tn, "group_title": gt, "source": src, "url": url,
        "headers": {}, "logo": ""}
    assert not keep(ent("2026-08-27 14:06:22", gt="🕘️更新时间", tid="CCTV-1"))
    assert not keep(ent("2026-09-17 12:26:35", tid="更新时间", src=24))
    assert not keep(ent("维护时间：2025-1-15#佛系维护...", gt="•温馨「提示」", src=15))
    assert not keep(ent("公告说明：IPV6 暂无", src=15)) and not keep(ent("X", url="[NO PUBLIC STREAM]", src=11))
    assert not keep(ent("北京影视", url='豫",北京影视', src=26))
    assert keep(ent("CCTV-1", gt="📺央视频道")) and keep(ent("J SPORTS", url="https://n/pxx.php?shk_cid=bs08#.m3u8"))
    # Free-TV really has "#" inside a url; only the txt parser splits on it.
    e = et.parse_m3u('#EXTINF:-1 group-title="日本",W\nhttps://n/pxx.php?id=bs08#.m3u8\n', 11)
    assert e[0]["url"] == "https://n/pxx.php?id=bs08#.m3u8"
    assert pre_status("http://[2409:8087::2]:6060/a.m3u8") == "ipv6"
    assert pre_status("rtmp://h/live") == "untested-protocol"
    assert pre_status("http://127.0.0.1:34567/fh/x.flv") == "excluded-lan"
    assert pre_status("http://192.168.1.2/a") == "excluded-lan" and pre_status("http://localhost/a") == "excluded-lan"
    assert pre_status("https://www.youtube.com/watch?v=x") == "excluded-host"
    assert pre_status("https://tve.turner.com/cnn_slate/x.m3u8") == "excluded-slate"
    assert pre_status("http://74.91.26.218:82/live/cctv1hd.m3u8") is None
    cl = lambda *a, **k: classify(ent(*a, **k))[:2]
    assert cl("CCTV-13 新闻") == ("央视", "CCTV13 新闻")
    assert cl("CCTV-4K 超高清") == ("央视", "CCTV-4K"), cl("CCTV-4K 超高清")
    assert cl("CGTN Arabic", tid="CGTNArabic.cn") == ("央视", "CGTN Arabic")
    assert cl("凤凰中文", gt="🌊港·澳·台") == ("凤凰", "凤凰卫视中文台")
    assert cl("湖南卫视高清") == ("卫视", "湖南卫视") and cl("湖南卫视 4K") == ("卫视", "湖南卫视 4K")
    assert cl("澳门卫视", gt="港澳台频道") == ("港澳台", "澳门卫视") and cl("無線衛星亞洲台")[0] == "港澳台"
    assert cl("双辽", gt="纪录频道", src=24) == ("地方", "双辽") and cl("睛彩广场舞", gt="🏀体育频道")[0] == "地方"
    assert cl("特种兵之火凤凰", gt="电视剧频道")[0] == "地方" and cl("福建漳州醉美沙滩翡翠湾")[0] == "地方"
    assert cl("WCETV Digital Channel 31.8", tid="WCETVDigitalChannel318.us@SD", src=2)[0] == "海外·综合"
    assert cl("三沙卫视") == ("卫视", "三沙卫视") and cl("「中」凤凰传奇-月亮之上", gt="•MTV")[0] == "地方"
    assert cl("翡翠台", src=21) == ("港台新闻", "翡翠台") and cl("HOY 78", src=21) == ("港澳台", "HOY 78")
    assert cl("[BD]澳视澳门", tn="澳視澳門", src=6) == ("港台综艺", "澳視澳門") and cl("龍華卡通台")[1] == "龍華卡通台"
    assert cl("[BD]cna", tn="CNA", src=9) == ("新马", "CNA")
    assert cl("[BD]cctv-9纪录", tn="Animax(HK)", src=5)[0] == "央视"
    assert cl("NHK総合", tid="NHKG.jp@SD", src=11)[0] == "日本"
    assert cl("广东体育", gt="🏀体育频道") == ("体育", "广东体育")
    assert cl("ESPN (1080p)", tid="ESPN.us@SD", gt="Sports", src=2) == ("体育", "ESPN")
    assert cl("Discovery Channel", tid="DiscoveryChannel.us@SD", src=2) == ("纪录片", "Discovery Channel")
    assert cl("BBC News (1080p) [Geo-blocked]", tid="BBCNews.uk@SD", gt="News", src=2) == ("国际新闻", "BBC News")
    assert cl("NewTV动作电影") == ("数字频道", "NewTV动作电影")
    assert cl("嵊州新闻综合", src=23) == ("地方", "嵊州新闻综合")
    assert cl("00s Replay", tid="00sReplay.us@SD", gt="Movies", src=2) == ("海外·电影", "00s Replay")
    assert cl("Kanali 7 Ⓢ", tid="Kanali7.al", gt="Albania", src=11) == ("海外·综合", "Kanali 7")
    assert cl("ABC15 Phoenix", tid="KNXV.us@SD", gt="News", src=2) == ("国际新闻", "ABC15 Phoenix")
    assert classify(ent("CNA", tid="CNA.sg@SD", src=2))[2] == "sg"
    assert ident(tidy("CCTV4K")) != ident(tidy("CCTV4")) and ident(tidy("湖南卫视 HD")) == ident(tidy("湖南衛視高清"))
    assert ident(tidy("BBC News (1080p) [Geo-blocked]")) == ident("BBC News")
    assert project(SRC_URL[19]) == "Guovin/iptv-api" and project(SRC_URL[8]) == "iptv-org/iptv"
    assert slow(ent("x", url="http://stream1.freetv.fun/x.m3u8")) and not keep(ent("x", url="http://stream1.freetv.fun/x.m3u8"))
    assert keep(ent("x", url="http://www.freetv.top/x.m3u8")) and keep(ent("x", url="http://notfreetv.fun/x.m3u8"))

    # names
    assert ident("Губерния") and ident("Самара") and ident("Губерния") != ident("Самара")
    assert ident(tidy("CCTV5+")) != ident(tidy("CCTV5")) and ident("ETV Plus") == ident("ETV+")
    assert ident(tidy("CCTV4K")) != ident(tidy("CCTV4")) and ident("DW Español") == ident("DW Espanol") != ident("DW")
    assert ident("ガイア") != ident("カイア") and ident("ＮＨＫ") == ident("NHK")
    assert ident(tidy("CCTV-1 [BD] 高清")) == ident("CCTV1") and ident(tidy("「US」 Newsma xTV")) == ident("Newsmax TV")
    assert ident(tidy("半岛新闻「阿拉伯」")) != ident(tidy("半岛新闻")) and tidy("Sky News Arabia (Portrait)") == "Sky News Arabia (Portrait)"
    assert tidy("TVB翡翠台（备用）") == "TVB翡翠台" and tidy("BBC News (1080p) (HEVC)") == "BBC News" and tidy("WayPoint TV | HD 720p") == "WayPoint TV"
    assert tidy("3HD") == "3HD" and tidy("Caracol HD2") == "Caracol HD2" and tidy("2M Monde") == "2M Monde"

    # channels, built from fake entries through collect() so every field channels() reads is real
    def chans(es, cur=()):
        return channels(collect(es, {ukey(e): {"status": "ok"} for e in es}), cur)
    ch = chans([ent("Pluto TV Paranormal", "http://h/1", gt="Documentary", src=2),
                ent("Pluto TV Paranormal", "http://h/2", gt="Movies", src=2)])
    assert [(c["group"], c["title"], len(c["all"])) for c in ch] == [("纪录片", "Pluto TV Paranormal", 2)], ch
    ch = chans([dict(ent("CCTV1", "http://h/ua"), headers={"User-Agent": "x"}), ent("CCTV1", "http://h/plain")])
    assert [u["url"] for u in ch[0]["all"]] == ["http://h/plain", "http://h/ua"], ch
    ch = chans([ent("CCTV1", "http://h/a"), ent("CCTV1", "http://h/b")], [{"group": "央视", "title": "CCTV1 综合", "uris": ["http://h/b"]}])
    assert [u["url"] for u in ch[0]["all"]] == ["http://h/b", "http://h/a"] and ch[0]["uris"][0]["url"] == "http://h/b", ch
    nick = [ent("Nickelodeon", "http://h/1", tid="Nick.us"), ent("Nickelodeon", "http://h/2", tid="Nick.us@SD"),
            ent("Nickelodeon", "http://h/3", tid="Nick.ro"), ent("Nickelodeon", "http://h/4")]
    ch = chans(nick)
    assert sorted((c["title"], len(c["all"]), c["cc"]) for c in ch) == [("Nickelodeon (RO)", 1, "ro"), ("Nickelodeon (US)", 3, "us")], ch
    ch = chans(nick[:2] + nick[3:])
    assert [(c["title"], len(c["all"]), c["cc"]) for c in ch] == [("Nickelodeon", 3, "us")], ch
    assert len(chans([ent("東森新聞", "http://h/1", tid="x.tw"), ent("東森新聞", "http://h/2", tid="x.us")])) == 1
    ch = chans([ent("HOY 78", "http://h/1", src=21), ent("翡翠台", "http://h/2", src=21)],
               [{"group": "港台新闻", "title": "HOY 78台", "uris": ["http://h/1"]}])
    assert [(c["group"], c["title"], c["cur"], c["was"]) for c in ch] == [  # 翡翠台 is in et.ORDER, so first
        ("港台新闻", "翡翠台", "", "港台新闻"), ("港台新闻", "HOY 78台", "HOY 78台", "港澳台")], ch
    assert [lite({"group": g, "title": t, "cur": cur}) for g, t, cur in (
        ("体育", "Eurosport", "Eurosport"), ("卫视", "湖南卫视 4K", ""), ("体育", "五星体育", ""), ("体育", "Eurosport", ""),
        ("央视", "CCTV-Billiards", ""), ("央视", "CCTV1 综合", ""), ("地方", "广东珠江", ""), ("地方", "山东教育", ""),
        ("地方", "深圳飞扬971", ""), ("地方", "福建武夷山玉女峰", ""), ("地方", "嵊州新闻综合", ""), ("地方", "浙江钱江频道", ""),
        ("海外·电影", "HBO Movies", ""), ("海外·综合", "sbs", ""), ("海外·电影", "HBO Movies 2", ""))] == [
        True, False, True, False, False, True, True, True, False, False, False, False, True, True, False]
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]  # an unknown flag used to fall through to a full scan and re-download every source
    flags = {x for i, x in enumerate(a) if not (x.isdigit() and i and a[i - 1] in ("--workers", "--limit"))}
    if flags - {"--selftest", "--report-only", "--workers", "--limit"}:
        print(__doc__)
        sys.exit(0 if flags & {"-h", "--help"} else 2)
    selftest() if "--selftest" in sys.argv else main()
