// Compilé dans la BETA seulement (et les recettes E2E_HOOKS) : absent du binaire de l'App Store (Pronos, contrôle Apple du 26.11).
#if BETA || E2E_HOOKS

import Foundation
import SwiftUI

/// Pronos entre amis (avis f071c5f46e3d, 17.11.2026, migration 20261117180000) : jamais d'argent ni de lot ; des points
/// au classement du groupe. La base garde les réponses cachées (organisateur compris) jusqu'au dévoilement et décide de
/// tout ; l'app ne fait qu'appeler le relais POST /api/account/pronos/rpc.
///
/// Pronos v2 (18.11.2026, migration 20261118090000) : nouveaux types (yesno, overunder, when, majority, award), patates
/// à planter (monnaie fictive, gratuite, sans valeur : un sac par personne et par groupe / événement), contestation,
/// réactions, saison. Toutes les clés v2 sont facultatives ici : un serveur d'avant les renvoie absentes.
/// Patates à l'écran seulement si `store.features.patates` (drapeau du site) ET `patates_on` (réglage de la base).

struct PronoGroupRef: Codable, Hashable {
    let id: String
    let name: String
    let emoji: String
    let color: String?
    /// Photo du groupe (lien signé quand le serveur l'a signé ; un chemin brut est ignoré par l'écran).
    var photo: String?
}

struct PronoEventRef: Codable, Hashable {
    let id: String
    let title: String
    var startsAt: String?
}

/// Terrain des patates : le groupe ou l'événement du prono (un sac par personne et par terrain).
/// (PronoTerrain, avec nom et emoji, est la version des écrans de liste : PronosListView.swift.)
struct PronoTerrainRef: Codable, Hashable {
    /// « group » ou « event ».
    let kind: String
    let id: String

    var groupID: String? { kind == "group" ? id : nil }
    var eventID: String? { kind == "event" ? id : nil }
}

/// Couverture d'une carte de la liste : couleur, emoji et photo du groupe (nil pour un événement).
struct PronoCover: Codable, Hashable {
    let color: String?
    let emoji: String?
    var photo: String?
}

/// Le champ : total planté et nombre de planteurs (visibles avant le dévoilement) ; par réponse seulement après.
struct PronoField: Codable, Hashable {
    struct Share: Codable, Hashable {
        let optionId: String
        let total: Int
    }
    let total: Int
    let planters: Int
    var byOption: [Share]?
}

/// Mon sac sur un terrain. `season` seulement depuis prono_bag (pas dans la fiche).
struct PronoBag: Codable, Hashable {
    struct Season: Codable, Hashable {
        /// « 2026-11-01 ».
        var month: String?
        let harvestNet: Int
    }
    let balance: Int
    /// Prochaine remontée à 100 (lundi 0 h, heure de Suisse).
    var refillAt: String?
    var maxStake: Int?
    var season: Season?

    /// Plantable au plus sur un prono : 20, et jamais plus que le sac.
    var plantable: Int { max(0, min(maxStake ?? PronoPatates.maxStake, balance)) }
}

/// Une ligne de l'historique de MON sac (prono_bag_history : les miens seulement, 60 derniers).
struct PronoBagMove: Codable, Hashable, Identifiable {
    struct Ref: Codable, Hashable {
        let id: String
        /// nil si le prono a été masqué par la modération.
        var question: String?
    }
    let at: String
    let delta: Int
    /// start, refill, plant, unplant, refund, harvest.
    let reason: String
    var terrain: PronoTerrainRef?
    var prono: Ref?

    var id: String { "\(at)|\(reason)|\(delta)|\(prono?.id ?? "")" }
}

/// Classement de la saison (mois) d'un groupe : récolte nette, justesse. Jamais de classement au sac.
struct PronoSeason: Codable, Hashable {
    struct Row: Codable, Hashable, Identifiable {
        let user: PronoFace
        let harvestNet: Int
        let right: Int
        let played: Int
        let rank: Int
        /// Places gagnées (+) ou perdues (−) depuis la veille ; nil hors du mois en cours ou nouveau venu.
        var move: Int?
        var id: String { user.id }
    }
    let month: String
    let rows: [Row]
    var me: Row?
}

struct PronoAwardCategory: Codable, Hashable, Identifiable {
    let id: String
    let emoji: String
    let label: String
}

/// Modèle prêt (prono_templates) : jamais d'alcool, jamais d'argent.
struct PronoTemplate: Codable, Hashable, Identifiable {
    let id: String
    let kind: String
    let emoji: String
    let title: String
    let question: String
    var options: [String]?
    var line: Double?
    var award: String?
    var hint: String?
    /// Trophée : la liste fermée des catégories (toutes positives).
    var awards: [PronoAwardCategory]?
}

/// Contestation d'un résultat (12 h après le résultat), puis vote des joueurs (24 h).
struct PronoContest: Codable, Hashable {
    struct Reason: Codable, Hashable {
        let user: PronoFace
        let reason: String
        let at: String
    }
    var until: String?
    var open: Bool?
    var contested: Bool?
    var voteUntil: String?
    var voteOpen: Bool?
    var fair: Int?
    var unfair: Int?
    /// true : « c'est juste », false : « pas juste », nil : pas voté.
    var myVote: Bool?
    var canContest: Bool?
    var canVote: Bool?
    var reasons: [Reason]?
}

/// « Seuls 2 sur 8 l'avaient vu ».
struct PronoRarity: Codable, Hashable {
    let right: Int
    let of: Int
}

struct PronoReaction: Codable, Hashable, Identifiable {
    let emoji: String
    let count: Int
    let mine: Bool
    var id: String { emoji }
}

struct PronoOption: Codable, Hashable, Identifiable {
    let id: String
    let label: String
    let count: Int?
    let correct: Bool?
}

struct PronoAnswerRef: Codable, Hashable {
    let optionId: String?
    let number: Double?
    let text: String?
    let personId: String?
    let winner: Bool?
    /// Patates plantées (0 = sans patates).
    var stake: Int?
    /// Heure devinée (kind when).
    var answerAt: String?
    /// Récolte versée (nil avant le règlement ; 0 = au compost).
    var harvest: Int?
}

struct PronoShownAnswer: Codable, Hashable, Identifiable {
    let user: PronoFace
    let optionId: String?
    let number: Double?
    let text: String?
    let hidden: Bool?
    let person: PronoFace?
    let winner: Bool
    var stake: Int?
    var harvest: Int?
    var answerAt: String?

    var id: String { user.id }
}

struct PronoResult: Codable, Hashable {
    let optionId: String?
    let number: Double?
    let person: PronoFace?
    var at: String?
    /// Heure de l'événement (kind when, « C'est arrivé ! »).
    var time: String?
    /// L'organisateur a joué son propre prono.
    var byPlayer: Bool?
    /// Trophée : lauréat·e(s) avec leurs voix (`votes`).
    var people: [PronoFace]?
}

struct PronoLink: Codable, Hashable {
    let token: String?
    let path: String?
}

struct Prono: Codable, Identifiable, Hashable {
    let id: String
    let question: String
    let kind: String
    let points: Int
    let closesAt: String
    let reveal: String
    let state: String
    let revealed: Bool
    let createdAt: String
    let mine: Bool
    let locked: Bool
    let creator: PronoFace
    let group: PronoGroupRef?
    let event: PronoEventRef?
    let options: [PronoOption]
    let candidates: [PronoFace]?
    let myAnswer: PronoAnswerRef?
    let answered: [PronoFace]
    let players: Int
    let answers: [PronoShownAnswer]?
    let result: PronoResult?
    let winners: [PronoFace]?
    let canAnswer: Bool
    let canEdit: Bool
    let canMoveEnd: Bool
    let canResult: Bool
    let canCancel: Bool
    let link: PronoLink?

    // v2 (18.11) : toutes facultatives.
    /// Plus / Moins : la ligne (7,5).
    var line: Double?
    /// « Sans dépasser » (number, when).
    var notOver: Bool?
    /// « Comment on tranche ? »
    var rules: String?
    var template: String?
    /// Prono avec patates (seulement avec un groupe ou un événement).
    var patates: Bool?
    var award: String?
    var awardEmoji: String?
    var awardLabel: String?
    var terrain: PronoTerrainRef?
    var field: PronoField?
    /// Mon sac sur le terrain (nil si je ne joue pas ou sans patates).
    var bag: PronoBag?
    var settled: Bool?
    var cancelReason: String?
    var contest: PronoContest?
    var rarity: PronoRarity?
    var unanimous: Bool?
    var reactions: [PronoReaction]?
    /// Trophée : je me suis retiré·e de la liste.
    var optout: Bool?
    /// « C'est arrivé ! » (when, organisateur).
    var canHappen: Bool?
    /// Réglage de la base : patates allumées.
    var patatesOn: Bool?

    var closes: Date? { PronoFormat.date(closesAt) }

    /// Les options portent la réponse (choix, Oui / Non, Plus / Moins, majorité).
    var hasOptions: Bool { PronoKind.hasOptions(kind) }

    /// Forme (▲ ◆ ● ■ ⬢ ★) d'une option : sa place dans la liste.
    func shape(of option: String?) -> PronoShape {
        PronoShape.at(options.firstIndex { $0.id == option } ?? 0)
    }

    /// Réponse lisible (ma réponse, dévoilement).
    func label(option: String?, number: Double?, text: String?, person: PronoFace?, personId: String? = nil, at: String? = nil) -> String {
        switch kind {
        case "choice", "yesno", "overunder", "majority": return options.first { $0.id == option }?.label ?? "—"
        case "number": return number.map(PronoFormat.number) ?? "—"
        case "when": return at.map(PronoFormat.time) ?? "—"
        case "person", "award":
            let who = person ?? candidates?.first { $0.id == personId }
            return who?.label ?? "—"
        default: return text ?? "Réponse masquée"
        }
    }

    var resultLabel: String {
        guard let result else { return "" }
        switch kind {
        case "choice", "yesno", "overunder", "majority": return options.first { $0.id == result.optionId }?.label ?? ""
        case "number": return result.number.map(PronoFormat.number) ?? ""
        case "when": return result.time.map(PronoFormat.time) ?? ""
        case "person": return result.person?.label ?? ""
        case "award": return (result.people ?? []).map(\.label).joined(separator: " & ")
        default: return ""
        }
    }
}

struct PronoCard: Codable, Identifiable, Hashable {
    let id: String
    let question: String
    let kind: String
    let points: Int
    let closesAt: String
    let state: String
    let revealed: Bool
    let mine: Bool
    let creator: PronoFace
    let group: PronoGroupRef?
    let event: PronoEventRef?
    let answeredCount: Int
    let players: Int
    let faces: [PronoFace]
    let answered: Bool
    let won: Bool
    let winners: [PronoFace]?
    let winnersCount: Int?

    // v2 (18.11) : toutes facultatives.
    var patates: Bool?
    /// Total du champ (patates plantées par tout le monde).
    var fieldTotal: Int?
    var myStake: Int?
    var myHarvest: Int?
    var template: String?
    var award: String?
    var awardEmoji: String?
    var awardLabel: String?
    var line: Double?
    var settled: Bool?
    var cancelReason: String?
    /// Fin dans moins d'une heure.
    var closesSoon: Bool?
    /// Couverture du groupe (nil : événement ou personnes choisies).
    var cover: PronoCover?
    var patatesOn: Bool?
    /// Nombre de planteurs (si la base l'envoie dans la liste).
    var planters: Int?
    /// Pastilles de la carte (si la base les envoie dans la liste).
    var options: [PronoOption]?
    var candidates: [PronoFace]?

    var closes: Date? { PronoFormat.date(closesAt) }

    /// Onglets de « Mes pronos » : À jouer (ouverts pas joués), En attente (joués encore ouverts + fermés sans
    /// résultat), Terminés.
    var tab: PronoTab {
        switch state {
        case "open": return answered ? .waiting : .toPlay
        case "closed": return .waiting
        default: return .done
        }
    }

    /// À faire pour moi : résultat à donner, ou prono ouvert où je n'ai pas joué.
    var todo: Bool { (state == "closed" && mine) || (state == "open" && !answered) }
}

struct PronoBoard: Codable, Hashable {
    struct Row: Codable, Hashable, Identifiable {
        let user: PronoFace
        let points: Int
        let right: Int
        let played: Int
        var id: String { user.id }
    }
    let since: String?
    let manage: Bool
    let pronos: Int
    let rows: [Row]
}

enum PronoTab: String, CaseIterable, Identifiable {
    case toPlay, waiting, done
    var id: String { rawValue }
    var title: String {
        switch self {
        case .toPlay: return "À jouer"
        case .waiting: return "En attente"
        case .done: return "Terminés"
        }
    }
}

/// Fonctions du site lues par les Pronos (GET /api/features). Absent (ancien serveur) = éteint.
struct PronoFeatures: Decodable, Equatable {
    var patates = false

    init(patates: Bool = false) { self.patates = patates }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        patates = try values.decodeIfPresent(Bool.self, forKey: .patates) ?? false
    }

    private enum CodingKeys: String, CodingKey { case patates }
}

/// Types de pronos : libellé, symbole, réponse par option.
enum PronoKind {
    static let all = ["choice", "yesno", "overunder", "number", "when", "person", "majority", "award", "text"]

    static func label(_ kind: String) -> String {
        switch kind {
        case "choice": return "Choix"
        case "yesno": return "Oui / Non"
        case "overunder": return "Plus / Moins"
        case "number": return "Nombre"
        case "when": return "Heure"
        case "person": return "Une personne"
        case "majority": return "Devine la bande"
        case "award": return "Trophée"
        default: return "Réponse libre"
        }
    }

    /// SF Symbol du type (iOS 16).
    static func symbol(_ kind: String) -> String {
        switch kind {
        case "choice": return "diamond.fill"
        case "yesno": return "circle.lefthalf.filled"
        case "overunder": return "arrow.up.arrow.down"
        case "number": return "number"
        case "when": return "clock.fill"
        case "person": return "person.fill"
        case "majority": return "person.3.fill"
        case "award": return "trophy.fill"
        default: return "text.cursor"
        }
    }

    static func hasOptions(_ kind: String) -> Bool { ["choice", "yesno", "overunder", "majority"].contains(kind) }

    /// Trophée et réponse libre : jamais de patates.
    static func allowsPatates(_ kind: String) -> Bool { kind != "award" && kind != "text" }
}

/// Patates (monnaie fictive, gratuite, sans valeur). Le calcul fait foi en base (private.prono_split) ; ces aides ne
/// servent qu'à l'affichage (« 6 sur 10 » de ta part du champ, aperçu d'un dévoilement).
enum PronoPatates {
    static let maxStake = 20
    static let start = 100
    /// Rappel affiché sous chaque sac (conformité).
    static let noValue = "Les confettis n'ont aucune valeur : ils ne s'achètent pas, ne se vendent pas, ne s'échangent pas."
    static let refillNote = "Ton sac remonte à 100 🎊 chaque lundi."

    struct Entry: Hashable {
        let id: String
        let stake: Int
        let winner: Bool
    }

    struct Share: Equatable {
        let back: Int
        /// Rendues (annulé, unanimes, personne n'a vu juste, moins de 2 planteurs).
        let refund: Bool
    }

    /// Partage du champ (somme nulle) : récolte = planté × champ / planté des gagnants, arrondi vers le bas, reste au
    /// plus fort reste (ordre des réponses en cas d'égalité). Tout rendu si annulé, moins de 2 planteurs, personne ou
    /// tout le monde juste. Entrées dans l'ordre des réponses ; seules celles avec des patates comptent.
    static func split(_ entries: [Entry], cancelled: Bool = false) -> [String: Share] {
        let planted = entries.filter { $0.stake > 0 }
        let field = planted.reduce(0) { $0 + $1.stake }
        let won = planted.filter(\.winner).reduce(0) { $0 + $1.stake }
        var out: [String: Share] = [:]
        guard !planted.isEmpty else { return out }
        if cancelled || planted.count < 2 || won == 0 || won == field {
            for e in planted { out[e.id] = Share(back: e.stake, refund: true) }
            return out
        }
        let winners = planted.filter(\.winner)
        let rest = field - winners.reduce(0) { $0 + ($1.stake * field) / won }
        let order = winners.enumerated().sorted {
            let (a, b) = (($0.element.stake * field) % won, ($1.element.stake * field) % won)
            return a != b ? a > b : $0.offset < $1.offset
        }
        for (rank, item) in order.enumerated() {
            out[item.element.id] = Share(back: (item.element.stake * field) / won + (rank < rest ? 1 : 0), refund: false)
        }
        for e in planted where !e.winner { out[e.id] = Share(back: 0, refund: false) }
        return out
    }

    /// Ta part, en dixièmes (« 6 sur 10 ») : au moins 1 dès qu'on a une part, jamais plus de 10.
    static func tenths(part: Int, of whole: Int) -> Int {
        guard part > 0, whole > 0 else { return 0 }
        return min(10, max(1, Int((Double(part) * 10 / Double(whole)).rounded())))
    }
}

enum PronoFormat {
    static func date(_ iso: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: iso) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: iso)
    }

    private static func formatter(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich")
        f.dateFormat = format
        return f
    }

    /// « sam. 21.11 à 18:00 » (heure de Suisse).
    static func short(_ iso: String) -> String {
        guard let d = date(iso) else { return "" }
        return formatter("EEE d.MM 'à' HH:mm").string(from: d)
    }

    /// « 21:47 » (heure de Suisse) : réponse et résultat d'un prono « heure ».
    static func time(_ iso: String) -> String {
        guard let d = date(iso) else { return "—" }
        return formatter("HH:mm").string(from: d)
    }

    static func number(_ n: Double) -> String {
        n == n.rounded() ? String(Int(n)) : String(n).replacingOccurrences(of: ".", with: ",")
    }

    /// « 7,5 » : ligne d'un Plus / Moins.
    static func line(_ n: Double) -> String { number(n) }

    static func points(_ n: Int) -> String { n > 1 ? "\(n) points" : "\(n) point" }

    /// « 5 🎊 ».
    static func patates(_ n: Int) -> String { "\(n) 🎊" }

    /// « 120 🎊 sur la piste · 5 joueurs » (jamais de multiplicateur ni de « tu peux récolter »).
    static func field(total: Int, planters: Int) -> String {
        "\(total) 🎊 sur la piste · \(planters) \(planters > 1 ? "joueurs" : "joueur")"
    }

    /// Récolte d'un prono : « +18 🎊 », « 5 🎊 rendus », « 5 🎊 au balai », « 5 🎊 lancés » (pas encore réglé).
    /// Jamais de signe moins. `refunded` : prono annulé ou unanimes, personne n'a vu juste, moins de 2 planteurs.
    static func harvest(stake: Int, harvest: Int?, refunded: Bool = false) -> String {
        guard let harvest else { return stake > 0 ? "\(stake) 🎊 lancés" : "" }
        if refunded, harvest > 0 { return "\(harvest) 🎊 rendus" }
        if harvest > 0 { return "+\(harvest) 🎊" }
        return stake > 0 ? "\(stake) 🎊 au balai" : ""
    }

    /// Ligne de l'historique du sac. `compost` : prono réglé sans récolte (« Lancés · partis au balai »).
    static func move(_ m: PronoBagMove, compost: Bool = false) -> (title: String, amount: String) {
        let n = abs(m.delta)
        switch m.reason {
        case "start": return ("Sac de départ", "+\(n) 🎊")
        case "refill": return ("Remonté à 100 (lundi)", "+\(n) 🎊")
        case "plant": return (compost ? "Lancés · partis au balai" : "Lancés", "−\(n) 🎊")
        case "unplant": return ("Repris", "+\(n) 🎊")
        case "refund": return ("Rendus", "+\(n) 🎊")
        case "harvest": return ("Ramassés", "+\(n) 🎊")
        default: return ("Sac", "\(m.delta) 🎊")
        }
    }

    /// « novembre » depuis « 2026-11-01 ».
    static func month(_ day: String) -> String {
        guard let d = formatter("yyyy-MM-dd").date(from: String(day.prefix(10))) else { return "" }
        return formatter("LLLL").string(from: d)
    }

    /// « lundi à 0 h » : prochaine remontée du sac (au-delà d'une semaine : « lun. 24.11 »).
    static func refill(_ iso: String?) -> String {
        guard let iso, let d = date(iso), d.timeIntervalSinceNow > 7 * 86_400 else { return "lundi à 0 h" }
        return formatter("EEE d.MM").string(from: d)
    }

    /// Palier du compte à rebours.
    enum Tier: Equatable {
        /// Plus de 24 h : date calme (« Jusqu'à jeu. 19 h »).
        case later
        /// 1 à 24 h : « Dans 2 h 14 ».
        case today
        /// Moins d'1 h : minutes en ambre (« 12 min »).
        case soon
        /// Moins de 60 s : anneau qui se vide (« 0:48 »).
        case last
        case over
    }

    static func tier(until end: Date, now: Date = Date()) -> Tier {
        let left = end.timeIntervalSince(now)
        if left <= 0 { return .over }
        if left < 60 { return .last }
        if left < 3600 { return .soon }
        if left < 86_400 { return .today }
        return .later
    }

    /// Texte court du compte à rebours (puce des cartes).
    static func countdown(until end: Date, now: Date = Date()) -> String {
        let left = Int(end.timeIntervalSince(now).rounded(.up))
        switch tier(until: end, now: now) {
        case .over: return "Fermé"
        case .last: return "0:" + String(format: "%02d", left)
        case .soon: return "\(max(1, left / 60)) min"
        case .today: return "Dans \(left / 3600) h " + String(format: "%02d", (left % 3600) / 60)
        case .later:
            var cal = Calendar(identifier: .gregorian)
            cal.timeZone = TimeZone(identifier: "Europe/Zurich") ?? .current
            let round = cal.component(.minute, from: end) == 0
            return "Jusqu'à " + formatter(round ? "EEE H 'h'" : "EEE H 'h' mm").string(from: end)
        }
    }

    /// Grand compte à rebours de la fiche : [(« 2 », « j »), (« 04 », « h »), (« 12 », « min »)].
    static func countdownParts(until end: Date, now: Date = Date()) -> [(value: String, unit: String)] {
        let left = max(0, Int(end.timeIntervalSince(now)))
        let (d, h, m, s) = (left / 86_400, (left % 86_400) / 3600, (left % 3600) / 60, left % 60)
        if d > 0 { return [("\(d)", "j"), (String(format: "%02d", h), "h"), (String(format: "%02d", m), "min")] }
        if h > 0 { return [("\(h)", "h"), (String(format: "%02d", m), "min")] }
        return [("\(m)", "min"), (String(format: "%02d", s), "s")]
    }

    /// VoiceOver : « Fin dans 2 heures et 14 minutes ».
    static func countdownSpoken(until end: Date, now: Date = Date()) -> String {
        let left = max(0, Int(end.timeIntervalSince(now)))
        if left == 0 { return "Fermé" }
        let (d, h, m) = (left / 86_400, (left % 86_400) / 3600, (left % 3600) / 60)
        var parts: [String] = []
        if d > 0 { parts.append("\(d) jour\(d > 1 ? "s" : "")") }
        if h > 0 { parts.append("\(h) heure\(h > 1 ? "s" : "")") }
        if d == 0, m > 0 { parts.append("\(m) minute\(m > 1 ? "s" : "")") }
        if parts.isEmpty { return "Fin dans \(left) secondes" }
        return "Fin dans " + parts.joined(separator: " et ")
    }

    static func stateLine(state: String, closesAt: String, revealed: Bool) -> String {
        switch state {
        case "open": return "Fin \(short(closesAt))"
        case "closed": return revealed ? "Fermé · réponses dévoilées" : "Fermé · résultat attendu"
        case "done": return "Terminé"
        default: return "Annulé"
        }
    }

    static func place(group: PronoGroupRef?, event: PronoEventRef?, creator: PronoFace) -> String {
        if let group { return "\(group.emoji) \(group.name)" }
        if let event { return "📅 \(event.title)" }
        return "Proposé par \(creator.me == true ? "toi" : creator.name)"
    }
}

@MainActor
final class PronosStore: ObservableObject {
    /// Pronos à jouer + résultats à donner (pastille de Réglages › Autres apps › Pronos).
    @Published private(set) var badge = 0
    /// Fonctions du site (GET /api/features) : `features.patates`. Relu par `refreshFeatures()` à l'ouverture des Pronos.
    @Published private(set) var features = PronoFeatures()
    /// Modèles prêts (prono_templates), gardés le temps de la session.
    @Published private(set) var cachedTemplates: [PronoTemplate]?

    static let reactions = ["😂", "🔥", "🥔", "👀", "🤯", "👏"]

    private let api: PartyAPI
    private weak var web: WebStorage?
    private(set) lazy var moderation = ModerationStore(api: api, web: web)

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    /// Appel du relais ; la réponse de la base (« result ») décodée en T.
    func call<T: Decodable>(_ fn: String, _ args: [String: Any] = [:], as: T.Type = T.self) async throws -> T {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour jouer aux pronos.") }
        // Drapeau « patates » du site lu une fois, avant le premier écran (sinon les patates restaient cachées).
        if !featuresRead { await refreshFeatures() }
        let reply = try await api.pronosRPC(token: token, fn: fn, args: args)
        let result = reply["result"] ?? NSNull()
        let data = try JSONSerialization.data(withJSONObject: result, options: [.fragmentsAllowed])
        return try Self.decoder.decode(T.self, from: data)
    }

    /// Appel sans réponse utile (supprimer, remettre à zéro).
    func run(_ fn: String, _ args: [String: Any] = [:]) async throws {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour jouer aux pronos.") }
        _ = try await api.pronosRPC(token: token, fn: fn, args: args)
    }

    func refreshBadge() async {
        struct Badge: Decodable { let toPlay: Int; let toResult: Int }
        guard let b = try? await call("prono_badge", as: Badge.self) else { return }
        Motion.animate(Motion.snappy) { badge = b.toPlay + b.toResult }
    }

    // MARK: Patates et v2

    /// Lit `patates` dans GET /api/features (comme Zicou, Discussions, bar). Erreur réseau : l'état connu reste.
    func refreshFeatures() async {
        guard let f: PronoFeatures = try? await api.get("/api/features", query: [:]) else { return }
        featuresRead = true
        if f != features { features = f }
    }

    private var featuresRead = false

    /// Drapeau lu au moins une fois avant de demander un sac ou une saison.
    private func patatesAllowed() async -> Bool {
        if !featuresRead { await refreshFeatures() }
        return features.patates
    }

    /// Patates à l'écran : drapeau du site ET réglage de la base ET prono avec patates.
    func showsPatates(_ p: Prono) -> Bool { features.patates && p.patatesOn == true && p.patates == true }
    func showsPatates(_ c: PronoCard) -> Bool { features.patates && c.patatesOn == true && c.patates == true }

    private func terrain(_ groupID: String?, _ eventID: String?) -> [String: Any] {
        var args: [String: Any] = [:]
        if let groupID { args["group_id"] = groupID }
        if let eventID { args["event_id"] = eventID }
        return args
    }

    static let patatesClosed = "Les confettis ne sont pas ouverts ici."

    /// Mon sac sur un terrain (un groupe OU un événement). Patates éteintes (site ou base) : erreur patatesClosed.
    func bag(groupID: String? = nil, eventID: String? = nil) async throws -> PronoBag {
        guard await patatesAllowed(),
              let bag = try await call("prono_bag", terrain(groupID, eventID), as: PronoBag?.self) else {
            throw PartyAPIError.server(Self.patatesClosed)
        }
        return bag
    }

    /// MON historique (60 derniers mouvements) ; sans terrain : tous mes sacs. Jamais celui d'un autre.
    func bagHistory(groupID: String? = nil, eventID: String? = nil) async throws -> [PronoBagMove] {
        guard await patatesAllowed() else { return [] }
        return try await call("prono_bag_history", terrain(groupID, eventID), as: [PronoBagMove]?.self) ?? []
    }

    /// Saison d'un groupe ; `month` « 2026-11-01 » (heure de Suisse), nil = le mois en cours. Patates éteintes : erreur.
    func season(groupID: String, month: String? = nil) async throws -> PronoSeason {
        var args: [String: Any] = ["group_id": groupID]
        if let month { args["month"] = String(month.prefix(10)) }
        guard await patatesAllowed(), let season = try await call("prono_season", args, as: PronoSeason?.self) else {
            throw PartyAPIError.server(Self.patatesClosed)
        }
        return season
    }

    /// Contester un résultat (raison obligatoire, 3 à 140 caractères, filtrée par la base).
    func contest(id: String, reason: String) async throws -> Prono {
        try await call("prono_contest", ["id": id, "reason": reason.trimmingCharacters(in: .whitespacesAndNewlines)])
    }

    /// Vote des joueurs sur une contestation : `fair` true = « c'est juste ».
    func contestVote(id: String, fair: Bool) async throws -> Prono {
        try await call("prono_contest_vote", ["id": id, "fair": fair])
    }

    /// Réaction (PronosStore.reactions : 😂 🔥 🎊 👀 🤯 👏) : bascule.
    func react(id: String, emoji: String) async throws -> Prono {
        try await call("prono_react", ["id": id, "emoji": emoji])
    }

    /// Trophée : me retirer de la liste (`out` true) ou y revenir.
    func optout(id: String, out: Bool) async throws -> Prono {
        try await call("prono_optout", ["id": id, "out": out])
    }

    /// Modèles prêts (gardés en mémoire après la première lecture).
    func templates() async throws -> [PronoTemplate] {
        if let cachedTemplates { return cachedTemplates }
        let list = try await call("prono_templates", as: [PronoTemplate]?.self) ?? []
        cachedTemplates = list
        return list
    }

    static func message(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? "Ça n'a pas marché. Réessaie dans un instant."
    }
}

/// Où ouvrir les pronos depuis la page web (PartyNative.pronos) ou une notification.
enum PronoRoute: Identifiable, Equatable {
    case list(group: String?)
    case open(String)
    case create(group: String?, event: String?)

    var id: String {
        switch self {
        case .list(let g): return "list:\(g ?? "")"
        case .open(let id): return "open:\(id)"
        case .create(let g, let e): return "create:\(g ?? ""):\(e ?? "")"
        }
    }

    /// Message du pont : « open:<uuid> », « list », « list:<uuid> », « create », « create:group:<uuid> »,
    /// « create:event:<uuid> ». nil pour tout le reste (rien d'autre n'est accepté).
    static func parse(_ body: String) -> PronoRoute? {
        let parts = body.split(separator: ":", omittingEmptySubsequences: false).map(String.init)
        func uuid(_ s: String) -> String? { UUID(uuidString: s)?.uuidString.lowercased() }
        switch (parts.first, parts.count) {
        case ("open", 2): return uuid(parts[1]).map { .open($0) }
        case ("list", 1): return .list(group: nil)
        case ("list", 2): return uuid(parts[1]).map { .list(group: $0) }
        case ("create", 1): return .create(group: nil, event: nil)
        case ("create", 3):
            guard let id = uuid(parts[2]) else { return nil }
            if parts[1] == "group" { return .create(group: id, event: nil) }
            if parts[1] == "event" { return .create(group: nil, event: id) }
            return nil
        default: return nil
        }
    }

    /// Notification d'un prono : « /?tab=events&prono=<id> » (send-push, tapPath).
    static func requested(in url: URL) -> String? {
        guard let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems,
              items.first(where: { $0.name == "tab" })?.value == "events",
              let id = items.first(where: { $0.name == "prono" })?.value.flatMap(UUID.init(uuidString:)) else { return nil }
        return id.uuidString.lowercased()
    }
}
#endif
