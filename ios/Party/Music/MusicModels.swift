import Foundation

/// État de la soirée vu par un invité (GET /api/state, app/main.py `state` + `public_sonos`).
struct PartyState: Decodable, Equatable {
    let active: Bool
    let room: String?
    /// Message si l'invité est banni (il ne peut plus ajouter de titres).
    let blocked: String?
    /// Prénom connu du serveur (l'hôte a pu le modifier).
    let name: String?
    /// La musique est injoignable (l'enceinte ne répond pas).
    let error: String?
    let now: NowPlaying?
    let upcoming: [QueueItem]
    let upcomingTotal: Int
    let played: [PlayedItem]
    /// Mes messages à l'hôte et ses réponses.
    let messages: [HostMessage]
    /// false quand Spotify gère la file (mode extérieur) : on ne retire plus ses titres depuis l'app.
    let queueEditable: Bool
    /// PLAYING, PAUSED_PLAYBACK, STOPPED, TRANSITIONING (Sonos et Spotify, app/sonos.py · spotify_player.py).
    let playback: String?
    /// Invité sans compte : titres encore possibles ce soir (nil : compte, sans cette limite ; app/guest_gate.py).
    let guestTracks: GuestTracks?

    /// Musique en pause ou arrêtée : les heures de passage ne s'écoulent pas.
    var isPaused: Bool { playback == "PAUSED_PLAYBACK" || playback == "STOPPED" }

    enum CodingKeys: String, CodingKey {
        case active, room, blocked, name, error, now, upcoming, played, messages
        case upcomingTotal = "upcoming_total"
        case queueEditable = "queue_editable"
        case playback = "state"
        case guestTracks = "guest_tracks"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        active = try c.decode(Bool.self, forKey: .active)
        room = try c.decodeIfPresent(String.self, forKey: .room)
        blocked = try c.decodeIfPresent(String.self, forKey: .blocked)
        name = try c.decodeIfPresent(String.self, forKey: .name)
        error = try c.decodeIfPresent(String.self, forKey: .error)
        now = try c.decodeIfPresent(NowPlaying.self, forKey: .now)
        upcoming = try c.decodeIfPresent([QueueItem].self, forKey: .upcoming) ?? []
        upcomingTotal = try c.decodeIfPresent(Int.self, forKey: .upcomingTotal) ?? upcoming.count
        played = try c.decodeIfPresent([PlayedItem].self, forKey: .played) ?? []
        messages = try c.decodeIfPresent([HostMessage].self, forKey: .messages) ?? []
        queueEditable = try c.decodeIfPresent(Bool.self, forKey: .queueEditable) ?? true
        playback = try c.decodeIfPresent(String.self, forKey: .playback)
        guestTracks = try c.decodeIfPresent(GuestTracks.self, forKey: .guestTracks)
    }
}

/// Titres proposés en invité ce soir, au plus `limit` (réglé par l'admin ; 0 = compte requis pour proposer).
struct GuestTracks: Decodable, Equatable {
    let used: Int
    let limit: Int
    let left: Int

    /// Texte affiché au-dessus de la recherche (la musique reste accessible sans compte).
    var text: String {
        let titles = { (n: Int) in "\(n) titre\(n > 1 ? "s" : "")" }
        if left > 0 {
            return "En invité : encore \(titles(left)) à proposer ce soir. Crée ton compte dans Réglages (juste ton numéro) pour en proposer plus."
        }
        let start = limit == 0 ? "Proposer des titres demande un compte ce soir."
            : "Tu as proposé tes \(titles(limit)) de la soirée en invité."
        return start + " Crée ton compte (juste ton numéro) pour en proposer d'autres."
    }

    /// Limite atteinte (ou compte requis ce soir) : la recherche disparaît, le bouton « Créer mon compte » la remplace.
    var needsAccount: Bool { left <= 0 }
}

struct HostMessage: Decodable, Equatable, Identifiable {
    let id: String
    let text: String
    let reply: String?
}

struct NowPlaying: Decodable, Equatable {
    let title: String
    let artist: String
    let art: String
    /// Prénom de l'invité qui l'a demandé.
    let by: String?
    let trackID: String?

    enum CodingKeys: String, CodingKey {
        case title, artist, art, by
        case trackID = "track_id"
    }

    var isEmpty: Bool { title.isEmpty && artist.isEmpty }
}

struct QueueItem: Decodable, Equatable, Identifiable {
    let title: String
    let artist: String
    let art: String
    let trackID: String?
    let by: String?
    /// Identifiant de MA demande (je peux la retirer) ; nil pour les titres des autres.
    let rid: String?
    /// Secondes avant le passage, au moment de la réponse du serveur.
    let eta: Double?

    enum CodingKeys: String, CodingKey {
        case title, artist, art, by, rid, eta
        case trackID = "track_id"
    }

    var id: String { rid ?? "\(trackID ?? title)-\(artist)" }
    var isMine: Bool { rid != nil }
}

struct PlayedItem: Decodable, Equatable, Identifiable {
    let title: String
    let artist: String
    let art: String
    let trackID: String?

    enum CodingKeys: String, CodingKey {
        case title, artist, art
        case trackID = "track_id"
    }

    var id: String { "\(trackID ?? title)-\(artist)" }
}

/// Résultat de recherche Spotify (GET /api/search, app/spotify.py `_track`).
struct SpotifyTrack: Decodable, Equatable, Identifiable {
    let id: String
    let title: String
    let artist: String
    let album: String
    let image: String
}

/// Heure de passage, comme la page web (`etaText`) : « dans ~5 min », « vers 23:40 ».
enum PassageTime {
    static func text(eta: Double?, receivedAt: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        guard let eta else { return "" }
        let left = eta - now.timeIntervalSince(receivedAt)
        if left < 60 { return "dans moins d'1 min" }
        if left < 3600 { return "dans ~\(Int((left / 60).rounded())) min" }
        let at = now.addingTimeInterval(left)
        let parts = calendar.dateComponents([.hour, .minute], from: at)
        return String(format: "vers %02d:%02d", parts.hour ?? 0, parts.minute ?? 0)
    }
}

/// Réponse de POST /api/queue : bandeaux de Zicou éventuels (app/pet_reactions.py ; absents d'un ancien serveur).
struct EnqueueResult: Decodable {
    let zicou: [ZicouReaction]?
}

/// Petit bandeau « +5 🪙 pour Zicou » (kind reward) ou proposition d'adopter un Zicou, une seule fois (kind adopt).
struct ZicouReaction: Decodable, Equatable {
    let kind: String
    let text: String
}

/// GET /api/features : fonctions en bêta. Compagnon (Zicou) : allumé sur le site de test seulement. Discussions :
/// fermées en production tant qu'Apple ne les a pas vues (onglet, « Écrire », conversations natives masqués).
/// Absent (ancien serveur) = éteint.
struct PartyFeatures: Decodable, Equatable {
    let compagnon: Bool
    let discussions: Bool

    init(compagnon: Bool, discussions: Bool = false) {
        self.compagnon = compagnon
        self.discussions = discussions
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        compagnon = try values.decodeIfPresent(Bool.self, forKey: .compagnon) ?? false
        discussions = try values.decodeIfPresent(Bool.self, forKey: .discussions) ?? false
    }

    private enum CodingKeys: String, CodingKey { case compagnon, discussions }
}

/// Réglages › Compagnon : « Réactions de Zicou » (bandeaux dans l'app, jamais une notification).
struct ZicouReactionsPrefs: Decodable, Equatable {
    let enabled: Bool
}
