#!/usr/bin/env python3
"""On-device playback verifier for the my-newtv apk (applicationId com.lizongying.newmytv).

Switches to each channel by its 1-based index using the digit keys, then reads
the app's own logcat to decide whether it actually plays.

Log signals (source: my-tv-0 app/src/main/java/com/lizongying/mytv0/):
  MainActivity:237  I/MainActivity: "<title> playing"    errInfo == ""
  MainActivity:241  I/MainActivity: "<title> <errInfo>"  errInfo == R.string.play_error
  MainActivity:255  I/MainActivity: "<title> 嘗試播放"    ready -> play(tvModel)
  PlayerFragment:147 I/PlayerFragment: "retry <i> <type> <n>/<max>"  onPlayerError
  PlayerFragment:113 I/PlayerFragment: "<title> 播放停止"  onIsPlayingChanged(false)

Trap: TVModel.setReady(retry=false) calls setErrInfo("") (TVModel.kt:97), so every
channel *switch* emits a bogus "<title> playing" immediately followed (same ms) by
"<title> 嘗試播放". Only a "playing" NOT followed by that attempt line is real.

    python3 verify_playback.py --serial <tv-ip>:5555 --count 10
    python3 verify_playback.py --selftest    # pure log-classifier checks, no TV needed
"""
import argparse, csv, re, struct, subprocess, sys, time

DEV = ""    # adb serial of the TV, set from --serial
PKG = "com.lizongying.newmytv"
# The applicationId was renamed but the Kotlin package was not, so the activity still
# lives under com.lizongying.mytv0.
CLS = "/com.lizongying.mytv0.MainActivity"

R_ATTEMPT = re.compile(r"I/MainActivity\(\s*\d+\): (.+) 嘗試播放\s*$")
R_OK = re.compile(r"I/MainActivity\(\s*\d+\): (.+) playing\s*$")
R_ERR = re.compile(r"I/MainActivity\(\s*\d+\): (.+) (?:播放错误|播放錯誤|Play error)\s*$")
R_STOP = re.compile(r"I/PlayerFragment\(\s*\d+\): (.+) 播放停止\s*$")
R_RETRY = re.compile(r"I/PlayerFragment\(\s*\d+\): retry \d+ \S+ \d+/\d+\s*$")
R_CAUSE = re.compile(r"ENETUNREACH|EHOSTUNREACH|ECONNREFUSED|ETIMEDOUT|UnknownHost"
                     r"|Caused by|Playback error|Response code|SocketTimeout|Unable to connect")


def adb(*args, binary=False, tries=2):
    """adb call with one automatic reconnect."""
    for n in range(tries):
        p = subprocess.run(["adb", "-s", DEV] + list(args), capture_output=True, timeout=120)
        if p.returncode == 0:
            return p.stdout if binary else p.stdout.decode("utf-8", "replace")
        if n + 1 < tries:
            subprocess.run(["adb", "connect", DEV], capture_output=True)
            time.sleep(2)
    return b"" if binary else ""


def classify(log):
    """-> (verdict, title, decisive_line). Pure function; see selftest()."""
    raw = log.splitlines()
    ev = []  # (kind, title, line, lineno)
    for n, ln in enumerate(raw):
        for kind, rx in (("ok", R_OK), ("attempt", R_ATTEMPT), ("err", R_ERR),
                         ("stop", R_STOP), ("retry", R_RETRY)):
            m = rx.search(ln)
            if m:
                ev.append((kind, "" if rx is R_RETRY else m.group(1), ln.strip(), n))
                break
    # Our switch is the pair '<T> playing' + '<T> 嘗試播放' (setReady -> setErrInfo("")).
    # Anchoring on it drops the previous channel's tail, which leaks into the window
    # while the three digit keys are being typed.
    pair = [i for i in range(len(ev) - 1)
            if ev[i][0] == "ok" and ev[i + 1][0] == "attempt" and ev[i + 1][1] == ev[i][1]]
    if not pair:
        return "UNKNOWN", "", "no switch pair '<title> playing'+'<title> 嘗試播放' (input refused?)"
    p = pair[-1]
    title, anchor, dec = ev[p][1], ev[p][3], None
    tail = ev[p + 2:]
    for i, (k, t, ln, _) in enumerate(tail):
        if k == "ok" and t == title and not (
                i + 1 < len(tail) and tail[i + 1][0] == "attempt" and tail[i + 1][1] == t):
            dec = ("PLAYING", ln)          # genuine onIsPlayingChanged(true)
        elif (k == "err" and t == title) or k == "retry":
            dec = ("FAILED", ln)           # last decisive event wins: played-then-died = FAILED
    if dec and dec[0] == "FAILED":
        cause = [l.strip() for l in raw[anchor:] if R_CAUSE.search(l)]
        return "FAILED", title, cause[-1] if cause else dec[1]
    if dec:
        return dec[0], title, dec[1]
    stop = [l for k, t, l, _ in tail if k == "stop" and t == title]
    if stop:
        return "UNKNOWN", title, stop[-1] + "  (stalled: stopped, never resumed)"
    return "UNKNOWN", title, "attempted, then silence (stuck buffering / no response)"


def luminance():
    """Mean luminance of the framebuffer, every 8th pixel. Advisory only:
    screencap usually returns black for a hardware video SurfaceView."""
    d = adb("exec-out", "screencap", binary=True)
    nl = d[:256].rfind(b"\n")  # this TV prints a junk banner before the header
    for off in ([nl + 1] if nl >= 0 else []) + [0]:
        if len(d) < off + 12:
            continue
        w, h, _ = struct.unpack("<III", d[off:off + 12])
        px = d[off + 12:]
        if 0 < w <= 8192 and 0 < h <= 8192 and len(px) >= w * h * 4:
            s = px[:w * h * 4:32]  # every 8th pixel -> its R byte; G,B follow
            return round(sum(0.299 * px[i * 32] + 0.587 * px[i * 32 + 1] + 0.114 * px[i * 32 + 2]
                             for i in range(len(s))) / max(1, len(s)), 1)
    return -1.0


def prime():
    """Relaunch if backgrounded, then make menuFragment 'hidden' so digit input works.
    MainActivity.showChannel() bails while !menuFragment.isHidden, and a fragment that
    was never added reports isHidden == false -- so CENTER (open) + BACK (hide) once."""
    if PKG + "/" not in adb("shell", "dumpsys window | grep mCurrentFocus"):
        adb("shell", "am", "start", "-n", PKG + CLS)
        time.sleep(8)
    for k, d in ((23, 2), (4, 2)):
        adb("shell", "input", "keyevent", str(k))
        time.sleep(d)


def probe(i, wait):
    adb("logcat", "-c")
    for ch in "%03d" % i:  # 3 digits -> ChannelFragment commits immediately (no 5s wait)
        adb("shell", "input", "keyevent", str(7 + int(ch)))
        time.sleep(0.4)
    time.sleep(wait)
    pid = adb("shell", "pidof", PKG).strip()
    log = adb("logcat", "-d", "-v", "time", "--pid=" + pid) if pid else ""
    v, t, d = classify(log)
    n = len(re.findall(r"D/MainActivity\(\s*\d+\): keyCode ", log))
    if n != 3:  # someone else is driving this TV -> the verdict may not be ours
        d += "  [TAINTED: %d keyCode lines, expected 3]" % n
    return (v, t, d), log


def selftest():
    P = "09-16 12:00:00.000 I/MainActivity( 111): "
    F = "09-16 12:00:00.000 I/PlayerFragment( 111): "
    sw = P + "BBC News playing\n" + P + "BBC News 嘗試播放\n" + F + "BBC News 播放停止"
    assert classify(sw)[0] == "UNKNOWN", "switch artifact + teardown stop is not PLAYING"
    assert classify(sw + "\n" + P + "BBC News playing") == ("PLAYING", "BBC News",
                                                            P + "BBC News playing")
    # previous channel's genuine 'playing' leaks in before our switch -> must be ignored
    v, t, _ = classify(P + "CCTV3 综艺 playing\n" + sw)
    assert (v, t) == ("UNKNOWN", "BBC News"), (v, t)
    v, t, d = classify(sw + "\n" + F + "retry 0 HLS 1/10\n"
                       "09-16 12:00:01.000 E/ExoPlayerImplInternal( 111): "
                       "Caused by: android.system.ErrnoException: connect failed: ENETUNREACH")
    assert (v, t) == ("FAILED", "BBC News") and "ENETUNREACH" in d, (v, t, d)
    assert classify(sw + "\n" + P + "BBC News 播放错误")[0] == "FAILED"
    # played, then died -> FAILED (last decisive event wins)
    assert classify(sw + "\n" + P + "BBC News playing\n" + F + "retry 0 HLS 1/10")[0] == "FAILED"
    assert classify("")[0] == "UNKNOWN"
    print("selftest ok")


def main():
    global DEV, PKG
    a = argparse.ArgumentParser()
    a.add_argument("--count", type=int, default=5)
    a.add_argument("--start", type=int, default=1)
    a.add_argument("--wait", type=float, default=12)
    a.add_argument("--only", help="comma-separated indices instead of --start/--count")
    a.add_argument("--serial", help="adb serial of the TV, e.g. <tv-ip>:5555")
    a.add_argument("--pkg", default=PKG, help="app package (default: %s)" % PKG)
    a.add_argument("--selftest", action="store_true")
    a.add_argument("--out", default="results.csv")
    a = a.parse_args()
    if a.selftest:
        return selftest()
    selftest()
    if not a.serial:
        sys.exit("--serial <tv-ip>:5555 is required (adb devices lists the TV once it is paired)")
    DEV, PKG = a.serial, a.pkg
    if "package:" + PKG not in adb("shell", "pm", "list", "packages"):
        sys.exit("%s is not installed on %s" % (PKG, DEV))
    print("package:", PKG, "on", DEV)
    prime()
    rows, tally = [], {}
    idx = [int(x) for x in a.only.split(",")] if a.only else \
        list(range(a.start, a.start + a.count))
    for i in idx:
        (v, t, d), log = probe(i, a.wait)
        if d.startswith("no switch pair"):  # input swallowed -> re-prime and retry once
            prime()
            (v, t, d), log = probe(i, a.wait)
        if v != "PLAYING":  # keep the evidence for failures: uri fallbacks, retries, causes
            with open("log_%03d.txt" % i, "w") as f:
                f.write(log)
        lum = luminance()
        tally[v] = tally.get(v, 0) + 1
        rows.append([i, t, v, d, lum])
        print("%3d  %-12s %-8s lum=%-6s %s" % (i, t, v, lum, d[:110]), flush=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "title", "verdict", "decisive_log_line", "luminance"])
        w.writerows(rows)
    print("summary:", ", ".join("%s=%d" % kv for kv in sorted(tally.items())), "->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
