import ActivityKit
import Foundation
import OSLog

/// Ce qu'il faut faire de la Live Activity « Éclosion » après une lecture de Zicou. Décision pure (PartyTests),
/// appliquée par HatchActivities avec ActivityKit.
enum HatchActivityStep: Equatable {
    /// Œuf pondu : décompte jusqu'à l'éclosion.
    case start(name: String, laidAt: Date, hatchAt: Date)
    /// Éclos : « … est né ! », puis l'activité s'en va seule (dismissAfter).
    case hatched(id: String)
    /// Plus d'objet (réglage coupé, déconnexion, autre œuf) : retirée tout de suite.
    case end(id: String)

    struct Running: Equatable {
        let id: String
        let hatchAt: Date
        let hatched: Bool
    }

    /// Moins de 20 s avant l'éclosion : on ne démarre plus rien (la page la montre déjà).
    static let minimumLead: TimeInterval = 20
    /// Durée de l'œuf (app/pet.py EGG_SECONDS) : départ de la barre de progression.
    static let eggDuration: TimeInterval = 180
    /// « … est né ! » reste ce temps sur l'écran verrouillé, puis disparaît.
    static let dismissAfter: TimeInterval = 10 * 60
    private static let sameHatch: TimeInterval = 5

    static func plan(_ state: PetWidgetState?, now: Date, enabled: Bool, running: [Running]) -> [HatchActivityStep] {
        guard enabled, let state else { return running.map { .end(id: $0.id) } }
        let egg = state.isEgg ? state.hatchAt.flatMap { $0 > now ? $0 : nil } : nil
        var steps: [HatchActivityStep] = []
        var followed = false
        for activity in running {
            if let egg, abs(activity.hatchAt.timeIntervalSince(egg)) < sameHatch, !followed {
                followed = true          // le même œuf : rien à faire, le décompte avance seul
            } else if egg != nil {
                steps.append(.end(id: activity.id))       // un autre œuf (ou un doublon)
            } else if !activity.hatched {
                steps.append(.hatched(id: activity.id))   // éclos (ou l'heure est passée)
            }
        }
        if let egg, !followed, egg.timeIntervalSince(now) > minimumLead {
            steps.append(.start(name: state.name, laidAt: egg.addingTimeInterval(-eggDuration), hatchAt: egg))
        }
        return steps
    }
}

/// Applique le plan. App au premier plan : l'éclosion est aussi programmée (l'activité passe à « … est né ! » à
/// l'heure). App fermée : l'activité est périmée à l'heure de l'éclosion (staleDate) et affiche déjà « … est né ! » ;
/// elle est terminée à la prochaine ouverture, et iOS la retire de toute façon au bout de 8 h au plus.
@MainActor
enum HatchActivities {
    private static let log = Logger(subsystem: "ch.bobycharbon.party", category: "hatch-activity")
    private static var timer: Task<Void, Never>?

    static func sync(_ state: PetWidgetState?, now: Date = Date()) {
        guard #available(iOS 16.2, *) else { return }
        let allowed = LiveActivitySetting.isEnabled && ActivityAuthorizationInfo().areActivitiesEnabled
        let activities = Activity<HatchActivityAttributes>.activities.filter {
            $0.activityState == .active || $0.activityState == .stale
        }
        let byID = Dictionary(activities.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        let running = activities.map {
            HatchActivityStep.Running(id: $0.id, hatchAt: $0.content.state.hatchAt, hatched: $0.content.state.hatched)
        }
        for step in HatchActivityStep.plan(state, now: now, enabled: allowed, running: running) {
            switch step {
            case .start(let name, let laidAt, let hatchAt):
                do {
                    let content = ActivityContent(state: HatchActivityAttributes.ContentState(hatchAt: hatchAt, hatched: false),
                                                  staleDate: hatchAt)
                    _ = try Activity.request(attributes: HatchActivityAttributes(name: name, laidAt: laidAt), content: content)
                } catch {
                    log.error("Live Activity de l'éclosion refusée : \(error.localizedDescription, privacy: .public)")
                }
            case .hatched(let id):
                guard let activity = byID[id] else { continue }
                let final = ActivityContent(state: HatchActivityAttributes.ContentState(hatchAt: activity.content.state.hatchAt,
                                                                                         hatched: true), staleDate: nil)
                Task { await activity.end(final, dismissalPolicy: .after(Date().addingTimeInterval(HatchActivityStep.dismissAfter))) }
            case .end(let id):
                guard let activity = byID[id] else { continue }
                Task { await activity.end(nil, dismissalPolicy: .immediate) }
            }
        }
        scheduleHatch(state, now: now)
    }

    /// Réglage coupé ou déconnexion : plus aucune activité d'éclosion.
    static func endAll() {
        timer?.cancel()
        sync(nil)
    }

    /// App ouverte pendant l'éclosion : on passe à « … est né ! » à l'heure, sans attendre la page.
    private static func scheduleHatch(_ state: PetWidgetState?, now: Date) {
        timer?.cancel()
        guard let state, state.isEgg, let hatch = state.hatchAt, hatch > now else { return }
        timer = Task {
            try? await Task.sleep(for: .seconds(hatch.timeIntervalSince(now) + 1))
            guard !Task.isCancelled else { return }
            sync(state)
        }
    }

    #if DEBUG
    /// Simulateur : SIMCTL_CHILD_PARTY_DEBUG_HATCH=1 démarre une éclosion de démonstration (3 min), comme si la page
    /// venait de recevoir un œuf (widgets compris).
    static func startDemoIfAsked() {
        guard ProcessInfo.processInfo.environment["PARTY_DEBUG_HATCH"] != nil else { return }
        let now = Date()
        let egg = PetWidgetState(name: "Zicou", stage: "egg", variant: "classic", emotion: "egg", asleep: false, sick: false,
                                 gauges: .init(food: 80, joy: 80, energy: 90, care: 90), streak: 3, chestReady: true,
                                 hatchAt: now.addingTimeInterval(HatchActivityStep.eggDuration - 13), diesAt: nil, at: now)
        PetWidgetBridge.received(egg)
    }
    #endif
}
