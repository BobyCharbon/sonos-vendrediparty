import SwiftUI

/// Onglet Réglages natif, à la manière des Réglages de l'iPhone : le compte en tête, puis Notifications.
/// Les écrans pas encore natifs (profil, abonnements, confidentialité, compte) s'ouvrent dans la page.
struct SettingsView: View {
    @ObservedObject var store: SettingsStore
    let topInset: CGFloat
    let isHost: Bool
    let open: (WebModel.PagePlace) -> Void

    var body: some View {
        NavigationStack {
            List {
                accountSection
                Section {
                    NavigationLink {
                        NotificationSettingsView(store: store, open: open)
                    } label: {
                        SettingsRow(symbol: "bell.badge.fill", tint: .red, title: "Notifications",
                                    hint: "Musique, jeux, avis et événements : choisis ce qui t'avertit")
                    }
                    if store.account != nil {
                        page(.account("/settings/subscriptions"), "tag.fill", .orange, "Abonnements",
                             "Catégories et tags d'événements que tu suis")
                    }
                }
                if isHost || store.account?.admin == true {
                    Section("Soirée") {
                        page(.tab("host"), "person.2.fill", .blue, "Invités et messages", "Messages des invités, invités, bannis")
                        page(.admin, "slider.horizontal.3", .gray, "Admin de la soirée", "Musique, enceintes, joueurs, jeux et réglages du site")
                        if store.account?.admin == true {
                            page(.account("/admin"), "shield.lefthalf.filled", .indigo, "Administration du groupe",
                                 "Demandes, membres, rôles et droits")
                        }
                    }
                }
                Section {
                    page(.tab("stats"), "trophy.fill", .orange, "Mes stats de jeu", "Purify Test : dernier score, radar et record")
                    page(.tab("feedback"), "bubble.left.and.bubble.right.fill", .green, "Ton avis", "Une idée, un bug ? Écris à l'organisateur")
                }
                if store.account != nil {
                    Section {
                        page(.account("/privacy"), "lock.fill", .blue, "Confidentialité", "Tes données et tes choix")
                        page(.account("/settings/account"), "gearshape.fill", .gray, "Gérer mon compte", "Suppression du compte")
                        page(.account("/account"), "rectangle.portrait.and.arrow.right", .red, "Se déconnecter", "En bas de la page du compte")
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
                Button { open(.account("/account")) } label: {
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
                .foregroundStyle(.primary)
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
