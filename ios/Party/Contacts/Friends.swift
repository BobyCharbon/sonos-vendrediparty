import Contacts
import Foundation

// Mes amis dans Party (avis 84fab3987f68) : les contacts de l'iPhone qui sont inscrits sur Party, et ceux à inviter.
// Tout ce qui touche au répertoire est calculé ICI, sur l'iPhone : aucun numéro ni nom ne part vers Party (seulement les
// empreintes de ContactNames, puis les identifiants de comptes déjà reconnus).

/// Un compte Party reconnu dans mes contacts (POST /api/account/contacts/friends) : jamais de numéro ni de rôle.
struct PartyFriend: Decodable, Equatable, Identifiable, Sendable {
    let id: String
    let displayName: String
    let photo: String?
    let joinedAt: Date?
    let commonGroups: [String]

    enum CodingKeys: String, CodingKey { case id, photo, displayName = "display_name", joinedAt = "joined_at", commonGroups = "common_groups" }

    init(id: String, displayName: String, photo: String? = nil, joinedAt: Date? = nil, commonGroups: [String] = []) {
        self.id = id
        self.displayName = displayName
        self.photo = photo
        self.joinedAt = joinedAt
        self.commonGroups = commonGroups
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        displayName = try c.decodeIfPresent(String.self, forKey: .displayName) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        joinedAt = (try c.decodeIfPresent(String.self, forKey: .joinedAt)).flatMap(PartyDates.parse)
        commonGroups = try c.decodeIfPresent([String].self, forKey: .commonGroups) ?? []
    }
}

/// Mon lien personnel d'invitation (POST /api/account/invite).
struct AppInviteLink: Decodable, Equatable, Sendable {
    let token: String
    let url: URL
    let joined: Int
}

/// Dates de Postgres (« 2026-11-03T10:00:00.518591+00:00 », avec ou sans fractions).
enum PartyDates {
    static func parse(_ text: String) -> Date? {
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: text) { return date }
        return ISO8601DateFormatter().date(from: text)
    }
}

/// Une ligne de la liste : le compte et le nom que je lui ai donné dans mes contacts.
struct FriendRow: Equatable, Identifiable, Sendable {
    let friend: PartyFriend
    let contactName: String

    var id: String { friend.id }
    var label: PersonLabel { PersonLabel(contact: contactName, pseudo: friend.displayName) }
}

/// Un contact du répertoire SANS compte Party (onglet « À inviter ») : son meilleur numéro, mobile d'abord.
struct InviteCandidate: Equatable, Identifiable, Sendable {
    let id: String
    let name: String
    /// Numéro tel qu'écrit dans le répertoire (pour le SMS), et sa forme internationale.
    let phone: String
    let e164: String
    let mobile: Bool
}

/// Un numéro du répertoire avec son étiquette (« mobile », « iPhone », « domicile »…).
struct LabeledNumber: Equatable, Sendable {
    let value: String
    let label: String?
}

struct DirectoryContact: Equatable, Sendable {
    let identifier: String
    let name: String
    let numbers: [LabeledNumber]
}

/// Calculs de l'écran, sans état : testables tels quels.
enum FriendsLogic {
    static let newcomerDays = 14
    /// Au-delà, une seule notification regroupée (« 5 de tes contacts sont sur Party »).
    static let groupedAfter = 3

    /// Liste A–Z par nom du contact (comme l'app Contacts), puis par pseudo.
    static func rows(_ friends: [PartyFriend], names: [String: String]) -> [FriendRow] {
        friends.compactMap { friend in names[friend.id].map { FriendRow(friend: friend, contactName: $0) } }
            .sorted { a, b in
                let order = a.contactName.localizedStandardCompare(b.contactName)
                return order == .orderedSame ? a.friend.displayName.localizedStandardCompare(b.friend.displayName) == .orderedAscending
                                             : order == .orderedAscending
            }
    }

    /// Lettre d'index : la première lettre sans accent, « # » pour le reste (rangé à la fin).
    static func letter(of name: String) -> String {
        guard let first = name.trimmingCharacters(in: .whitespaces).first else { return "#" }
        let folded = String(first).folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr_CH")).uppercased()
        return folded.range(of: "^[A-Z]$", options: .regularExpression) != nil ? folded : "#"
    }

    static func sections(_ rows: [FriendRow]) -> [(letter: String, rows: [FriendRow])] {
        var order: [String] = []
        var grouped: [String: [FriendRow]] = [:]
        for row in rows {
            let key = letter(of: row.contactName)
            if grouped[key] == nil { order.append(key) }
            grouped[key, default: []].append(row)
        }
        let sorted = order.filter { $0 != "#" } + order.filter { $0 == "#" }
        return sorted.map { ($0, grouped[$0] ?? []) }
    }

    /// Arrivés sur Party ces 14 derniers jours, les plus récents d'abord.
    static func newcomers(_ rows: [FriendRow], now: Date = Date()) -> [FriendRow] {
        let since = now.addingTimeInterval(-Double(newcomerDays) * 86_400)
        return rows.filter { ($0.friend.joinedAt ?? .distantPast) >= since }
            .sorted { ($0.friend.joinedAt ?? .distantPast) > ($1.friend.joinedAt ?? .distantPast) }
    }

    /// Recherche sur le nom du contact ou le pseudo, sans tenir compte des accents ni des majuscules.
    static func matches(_ text: String, query: String) -> Bool {
        let q = query.trimmingCharacters(in: .whitespaces)
        return q.isEmpty || text.range(of: q, options: [.caseInsensitive, .diacriticInsensitive]) != nil
    }

    static func filter(_ rows: [FriendRow], query: String) -> [FriendRow] {
        rows.filter { matches($0.contactName, query: query) || matches($0.friend.displayName, query: query) }
    }

    /// « À inviter » : les contacts dont AUCUN numéro n'a de compte Party (d'après leur numéro), mobiles d'abord, A–Z.
    /// matched = identifiants des contacts reconnus ; leurs numéros écartent aussi un doublon du même numéro.
    static func toInvite(_ directory: [DirectoryContact], matched: Set<String>,
                         region: String = PhoneNumbers.deviceRegion) -> [InviteCandidate] {
        let taken = Set(directory.filter { matched.contains($0.identifier) }
            .flatMap { $0.numbers.flatMap { PhoneNumbers.candidates($0.value, region: region) } })
        let list: [InviteCandidate] = directory.compactMap { contact in
            guard !matched.contains(contact.identifier), !contact.name.isEmpty else { return nil }
            let numbers = contact.numbers.compactMap { n in PhoneNumbers.e164(n.value, region: region).map { (n, $0) } }
            guard !numbers.isEmpty, numbers.allSatisfy({ !taken.contains($0.1) }) else { return nil }
            let best = numbers.first { isMobile($0.0, e164: $0.1) } ?? numbers[0]
            return InviteCandidate(id: contact.identifier, name: contact.name, phone: best.0.value, e164: best.1,
                                   mobile: isMobile(best.0, e164: best.1))
        }
        return list.sorted { a, b in
            a.mobile != b.mobile ? a.mobile : a.name.localizedStandardCompare(b.name) == .orderedAscending
        }
    }

    /// Mobile : étiquette « mobile » / « iPhone », ou numéro mobile suisse (+417…) ou français (+336, +337).
    static func isMobile(_ number: LabeledNumber, e164: String) -> Bool {
        if let label = number.label, [CNLabelPhoneNumberMobile, CNLabelPhoneNumberiPhone].contains(label) { return true }
        return e164.hasPrefix("+417") || e164.hasPrefix("+336") || e164.hasPrefix("+337")
    }

    /// Comptes reconnus depuis la comparaison précédente. Jamais à la toute première comparaison (tout serait « nouveau »).
    static func newlyMatched(before: ContactNamesSnapshot, after: ContactNamesSnapshot) -> [String] {
        guard before.syncedAt != nil else { return [] }
        return Set(after.names.keys).subtracting(before.names.keys).sorted()
    }

    /// Texte de la notification « Ton contact Léa est sur Party », regroupée au-delà de 3.
    static func joinMessage(_ names: [String]) -> String? {
        let list = names.filter { !$0.isEmpty }
        switch list.count {
        case 0: return nil
        case 1: return "Ton contact \(list[0]) est sur Party"
        case 2: return "Tes contacts \(list[0]) et \(list[1]) sont sur Party"
        case 3: return "Tes contacts \(list[0]), \(list[1]) et \(list[2]) sont sur Party"
        default: return "\(list.count) de tes contacts sont sur Party : \(list[0]), \(list[1]) et d'autres"
        }
    }

    /// « Invité il y a 2 j » : gardé sur l'iPhone seulement.
    static func invitedText(_ date: Date, now: Date = Date()) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.locale = Locale(identifier: "fr_CH")
        formatter.unitsStyle = .short
        return "Invité · \(formatter.localizedString(for: date, relativeTo: now))"
    }

    /// Texte du SMS d'invitation, avec mon lien personnel.
    static func smsBody(firstName: String, link: URL) -> String {
        let hello = firstName.isEmpty ? "Salut" : "Salut \(firstName)"
        return "\(hello) ! Je suis sur Party pour nos soirées et événements, rejoins-moi : \(link.absoluteString)"
    }
}
