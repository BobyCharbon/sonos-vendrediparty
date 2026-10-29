import SwiftUI

/// Onglet Réglages natif, à la manière des Réglages de l'iPhone : le compte en tête, puis Notifications.
/// Tout est natif ; seuls les écrans d'un événement (voir, modifier) s'ouvrent dans le module Événements.
struct SettingsView: View {
    @ObservedObject var store: SettingsStore
    let topInset: CGFloat
    let isHost: Bool
    var hostMusic: HostMusicStore?
    let open: (WebModel.PagePlace) -> Void
    @State private var confirmSignOut = false

    var body: some View {
        NavigationStack {
            List {
                accountSection
                Section {
                    NavigationLink {
                        NotificationSettingsView(store: store)
                    } label: {
                        SettingsRow(symbol: "bell.badge.fill", tint: .red, title: "Notifications",
                                    hint: "Musique, jeux, avis et événements ; catégories et tags suivis")
                    }
                    if store.account != nil {
                        NavigationLink {
                            GroupsView(store: store.groups, privacy: store.privacy)
                        } label: {
                            SettingsRow(symbol: "person.3.fill", tint: .blue, title: "Groupes",
                                        hint: "Les groupes dont tu fais partie ; crée les tiens")
                        }
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
                                        hint: "Purify Test : dernier score, profil et record")
                        }
                    }
                    // « Ton avis » : l'hôte, et les comptes Guest+ et au-dessus (droit « Écrire un avis »).
                    if isHost || store.account?.feedback == true {
                        page(.tab("feedback"), "bubble.left.and.bubble.right.fill", .green, "Ton avis", "Une idée, un bug ? Écris à l'organisateur")
                    }
                }
                Section {
                    NavigationLink { PrivacyView() } label: {
                        SettingsRow(symbol: "lock.fill", tint: .blue, title: "Confidentialité", hint: "Tes données et tes choix")
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
            .background(AppConfig.background)
            .navigationTitle("Réglages")
        }
        .tint(Palette.accent)
        .padding(.top, topInset)
        .background(AppConfig.background.ignoresSafeArea())
        .task { await store.refreshAccount() }
        .confirmationDialog("Se déconnecter de ce compte ?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("Se déconnecter", role: .destructive) { Task { await store.session.signOut() } }
        } message: {
            Text("Tu pourras te reconnecter avec ton numéro. Les notifications des événements s'arrêtent sur cet iPhone.")
        }
        .overlay(alignment: .bottom) { SessionNotice(store: store.session) }
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

    private func page(_ place: WebModel.PagePlace, _ symbol: String, _ tint: Color, _ title: String, _ hint: String) -> some View {
        Button { open(place) } label: {
            HStack {
                SettingsRow(symbol: symbol, tint: tint, title: title, hint: hint)
                Spacer(minLength: 0)
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
        AsyncImage(url: photo.flatMap(URL.init(string:))) { image in
            image.resizable().scaledToFill()
        } placeholder: {
            Text(name.first.map(String.init) ?? "")
                .font(.title2.weight(.bold))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .overlay { if name.isEmpty { Image(systemName: "person.fill").font(.title2) } }
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
