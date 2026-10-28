import SwiftUI

/// Top playlists : lancer en aléatoire (remplace la file, garde les demandes), monter, retirer, ajouter.
struct HostTopSection: View {
    @ObservedObject var store: HostMusicStore
    let state: AdminState
    @State private var link = ""
    @State private var toLaunch: AdminState.TopPlaylist?

    var body: some View {
        HostSection("Top playlists", symbol: "music.note.list", badge: count, key: "top", openByDefault: false) {
            VStack(alignment: .leading, spacing: 8) {
                Text("▶︎ remplace la file et lance la playlist en aléatoire. Les demandes en attente sont gardées et passent en premier.")
                    .font(.footnote).foregroundStyle(.secondary)
                if state.topPlaylists.isEmpty {
                    Text("Aucune playlist : ajoute un lien Spotify ci-dessous").font(.subheadline).foregroundStyle(.secondary).card()
                }
                ForEach(Array(state.topPlaylists.enumerated()), id: \.element.id) { index, playlist in
                    row(playlist, index: index)
                }
                addForm
            }
        }
        .confirmationDialog("Lancer « \(toLaunch?.title ?? "") » en aléatoire ?", isPresented: Binding(
            get: { toLaunch != nil }, set: { if !$0 { toLaunch = nil } }), titleVisibility: .visible) {
            Button("Lancer") { if let toLaunch { Task { await store.launch(toLaunch) } } }
        } message: { Text("La file actuelle sera remplacée (les demandes en attente sont gardées).") }
    }

    private var count: String? { state.topPlaylists.isEmpty ? nil : "\(state.topPlaylists.count)" }

    private func row(_ playlist: AdminState.TopPlaylist, index: Int) -> some View {
        let launchable = state.active && (!state.usesSpotify || playlist.id.hasPrefix("spotify:playlist:"))
        return HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text((playlist.isSpotify ? "🟢 " : "🔀 ") + playlist.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text(playlist.isSpotify ? "Spotify" : "Sonos").font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Button { toLaunch = playlist } label: { Image(systemName: "play.fill") }
                .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(!launchable || store.busy.contains("launch.\(playlist.id)"))
                .accessibilityLabel("Lancer en aléatoire")
            Menu {
                if index > 0 {
                    Button { Task { await store.editTop(["action": "up", "id": playlist.id]) } } label: { Label("Monter", systemImage: "arrow.up") }
                }
                Button(role: .destructive) { Task { await store.editTop(["action": "remove", "id": playlist.id]) } } label: {
                    Label("Retirer de la liste", systemImage: "trash")
                }
            } label: { Image(systemName: "ellipsis.circle").font(.title3).frame(width: 36, height: 36) }
            .accessibilityLabel("Actions pour \(playlist.title)")
        }
        .card()
    }

    private var addForm: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                TextField("Lien Spotify d'une playlist", text: $link).autocorrectionDisabled().textInputAutocapitalization(.never)
                Button("Ajouter") {
                    let url = link.trimmingCharacters(in: .whitespaces)
                    Task { await store.editTop(["action": "add", "url": url], message: "Playlist ajoutée"); link = "" }
                }
                .disabled(link.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .card()
            if !state.usesSpotify || state.source == "spotify_sonos" {
                Menu {
                    if store.sonosPlaylists.isEmpty { Text("Chargement…") }
                    ForEach(store.sonosPlaylists) { p in
                        Button("\(p.kind == "sonos" ? "Playlist" : "Favori") · \(p.title)") {
                            Task { await store.editTop(["action": "add", "id": p.id], message: "Playlist ajoutée") }
                        }
                    }
                } label: {
                    Label("Depuis Sonos (playlists et favoris)", systemImage: "hifispeaker.2").frame(maxWidth: .infinity, alignment: .leading)
                }
                .card()
                .task { await store.loadSonosPlaylists() }
            }
        }
    }
}

/// Enceintes du groupe de la soirée : ajouter, retirer, volume de chacune (relues toutes les 10 s, section ouverte).
struct HostSpeakersSection: View {
    @ObservedObject var store: HostMusicStore
    @State private var volumes: [String: Double] = [:]
    private static let refresh: Duration = .seconds(10)

    var body: some View {
        HostSection("Enceintes", symbol: "hifispeaker.2.fill", key: "speakers", openByDefault: false) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Ajoute des enceintes au groupe de la soirée ; chaque curseur règle une enceinte.")
                    .font(.footnote).foregroundStyle(.secondary)
                if let error = store.speakersError { Text(error).font(.subheadline).foregroundStyle(.secondary) }
                if store.speakers.isEmpty && store.speakersError == nil { ProgressView().frame(maxWidth: .infinity) }
                ForEach(store.speakers) { speaker in row(speaker) }
            }
            .task {
                while !Task.isCancelled {
                    await store.loadSpeakers()
                    try? await Task.sleep(for: Self.refresh)
                }
            }
        }
    }

    private func row(_ speaker: Speaker) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text((speaker.inGroup ? "🔊 " : "🔈 ") + speaker.name).font(.subheadline.weight(.semibold))
                    Text(speaker.coordinator ? "enceinte principale de la soirée" : speaker.inGroup ? "dans le groupe" : "hors du groupe")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                if !speaker.coordinator {
                    if store.busy.contains("sp.\(speaker.uid)") {
                        ProgressView()
                    } else {
                        Button(speaker.inGroup ? "Retirer" : "＋ Ajouter") { Task { await store.group(speaker, join: !speaker.inGroup) } }
                            .buttonStyle(.bordered).tint(speaker.inGroup ? .red : Palette.accent)
                    }
                }
            }
            HStack {
                Image(systemName: "speaker.fill").foregroundStyle(.secondary)
                Slider(value: Binding(get: { volumes[speaker.uid] ?? Double(speaker.volume) }, set: { value in
                    volumes[speaker.uid] = value
                    store.setSpeakerVolume(speaker, Int(value))
                }), in: 0...100, step: 1)
                .tint(Palette.accent)
                .accessibilityLabel("Volume \(speaker.name)")
                Text("\(Int(volumes[speaker.uid] ?? Double(speaker.volume)))").font(.caption.monospacedDigit()).frame(width: 30)
            }
        }
        .opacity(speaker.inGroup ? 1 : 0.75)
        .card()
    }
}

/// Toutes les demandes de la soirée (en attente, jouées, retirées), avec retrait des demandes en attente.
struct HostRequestsSection: View {
    @ObservedObject var store: HostMusicStore
    let state: AdminState

    var body: some View {
        HostSection("Demandes des invités", symbol: "person.2.wave.2", badge: badge, key: "requests", openByDefault: false) {
            VStack(spacing: 6) {
                if state.requests.isEmpty { Text("Aucune demande pour l'instant").font(.subheadline).foregroundStyle(.secondary) }
                ForEach(state.requests) { request in row(request) }
            }
        }
    }

    private var badge: String? {
        let waiting = state.requests.filter { $0.status == "queued" }.count
        return state.requests.isEmpty ? nil : "\(waiting) en attente · \(state.requests.count)"
    }

    private func row(_ request: AdminState.GuestRequest) -> some View {
        let labels = ["queued": state.usesSpotify ? "envoyé à Spotify" : "en attente", "played": "joué", "removed": "retiré"]
        let time = Date(timeIntervalSince1970: request.addedAt).formatted(date: .omitted, time: .shortened)
        return HStack(spacing: 10) {
            HostArtwork(path: request.image, load: store.artwork, size: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(request.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text(request.artist).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                Text("\(request.guestName) · \(time) · \(labels[request.status] ?? "")")
                    .font(.caption2.weight(.semibold)).foregroundStyle(request.status == "queued" ? Palette.accent : .secondary)
            }
            Spacer()
            if request.status == "queued" && !state.usesSpotify {
                Button(role: .destructive) { Task { await store.removeRequest(request) } } label: { Image(systemName: "xmark") }
                    .buttonStyle(.bordered).disabled(store.busy.contains("r.\(request.id)"))
                    .accessibilityLabel("Retirer de la file")
            }
        }
        .opacity(request.status == "queued" ? 1 : 0.55)
        .card(request.status == "queued" ? Palette.mine.opacity(0.55) : Palette.card)
    }
}
