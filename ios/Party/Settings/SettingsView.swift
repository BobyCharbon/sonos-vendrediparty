import SwiftUI

/// Onglet Réglages natif, à la manière des Réglages de l'iPhone : le compte en tête, puis Notifications.
/// Tout est natif ; seuls les écrans d'un événement (voir, modifier) s'ouvrent dans le module Événements.
struct SettingsView: View {
    @ObservedObject var store: SettingsStore
    let topInset: CGFloat
    let isHost: Bool
    var hostMusic: HostMusicStore?
    /// « Ton avis » / « Retours » (page, native-tabs.js) : libellé et pastille des avis à traiter ou des réponses.
    var feedbackEntry: TabBarState.FeedbackEntry?
    let open: (WebModel.PagePlace) -> Void
    @State private var confirmSignOut = false
    @State private var joinLink: JoinLink?

    var body: some View {
        NavigationStack {
            List {
                accountSection
                if store.account != nil {
                    MoonBanner(store: store.pause)
                }
                Section {
                    NavigationLink {
                        NotificationSettingsView(store: store)
                    } label: {
                        SettingsRow(symbol: "bell.badge.fill", tint: .red, title: "Notifications",
                                    hint: "Musique, jeux, avis et événements ; catégories et tags suivis")
                    }
                    if store.account != nil {
                        NavigationLink {
                            TricountListView(store: store.tricount, myName: store.account?.name ?? "")
                        } label: {
                            SettingsRow(symbol: "banknote.fill", tint: .green, title: "Pot commun",
                                        hint: "Dépenses partagées : qui a payé, qui doit quoi, remboursements")
                        }
                        .accessibilityIdentifier("settings-tricount")
                        NavigationLink {
                            GroupsView(store: store.groups, privacy: store.privacy)
                        } label: {
                            SettingsRow(symbol: "person.3.fill", tint: .blue, title: "Groupes",
                                        hint: "Les groupes dont tu fais partie ; crée les tiens")
                        }
                        NavigationLink {
                            FriendsView(store: store.friends, privacy: store.privacy)
                        } label: {
                            SettingsRow(symbol: "person.2.circle.fill", tint: .pink, title: "Mes amis dans Party",
                                        hint: "Tes contacts inscrits sur Party ; invite les autres")
                        }
                        .accessibilityIdentifier("settings-friends")
                    }
                }
                if isHost || store.account?.admin == true || store.account?.groupAdmin == true {
                    Section("Administration") {
                        if isHost || store.account?.admin == true {
                            if let hostMusic {
                                NavigationLink { HostPeopleView(store: hostMusic) } label: {
                                    SettingsRow(symbol: "person.2.fill", tint: .blue, title: "Invités et messages",
                                                hint: "Messages des invités, invités, bannis, journal")
                                }
                                NavigationLink {
                                    PartyAdminView(store: hostMusic, openMusic: { open(.tab("music")) }, openWebAdmin: { open(.admin) })
                                } label: {
                                    SettingsRow(symbol: "slider.horizontal.3", tint: .gray, title: "Admin de la soirée",
                                                hint: "État, code et QR, jeux en cours, arrêt ; la musique dans Musique")
                                }
                            }
                        }
                        if store.account?.admin == true {
                            NavigationLink { AIUsageView(store: store.tricount) } label: {
                                SettingsRow(symbol: "sparkles", tint: .purple, title: "Assistant IA",
                                            hint: "Qui l'utilise et ce que ça coûte ce mois-ci")
                            }
                        }
                        if store.account?.groupAdmin == true {
                            NavigationLink {
                                GroupAdminView(store: store.groupAdmin, session: store.session, open: open)
                            } label: {
                                SettingsRow(symbol: "shield.lefthalf.filled", tint: .indigo, title: "Administration du groupe",
                                            hint: "Propositions, demandes, membres, rôles et droits, journal")
                            }
                        }
                    }
                }
                Section {
                    if store.account != nil {
                        NavigationLink {
                            GameStatsView(store: store.session) { open(.tab("games")) }
                        } label: {
                            SettingsRow(symbol: "trophy.fill", tint: .orange, title: "Mes stats de jeu",
                                        hint: "Purify Test et Méninges : scores, profil, records")
                        }
                    }
                    // « Ton avis » : l'hôte (« Retours »), et les comptes Guest+ et au-dessus (droit « Écrire un avis »).
                    // Sorti de la barre d'onglets le 4.11 (onglet Zicou) : sa pastille est reportée ici.
                    if Self.showsFeedback(isHost: isHost, account: store.account?.feedback == true, entry: feedbackEntry) {
                        page(.tab("feedback"), "bubble.left.and.bubble.right.fill", .green, Self.feedbackTitle(isHost: isHost, entry: feedbackEntry),
                             isHost ? "Les idées et bugs des invités ; ton avis aussi" : "Une idée, un bug ? Écris à l'organisateur",
                             badge: feedbackEntry?.badge)
                        .accessibilityIdentifier("settings-feedback")
                    }
                }
                Section {
                    NavigationLink { PrivacyView(moderation: store.account != nil ? store.moderation : nil) } label: {
                        SettingsRow(symbol: "lock.fill", tint: .blue, title: "Confidentialité",
                                    hint: store.account != nil ? "Personnes bloquées, conditions d'utilisation, tes données" : "Tes données et tes choix")
                    }
                    if store.account != nil {
                        NavigationLink {
                            DeleteAccountView(store: store.session, isAdmin: store.account?.admin == true)
                        } label: {
                            SettingsRow(symbol: "gearshape.fill", tint: .gray, title: "Gérer mon compte", hint: "Suppression du compte")
                        }
                        Button { confirmSignOut = true } label: {
                            SettingsRow(symbol: "rectangle.portrait.and.arrow.right", tint: .red, title: "Se déconnecter",
                                        hint: "Cet iPhone oublie ton compte ; tu restes invité de la soirée")
                        }
                        .foregroundStyle(.primary)
                        .disabled(store.session.busy)
                    }
                }
                Section {
                } footer: {
                    Text("Party ! \(Self.version)").frame(maxWidth: .infinity)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            // Connexion, déconnexion, droits relus : les sections apparaissent ou s'en vont en glissant,
            // au lieu de surgir d'un coup quand le compte arrive après l'affichage.
            .motion(Motion.smooth, value: store.account != nil)
            .motion(Motion.smooth, value: store.account?.admin)
            .motion(Motion.smooth, value: store.account?.groupAdmin)
            .motion(Motion.smooth, value: store.account?.feedback)
            .background(AppConfig.background)
            .navigationTitle("Réglages")
            // Lien d'invitation dans Party ouvert dans l'app (/events/join/<lien>) : « X t'invite sur Party ».
            // Gardé jusqu'à la connexion : la feuille revient alors et le lien est réclamé.
            .sheet(item: $joinLink) { link in
                JoinInviteSheet(store: store.friends, invite: link.id, signedIn: store.account != nil)
                    .presentationDetents([.medium])
            }
            .onReceive(store.friends.$pendingInvite.dropFirst()) { invite in
                if let invite { joinLink = JoinLink(id: invite) }
            }
            .onChange(of: store.account != nil) { signedIn in
                if signedIn, let invite = store.friends.pendingInvite { joinLink = JoinLink(id: invite) }
            }
            // Lune en haut à droite (avis de l'admin) : pause de tout, sauf les notifications admin.
            .toolbar {
                if store.account != nil {
                    ToolbarItem(placement: .navigationBarTrailing) { MoonMenu(store: store.pause) }
                }
            }
        }
        .tint(Palette.accent)
        .padding(.top, topInset)
        .background(AppConfig.background.ignoresSafeArea())
        .task {
            await store.refreshAccount()
            await store.pause.load()
        }
        .confirmationDialog("Se déconnecter de ce compte ?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("Se déconnecter", role: .destructive) { Task { await store.session.signOut() } }
        } message: {
            Text("Tu pourras te reconnecter avec ton numéro. Les notifications des événements s'arrêtent sur cet iPhone.")
        }
        .overlay(alignment: .bottom) { SessionNotice(store: store.session) }
        // Lien d'un pot commun ouvert (lien universel) : « Rejoindre » s'affiche par-dessus les Réglages.
        .sheet(item: Binding(get: { store.tricount.pendingJoin.map(TricountLink.init) }, set: { store.tricount.pendingJoin = $0?.id })) { link in
            JoinTricountView(store: store.tricount, link: link.id, myName: store.account?.name ?? "") { _ in }
        }
    }

    @ViewBuilder
    private var accountSection: some View {
        Section {
            if let account = store.account {
                NavigationLink { ProfileView(store: store) } label: {
                    HStack(spacing: 14) {
                        Avatar(photo: account.photo, name: account.name)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(account.name.isEmpty ? "Profil à compléter" : account.name).font(.title3.weight(.semibold))
                            Text("Mon profil : surnom, photo, prénom et nom").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .accessibilityLabel("Mon profil : \(account.name)")
            } else {
                NavigationLink { SignInView(store: store.session) } label: {
                    HStack(spacing: 14) {
                        Avatar(photo: nil, name: "")
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Se connecter").font(.title3.weight(.semibold))
                            Text("Avec ton numéro : événements, jeux à compte et tes stats sur tous tes appareils")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    static func showsFeedback(isHost: Bool, account: Bool, entry: TabBarState.FeedbackEntry?) -> Bool {
        isHost || account || entry?.allowed == true
    }

    static func feedbackTitle(isHost: Bool, entry: TabBarState.FeedbackEntry?) -> String {
        entry?.label ?? (isHost ? "Retours" : "Ton avis")
    }

    private func page(_ place: WebModel.PagePlace, _ symbol: String, _ tint: Color, _ title: String, _ hint: String,
                      badge: String? = nil) -> some View {
        Button { open(place) } label: {
            HStack {
                SettingsRow(symbol: symbol, tint: tint, title: title, hint: hint)
                Spacer(minLength: 0)
                if let badge {
                    Text(badge)
                        .font(.footnote.weight(.semibold)).foregroundStyle(.white)
                        .padding(.horizontal, 7).frame(minWidth: 22, minHeight: 22)
                        .background(Color.red, in: Capsule())
                        .accessibilityLabel("\(badge) à voir")
                }
                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
            }
        }
        .foregroundStyle(.primary)
    }

    private static var version: String {
        let info = Bundle.main.infoDictionary
        return "\(info?["CFBundleShortVersionString"] as? String ?? "") (\(info?["CFBundleVersion"] as? String ?? ""))"
    }
}

/// Ligne des Réglages : pastille colorée avec symbole, titre et explication courte.
struct SettingsRow: View {
    let symbol: String
    let tint: Color
    let title: String
    var hint: String?

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 29, height: 29)
                .background(tint, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                if let hint { Text(hint).font(.footnote).foregroundStyle(.secondary) }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

private struct Avatar: View {
    let photo: String?
    let name: String

    var body: some View {
        // Photo du compte téléchargée : fondu depuis l'initiale.
        AsyncImage(url: photo.flatMap(URL.init(string:)), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(name.first.map(String.init) ?? "")
                    .font(.title2.weight(.bold))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .overlay { if name.isEmpty { Image(systemName: "person.fill").font(.title2) } }
            }
        }

        .frame(width: 58, height: 58)
        .background(Palette.accent.opacity(0.35))
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}

/// Bandeau « Tu es déconnecté »… (le compte est suivi par son propre store).
private struct SessionNotice: View {
    @ObservedObject var store: AccountStore

    var body: some View { AdminNotice(notice: $store.notice) }
}

private struct TricountLink: Identifiable { let id: String }
private struct JoinLink: Identifiable { let id: String }
