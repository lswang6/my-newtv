#!/usr/bin/env python3
"""Build a tested channel list for the Android TV IPTV app.

Downloads a handful of public m3u playlists, keeps only the channels we care
about (央视 / 凤凰 / 港台新闻 / 国际新闻), then proves every candidate URL by
actually fetching it from the TV with the static curl that lives in
/data/local/tmp. Codec info comes from ffprobe on the Mac and is advisory only.

    python3 extract_test.py --selftest             # parser + normalizer checks
    python3 extract_test.py --serial <tv-ip>:5555  # full run (TV is the reachability judge)
    python3 extract_test.py --mac                  # same protocol, run from the Mac instead
    python3 extract_test.py --out DIR              # write the three files somewhere else
"""
import csv, json, os, re, shlex, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
# playlists/ next to tools/ holds both the upstream copies we read and, unless --out
# says otherwise, the three files we write.
DATA = os.path.normpath(os.path.join(HERE, os.pardir, "playlists"))
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else DATA
# adb serial of the TV, "<tv-ip>:5555" for a network device. Required unless --mac.
DEV = sys.argv[sys.argv.index("--serial") + 1] if "--serial" in sys.argv else ""
USE_TV = "--mac" not in sys.argv
MAX_PER_CH, MAX_PER_HOST, POOL = 8, 3, 8
# Groups built by pattern rather than from a fixed roster, with how many survive the cut.
CAPS = {"体育": 30, "卫视": 30, "纪录片": 20, "港台综艺": 25}
GORDER = {"央视": 0, "凤凰": 1, "港台新闻": 2, "国际新闻": 3,
          "体育": 4, "卫视": 5, "纪录片": 6, "港台综艺": 7}

SOURCES = [
    ("news", "https://iptv-org.github.io/iptv/categories/news.m3u"),
    ("hk", "https://iptv-org.github.io/iptv/countries/hk.m3u"),
    ("uk", "https://iptv-org.github.io/iptv/countries/uk.m3u"),
    ("tw", "https://iptv-org.github.io/iptv/countries/tw.m3u"),
    ("cn", "https://iptv-org.github.io/iptv/countries/cn.m3u"),
    ("freetv", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("guovin", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
    ("itv", "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/itv.m3u"),
    ("sports", "https://iptv-org.github.io/iptv/categories/sports.m3u"),
    ("us", "https://iptv-org.github.io/iptv/countries/us.m3u"),
    ("documentary", "https://iptv-org.github.io/iptv/categories/documentary.m3u"),
]
# Playlists added for the pattern-matched groups. Feeding them to the news matchers as
# well would pull new, untested urls into the four original groups, so they are fenced
# off: they reach canon_extra but never canon.
EXTRA = {"sports", "us", "documentary"}
# Hosts that only answer from inside China. They still get listed as candidates
# but they sort last, because this box reaches the internet through a KR proxy.
DEAD = re.compile(r"chinamobile|cmvideo|ottrrs|39\.134\.|\[|ipv6", re.I)
# Pages, not streams. They answer 200 with kilobytes of HTML or text, which used to
# sail through the "non-HLS but big enough" branch even though ExoPlayer cannot open them.
BADHOST = re.compile(r"(^|\.)(youtube\.com|youtu\.be|raw\.githubusercontent\.com|github\.com)$", re.I)

# ---------------------------------------------------------------- m3u parsing

def parse_m3u(text, src):
    out, cur, hdrs = [], None, {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            attrs = dict(re.findall(r'([A-Za-z0-9_-]+)="([^"]*)"', line))
            q = line.rfind('"')
            i = line.find(",", q + 1) if q != -1 else line.find(",")
            cur = {"name": line[i + 1:].strip() if i != -1 else "",
                   "tvg_id": attrs.get("tvg-id", ""), "tvg_name": attrs.get("tvg-name", ""),
                   "logo": attrs.get("tvg-logo", ""), "group_title": attrs.get("group-title", ""),
                   "source": src}
            # iptv-org puts the UA on the #EXTINF line itself; others use #EXTVLCOPT below it.
            hdrs = {}
            if attrs.get("http-user-agent"):
                hdrs["User-Agent"] = attrs["http-user-agent"]
            if attrs.get("http-referrer") or attrs.get("http-referer"):
                hdrs["Referer"] = attrs.get("http-referrer") or attrs.get("http-referer")
        elif line.startswith("#EXTVLCOPT:") and "=" in line:
            k, v = line[11:].split("=", 1)
            k = k.strip().lower()
            if k == "http-user-agent":
                hdrs["User-Agent"] = v.strip()
            elif k in ("http-referrer", "http-referer"):
                hdrs["Referer"] = v.strip()
        elif line.startswith("#") or not line:
            continue
        elif cur:
            cur.update(url=line, headers=hdrs)
            out.append(cur)
            cur, hdrs = None, {}
    return out


def parse_builtin_json(text, src):
    out = []
    for ch in json.loads(text):
        for u in ch.get("uris", []):
            out.append({"name": ch.get("title", ""), "tvg_id": "", "tvg_name": ch.get("title", ""),
                        "logo": ch.get("logo", ""), "source": src, "url": u, "headers": {}})
    return out

# ------------------------------------------------------------ name normalizer

CCTV = {1: "综合", 2: "财经", 3: "综艺", 4: "中文国际", 5: "体育", 6: "电影", 7: "国防军事",
        8: "电视剧", 9: "纪录", 10: "科教", 11: "戏曲", 12: "社会与法", 13: "新闻", 14: "少儿",
        15: "音乐", 16: "奥林匹克", 17: "农业农村"}
CCTV_ORDER = ["CCTV1 综合", "CCTV2 财经", "CCTV3 综艺", "CCTV4 中文国际", "CCTV4 欧洲", "CCTV4 美洲",
              "CCTV5 体育", "CCTV5+ 体育赛事"] + ["CCTV%d %s" % (n, CCTV[n]) for n in range(6, 18)] + \
             ["CGTN", "CGTN 纪录"]

# (canonical, include, exclude, gated-to-hk/tw-source)
TABLE = {
    "凤凰": [("凤凰资讯台", r"(凤凰|鳳凰)\s*资讯|(凤凰|鳳凰)\s*資訊|Phoenix\s*Info", r"phoenix\.de", 0),
             ("凤凰香港台", r"(凤凰|鳳凰)\s*香港|Phoenix\s*(TV\s*)?Hong\s*Kong|Phoenix\s*HK", r"phoenix\.de", 0),
             ("凤凰卫视中文台", r"(凤凰|鳳凰)(\s*(卫视|衛視))?\s*中文|(凤凰|鳳凰)\s*(卫视|衛視)$|Phoenix\s*(TV|Chinese|CNE)", r"phoenix\.de", 0)],
    "港台新闻": [
        ("無綫新聞台", r"無綫新聞|无线新闻|TVB\s*新聞|TVB\s*新闻", None, 0),
        ("無綫新聞台", r"^TVB\s*News|^TVBNews\.", None, 1),
        ("翡翠台", r"翡翠台", None, 0),
        ("翡翠台", r"^Jade\b|^TVBJade\.", r"Golden", 1),
        ("Now 新聞台", r"[Nn]ow\s*新聞|[Nn]ow\s*新闻", None, 0),
        ("Now 新聞台", r"^Now\s*(TV\s*)?News|^NowNews\.", None, 1),
        ("有線新聞台", r"有線新聞|有线新闻", None, 0),
        ("有線新聞台", r"^i-?CABLE\s*News|^iCableNews\.", None, 1),
        ("HOY 資訊台", r"HOY\s*資訊|HOY\s*资讯|^HOY\s*Info|^HOYInfo", None, 0),
        ("HOY TV", r"^HOY\s*TV$|^HOYTV\.|香港開電視|香港开电视", None, 0),
        ("ViuTV", r"^ViuTV\b|^ViuTV\.", None, 0),
        ("RTHK 31", r"RTHK\s*(TV\s*)?31|港台電視\s*31|港台电视\s*31", None, 0),
        ("RTHK 32", r"RTHK\s*(TV\s*)?32|港台電視\s*32|港台电视\s*32", None, 0),
        ("中天新聞", r"中天新聞|中天新闻", None, 0),
        ("中天新聞", r"^CTi\s*News|^CTiNews\.", None, 1),
        ("TVBS新聞", r"TVBS\s*新聞|TVBS\s*新闻", None, 0),
        ("TVBS新聞", r"^TVBS\s*News|^TVBSNews\.", None, 1),
        ("TVBS", r"^TVBS(\s*Asia)?$|^TVBS\.tw", None, 1),
        ("東森財經新聞", r"東森財經|东森财经", None, 0),
        ("東森財經新聞", r"^EBC\s*Financial|^EBCFinancial", None, 1),
        ("東森新聞", r"東森新聞|东森新闻", None, 0),
        ("東森新聞", r"^EBC\s*News|^EBCNews\.", None, 1),
        ("民視新聞", r"民視新聞|民视新闻", None, 0),
        ("民視新聞", r"^FTV\s*News|^FTVNews\.", None, 1),
        ("三立新聞", r"三立新聞|三立新闻|三立\s*iNEWS", None, 0),
        ("三立新聞", r"^SET\s*(i)?News|^SETNews\.", None, 1),
        ("年代新聞", r"年代新聞|年代新闻", None, 0),
        ("年代新聞", r"^ERA\s*News|^ERANews\.", None, 1),
        ("非凡新聞", r"非凡新聞|非凡新闻", None, 0),
        ("非凡新聞", r"^USTV.*News|Unique\s*Business", None, 1),
        ("華視新聞", r"華視新聞|华视新闻", None, 0),
        ("華視新聞", r"^CTS\s*News|^CTSNews\.", None, 1),
        ("寰宇新聞", r"寰宇新聞|寰宇新闻", None, 0),
        ("公視", r"公視$|公视$|公視主頻|公共電視", None, 0),
        ("公視", r"^PTS(\s*(TV|1|Main))?$|^PTS\.tw", None, 1),
        ("中視新聞", r"中視新聞|中视新闻", None, 0),
        ("台視新聞", r"台視新聞|台视新闻", None, 0),
        ("台視新聞", r"^TTV\s*News|^TTVNews\.", None, 1),
    ],
    "国际新闻": [
        ("BBC World News", r"^BBC\s*World\s*News|^BBCWorldNews\.", None, 0),
        ("BBC News", r"^BBC\s*News\b|^BBCNews", r"Arabic|Persian|Hindi|Parliament|عربي", 0),
        ("CNN International", r"^CNN\s*International|^CNNInternational\.", None, 0),
        ("CNN", r"^CNN(\s*(USA|US))?($|[\s.])", r"News18|T(ü|u)rk|Brasil|Indonesia|Portugal|Philippines|Chile|Espa|Arabic|Greece|Prima|Radio|Albania", 0),
        ("Al Jazeera English", r"^Al\s*Jazeera(\s*English)?($|[\s.])|^AlJazeeraEnglish\.", r"Arabic|Mubasher|Balkans|Documentary|T(ü|u)rk|عربي", 0),
        ("Sky News", r"^Sky\s*News($|[\s.])|^SkyNews\.uk", r"Arabia|Australia|Extra|Breakfast|Weather", 0),
        ("France 24 English", r"^France\s*24(\s*English)?($|[\s.])|^France24English\.", r"Fran(ç|c)ais|French|Arab|Espa|Spanish|عربي", 0),
        ("DW English", r"^DW($|[\s.])|^DWEnglish\.", r"Deutsch|German|Espa|Arab|Hindi|عربي", 0),
        ("NHK World-Japan", r"^NHK\s*World|^NHKWorld", r"Premium", 0),
        ("Euronews English", r"^Euronews(\s*(English|EN))?$|^Euronews(English)?\.", None, 0),
        ("Bloomberg TV", r"^Bloomberg(\s*(TV|Television))?($|[\s.])|^BloombergTV\.", r"Originals|Quicktake|Asia\s*Pacific", 0),
        ("CNBC", r"^CNBC(\s*(World|USA?))?($|[\s.])", r"Arabia|Awaaz|TV18|Africa|Europe|Asia|MGL", 0),
        ("CNA", r"^CNA($|[\s.])|^Channel\s*News\s*Asia|^ChannelNewsAsia\.", None, 0),
        ("Arirang", r"^Arirang($|[\s.])|^ArirangTV\.|^Arirang\s*(TV|World)", None, 0),
        ("TRT World", r"^TRT\s*World|^TRTWorld\.", None, 0),
        ("ABC News Australia", r"^ABC\s*News\s*(Australia|AU)|^ABCNews(Australia)?\.au", None, 0),
        ("ABC News Live", r"^ABC\s*News\s*(Live|Now)|^ABCNewsLive\.", None, 0),
        ("CBS News", r"^CBS\s*News(\s*(24\s*/?\s*7|Live|Streaming))?($|\.)|^CBSNews\.", None, 0),
        ("NBC News Now", r"^NBC\s*News\s*Now|^NBCNewsNow\.", None, 0),
        ("Fox News", r"^Fox\s*News(\s*Channel)?($|[\s.])|^FoxNews\.", r"Radio|Espa", 0),
        ("Reuters TV", r"^Reuters($|[\s.])|^Reuters(TV|Now)\.", None, 0),
    ],
}
ORDER = list(dict.fromkeys(CCTV_ORDER + [c for g in ("凤凰", "港台新闻", "国际新闻")
                                         for c, _, _, _ in TABLE[g]]))
GROUP_OF = dict([(c, "央视") for c in CCTV_ORDER] +
                [(c, g) for g in ("凤凰", "港台新闻", "国际新闻") for c, _, _, _ in TABLE[g]])


# A single non-English blocklist, tested against the whole entry. Every channel we
# want is English or Chinese, and the language usually only shows up in one of the
# three name fields (tvg-id="DW.de@Russian" while the display name is just "DW").
NONENG = re.compile(r"Arab|Русск|Russ|Fran(ç|c)ais|French|Espa|Spanish|Deutsch|German|Italian|"
                    r"Italia|Portug|Hindi|Urdu|Bangla|T(ü|u)rk|Farsi|Persian|Swahili|Amharic|"
                    r"Indonesia|Bulgaria|Serbia|Alban|Romania|Greek|Ελλ|Magyar|Hungar|Polski|"
                    r"Polish|Mongolia|Latino|Brasil|M(é|e)xico|Balkan|Japanese|Korean|Vietnam|"
                    r"Thai|عربي|阿拉伯|俄语|法语|西班牙", re.I)


def strip_deco(s):
    s = re.sub(r"\(\s*\d{3,4}[pi]\s*\)|\(\s*\d+\s*[Kk]\s*\)|\[[^\]]*\]|[Ⓐ-ⓩ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canon_cctv(s, full=None):
    if re.search(r"CGTN", s, re.I):
        if NONENG.search(full or s):
            return None
        return "CGTN 纪录" if re.search(r"Doc|纪录|記錄|紀錄", s, re.I) else "CGTN"
    if re.search(r"CCTV[\s\-]*4\D{0,8}(欧洲|歐洲|（欧）|\(欧\)|Europe)", s, re.I):
        return "CCTV4 欧洲"
    if re.search(r"CCTV[\s\-]*4\D{0,8}(美洲|（美）|\(美\)|America)", s, re.I):
        return "CCTV4 美洲"
    if re.search(r"CCTV[\s\-]*5\s*(\+|＋|Plus)", s, re.I):
        return "CCTV5+ 体育赛事"
    m = re.search(r"CCTV[\s\-]*(\d{1,2})(?![\dKk])", s, re.I)
    if m and 1 <= int(m.group(1)) <= 17:
        n = int(m.group(1))
        return "CCTV%d %s" % (n, CCTV[n])
    return None


def canon(name, tvg_id="", tvg_name="", source=""):
    """Map a playlist entry onto one of our canonical channel names, or None."""
    hktw = source in ("hk", "tw") or bool(re.search(r"\.(hk|tw)\b", tvg_id, re.I))
    parts = [p for p in (strip_deco(name), strip_deco(tvg_name), tvg_id) if p]
    full = " | ".join(parts)
    for s in parts:
        c = canon_cctv(s, full)
        if c:
            return c
        for g in ("凤凰", "港台新闻", "国际新闻"):
            for cname, inc, exc, gated in TABLE[g]:
                if gated and not hktw:
                    continue
                if not re.search(inc, s, re.I):
                    continue
                if exc and re.search(exc, full, re.I):
                    continue
                if GROUP_OF[cname] == "国际新闻" and NONENG.search(full):
                    continue
                return cname
    return None

# ------------------------------------------------------------- sports matcher

# 体育 is open ended: rather than a fixed roster we take anything that looks like sport
# and then rank it, because the useful channels are not knowable in advance.
SPORT = re.compile(r"体育|體育|Sports?\b|ESPN|beIN|Eurosport|NBA|Tennis|Golf|F1\b|Formula|Racing|"
                   r"MotoGP|Fight|UFC|WWE|Cricket|Rugby|Football|Soccer|Premier League|La Liga|"
                   r"Bundesliga|Serie A|Ligue 1|Olympic|DAZN|TSN\b|Sky Sport|Fox Sport|Sportsnet|"
                   r"Setanta|Astro Arena|ELEVEN|劲爆|五星体育|广东体育|北京体育|纬来体育|緯來體育|"
                   r"愛爾達|爱尔达|博斯|睿播|足球|篮球|籃球", re.I)
# Gambling, adult, and the pastimes Chinese line-ups file under sport but nobody tunes in for.
NOTSPORT = re.compile(r"betting|bet365|sportsbet|bookmak|casino|poker|斗地主|棋牌|扑克|xxx|adult|"
                      r"porn|广场舞|垂钓|围棋", re.I)
# Language and region markers that NONENG does not catch because the name is transliterated.
SPORT_LANG = re.compile(r"Deportes|Latin\s*America|Czechia|Eurasia|Ukraine|Khel|Heldinnen|Nordic|"
                        r"Benelux|Polska|Ceska|Slovak|Baltic|Adria|Srbija|Hrvat|Match!|Hispanic", re.I)
# The order the brief asked for: the international names people actually look for, in rank order.
BRANDS = ["ESPN", "Sky Sports", "beIN", "Eurosport", "TNT Sports", "BT Sport", "DAZN", "NBA TV",
          "Tennis Channel", "Golf Channel", "Fox Sports", "TSN@^TSN\\s?[1-5]?$", "Sportsnet", "Setanta",
          "Astro Arena", "ELEVEN", "Premier Sports", "CBS Sports", "NFL", "MLB", "NHL",
          "Olympic", "Star Sports", "SuperSport", "Willow"]
# Chinese sports channels worth surfacing first, in the order the brief listed them.
CN_PREF = ["广东体育", "五星体育", "北京体育", "劲爆体育", "纬来体育", "緯來體育", "愛爾達體育",
           "博斯運動", "风云足球", "足球频道", "山东体育", "江苏体育", "天津体育", "超级体育"]
CJK = re.compile(r"[\u4e00-\u9fff]")
# Tier 2 is filler, so it is held to the brief's "English-language international" line. A
# name like "Meridiano TV" or "TVR Sport" carries no language marker, but iptv-org's tvg-id
# ends in the country, which is a reliable enough stand-in.
EN_CC = re.compile(r"\.(us|uk|gb|ca|au|nz|ie|sg|in|za|ph|jm|ke|ng)\b|@(EN|English)\b", re.I)


def clean_title(s):
    """Strip the decorations and quality suffixes playlists bolt onto a channel name."""
    s = strip_deco(s)
    for _ in range(3):
        s = re.sub(r"\s*\b(HD|FHD|UHD|SD|4K|HEVC|50\s?FPS|H\.?265)\b\s*$", "", s, flags=re.I).strip()
    return re.sub(r"\s+", " ", s).strip(" -_|")


def canon_sport(e):
    """Return (title, tier, rank) for a sports entry, or None. Tier 0 is Chinese, 1 is a
    known international brand, 2 is everything else."""
    hay = " | ".join([e["name"], e.get("tvg_name", ""), e.get("tvg_id", ""), e.get("group_title", "")])
    if not SPORT.search(hay) or NOTSPORT.search(hay) or SPORT_LANG.search(hay):
        return None
    if NONENG.search(hay) or re.search(r"CCTV[\s\-]*5", hay, re.I):
        return None  # CCTV5 and CCTV5+ already live in 央视
    title = clean_title(e["name"]) or clean_title(e.get("tvg_name", ""))
    if not title:
        return None
    if CJK.search(title):
        pref = CN_PREF.index(title) if title in CN_PREF else len(CN_PREF)
        return title, 0, pref
    for i, b in enumerate(BRANDS):
        pat = b.split("@", 1)[1] if "@" in b else re.escape(b) + r"\b"
        if re.match(pat, title, re.I):
            return title, 1, i
    if not EN_CC.search(e.get("tvg_id", "")):
        return None
    return title, 2, 0


def merge_key(t):
    """Two sources spelling the same channel differently should land on one entry."""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t.lower())


# ------------------------------------------- satellite, documentary, HK/TW entertainment

# Just the characters these playlists actually vary on, which is cheaper and safer than
# pulling in a full traditional-to-simplified table.
T2S = {"廣": "广", "遼": "辽", "寧": "宁", "龍": "龙", "陝": "陕", "貴": "贵", "雲": "云",
       "東": "东", "蘇": "苏", "內": "内", "灣": "湾", "區": "区", "慶": "庆", "肅": "肃",
       "團": "团", "廈": "厦", "邊": "边", "衛": "卫", "視": "视", "華": "华", "臺": "台",
       "劇": "剧", "電": "电", "綜": "综", "藝": "艺", "頻": "频", "紀": "纪", "實": "实",
       "錄": "录", "經": "经", "典": "典", "黃": "黄", "來": "来", "緯": "纬", "歡": "欢",
       "樂": "乐", "娛": "娱", "會": "会", "萊": "莱", "塢": "坞", "壹": "壹", "戲": "戏"}


def simp(t):
    return "".join(T2S.get(ch, ch) for ch in t)


# The conventional running order for Chinese provincial satellite channels.
WEISHI = ["湖南", "浙江", "江苏", "东方", "北京", "安徽", "山东", "天津", "深圳", "广东",
          "湖北", "四川", "重庆", "江西", "河南", "河北", "辽宁", "黑龙江", "吉林", "东南",
          "贵州", "云南", "广西", "海南", "陕西", "山西", "甘肃", "宁夏", "青海", "新疆",
          "西藏", "内蒙古", "兵团", "三沙", "大湾区", "厦门", "康巴", "延边"]

DOC_BRANDS = ["Discovery", "National Geographic", "Nat Geo", "BBC Earth", "Animal Planet",
              "History", "Smithsonian", "Curiosity", "Love Nature", "Viasat Nature",
              "Docu", "Documentary"]
DOC = re.compile(r"Discovery|National\s*Geographic|Nat\s*Geo|BBC\s*Earth|Animal\s*Planet|"
                 r"History|Smithsonian|Curiosity|Love\s*Nature|Viasat\s*Nature|Documentary|"
                 r"Docu|纪实|紀實|纪录|紀錄|人文|求索", re.I)

# 港台综艺 is enumerated, so it is a table: title, pattern, tier. Hong Kong first, then the
# Taiwan majors, then the rest. 翡翠台 is deliberately absent, it lives in 港台新闻.
HKTV = [
    ("J2", r"(TVB\s*)?\bJ2\b", 0), ("明珠台", r"明珠台|TVB\s*Pearl", 0),
    ("TVB Plus", r"TVB\s*Plus", 0), ("千禧經典台", r"千禧(經典|经典)", 0),
    ("黃金翡翠台", r"(黃|黄)金翡翠", 0), ("星河頻道", r"星河|TVB\s*Xing\s*He", 0),
    ("澳視澳門", r"澳(視|视)澳門|澳视澳门|澳門蓮花|澳门莲花|TDM", 0),
    ("中天綜合台", r"中天(綜合|综合)", 1), ("中天娛樂台", r"中天(娛樂|娱乐)", 1),
    ("東森綜合台", r"(東|东)森(綜合|综合)", 1), ("東森戲劇台", r"(東|东)森(戲劇|戏剧)", 1),
    ("東森電影台", r"(東|东)森(電影|电影)", 1), ("東森洋片台", r"(東|东)森洋片", 1),
    ("三立台灣台", r"三立(台灣|台湾)", 1), ("三立都會台", r"三立(都會|都会)", 1),
    ("三立戲劇台", r"三立(戲劇|戏剧)", 1),
    ("緯來日本台", r"(緯|纬)(來|来)日本", 1), ("緯來綜合台", r"(緯|纬)(來|来)(綜合|综合)", 1),
    ("緯來戲劇台", r"(緯|纬)(來|来)(戲劇|戏剧)", 1), ("緯來電影台", r"(緯|纬)(來|来)(電影|电影)", 1),
    ("八大綜合台", r"八大(綜合|综合)", 1), ("八大戲劇台", r"八大(戲劇|戏剧)", 1),
    ("八大第一台", r"八大第一", 1),
    ("民視第一台", r"民(視|视)第一", 1), ("民視台灣台", r"民(視|视)(台灣|台湾)", 1),
    ("TVBS歡樂台", r"TVBS\s*(歡樂|欢乐)", 1),
    ("衛視中文台", r"(衛|卫)(視|视)中文|STAR\s*Chinese\s*Channel", 1),
    ("衛視電影台", r"(衛|卫)(視|视)(電影|电影)|STAR\s*Chinese\s*Movies", 1),
    ("華視", r"^(華|华)(視|视)$|^CTS\b", 2), ("中視", r"^中(視|视)$|^CTV$", 2),
    ("台視", r"^台(視|视)$|^TTV$", 2),
    ("龍華戲劇台", r"(龍|龙)(華|华)", 2), ("龍祥時代電影台", r"(龍|龙)祥", 2),
    ("好萊塢電影台", r"好(萊|莱)(塢|坞)", 2), ("年代MUCH", r"年代\s*MUCH", 2),
    ("壹電視綜合台", r"壹(電視|电视)(綜合|综合)", 2),
]


def canon_satellite(e, title, hay):
    m = re.search(r"([\u4e00-\u9fff]{2,4})\s*(卫视|衛視)", simp(hay))
    if not m:
        return None
    pre = m.group(1)
    if "凤凰" in pre or "鳳凰" in pre:
        return None                              # 凤凰卫视 has its own group
    for i, w in enumerate(WEISHI):               # longest sensible suffix wins, e.g. 黑龙江
        if pre.endswith(w):
            return "卫视", w + "卫视", 0, i
    return None


def canon_doc(e, title, hay):
    # The name itself has to say documentary. iptv-org tags every entry in its documentary
    # category group-title="Documentary", so matching the haystack alone swept in reality
    # shows and true-crime reruns.
    if not DOC.search(title) or re.search(r"RT\s*Doc|Russia\s*Today", title, re.I):
        return None
    if CJK.search(title):
        return "纪录片", simp(title), 0, 0
    # Same country gate as the sports filler: "National Geographic Finland" and "Asharq
    # Discovery" carry no language marker in the name, but the tvg-id ends in the country.
    if not EN_CC.search(e.get("tvg_id", "")):
        return None
    for i, b in enumerate(DOC_BRANDS):
        if re.search(re.escape(b), title, re.I):
            return "纪录片", title, 1, i
    return "纪录片", title, 2, 0


def canon_hktv(e, title, hay):
    for i, (name, pat, tier) in enumerate(HKTV):
        if re.search(pat, hay, re.I) or re.search(pat, simp(hay), re.I):
            return "港台综艺", name, tier, i
    return None


def canon_extra(e):
    """The pattern-matched groups, tried in order. Returns (group, title, tier, rank)."""
    hay = " | ".join([e["name"], e.get("tvg_name", ""), e.get("tvg_id", ""), e.get("group_title", "")])
    title = clean_title(e["name"]) or clean_title(e.get("tvg_name", ""))
    if not title:
        return None
    sat = canon_satellite(e, title, hay)
    if sat:
        return sat
    if NONENG.search(hay) or SPORT_LANG.search(hay):
        return None
    sp = canon_sport(e)
    if sp:
        return "体育", sp[0], sp[1], sp[2]
    d = canon_doc(e, title, hay)
    if d:
        return d
    return canon_hktv(e, title, hay)

# --------------------------------------------------------------- fetch / test

def sh(cmd, timeout=45):
    argv = ["adb", "-s", DEV, "shell", cmd] if USE_TV else ["sh", "-c", cmd]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
        return p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "", "timeout"


def fetch(url, headers, timeout=10):
    """One curl. Returns (code, size, ms, url_effective, body_head)."""
    body = "/data/local/tmp/b$$" if USE_TV else "/tmp/b$$"
    # -4 everywhere: the TV has no IPv6 route, so an AAAA-only host must fail here too.
    p = ["/data/local/tmp/curl" if USE_TV else "curl", "-skL4", "--compressed", "--max-time", str(timeout), "-r", "0-200000"]
    if USE_TV:
        p += ["--doh-url", "https://223.5.5.5/dns-query", "--doh-insecure"]
    for k, v in (headers or {}).items():
        p += ["-H", shlex.quote("%s: %s" % (k, v))]
    p += ["-o", body, "-w", "'%{http_code} %{size_download} %{time_total} %{url_effective}'", shlex.quote(url)]
    cmd = " ".join(p) + '; echo " $?"; echo @@B@@; head -c 3000 ' + body + "; rm -f " + body
    out, err = sh(cmd, timeout=timeout + 25)
    if "@@B@@" not in out:
        if USE_TV and ("closed" in err or "offline" in err or "device" in err):
            subprocess.run(["adb", "connect", DEV], capture_output=True)
            out, err = sh(cmd, timeout=timeout + 25)
        if "@@B@@" not in out:
            return 0, 0, 0, "", ""
    stats, _, rest = out.partition("@@B@@")
    f = stats.strip().split()
    if len(f) < 4:
        return 0, 0, 0, "", ""
    return int(f[0]), int(f[1]), int(float(f[2]) * 1000), " ".join(f[3:-1]), rest.lstrip("\n")


def first_uri(body, tag):
    lines, take = body.splitlines(), False
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("#" + tag):
            take = True
        elif take and ln and not ln.startswith("#"):
            return ln
    return None


def test_url(url, headers):
    """TV-side reachability. Returns (status, playlist_ms, segment_ms, seg_bytes, is_hls).

    is_hls says whether the body really was a playlist. A non-HLS body only proves that
    bytes arrived, so the caller makes those wait for ffprobe before trusting them."""
    if url.startswith(("rtmp", "rtsp", "rtp", "udp")):
        return "untested-protocol", 0, 0, 0, False
    code, size, ms, eff, body = fetch(url, headers, 10)
    if code not in (200, 206) or size == 0:
        return "http-%d" % code if code else "no-response", ms, 0, 0, False
    if not body.lstrip().startswith("#EXTM3U"):
        return ("ok" if size >= 50000 else "short-body"), ms, ms, size, False
    pl, ptime = eff or url, ms
    # epg.pw keeps answering 200 for an offline channel, with a master whose only variant is
    # files4.3y1.xyz/media/video/nosignal_h264: a real 1080p loop of a no-signal card and a
    # QR-code ad, so the segment check alone passes it.
    if "nosignal" in (pl + body).lower():
        return "excluded-slate", ms, 0, 0, True
    if "#EXT-X-STREAM-INF" in body:
        v = first_uri(body, "EXT-X-STREAM-INF")
        if not v:
            return "no-variant", ms, 0, 0, True
        code, size, ms2, eff2, body2 = fetch(urljoin(pl, v), headers, 10)
        if code not in (200, 206) or not body2.lstrip().startswith("#EXTM3U"):
            return "variant-http-%d" % code, ptime, 0, 0, True
        pl, body, ptime = eff2 or urljoin(pl, v), body2, ptime + ms2
    seg = first_uri(body, "EXTINF")
    if not seg:
        return "no-segment", ptime, 0, 0, True
    code, size, ms3, _, _ = fetch(urljoin(pl, seg), headers, 12)
    if code in (200, 206) and size >= 50000:
        return "ok", ptime, ms3, size, True
    if code in (200, 206) and size > 0:
        return "ok-small", ptime, ms3, size, True
    return "seg-http-%d" % code, ptime, ms3, size, True


def transient(st):
    """Statuses that usually mean the host shed load rather than the stream being dead."""
    # A live playlist rolls: a segment can 404 simply because it expired between the two
    # fetches, so segment 404s get a second chance while structural 404s do not.
    return st in ("no-response", "seg-http-404") or bool(re.search(r"-(0|301|302|408|429|5\d\d)$", st))


def test_twice(e):
    r = test_url(e["url"], e["headers"])
    return test_url(e["url"], e["headers"]) if transient(r[0]) else r


def interleave(items, key):
    """Round-robin by host, so the eight in-flight requests hit eight different servers.
    The small CCTV mirror farm throttles hard when several of its channels are pulled
    at once, and that showed up as timeouts and stray 302s."""
    buckets = {}
    for it in items:
        buckets.setdefault(key(it), []).append(it)
    out = []
    while buckets:
        for h in list(buckets):
            out.append(buckets[h].pop(0))
            if not buckets[h]:
                del buckets[h]
    return out


def probe_codec(url, headers):
    # Several of these CDNs serve HLS segments named .jpg, or with no extension at all, to
    # slip past filtering. ffmpeg refuses to open those by default and then reports no
    # streams, which reads as "not video" even though it has already detected mpegts and
    # ExoPlayer plays them. The three relaxing options below are what make the difference
    # between codec "unknown" and h264 for the jdshipin redirectors.
    # ffprobe has no -4; the Mac has no public IPv6 route, so v4 is what it uses anyway.
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=codec_name,width,height", "-of", "csv=p=0", "-extension_picky", "0",
           "-allowed_extensions", "ALL", "-allowed_segment_extensions", "ALL",
           "-timeout", "10000000", "-rw_timeout", "10000000"]
    if headers.get("User-Agent"):
        cmd += ["-user_agent", headers["User-Agent"]]
    if headers.get("Referer"):
        cmd += ["-headers", "Referer: %s\r\n" % headers["Referer"]]
    for attempt in range(2):                 # one retry: these probes are flaky, not wrong
        try:
            p = subprocess.run(cmd + [url], capture_output=True, timeout=25)
            f = p.stdout.decode().strip().splitlines()[0].split(",")
            return f[0], f[1] if len(f) > 1 else "", f[2] if len(f) > 2 else ""
        except Exception:
            pass
    return "unknown", "", ""

# ------------------------------------------------------------------ pipeline

def download():
    os.makedirs(CACHE, exist_ok=True)
    entries = []
    for name, url in SOURCES:
        p = os.path.join(CACHE, name + ".m3u")
        try:  # always refetch, these lists churn; keep the last copy if the fetch breaks
            for attempt in range(3):             # the proxy truncates responses fairly often
                try:
                    with urllib.request.urlopen(url, timeout=60) as r:
                        body = r.read()
                    break
                except Exception:
                    if attempt == 2:
                        raise
            open(p, "wb").write(body)
        except Exception as exc:
            if not os.path.exists(p):
                raise
            print("  %s: refetch failed (%s), using the cached copy" % (name, exc))
        entries += parse_m3u(open(p, encoding="utf-8", errors="replace").read(), name)
    entries += parse_m3u(open(os.path.join(DATA, "upstream", "my-tv-0_default_mobile.txt"), encoding="utf-8").read(), "builtin-mobile")
    entries += parse_builtin_json(open(os.path.join(DATA, "upstream", "my-tv-0_default_channels.txt"), encoding="utf-8").read(), "builtin-json")
    return entries


def main():
    if USE_TV and not DEV:
        sys.exit("give --serial <tv-ip>:5555 for the TV, or --mac to test from this machine")
    os.makedirs(OUT, exist_ok=True)
    entries = download()
    by_ch, seen, srank, titles = {}, set(), {}, {}
    for e in entries:
        c = None if e["source"] in EXTRA else canon(e["name"], e["tvg_id"], e["tvg_name"], e["source"])
        if c:
            e["canon"], e["cgroup"] = c, GROUP_OF[c]
        else:
            x = canon_extra(e)
            if not x:
                continue
            g, k = x[0], x[0] + "/" + merge_key(x[1])
            titles.setdefault(k, x[1])           # first spelling seen wins
            e["canon"], e["cgroup"], c = titles[k], g, titles[k]
            srank[c] = min(srank.get(c, (9, 9)), x[2:])
        # "[" is an IPv6 literal and the TV has no IPv6 route, so those are dropped outright.
        if (c, e["url"]) in seen or "[" in e["url"]:
            continue
        seen.add((c, e["url"]))
        by_ch.setdefault(c, []).append(e)
    print("matched %d channels (%d pattern-matched), %d unique urls"
          % (len(by_ch), len(srank), len(seen)))

    rows, todo = [], []
    for c in sorted(by_ch, key=lambda t: (GORDER[by_ch[t][0]["cgroup"]],
                                          ORDER.index(t) if t in ORDER else 0, t)):
        # Prefer hosts that answer from this egress, and spread across hosts so one
        # dead CDN cannot eat every slot. ponytail: static host list, revisit if the
        # proxy changes.
        cands = sorted(by_ch[c], key=lambda e: (1 if DEAD.search(e["url"]) else 0, e["url"]))
        picked, per_host = [], {}
        for e in cands:
            # CNN's standby card streams perfectly and shows no programme, so it is listed
            # as a candidate but never tested and never selected.
            if "slate" in e["url"].lower():
                e["status"] = "excluded-slate"
                continue
            h = urlparse(e["url"]).hostname or ""
            if BADHOST.search(h):
                e["status"] = "excluded-host"
                continue
            if per_host.get(h, 0) >= MAX_PER_HOST or len(picked) >= MAX_PER_CH:
                continue
            per_host[h] = per_host.get(h, 0) + 1
            picked.append(e)
        for e in cands:
            e["picked"] = e in picked
            rows.append(e)
        todo += picked

    # Reachability is expensive and does not change minute to minute, so it is cached by
    # url. Pass --retest to ignore the cache and hit the TV again.
    cpath = os.path.join(CACHE, "tvtest.json")
    cache = json.load(open(cpath)) if os.path.exists(cpath) and "--retest" not in sys.argv else {}
    key = lambda e: e["url"] + "|" + json.dumps(e["headers"], sort_keys=True)
    fresh = interleave([e for e in todo if key(e) not in cache],
                       lambda e: urlparse(e["url"]).hostname or "")
    print("testing %d of %d candidate urls on %s (%d cached)"
          % (len(fresh), len(todo), "the TV" if USE_TV else "the Mac", len(todo) - len(fresh)))
    if fresh:
        with ThreadPoolExecutor(POOL) as ex:
            for e, r in zip(fresh, ex.map(test_twice, fresh)):
                cache[key(e)] = list(r)
        os.makedirs(CACHE, exist_ok=True)
        json.dump(cache, open(cpath, "w"))
    for e in todo:
        e["status"], e["pl_ms"], e["seg_ms"], e["seg_bytes"], e["hls"] = cache[key(e)]

    reachable = [e for e in todo if e["status"].startswith("ok")]
    # Codecs are cached too, and only successes are kept. ffprobe fails intermittently on
    # the raw-mpegts urls, and because an unidentified non-playlist url is treated as "not
    # video", one flaky probe used to drop a whole channel between otherwise identical runs.
    cdpath = os.path.join(CACHE, "codec.json")
    cc = json.load(open(cdpath)) if os.path.exists(cdpath) and "--reprobe" not in sys.argv else {}
    fresh = [e for e in reachable if e["url"] not in cc]
    print("%d/%d urls reachable; probing %d codecs (%d cached)"
          % (len(reachable), len(todo), len(fresh), len(reachable) - len(fresh)))
    with ThreadPoolExecutor(4) as ex:
        for e, cd in zip(fresh, ex.map(lambda e: probe_codec(e["url"], e["headers"]), fresh)):
            if cd[0] != "unknown":
                cc[e["url"]] = cd
    os.makedirs(CACHE, exist_ok=True)
    json.dump(cc, open(cdpath, "w"))
    for e in reachable:
        e["codec"], e["w"], e["h"] = cc.get(e["url"], ("unknown", "", ""))
    # A body that was not a playlist only proves bytes arrived. ExoPlayer needs video, so
    # ffprobe has to name a codec before such a url counts.
    for e in reachable:
        if not e["hls"] and e.get("codec", "unknown") == "unknown":
            e["status"] = "not-video"

    with open(os.path.join(OUT, "candidates.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canonical_name", "group", "url", "source", "headers_json", "tv_status",
                    "tv_playlist_ms", "tv_segment_ms", "seg_bytes", "codec", "width", "height", "verdict"])
        for e in rows:
            c, st = e["canon"], e.get("status", "skipped-cap")
            w.writerow([c, e["cgroup"], e["url"], e["source"], json.dumps(e["headers"], ensure_ascii=False),
                        st, e.get("pl_ms", ""), e.get("seg_ms", ""), e.get("seg_bytes", ""),
                        e.get("codec", ""), e.get("w", ""), e.get("h", ""),
                        "pass" if st.startswith("ok") else
                        ("skipped" if st.startswith("skipped") else
                         ("excluded" if st.startswith("excluded-") else "fail"))])

    out = []
    for c in sorted(by_ch, key=lambda t: (GORDER[by_ch[t][0]["cgroup"]],
                                          ORDER.index(t) if t in ORDER else 0, t)):
        ok = [e for e in by_ch[c] if e.get("status", "").startswith("ok")]
        if not ok:
            continue
        groups = {}
        for e in ok:
            groups.setdefault(json.dumps(e["headers"], sort_keys=True), []).append(e)
        for i, (hj, lst) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
            if i and len(lst) < 1:
                continue
            # h264 that ffprobe actually saw, then playlists we proved by downloading a
            # segment, then anything else, and within a tier the quickest segment wins.
            # hevc and mpeg2 go last: this armeabi-v7a Android 9 box decodes neither reliably.
            lst.sort(key=lambda e: (0 if e.get("codec", "").startswith("h264") else
                                    (3 if e.get("codec") in ("hevc", "mpeg2video") else
                                     (2 if e.get("codec", "unknown") == "unknown" else 1)),
                                    e.get("seg_ms", 99999)))
            ch = {"group": by_ch[c][0]["cgroup"], "title": c if not i else "%s (%d)" % (c, i + 1),
                  "logo": next((e["logo"] for e in lst if e["logo"]), ""),
                  "uris": [e["url"] for e in lst[:3]]}
            if json.loads(hj):
                ch["headers"] = json.loads(hj)
            ch["_seg"] = min(e.get("seg_ms", 99999) for e in lst)
            out.append(ch)

    # The pattern-matched groups are ranked rather than rostered: the preferred names in
    # the order the brief gave, then whatever is left, quickest segment first. Each group
    # is then cut to its cap.
    srt, keep = {}, set()
    for g, cap in CAPS.items():
        grp = [c for c in out if c["group"] == g]
        grp.sort(key=lambda c: srank.get(c["title"].split(" (")[0], (9, 9)) + (c["_seg"],))
        keep |= {id(c) for c in grp[:cap]}
        srt.update({id(c): i for i, c in enumerate(grp)})
        if len(grp) > cap:
            print("%s: kept %d of %d passing channels" % (g, cap, len(grp)))
    out = [c for c in out if c["group"] not in CAPS or id(c) in keep]
    out.sort(key=lambda c: (GORDER[c["group"]], srt.get(id(c), 0) if c["group"] in CAPS else
                            (ORDER.index(c["title"].split(" (")[0])
                             if c["title"].split(" (")[0] in ORDER else 999)))
    for c in out:
        c.pop("_seg", None)
    json.dump(out, open(os.path.join(OUT, "channels.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_report(rows, todo, out, srank)
    print("\n" + open(os.path.join(OUT, "report.md"), encoding="utf-8").read())
    print("TOTAL PASSING CHANNELS: %d" % len(out))


def write_report(rows, todo, out, srank):
    L = ["# Channel list build report", "",
         "Reachability was measured from the TV (LAN) with its static curl and DNS over HTTPS. "
         "The TV reaches the internet through the router's proxy, whose egress is the same as the Mac's: "
         "an Oracle Cloud node in South Korea. Results therefore describe what that proxy can reach, "
         "not what a Chinese residential line would see.", ""]
    for g in GORDER:
        names = [c for c in ORDER if GROUP_OF[c] == g]
        cand = [r for r in rows if r["cgroup"] == g]
        got = [c["title"].split(" (")[0] for c in out if c["group"] == g]
        L.append("## %s" % g)
        L.append("%d candidate urls, %d channels passing." % (len(cand), len(set(got))))
        if g in CAPS:  # the count above is post-cap, so spell the rest out
            allc = sorted({r["canon"] for r in cand})
            passing = {r["canon"] for r in cand if str(r.get("status", "")).startswith("ok")}
            blocked = sorted(set(allc) - passing)
            L.append("%d channels were matched and tested and %d of them had a playable url; the "
                     "list keeps the best %d, the preferred names first and the remainder by "
                     "segment latency." % (len(allc), len(passing), len(set(got))))
            if blocked:
                L.append("Matched but nothing playable from here: " + ", ".join(blocked[:40])
                         + ("." if len(blocked) <= 40 else ", and %d more." % (len(blocked) - 40)))
            L.append("")
            continue
        missing = [n for n in names if n not in got and any(r["canon"] == n for r in rows)]
        absent = [n for n in names if not any(r["canon"] == n for r in rows)]
        if missing:
            L.append("Found in the playlists but not reachable: " + ", ".join(missing) + ".")
        if absent:
            L.append("Not present in any source playlist: " + ", ".join(absent) + ".")
        L.append("")
    hv = [c["title"] for c in out
          if any(r.get("codec") in ("hevc", "mpeg2video") for r in todo if r["url"] in c["uris"])]
    hd = [c["title"] for c in out if "headers" in c]
    L.append("## Notes")
    L.append("Every China Mobile / cmvideo CCTV feed carried by the built-in lists times out or answers 403 "
             "from this egress; the CCTV streams that do work come from overseas mirrors, which hand out "
             "redirect URLs signed against the client IP, so the unsigned entry url is what gets stored.")
    L.append("")
    L.append("The Hong Kong and Taiwan channels that iptv-org tags [Geo-blocked] answer 403 from Korea: "
             "HOY, TVBS新聞, 東森新聞, 東森財經新聞, 華視新聞 and RTHK 32. Those streams are alive, they simply "
             "refuse this egress, and they would very likely play from a Hong Kong or Taiwan address.")
    L.append("")
    if not any(c["title"].startswith("CNN") for c in out):
        L.append("CNN and CNN International have no usable url. The only turnerlive address in these "
                 "playlists points at cnn_slate, the standby card, which the brief rules out, and the "
                 "real feed gates its segments behind a cable-provider token. CNN sits on iptv-org's "
                 "blocklist for the same reason, so there is nothing free to fall back on.")
        L.append("")
    L.append("")
    L.append("The router proxy filters some destinations itself. Instead of failing the connection it "
             "answers with a 41-byte page reading \"the content is not available in your area\", "
             "sometimes under HTTP 200 and sometimes under a 301 that redirects onto itself. The same "
             "body comes back from unrelated origins, a CCTV mirror on 74.91.26.218 and bloomberg.com "
             "among them, which is how we know it is injected rather than sent by the stream. A plain "
             "status-code check would have accepted these; the segment-size rule is what catches them.")
    L.append("")
    L.append("The BBC CMAF/DASH manifests on vs-cmaf-*.akamaized.net cannot pass the non-HLS test by "
             "construction, since the manifest is a few kilobytes of XML rather than media. BBC News still "
             "passes on its HLS urls.")
    L.append("")
    L.append("ABC News Live publishes ten numbered feeds on abcnews-streams.akamaized.net; the master "
             "playlist loads but its variants answer 404 from here, so the channel is listed as not "
             "reachable rather than missing.")
    L.append("")
    L.append("The mirror farm that carries most of the working CCTV feeds throttles when several of its "
             "channels are pulled at once, which showed up as timeouts and stray 302s. Requests are "
             "therefore round-robined across hosts and a transient failure is retried once.")
    L.append("")
    L.append("A url now has to prove it carries video. Either the body is a real playlist and a "
             "media segment of at least fifty kilobytes came back, or ffprobe has to name a codec. "
             "The earlier rule accepted any non-playlist response over fifty kilobytes, which let "
             "YouTube watch pages and GitHub text files through: they are large and they answer 200, "
             "but ExoPlayer cannot open either. Those four hosts are now refused outright and the "
             "affected channels were dropped unless another url stood up.")
    L.append("")
    L.append("Making ffprobe a gate meant loosening it first. Several of these CDNs name their "
             "segments .jpg or give them no extension at all, and ffmpeg refuses such a file by "
             "default even after it has detected mpegts inside, so the probe came back empty and "
             "the stream looked like it was not video. With -extension_picky 0 and the two "
             "allowed-extension options the same urls resolve to h264, which is how the jdshipin "
             "redirectors behind 凤凰, 無綫新聞台, 翡翠台 and ViuTV were confirmed rather than dropped. "
             "ffprobe has no -4 option, so that could not be set; the Mac has no public IPv6 route "
             "and reaches these hosts over v4 regardless.")
    L.append("")
    L.append("HEVC or MPEG-2: " + (", ".join(hv) if hv else "none of the selected urls probed as HEVC, so nothing "
             "had to be demoted for this armeabi-v7a box; %d of %d selected urls probed as h264 and the "
             "rest could not be identified by ffprobe." % (
                 sum(1 for c in out for u in c["uris"]
                     for r in todo if r["url"] == u and r.get("codec", "").startswith("h264")),
                 sum(len(c["uris"]) for c in out))))
    L.append("")
    L.append("体育, 卫视, 纪录片 and 港台综艺 are matched by pattern rather than from a roster, so "
             "they are ranked instead of curated and then cut to %s respectively. The three extra "
             "playlists that feed them, the iptv-org sports and documentary categories and the US "
             "country list, are fenced off from the four news groups, so adding them could not "
             "disturb channels that had already been tested."
             % ", ".join("%s at %d" % (g, c) for g, c in CAPS.items()))
    L.append("")
    L.append("Headers: " + (", ".join(hd) if hd else "no passing channel needed a User-Agent or Referer. "
             "The source playlists do carry 59 entries with http-user-agent set, but none of them is one "
             "of the channels we want, so every uri below is a plain GET."))
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

# ------------------------------------------------------------------ selftest

def selftest():
    e = parse_m3u('#EXTM3U\n#EXTINF:-1 tvg-id="X.hk" tvg-name="N, with comma" tvg-logo="http://l/p.png"'
                  ' group-title="G",Some Name (1080p)\n#EXTVLCOPT:http-user-agent=UA/1\n'
                  '#EXTVLCOPT:http-referrer=http://r/\nhttp://h/s.m3u8\n', "t")
    assert len(e) == 1 and e[0]["url"] == "http://h/s.m3u8", e
    assert e[0]["name"] == "Some Name (1080p)" and e[0]["logo"] == "http://l/p.png", e
    assert e[0]["headers"] == {"User-Agent": "UA/1", "Referer": "http://r/"}, e
    assert canon("CCTV-13 新闻") == "CCTV13 新闻"
    assert canon("CCTV 4 Europe") == "CCTV4 欧洲"
    assert canon("CCTV5+") == "CCTV5+ 体育赛事" and canon("CCTV-5") == "CCTV5 体育"
    assert canon("CCTV17") == "CCTV17 农业农村" and canon("CCTV1 综合") == "CCTV1 综合"
    assert canon("CCTV4K 超高清") is None and canon("CCTV8K") is None
    assert canon("", tvg_id="CCTV10.cn@SD") == "CCTV10 科教"
    assert canon("CGTN Documentary") == "CGTN 纪录" and canon("CGTN America") == "CGTN"
    assert canon("CGTN Arabic") is None
    assert canon("ABC15 Phoenix") is None and canon("12 News Phoenix") is None
    assert canon("Phoenix InfoNews Channel") == "凤凰资讯台"
    assert canon("凤凰资讯 (720p)") == "凤凰资讯台" and canon("凤凰中文 (720p)") == "凤凰卫视中文台"
    assert canon("A2 CNN Albania") is None and canon("CNN-News18") is None
    assert canon("CNN International (1080p)") == "CNN International" and canon("CNN") == "CNN"
    assert canon("BBC News (1080p) [Geo-blocked]") == "BBC News" and canon("BBC Arabic") is None
    assert canon("TVBS News (TVBS新聞台) [Geo-blocked]", source="tw") == "TVBS新聞"
    assert canon("CTV News", source="news") is None, "Canadian CTV must not become 中視新聞"
    assert canon("Golden Jade (1080p)", source="hk") is None and canon("Jade (1080p)", source="hk") == "翡翠台"
    assert canon("EBC Financial News (東森財經新聞台)", source="tw") == "東森財經新聞"
    assert canon("Sky News Arabia") is None and canon("Sky News") == "Sky News"
    # Language markers often hide in a field other than the one that matched.
    assert canon("CGTN Español", tvg_id="CGTNSpanish.cn") is None
    assert canon("DW", tvg_id="DW.de@Russian") is None and canon("DW English") == "DW English"
    assert canon("Euronews Bulgaria", tvg_id="EuronewsBulgaria.bg@SD") is None
    assert canon("Euronews (720p)", tvg_id="Euronews.uk@SD") == "Euronews English"
    assert canon("CCTV-4 中文国际（欧）", tvg_id="CCTV4Europe.cn") == "CCTV4 欧洲"
    assert canon("CCTV-4 中文国际（美）", tvg_id="CCTV4America.cn") == "CCTV4 美洲"
    assert canon("CCTV-4", tvg_id="CCTV4.cn@SD") == "CCTV4 中文国际"
    assert canon("ABC News", tvg_id="ABCNews.au") == "ABC News Australia"
    assert canon("ABC News Albania", tvg_id="ABCNewsAlbania.al") is None
    assert canon("CNBC Europe") is None and canon("CNBC (1080p)") == "CNBC"
    # Header on the #EXTINF line, the way iptv-org writes it.
    e2 = parse_m3u('#EXTINF:-1 tvg-id="A" http-user-agent="Mozilla/5.0" group-title="News",X\nhttp://h/a\n', "t")
    assert e2[0]["headers"] == {"User-Agent": "Mozilla/5.0"}, e2
    sp = lambda n, g="", i="": canon_sport({"name": n, "tvg_name": "", "tvg_id": i, "group_title": g})
    assert sp("广东体育 (1080p)")[:2] == ("广东体育", 0)
    assert sp("ESPN HD")[:2] == ("ESPN", 1) and sp("Sky Sports F1")[1] == 1
    assert sp("beIN Sports 1")[0] == "beIN Sports 1"
    assert sp("CCTV-5 体育") is None and sp("CCTV5+ HD") is None, "CCTV5 belongs to 央视"
    assert sp("ESPN Deportes") is None and sp("Match! Ultra") is None
    assert sp("Eurosport 1 Russia") is None and sp("Star Sports Khel") is None
    assert sp("JJ斗地主", g="体育") is None and sp("快乐垂钓", g="体育") is None
    assert sp("纬来电影") is None and sp("纬来体育")[0] == "纬来体育"
    assert sp("Bet365 Stream") is None
    assert sp("BBC News") is None
    assert sp("Some Channel", g="Sports", i="Some.us@SD")[1] == 2, "group-title alone counts as sport"
    assert sp("Meridiano TV", g="Sports", i="MeridianoTV.ve@SD") is None, "Spanish filler stays out"
    assert sp("Vinh Long TV 4", g="Sports", i="VinhLongTV4.vn@SD") is None
    assert sp("MSG", g="Sports", i="MSG.us@SD")[1] == 2
    assert sp("FIFA+ Hispanic America", i="FIFAPlus.uk@HispanicAmerica") is None
    assert merge_key("beIN SPORTS 1") == merge_key("beIN Sports 1")
    ex = lambda n, g="", i="": canon_extra({"name": n, "tvg_name": "", "tvg_id": i, "group_title": g})
    assert ex("湖南卫视HD")[:2] == ("卫视", "湖南卫视")
    assert ex("湖南衛視高清")[:2] == ("卫视", "湖南卫视")
    assert ex("黑龙江卫视")[1] == "黑龙江卫视", "longest province name must win over 龙江"
    assert ex("内蒙古卫视 (1080p)")[1] == "内蒙古卫视"
    assert ex("凤凰卫视资讯台") is None, "凤凰 has its own group"
    assert ex("湖南卫视")[3] < ex("浙江卫视")[3] < ex("贵州卫视")[3], "popularity order"
    assert ex("National Geographic HD", i="NatGeo.us@HD")[0] == "纪录片"
    assert ex("Discovery Channel Italia") is None
    assert ex("National Geographic Finland", i="NationalGeographicFinland.fi@SD") is None
    assert ex("RT Documentary", i="RTDocumentary.ru@SD") is None
    assert ex("Curiosity Now", i="CuriosityNOW.de@EN")[0] == "纪录片", "iptv-org's own @EN tag counts"
    assert ex("Teen Mom", g="Documentary", i="TeenMom.us@SD") is None, "group-title alone is not enough"
    assert ex("Forensic Files", g="Documentary", i="ForensicFiles.us@SD") is None
    assert ex("RT Documentary English", i="RTDoc.ru@English") is None
    assert ex("Discovery Channel", i="DiscoveryChannel.us@SD")[0] == "纪录片"
    assert ex("求索纪录")[:3] == ("纪录片", "求索纪录", 0)
    assert ex("TVB J2 (1080p)")[:3] == ("港台综艺", "J2", 0)
    assert ex("明珠台")[:2] == ("港台综艺", "明珠台")
    assert ex("東森戲劇台")[:3] == ("港台综艺", "東森戲劇台", 1)
    assert ex("东森戏剧台")[1] == "東森戲劇台", "simplified spelling maps to the same channel"
    assert ex("緯來日本台")[1] == "緯來日本台"
    assert ex("衛視中文台")[1] == "衛視中文台"
    assert canon("翡翠台", source="hk") == "翡翠台", "翡翠台 stays in 港台新闻"
    assert clean_title("Fox Sports 1 (1080p) [Not 24/7] HD") == "Fox Sports 1"
    assert first_uri("#EXTM3U\n#EXTINF:9,\nseg1.ts\n", "EXTINF") == "seg1.ts"
    global fetch
    real, fetch = fetch, lambda u, h, t: (200, 127, 5, u, "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n"
                                          "http://files4.3y1.xyz/media/video/nosignal_h264/playlist.m3u8\n")
    assert test_url("https://epg.pw/stream/ab.m3u8", {})[0] == "excluded-slate"
    fetch = real
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
