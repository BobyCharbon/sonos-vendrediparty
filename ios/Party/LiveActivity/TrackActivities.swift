import ActivityKit
import Foundation

/// Ce qu'il faut faire des Live Activities « Ton titre arrive » après une mise à jour de la file.
/// Décision pure (testée dans PartyTests) ; TrackActivities l'applique avec ActivityKit.
enum TrackActivityStep: Equatable {
    /// Démarrer pour mon prochain titre.
    case start(requestID: String, trackID: String, title: String, artist: String, arrival: Date)
    /// Recaler l'heure de passage.
    case update(requestID: String, arrival: Date)
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
                steps.append(.update(requestID: activity.requestID, arrival: receivedAt.addingTimeInterval(next.eta ?? 0)))
            } else {
                steps.append(.end(requestID: activity.requestID))
            }
        }
        if !followed, let next, let rid = next.rid, let trackID = next.trackID, playingTrack != trackID {
            steps.append(.start(requestID: rid, trackID: trackID, title: next.title, artist: next.artist,
                                arrival: receivedAt.addingTimeInterval(next.eta ?? 0)))
        }
        return steps
    }
}

/// Applique le plan avec ActivityKit, à chaque mise à jour de la file (MusicStore.reload).
@MainActor
enum TrackActivities {
    /// « C'est ton titre ! » reste affiché le temps du morceau (environ), puis s'efface.
    private static let playingStay: TimeInterval = 4 * 60
    /// Une heure de passage dépassée de plus que ça : l'activité est périmée (iOS l'estompe).
    private static let staleAfter: TimeInterval = 10 * 60

    static func sync(_ state: PartyState, receivedAt: Date) {
        guard #available(iOS 16.2, *), ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        let activities = Activity<TrackActivityAttributes>.activities
        let running = activities.map { (requestID: $0.attributes.requestID, trackID: $0.attributes.trackID) }
        let byRequest = Dictionary(activities.map { ($0.attributes.requestID, $0) }, uniquingKeysWith: { first, _ in first })

        for step in TrackActivityStep.plan(state, receivedAt: receivedAt, running: running) {
            switch step {
            case .start(let rid, let trackID, let title, let artist, let arrival):
                let attributes = TrackActivityAttributes(requestID: rid, trackID: trackID, title: title, artist: artist)
                _ = try? Activity.request(attributes: attributes, content: content(arrival: arrival, playing: false))
            case .update(let rid, let arrival):
                guard let activity = byRequest[rid] else { continue }
                Task { await activity.update(content(arrival: arrival, playing: false)) }
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

    @available(iOS 16.2, *)
    private static func content(arrival: Date, playing: Bool) -> ActivityContent<TrackActivityAttributes.ContentState> {
        ActivityContent(state: TrackActivityAttributes.ContentState(arrival: arrival, playing: playing),
                        staleDate: playing ? nil : arrival.addingTimeInterval(staleAfter))
    }
}
