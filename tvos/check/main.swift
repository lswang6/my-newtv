// swiftc NewMyTV/Shared/Playlist.swift check/main.swift -o $TMPDIR/check && $TMPDIR/check ../playlists/current.m3u ../app/src/main/res/raw/lite.m3u
import Foundation

let sample = """
#EXTM3U
#EXTINF:-1 tvg-name="A" tvg-logo="https://x/a.png" group-title="央视",CCTV1 综合
http://h/1.m3u8
#EXTINF:-1 group-title="央视",CCTV1 综合
#EXTVLCOPT:http-user-agent=UA
http://h/2.m3u8
#EXTINF:-1 group-title="凤凰",凤凰中文
http://127.0.0.1:34567/fh/x.flv
#EXTINF:-1 group-title="体育",Sport
http://h/s.flv
"""
let c = Playlist.parse(sample)
assert(c.count == 1, "flv/local entries dropped, duplicates merged")
assert(c[0].name == "CCTV1 综合" && c[0].group == "央视")
assert(c[0].sources.map(\.url.absoluteString) == ["http://h/1.m3u8", "http://h/2.m3u8"])
assert(c[0].sources[0].userAgent == nil && c[0].sources[1].userAgent == "UA")
let live = URL(string: "file:///x/live.m3u8")!
let hls = Playlist.channels(from: "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:6.0,\nseg.ts\n", url: live)
assert(hls.count == 1 && hls[0].name == "live.m3u8" && hls[0].group == "直播流" && hls[0].sources[0].url == live)
assert(Playlist.channels(from: "<html>404</html>", url: live).isEmpty)
for f in CommandLine.arguments.dropFirst() {
    let list = Playlist.parse(try! String(contentsOfFile: f, encoding: .utf8))
    print(f, list.count, "channels", list.reduce(0) { $0 + $1.sources.count }, "sources")
}
print("ok")
