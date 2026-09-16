#!/usr/bin/env python3
"""Turn the tested playlists/channels.json into the gua64 list the apk ships.

Two things happen here that the test run cannot do for itself: the three 凤凰卫视
channels are given the app's own local route as their first uri, and the groups are
put in the running order the app shows them in.

    python3 merge.py                     # playlists/channels.json -> app/.../raw/channels.txt
    python3 merge.py in.json out.txt     # explicit paths
    python3 merge.py --selftest          # checks only, writes nothing
"""
import json, os, sys

from gua64 import encode, decode

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
IN = os.path.join(REPO, "playlists", "channels.json")
RAW = os.path.join(REPO, "app", "src", "main", "res", "raw", "channels.txt")

FH = 'http://127.0.0.1:34567/fh/%s.flv'
PHOENIX = [  # title, fengshows live_id, logo
    ('凤凰卫视资讯台', '7c96b084-60e1-40a9-89c5-682b994fb680', 'http://c1.fengshows-cdn.com/a/2021_22/79dcc3a9da358a3.png'),
    ('凤凰卫视中文台', 'f7f48462-9b13-485b-8101-7b54716411ec', 'http://c1.fengshows-cdn.com/a/2021_22/ede3d9e09be28e5.png'),
    ('凤凰卫视香港台', '15e02d92-1698-416c-af2f-3e9a872b4d78', 'http://c1.fengshows-cdn.com/a/2021_23/325d941090bee17.png'),
]
ORDER = ['央视', '凤凰', '港台新闻', '国际新闻', '体育', '卫视', '纪录片', '港台综艺']


def merge(chs):
    mirrors = {c['title'].replace('卫视', ''): c for c in chs if c['group'] == '凤凰'}
    phoenix = []
    for title, lid, logo in PHOENIX:
        m = mirrors.get(title.replace('卫视', ''), {})
        uris = [FH % lid] + [u for u in m.get('uris', []) if u not in (FH % lid,)]
        phoenix.append({'group': '凤凰', 'title': title, 'logo': m.get('logo') or logo, 'uris': uris[:3]})
    rest = [c for c in chs if c['group'] != '凤凰']
    out = [c for g in ORDER for c in (phoenix if g == '凤凰' else [x for x in rest if x['group'] == g])]
    assert len(out) == len(rest) + 3
    return out


def selftest():
    sample = [{'group': '央视', 'title': 'CCTV1 综合', 'logo': '', 'uris': ['http://a/b.m3u8']},
              {'group': '凤凰', 'title': '凤凰资讯台', 'logo': 'L', 'uris': ['http://m/x.m3u8']}]
    m = merge(sample)
    assert [c['group'] for c in m] == ['央视', '凤凰', '凤凰', '凤凰']
    assert m[1]['uris'] == [FH % PHOENIX[0][1], 'http://m/x.m3u8'] and m[1]['logo'] == 'L'
    print('selftest ok')


if __name__ == '__main__':
    selftest()
    if '--selftest' in sys.argv:
        sys.exit(0)
    if any(a.startswith('-') for a in sys.argv[1:]):  # --selftest already handled above
        sys.exit(__doc__)
    args = sys.argv[1:]
    src = args[0] if args else IN
    dst = args[1] if len(args) > 1 else RAW
    chs = merge(json.load(open(src, encoding='utf-8')))
    txt = encode(json.dumps(chs, ensure_ascii=False, separators=(',', ':')))
    assert json.loads(decode(txt)) == chs
    open(dst, 'w', encoding='utf-8').write(txt)
    from collections import Counter
    print(len(chs), 'channels', dict(Counter(c['group'] for c in chs)), '->', dst)
