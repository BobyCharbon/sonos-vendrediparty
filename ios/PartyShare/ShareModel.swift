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
        /// Lien mis de côté : l'app crée l'événement avec l'IA à sa prochaine ouverture.
        case eventReady
        /// App App Store : seulement « Créer l'événement » (pas de file Musique, l'onglet est caché ; Apple 2.3.1(a)).
        case eventOffer
    }

    /// App App Store (identifiant sans « .beta ») : l'extension ne sert qu'à créer un événement à partir d'un lien.
    static var isStoreApp: Bool { !(Bundle.main.bundleIdentifier ?? "").contains(".beta") }

    @Published private(set) var phase: Phase = .loading
    @Published private(set) var adding: String?
    @Published var name = ""
    /// Le lien partagé (page web), proposé aussi pour créer un événement avec l'IA.
    @Published private(set) var link: String?

    private var api: PartyAPI?
    private var jar: SnapshotCookieJar?

    func start(shared: String) async {
        let query = SharedLink.query(from: shared)
        link = query.hasPrefix("http") ? query : nil
        if Self.isStoreApp {
            phase = link == nil ? .failed("Partage le lien d'une page (invitation, lieu, billetterie) pour créer un événement.") : .eventOffer
            return
        }
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
            guard phase != .eventReady else { return }  // « Créer l'événement » touché pendant la recherche : on le garde
            phase = tracks.isEmpty ? .failed("Aucun titre trouvé pour ce lien.") : .choose(tracks)
        } catch PartyAPIError.needsCode {
            phase = .needsApp
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    /// « Créer un événement avec ce lien » : l'app le reprend à son ouverture et lance l'assistant IA avec.
    func prepareEvent() {
        guard let link else { return }
        SharedSession.savePendingEvent(link)
        phase = .eventReady
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
