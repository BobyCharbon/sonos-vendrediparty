import Foundation
import Testing
@testable import Party

/// Réponses du serveur (app/main.py) décodées comme l'écran natif les utilise.
struct MusicModelsTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Soirée en cours : titre, file, mes titres, messages")
    func decodesAnActiveParty() throws {
        let state: PartyState = try decode("""
        {"active": true, "room": "Salon", "source": "sonos", "blocked": null, "name": "Léa",
         "messages": [{"id": "m1", "text": "Plus fort !", "at": 1.0, "reply": "OK 👍", "reply_at": 2.0}],
         "played": [{"title": "Avant", "artist": "X", "art": "", "track_id": "t0"}],
         "queue_editable": false, "device": "", "state": "PLAYING", "from_queue": true,
         "now": {"title": "Maintenant", "artist": "Y", "art": "/art?p=a", "position": "0:01:00",
                 "duration": "0:03:00", "by": "Tom", "track_id": "t1"},
         "upcoming": [{"title": "Le mien", "artist": "Z", "art": "", "track_id": "t2", "by": "Léa",
                       "rid": "r2", "eta": 120, "service": null},
                      {"title": "Le sien", "artist": "W", "art": "", "track_id": "t3", "by": "Tom",
                       "rid": null, "eta": 300, "service": null}],
         "upcoming_total": 7}
        """)
        #expect(state.active && state.room == "Salon" && state.name == "Léa")
        #expect(state.now?.title == "Maintenant" && state.now?.by == "Tom")
        #expect(state.upcoming.map(\.isMine) == [true, false])
        #expect(state.upcomingTotal == 7 && state.queueEditable == false)
        #expect(state.messages.first?.reply == "OK 👍" && state.played.count == 1)
    }

    @Test("Pas de soirée : seuls « active » et quelques champs sont envoyés")
    func decodesAClosedParty() throws {
        let state: PartyState = try decode(#"{"active": false}"#)
        #expect(!state.active && state.upcoming.isEmpty && state.queueEditable && state.upcomingTotal == 0)
    }

    @Test("Résultat de recherche Spotify")
    func decodesSearchResults() throws {
        let tracks: [SpotifyTrack] = try decode("""
        [{"id": "abcdefghijklmnopqrstuv", "title": "Titre", "artist": "A, B", "album": "Album",
          "image": "https://i.scdn.co/x", "duration_ms": 1000, "explicit": false}]
        """)
        #expect(tracks.first?.artist == "A, B")
    }

    @Test("Heure de passage, comme la page web", arguments: [
        (30.0, "dans moins d'1 min"), (299.0, "dans ~5 min"), (3540.0, "dans ~59 min"),
    ])
    func passageTimeIsWorded(eta: Double, expected: String) {
        let now = Date()
        #expect(PassageTime.text(eta: eta, receivedAt: now, now: now) == expected)
    }

    @Test("Au-delà d'une heure : l'heure de passage")
    func passageTimeBeyondAnHour() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Zurich")!
        let received = calendar.date(from: DateComponents(year: 2026, month: 10, day: 30, hour: 22, minute: 0))!
        #expect(PassageTime.text(eta: 5400, receivedAt: received, now: received, calendar: calendar) == "vers 23:30")
        #expect(PassageTime.text(eta: nil, receivedAt: received) == "")
    }
}

/// Barre d'onglets décrite par la page (app/static/native-tabs.js).
struct TabBarStateTests {
    private func state(active: String, native: [String]?) -> TabBarState? {
        var body: [String: Any] = [
            "hidden": false,
            "tabs": ["music", "games"].map { ["id": $0, "label": $0, "active": $0 == active, "badge": NSNull(), "soon": false] },
        ]
        if let native { body["native"] = native }
        return TabBarState(message: body)
    }

    @Test("L'onglet actif s'affiche en natif seulement si la page le permet")
    func nativeScreenFollowsThePage() {
        #expect(state(active: "music", native: ["music"])?.nativeScreen == "music")
        #expect(state(active: "games", native: ["music"])?.nativeScreen == nil)
        #expect(state(active: "music", native: [])?.nativeScreen == nil)       // l'hôte
        #expect(state(active: "music", native: nil)?.nativeScreen == nil)      // page plus ancienne
    }

    @Test("L'hôte est signalé par la page ; absent, on est invité")
    func hostFlag() {
        #expect(state(active: "music", native: ["music"])?.host == false)
        let host = TabBarState(message: ["hidden": false, "host": true, "native": ["music"],
                                         "tabs": [["id": "music", "label": "Musique", "active": true, "badge": NSNull(), "soon": false]]])
        #expect(host?.host == true && host?.nativeScreen == "music")
    }

        @Test("Un message qui n'est pas une description d'onglets est ignoré")
    func rejectsOtherMessages() {
        #expect(TabBarState(message: "bonjour") == nil)
        #expect(TabBarState(message: ["hidden": false]) == nil)
    }
}
