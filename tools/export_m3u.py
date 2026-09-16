#!/usr/bin/env python3
"""Write playlists/current.m3u: exactly the list the apk plays, in the apk's own order.

channels.json is what the test run produced; the three 凤凰卫视 entries the app actually
shows are built by merge.py, so we go through merge() rather than reading the json
straight, and current.m3u then matches channels.txt channel for channel.

    python3 export_m3u.py [out.m3u]
"""
import json, os, sys

from merge import FH, IN, PHOENIX, merge

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, os.pardir, "playlists", "current.m3u"))
FH_PREFIX = FH.split("%s")[0]
LIVE_ID = {FH % lid: lid for _, lid, _ in PHOENIX}

HEADER = """# 本文件是 my-newtv apk 内置的频道列表，截至 2026-09-16。
# 测试只从一个网络位置做过：路由器代理出口在韩国（Oracle Cloud 节点），仅 IPv4。
# 能不能播放随地区、网络和时间变化，依赖之前请自己重测一遍。
#
# 凤凰卫视的三个频道用的是 app 内部的本地转发地址 http://127.0.0.1:34567/fh/<id>.flv，
# 只有在 app 里才有效，别的播放器打不开。下面每个凤凰频道前都注明了原始的 fengshows
# live_id，可以自己换成签名后的 FLV 地址：
#   GET https://m.fengshows.com/api/v3/hub/live/auth-url?live_id=<id>&live_qa=HD
#   请求头带一个空的 token，返回的就是签名过的 FLV 播放地址。
"""


def to_m3u(chs):
    L = ["#EXTM3U", HEADER.rstrip("\n")]
    for c in chs:
        for u in c["uris"]:
            if u in LIVE_ID:
                L.append("# fengshows live_id: " + LIVE_ID[u])
            L.append('#EXTINF:-1 tvg-name="%s" tvg-logo="%s" group-title="%s",%s'
                     % (c["title"], c.get("logo", ""), c["group"], c["title"]))
            for k, opt in (("User-Agent", "http-user-agent"), ("Referer", "http-referrer")):
                if c.get("headers", {}).get(k):
                    L.append("#EXTVLCOPT:%s=%s" % (opt, c["headers"][k]))
            L.append(u)
    return "\n".join(L) + "\n"


def selftest(chs):
    text = to_m3u(chs)
    lines = text.splitlines()
    assert lines[0] == "#EXTM3U"
    assert sum(1 for l in lines if l.startswith("#EXTINF")) == sum(len(c["uris"]) for c in chs)
    assert sum(1 for l in lines if not l.startswith("#")) == sum(len(c["uris"]) for c in chs)
    assert sum(1 for l in lines if l.startswith(FH_PREFIX)) == len(PHOENIX)
    # every uri is preceded by its own #EXTINF, and headers ride between the two
    for i, l in enumerate(lines):
        if not l.startswith("#"):
            assert any(lines[j].startswith("#EXTINF") for j in range(max(0, i - 3), i)), l
    return text


if __name__ == "__main__":
    chs = merge(json.load(open(IN, encoding="utf-8")))
    text = selftest(chs)
    dst = sys.argv[1] if len(sys.argv) > 1 else OUT
    open(dst, "w", encoding="utf-8").write(text)
    print(len(chs), "channels,", sum(len(c["uris"]) for c in chs), "urls ->", dst)
