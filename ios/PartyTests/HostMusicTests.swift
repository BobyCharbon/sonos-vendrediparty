import Foundation
import Testing
@testable import Party

/// « Gérer la soirée » natif : décodage de la vraie réponse du serveur et règles de la file (poignée « réorganiser »).
struct HostMusicTests {
    /// Réponse réelle de GET /api/admin/state (générée par le serveur de test : file de snap(), une demande de Léa).
    static let adminStateJSON = ##"{"feedback_new": 0, "guest_pin": "0537", "guest_url": "https://party.bobycharbon.ch/", "active": true, "room_uid": "RINCON_X", "room_name": "Salon", "mode": "next", "started_at": 1793204286.588437, "spotify_configured": false, "requests": [{"id": "rq1", "track_id": "bbbbbbbbbbbbbbbbbbbbbb", "title": "Trois", "artist": "A", "image": "", "guest_id": "guest-1234567", "guest_name": "Léa", "added_at": 1800000000, "status": "queued", "ip": "", "duration_ms": 0}], "guests": [{"guest_id": "guest-1234567", "name": "Léa", "joined_at": 1800000000, "total": 1, "queued": 1, "via": ["music"], "active_at": 1800000000, "ban": null, "last_seen": 0}], "bans": [], "messages": [], "top_playlists": [{"id": "spotify:playlist:37i9dQZF1DX05r4Oy3Ln97", "title": "Soirée"}], "source": "sonos", "spotify_transfer_issues": [], "spotify_legacy_pending": 0, "spotify_account": null, "admin_notify": {"messages": true, "games": false, "feedback": true}, "games": [], "event": null, "sonos": {"queue_editable": true, "device": "", "state": "PLAYING", "from_queue": true, "now": {"title": "En cours", "artist": "A", "art": "", "position": "", "duration": "", "by": null, "track_id": "cccccccccccccccccccccc"}, "upcoming": [{"title": "Un", "artist": "A", "art": "", "track_id": "aaaaaaaaaaaaaaaaaaaaaa", "by": null, "rid": null, "eta": null, "service": null}, {"title": "Deux", "artist": "A", "art": "", "track_id": null, "by": null, "rid": null, "eta": null, "service": null}, {"title": "Trois", "artist": "A", "art": "", "track_id": "bbbbbbbbbbbbbbbbbbbbbb", "by": "Léa", "rid": null, "eta": null, "service": null}], "upcoming_total": 3, "volume": null}, "queue": [{"pos": 5, "key": "aaaaaaaaaaaaaaaaaaaaaa", "title": "Un", "artist": "A", "art": "", "by": null, "eta": null, "service": null}, {"pos": 6, "key": "Deux|A", "title": "Deux", "artist": "A", "art": "", "by": null, "eta": null, "service": null}, {"pos": 7, "key": "bbbbbbbbbbbbbbbbbbbbbb", "title": "Trois", "artist": "A", "art": "", "by": "Léa", "eta": null, "service": null}]}"##

    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("La réponse du serveur est décodée : soirée, lecture, file, demandes, invités, playlists")
    func decodesRealAdminState() throws {
        let state: AdminState = try decode(Self.adminStateJSON)
        #expect(state.active && state.source == "sonos" && state.roomName == "Salon" && state.mode == "next")
        #expect(state.guestPin.count == 4 && state.queueEditable && state.hasSpeakers)
        #expect(state.sonos?.isPlaying == true && state.sonos?.now.title == "En cours")
        #expect(state.queue.map(\.pos) == [5, 6, 7] && state.queue[2].by == "Léa" && state.queue[1].key == "Deux|A")
        #expect(state.requests.first?.guestName == "Léa" && state.requests.first?.status == "queued")
        #expect(state.guests.first?.name == "Léa" && state.guests.first?.ban == nil)
        #expect(state.topPlaylists.first?.isSpotify == true && state.warning == nil)
    }

    @Test("Réduire la file : seules les demandes des invités restent, à leur place")
    func collapsedQueueKeepsRequests() throws {
        let state: AdminState = try decode(Self.adminStateJSON)
        #expect(QueueOrder.visible(state.queue, showPlaylist: false).map(\.title) == ["Trois"])
        #expect(QueueOrder.visible(state.queue, showPlaylist: true).count == 3)
    }

    @Test("Poignée : l'index suit le doigt, borné à la liste ; la position visée est celle du titre remplacé")
    func dragTargets() throws {
        let state: AdminState = try decode(Self.adminStateJSON)
        #expect(QueueOrder.index(from: 2, translation: -140, rowHeight: 68, count: 3) == 0)
        #expect(QueueOrder.index(from: 0, translation: 30, rowHeight: 68, count: 3) == 0)
        #expect(QueueOrder.index(from: 0, translation: 40, rowHeight: 68, count: 3) == 1)
        #expect(QueueOrder.index(from: 1, translation: 900, rowHeight: 68, count: 3) == 2)
        #expect(QueueOrder.targetPosition(in: state.queue, from: 2, to: 0) == 5)
        #expect(QueueOrder.targetPosition(in: state.queue, from: 0, to: 2) == 7)
        #expect(QueueOrder.targetPosition(in: state.queue, from: 1, to: 1) == nil)
        #expect(QueueOrder.moving(state.queue, from: 2, to: 0).map(\.title) == ["Trois", "Un", "Deux"])
    }

    @Test("Soirée extérieure : file non modifiable, avertissement si rien ne joue")
    func spotifyParty() throws {
        let json = Self.adminStateJSON.replacingOccurrences(of: #""source": "sonos""#, with: #""source": "spotify""#)
            .replacingOccurrences(of: #""state": "PLAYING""#, with: #""state": "STOPPED""#)
        let state: AdminState = try decode(json)
        #expect(!state.queueEditable && !state.hasSpeakers && state.warning?.contains("Rien ne joue") == true)
    }

    @Test("Code choisi par l'hôte : 4 chiffres exactement")
    func guestPin() {
        #expect(GuestPin.isValid("0420") && !GuestPin.isValid("042") && !GuestPin.isValid("04a0") && !GuestPin.isValid("٠١٢٣"))
    }

    @Test("Doublon refusé par le serveur : message gardé pour la confirmation")
    func duplicateMessage() {
        #expect(PartyAPIError.duplicate("Déjà dans la file").errorDescription == "Déjà dans la file")
    }
}
