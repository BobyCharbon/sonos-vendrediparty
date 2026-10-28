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

/// Extension « Partager › Party » : ce qui est recherché à partir du partage.
struct SharedLinkTests {
    @Test("Le lien est extrait du texte partagé par Spotify, YouTube…", arguments: [
        ("Écoute Angel Dust de Sara Landry https://open.spotify.com/track/4QNEi4zAOm0Fwf?si=x",
         "https://open.spotify.com/track/4QNEi4zAOm0Fwf?si=x"),
        ("  https://youtu.be/dQw4w9WgXcQ  ", "https://youtu.be/dQw4w9WgXcQ"),
        ("Daft Punk One More Time", "Daft Punk One More Time"),
    ])
    func extractsTheLink(shared: String, expected: String) {
        #expect(SharedLink.query(from: shared) == expected)
    }

    @Test("Un cookie enregistré dans le trousseau redonne le même cookie")
    func storedCookieRoundTrip() throws {
        let cookie = try #require(HTTPCookie(properties: [.name: "vp_guest", .value: "abc", .domain: "partytest.bobycharbon.ch",
                                                          .path: "/", .secure: "TRUE"]))
        let back = try #require(StoredCookie(cookie).cookie)
        #expect(back.name == "vp_guest" && back.value == "abc" && back.isSecure)
        #expect(PartyAPI.cookie(back, appliesTo: URL(string: "https://partytest.bobycharbon.ch/api/queue")!))
        #expect(!PartyAPI.cookie(back, appliesTo: URL(string: "https://party.bobycharbon.ch/api/queue")!))
    }
}


/// Mode de l'hôte pour la Musique : retenu d'une ouverture de l'app à l'autre.
@MainActor
struct HostModeTests {
    @Test("Le mode de l'hôte est retenu écran par écran, d'une ouverture à l'autre")
    func hostModeIsRemembered() {
        let base = URL(string: "https://partytest.bobycharbon.ch")!
        WebModel(start: base).setHostManages(true, screen: "music")
        WebModel(start: base).setHostManages(false, screen: "feedback")
        let reopened = WebModel(start: base)
        #expect(reopened.hostManages("music") && !reopened.hostManages("feedback"))
        reopened.setHostManages(false, screen: "music")
        #expect(!WebModel(start: base).hostManages("music"))
    }
}

/// « Ton avis » : réponses du serveur (app/feedback.py `mine`) et mots affichés.
struct FeedbackTests {
    @Test("Mes retours : état, réponse de l'hôte, terminé non lu")
    func decodesMyFeedback() throws {
        let list = try JSONDecoder().decode(FeedbackList.self, from: Data("""
        {"mine": [{"id": "f1", "at": 1793142000.5, "kind": "bug", "text": "Le quiz se fige", "status": "done",
                   "reply": "Corrigé, merci !", "unseen": true},
                  {"id": "f2", "at": 1793140000, "kind": "idea", "text": "Mode équipe", "status": "progress",
                   "reply": "", "unseen": false}]}
        """.utf8))
        #expect(list.mine.map(\.id) == ["f1", "f2"])
        #expect(list.mine[0].unseen && list.mine[0].reply == "Corrigé, merci !")
        #expect(FeedbackStatus.label(for: list.mine[0].status) == "✅ Terminé")
        #expect(FeedbackStatus.label(for: "progress") == "🔧 En cours de correction")
        #expect(FeedbackKind.label(for: list.mine[1].kind) == "💡 Idée")
    }

    @Test("Les mêmes limites que le serveur : 3 à 1000 caractères")
    func rules() {
        #expect(FeedbackRules.minimumLength == 3 && FeedbackRules.maximumLength == 1000)
        #expect(FeedbackKind.allCases.map(\.rawValue) == ["idea", "bug", "other"])
    }
}

/// QR code de l'hôte (app/main.py : /qr.svg et QR d'une partie).
struct PartyLinkTests {
    private let internalHost: (URL) -> Bool = { $0.host == "partytest.bobycharbon.ch" }

    @Test("QR de la soirée : le code est rejoint directement")
    func partyCode() {
        #expect(PartyLink.parse("https://partytest.bobycharbon.ch/?pin=4821", isInternal: internalHost) == .party(code: "4821"))
        #expect(PartyLink.parse(" 4821 ", isInternal: internalHost) == .party(code: "4821"))  // code seul
    }

    @Test("QR d'une partie : ouvert dans la page")
    func gameCode() {
        let url = URL(string: "https://partytest.bobycharbon.ch/?game=7731")!
        #expect(PartyLink.parse(url.absoluteString, isInternal: internalHost) == .page(url))
    }

    @Test("QR d'autre chose : refusé (site inconnu, http, texte)")
    func foreign() {
        #expect(PartyLink.parse("https://exemple.com/?pin=4821", isInternal: internalHost) == nil)
        #expect(PartyLink.parse("http://partytest.bobycharbon.ch/?pin=4821", isInternal: internalHost) == nil)
        #expect(PartyLink.parse("WIFI:S:maison;T:WPA;P:secret;;", isInternal: internalHost) == nil)
    }
}


/// Live Activity « Ton titre arrive » : quand la démarrer, la recaler, la terminer.
struct TrackActivityPlanTests {
    private func state(now: String?, upcoming: [(rid: String?, track: String, eta: Double)]) throws -> PartyState {
        let items = upcoming.map { #"{"title": "T-\#($0.track)", "artist": "A", "art": "", "track_id": "\#($0.track)", "by": "Léa", "rid": \#($0.rid.map { "\"\($0)\"" } ?? "null"), "eta": \#($0.eta)}"# }
        let json = #"{"active": true, "now": {"title": "N", "artist": "A", "art": "", "by": null, "track_id": \#(now.map { "\"\($0)\"" } ?? "null")}, "upcoming": [\#(items.joined(separator: ","))]}"#
        return try JSONDecoder().decode(PartyState.self, from: Data(json.utf8))
    }

    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)

    @Test("Mon titre ajouté : une activité démarre avec son heure de passage")
    func startsForMyNextTrack() throws {
        let steps = TrackActivityStep.plan(try state(now: "x", upcoming: [(nil, "a", 60), ("r1", "b", 300), ("r2", "c", 600)]),
                                           receivedAt: t0, running: [])
        #expect(steps == [.start(requestID: "r1", trackID: "b", title: "T-b", artist: "A", arrival: t0.addingTimeInterval(300), paused: false, ahead: 1)])
    }

    @Test("Déjà suivi : l'heure est recalée, pas de doublon")
    func updatesTheFollowedTrack() throws {
        let steps = TrackActivityStep.plan(try state(now: "x", upcoming: [("r1", "b", 120)]), receivedAt: t0,
                                           running: [(requestID: "r1", trackID: "b")])
        #expect(steps == [.update(requestID: "r1", arrival: t0.addingTimeInterval(120), paused: false, ahead: 0)])
    }

    @Test("Le titre passe : vert « Ton titre joue actuellement », seul (le suivant attend la fin)")
    func playingStaysAlone() throws {
        let steps = TrackActivityStep.plan(try state(now: "b", upcoming: [("r2", "c", 200)]), receivedAt: t0,
                                           running: [(requestID: "r1", trackID: "b")])
        #expect(steps == [.playing(requestID: "r1")])
    }

    @Test("Titre fini : l'activité disparaît, le titre suivant de la personne prend le relais")
    func finishedThenNext() throws {
        let steps = TrackActivityStep.plan(try state(now: "x", upcoming: [("r2", "c", 200)]), receivedAt: t0,
                                           running: [(requestID: "r1", trackID: "b")])
        #expect(steps == [.end(requestID: "r1"),
                          .start(requestID: "r2", trackID: "c", title: "T-c", artist: "A", arrival: t0.addingTimeInterval(200), paused: false, ahead: 0)])
    }

    @Test("Titre fini et plus rien en attente : l'activité disparaît, rien ne redémarre")
    func finishedAndNothingLeft() throws {
        let steps = TrackActivityStep.plan(try state(now: "x", upcoming: [(nil, "a", 60)]), receivedAt: t0,
                                           running: [(requestID: "r1", trackID: "b")])
        #expect(steps == [.end(requestID: "r1")])
    }

    @Test("Musique en pause : l'activité le sait (pas de décompte qui file)")
    func pausedIsPassedOn() throws {
        let paused = try JSONDecoder().decode(PartyState.self, from: Data(#"{"active": true, "state": "PAUSED_PLAYBACK", "upcoming": [{"title": "T", "artist": "A", "art": "", "track_id": "b", "by": null, "rid": "r1", "eta": 1200}]}"#.utf8))
        #expect(paused.isPaused)
        #expect(TrackActivityStep.plan(paused, receivedAt: t0, running: [(requestID: "r1", trackID: "b")])
                == [.update(requestID: "r1", arrival: t0.addingTimeInterval(1200), paused: true, ahead: 0)])
    }

    @Test("En pause, la file bouge : la place du titre suit (pas « le prochain » à tort)")
    func aheadFollowsTheQueueWhilePaused() throws {
        let moved = try JSONDecoder().decode(PartyState.self, from: Data(#"{"active": true, "state": "PAUSED_PLAYBACK", "upcoming": [{"title": "X", "artist": "A", "art": "", "track_id": "x", "by": null, "rid": null, "eta": 30}, {"title": "Y", "artist": "A", "art": "", "track_id": "y", "by": null, "rid": null, "eta": 200}, {"title": "T", "artist": "A", "art": "", "track_id": "b", "by": null, "rid": "r1", "eta": 400}]}"#.utf8))
        #expect(TrackActivityStep.plan(moved, receivedAt: t0, running: [(requestID: "r1", trackID: "b")])
                == [.update(requestID: "r1", arrival: t0.addingTimeInterval(400), paused: true, ahead: 2)])
    }

    @Test("Titre retiré de la file : l'activité s'arrête")
    func endsWhenRemoved() throws {
        let steps = TrackActivityStep.plan(try state(now: "x", upcoming: []), receivedAt: t0, running: [(requestID: "r1", trackID: "b")])
        #expect(steps == [.end(requestID: "r1")])
    }
}
