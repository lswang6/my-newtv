import AVFoundation
import Combine

@MainActor
final class TV: ObservableObject {
    /// Bundled lists; only the macOS build ships them (App Store 5.2.3). List id "url" is the user's playlist.
    static let lists = [("current", "默认列表"), ("lite", "全球精简")]
        .filter { Bundle.main.url(forResource: $0.0, withExtension: "m3u") != nil }

    @Published private(set) var channels: [Channel] = []
    @Published private(set) var current = 0
    @Published private(set) var status = ""
    @Published private(set) var list = UserDefaults.standard.string(forKey: "list") ?? TV.lists.first?.0 ?? "url"
    @Published private(set) var playlistURL = UserDefaults.standard.string(forKey: "playlistURL") ?? ""

    /// Picker / list-switch options.
    var choices: [(String, String)] { TV.lists + (playlistURL.isEmpty ? [] : [("url", "我的列表")]) }

    let player = AVPlayer()
    private var sourceIndex = 0
    private var itemStatus: AnyCancellable?
    private var watchdog: Task<Void, Never>?

    init() { load(list) }

    func load(_ name: String) {
        guard let url = Bundle.main.url(forResource: name, withExtension: "m3u"),
              let text = try? String(contentsOf: url, encoding: .utf8) else {
            // "url", or a bundled list this build doesn't ship: the user's playlist.
            list = "url"
            if !playlistURL.isEmpty { Task { _ = await loadURL(playlistURL) } }
            return
        }
        show(name, Playlist.parse(text))
    }

    /// Loads an M3U playlist or a single HLS stream; returns an error message, nil on success.
    func loadURL(_ s: String) async -> String? {
        var s = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if !s.isEmpty, !s.contains("://") { s = "http://" + s }  // typed on a TV remote, the scheme is often left off
        do {
            // Bad input fails inside URLSession too, so the error alert never races the input alert's dismissal.
            let url = URL(string: s) ?? URL(string: "invalid:")!
            let (data, _) = try await URLSession.shared.data(from: url)
            let chs = Playlist.channels(from: String(decoding: data, as: UTF8.self), url: url)
            guard !chs.isEmpty else { return "没有找到可播放的频道" }
            playlistURL = s
            UserDefaults.standard.set(s, forKey: "playlistURL")
            show("url", chs)
            return nil
        } catch {
            return error.localizedDescription
        }
    }

    private func show(_ name: String, _ chs: [Channel]) {
        list = name
        UserDefaults.standard.set(name, forKey: "list")
        channels = chs
        play(UserDefaults.standard.integer(forKey: "channel.\(name)"))
    }

    func play(_ i: Int) {
        guard !channels.isEmpty else { return }
        current = (i % channels.count + channels.count) % channels.count
        UserDefaults.standard.set(current, forKey: "channel.\(list)")
        sourceIndex = 0
        start()
    }

    func step(_ delta: Int) { play(current + delta) }

    private func start() {
        let ch = channels[current]
        watchdog?.cancel()
        guard sourceIndex < ch.sources.count else {
            player.replaceCurrentItem(with: nil)
            status = "无法播放"
            return
        }
        let src = ch.sources[sourceIndex]
        let asset = AVURLAsset(url: src.url, options: src.userAgent.map { [AVURLAssetHTTPUserAgentKey: $0] })
        let item = AVPlayerItem(asset: asset)
        player.replaceCurrentItem(with: item)
        player.play()
        status = ch.sources.count > 1 ? "线路 \(sourceIndex + 1)/\(ch.sources.count)" : ""
        itemStatus = item.publisher(for: \.status)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] s in if s == .failed { self?.nextSource() } }
        // ponytail: fixed 15 s startup budget per source; make it a setting if slow links need more.
        watchdog = Task { [weak self] in
            try? await Task.sleep(for: .seconds(15))
            guard let self, !Task.isCancelled, self.player.currentItem === item,
                  self.player.timeControlStatus != .playing else { return }
            self.nextSource()
        }
    }

    private func nextSource() {
        sourceIndex += 1
        start()
    }
}
