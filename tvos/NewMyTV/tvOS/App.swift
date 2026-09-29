import AVFoundation
import SwiftUI
import UIKit

@main
struct NewMyTVApp: App {
    init() {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
        UIApplication.shared.isIdleTimerDisabled = true
    }

    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

final class PlayerUIView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
}

struct PlayerLayer: UIViewRepresentable {
    let player: AVPlayer
    func makeUIView(context: Context) -> PlayerUIView {
        let v = PlayerUIView()
        (v.layer as! AVPlayerLayer).player = player
        return v
    }
    func updateUIView(_ v: PlayerUIView, context: Context) {}
}

struct ContentView: View {
    @StateObject private var tv = TV()
    @State private var showList = false
    @State private var showBanner = true
    @State private var askURL = false
    @State private var urlText = ""
    @State private var error: String?
    @Environment(\.scenePhase) private var scenePhase

    private func ask() { urlText = tv.playlistURL; askURL = true }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            PlayerLayer(player: tv.player).ignoresSafeArea()
            if showBanner || tv.status == "无法播放", tv.channels.indices.contains(tv.current) {
                let ch = tv.channels[tv.current]
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(tv.current + 1)  \(ch.name)").font(.title2.bold())
                    if !tv.status.isEmpty { Text(tv.status).font(.callout).foregroundStyle(.secondary) }
                }
                .padding(24)
                .background(.black.opacity(0.6), in: RoundedRectangle(cornerRadius: 16))
                .padding(60)
            }
            if tv.channels.isEmpty {
                VStack(spacing: 30) {
                    Text("还没有频道").font(.title2.bold())
                    Text("添加一个 M3U 播放列表或直播流 (m3u8) 链接").foregroundStyle(.secondary)
                    Button("添加播放列表") { ask() }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if showList {
                ChannelList(tv: tv, ask: { showList = false; ask() }) { showList = false }
                    .onExitCommand { showList = false }
            } else {
                // Remote target while the list is closed; the list is a sibling so its buttons stay focusable.
                Color.clear
                    .contentShape(Rectangle())
                    .focusable()
                    .onTapGesture { showList = true }
                    .onMoveCommand { dir in
                        switch dir {
                        case .up: tv.step(-1)
                        case .down: tv.step(1)
                        default: showList = true
                        }
                    }
            }
        }
        .background(Color.black)
        .alert("播放列表", isPresented: $askURL) {
            TextField("M3U 或 m3u8 链接", text: $urlText)
                .autocorrectionDisabled()
                .keyboardType(.URL)
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
            if phase == .active { tv.play(tv.current) }  // live buffer is stale after background
        }
    }
}

struct ChannelList: View {
    enum Focus: Hashable { case group(String), channel(Int) }

    @ObservedObject var tv: TV
    let ask: () -> Void
    let close: () -> Void
    @State private var group = ""
    @FocusState private var focus: Focus?

    private var groups: [String] {
        var seen = Set<String>()
        return tv.channels.map(\.group).filter { seen.insert($0).inserted }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 30) {
            VStack(alignment: .leading) {
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(groups, id: \.self) { g in
                            Button { group = g } label: {
                                Text((g == group ? "▸ " : "") + g).frame(maxWidth: .infinity, alignment: .leading)
                            }
                            .focused($focus, equals: .group(g))
                        }
                    }
                    .padding(20)
                }
                Divider().padding(.vertical)
                // Below the groups so a stray Left from the channels doesn't land on a list switch.
                ForEach(tv.choices, id: \.0) { id, title in
                    Button { tv.load(id) } label: {
                        Text(title + (tv.list == id ? " ✓" : "")).frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                Button(action: ask) {
                    Text("播放列表链接…").frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(width: 380)
            .focusSection()

            ScrollView {
                VStack(spacing: 12) {
                    ForEach(tv.channels.filter { $0.group == group }) { ch in
                        Button { tv.play(ch.id); close() } label: {
                            HStack(spacing: 20) {
                                AsyncImage(url: ch.logo) { $0.resizable().scaledToFit() } placeholder: { Color.clear }
                                    .frame(width: 80, height: 45)
                                Text("\(ch.id + 1)").monospacedDigit().foregroundStyle(.secondary)
                                Text(ch.name)
                                Spacer()
                                if ch.id == tv.current { Image(systemName: "play.fill") }
                            }
                        }
                        .focused($focus, equals: .channel(ch.id))
                    }
                }
                .padding(20)
            }
            .frame(width: 720)
            .focusSection()
        }
        .padding(50)
        .frame(maxHeight: .infinity)
        .background(Color.black.opacity(0.85))
        .defaultFocus($focus, .channel(tv.current))
        .onChange(of: focus) { _, f in if case .group(let g)? = f { group = g } }
        .onChange(of: groups) { _, g in group = g.first ?? "" }  // list switched (the URL list loads async)
        .onAppear {
            guard tv.channels.indices.contains(tv.current) else { return }
            group = tv.channels[tv.current].group
            focus = .channel(tv.current)
        }
    }
}
