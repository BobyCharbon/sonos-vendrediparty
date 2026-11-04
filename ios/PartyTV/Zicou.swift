import Foundation

/// Un Zicou de la soirée (GET /api/tv/zicou) : l'aspect seulement. Le nom est le surnom du compte déjà modéré par le
/// serveur, ou rien : la télé n'affiche jamais un autre texte (ni le nom du Zicou, ni un prénom tapé par un joueur).
struct ZicouDancer: Equatable, Identifiable {
    enum Stage: String { case egg, baby, teen, adult }
    enum Variant: String { case star, classic, wild }

    let key: String
    let name: String?
    let stage: Stage
    let emotion: String
    let variant: Variant
    /// Accessoires portés, par emplacement (head, eyes, neck, back, facets…).
    let acc: [String: String]
    let shiny: Bool
    /// Place dans la partie regardée (nil : il ne joue pas).
    let pid: String?

    var id: String { key }

    static let emotions: Set<String> = ["egg", "happy", "party", "hungry", "tired", "sad", "sick", "sleep"]

    /// Lecture tolérante : une entrée illisible est ignorée (jamais de plantage pour un Zicou).
    init?(_ json: JSON) {
        guard let key = json["key"].string, !key.isEmpty, let stage = Stage(rawValue: json["stage"].string ?? "") else { return nil }
        self.key = key
        let name = (json["name"].string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        self.name = name.isEmpty ? nil : String(name.prefix(20))
        self.stage = stage
        let emotion = json["emotion"].string ?? "happy"
        self.emotion = stage == .egg ? "egg" : (Self.emotions.contains(emotion) ? emotion : "happy")
        variant = Variant(rawValue: json["variant"].string ?? "") ?? .classic
        if case .object(let slots) = json["acc"] {
            acc = slots.compactMapValues(\.string)
        } else {
            acc = [:]
        }
        shiny = json["shiny"].bool
        pid = json["pid"].string
    }

    static func list(_ json: JSON) -> [ZicouDancer] {
        var seen = Set<String>()
        return json["zicous"].array.compactMap(ZicouDancer.init).filter { seen.insert($0.key).inserted }
    }
}

/// Zicou en vedette (économie du 4.11.2026) : un présent a dépensé des pièces gagnées pour que son Zicou danse 30 s au
/// milieu de l'écran. Même aspect qu'un danseur (jamais de texte libre) ; `left` : secondes restantes à l'écran.
struct ZicouStar: Equatable {
    let dancer: ZicouDancer
    let left: Int
    let waiting: Int

    init?(_ json: JSON) {
        guard let dancer = ZicouDancer(json["star"]) else { return nil }
        self.dancer = dancer
        left = max(0, Int(json["star"]["left"].double ?? 0))
        waiting = max(0, Int(json["star_waiting"].double ?? 0))
    }

    /// Une même vedette (même passage) : la clé seule, le décompte n'en fait pas une nouvelle.
    static func == (a: ZicouStar, b: ZicouStar) -> Bool { a.dancer == b.dancer }
}

/// Décor du Salon de Party débloqué par la caisse commune du groupe (emoji et libellé fixés par le serveur).
struct SalonBadge: Equatable, Identifiable {
    let id: String
    let emoji: String
    let label: String

    static func list(_ json: JSON) -> [SalonBadge] {
        json["salon"].array.compactMap { item in
            guard let id = item["id"].string, let emoji = item["emoji"].string, !emoji.isEmpty else { return nil }
            return SalonBadge(id: id, emoji: String(emoji.prefix(4)), label: String((item["label"].string ?? "").prefix(60)))
        }
    }
}

/// La piste de danse : qui est visible (rotation), sur quel tempo, et qui fait sa figure de victoire.
enum ZicouFloor {
    /// Zicou visibles en même temps sous le coin musique (au-delà : rotation).
    static let maxVisible = 6
    /// Durée d'un groupe à l'écran avant le suivant.
    static let rotateEvery: TimeInterval = 10
    /// Durée de la figure de victoire.
    static let figureSeconds: TimeInterval = 2.6
    /// La Sonos ne donne pas le tempo : un pas régulier de musique de fête, sauf si la musique en annonce un.
    static let defaultBPM = 116.0

    /// Tempo à suivre : celui du titre en cours s'il est connu (tempo / bpm), sinon un pas régulier.
    static func beatsPerMinute(_ music: JSON) -> Double {
        for field in ["tempo", "bpm"] {
            if let bpm = music["now"][field].double, (60...200).contains(bpm) { return bpm }
        }
        return defaultBPM
    }

    /// Le groupe visible au tour `turn` : des pages de `limit`, à la suite. Les gagnants du moment sont toujours
    /// montrés (en tête), les autres places tournent parmi le reste.
    static func visible(_ all: [ZicouDancer], turn: Int, limit: Int = maxVisible, pinned: Set<String> = []) -> [ZicouDancer] {
        guard limit > 0 else { return [] }
        let stars = all.filter { pinned.contains($0.key) }.prefix(limit)
        let rest = all.filter { !pinned.contains($0.key) }
        let room = limit - stars.count
        guard room > 0, !rest.isEmpty else { return Array(stars) }
        if rest.count <= room { return Array(stars) + rest }
        let pages = Int((Double(rest.count) / Double(room)).rounded(.up))
        let start = ((turn % pages) + pages) % pages * room
        var page = Array(rest[start..<min(rest.count, start + room)])
        if page.count < room { page += rest.prefix(room - page.count) }   // dernière page complétée par le début
        return Array(stars) + page
    }

    /// Tour de rotation à un instant donné (même rythme pour toute la piste).
    static func turn(at date: Date) -> Int { Int(date.timeIntervalSinceReferenceDate / rotateEvery) }

    /// Gagnants de la partie affichée : manche gagnée (lignes « Gagnent ») ou champion de fin de partie.
    static func winnerNames(_ shown: JSON) -> [String] {
        if shown["phase"].string == "end", let champion = EndTV.champion(of: shown) { return [champion] }
        return Outcome.of(shown)?.lines(.win).map(\.name) ?? []
    }

    /// Identifie un moment de victoire : une nouvelle valeur relance la figure.
    static func victoryKey(_ shown: JSON) -> String? {
        let names = winnerNames(shown)
        guard !names.isEmpty else { return nil }
        if shown["phase"].string == "end" { return "end-\(shown["code"].string ?? "")-\(shown["type"].string ?? "")" }
        return Outcome.of(shown)?.key
    }

    /// Zicou des gagnants : par leur place dans la partie (pid), sinon par le surnom (même nom, accents et casse ignorés).
    static func winners(_ shown: JSON, among zicous: [ZicouDancer]) -> Set<String> {
        let names = winnerNames(shown).map(fold)
        guard !names.isEmpty else { return [] }
        let pids = Set(shown["players"].array.filter { names.contains(fold($0["name"].string ?? "")) }.compactMap { $0["pid"].string })
        return Set(zicous.filter { z in
            if let pid = z.pid { return pids.contains(pid) }
            return z.name.map { names.contains(fold($0)) } ?? false
        }.map(\.key))
    }

    /// « 6 Zicou dansent », « 1 Zicou danse ».
    static func headline(_ count: Int) -> String { count > 1 ? "\(count) Zicou dansent" : "\(count) Zicou danse" }

    private static func fold(_ s: String) -> String {
        s.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            .folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil)
    }
}
