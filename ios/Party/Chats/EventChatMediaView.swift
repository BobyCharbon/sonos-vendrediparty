import SwiftUI

/// « Médias, liens et vocaux » de la discussion d'un événement, façon WhatsApp : grille des photos, liste des liens,
/// liste des vocaux (écoute sur place). Un toucher sur une photo l'ouvre en plein écran (« Voir dans la discussion »),
/// sur un lien l'ouvre, et « Voir le message » ramène au message (store.jumpTo, par onJump).
struct EventChatMediaView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case photo, link, audio
        var id: String { rawValue }
        var title: String { self == .photo ? "Médias" : self == .link ? "Liens" : "Vocaux" }
    }

    @ObservedObject var store: ChatsStore
    var initial: Tab = .photo
    let onJump: (String) -> Void

    @State private var tab: Tab = .photo
    @State private var items: [ChatMediaItem] = []
    @State private var loading = true
    @State private var more = true
    @State private var viewing: ChatMediaItem?
    @StateObject private var player = VoicePlayer()

    static let page = 60

    private var shown: [ChatMediaItem] { items.filter { $0.kind == tab.rawValue } }

    var body: some View {
        VStack(spacing: 0) {
            Picker("Afficher", selection: $tab) {
                ForEach(Tab.allCases) { Text($0.title).tag($0) }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16).padding(.vertical, 10)
            .onChange(of: tab) { _ in Haptics.selection() }

            ScrollView {
                Group {
                    if shown.isEmpty && !loading {
                        empty.padding(.top, 80)
                    } else {
                        switch tab {
                        case .photo: grid
                        case .link: links
                        case .audio: voices
                        }
                    }
                }
                .id(tab)
                .transition(.opacity)
                if loading {
                    ProgressView().padding(24)
                } else if more && !items.isEmpty {
                    // Bas de la liste atteint : la page précédente se charge toute seule.
                    Color.clear.frame(height: 1).onAppear { Task { await load() } }
                }
            }
        }
        .background(AppConfig.background.ignoresSafeArea())
        .motion(Motion.smooth, value: tab)
        .motion(Motion.smooth, value: items.count)
        .navigationTitle("Médias, liens et vocaux")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            tab = initial
            if items.isEmpty { await load() }
        }
        .onDisappear { player.stop() }
        .fullScreenCover(item: $viewing) { item in
            EventChatPhotoViewer(item: item) { onJump(item.messageId) }
        }
    }

    private func load() async {
        guard more else { return }
        loading = true
        let page = await store.media(before: items.last?.at)
        let known = Set(items.map(\.url))
        items += page.filter { !known.contains($0.url) }
        more = page.count >= Self.page
        loading = false
    }

    // MARK: Photos

    private var grid: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 2), count: 3), spacing: 2) {
            ForEach(shown, id: \.url) { item in
                Button {
                    Haptics.tap()
                    viewing = item
                } label: {
                    Color.white.opacity(0.06)
                        .aspectRatio(1, contentMode: .fit)
                        .overlay {
                            AsyncImage(url: URL(string: item.url), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
                                if let image = phase.image { image.resizable().scaledToFill().transition(.opacity) } else { ProgressView() }
                            }
                        }
                        .clipped()
                        .contentShape(Rectangle())
                }
                .buttonStyle(PressableStyle(scale: 0.97))
                .accessibilityLabel("Photo de \(item.authorName), \(ChatDates.short(item.at))")
                .accessibilityHint("Ouvre la photo en plein écran")
            }
        }
    }

    // MARK: Liens

    private var links: some View {
        LazyVStack(spacing: 0) {
            ForEach(shown, id: \.url) { item in
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "link").font(.title3).foregroundStyle(.tint)
                        .frame(width: 44, height: 44).background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    VStack(alignment: .leading, spacing: 3) {
                        if let url = URL(string: item.url) {
                            Link(destination: url) {
                                Text(url.host ?? item.url).font(.subheadline.weight(.semibold)).lineLimit(1)
                            }
                            Text(item.url).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        }
                        if let text = item.text, !text.isEmpty {
                            Text(text).font(.footnote).lineLimit(2)
                        }
                        Text("\(item.authorName) · \(ChatDates.short(item.at))").font(.caption2).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    jumpButton(item)
                }
                .padding(.horizontal, 16).padding(.vertical, 10)
                Divider().padding(.leading, 72)
            }
        }
    }

    // MARK: Vocaux

    private var voices: some View {
        LazyVStack(spacing: 0) {
            ForEach(shown, id: \.url) { item in
                let active = player.playing == item.url
                HStack(spacing: 12) {
                    Button {
                        Haptics.tap()
                        if let url = URL(string: item.url) { player.toggle(id: item.url, url: url) }
                    } label: {
                        Image(systemName: active ? "pause.fill" : "play.fill").font(.title3)
                            .frame(width: 44, height: 44).foregroundStyle(.black)
                            .background(Color(uiColor: AppConfig.uiAccent), in: Circle())
                    }
                    .buttonStyle(PressableStyle())
                    .accessibilityLabel(active ? "Pause" : "Écouter le vocal de \(item.authorName)")
                    VStack(alignment: .leading, spacing: 6) {
                        Text(item.authorName).font(.subheadline.weight(.semibold))
                            .foregroundStyle(ChatTimeline.nameColor(for: item.authorName))
                        ProgressView(value: active ? player.progress : 0).tint(Color(uiColor: AppConfig.uiAccent))
                        Text(ChatDates.short(item.at)).font(.caption2).foregroundStyle(.secondary)
                    }
                    jumpButton(item)
                }
                .padding(.horizontal, 16).padding(.vertical, 10)
                Divider().padding(.leading, 72)
            }
        }
    }

    private func jumpButton(_ item: ChatMediaItem) -> some View {
        Button {
            Haptics.tap()
            player.stop()
            onJump(item.messageId)
        } label: {
            Image(systemName: "arrow.uturn.left.circle").font(.title3).foregroundStyle(.secondary)
        }
        .buttonStyle(.borderless)
        .accessibilityLabel("Voir le message dans la discussion")
    }

    private var empty: some View {
        VStack(spacing: 10) {
            Image(systemName: tab == .photo ? "photo.on.rectangle.angled" : tab == .link ? "link" : "waveform")
                .font(.system(size: 40)).foregroundStyle(.secondary)
            Text(tab == .photo ? "Aucune photo" : tab == .link ? "Aucun lien" : "Aucun vocal").font(.headline)
            Text("Ce qui est partagé dans la discussion apparaît ici.").font(.subheadline).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 32)
    }
}

/// Photo en plein écran : pincer pour zoomer, double toucher, glisser vers le bas pour fermer ; « Voir dans la
/// discussion » ramène au message.
struct EventChatPhotoViewer: View {
    let item: ChatMediaItem
    let onJump: () -> Void
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var scale: CGFloat = 1
    @State private var lastScale: CGFloat = 1
    @State private var drag: CGSize = .zero

    var body: some View {
        ZStack {
            Color.black.opacity(1 - min(0.6, abs(drag.height) / 600)).ignoresSafeArea()
            AsyncImage(url: URL(string: item.url)) { phase in
                if let image = phase.image { image.resizable().scaledToFit() } else { ProgressView().tint(.white) }
            }
            .scaleEffect(scale)
            .offset(scale > 1 ? .zero : drag)
            .gesture(MagnificationGesture()
                .onChanged { scale = max(1, min(4, lastScale * $0)) }
                .onEnded { _ in lastScale = scale })
            .simultaneousGesture(DragGesture()
                .onChanged { if scale <= 1 { drag = $0.translation } }
                .onEnded { value in
                    if scale <= 1 && abs(value.translation.height) > 120 { dismiss() } else { Motion.animate { drag = .zero } }
                })
            .onTapGesture(count: 2) {
                Motion.animate(Motion.snappy) { scale = scale > 1 ? 1 : 2.5; lastScale = scale }
            }
            .accessibilityLabel("Photo de \(item.authorName)")
            .accessibilityAddTraits(.isImage)
        }
        .overlay(alignment: .top) {
            HStack {
                Button { dismiss() } label: {
                    Image(systemName: "xmark").font(.headline).frame(width: 40, height: 40).background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel("Fermer")
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text(item.authorName).font(.subheadline.weight(.semibold))
                    Text(ChatDates.short(item.at)).font(.caption).foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16).padding(.top, 8)
            .foregroundStyle(.white)
        }
        .overlay(alignment: .bottom) {
            Button {
                Haptics.tap()
                dismiss()
                // Après la fermeture du plein écran : la feuille des infos se ferme à son tour.
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { onJump() }
            } label: {
                Label("Voir dans la discussion", systemImage: "bubble.left.and.text.bubble.right")
                    .font(.subheadline.weight(.semibold)).padding(.horizontal, 18).padding(.vertical, 12)
                    .background(.ultraThinMaterial, in: Capsule())
            }
            .foregroundStyle(.white)
            .padding(.bottom, 24)
            .opacity(drag == .zero ? 1 : 0)
        }
        .animation(reduceMotion ? nil : Motion.snappy, value: drag == .zero)
        .preferredColorScheme(.dark)
    }
}
