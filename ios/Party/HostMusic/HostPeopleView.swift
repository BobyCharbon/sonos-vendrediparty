import SwiftUI

extension HostMusicStore {
    func messages(_ action: String, ids: [String]?) async {
        await run(ids?.first.map { "m.\($0)" } ?? "m.all") { apply(try await api.adminMessages(action, ids: ids)) }
    }

    func reply(_ message: HostPeople.Message, _ text: String) async -> Bool {
        var done = false
        await run("m.\(message.id)") {
            apply(try await api.adminReply(id: message.id, text: text))
            notice = Notice(text: "Réponse envoyée ↩︎")
            done = true
        }
        return done
    }

    func unban(_ ban: HostPeople.Ban) async {
        await run("g.\(ban.guestID)") {
            apply(try await api.adminGuest("unban", guestID: ban.guestID).state)
            notice = Notice(text: "\(ban.name) débloqué")
        }
    }

    func closeGame(_ game: HostPeople.Game) async {
        await run("game.\(game.code)") {
            apply(try await api.adminCloseGame(code: game.code))
            notice = Notice(text: "Partie \(game.code) fermée")
        }
    }
}

/// Réglages › Invités et messages (hôte) : messages des invités (lire, répondre, supprimer), invités présents,
/// bloqués / bannis des soirées précédentes, journal de la soirée.
struct HostPeopleView: View {
    @ObservedObject var store: HostMusicStore
    @State private var drafts: [String: String] = [:]
    @State private var deleting: HostPeople.Message?

    var body: some View {
        List {
            if let state = store.state {
                messages(state.people)
                guests(state)
                let others = state.people.otherBans(listed: state.guests, active: state.active)
                if !others.isEmpty { bans(others) }
                Section {
                    NavigationLink { PartyJournalView(api: store.api) } label: {
                        SettingsRow(symbol: "list.bullet.rectangle.portrait.fill", tint: .gray, title: "Journal de la soirée",
                                    hint: "Qui a fait quoi dans l'admin. Rien n'y est modifiable.")
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Invités et messages")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { HostLoading(store: store) }
        .overlay(alignment: .bottom) { HostNoticeBanner(store: store) }
        .refreshable { await store.reload() }
        .task { store.start() }
        .confirmationDialog("Supprimer ce message ?", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }),
                            titleVisibility: .visible) {
            Button("Supprimer", role: .destructive) {
                guard let message = deleting else { return }
                Task { await store.messages("delete", ids: [message.id]) }
            }
        }
    }

    private func messages(_ people: HostPeople) -> some View {
        Section {
            if people.messages.isEmpty { Text("Aucun message").foregroundStyle(.secondary) }
            ForEach(people.messages) { message in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline) {
                        if !message.read { Circle().fill(Palette.accent).frame(width: 8, height: 8).accessibilityLabel("Non lu") }
                        Text(message.name).font(.subheadline.weight(.semibold))
                        Text("· \(time(message.at))").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Button { Task { await store.messages(message.read ? "unread" : "read", ids: [message.id]) } } label: {
                            Image(systemName: message.read ? "envelope.badge" : "checkmark.circle")
                        }
                        .buttonStyle(.borderless)
                        .accessibilityLabel(message.read ? "Marquer non lu" : "Marquer lu")
                        Button(role: .destructive) { deleting = message } label: { Image(systemName: "trash") }
                            .buttonStyle(.borderless)
                            .accessibilityLabel("Supprimer le message")
                    }
                    Text(message.text)
                    if let reply = message.reply {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("↩︎ Ta réponse · \(time(message.replyAt ?? 0))").font(.caption).foregroundStyle(.secondary)
                            Text(reply).font(.subheadline)
                        }
                        .padding(8)
                        .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
                    }
                    HStack {
                        TextField(message.reply == nil ? "Répondre…" : "Modifier ta réponse…",
                                  text: Binding(get: { drafts[message.id] ?? "" }, set: { drafts[message.id] = String($0.prefix(300)) }))
                            .textFieldStyle(.roundedBorder)
                            .submitLabel(.send)
                            .onSubmit { send(message) }
                            .accessibilityLabel("Répondre à \(message.name)")
                        Button("Envoyer") { send(message) }
                            .buttonStyle(.borderless)
                            .disabled((drafts[message.id] ?? "").trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
                .padding(.vertical, 4)
                .disabled(store.busy.contains("m.\(message.id)"))
            }
            if people.unread > 0 {
                Button("Tout marquer comme lu") { Task { await store.messages("read", ids: nil) } }
                    .disabled(store.busy.contains("m.all"))
            }
        } header: {
            Text("Messages des invités" + (people.unread > 0 ? " · \(people.unread) non lu\(people.unread > 1 ? "s" : "")" : ""))
        }
    }

    private func guests(_ state: AdminState) -> some View {
        Section {
            if state.guests.isEmpty { Text("Aucun invité pour l'instant").foregroundStyle(.secondary) }
            ForEach(state.guests) { guest in
                GuestRow(store: store, guest: guest, usesSpotify: state.usesSpotify)
                    .listRowInsets(EdgeInsets(top: 4, leading: 8, bottom: 4, trailing: 8))
            }
        } header: {
            Text("Invités · \(state.onlineGuests.count) en ligne")
        } footer: {
            Text("Touche ⋯ pour renommer, déconnecter, bloquer 10 minutes, bannir ou retirer ses titres.")
        }
    }

    private func bans(_ bans: [HostPeople.Ban]) -> some View {
        Section("Bloqués / bannis") {
            ForEach(bans) { ban in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(ban.name).font(.subheadline.weight(.semibold))
                        Text(ban.label).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Débloquer") { Task { await store.unban(ban) } }
                        .buttonStyle(.bordered).controlSize(.small)
                        .disabled(store.busy.contains("g.\(ban.guestID)"))
                }
            }
        }
    }

    private func send(_ message: HostPeople.Message) {
        let text = (drafts[message.id] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        Task { if await store.reply(message, text) { drafts[message.id] = nil } }
    }

    private func time(_ at: Double) -> String {
        Date(timeIntervalSince1970: at).formatted(date: .omitted, time: .shortened)
    }
}

/// Réglages › Admin de la soirée (hôte) : état, code et QR, jeux en cours, arrêt ; la musique a son propre écran.
struct PartyAdminView: View {
    @ObservedObject var store: HostMusicStore
    let openMusic: () -> Void
    let openWebAdmin: () -> Void
    @State private var confirmStop = false
    @State private var closing: HostPeople.Game?

    var body: some View {
        List {
            if let state = store.state {
                Section {
                    LabeledContent("Soirée", value: state.active ? "En cours" : "Arrêtée")
                    if state.active {
                        if !state.placeLabel.isEmpty { LabeledContent("Lieu", value: state.placeLabel) }
                        LabeledContent("Invités en ligne", value: "\(state.onlineGuests.count)")
                        if let event = state.event { LabeledContent("Événement", value: event.title) }
                    }
                    Button(action: openMusic) {
                        SettingsRow(symbol: "music.note.list", tint: .pink, title: state.active ? "Gérer la musique" : "Lancer la soirée",
                                    hint: "File d'attente, ajout, mode, enceintes, playlists, Spotify")
                    }
                    .foregroundStyle(.primary)
                }
                if state.active {
                    Section {
                        LabeledContent("Code de la soirée", value: state.guestPin)
                        QRCodeView(text: state.guestURL)
                            .frame(maxWidth: 220)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                        Button("Nouveau code au hasard") { Task { await store.newPin() } }
                            .disabled(store.busy.contains("pin"))
                    } header: {
                        Text("Accès invités")
                    } footer: {
                        Text("Un nouveau code déconnecte tous les invités : ils devront saisir le nouveau ou rescanner le QR.")
                    }
                }
                games(state.people.games)
                if state.active {
                    Section {
                        Button("Arrêter la soirée", role: .destructive) { confirmStop = true }
                            .disabled(store.busy.contains("stop"))
                    }
                }
                Section {
                    Button("Ouvrir l'admin du site (secours)", action: openWebAdmin)
                } footer: {
                    Text("Tout se fait ici et dans Musique ; la page d'admin du site reste disponible au besoin.")
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Admin de la soirée")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { HostLoading(store: store) }
        .overlay(alignment: .bottom) { HostNoticeBanner(store: store) }
        .refreshable { await store.reload() }
        .task { store.start() }
        .confirmationDialog("Arrêter la soirée ?", isPresented: $confirmStop, titleVisibility: .visible) {
            Button("Arrêter la soirée", role: .destructive) { Task { await store.stopParty() } }
        } message: {
            Text("La musique s'arrête et les invités ne peuvent plus ajouter de titres.")
        }
        .confirmationDialog("Fermer la partie \(closing?.code ?? "") pour tous ses joueurs ?",
                            isPresented: Binding(get: { closing != nil }, set: { if !$0 { closing = nil } }), titleVisibility: .visible) {
            Button("Fermer la partie", role: .destructive) {
                guard let game = closing else { return }
                Task { await store.closeGame(game) }
            }
        }
    }

    @ViewBuilder
    private func games(_ games: [HostPeople.Game]) -> some View {
        Section {
            if games.isEmpty { Text("Aucune partie en cours").foregroundStyle(.secondary) }
            ForEach(games) { game in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(game.name).font(.subheadline.weight(.semibold))
                        Text(game.summary).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                    Spacer()
                    Button("Fermer", role: .destructive) { closing = game }
                        .buttonStyle(.bordered).controlSize(.small)
                        .disabled(store.busy.contains("game.\(game.code)"))
                }
            }
        } header: {
            Text("Jeux en cours · \(games.count)")
        }
    }
}

/// Journal de la soirée (lecture seule), 50 lignes par page.
struct PartyJournalView: View {
    let api: PartyAPI
    @State private var entries: [PartyJournal.Entry] = []
    @State private var more = false
    @State private var loaded = false
    @State private var error: String?

    private static let page = 50

    var body: some View {
        List {
            Section {
                if loaded && entries.isEmpty && error == nil { Text("Rien dans le journal pour l'instant").foregroundStyle(.secondary) }
                if let error { Text(error).foregroundStyle(.secondary) }
                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.text)
                        Text(entry.when + (entry.ip.map { " · \($0)" } ?? "")).font(.footnote).foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .combine)
                }
                if more { Button("Plus ancien") { Task { await load(before: entries.last?.id) } } }
            } footer: {
                Text("Connexions admin, refus, invités renommés, déconnectés, bloqués, bannis, parties fermées.")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Journal de la soirée")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if !loaded { ProgressView() } }
        .refreshable { await load(before: nil) }
        .task { if !loaded { await load(before: nil) } }
    }

    private func load(before: String?) async {
        do {
            let page = try await api.adminJournal(before: before, limit: Self.page)
            entries = before == nil ? page.entries : entries + page.entries
            more = page.entries.count == Self.page
            error = nil
        } catch {
            self.error = "Journal indisponible : \(HostMusicStore.message(error))"
        }
        loaded = true
    }
}

/// Premier chargement de l'état d'hôte : roue, ou l'erreur avec « Réessayer ».
private struct HostLoading: View {
    @ObservedObject var store: HostMusicStore

    var body: some View {
        if store.state == nil {
            if case .failed(let message) = store.phase {
                VStack(spacing: 12) {
                    Text(message).multilineTextAlignment(.center).foregroundStyle(.secondary)
                    Button("Réessayer") { Task { await store.reload() } }
                }
                .padding()
            } else {
                ProgressView()
            }
        }
    }
}

/// Bandeau de l'hôte (confirmation ou refus), effacé au bout de 3 s.
private struct HostNoticeBanner: View {
    @ObservedObject var store: HostMusicStore

    var body: some View {
        if let notice = store.notice {
            Text(notice.text)
                .font(.subheadline.weight(.semibold))
                .multilineTextAlignment(.center)
                .foregroundStyle(notice.isError ? .red : .primary)
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(Palette.card, in: Capsule())
                .padding(.bottom, 12).padding(.horizontal, 16)
                .task(id: notice.text) {
                    try? await Task.sleep(for: .seconds(3))
                    if store.notice == notice { store.notice = nil }
                }
        }
    }
}
