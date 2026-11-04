import Contacts
import CryptoKit
import Foundation

/// Accès au répertoire, tel que l'app le voit.
enum ContactsAccess: Equatable {
    case notDetermined, denied, restricted, authorized
    /// iOS 18 : seulement les contacts choisis par l'utilisateur.
    case limited

    var canRead: Bool { self == .authorized || self == .limited }
}

/// Un contact du répertoire : son nom tel que l'utilisateur l'a écrit, ses numéros (rien ne quitte l'iPhone).
struct ContactEntry: Equatable, Sendable {
    let identifier: String
    let name: String
    let numbers: [String]
}

struct ContactMatch: Codable, Equatable, Sendable {
    let userID: String
    let hash: String

    enum CodingKeys: String, CodingKey { case hash, userID = "user_id" }
}

protocol ContactsSource: Sendable {
    func access() -> ContactsAccess
    func requestAccess() async -> Bool
    func entries() async throws -> [ContactEntry]
}

protocol ContactsMatching: Sendable {
    func key() async throws -> String
    func match(_ hashes: [String]) async throws -> [ContactMatch]
}

/// Ce qui est gardé sur l'iPhone (Application Support, chiffré tant que l'iPhone est verrouillé) : jamais envoyé.
struct ContactNamesSnapshot: Codable, Equatable {
    var names: [String: String] = [:]
    /// Compte → identifiant du contact (« Voir le contact » sur la fiche).
    var contacts: [String: String] = [:]
    /// Compte → empreinte de son numéro (celle que contacts_match a reconnue) : preuve, pour « Écrire » (messages
    /// directs), qu'on a la personne dans ses contacts. Optionnel : un ancien cache se relit sans.
    var hashes: [String: String]? = nil
    var syncedAt: Date?
    /// Empreinte de la liste envoyée : inutile de redemander si rien n'a changé.
    var fingerprint: String?
}

/// Noms des contacts (avis f780431defe7) : un membre Party qui est dans le répertoire s'affiche sous le nom que
/// l'utilisateur lui a donné, « Nom du contact · pseudo », comme WhatsApp. Seulement dans l'app iPhone ; les numéros
/// partent hachés (HMAC-SHA256 avec la clé de Party), les noms restent sur l'appareil.
@MainActor
final class ContactNames: ObservableObject {
    static let shared = ContactNames()

    /// Au-delà, on redemande même si le répertoire n'a pas changé (nouveaux membres Party).
    static let staleAfter: TimeInterval = 12 * 3600
    private static let changeDelay: UInt64 = 2_000_000_000
    private static let promptKey = "party.contacts.prompted"

    @Published private(set) var access: ContactsAccess
    @Published private(set) var snapshot: ContactNamesSnapshot
    @Published private(set) var syncing = false
    @Published private(set) var error: String?

    private let source: ContactsSource
    private var matcher: ContactsMatching?
    private let file: URL?
    private let defaults: UserDefaults
    private var observer: NSObjectProtocol?
    /// Après chaque nouvelle comparaison : l'ancien et le nouveau résultat (notification des contacts arrivés).
    var matchesChanged: ((ContactNamesSnapshot, ContactNamesSnapshot) -> Void)?
    private var pendingChange: Task<Void, Never>?

    init(source: ContactsSource = DeviceContacts(), matcher: ContactsMatching? = nil,
         file: URL? = ContactNames.defaultFile, defaults: UserDefaults = .standard) {
        self.source = source
        self.matcher = matcher
        self.file = file
        self.defaults = defaults
        access = source.access()
        snapshot = file.flatMap { try? Data(contentsOf: $0) }.flatMap { try? JSONDecoder().decode(ContactNamesSnapshot.self, from: $0) }
            ?? ContactNamesSnapshot()
        if !access.canRead { snapshot = ContactNamesSnapshot() }
    }

    nonisolated static var defaultFile: URL? {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?
            .appendingPathComponent("contact-names.json")
    }

    /// Branché au lancement (WebModel) : session du compte pour parler à Party, et suivi des changements du répertoire.
    func configure(api: PartyAPI, web: WebStorage) {
        matcher = PartyContactsMatcher(api: api, web: web)
        // « Ton contact Léa est sur Party » : comparée à chaque nouvelle reconnaissance (Mes amis dans Party).
        ContactJoinNotifier.shared.configure(api: api, web: web)
        matchesChanged = { before, after in ContactJoinNotifier.shared.matchesChanged(before: before, after: after) }
        guard observer == nil else { return }
        observer = NotificationCenter.default.addObserver(forName: .CNContactStoreDidChange, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.contactsChanged() }
        }
        Task { await refresh() }
    }

    // MARK: Lecture

    var names: [String: String] { snapshot.names }
    var recognized: Int { snapshot.names.count }

    /// Nom à afficher : celui du contact s'il existe, sinon le pseudo.
    func displayName(for userID: String?, fallback pseudo: String) -> String {
        label(for: userID, pseudo: pseudo).primary
    }

    func label(for userID: String?, pseudo: String) -> PersonLabel {
        PersonLabel(contact: userID.flatMap { snapshot.names[$0] }, pseudo: pseudo)
    }

    func contactIdentifier(for userID: String) -> String? { snapshot.contacts[userID] }

    /// Empreinte du numéro de ce membre s'il est dans mes contacts (messages directs : « Écrire »).
    func contactHash(for userID: String) -> String? { snapshot.hashes?[userID] }

    // MARK: Accès

    /// Écran d'explication proposé une seule fois (Discussions), tant que l'iPhone n'a pas encore répondu.
    var shouldPrompt: Bool { access == .notDetermined && !defaults.bool(forKey: Self.promptKey) }

    func promptShown() { defaults.set(true, forKey: Self.promptKey) }

    /// Demande d'accès (fenêtre d'iOS), puis première reconnaissance.
    func requestAccess() async {
        promptShown()
        _ = await source.requestAccess()
        access = source.access()
        await refresh(force: true)
    }

    /// Retour au premier plan : l'accès a pu changer dans Réglages ; actualisation si c'est ancien.
    func appBecameActive() {
        access = source.access()
        Task { await refresh() }
    }

    // MARK: Reconnaissance

    func refresh(force: Bool = false) async {
        access = source.access()
        guard access.canRead else {
            if !snapshot.names.isEmpty { save(ContactNamesSnapshot()) }
            return
        }
        guard let matcher, !syncing else { return }
        syncing = true
        defer { syncing = false }
        do {
            let entries = try await source.entries()
            let key = try await matcher.key()
            let table = Self.digests(entries, key: key)
            let fingerprint = Self.fingerprint(of: table.keys, key: key)
            let fresh = snapshot.syncedAt.map { Date().timeIntervalSince($0) < Self.staleAfter } ?? false
            if !force && fresh && fingerprint == snapshot.fingerprint { return }
            let matches = table.isEmpty ? [] : try await matcher.match(table.keys.sorted())
            let before = snapshot
            save(Self.snapshot(from: matches, table: table, fingerprint: fingerprint))
            matchesChanged?(before, snapshot)
            error = nil
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? "Tes contacts n'ont pas pu être comparés. Réessaie plus tard."
        }
    }

    /// Empreinte → contact (le premier contact qui a ce numéro l'emporte).
    nonisolated static func digests(_ entries: [ContactEntry], key: String, region: String = PhoneNumbers.deviceRegion) -> [String: ContactEntry] {
        var table: [String: ContactEntry] = [:]
        for entry in entries where !entry.name.isEmpty {
            for number in entry.numbers {
                for e164 in PhoneNumbers.candidates(number, region: region) {
                    let hash = PhoneNumbers.digest(e164, key: key)
                    if table[hash] == nil { table[hash] = entry }
                }
            }
        }
        return table
    }

    nonisolated static func snapshot(from matches: [ContactMatch], table: [String: ContactEntry], fingerprint: String) -> ContactNamesSnapshot {
        var result = ContactNamesSnapshot(syncedAt: Date(), fingerprint: fingerprint)
        for match in matches.sorted(by: { $0.hash < $1.hash }) {
            guard let entry = table[match.hash], result.names[match.userID] == nil else { continue }
            result.names[match.userID] = entry.name
            result.contacts[match.userID] = entry.identifier
            result.hashes = (result.hashes ?? [:]).merging([match.userID: match.hash]) { first, _ in first }
        }
        return result
    }

    private nonisolated static func fingerprint(of hashes: Dictionary<String, ContactEntry>.Keys, key: String) -> String {
        let joined = (hashes.sorted() + [key]).joined(separator: ",")
        return SHA256.hash(data: Data(joined.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    /// Un contact ajouté, renommé ou supprimé (ici ou dans l'app Contacts) : on relit après un court instant.
    private func contactsChanged() {
        pendingChange?.cancel()
        pendingChange = Task { [weak self] in
            try? await Task.sleep(nanoseconds: Self.changeDelay)
            guard !Task.isCancelled else { return }
            await self?.refresh(force: true)
        }
    }

    private func save(_ next: ContactNamesSnapshot) {
        snapshot = next
        guard let file else { return }
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let data = try? JSONEncoder().encode(next) {
            try? data.write(to: file, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        }
    }
}

/// Le vrai répertoire de l'iPhone (CNContactStore).
struct DeviceContacts: ContactsSource {
    func access() -> ContactsAccess {
        let status = CNContactStore.authorizationStatus(for: .contacts)
        if #available(iOS 18, *), status == .limited { return .limited }
        switch status {
        case .authorized: return .authorized
        case .denied: return .denied
        case .restricted: return .restricted
        default: return .notDetermined
        }
    }

    func requestAccess() async -> Bool {
        (try? await CNContactStore().requestAccess(for: .contacts)) ?? false
    }

    func entries() async throws -> [ContactEntry] {
        try await Task.detached(priority: .utility) {
            let store = CNContactStore()
            let keys: [CNKeyDescriptor] = [CNContactFormatter.descriptorForRequiredKeys(for: .fullName),
                                           CNContactPhoneNumbersKey as CNKeyDescriptor,
                                           CNContactNicknameKey as CNKeyDescriptor,
                                           CNContactOrganizationNameKey as CNKeyDescriptor]
            var list: [ContactEntry] = []
            try store.enumerateContacts(with: CNContactFetchRequest(keysToFetch: keys)) { contact, _ in
                let numbers = contact.phoneNumbers.map { $0.value.stringValue }
                guard !numbers.isEmpty else { return }
                list.append(ContactEntry(identifier: contact.identifier, name: Self.name(of: contact), numbers: numbers))
            }
            return list
        }.value
    }

    static func name(of contact: CNContact) -> String {
        let full = CNContactFormatter.string(from: contact, style: .fullName)?.trimmingCharacters(in: .whitespaces) ?? ""
        if !full.isEmpty { return full }
        return [contact.nickname, contact.organizationName].map { $0.trimmingCharacters(in: .whitespaces) }.first { !$0.isEmpty } ?? ""
    }
}

/// Party (POST /api/account/contacts/key et /match) avec la session du compte.
struct PartyContactsMatcher: ContactsMatching, @unchecked Sendable {
    let api: PartyAPI
    weak var web: WebStorage?

    private struct KeyReply: Decodable { let key: String }
    private struct MatchReply: Decodable { let matches: [ContactMatch] }

    private func token() async throws -> String {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi pour reconnaître tes contacts") }
        return token
    }

    func key() async throws -> String {
        let reply: KeyReply = try await api.postDecoding("/api/account/contacts/key", body: ["token": try await token()])
        return reply.key
    }

    func match(_ hashes: [String]) async throws -> [ContactMatch] {
        let reply: MatchReply = try await api.postDecoding("/api/account/contacts/match",
                                                           body: ["token": try await token(), "hashes": hashes], timeout: 30)
        return reply.matches
    }
}
