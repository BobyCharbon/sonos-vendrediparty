import SwiftUI

/// Fiche profil d'un membre (POST /api/account/card) : ce que ses choix de confidentialité laissent voir.
struct MemberCard: Decodable, Equatable, Identifiable {
    let id: String
    let displayName: String
    let photo: String?
    let role: MemberRole
    let root: Bool
    let me: Bool
    let firstName: String?
    let lastName: String?
    let phone: String?
    let groups: [String]

    enum CodingKeys: String, CodingKey {
        case id, photo, role, root, me, phone, groups
        case displayName = "display_name", firstName = "first_name", lastName = "last_name"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        displayName = try c.decodeIfPresent(String.self, forKey: .displayName) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        role = (try? c.decode(MemberRole.self, forKey: .role)) ?? .guest
        root = try c.decodeIfPresent(Bool.self, forKey: .root) ?? false
        me = try c.decodeIfPresent(Bool.self, forKey: .me) ?? false
        firstName = try c.decodeIfPresent(String.self, forKey: .firstName)
        lastName = try c.decodeIfPresent(String.self, forKey: .lastName)
        phone = try c.decodeIfPresent(String.self, forKey: .phone)
        groups = try c.decodeIfPresent([String].self, forKey: .groups) ?? []
    }

    var fullName: String { [firstName, lastName].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ") }
    var dialable: String? { phone.map { "+" + $0.trimmingCharacters(in: CharacterSet(charactersIn: "+")) } }
}

/// Mes choix : nom et prénom publics, et les groupes où je montre mon numéro.
struct Privacy: Decodable, Equatable {
    let showName: Bool
    let phoneGroups: [String]

    enum CodingKeys: String, CodingKey { case showName = "show_name", phoneGroups = "phone_groups" }
}

extension PartyAPI {
    func memberCard(token: String, id: String) async throws -> MemberCard {
        try await postDecoding("/api/account/card", body: ["token": token, "id": id])
    }

    func privacy(token: String) async throws -> Privacy { try await postDecoding("/api/account/privacy", body: ["token": token]) }

    func setNamePublic(token: String, on: Bool) async throws -> Privacy {
        try await postDecoding("/api/account/privacy/name", body: ["token": token, "on": on])
    }

    func setGroupPhoneShare(token: String, groupID: String, on: Bool) async throws -> Privacy {
        try await postDecoding("/api/account/privacy/phone", body: ["token": token, "group_id": groupID, "on": on])
    }
}

/// Confidentialité du compte (Mon profil, Groupes) : lue une fois, mise à jour à chaque choix.
@MainActor
final class PrivacyStore: ObservableObject {
    @Published private(set) var privacy: Privacy?
    @Published private(set) var saving = false
    @Published var error: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    func load() async {
        guard let token = await web?.accountToken() else { return }
        privacy = try? await api.privacy(token: token)
    }

    func sharesPhone(in group: String) -> Bool { privacy?.phoneGroups.contains(group) == true }

    func setNamePublic(_ on: Bool) async {
        await save { token in try await api.setNamePublic(token: token, on: on) }
    }

    func setPhone(_ on: Bool, group: String) async {
        await save { token in try await api.setGroupPhoneShare(token: token, groupID: group, on: on) }
    }

    func card(_ id: String) async throws -> MemberCard {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi pour voir les profils") }
        return try await api.memberCard(token: token, id: id)
    }

    private func save(_ job: (String) async throws -> Privacy) async {
        guard let token = await web?.accountToken() else { return }
        saving = true
        defer { saving = false }
        do {
            privacy = try await job(token)
            error = nil
        } catch {
            self.error = "Ton choix n'a pas été enregistré. Réessaie."
        }
    }
}

/// Fiche profil : photo, surnom, rôle ; nom, numéro (appeler, écrire) et groupes en commun selon ce qui est permis.
struct MemberCardView: View {
    let store: PrivacyStore
    let memberID: String
    @State private var card: MemberCard?
    @State private var error: String?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            List {
                if let card {
                    Section {
                        VStack(spacing: 8) {
                            AdminAvatar(photo: card.photo, name: card.displayName, size: 104)
                            Text(card.displayName.isEmpty ? "Profil à compléter" : card.displayName).font(.title2.weight(.bold))
                            if !card.fullName.isEmpty { Text(card.fullName).foregroundStyle(.secondary) }
                            Text((card.root ? "👑 Root" : card.role.label) + (card.me ? " · c'est toi" : ""))
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .accessibilityElement(children: .combine)
                    }
                    .listRowBackground(Color.clear)
                    if let phone = card.dialable {
                        Section("Numéro") {
                            Text(phone).font(.headline)
                            Button("Appeler") { if let url = URL(string: "tel:\(phone)") { openURL(url) } }
                            Button("Message") { if let url = URL(string: "sms:\(phone)") { openURL(url) } }
                        }
                    }
                    if !card.groups.isEmpty {
                        Section(card.me ? "Mes groupes" : "Groupes en commun") {
                            Text(card.groups.joined(separator: " · "))
                        }
                    }
                    if card.me {
                        Section {
                        } footer: {
                            Text("Ton nom et ton numéro restent cachés tant que tu ne choisis pas de les montrer (Mon profil, Groupes).")
                        }
                    }
                } else if let error {
                    Text(error).foregroundStyle(.secondary)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle("Profil")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Fermer") { dismiss() } } }
            .overlay { if card == nil && error == nil { ProgressView() } }
            .task {
                do { card = try await store.card(memberID) } catch { self.error = error.localizedDescription }
            }
        }
        .tint(Palette.accent)
    }
}
