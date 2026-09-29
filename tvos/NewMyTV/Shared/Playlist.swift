import Foundation

struct Source {
    let url: URL
    let userAgent: String?
}

struct Channel: Identifiable {
    let id: Int
    let name: String
    let group: String
    let logo: URL?
    var sources: [Source]
}

enum Playlist {
    /// Parses M3U; entries with the same group + name become fallback sources of one channel.
    static func parse(_ text: String) -> [Channel] {
        var channels: [Channel] = []
        var index: [String: Int] = [:]
        var name = "", group = "", logo: URL?, ua: String?
        for raw in text.split(whereSeparator: \.isNewline) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.hasPrefix("#EXTINF") {
                let cut = line.range(of: "\",", options: .backwards) ?? line.range(of: ",")
                name = cut.map { String(line[$0.upperBound...]).trimmingCharacters(in: .whitespaces) } ?? ""
                group = attr("group-title", line) ?? "其他"
                logo = attr("tvg-logo", line).flatMap(URL.init(string:))
                ua = nil
            } else if line.hasPrefix("#EXTVLCOPT:http-user-agent=") {
                ua = String(line.dropFirst("#EXTVLCOPT:http-user-agent=".count))
            } else if !line.hasPrefix("#"), !line.isEmpty, !name.isEmpty, let url = URL(string: line) {
                // ponytail: AVPlayer can't play FLV (Phoenix + a few others); TVVLCKit would cover them.
                guard url.pathExtension.lowercased() != "flv", url.host != "127.0.0.1" else { continue }
                let key = group + "\u{1}" + name
                if let i = index[key] {
                    channels[i].sources.append(Source(url: url, userAgent: ua))
                } else {
                    index[key] = channels.count
                    channels.append(Channel(id: channels.count, name: name, group: group, logo: logo,
                                            sources: [Source(url: url, userAgent: ua)]))
                }
                ua = nil
            }
        }
        return channels
    }

    /// `parse`, or a bare HLS stream (no channel entries) becomes one channel playing `url` itself.
    static func channels(from text: String, url: URL) -> [Channel] {
        let list = parse(text)
        guard list.isEmpty, text.contains("#EXT-X-") else { return list }
        return [Channel(id: 0, name: url.host ?? url.lastPathComponent, group: "直播流", logo: nil,
                        sources: [Source(url: url, userAgent: nil)])]
    }

    private static func attr(_ key: String, _ line: String) -> String? {
        guard let start = line.range(of: key + "=\"") else { return nil }
        guard let end = line[start.upperBound...].firstIndex(of: "\"") else { return nil }
        let value = String(line[start.upperBound..<end])
        return value.isEmpty ? nil : value
    }
}
