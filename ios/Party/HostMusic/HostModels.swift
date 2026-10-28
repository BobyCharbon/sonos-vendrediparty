import Foundation

/// État de la soirée vu par l'hôte (GET /api/admin/state, app/main.py admin_state) : ce que montre la page admin
/// (app/static/music-admin.js), décodé pour l'écran natif « Gérer la soirée ».
struct AdminState: Decodable, Equatable {
    struct Playback: Decodable, Equatable {
        struct Now: Decodable, Equatable {
            let title: String
            let artist: String
            let art: String
            let by: String?
        }
        let state: String
        let fromQueue: Bool
        let device: String
        let now: Now
        let volume: Int?

        enum CodingKeys: String, CodingKey { case state, now, device, volume, fromQueue = "from_queue" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            state = try c.decodeIfPresent(String.self, forKey: .state) ?? "STOPPED"
            fromQueue = try c.decodeIfPresent(Bool.self, forKey: .fromQueue) ?? true
            device = try c.decodeIfPresent(String.self, forKey: .device) ?? ""
            now = try c.decode(Now.self, forKey: .now)
            volume = try c.decodeIfPresent(Int.self, forKey: .volume)
        }

        var isPlaying: Bool { state == "PLAYING" || state == "TRANSITIONING" }
    }

    struct QueueTrack: Decodable, Equatable, Identifiable {
        let pos: Int
        let key: String
        let title: String
        let artist: String
        let art: String
        let by: String?
        let eta: Double?
        let service: String?
        /// Position dans la file : unique, change quand la file bouge (l'écran se redessine alors).
        var id: String { "\(pos)|\(key)" }
        var isRequest: Bool { by != nil }
    }

    struct GuestRequest: Decodable, Equatable, Identifiable {
        let id: String
        let title: String
        let artist: String
        let image: String
        let guestName: String
        let addedAt: Double
        let status: String

        enum CodingKeys: String, CodingKey { case id, title, artist, image, status, guestName = "guest_name", addedAt = "added_at" }
    }

    struct Guest: Decodable, Equatable, Identifiable {
        struct Ban: Decodable, Equatable { let until: Double }
        let guestID: String
        let name: String
        let joinedAt: Double
        let total: Int
        let queued: Int
        let via: [String]
        let activeAt: Double
        let lastSeen: Double
        let ban: Ban?
        var id: String { guestID }

        enum CodingKeys: String, CodingKey {
            case name, total, queued, via, ban
            case guestID = "guest_id", joinedAt = "joined_at", activeAt = "active_at", lastSeen = "last_seen"
        }

        /// Invité « connecté » : s'est manifesté il y a moins de 30 s (même seuil que la page).
        func isOnline(now: Date = Date()) -> Bool { now.timeIntervalSince1970 - lastSeen < 30 }
    }

    struct TopPlaylist: Decodable, Equatable, Identifiable {
        let id: String
        let title: String
        var isSpotify: Bool { id.hasPrefix("spotify:") }
    }

    struct SpotifyAccount: Decodable, Equatable {
        let connected: Bool
        let name: String?
        let premium: Bool
    }

    struct LinkedEvent: Decodable, Equatable {
        let id: String
        let title: String
    }

    let active: Bool
    let source: String
    let roomName: String
    let mode: String
    let guestPin: String
    let guestURL: String
    let sonos: Playback?
    let sonosError: String?
    var queue: [QueueTrack]
    let requests: [GuestRequest]
    let guests: [Guest]
    let topPlaylists: [TopPlaylist]
    let spotifyAccount: SpotifyAccount?
    let event: LinkedEvent?

    enum CodingKeys: String, CodingKey {
        case active, source, mode, sonos, queue, requests, guests, event
        case roomName = "room_name", guestPin = "guest_pin", guestURL = "guest_url", sonosError = "sonos_error"
        case topPlaylists = "top_playlists", spotifyAccount = "spotify_account"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        active = try c.decodeIfPresent(Bool.self, forKey: .active) ?? false
        source = try c.decodeIfPresent(String.self, forKey: .source) ?? "sonos"
        roomName = try c.decodeIfPresent(String.self, forKey: .roomName) ?? ""
        mode = try c.decodeIfPresent(String.self, forKey: .mode) ?? "next"
        guestPin = try c.decodeIfPresent(String.self, forKey: .guestPin) ?? ""
        guestURL = try c.decodeIfPresent(String.self, forKey: .guestURL) ?? ""
        sonos = try c.decodeIfPresent(Playback.self, forKey: .sonos)
        sonosError = try c.decodeIfPresent(String.self, forKey: .sonosError)
        queue = try c.decodeIfPresent([QueueTrack].self, forKey: .queue) ?? []
        requests = try c.decodeIfPresent([GuestRequest].self, forKey: .requests) ?? []
        guests = try c.decodeIfPresent([Guest].self, forKey: .guests) ?? []
        topPlaylists = try c.decodeIfPresent([TopPlaylist].self, forKey: .topPlaylists) ?? []
        spotifyAccount = try c.decodeIfPresent(SpotifyAccount.self, forKey: .spotifyAccount)
        event = try c.decodeIfPresent(LinkedEvent.self, forKey: .event)
    }

    /// Soirée extérieure (Spotify) : l'ordre et les retraits se gèrent dans Spotify.
    var usesSpotify: Bool { source == "spotify" || source == "spotify_sonos" }
    var queueEditable: Bool { !usesSpotify }
    var hasSpeakers: Bool { source != "spotify" }

    /// Libellé sous « Soirée en cours », comme la page.
    var placeLabel: String {
        if source == "spotify_sonos" { return "🏠 Party maison · \(roomName) · Spotify" }
        if usesSpotify { return "🏕️ Party extérieur · Spotify" + (sonos.map { $0.device.isEmpty ? "" : " · \($0.device)" } ?? "") }
        return roomName
    }

    /// Avertissement en tête (rien ne joue, Sonos injoignable…), comme la page ; nil s'il n'y a rien à dire.
    var warning: String? {
        if let sonosError { return (usesSpotify ? "Spotify : " : "Sonos injoignable : ") + sonosError }
        if usesSpotify, sonos?.state == "STOPPED" { return "⚠️ Rien ne joue sur Spotify : lance une playlist sur ton téléphone." }
        if let sonos, !sonos.fromQueue {
            return "⚠️ La musique ne joue pas depuis la file Sonos (Spotify Connect / Jam ?). Lance une playlist depuis l'app Sonos."
        }
        return nil
    }

    var onlineGuests: [Guest] { guests.filter { $0.isOnline() } }
}

/// Modes d'insertion, textes de la page.
enum InsertMode: String, CaseIterable, Identifiable {
    case next, fair
    var id: String { rawValue }
    var label: String { self == .next ? "À la suite" : "Équitable" }
    var help: String {
        switch self {
        case .next: return "Chaque demande passe après celles déjà en attente (premier arrivé, premier servi), avant la suite de ta playlist."
        case .fair: return "Les demandes passent avant ta playlist, une par invité à tour de rôle : personne ne monopolise la file. L'activer réorganise aussi la file actuelle."
        }
    }
}

struct SonosRoom: Decodable, Equatable, Identifiable {
    let uid: String
    let name: String
    var id: String { uid }
}

struct Speaker: Decodable, Equatable, Identifiable {
    let uid: String
    let name: String
    let volume: Int
    let inGroup: Bool
    let coordinator: Bool
    var id: String { uid }

    enum CodingKeys: String, CodingKey { case uid, name, volume, coordinator, inGroup = "in_group" }
}

struct SonosPlaylist: Decodable, Equatable, Identifiable {
    let id: String
    let title: String
    let kind: String
}

struct EventOption: Decodable, Equatable, Identifiable {
    let id: String
    let title: String
    let startsAt: String
    enum CodingKeys: String, CodingKey { case id, title, startsAt = "starts_at" }
}

/// Résultat de recherche de l'hôte (titre Spotify, éventuellement trouvé depuis un lien Deezer, YouTube…).
struct HostSearchTrack: Decodable, Equatable, Identifiable {
    let id: String
    let title: String
    let artist: String
    let image: String
    let explicit: Bool
    let via: String?

    enum CodingKeys: String, CodingKey { case id, title, artist, image, explicit, via }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        title = try c.decode(String.self, forKey: .title)
        artist = try c.decode(String.self, forKey: .artist)
        image = try c.decodeIfPresent(String.self, forKey: .image) ?? ""
        explicit = try c.decodeIfPresent(Bool.self, forKey: .explicit) ?? false
        via = try c.decodeIfPresent(String.self, forKey: .via)
    }
}

/// File affichée et déplacement par la poignée « réorganiser ».
enum QueueOrder {
    /// « Réduire » cache seulement les titres de la playlist ; les demandes des invités restent à leur place.
    static func visible(_ queue: [AdminState.QueueTrack], showPlaylist: Bool) -> [AdminState.QueueTrack] {
        showPlaylist ? queue : queue.filter(\.isRequest)
    }

    /// Ligne lâchée à l'index `to` de la liste affichée : position Sonos visée (celle du titre qui occupait cette place).
    static func targetPosition(in shown: [AdminState.QueueTrack], from: Int, to: Int) -> Int? {
        guard shown.indices.contains(from), shown.indices.contains(to), from != to else { return nil }
        return shown[to].pos
    }

    /// Nouvel index pendant le glissement : décalage du doigt / hauteur d'une ligne, borné à la liste.
    static func index(from start: Int, translation: Double, rowHeight: Double, count: Int) -> Int {
        guard count > 0, rowHeight > 0 else { return start }
        return min(count - 1, max(0, start + Int((translation / rowHeight).rounded())))
    }

    /// Identité d'affichage d'un titre, qui ne change pas quand la file est renumérotée après un déplacement
    /// (la position Sonos, elle, change) : clé du titre et rang parmi ses doublons.
    static func stableIDs(_ list: [AdminState.QueueTrack]) -> [String] {
        var seen: [String: Int] = [:]
        return list.map { track in
            let n = seen[track.key, default: 0]
            seen[track.key] = n + 1
            return "\(track.key)#\(n)"
        }
    }

    /// Ordre affiché pendant le glissement (la ligne prise se place à l'index visé).
    static func moving(_ list: [AdminState.QueueTrack], from: Int, to: Int) -> [AdminState.QueueTrack] {
        guard list.indices.contains(from), list.indices.contains(to) else { return list }
        var copy = list
        let item = copy.remove(at: from)
        copy.insert(item, at: to)
        return copy
    }
}

/// Code d'accès des invités choisi par l'hôte : 4 chiffres.
enum GuestPin {
    static func isValid(_ text: String) -> Bool { text.count == 4 && text.allSatisfy { $0.isASCII && $0.isNumber } }
}
