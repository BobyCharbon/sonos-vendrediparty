import ActivityKit
import Foundation
import OSLog

/// Ce qu'il faut faire des Live Activities « Ton titre arrive » après une mise à jour de la file.
/// Décision pure (testée dans PartyTests) ; TrackActivities l'applique avec ActivityKit.
enum TrackActivityStep: Equatable {
    /// Démarrer pour mon prochain titre.
    case start(requestID: String, trackID: String, title: String, artist: String, arrival: Date, paused: Bool)
    /// Recaler l'heure de passage.
    case update(requestID: String, arrival: Date, paused: Bool)
    /// Le titre passe : « C'est ton titre ! », puis effacement.
    case playing(requestID: String)
    /// Titre retiré de la file, ou passé pendant que l'app était fermée.
    case end(requestID: String)

    /// running : activités en cours (demande, titre). Une seule suivie à la fois : mon prochain titre.
    static func plan(_ state: PartyState, receivedAt: Date, running: [(requestID: String, trackID: String)]) -> [TrackActivityStep] {
        let next = state.upcoming.first { $0.isMine && $0.rid != nil && $0.trackID != nil }
        let playingTrack = state.now?.trackID
        var steps: [TrackActivityStep] = []
        var followed = false
        for activity in running {
            if activity.trackID == playingTrack {
                steps.append(.playing(requestID: activity.requestID))
            } else if let next, activity.requestID == next.rid {
                followed = true
                steps.append(.update(requestID: activity.requestID, arrival: receivedAt.addingTimeInterval(next.eta ?? 0),
                                     paused: state.isPaused))
            } else {
                steps.append(.end(requestID: activity.requestID))
            }
        }
        if !followed, let next, let rid = next.rid, let trackID = next.trackID, playingTrack != trackID {
            steps.append(.start(requestID: rid, trackID: trackID, title: next.title, artist: next.artist,
                                arrival: receivedAt.addingTimeInterval(next.eta ?? 0), paused: state.isPaused))
        }
        return steps
    }
}

/// Applique le plan avec ActivityKit, à chaque mise à jour de la file (MusicStore.reload).
@MainActor
enum TrackActivities {
    private static let log = Logger(subsystem: "ch.bobycharbon.party", category: "live-activity")
    /// « C'est ton titre ! » reste affiché le temps du morceau (environ), puis s'efface.
    private static let playingStay: TimeInterval = 4 * 60

    static func sync(_ state: PartyState, receivedAt: Date) {
        guard #available(iOS 16.2, *), ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        // Seules les activités visibles comptent : une activité balayée par l'utilisateur ou terminée par iOS reste
        // listée (état « dismissed » / « ended ») ; la croire suivie empêchait d'en recréer une.
        let all = Activity<TrackActivityAttributes>.activities
        for gone in all where gone.activityState == .dismissed || gone.activityState == .ended {
            Task { await gone.end(nil, dismissalPolicy: .immediate) }
        }
        let activities = all.filter { $0.activityState == .active || $0.activityState == .stale }
        let running = activities.map { (requestID: $0.attributes.requestID, trackID: $0.attributes.trackID) }
        let byRequest = Dictionary(activities.map { ($0.attributes.requestID, $0) }, uniquingKeysWith: { first, _ in first })

        for step in TrackActivityStep.plan(state, receivedAt: receivedAt, running: running) {
            switch step {
            case .start(let rid, let trackID, let title, let artist, let arrival, let paused):
                let attributes = TrackActivityAttributes(requestID: rid, addedAt: Date(), trackID: trackID, title: title, artist: artist)
                do {
                    _ = try Activity.request(attributes: attributes, content: content(arrival: arrival, playing: false, paused: paused))
                } catch {
                    log.error("Live Activity refusée : \(error.localizedDescription, privacy: .public)")
                }
            case .update(let rid, let arrival, let paused):
                guard let activity = byRequest[rid] else { continue }
                Task { await activity.update(content(arrival: arrival, playing: false, paused: paused)) }
            case .playing(let rid):
                guard let activity = byRequest[rid] else { continue }
                Task {
                    await activity.end(content(arrival: Date(), playing: true),
                                       dismissalPolicy: .after(Date().addingTimeInterval(playingStay)))
                }
            case .end(let rid):
                guard let activity = byRequest[rid] else { continue }
                Task { await activity.end(nil, dismissalPolicy: .immediate) }
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
    private static func content(arrival: Date, playing: Bool, paused: Bool = false) -> ActivityContent<TrackActivityAttributes.ContentState> {
        // Périmée à l'heure estimée : l'activité affiche « D'un instant à l'autre » au lieu d'un décompte à 0:00
        // (l'app fermée ne voit pas le titre démarrer ; l'heure est recalée à la prochaine ouverture).
        // En pause, rien ne s'écoule : pas de péremption, le temps restant est figé.
        ActivityContent(state: TrackActivityAttributes.ContentState(arrival: arrival, playing: playing, paused: paused,
                                                                     remaining: max(0, arrival.timeIntervalSinceNow)),
                        staleDate: playing || paused ? nil : arrival)
    }
}
