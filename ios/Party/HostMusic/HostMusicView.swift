import SwiftUI

/// « Gérer la soirée » en natif : tout ce que contient la page admin de la musique, rangé en sections repliables.
/// L'ancienne version (page) reste accessible par le menu « … ».
struct HostMusicView: View {
    @ObservedObject var store: HostMusicStore
    let topInset: CGFloat
    /// « Vue invité » : l'écran Musique des invités.
    let guestView: () -> Void
    /// « Ancienne version » : la page admin, en secours.
    let pageView: () -> Void

    @AppStorage("hostQueueShowPlaylist") private var showPlaylist = false
    @State private var dragging = false
    @State private var confirmStop = false
    @State private var volume: Double?

    var body: some View {
        ScrollViewReader { reader in
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    header
                    content
                }
                // Chargement → écran, soirée lancée ou arrêtée : fondu posé, pas à chaque rafraîchissement.
                .motion(Motion.smooth, value: store.phase)
                .motion(Motion.smooth, value: store.state?.active)
                .padding(.horizontal, 16)
                .padding(.top, topInset + 8)
                .padding(.bottom, 32)
            }
            #if DEBUG
            .task {  // captures : PARTY_DEBUG_HOST_ANCHOR=<section> fait défiler jusqu'à elle
                guard let anchor = ProcessInfo.processInfo.environment["PARTY_DEBUG_HOST_ANCHOR"] else { return }
                try? await Task.sleep(for: .seconds(1.5))
                reader.scrollTo(anchor, anchor: .top)
            }
            #endif
        }
        .tint(Palette.accent)
        .scrollDisabled(dragging)
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await store.reload() }
        .background(AppConfig.background.ignoresSafeArea())
        .overlay(alignment: .bottom) { noticeBanner }
        .onAppear { store.start() }
        .onDisappear { store.stop() }
        .confirmationDialog("Arrêter la soirée ?", isPresented: $confirmStop, titleVisibility: .visible) {
            Button("Arrêter la soirée", role: .destructive) { Task { await store.stopParty() } }
        } message: { Text("La file des invités se ferme.") }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Gérer la soirée").font(.title.weight(.heavy)).lineLimit(1).minimumScaleFactor(0.7)
                if let state = store.state, state.active {
                    HStack(spacing: 6) {
                        Text("● Soirée en cours").font(.caption.weight(.bold)).foregroundStyle(.green)
                        Text(state.placeLabel).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                    .transition(.opacity)
                }
            }
            Spacer(minLength: 8)
            Button(action: guestView) { Label("Vue invité", systemImage: "person.2") }
                .buttonStyle(.bordered).tint(Palette.accent)
            Menu {
                Button(action: pageView) { Label("Ancienne version (page)", systemImage: "safari") }
                Button { Task { await store.reload() } } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
            } label: {
                Image(systemName: "ellipsis.circle").font(.title2)
            }
            .accessibilityLabel("Plus d'options")
        }
    }

    @ViewBuilder
    private var content: some View {
        switch store.phase {
        case .loading:
            ProgressView().frame(maxWidth: .infinity).padding(.top, 40).transition(.opacity)
        case .failed(let message):
            VStack(spacing: 12) {
                Text(message).multilineTextAlignment(.center).foregroundStyle(.secondary)
                Button("Réessayer") { Haptics.tap(); Task { await store.reload() } }.buttonStyle(.borderedProminent).tint(Palette.accent)
                Button("Ancienne version (page)", action: pageView)
            }
            .frame(maxWidth: .infinity).padding(.top, 30)
            .motionTransition()
        case .ready:
            if let state = store.state {
                if state.active { live(state) } else { HostSetupView(store: store).motionTransition() }
            }
        }
    }

    @ViewBuilder
    private func live(_ state: AdminState) -> some View {
        if let warning = state.warning {
            Text(warning).font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(Color.orange.opacity(0.25))
                .motionTransition()
        }
        nowPlaying(state)
        HostAddSection(store: store, state: state)
        queueSection(state)
        HostAccessSection(store: store, state: state)
        if !state.usesSpotify { HostModeSection(store: store, state: state) }
        HostTopSection(store: store, state: state)
        if state.hasSpeakers { HostSpeakersSection(store: store) }
        HostRequestsSection(store: store, state: state)
        HostSection("Compte Spotify", symbol: "music.note", key: "spotify", openByDefault: false) {
            SpotifyAccountCard(store: store)
        }
        HostButton(title: "Arrêter la soirée", symbol: "stop.circle", role: .destructive, busy: store.busy.contains("stop")) {
            confirmStop = true
        }
        .padding(.top, 10)
    }

    // MARK: En cours, lecture, volume

    private func nowPlaying(_ state: AdminState) -> some View {
        let playback = state.sonos
        return VStack(spacing: 12) {
            HStack(spacing: 12) {
                HostArtwork(path: playback?.now.art ?? "", load: store.artwork, size: 64)
                VStack(alignment: .leading, spacing: 3) {
                    Text(playback.map { $0.isPlaying ? "▶︎ En cours" : "⏸ \($0.state)" } ?? "")
                        .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    // Titre suivant : fondu enchaîné entre l'ancien et le nouveau titre.
                    VStack(alignment: .leading, spacing: 3) {
                        Text(playback?.now.title.isEmpty == false ? playback!.now.title : "Rien ne joue")
                            .font(.headline).lineLimit(2)
                        if let artist = playback?.now.artist, !artist.isEmpty { Text(artist).font(.subheadline).foregroundStyle(.secondary).lineLimit(1) }
                        if let by = playback?.now.by { Text("ajouté par \(by)").font(.caption2.weight(.semibold)).foregroundStyle(Palette.accent) }
                    }
                    .id(playback?.now.title ?? "")
                    .transition(.opacity)
                }
                Spacer(minLength: 0)
            }
            .motion(Motion.smooth, value: playback?.now.title ?? "")
            HStack(spacing: 10) {
                Button { Haptics.tap(); Task { await store.togglePlayback() } } label: {
                    Label(playback?.isPlaying == true ? "Pause" : "Lecture", systemImage: playback?.isPlaying == true ? "pause.fill" : "play.fill")
                        .frame(maxWidth: .infinity, minHeight: 30)
                }
                .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(store.busy.contains("playback"))
                Button { Haptics.tap(); Task { await store.skip() } } label: {
                    Label("Passer", systemImage: "forward.fill").frame(maxWidth: .infinity, minHeight: 30)
                }
                .buttonStyle(.bordered).disabled(store.busy.contains("skip"))
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(state.source == "spotify" ? "Volume (téléphone)" : "Volume global (toutes les enceintes du groupe)")
                    .font(.caption).foregroundStyle(.secondary)
                HStack {
                    Image(systemName: "speaker.fill").foregroundStyle(.secondary)
                    Slider(value: Binding(get: { volume ?? Double(playback?.volume ?? 0) }, set: { value in
                        volume = value
                        store.setVolume(Int(value))
                    }), in: 0...100, step: 1, onEditingChanged: { editing in
                        if !editing { Task { try? await Task.sleep(for: .seconds(3)); volume = nil } }
                    })
                    .tint(Palette.accent)
                    .accessibilityLabel("Volume")
                    Image(systemName: "speaker.wave.3.fill").foregroundStyle(.secondary)
                    Text("\(Int(volume ?? Double(playback?.volume ?? 0)))").font(.caption.monospacedDigit()).frame(width: 30)
                        .contentTransition(.numericText())
                        .motion(Motion.snappy, value: volume == nil ? playback?.volume ?? 0 : -1)
                }
            }
        }
        .card()
    }

    // MARK: File d'attente

    private func queueSection(_ state: AdminState) -> some View {
        let playlistCount = state.queue.filter { !$0.isRequest }.count
        let shown = QueueOrder.visible(state.queue, showPlaylist: showPlaylist)
        return HostSection("File d'attente", symbol: "list.number", badge: state.queue.isEmpty ? nil : "\(state.queue.count)", key: "queue") {
            VStack(alignment: .leading, spacing: 8) {
                Text(state.queueEditable
                     ? "≡ appui long puis glisser pour réorganiser · « … » pour jouer ensuite, maintenant ou retirer"
                     : "Aperçu de la file Spotify : change l'ordre ou retire des titres directement dans Spotify.")
                    .font(.footnote).foregroundStyle(.secondary)
                if state.queue.isEmpty {
                    Text(state.usesSpotify ? "Aucun titre à venir renvoyé par Spotify" : "La file est vide")
                        .font(.subheadline).foregroundStyle(.secondary)
                } else if shown.isEmpty {
                    Text("Aucune demande des invités pour l'instant").font(.subheadline).foregroundStyle(.secondary)
                } else {
                    HostQueueList(tracks: shown, editable: state.queueEditable, receivedAt: store.stateAt, busy: store.busy,
                                  dragging: $dragging,
                                  action: { track, action in Task { await store.queueAction(track, action) } },
                                  move: { track, position in Task { await store.move(track, to: position) } },
                                  artwork: store.artwork)
                }
                if playlistCount > 0 {
                    Button {
                        Haptics.tap()
                        Motion.animate(Motion.smooth) { showPlaylist.toggle() }
                    } label: {
                        Label(showPlaylist ? "Masquer les titres de la playlist" : "Voir les \(playlistCount) titre\(playlistCount > 1 ? "s" : "") de la playlist",
                              systemImage: showPlaylist ? "eye.slash" : "music.note.list")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
    }

    // MARK: Messages

    private var noticeBanner: some View {
        let notice = store.notice
        return NoticeBanner(
            notice: notice.map { NoticeBanner.Notice(text: $0.text, isError: $0.isError, id: $0.id) },
            action: notice?.undo.map { token in
                NoticeBanner.Action(title: "Annuler") {
                    store.notice = nil
                    Task { await store.undo(token) }
                }
            },
            seconds: notice?.undo == nil ? 3 : 6
        ) {
            if store.notice?.id == notice?.id { store.notice = nil }
        }
    }

}
