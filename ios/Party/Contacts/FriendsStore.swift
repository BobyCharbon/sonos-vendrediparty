import Contacts
import Foundation

extension PartyAPI {
    private struct FriendsReply: Decodable { let friends: [PartyFriend] }
    private struct PreviewReply: Decodable { let invite: AppInvitePreview? }

    /// Comptes reconnus dans mes contacts → surnom, photo, arrivée sur Party, groupes en commun (jamais de numéro).
    func contactFriends(token: String, ids: [String]) async throws -> [PartyFriend] {
        guard !ids.isEmpty else { return [] }
        let reply: FriendsReply = try await postDecoding("/api/account/contacts/friends", body: ["token": token, "ids": ids], timeout: 30)
        return reply.friends
    }

    func myAppInvite(token: String, renew: Bool = false) async throws -> AppInviteLink {
        try await postDecoding("/api/account/invite", body: ["token": token, "renew": renew])
    }

    func appInvitePreview(_ invite: String) async throws -> AppInvitePreview? {
        let reply: PreviewReply = try await postDecoding("/api/account/invite/preview", body: ["invite": invite])
        return reply.invite
    }

    func claimAppInvite(token: String, invite: String) async throws -> AppInviteClaim {
        try await postDecoding("/api/account/invite/claim", body: ["token": token, "invite": invite])
    }

    private struct InvitedByReply: Decodable { let invitedBy: [InvitedBy]?; enum CodingKeys: String, CodingKey { case invitedBy = "invited_by" } }

    /// nil : pas le droit « Voir qui a invité qui ».
    func invitedBy(token: String, id: String) async throws -> [InvitedBy]? {
        let reply: InvitedByReply = try await postDecoding("/api/account/card/invited-by", body: ["token": token, "id": id])
        return reply.invitedBy
    }
}

struct AppInvitePreview: Decodable, Equatable, Sendable { let inviter: String }

/// Le nom de l'inviteur n'est jamais renvoyé à l'invité : « qui a invité qui » est réservé aux admins.
struct AppInviteClaim: Decodable, Equatable, Sendable { let new: Bool }

/// Une arrivée par lien, pour la fiche d'un membre (admins) : qui, par quel lien, quand.
struct InvitedBy: Decodable, Equatable, Identifiable, Sendable {
    let inviter: String
    let via: String
    let targetName: String?
    let at: Date?

    var id: String { "\(via)-\(at?.timeIntervalSince1970 ?? 0)-\(targetName ?? "")" }

    enum CodingKeys: String, CodingKey { case inviter, via, at, targetName = "target_name" }

    init(inviter: String, via: String, targetName: String?, at: Date?) {
        self.inviter = inviter
        self.via = via
        self.targetName = targetName
        self.at = at
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        inviter = try c.decodeIfPresent(String.self, forKey: .inviter) ?? ""
        via = try c.decode(String.self, forKey: .via)
        targetName = try c.decodeIfPresent(String.self, forKey: .targetName)
        at = (try c.decodeIfPresent(String.self, forKey: .at)).flatMap(PartyDates.parse)
    }

    /// « via le groupe Les amis », « via l'événement Halloween », « avec son lien Party ».
    var how: String {
        switch via {
        case "group": return "via le groupe \(targetName ?? "(supprimé)")"
        case "event": return "via l'événement \(targetName ?? "(supprimé)")"
        default: return "avec son lien Party"
        }
    }
}

/// Le répertoire avec les étiquettes des numéros (« mobile »…), pour l'onglet « À inviter ». Reste sur l'iPhone.
protocol DirectorySource: Sendable {
    func contacts() async throws -> [DirectoryContact]
}

struct DeviceDirectory: DirectorySource {
    func contacts() async throws -> [DirectoryContact] {
        try await Task.detached(priority: .utility) {
            let keys: [CNKeyDescriptor] = [CNContactFormatter.descriptorForRequiredKeys(for: .fullName),
                                           CNContactPhoneNumbersKey as CNKeyDescriptor,
                                           CNContactNicknameKey as CNKeyDescriptor,
                                           CNContactOrganizationNameKey as CNKeyDescriptor]
            var list: [DirectoryContact] = []
            try CNContactStore().enumerateContacts(with: CNContactFetchRequest(keysToFetch: keys)) { contact, _ in
                let numbers = contact.phoneNumbers.map { LabeledNumber(value: $0.value.stringValue, label: $0.label) }
                guard !numbers.isEmpty else { return }
                list.append(DirectoryContact(identifier: contact.identifier, name: DeviceContacts.name(of: contact), numbers: numbers))
            }
            return list
        }.value
    }
}

/// Réglages › Mes amis dans Party : amis reconnus, contacts à inviter, mon lien personnel, invitation reçue par lien.
@MainActor
final class FriendsStore: ObservableObject {
    @Published private(set) var friends: [PartyFriend] = []
    @Published private(set) var loaded = false
    @Published private(set) var loading = false
    @Published private(set) var error: String?
    @Published private(set) var toInvite: [InviteCandidate] = []
    @Published private(set) var invite: AppInviteLink?
    /// Mon rôle ne permet pas d'inviter (droit « Inviter dans Party » retiré) : bannière et bouton masqués.
    @Published private(set) var canInvite = true
    @Published private(set) var invited: [String: Date]
    @Published private(set) var myGroups: [GroupList.Group] = []
    @Published var notice: String?
    /// Lien /events/join/<lien> ouvert dans l'app : la feuille « X t'invite sur Party » s'affiche.
    @Published var pendingInvite: String?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private let directory: DirectorySource
    private let defaults: UserDefaults
    private static let invitedKey = "party.friends.invited"
    private static let pendingKey = "party.friends.pendingInvite"

    init(api: PartyAPI, web: WebStorage?, directory: DirectorySource = DeviceDirectory(), defaults: UserDefaults = .standard) {
        self.api = api
        self.web = web
        self.directory = directory
        self.defaults = defaults
        let stored = defaults.dictionary(forKey: Self.invitedKey) as? [String: Double] ?? [:]
        invited = stored.mapValues { Date(timeIntervalSince1970: $0) }
        pendingInvite = defaults.string(forKey: Self.pendingKey)
    }

    // MARK: Chargement

    /// Contacts relus (empreintes), puis les amis reconnus, la liste à inviter et mon lien.
    func load(force: Bool = false) async {
        guard !loading else { return }
        loading = true
        defer { loading = false }
        let contacts = ContactNames.shared
        await contacts.refresh(force: force)
        guard contacts.access.canRead, let token = await web?.accountToken() else {
            friends = []
            toInvite = []
            loaded = true
            return
        }
        do {
            friends = try await api.contactFriends(token: token, ids: Array(contacts.names.keys).sorted())
            error = contacts.error
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? "Tes amis n'ont pas pu être chargés."
        }
        toInvite = FriendsLogic.toInvite((try? await directory.contacts()) ?? [], matched: Set(contacts.snapshot.contacts.values))
        loaded = true
        await loadInvite(token: token)
        myGroups = ((try? await api.groups(token: token))?.groups ?? []).filter { $0.mine && !$0.system }
    }

    private func loadInvite(token: String, renew: Bool = false) async {
        do {
            invite = try await api.myAppInvite(token: token, renew: renew)
            canInvite = true
            if renew { notice = "Nouveau lien : l'ancien ne marche plus" }
        } catch PartyAPIError.server(let message) where message.contains("rôle") {
            canInvite = false
        } catch {
            if renew { notice = (error as? LocalizedError)?.errorDescription ?? "Le lien n'a pas pu être changé." }
        }
    }

    func renewLink() async {
        guard let token = await web?.accountToken() else { return }
        await loadInvite(token: token, renew: true)
    }

    var rows: [FriendRow] { FriendsLogic.rows(friends, names: ContactNames.shared.names) }

    // MARK: Actions

    /// SMS envoyé (ou partage) : gardé sur cet iPhone, pour « Invité · il y a 2 j ».
    func markInvited(_ candidate: InviteCandidate, at date: Date = Date()) {
        invited[candidate.id] = date
        defaults.set(invited.mapValues(\.timeIntervalSince1970), forKey: Self.invitedKey)
    }

    func add(_ friend: PartyFriend, to group: GroupList.Group, as name: String) async {
        guard let token = await web?.accountToken() else { return }
        do {
            _ = try await api.inviteToGroup(token: token, groupID: group.id, member: friend.id, phone: nil)
            notice = "\(name) a reçu ton invitation dans « \(group.name) »"
        } catch {
            notice = (error as? LocalizedError)?.errorDescription ?? "L'invitation n'a pas pu être envoyée."
        }
    }

    /// Numéro du contact (répertoire de l'iPhone) relié à ce compte, pour un SMS.
    func phone(of friend: PartyFriend) -> String? {
        guard let identifier = ContactNames.shared.contactIdentifier(for: friend.id),
              let contact = try? CNContactStore().unifiedContact(withIdentifier: identifier, keysToFetch: [CNContactPhoneNumbersKey as CNKeyDescriptor])
        else { return nil }
        let numbers = contact.phoneNumbers.map { LabeledNumber(value: $0.value.stringValue, label: $0.label) }
        return (numbers.first { n in PhoneNumbers.e164(n.value).map { FriendsLogic.isMobile(n, e164: $0) } ?? false } ?? numbers.first)?.value
    }

    // MARK: Invitation reçue par lien (/events/join/<lien>)

    func received(_ invite: String) {
        pendingInvite = invite
        defaults.set(invite, forKey: Self.pendingKey)
    }

    func preview(_ invite: String) async -> AppInvitePreview? {
        try? await api.appInvitePreview(invite)
    }

    /// Réclame le lien gardé (compte connecté, profil complet) ; la base refuse un compte ancien ou son propre lien.
    func claim(_ invite: String) async -> Result<AppInviteClaim, Error> {
        guard let token = await web?.accountToken() else { return .failure(PartyAPIError.server("Connecte-toi pour accepter l'invitation")) }
        do {
            let result = try await api.claimAppInvite(token: token, invite: invite)
            forgetInvite()
            return .success(result)
        } catch {
            let message = (error as? LocalizedError)?.errorDescription ?? ""
            if !message.localizedCaseInsensitiveContains("profil") { forgetInvite() }  // définitif : inutile de réessayer
            return .failure(error)
        }
    }

    func forgetInvite() {
        pendingInvite = nil
        defaults.removeObject(forKey: Self.pendingKey)
    }
}
