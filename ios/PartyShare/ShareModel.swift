import Foundation

/// « Partager › Party » : le lien (ou le texte) partagé devient un titre Spotify ajouté à la file de la soirée,
/// avec la session de l'app (trousseau partagé). Même règles que l'app : prénom obligatoire, doublons refusés.
@MainActor
final class ShareModel: ObservableObject {
    enum Phase: Equatable {
        case loading
        /// Pas de session : l'app n'a jamais rejoint de soirée sur ce téléphone, ou le code a changé.
        case needsApp
        case choose([SpotifyTrack])
        case added(String)
        case failed(String)
    }

    @Published private(set) var phase: Phase = .loading
    @Published private(set) var adding: String?
    @Published var name = ""

    private var api: PartyAPI?
    private var jar: SnapshotCookieJar?

    func start(shared: String) async {
        let query = SharedLink.query(from: shared)
        guard let snapshot = SharedSession.load() else {
            phase = .needsApp
            return
        }
        let jar = SnapshotCookieJar(snapshot)
        let api = PartyAPI(base: snapshot.base, jar: jar)
        self.jar = jar
        self.api = api
        name = snapshot.name
        guard !query.isEmpty else {
            phase = .failed("Rien à ajouter dans ce partage.")
            return
        }
        do {
            let tracks = try await api.search(query)
            phase = tracks.isEmpty ? .failed("Aucun titre trouvé pour ce lien.") : .choose(tracks)
        } catch PartyAPIError.needsCode {
            phase = .needsApp
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func add(_ track: SpotifyTrack) async {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let api, let jar, !name.isEmpty, adding == nil else { return }
        adding = track.id
        defer { adding = nil }
        do {
            try await api.enqueue(trackID: track.id, guestID: jar.snapshot.guestID, name: name)
            if name != jar.snapshot.name {
                var snapshot = jar.snapshot
                snapshot.name = name
                SharedSession.save(snapshot)  // l'app le reprendra à sa prochaine ouverture
            }
            phase = .added(track.title)
        } catch PartyAPIError.needsCode {
            phase = .needsApp
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }
}
