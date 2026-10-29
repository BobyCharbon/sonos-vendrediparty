import Foundation

/// Appels de l'hôte (session vp_admin de la vue web), mêmes routes que la page admin (app/static/music-admin.js).
extension PartyAPI {
    func adminState() async throws -> AdminState { try await get("/api/admin/state", query: [:]) }

    func adminRooms() async throws -> [SonosRoom] { try await get("/api/admin/rooms", query: [:]) }

    func adminStart(roomUID: String, mode: String, source: String) async throws -> AdminState {
        try await postDecoding("/api/admin/start", body: ["room_uid": roomUID, "mode": mode, "source": source])
    }

    func adminStop() async throws -> AdminState { try await postDecoding("/api/admin/stop", body: [:]) }

    func adminPlayback(_ action: String) async throws -> AdminState {
        try await postDecoding("/api/admin/playback", body: ["action": action])
    }

    func adminSkip() async throws { try await post("/api/admin/skip", body: [:]) }

    func adminVolume(_ volume: Int) async throws { try await post("/api/admin/volume", body: ["volume": volume]) }

    func adminSearch(_ query: String) async throws -> [HostSearchTrack] {
        try await get("/api/admin/search", query: ["q": query])
    }

    /// where : next (juste après le titre en cours) | end (à la suite des demandes) ; force : doublon accepté.
    func adminAdd(trackID: String, where place: String, force: Bool) async throws -> AdminState {
        try await postDecoding("/api/admin/add", body: ["track_id": trackID, "where": place, "force": force])
    }

    /// action : next | up | down | play | remove | move (vers `to`). Réponse : état, et jeton d'annulation d'un retrait.
    func adminQueue(pos: Int, key: String, action: String, to: Int? = nil) async throws -> AdminChange {
        var body: [String: Any] = ["pos": pos, "key": key, "action": action]
        if let to { body["to"] = to }
        return try await postDecoding("/api/admin/queue", body: body)
    }

    func adminUndo(_ token: String) async throws -> AdminState { try await postDecoding("/api/admin/undo", body: ["token": token]) }

    func adminRemoveRequest(_ id: String) async throws -> AdminChange {
        try await postDecoding("/api/admin/remove", body: ["request_id": id])
    }

    func adminMode(_ mode: String) async throws -> AdminChange { try await postDecoding("/api/admin/mode", body: ["mode": mode]) }

    /// pin : nil = au hasard.
    func adminPin(_ pin: String?) async throws -> AdminState {
        try await postDecoding("/api/admin/pin", body: pin.map { ["pin": $0] } ?? [:])
    }

    func adminEventOptions(token: String) async throws -> [EventOption] {
        try await postDecoding("/api/admin/event/options", body: ["token": token])
    }

    func adminLinkEvent(id: String, title: String) async throws -> AdminState {
        try await postDecoding("/api/admin/event", body: ["event_id": id, "title": title])
    }

    func adminTopPlaylists(_ body: [String: Any]) async throws -> AdminState {
        try await postDecoding("/api/admin/playlists/top", body: body)
    }

    func adminLaunchPlaylist(_ id: String) async throws -> AdminState { try await postDecoding("/api/admin/playlist", body: ["id": id]) }

    func adminSonosPlaylists() async throws -> [SonosPlaylist] { try await get("/api/admin/playlists", query: [:]) }

    func adminSpeakers() async throws -> [Speaker] { try await get("/api/admin/speakers", query: [:]) }

    func adminGroupSpeaker(uid: String, join: Bool) async throws -> [Speaker] {
        try await postDecoding("/api/admin/speakers/group", body: ["uid": uid, "join": join])
    }

    func adminSpeakerVolume(uid: String, volume: Int) async throws {
        try await post("/api/admin/speakers/volume", body: ["uid": uid, "volume": volume])
    }

    func adminSpotifyLogout() async throws -> AdminState { try await postDecoding("/api/admin/spotify/logout", body: [:]) }

    /// Invités : rename (name), kick, ban (minutes, nil = sans limite), unban, purge (retire ses titres).
    func adminGuest(_ action: String, guestID: String, name: String? = nil, minutes: Int? = nil) async throws -> AdminChange {
        let paths = ["rename": "/api/admin/rename", "kick": "/api/admin/kick", "ban": "/api/admin/ban",
                     "unban": "/api/admin/unban", "purge": "/api/admin/purge"]
        guard let path = paths[action] else { throw PartyAPIError.server("Action inconnue") }
        var body: [String: Any] = ["guest_id": guestID]
        if let name { body["name"] = name }
        if action == "ban" { body["minutes"] = minutes.map { $0 as Any } ?? NSNull() }
        return try await postDecoding(path, body: body)
    }
}

/// Réponse d'une action qui renvoie l'état et, pour un retrait, de quoi l'annuler (« Annuler » remet à sa place).
struct AdminChange: Decodable {
    let state: AdminState
    let undo: String?
    /// Mode équitable : nombre de déplacements faits pour réorganiser la file.
    let reordered: Int?

    enum CodingKeys: String, CodingKey { case undo, reordered }

    init(from decoder: Decoder) throws {
        state = try AdminState(from: decoder)
        let c = try decoder.container(keyedBy: CodingKeys.self)
        undo = try c.decodeIfPresent(String.self, forKey: .undo)
        reordered = try c.decodeIfPresent(Int.self, forKey: .reordered)
    }
}
