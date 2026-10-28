import ActivityKit
import Foundation
import OSLog

/// Ce qu'il faut faire des Live Activities « Ton titre arrive » après une mise à jour de la file.
/// Décision pure (testée dans PartyTests) ; TrackActivities l'applique avec ActivityKit.
enum TrackActivityStep: Equatable {
    /// Démarrer pour mon prochain titre.
    case start(requestID: String, trackID: String, title: String, artist: String, arrival: Date, paused: Bool, ahead: Int)
    /// Recaler l'heure de passage.
    case update(requestID: String, arrival: Date, paused: Bool, ahead: Int)
    /// Le titre passe : « C'est ton titre ! », puis effacement.
    case playing(requestID: String)
    /// Titre retiré de la file, ou passé pendant que l'app était fermée.
    case end(requestID: String)

    /// running : activités en cours (demande, titre). Une seule suivie à la fois : mon prochain titre.
    static func plan(_ state: PartyState, receivedAt: Date, running: [(requestID: String, trackID: String)]) -> [TrackActivityStep] {
        let index = state.upcoming.firstIndex { $0.isMine && $0.rid != nil && $0.trackID != nil }
        let next = index.map { state.upcoming[$0] }
        let ahead = index ?? 0
        let playingTrack = state.now?.trackID
        var steps: [TrackActivityStep] = []
        var followed = false
        for activity in running {
            if activity.trackID == playingTrack {
                steps.append(.playing(requestID: activity.requestID))
            } else if let next, activity.requestID == next.rid {
                followed = true
                steps.append(.update(requestID: activity.requestID, arrival: receivedAt.addingTimeInterval(next.eta ?? 0),
                                     paused: state.isPaused, ahead: ahead))
            } else {
                steps.append(.end(requestID: activity.requestID))
            }
        }
        if !followed, let next, let rid = next.rid, let trackID = next.trackID, playingTrack != trackID {
            steps.append(.start(requestID: rid, trackID: trackID, title: next.title, artist: next.artist,
                                arrival: receivedAt.addingTimeInterval(next.eta ?? 0), paused: state.isPaused, ahead: ahead))
        }
        return steps
    }
}

/// Applique le plan avec ActivityKit, à chaque mise à jour de la file (MusicStore.reload). App fermée, c'est le
/// serveur qui tient l'activité à jour par push (app/live_activity.py) : chaque activité est demandée avec un jeton
/// de push, envoyé au serveur par `report` (branché par MusicStore).
@MainActor
enum TrackActivities {
    private static let log = Logger(subsystem: "ch.bobycharbon.party", category: "live-activity")
    /// requestID : jeton de cette activité (vide : plus suivie) ; nil : jeton de démarrage par push (vide : coupé).
    static var report: ((_ requestID: String?, _ token: String) -> Void)?
    /// Activités dont on écoute déjà le jeton (un seul flux par activité).
    private static var observed: Set<String> = []
    private static var observingStart = false
    /// Dernier jeton de démarrage reçu, et s'il a été retiré du serveur (réglage coupé).
    private static var startToken: String?
    private static var startWithdrawn = false
    /// « C'est ton titre ! » reste affiché le temps du morceau (environ), puis s'efface.
    private static let playingStay: TimeInterval = 4 * 60

    static func sync(_ state: PartyState, receivedAt: Date) {
        guard #available(iOS 16.2, *), ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        // Coupé dans Réglages › Notifications › Musique : aucune activité.
        guard LiveActivitySetting.isEnabled else { return endAll() }
        observeStartToken()
        if startWithdrawn, let startToken {  // réglage rallumé : le serveur peut de nouveau démarrer par push
            startWithdrawn = false
            report?(nil, startToken)
        }
        // Seules les activités visibles comptent : une activité balayée par l'utilisateur ou terminée par iOS reste
        // listée (état « dismissed » / « ended ») ; la croire suivie empêchait d'en recréer une.
        let all = Activity<TrackActivityAttributes>.activities
        for gone in all where gone.activityState == .dismissed || gone.activityState == .ended {
            Task { await gone.end(nil, dismissalPolicy: .immediate) }
        }
        let activities = all.filter { $0.activityState == .active || $0.activityState == .stale }
        activities.forEach(observe)  // activités démarrées par push, ou avant un redémarrage de l'app
        let running = activities.map { (requestID: $0.attributes.requestID, trackID: $0.attributes.trackID) }
        let byRequest = Dictionary(activities.map { ($0.attributes.requestID, $0) }, uniquingKeysWith: { first, _ in first })

        for step in TrackActivityStep.plan(state, receivedAt: receivedAt, running: running) {
            switch step {
            case .start(let rid, let trackID, let title, let artist, let arrival, let paused, let ahead):
                let attributes = TrackActivityAttributes(requestID: rid, addedAt: Date(), trackID: trackID, title: title, artist: artist)
                do {
                    let activity = try Activity.request(attributes: attributes,
                                                        content: content(arrival: arrival, playing: false, paused: paused, ahead: ahead),
                                                        pushType: .token)
                    observe(activity)
                } catch {
                    log.error("Live Activity refusée : \(error.localizedDescription, privacy: .public)")
                }
            case .update(let rid, let arrival, let paused, let ahead):
                guard let activity = byRequest[rid] else { continue }
                Task { await activity.update(content(arrival: arrival, playing: false, paused: paused, ahead: ahead)) }
            case .playing(let rid):
                guard let activity = byRequest[rid] else { continue }
                Task {
                    await activity.end(content(arrival: Date(), playing: true),
                                       dismissalPolicy: .after(Date().addingTimeInterval(playingStay)))
                }
            case .end(let rid):
                guard let activity = byRequest[rid] else { continue }
                report?(rid, "")
                Task { await activity.end(nil, dismissalPolicy: .immediate) }
            }
        }
    }

    /// Réglage coupé : les activités en cours disparaissent tout de suite, le serveur ne les suit plus et ne
    /// démarre plus rien par push.
    static func endAll() {
        guard #available(iOS 16.2, *) else { return }
        for activity in Activity<TrackActivityAttributes>.activities {
            report?(activity.attributes.requestID, "")
            Task { await activity.end(nil, dismissalPolicy: .immediate) }
        }
        if !startWithdrawn {  // une fois, pas à chaque mise à jour de la file
            startWithdrawn = true
            report?(nil, "")
        }
    }

    /// Jeton de push de l'activité, envoyé au serveur à chaque changement (Apple peut le renouveler).
    @available(iOS 16.2, *)
    private static func observe(_ activity: Activity<TrackActivityAttributes>) {
        let rid = activity.attributes.requestID
        guard !observed.contains(rid) else { return }
        observed.insert(rid)
        Task {
            for await data in activity.pushTokenUpdates {
                report?(rid, data.map { String(format: "%02x", $0) }.joined())
            }
        }
    }

    /// iOS 17.2+ : jeton de démarrage, pour qu'un titre ajouté app fermée démarre quand même sa Live Activity.
    private static func observeStartToken() {
        guard #available(iOS 17.2, *), !observingStart else { return }
        observingStart = true
        Task {
            for await data in Activity<TrackActivityAttributes>.pushToStartTokenUpdates {
                let token = data.map { String(format: "%02x", $0) }.joined()
                startToken = token
                if LiveActivitySetting.isEnabled { report?(nil, token) }
            }
        }
    }

    #if DEBUG
    /// Simulateur : SIMCTL_CHILD_PARTY_DEBUG_ACTIVITY=1 démarre une activité de démonstration (décompte de 5 min).
    static func startDemoIfAsked() {
        guard #available(iOS 16.2, *), ProcessInfo.processInfo.environment["PARTY_DEBUG_ACTIVITY"] != nil else { return }
        let attributes = TrackActivityAttributes(requestID: "demo", addedAt: Date().addingTimeInterval(-120), trackID: "demo",
                                                 title: "La vie qu'on mène", artist: "Ninho")
        _ = try? Activity.request(attributes: attributes, content: content(arrival: Date().addingTimeInterval(300), playing: false))
    }
    #endif

    @available(iOS 16.2, *)
    private static func content(arrival: Date, playing: Bool, paused: Bool = false,
                                ahead: Int = 0) -> ActivityContent<TrackActivityAttributes.ContentState> {
        // Périmée à l'heure estimée : l'activité affiche « D'un instant à l'autre » au lieu d'un décompte à 0:00
        // (l'app fermée ne voit pas le titre démarrer ; l'heure est recalée à la prochaine ouverture).
        // En pause, rien ne s'écoule : pas de péremption, le temps restant est figé.
        ActivityContent(state: TrackActivityAttributes.ContentState(arrival: arrival, playing: playing, paused: paused,
                                                                     remaining: max(0, arrival.timeIntervalSinceNow), ahead: ahead),
                        staleDate: playing || paused ? nil : arrival)
    }
}
