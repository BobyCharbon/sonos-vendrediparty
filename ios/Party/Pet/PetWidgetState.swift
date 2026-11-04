import Foundation

/// Zicou tel que la page l'a reçu du serveur (/api/pet/me, /api/pet/act : champ « pet »), réduit à ce que montrent
/// les widgets et la Live Activity de l'éclosion. Partagé par l'app (qui l'enregistre) et PartyWidgets (qui le dessine).
///
/// Le nom vient du serveur, qui le filtre à chaque changement (app/pet_store.py, action « rename » :
/// moderation.require_clean) ; sans nom lisible, on montre « Zicou ». Aucun autre texte de joueur n'est gardé.
struct PetWidgetState: Codable, Equatable {
    struct Gauges: Codable, Equatable {
        var food: Double
        var joy: Double
        var energy: Double
        var care: Double

        var lowest: Double { min(food, joy, energy, care) }
        var all: [Double] { [food, joy, energy, care] }
    }

    var name: String
    /// egg, baby, teen, adult, dead
    var stage: String
    /// star, classic, wild
    var variant: String
    /// egg, happy, party, hungry, tired, sad, sick, sleep, ghost (app/pet.py, emotion)
    var emotion: String
    var asleep: Bool
    var sick: Bool
    var gauges: Gauges
    /// Série 🔥 en cours (jours).
    var streak: Int
    /// Cadeau du jour (coffre) pas encore ouvert aujourd'hui.
    var chestReady: Bool
    /// Œuf : moment de l'éclosion (pondu + 3 min).
    var hatchAt: Date?
    /// Sans soins, moment où il s'envolerait (serveur : projections) ; nil s'il n'est pas en danger.
    var diesAt: Date?
    /// Moment de la lecture (les jauges valent `gauges` à cet instant).
    var at: Date

    static let defaultName = "Zicou"
    static let nameMax = 20

    var isEgg: Bool { stage == "egg" }
    var isGone: Bool { stage == "dead" }
}

// MARK: Lecture de la réponse du serveur

extension PetWidgetState {
    /// Champs de « pet » dans la réponse du serveur (app/pet.py view, app/pet_loop.py view sous « daily »).
    private struct Wire: Decodable {
        struct Gauges: Decodable {
            let food: Double?
            let joy: Double?
            let energy: Double?
            let care: Double?
        }

        struct Daily: Decodable {
            struct Chest: Decodable { let state: String? }
            struct Streak: Decodable { let count: Int? }
            let chest: Chest?
            let streak: Streak?
        }

        let name: String?
        let stage: String
        let variant: String?
        let emotion: String?
        let asleep: Bool?
        let sick: Bool?
        let gauges: Gauges?
        let streak: Int?
        let next_stage_in: Double?
        let dies_at: String?
        let daily: Daily?
    }

    static let stages: Set<String> = ["egg", "baby", "teen", "adult", "dead"]
    static let emotions: Set<String> = ["egg", "happy", "party", "hungry", "tired", "sad", "sick", "sleep", "ghost"]

    /// Corps « pet » (JSON) reçu à `receivedAt` ; nil s'il est illisible.
    static func decode(_ data: Data, receivedAt: Date) -> PetWidgetState? {
        guard let wire = try? JSONDecoder().decode(Wire.self, from: data), stages.contains(wire.stage) else { return nil }
        let g = wire.gauges
        let emotion = wire.emotion.flatMap { emotions.contains($0) ? $0 : nil } ?? (wire.stage == "egg" ? "egg" : "happy")
        let hatchAt = wire.stage == "egg" ? receivedAt.addingTimeInterval(max(0, wire.next_stage_in ?? 0)) : nil
        return PetWidgetState(
            name: displayName(wire.name), stage: wire.stage, variant: wire.variant ?? "classic", emotion: emotion,
            asleep: wire.asleep ?? false, sick: wire.sick ?? false,
            gauges: Gauges(food: clamp(g?.food), joy: clamp(g?.joy), energy: clamp(g?.energy), care: clamp(g?.care)),
            streak: max(0, wire.daily?.streak?.count ?? wire.streak ?? 0),
            chestReady: wire.daily?.chest?.state == "ready",
            hatchAt: hatchAt, diesAt: wire.dies_at.flatMap(parseDate), at: receivedAt)
    }

    /// Nom montré : celui du serveur (déjà filtré), sinon « Zicou ».
    static func displayName(_ raw: String?) -> String {
        let name = (raw ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty, name.count <= nameMax, !name.contains(where: \.isNewline) else { return defaultName }
        return name
    }

    private static func clamp(_ value: Double?) -> Double {
        min(PetRates.full, max(0, value ?? 0))
    }

    static func parseDate(_ raw: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: raw) { return date }
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: raw)
    }
}

// MARK: Texte (ton doux, jamais culpabilisant)

extension PetWidgetState {
    static func moodLine(_ emotion: String, name: String) -> String {
        switch emotion {
        case "egg": return "Quelque chose bouge dans l'œuf…"
        case "ghost": return "\(name) s'est envolé ✨"
        case "sleep": return "\(name) fait de beaux rêves"
        case "sick": return "\(name) aimerait un petit soin"
        case "hungry": return "\(name) a un petit creux"
        case "tired": return "\(name) bâille…"
        case "sad": return "\(name) aimerait jouer"
        case "party": return "\(name) est en mode fête !"
        default: return "\(name) va bien"
        }
    }

    /// Mot court (écran verrouillé, ligne de texte).
    static func moodWord(_ emotion: String) -> String {
        switch emotion {
        case "egg": return "éclosion"
        case "ghost": return "envolé"
        case "sleep": return "dort"
        case "sick": return "un soin ?"
        case "hungry": return "a faim"
        case "tired": return "fatigué"
        case "sad": return "veut jouer"
        case "party": return "en fête"
        default: return "va bien"
        }
    }
}
