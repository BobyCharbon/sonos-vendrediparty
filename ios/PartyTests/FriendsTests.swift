import Contacts
import Foundation
import Testing
@testable import Party

/// Mes amis dans Party (avis 84fab3987f68) : tri A–Z, nouveaux, contacts à inviter (sur l'iPhone), notification des
/// contacts arrivés (jamais à la première comparaison, regroupée au-delà de 3), heures de silence, décodage.
struct FriendsLogicTests {
    private func friend(_ id: String, _ pseudo: String, joined: Date? = nil) -> PartyFriend {
        PartyFriend(id: id, displayName: pseudo, joinedAt: joined)
    }

    @Test("Liste A–Z par nom du contact, accents compris ; « # » pour le reste, à la fin")
    func sortsByContactName() {
        let rows = FriendsLogic.rows([friend("1", "zz"), friend("2", "aa"), friend("3", "mm"), friend("4", "nn"), friend("5", "pas dans mes contacts")],
                                     names: ["1": "Élodie", "2": "Zoé", "3": "adrien", "4": "07 Club"])
        #expect(rows.map(\.contactName) == ["07 Club", "adrien", "Élodie", "Zoé"])
        #expect(FriendsLogic.sections(rows).map(\.letter) == ["A", "E", "Z", "#"])
        #expect(rows.first { $0.id == "2" }?.label.text == "Zoé · aa")
    }

    @Test("Nouveaux sur Party : arrivés ces 14 jours, les plus récents d'abord")
    func newcomers() {
        let now = Date()
        let rows = FriendsLogic.rows([friend("1", "a", joined: now.addingTimeInterval(-86_400 * 20)),
                                      friend("2", "b", joined: now.addingTimeInterval(-86_400 * 2)),
                                      friend("3", "c", joined: now.addingTimeInterval(-3600))],
                                     names: ["1": "Anne", "2": "Bob", "3": "Cyril"])
        #expect(FriendsLogic.newcomers(rows, now: now).map(\.id) == ["3", "2"])
    }

    @Test("Recherche sur le nom ou le pseudo, sans accents ni majuscules")
    func search() {
        let rows = FriendsLogic.rows([friend("1", "Mimi"), friend("2", "Toto")], names: ["1": "Mélanie", "2": "Thomas"])
        #expect(FriendsLogic.filter(rows, query: "mela").map(\.id) == ["1"])
        #expect(FriendsLogic.filter(rows, query: "TOTO").map(\.id) == ["2"])
        #expect(FriendsLogic.filter(rows, query: " ").count == 2)
    }

    @Test("À inviter : contacts non reconnus seulement, mobiles d'abord, un numéro déjà reconnu écarté")
    func toInvite() {
        let directory = [
            DirectoryContact(identifier: "c1", name: "Léa", numbers: [LabeledNumber(value: "079 111 11 11", label: CNLabelPhoneNumberMobile)]),
            DirectoryContact(identifier: "c2", name: "Bureau", numbers: [LabeledNumber(value: "022 222 22 22", label: CNLabelWork)]),
            DirectoryContact(identifier: "c3", name: "Arthur", numbers: [LabeledNumber(value: "022 333 33 33", label: CNLabelHome),
                                                                        LabeledNumber(value: "+33 6 12 34 56 78", label: nil)]),
            DirectoryContact(identifier: "c4", name: "Léa (double)", numbers: [LabeledNumber(value: "+41791111111", label: nil)]),
            DirectoryContact(identifier: "c5", name: "", numbers: [LabeledNumber(value: "079 555 55 55", label: nil)]),
        ]
        let list = FriendsLogic.toInvite(directory, matched: ["c1"], region: "CH")
        #expect(list.map(\.id) == ["c3", "c2"])  // Léa (et son doublon) est déjà sur Party ; mobile d'abord
        #expect(list.first?.phone == "+33 6 12 34 56 78" && list.first?.mobile == true)
        #expect(list.last?.mobile == false)
    }

    @Test("Contacts arrivés : rien à la première comparaison, puis seulement les nouveaux comptes")
    func newlyMatched() {
        let first = ContactNamesSnapshot(names: ["u1": "Léa"], syncedAt: nil)
        let second = ContactNamesSnapshot(names: ["u1": "Léa", "u2": "Tom"], syncedAt: Date())
        #expect(FriendsLogic.newlyMatched(before: ContactNamesSnapshot(), after: first).isEmpty)
        #expect(FriendsLogic.newlyMatched(before: ContactNamesSnapshot(names: ["u1": "Léa"], syncedAt: Date()), after: second) == ["u2"])
    }

    @Test("Texte : un, deux, trois prénoms ; au-delà, regroupé", arguments: [
        (["Léa"], "Ton contact Léa est sur Party"),
        (["Léa", "Tom"], "Tes contacts Léa et Tom sont sur Party"),
        (["Léa", "Tom", "Max"], "Tes contacts Léa, Tom et Max sont sur Party"),
        (["Léa", "Tom", "Max", "Zoé", "Ana"], "5 de tes contacts sont sur Party : Léa, Tom et d'autres"),
    ])
    func joinMessage(names: [String], expected: String) {
        #expect(FriendsLogic.joinMessage(names) == expected)
    }

    @Test("Seuls les comptes arrivés récemment comptent (pas un ami de longue date ajouté aux contacts)")
    func recentOnly() {
        let now = Date()
        let list = ContactJoinNotifier.recentlyJoined([friend("old", "a", joined: now.addingTimeInterval(-86_400 * 30)),
                                                       friend("new", "b", joined: now.addingTimeInterval(-3600)),
                                                       friend("unknown", "c")], now: now)
        #expect(list.map(\.id) == ["new"])
    }

    @Test("Heures de silence : reportée à leur fin, minuit compris")
    func quietHours() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Zurich")!
        let night = calendar.date(from: DateComponents(year: 2026, month: 11, day: 4, hour: 23, minute: 30))!
        let morning = calendar.date(from: DateComponents(year: 2026, month: 11, day: 4, hour: 7, minute: 0))!
        let noon = calendar.date(from: DateComponents(year: 2026, month: 11, day: 4, hour: 12))!
        #expect(ContactJoinNotifier.delayForQuietHours(start: "23:00", end: "08:00", now: night, calendar: calendar) == 8.5 * 3600)
        #expect(ContactJoinNotifier.delayForQuietHours(start: "23:00", end: "08:00", now: morning, calendar: calendar) == 3600)
        #expect(ContactJoinNotifier.delayForQuietHours(start: "23:00", end: "08:00", now: noon, calendar: calendar) == 0)
        #expect(ContactJoinNotifier.delayForQuietHours(start: nil, end: nil, now: night, calendar: calendar) == 0)
    }

    @Test("Décodage : dates Postgres, champs absents, jamais de numéro attendu")
    func decoding() throws {
        let json = #"{"friends":[{"id":"u1","display_name":"Mimi","photo":null,"joined_at":"2026-11-03T10:00:00.518591+00:00","common_groups":["Vendredi Party"]},{"id":"u2"}]}"#
        struct Reply: Decodable { let friends: [PartyFriend] }
        let friends = try JSONDecoder().decode(Reply.self, from: Data(json.utf8)).friends
        #expect(friends[0].joinedAt == PartyDates.parse("2026-11-03T10:00:00Z")!.addingTimeInterval(0.518591)
                || abs(friends[0].joinedAt!.timeIntervalSince(PartyDates.parse("2026-11-03T10:00:00Z")!)) < 1)
        #expect(friends[0].commonGroups == ["Vendredi Party"])
        #expect(friends[1].displayName.isEmpty && friends[1].joinedAt == nil && friends[1].commonGroups.isEmpty)
        let link = try JSONDecoder().decode(AppInviteLink.self, from: Data(#"{"token":"t","url":"https://party.bobycharbon.ch/events/join/t","joined":2}"#.utf8))
        #expect(link.joined == 2)
        let prefs = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(#"{"push_enabled":true,"new_event":"all","event_changed":true,"poll_new":true,"date_fixed":true,"poll_nudge":true,"waitlist":true,"reminders":[],"chat":"all","rsvp_mine":true,"proposals":true,"contact_joins":false}"#.utf8))
        #expect(prefs.contactJoins == false && prefs.referralJoins == nil)
    }

    @Test("Lien /events/join/<lien> reconnu, le reste ignoré")
    func joinLink() {
        let token = "6b1f6f0e-4a8e-4c55-9d43-2f0b7c1d9e21"
        #expect(WebModel.appInviteLink(in: URL(string: "https://party.bobycharbon.ch/events/join/\(token.uppercased())")!) == token)
        #expect(WebModel.appInviteLink(in: URL(string: "https://party.bobycharbon.ch/events/invite/\(token)")!) == nil)
        #expect(WebModel.appInviteLink(in: URL(string: "https://party.bobycharbon.ch/events/join/pas-un-lien")!) == nil)
    }

    @Test("SMS prérempli avec le prénom et le lien")
    func sms() {
        let url = URL(string: "https://party.bobycharbon.ch/events/join/t")!
        #expect(FriendsLogic.smsBody(firstName: "Léa", link: url).hasPrefix("Salut Léa !"))
        #expect(FriendsLogic.smsBody(firstName: "", link: url).contains(url.absoluteString))
    }
}

private struct OneSource: ContactsSource {
    let list: [ContactEntry]
    func access() -> ContactsAccess { .authorized }
    func requestAccess() async -> Bool { true }
    func entries() async throws -> [ContactEntry] { list }
}

private final class GrowingMatcher: ContactsMatching, @unchecked Sendable {
    static let key = String(repeating: "ef", count: 32)
    var accounts: [String: String]

    init(_ accounts: [String: String]) { self.accounts = accounts }
    func key() async throws -> String { Self.key }
    func match(_ hashes: [String]) async throws -> [ContactMatch] {
        accounts.compactMap { number, user in
            let hash = PhoneNumbers.digest(number, key: Self.key)
            return hashes.contains(hash) ? ContactMatch(userID: user, hash: hash) : nil
        }
    }
}

@MainActor
struct ContactJoinHookTests {
    @Test("Avant/après : la première comparaison ne signale rien, la suivante signale le nouveau compte")
    func hookBeforeAfter() async {
        let matcher = GrowingMatcher(["+41791111111": "u-lea"])
        let names = ContactNames(source: OneSource(list: [ContactEntry(identifier: "c1", name: "Léa", numbers: ["+41791111111"]),
                                                          ContactEntry(identifier: "c2", name: "Tom", numbers: ["+41792222222"])]),
                                 matcher: matcher, file: nil, defaults: UserDefaults(suiteName: UUID().uuidString)!)
        var seen: [[String]] = []
        names.matchesChanged = { before, after in seen.append(FriendsLogic.newlyMatched(before: before, after: after)) }
        await names.refresh(force: true)
        matcher.accounts["+41792222222"] = "u-tom"
        await names.refresh(force: true)
        #expect(seen == [[], ["u-tom"]])
    }
}
