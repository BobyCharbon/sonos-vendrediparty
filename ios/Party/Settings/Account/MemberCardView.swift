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
        case roleLabel = "role_label"
        case displayName = "display_name", firstName = "first_name", lastName = "last_name"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        displayName = try c.decodeIfPresent(String.self, forKey: .displayName) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        let key = try c.decodeIfPresent(String.self, forKey: .role) ?? "guest"
        // Nom du rôle donné par la base (rôles personnalisés) ; sinon rôle de base connu, ou Guest.
        if let label = try c.decodeIfPresent(String.self, forKey: .roleLabel) {
            role = MemberRole(key: key, label: label, rank: MemberRole(rawValue: key).rank)
        } else {
            role = (try? c.decode(MemberRole.self, forKey: .role)) ?? .guest
        }
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

    /// Méninges du membre face aux miens ; nil si on n'est pas connecté ou si la comparaison est indisponible.
    func brainCompare(_ id: String) async -> BrainCompare? {
        guard let token = await web?.accountToken() else { return nil }
        return try? await api.brainCompare(token: token, target: id)
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
    @State private var brain: BrainCompare?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @ObservedObject private var contacts = ContactNames.shared
    @State private var contactSheet: ContactSheetItem?

    var body: some View {
        NavigationStack {
            List {
                if let card {
                    Section {
                        VStack(spacing: 8) {
                            AdminAvatar(photo: card.photo, name: card.displayName, size: 104)
                            let known = contacts.label(for: card.me ? nil : card.id, pseudo: card.displayName)
                            Text(known.primary.isEmpty ? "Profil à compléter" : known.primary).font(.title2.weight(.bold))
                            if let nick = known.secondary {
                                // Nom de mon répertoire en titre ; le pseudo Party juste dessous (avis f780431defe7).
                                Label("\(nick) · dans tes contacts", systemImage: "person.crop.circle.badge.checkmark")
                                    .font(.subheadline).foregroundStyle(.secondary)
                            }
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
                            if !card.me { contactButton(card, phone: phone) }
                        }
                    } else if !card.me {
                        Section {
                        } footer: {
                            Text("\(card.displayName.isEmpty ? "Ce membre" : card.displayName) ne montre pas son numéro dans vos groupes : impossible de l'ajouter aux contacts depuis Party.")
                        }
                    }
                    if !card.groups.isEmpty {
                        Section(card.me ? "Mes groupes" : "Groupes en commun") {
                            Text(card.groups.joined(separator: " · "))
                        }
                    }
                    if let brain, !card.me, !brain.isSelf {
                        BrainCompareSection(compare: brain)
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
            .overlay { if card == nil && error == nil { ProgressView().transition(.opacity) } }
            .sheet(item: $contactSheet) { item in
                ContactCardSheet(mode: item.mode) { contactSheet = nil }.ignoresSafeArea()
            }
            // Fiche arrivée : fondu de la roue vers le profil, plutôt qu'un remplacement sec.
            .motion(Motion.smooth, value: card == nil)
            .task {
                do { card = try await store.card(memberID) } catch { self.error = error.localizedDescription }
                if card?.me == false { brain = await store.brainCompare(memberID) }
            }
        }
        .tint(Palette.accent)
    }
}

/// « Ajouter aux contacts » (nouvelle fiche Contacts préremplie : numéro, prénom et nom, sinon le pseudo) ou
/// « Voir le contact » s'il est déjà dans le répertoire. Enregistré : le nom du contact s'affiche aussitôt dans l'app.
private struct ContactSheetItem: Identifiable {
    let id = UUID()
    let mode: ContactCardSheet.Mode
}

private extension MemberCardView {
    @ViewBuilder func contactButton(_ card: MemberCard, phone: String) -> some View {
        if let identifier = contacts.contactIdentifier(for: card.id), contacts.access.canRead {
            Button {
                if let existing = ContactCardSheet.existing(identifier) { contactSheet = ContactSheetItem(mode: .existing(existing)) }
            } label: {
                Label("Voir le contact", systemImage: "person.crop.circle")
            }
            .accessibilityIdentifier("member-see-contact")
        } else {
            Button {
                Haptics.tap()
                let fresh = ContactCardSheet.newContact(phone: phone, firstName: card.firstName, lastName: card.lastName, pseudo: card.displayName)
                contactSheet = ContactSheetItem(mode: .new(fresh))
            } label: {
                Label("Ajouter aux contacts", systemImage: "person.crop.circle.badge.plus")
            }
            .accessibilityIdentifier("member-add-contact")
        }
    }
}
