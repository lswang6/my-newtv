import AVFoundation
import SwiftUI

@main
struct NewMyTVApp: App {
    init() {
        #if os(iOS)
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
        UIApplication.shared.isIdleTimerDisabled = true
        #endif
    }

    var body: some Scene {
        WindowGroup { ContentView() }
        #if os(macOS)
            .defaultSize(width: 1200, height: 720)
        #endif
    }
}

struct ContentView: View {
    @StateObject private var tv = TV()
    @State private var column = NavigationSplitViewColumn.detail
    @State private var query = ""
    @State private var showBanner = true
    @State private var wasBackground = false
    @State private var askURL = false
    @State private var urlText = ""
    @State private var error: String?
    @Environment(\.scenePhase) private var scenePhase

    /// Channels grouped in playlist order, filtered by the search text.
    private var groups: [(String, [Channel])] {
        var order: [String] = [], by: [String: [Channel]] = [:]
        for ch in tv.channels where query.isEmpty || ch.name.localizedCaseInsensitiveContains(query) {
            if by[ch.group] == nil { order.append(ch.group) }
            by[ch.group, default: []].append(ch)
        }
        return order.map { ($0, by[$0]!) }
    }

    private func ask() { urlText = tv.playlistURL; askURL = true }

    private var empty: some View {
        ContentUnavailableView {
            Label("还没有频道", systemImage: "tv")
        } description: {
            Text("添加一个 M3U 播放列表或直播流 (m3u8) 链接")
        } actions: {
            Button("添加播放列表") { ask() }
        }
    }

    var body: some View {
        NavigationSplitView(preferredCompactColumn: $column) {
            // List re-writes the selection on its own (macOS); only a real change may restart the stream.
            List(selection: Binding { tv.current } set: { i in
                // Same-value writes come on appear/scroll/search; bouncing to the player on those closes the list (iPhone).
                guard let i, i != tv.current else { return }
                tv.play(i)
                column = .detail
            }) {
                ForEach(groups, id: \.0) { group, chs in
                    Section(group) {
                        ForEach(chs) { ch in
                            HStack {
                                AsyncImage(url: ch.logo) { $0.resizable().scaledToFit() } placeholder: { Color.clear }
                                    .frame(width: 40, height: 24)
                                Text("\(ch.id + 1)").monospacedDigit().foregroundStyle(.secondary)
                                Text(ch.name)
                                Spacer()
                                if ch.id == tv.current { Image(systemName: "play.fill") }
                            }
                            .tag(ch.id)
                        }
                    }
                }
            }
            .overlay { if tv.channels.isEmpty { empty } }
            .safeAreaInset(edge: .top) {
                if tv.choices.count > 1 {
                    Picker("列表", selection: Binding { tv.list } set: { if $0 != tv.list { tv.load($0) } }) {
                        ForEach(tv.choices, id: \.0) { id, title in Text(title).tag(id) }
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                    .padding(.horizontal)
                }
            }
            .toolbar { Button("播放列表", systemImage: "link") { ask() } }
            .searchable(text: $query)
            .navigationSplitViewColumnWidth(min: 260, ideal: 320)
            .navigationTitle("我的电视")
        } detail: {
            PlayerView(player: tv.player)
                .overlay { if tv.channels.isEmpty { empty.environment(\.colorScheme, .dark) } }
                .overlay(alignment: .topLeading) {
                    if showBanner || tv.status == "无法播放", tv.channels.indices.contains(tv.current) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(tv.current + 1)  \(tv.channels[tv.current].name)").font(.headline)
                            if !tv.status.isEmpty { Text(tv.status).font(.caption).opacity(0.8) }
                        }
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(.black.opacity(0.6), in: RoundedRectangle(cornerRadius: 8))
                        .padding()
                        .allowsHitTesting(false)
                    }
                }
                .background(Color.black)
                .toolbar {
                    Button("上一个", systemImage: "chevron.up") { tv.step(-1) }
                        .keyboardShortcut(.upArrow, modifiers: [])
                    Button("下一个", systemImage: "chevron.down") { tv.step(1) }
                        .keyboardShortcut(.downArrow, modifiers: [])
                }
        }
        .alert("播放列表", isPresented: $askURL) {
            TextField("M3U 或 m3u8 链接", text: $urlText)
                .autocorrectionDisabled()
            #if os(iOS)
                .keyboardType(.URL)
                .textInputAutocapitalization(.never)
            #endif
            Button("添加") { Task { error = await tv.loadURL(urlText) } }
            Button("取消", role: .cancel) {}
        }
        .alert(error ?? "", isPresented: Binding { error != nil } set: { if !$0 { error = nil } }) {}
        .task(id: tv.current) {
            showBanner = true
            try? await Task.sleep(for: .seconds(4))
            showBanner = false
        }
        .onChange(of: scenePhase) { _, phase in
            // iOS only: macOS flips scenePhase on every window focus change.
            #if os(iOS)
            // Live buffer is stale after background; Control Centre only goes inactive, so it doesn't restart.
            if phase == .background { wasBackground = true }
            if phase == .active, wasBackground { wasBackground = false; tv.play(tv.current) }
            #endif
        }
    }
}

// ponytail: bare AVPlayerLayer, no transport controls. AVKit's VideoPlayer/AVPlayerView/controls trap inside AVKit
// once a live item loads on macOS 27 (SIGTRAP in AVKit's SwiftUI Binding getter); switch back when Apple fixes it.
#if os(macOS)
struct PlayerView: NSViewRepresentable {
    let player: AVPlayer
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        v.layer = AVPlayerLayer(player: player)
        v.wantsLayer = true
        return v
    }
    func updateNSView(_ v: NSView, context: Context) {}
}
#else
final class PlayerUIView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
}

struct PlayerView: UIViewRepresentable {
    let player: AVPlayer
    func makeUIView(context: Context) -> PlayerUIView {
        let v = PlayerUIView()
        (v.layer as! AVPlayerLayer).player = player
        return v
    }
    func updateUIView(_ v: PlayerUIView, context: Context) {}
}
#endif
