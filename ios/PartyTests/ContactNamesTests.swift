import Foundation
import Testing
@testable import Party

/// Noms des contacts (avis f780431defe7) : numéros normalisés en E.164, seules des empreintes partent, « Nom · pseudo ».
struct PhoneNumbersTests {
    @Test("Numéros suisses et français, toutes écritures", arguments: [
        ("+41 79 123 45 67", "CH", "+41791234567"),
        ("0041791234567", "CH", "+41791234567"),
        ("+41 (0)79 123 45 67", "FR", "+41791234567"),
        ("079 123 45 67", "CH", "+41791234567"),
        ("06 12 34 56 78", "FR", "+33612345678"),
        ("+33 6 12 34 56 78", "CH", "+33612345678"),
        ("41791234567", "CH", "+41791234567"),
        ("(415) 555-0100", "US", "+14155550100"),
        ("06 123 4567", "IT", "+39061234567"),
    ])
    func normalizes(raw: String, region: String, expected: String) {
        #expect(PhoneNumbers.e164(raw, region: region) == expected)
    }

    @Test("Numéro national : région du téléphone d'abord, puis la Suisse et la France")
    func nationalCandidates() {
        #expect(PhoneNumbers.candidates("079 123 45 67", region: "FR") == ["+33791234567", "+41791234567"])
        #expect(PhoneNumbers.candidates("079 123 45 67", region: "CH") == ["+41791234567", "+33791234567"])
        #expect(PhoneNumbers.candidates("+41791234567", region: "FR") == ["+41791234567"])
        #expect(PhoneNumbers.candidates("0791234", region: "CH") == ["+41791234"])  // trop court pour un autre pays
    }

    @Test("Ce qui n'est pas un numéro est ignoré", arguments: ["", "abc", "112", "+0041", "+1234567890123456"])
    func rejects(raw: String) {
        #expect(PhoneNumbers.candidates(raw, region: "CH").isEmpty)
    }

    @Test("Empreinte : HMAC-SHA256 hexadécimal, identique au calcul de la base")
    func digestMatchesServer() {
        let key = String(repeating: "ab", count: 32)
        #expect(PhoneNumbers.digest("+41791234567", key: key) == "70de532050f13c2954ee760ecfad6e1bf46bfff78ce1340f89de35d8f0a4bf00")
        #expect(PhoneNumbers.digest("+33612345678", key: key) == "be2fe1a2050b33760a6ef539f23b954c74a0a815feac17bd2ef9c5b818b06c71")
    }
}

struct PersonLabelTests {
    @Test("Nom du contact en principal, pseudo en plus")
    func contactThenPseudo() {
        let label = PersonLabel(contact: "Marie Dupont", pseudo: "Mimi")
        #expect(label.primary == "Marie Dupont")
        #expect(label.secondary == "Mimi")
        #expect(label.text == "Marie Dupont · Mimi")
    }

    @Test("Sans contact, ou même nom : le pseudo seul")
    func pseudoAlone() {
        #expect(PersonLabel(contact: nil, pseudo: "Mimi").text == "Mimi")
        #expect(PersonLabel(contact: "  ", pseudo: "Mimi").text == "Mimi")
        #expect(PersonLabel(contact: "Léa", pseudo: "lea").text == "Léa")
    }
}

private struct FakeSource: ContactsSource {
    var status: ContactsAccess = .authorized
    var list: [ContactEntry]
    func access() -> ContactsAccess { status }
    func requestAccess() async -> Bool { status.canRead }
    func entries() async throws -> [ContactEntry] { list }
}

private final class FakeMatcher: ContactsMatching, @unchecked Sendable {
    static let key = String(repeating: "cd", count: 32)
    let accounts: [String: String]  // E.164 → compte Party
    private(set) var sent: [[String]] = []

    init(accounts: [String: String]) { self.accounts = accounts }

    func key() async throws -> String { Self.key }

    func match(_ hashes: [String]) async throws -> [ContactMatch] {
        sent.append(hashes)
        return accounts.compactMap { number, user in
            let hash = PhoneNumbers.digest(number, key: Self.key)
            return hashes.contains(hash) ? ContactMatch(userID: user, hash: hash) : nil
        }
    }
}

@MainActor
struct ContactNamesStoreTests {
    private func store(_ source: FakeSource, _ matcher: FakeMatcher) -> ContactNames {
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("contacts-\(UUID().uuidString).json")
        return ContactNames(source: source, matcher: matcher, file: file, defaults: UserDefaults(suiteName: UUID().uuidString)!)
    }

    @Test("Les membres de mon répertoire prennent le nom du contact ; seules des empreintes partent")
    func recognizes() async {
        let matcher = FakeMatcher(accounts: ["+41791234567": "u-marie", "+41790000000": "u-inconnu"])
        let names = store(FakeSource(list: [ContactEntry(identifier: "c1", name: "Marie Dupont", numbers: ["079 123 45 67"]),
                                            ContactEntry(identifier: "c2", name: "Paul", numbers: ["+33 6 00 00 00 00"])]), matcher)
        await names.refresh(force: true)
        #expect(names.displayName(for: "u-marie", fallback: "Mimi") == "Marie Dupont")
        #expect(names.label(for: "u-marie", pseudo: "Mimi").text == "Marie Dupont · Mimi")
        #expect(names.displayName(for: "u-autre", fallback: "Toto") == "Toto")
        #expect(names.contactIdentifier(for: "u-marie") == "c1")
        let sent = matcher.sent.flatMap { $0 }
        #expect(!sent.isEmpty && sent.allSatisfy { $0.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil })
        #expect(!sent.contains { $0.contains("791234567") })
    }

    @Test("Répertoire inchangé et récent : pas de nouvelle demande, sauf actualisation forcée")
    func skipsWhenUnchanged() async {
        let matcher = FakeMatcher(accounts: ["+41791234567": "u-marie"])
        let names = store(FakeSource(list: [ContactEntry(identifier: "c1", name: "Marie", numbers: ["+41791234567"])]), matcher)
        await names.refresh()
        await names.refresh()
        #expect(matcher.sent.count == 1)
        await names.refresh(force: true)
        #expect(matcher.sent.count == 2)
    }

    @Test("Sans accès aux contacts : aucun nom, rien d'envoyé")
    func deniedShowsPseudos() async {
        let matcher = FakeMatcher(accounts: ["+41791234567": "u-marie"])
        let names = store(FakeSource(status: .denied, list: [ContactEntry(identifier: "c1", name: "Marie", numbers: ["+41791234567"])]), matcher)
        await names.refresh(force: true)
        #expect(names.names.isEmpty && matcher.sent.isEmpty)
        #expect(names.displayName(for: "u-marie", fallback: "Mimi") == "Mimi")
    }

    @Test("Accès limité (iOS 18) : les contacts partagés sont reconnus")
    func limitedAccessWorks() async {
        let matcher = FakeMatcher(accounts: ["+41791234567": "u-marie"])
        let names = store(FakeSource(status: .limited, list: [ContactEntry(identifier: "c1", name: "Marie", numbers: ["+41791234567"])]), matcher)
        await names.refresh(force: true)
        #expect(names.recognized == 1)
    }

    @Test("Suggestions de l'@ : le nom du contact trouve aussi le membre, le pseudo reste inséré")
    func mentionsFindContactNames() {
        let members = [Conversation.Member(id: "u-marie", name: "Mimi", photo: nil, admin: false, creator: false)]
        let found = Mentions.suggestions(for: "mar", members: members, me: nil, contacts: ["u-marie": "Marie Dupont"])
        #expect(found.first?.label == "Mimi")
        #expect(found.first?.hint == "Marie Dupont")
        #expect(Mentions.suggestions(for: "mar", members: members, me: nil).filter { $0.member != nil }.isEmpty)
    }

    @Test("Nouveau contact prérempli : numéro, prénom et nom, sinon le pseudo")
    func newContactPrefill() {
        let full = ContactCardSheet.newContact(phone: "+41791234567", firstName: "Marie", lastName: "Dupont", pseudo: "Mimi")
        #expect(full.givenName == "Marie" && full.familyName == "Dupont" && full.nickname == "Mimi")
        #expect(full.phoneNumbers.first?.value.stringValue == "+41791234567")
        let nick = ContactCardSheet.newContact(phone: "+41791234567", firstName: nil, lastName: nil, pseudo: "Mimi")
        #expect(nick.givenName == "Mimi" && nick.familyName.isEmpty)
    }
}
