import SwiftUI

/// Onglet Musique natif (invités) : rejoindre, titre en cours, recherche, file, messages à l'hôte.
/// Même contenu et mêmes règles que la page web (app/static/index.html, section data-view="music").
struct MusicView: View {
    @ObservedObject var store: MusicStore
    let topInset: CGFloat
    /// Hôte seulement : rouvre l'onglet Musique de la page, avec ses réglages.
    var manage: (() -> Void)?

    @State private var name = ""
    @State private var message = ""
    @State private var scanning = false

    var body: some View {
        ScrollView {
            // Liste paresseuse : seules les pochettes visibles sont demandées (comme loading="lazy" sur le site) ;
            // le serveur va chercher chaque pochette Sonos sur l'enceinte, 70 d'un coup la saturent.
            LazyVStack(alignment: .leading, spacing: 16) {
                header
                content
            }
            .padding(.horizontal, 16)
            .padding(.top, topInset + 8)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await store.reload() }
        .background(AppConfig.background.ignoresSafeArea())
        .overlay(alignment: .bottom) { noticeBanner }
        .alert("Ton prénom", isPresented: $store.asksName) {
            TextField("Prénom", text: $name).textInputAutocapitalization(.words)
            Button("Annuler", role: .cancel) {}
            Button("Ajouter") { Task { await store.confirm(name: name) } }
        } message: {
            Text("Il s'affiche à côté de tes titres dans la file.")
        }
        .sheet(isPresented: $scanning) {
            QRScannerSheet { text in Task { await store.handleScanned(text) } }
        }
        // Le suivi en direct tourne tant que l'app est ouverte (PartyApp, scenePhase) : on rafraîchit à l'affichage.
        .task { await store.reload() }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Musique").font(.largeTitle.weight(.heavy))
                if case .ready(let state) = store.phase, let room = state.room, !room.isEmpty {
                    Text(room).font(.subheadline).foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button { scanning = true } label: {
                Image(systemName: "qrcode.viewfinder").font(.title2)
            }
            .tint(Palette.accent)
            .accessibilityLabel("Scanner le QR de l'hôte (soirée ou partie)")
            if let manage {
                Button(action: manage) {
                    Label("Gérer la soirée", systemImage: "slider.horizontal.3")
                }
                .buttonStyle(.bordered)
                .tint(Palette.accent)
                .accessibilityHint("Ouvre les réglages de l'hôte ; touche à nouveau l'onglet Musique pour revenir")
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch store.phase {
        case .loading:
            ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
        case .needsCode:
            JoinCard(scan: { scanning = true }) { code in await store.join(code: code) }
        case .closed:
            InfoCard(symbol: "moon.zzz", text: "Pas de soirée en cours pour le moment.")
        case .offline(let reason):
            InfoCard(symbol: "wifi.exclamationmark", text: reason)
            Button("Réessayer") { Task { await store.reload() } }.buttonStyle(.borderedProminent).tint(Palette.accent)
        case .ready(let state):
            party(state)
        }
    }

    @ViewBuilder
    private func party(_ state: PartyState) -> some View {
        if let blocked = state.blocked { Warning(text: blocked) }
        if let error = state.error { Warning(text: error) }
        if let now = state.now, !now.isEmpty { NowPlayingCard(now: now, store: store) }
        Toggle(isOn: Binding(get: { store.notifyWhenPlaying },
                             set: { on in Task { await store.setNotifyWhenPlaying(on) } })) {
            Label("Me prévenir quand mon titre passe", systemImage: "bell")
        }
        .tint(Palette.accent)
        .card()
        if state.blocked == nil { search }
        upcoming(state)
        messages(state)
        if !state.played.isEmpty { played(state) }
    }

    // MARK: Recherche

    private var search: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                TextField("Titre, artiste ou lien", text: $store.query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                if store.searching { ProgressView() }
                if !store.query.isEmpty {
                    Button { store.query = "" } label: { Image(systemName: "xmark.circle.fill") }
                        .foregroundStyle(.secondary)
                        .accessibilityLabel("Effacer la recherche")
                }
            }
            .card()
            ForEach(store.results) { track in
                TrackRow(title: track.title, subtitle: track.artist, art: track.image, store: store) {
                    Button { Task { await store.add(track) } } label: {
                        if store.busyTrack == track.id { ProgressView() } else { Image(systemName: "plus.circle.fill").font(.title2) }
                    }
                    .tint(Palette.accent)
                    .disabled(store.busyTrack != nil)
                    .accessibilityLabel("Ajouter « \(track.title) »")
                }
            }
        }
    }

    // MARK: File d'attente

    @ViewBuilder
    private func upcoming(_ state: PartyState) -> some View {
        SectionTitle(text: state.upcomingTotal > 0 ? "À venir · \(state.upcomingTotal)" : "À venir")
        if state.upcoming.isEmpty {
            Text("La file est vide : ajoute le premier titre !").foregroundStyle(.secondary)
        }
        ForEach(state.upcoming) { item in
            let when = PassageTime.text(eta: item.eta, receivedAt: store.receivedAt)
            let who = item.by.map { "par \($0)" }
            TrackRow(title: item.title, subtitle: [item.artist, who, when].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "),
                     art: item.art, highlighted: item.isMine, store: store) {
                if item.isMine && state.queueEditable {
                    Button(role: .destructive) { Task { await store.remove(item) } } label: {
                        Image(systemName: "minus.circle.fill").font(.title2)
                    }
                    .accessibilityLabel("Retirer « \(item.title) » de la file")
                }
            }
        }
    }

    // MARK: Messages à l'hôte

    @ViewBuilder
    private func messages(_ state: PartyState) -> some View {
        SectionTitle(text: "Un mot à l'hôte")
        ForEach(state.messages) { item in
            VStack(alignment: .leading, spacing: 6) {
                Text(item.text)
                if let reply = item.reply, !reply.isEmpty {
                    Label(reply, systemImage: "arrowshape.turn.up.left.fill").foregroundStyle(Palette.accent)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .card()
        }
        HStack {
            TextField("Ton message", text: $message, axis: .vertical).lineLimit(1...4)
            Button("Envoyer") {
                Task { if await store.send(message: message) { message = "" } }
            }
            .buttonStyle(.borderedProminent)
            .tint(Palette.accent)
            .disabled(message.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .card()
    }

    private func played(_ state: PartyState) -> some View {
        DisclosureGroup("Déjà passés · \(state.played.count)") {
            ForEach(state.played) { item in
                TrackRow(title: item.title, subtitle: item.artist, art: item.art, store: store) { EmptyView() }
            }
        }
        .tint(.secondary)
        .card()
    }

    @ViewBuilder
    private var noticeBanner: some View {
        if let notice = store.notice {
            Text(notice.text)
                .font(.subheadline.weight(.semibold))
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(notice.isError ? Color.red.opacity(0.9) : Palette.card, in: Capsule())
                .padding(.bottom, 12)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .task(id: notice) {
                    try? await Task.sleep(for: .seconds(3))
                    withAnimation { store.notice = nil }
                }
        }
    }
}

// MARK: - Éléments

enum Palette {
    static let accent = Color(uiColor: AppConfig.uiAccent)
    static let card = Color(red: 0.11, green: 0.085, blue: 0.17)
    static let mine = Color(red: 0.22, green: 0.09, blue: 0.2)
}

private struct CardStyle: ViewModifier {
    var fill: Color = Palette.card
    func body(content: Content) -> some View {
        content.padding(12).background(fill, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

extension View {
    func card(_ fill: Color = Palette.card) -> some View { modifier(CardStyle(fill: fill)) }
}

private struct SectionTitle: View {
    let text: String
    var body: some View { Text(text).font(.title3.weight(.bold)).padding(.top, 4) }
}

private struct Warning: View {
    let text: String
    var body: some View {
        Label(text, systemImage: "exclamationmark.triangle.fill")
            .foregroundStyle(.orange)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card()
    }
}

private struct InfoCard: View {
    let symbol: String
    let text: String
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: symbol).font(.largeTitle).foregroundStyle(.secondary)
            Text(text).multilineTextAlignment(.center).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
        .card()
    }
}

private struct JoinCard: View {
    let scan: () -> Void
    let join: (String) async -> Void
    @State private var code = ""
    @State private var joining = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Scanne le QR de l'hôte ou entre le code de la soirée pour rejoindre la file d'attente.")
                .foregroundStyle(.secondary)
            HStack {
                TextField("Code", text: $code)
                    .keyboardType(.numberPad)
                    .font(.title2.monospacedDigit())
                    .textContentType(.oneTimeCode)
                Button {
                    joining = true
                    Task { await join(code); joining = false }
                } label: {
                    if joining { ProgressView() } else { Text("Entrer").bold() }
                }
                .buttonStyle(.borderedProminent)
                .tint(Palette.accent)
                .disabled(code.isEmpty || joining)
            }
            Button(action: scan) {
                Label("Scanner le QR de l'hôte", systemImage: "qrcode.viewfinder").frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .tint(Palette.accent)
        }
        .card()
    }
}

private struct NowPlayingCard: View {
    let now: NowPlaying
    let store: MusicStore

    var body: some View {
        HStack(spacing: 14) {
            Artwork(path: now.art, size: 88, store: store)
            VStack(alignment: .leading, spacing: 4) {
                Text("EN CE MOMENT").font(.caption.weight(.bold)).foregroundStyle(Palette.accent)
                Text(now.title).font(.headline).lineLimit(2)
                Text(now.artist).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                if let by = now.by { Text("demandé par \(by)").font(.caption).foregroundStyle(.secondary) }
            }
            Spacer(minLength: 0)
        }
        .card()
    }
}

private struct TrackRow<Trailing: View>: View {
    let title: String
    let subtitle: String
    let art: String
    var highlighted = false
    let store: MusicStore
    @ViewBuilder let trailing: () -> Trailing

    var body: some View {
        HStack(spacing: 12) {
            Artwork(path: art, size: 48, store: store)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body.weight(.semibold)).lineLimit(1)
                Text(subtitle).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer(minLength: 0)
            trailing()
        }
        .card(highlighted ? Palette.mine : Palette.card)
    }
}

/// Pochette : chargée avec la session de l'invité (les pochettes Sonos sont réservées aux invités).
private struct Artwork: View {
    let path: String
    let size: CGFloat
    let store: MusicStore
    @State private var image: UIImage?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(0.06))
            if let image {
                Image(uiImage: image).resizable().scaledToFill()
            } else {
                Image(systemName: "music.note").foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .task(id: path) { image = await store.artwork(path) }
    }
}
