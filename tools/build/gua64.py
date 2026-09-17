#!/usr/bin/env python3
"""gua64: the base64 variant upstream uses, with the 64 I Ching hexagram glyphs as its
alphabet. This is the encoding of app/src/main/res/raw/channels.txt.

    python3 tools/build/gua64.py                        # self-test
    python3 tools/build/gua64.py encode in.json out.txt
    python3 tools/build/gua64.py decode in.txt
"""
import json, sys

GUA = "䷁䷖䷇䷓䷏䷢䷬䷋䷎䷳䷦䷴䷽䷷䷞䷠䷆䷃䷜䷺䷧䷿䷮䷅䷭䷑䷯䷸䷟䷱䷛䷫䷗䷚䷂䷩䷲䷔䷐䷘䷣䷕䷾䷤䷶䷝䷰䷌䷒䷨䷻䷼䷵䷥䷹䷉䷊䷙䷄䷈䷡䷍䷪䷀"


def decode(s):
    bits = ''.join(format(GUA.index(c), '06b') for c in s if c in GUA)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits) - 7, 8)).decode('utf-8', 'replace')


def encode(text):
    b = text.encode('utf-8')
    b += b' ' * (-len(b) % 3)  # pad with spaces so no partial group; app trims after decode
    bits = ''.join(format(x, '08b') for x in b)
    return ''.join(GUA[int(bits[i:i + 6], 2)] for i in range(0, len(bits), 6))


def selftest():
    sample = '[{"group":"央视","title":"CCTV1 综合","logo":"","uris":["http://a/b.m3u8"]}]'
    assert json.loads(decode(encode(sample))) == json.loads(sample)
    assert decode(encode('hi')).strip() == 'hi'
    # the hand-built vector from the original decoder, so a reshuffled alphabet is caught
    assert decode(''.join(GUA[i] for i in [(0x68 >> 2), ((0x68 & 3) << 4) | (0x69 >> 4),
                                           ((0x69 & 15) << 2)])) == 'hi'
    print('selftest ok')


if __name__ == '__main__':
    selftest()
    if len(sys.argv) > 1 and sys.argv[1] == 'encode':
        data = json.load(open(sys.argv[2], encoding='utf-8'))
        out = encode(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        assert json.loads(decode(out)) == data
        open(sys.argv[3], 'w', encoding='utf-8').write(out)
        print('ok', len(data), 'channels ->', sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == 'decode':
        print(decode(open(sys.argv[2], encoding='utf-8').read().strip()))
