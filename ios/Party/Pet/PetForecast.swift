import Foundation

/// Rythme de vie du Compagnon, en points par heure : copie des constantes de app/pet.py (FOOD_RATE…), vérifiée par
/// tests/test_ios_pet_widget.py (un changement côté serveur sans cette copie fait échouer les tests Python).
enum PetRates {
    static let full = 100.0
    static let food = 2.4
    static let foodSleepFactor = 0.5
    static let joy = 1.8
    static let joySickFactor = 2.0
    static let joyStarvingFactor = 1.5
    static let energy = 3.0
    static let energyRegen = 11.0
    static let care = 1.5
    static let stageFactor: [String: Double] = ["baby": 1.2, "teen": 1.0, "adult": 0.9]
    static let low = 25.0
    static let partyLevel = 85.0
    static let stepHours = 1.0
}

/// Un instant de la chronologie d'un widget : Zicou tel qu'il sera à `date`, sans que le serveur ait à le dire.
struct PetMoment: Equatable {
    let date: Date
    let stage: String
    let emotion: String
    let gauges: PetWidgetState.Gauges
    let chestReady: Bool
    let streak: Int
    let hatchAt: Date?
    /// Barre « petit cadeau » : 0…1 (nil : pas de barre, œuf ou envolé), pleine ou non.
    var bar: Double? = nil
    var barFull = false
}

/// Chronologie des widgets : on fait vivre Zicou à partir de la dernière lecture (mêmes règles que app/pet.py,
/// advance/_step/emotion), sans minuteur serveur. Une entrée toutes les 30 min sur 12 h, plus l'éclosion et minuit
/// (le cadeau du jour redevient prêt).
enum PetForecast {
    static let horizon: TimeInterval = 12 * 3600
    static let spacing: TimeInterval = 30 * 60
    static let zurich = TimeZone(identifier: "Europe/Zurich") ?? .current

    static func moments(from state: PetWidgetState, now: Date) -> [PetMoment] {
        var dates = stride(from: 0, through: horizon, by: spacing).map { now.addingTimeInterval($0) }
        if let hatch = state.hatchAt, hatch > now, hatch < now.addingTimeInterval(horizon) { dates.append(hatch) }
        let midnight = nextMidnight(after: state.at)
        if midnight > now, midnight < now.addingTimeInterval(horizon) { dates.append(midnight) }
        if let full = state.barFullAt, full > now, full < now.addingTimeInterval(horizon) { dates.append(full) }
        return Set(dates).sorted().map { moment(of: state, at: $0) }
    }

    /// Zicou à `date`, avec sa barre « petit cadeau ».
    static func moment(of state: PetWidgetState, at date: Date) -> PetMoment {
        var m = lifeMoment(of: state, at: date)
        guard ["baby", "teen", "adult"].contains(m.stage), let full = state.barFullAt else { return m }
        m.barFull = date >= full
        if m.barFull {
            m.bar = 1
        } else if state.barRest == true {
            m.bar = 0
        } else if let from = state.barFrom, full > from {
            // Approximation linéaire (la pause de nuit est déjà dans full_at ; seul le rythme de l'aiguille en diffère).
            m.bar = min(0.99, max(0, date.timeIntervalSince(from) / full.timeIntervalSince(from)))
        }
        return m
    }

    /// Zicou à `date` (une date antérieure à la lecture donne la lecture elle-même).
    static func lifeMoment(of state: PetWidgetState, at date: Date) -> PetMoment {
        let chest = state.chestReady || date >= nextMidnight(after: state.at)
        var life = Life(stage: state.stage, asleep: state.asleep, sick: state.sick, gauges: state.gauges)
        var from = state.at
        if state.isEgg {
            guard let hatch = state.hatchAt, date >= hatch else {
                return PetMoment(date: date, stage: "egg", emotion: "egg", gauges: state.gauges, chestReady: chest,
                                 streak: state.streak, hatchAt: state.hatchAt)
            }
            life.stage = "baby"   // éclos : jauges de l'œuf, puis la vie commence
            from = max(from, hatch)
        }
        if state.isGone || (state.diesAt.map { date >= $0 } ?? false) {
            return PetMoment(date: date, stage: "dead", emotion: "ghost", gauges: life.gauges, chestReady: chest,
                             streak: state.streak, hatchAt: nil)
        }
        live(&life, hours: max(0, date.timeIntervalSince(from)) / 3600)
        // « En fête » après une soirée ou un cadeau : on ne connaît pas sa fin, on le garde seulement à la lecture.
        let party = state.emotion == "party" && date <= state.at
        return PetMoment(date: date, stage: life.stage, emotion: emotion(life, party: party), gauges: life.gauges,
                         chestReady: chest, streak: state.streak, hatchAt: nil)
    }

    struct Life {
        var stage: String
        var asleep: Bool
        var sick: Bool
        var gauges: PetWidgetState.Gauges
    }

    /// app/pet.py advance : pas d'une heure au plus.
    static func live(_ life: inout Life, hours total: Double) {
        var left = total
        while left > 1e-9 {
            let dt = min(PetRates.stepHours, left)
            step(&life, dt: dt)
            left -= dt
        }
    }

    /// app/pet.py _step.
    static func step(_ life: inout Life, dt: Double) {
        var g = life.gauges
        let k = PetRates.stageFactor[life.stage] ?? 1.0
        let foodRate = PetRates.food * k * (life.asleep ? PetRates.foodSleepFactor : 1.0)
        let starving = g.food <= 0 ? dt : max(0, dt - g.food / foodRate)
        g.food = clamp(g.food - foodRate * dt)
        let joyRate = PetRates.joy * (life.sick ? PetRates.joySickFactor : 1.0) * (starving > 0 ? PetRates.joyStarvingFactor : 1.0)
        g.joy = clamp(g.joy - joyRate * dt)
        g.care = clamp(g.care - PetRates.care * dt)
        if life.asleep {
            g.energy = clamp(g.energy + PetRates.energyRegen * dt)
            if g.energy >= PetRates.full { life.asleep = false }
        } else {
            g.energy = clamp(g.energy - PetRates.energy * k * dt)
            if g.energy <= 0 { life.asleep = true }
        }
        if g.care <= 0 { life.sick = true }
        life.gauges = g
    }

    /// app/pet.py emotion.
    static func emotion(_ life: Life, party: Bool) -> String {
        if life.stage == "egg" { return "egg" }
        if life.stage == "dead" { return "ghost" }
        if life.asleep { return "sleep" }
        if life.sick { return "sick" }
        let g = life.gauges
        if g.food < PetRates.low { return "hungry" }
        if g.energy < PetRates.low { return "tired" }
        if g.joy < PetRates.low { return "sad" }
        if party || g.lowest >= PetRates.partyLevel { return "party" }
        return "happy"
    }

    /// Minuit suivant à Zurich : le cadeau du jour redevient prêt (app/pet_loop.py, jour local).
    static func nextMidnight(after date: Date) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zurich
        let start = calendar.startOfDay(for: date)
        return calendar.date(byAdding: .day, value: 1, to: start) ?? date.addingTimeInterval(86_400)
    }

    private static func clamp(_ x: Double) -> Double { min(PetRates.full, max(0, x)) }
}
