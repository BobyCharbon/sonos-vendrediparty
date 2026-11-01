import SwiftUI

/// Onglet « Discussions » natif (avis n°10) : une discussion par groupe, la plus récente en haut, comme WhatsApp.
struct ChatsView: View {
    @ObservedObject var store: ChatsStore
    let topInset: CGFloat

    @State private var path: [String] = []

    var body: some View {
        NavigationStack(path: $path) {
            list
                .motion(Motion.smooth, value: listPhase)
                .navigationTitle("Discussions")
                .background(AppConfig.background.ignoresSafeArea())
                .toolbarBackground(AppConfig.background, for: .navigationBar)
                .navigationDestination(for: String.self) { group in
                    ConversationView(store: store, group: group)
                }
        }
        .tint(Color(uiColor: AppConfig.uiAccent))
        .padding(.top, topInset)
        .background(AppConfig.background.ignoresSafeArea())
        .task(id: path.isEmpty) {
            // Liste visible : relue au retour d'une conversation, puis toutes les 15 s.
            guard path.isEmpty else { return store.stopListLive() }
            await store.loadList()
            openRequested()
            await store.startListLive()  // nouveaux messages : la liste se met à jour en direct
            while !Task.isCancelled {
                try? await Task.sleep(for: ChatsStore.listEvery)
                guard !Task.isCancelled else { break }
                await store.loadList()
            }
        }
        .onDisappear { store.stopListLive() }
        .onChange(of: store.requested) { _ in openRequested() }
    }

    private func openRequested() {
        guard let group = store.requested else { return }
        store.requested = nil
        path = [group]
    }

    @ViewBuilder private var list: some View {
        if let chats = store.chats {
            List(chats) { chat in
                NavigationLink(value: chat.id) { ChatRow(chat: chat) }
                    .listRowBackground(AppConfig.background)
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            // Nouveau message dans un groupe : sa discussion remonte en tête en glissant, sans saut.
            .motion(Motion.snappy, value: chats.map(\.id))
            .overlay {
                if chats.isEmpty {
                    ContentUnavailable(text: "Rejoins ou crée un groupe (Réglages › Groupes) pour discuter avec ses membres.")
                        .transition(.opacity)
                }
            }
            .refreshable { await store.loadList() }
            .transition(.opacity)
        } else if let error = store.error {
            ContentUnavailable(text: error).transition(.opacity)
        } else {
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity).transition(.opacity)
        }
    }

    /// Chargement → liste ou erreur : fondu (une relecture de la liste ne rejoue rien).
    private var listPhase: Int { store.chats != nil ? 2 : store.error != nil ? 1 : 0 }
}

private struct ContentUnavailable: View {
    let text: String
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right").font(.largeTitle).foregroundStyle(.secondary)
            Text(text).multilineTextAlignment(.center).foregroundStyle(.secondary)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct ChatRow: View {
    let chat: ChatSummary

    var body: some View {
        HStack(spacing: 12) {
            Initials(name: chat.name, size: 48)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(chat.name).font(.body.weight(.semibold)).lineLimit(1)
                    Spacer()
                    Text(ChatDates.short(chat.lastAt)).font(.caption)
                        .foregroundStyle(chat.unread > 0 ? Color(uiColor: AppConfig.uiAccent) : .secondary)
                }
                HStack {
                    Text(chat.last ?? "Aucun message pour l'instant").font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    if chat.notify == .none { Image(systemName: "bell.slash").font(.caption).foregroundStyle(.secondary) }
                    if chat.unread > 0 {
                        Text(chat.unread > 99 ? "99+" : "\(chat.unread)")
                            .font(.caption2.weight(.bold)).foregroundStyle(.black)
                            .contentTransition(.numericText())
                            .padding(.horizontal, 6).frame(minWidth: 22, minHeight: 22)
                            .background(Color(uiColor: AppConfig.uiAccent), in: Capsule())
                            .motionTransition(.scale(scale: 0.4).combined(with: .opacity))
                    }
                }
            }
        }
        .padding(.vertical, 4)
        // Pastille de non-lus qui arrive, compte qui change, dernier message : petit rebond, chiffres qui défilent.
        .motion(Motion.bouncy, value: chat.unread)
        .motion(Motion.smooth, value: chat.last)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(chat.name)\(chat.unread > 0 ? ", \(chat.unread) non lus" : "")")
    }
}

/// Pastille ronde aux initiales (ou photo) : groupes et auteurs des messages.
struct Initials: View {
    let name: String
    var photo: String?
    var size: CGFloat = 32

    private var letters: String {
        name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
    }

    /// Teinte stable d'un lancement à l'autre (hashValue change à chaque lancement : la pastille changeait de couleur).
    private var hue: Double {
        let sum = name.unicodeScalars.reduce(UInt32(5381)) { ($0 &* 33) &+ $1.value }
        return Double(sum % 360) / 360
    }

    var body: some View {
        // Photo téléchargée : fondu depuis les initiales, plus d'apparition sèche.
        AsyncImage(url: photo.flatMap(URL.init(string:)), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(letters.isEmpty ? "?" : letters).font(.system(size: size * 0.36, weight: .bold)).foregroundStyle(.black)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(hue: hue, saturation: 0.45, brightness: 0.95))
            }
        }

        .frame(width: size, height: size)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}
