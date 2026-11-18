import XCTest
@testable import Party

/// Pronos (17.11) : messages du pont PartyNative.pronos, toucher d'une notification, lecture d'un prono tel que la base
/// le renvoie (prono_get), textes de l'écran. Pronos v2 (18.11) : JSON v2 (patates, contestation, réactions, saison,
/// sac, modèles), partage du champ affiché, vocabulaire (jamais d'argent ni de jeu d'argent).
@MainActor
final class PronosTests: XCTestCase {
    private let id = "11111111-2222-3333-4444-555555555555"

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try PronosStore.decoder.decode(T.self, from: Data(json.utf8))
    }

    func testTheBridgeAcceptsOnlyItsRoutes() {
        XCTAssertEqual(PronoRoute.parse("open:\(id.uppercased())"), .open(id))
        XCTAssertEqual(PronoRoute.parse("list"), .list(group: nil))
        XCTAssertEqual(PronoRoute.parse("list:\(id)"), .list(group: id))
        XCTAssertEqual(PronoRoute.parse("create"), .create(group: nil, event: nil))
        XCTAssertEqual(PronoRoute.parse("create:group:\(id)"), .create(group: id, event: nil))
        XCTAssertEqual(PronoRoute.parse("create:event:\(id)"), .create(group: nil, event: id))
        for bad in ["open:../admin", "open", "create:other:\(id)", "list:x", "board:\(id)", ""] {
            XCTAssertNil(PronoRoute.parse(bad), bad)
        }
    }

    func testANotificationOpensTheProno() {
        XCTAssertEqual(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=events&prono=\(id)")!), id)
        XCTAssertNil(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=events&prono=../admin")!))
        XCTAssertNil(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=chats&prono=\(id)")!))
    }

    func testAPronoFromTheDatabaseIsRead() throws {
        let json = """
        {"id": "\(id)", "question": "Qui gagne ?", "kind": "choice", "points": 3, "closes_at": "2026-11-18T19:00:00+00:00",
         "reveal": "result", "state": "done", "revealed": true, "created_at": "2026-11-17T19:00:00.123+00:00", "mine": false,
         "locked": true, "creator": {"id": "a", "name": "Léa", "avatar_url": null, "me": false, "photo": null},
         "group": {"id": "g", "name": "Les footeux", "emoji": "⚽", "color": "mint", "photo": null}, "event": null,
         "options": [{"id": "o1", "label": "Max", "count": 1, "correct": false}, {"id": "o2", "label": "Jo", "count": 2, "correct": true}],
         "candidates": null, "my_answer": {"option_id": "o2", "number": null, "text": null, "person_id": null, "winner": true},
         "answered": [{"id": "b", "name": "Marc", "avatar_url": "b/p.png", "me": true, "photo": "https://s/p"}], "players": 3,
         "answers": [{"user": {"id": "b", "name": "Marc", "avatar_url": null, "me": true}, "option_id": "o2", "number": null,
                      "text": null, "hidden": false, "person": null, "winner": true}],
         "result": {"option_id": "o2", "number": null, "person": null, "at": "2026-11-18T19:05:00+00:00"},
         "winners": [{"id": "b", "name": "Marc", "avatar_url": null, "me": true}],
         "can_answer": false, "can_edit": false, "can_move_end": false, "can_result": false, "can_cancel": false, "link": null}
        """
        let p = try decode(Prono.self, json)
        XCTAssertEqual(p.resultLabel, "Jo")
        XCTAssertEqual(p.myAnswer?.winner, true)
        XCTAssertEqual(p.winners?.first?.label, "Toi")
        XCTAssertEqual(p.answered.first?.photo, "https://s/p")
        XCTAssertEqual(p.label(option: "o1", number: nil, text: nil, person: nil), "Max")
        XCTAssertNotNil(p.closes)
        XCTAssertNotNil(PronoFormat.date(p.createdAt))
        // Un prono d'avant (sans les clés v2) reste lisible : rien des patates.
        XCTAssertNil(p.patates)
        XCTAssertNil(p.field)
        XCTAssertNil(p.bag)
    }

    // MARK: v2

    func testAV2PronoWithPatatesIsRead() throws {
        let json = """
        {"id": "\(id)", "question": "Qui gagne l'Eurovision samedi ?", "kind": "overunder", "points": 3,
         "closes_at": "2026-11-21T20:00:00+00:00", "reveal": "result", "state": "done", "revealed": true,
         "created_at": "2026-11-18T08:00:00+00:00", "mine": false, "locked": true,
         "creator": {"id": "a", "name": "Ludo Martin", "avatar_url": null, "me": false},
         "group": {"id": "g", "name": "Les Eurofans", "emoji": "🎤", "color": "sky", "photo": "https://s/g.jpg"},
         "event": null,
         "options": [{"id": "o1", "label": "Plus de 7,5", "count": 3, "correct": true},
                     {"id": "o2", "label": "Moins de 7,5", "count": 2, "correct": false}],
         "candidates": null,
         "my_answer": {"option_id": "o1", "number": null, "text": null, "person_id": null, "winner": true,
                       "stake": 10, "answer_at": null, "harvest": 18},
         "answered": [{"id": "b", "name": "Marc", "avatar_url": null, "me": true}], "players": 5,
         "answers": [{"user": {"id": "b", "name": "Marc", "avatar_url": null, "me": true}, "option_id": "o1", "number": null,
                      "text": null, "hidden": false, "person": null, "winner": true, "stake": 10, "harvest": 18, "answer_at": null}],
         "result": {"option_id": "o1", "number": null, "person": null, "at": "2026-11-21T22:00:00+00:00", "time": null,
                    "by_player": false, "people": null},
         "winners": [], "can_answer": false, "can_edit": false, "can_move_end": false, "can_result": false,
         "can_cancel": false, "link": null,
         "line": 7.5, "not_over": false, "rules": "Le score final du match.", "template": "buts", "patates": true,
         "award": null, "award_emoji": null, "award_label": null,
         "terrain": {"kind": "group", "id": "g"},
         "field": {"total": 42, "planters": 4, "by_option": [{"option_id": "o1", "total": 30}, {"option_id": "o2", "total": 12}]},
         "bag": {"balance": 86, "refill_at": "2026-11-23T23:00:00+00:00", "max_stake": 20},
         "settled": false, "cancel_reason": null,
         "contest": {"until": "2026-11-22T10:00:00+00:00", "open": true, "contested": false, "vote_until": null,
                     "vote_open": false, "fair": 0, "unfair": 0, "my_vote": null, "can_contest": true, "can_vote": false,
                     "reasons": []},
         "rarity": {"right": 2, "of": 5}, "unanimous": false,
         "reactions": [{"emoji": "🔥", "count": 3, "mine": true}, {"emoji": "🥔", "count": 1, "mine": false}],
         "optout": null, "can_happen": false, "patates_on": true}
        """
        let p = try decode(Prono.self, json)
        XCTAssertEqual(p.line, 7.5)
        XCTAssertEqual(PronoFormat.line(p.line ?? 0), "7,5")
        XCTAssertEqual(p.resultLabel, "Plus de 7,5")
        XCTAssertTrue(p.hasOptions)
        XCTAssertEqual(p.shape(of: "o2"), .diamond)
        XCTAssertEqual(p.terrain?.groupID, "g")
        XCTAssertNil(p.terrain?.eventID)
        XCTAssertEqual(p.group?.photo, "https://s/g.jpg")
        XCTAssertEqual(p.field?.total, 42)
        XCTAssertEqual(p.field?.byOption?.first?.total, 30)
        XCTAssertEqual(p.bag?.balance, 86)
        XCTAssertEqual(p.bag?.plantable, 20)
        XCTAssertEqual(p.myAnswer?.stake, 10)
        XCTAssertEqual(p.myAnswer?.harvest, 18)
        XCTAssertEqual(p.answers?.first?.harvest, 18)
        XCTAssertEqual(p.contest?.canContest, true)
        XCTAssertNil(p.contest?.myVote)
        XCTAssertEqual(p.rarity, PronoRarity(right: 2, of: 5))
        XCTAssertEqual(p.reactions?.first, PronoReaction(emoji: "🔥", count: 3, mine: true))
        XCTAssertEqual(p.patatesOn, true)
    }

    func testWhenAndAwardPronosAreRead() throws {
        let base = """
        "points": 1, "closes_at": "2026-11-21T20:00:00+00:00", "reveal": "close", "state": "done", "revealed": true,
        "created_at": "2026-11-18T08:00:00+00:00", "mine": true, "locked": true,
        "creator": {"id": "a", "name": "Léa", "avatar_url": null, "me": true}, "group": null,
        "event": {"id": "e", "title": "Raclette chez Léa", "starts_at": "2026-11-21T18:00:00+00:00"},
        "answered": [], "players": 6, "winners": [], "can_answer": false, "can_edit": false, "can_move_end": false,
        "can_result": false, "can_cancel": false, "link": null
        """
        let when = try decode(Prono.self, """
        {"id": "w", "question": "À quelle heure Max arrive ?", "kind": "when", "options": [], "candidates": null,
         "my_answer": {"option_id": null, "number": null, "text": null, "person_id": null, "winner": false,
                       "stake": 5, "answer_at": "2026-11-21T20:47:00+00:00", "harvest": 0},
         "result": {"option_id": null, "number": null, "person": null, "time": "2026-11-21T21:05:00+00:00"},
         "answers": [], "can_happen": true, "terrain": {"kind": "event", "id": "e"}, \(base)}
        """)
        XCTAssertEqual(when.resultLabel, "22:05")
        XCTAssertEqual(when.label(option: nil, number: nil, text: nil, person: nil, at: when.myAnswer?.answerAt), "21:47")
        XCTAssertEqual(when.terrain?.eventID, "e")
        XCTAssertEqual(when.event?.startsAt, "2026-11-21T18:00:00+00:00")
        XCTAssertEqual(when.canHappen, true)

        let award = try decode(Prono.self, """
        {"id": "t", "question": "Qui mérite le trophée « Ambianceur·euse » ?", "kind": "award", "options": [],
         "candidates": [{"id": "n", "name": "Nina Roy", "avatar_url": null, "me": false}],
         "my_answer": null, "answers": [], "award": "ambiance", "award_emoji": "🎉", "award_label": "Ambianceur·euse",
         "optout": false, "patates": false,
         "result": {"option_id": null, "number": null, "person": null,
                    "people": [{"id": "n", "name": "Nina Roy", "avatar_url": null, "me": false, "votes": 7}]}, \(base)}
        """)
        XCTAssertEqual(award.resultLabel, "Nina Roy")
        XCTAssertEqual(award.result?.people?.first?.votes, 7)
        XCTAssertEqual(award.awardEmoji, "🎉")
        XCTAssertEqual(award.optout, false)
        XCTAssertEqual(award.candidates?.first?.initials, "NR")
        XCTAssertFalse(PronoKind.allowsPatates("award"))
    }

    func testAV2CardIsSortedIntoItsTab() throws {
        func card(_ state: String, answered: Bool) throws -> PronoCard {
            try decode(PronoCard.self, """
            {"id": "c", "question": "Il restera du fromage ?", "kind": "yesno", "points": 1,
             "closes_at": "2026-11-18T20:00:00+00:00", "state": "\(state)", "revealed": false, "mine": false,
             "creator": {"id": "a", "name": "Léa", "avatar_url": null, "me": false}, "group": null, "event": null,
             "answered_count": 6, "players": 9, "faces": [], "answered": \(answered), "won": false,
             "winners": null, "winners_count": null, "patates": true, "field_total": 42, "my_stake": null,
             "my_harvest": null, "template": null, "award": null, "line": null, "settled": false, "cancel_reason": null,
             "closes_soon": true, "cover": {"color": "coral", "emoji": "🧀", "photo": null}, "patates_on": true}
            """)
        }
        let open = try card("open", answered: false)
        XCTAssertEqual(open.tab, .toPlay)
        XCTAssertEqual(open.fieldTotal, 42)
        XCTAssertEqual(open.cover?.emoji, "🧀")
        XCTAssertEqual(open.closesSoon, true)
        XCTAssertEqual(try card("open", answered: true).tab, .waiting)
        XCTAssertEqual(try card("closed", answered: true).tab, .waiting)
        XCTAssertEqual(try card("done", answered: true).tab, .done)
        XCTAssertEqual(try card("cancelled", answered: true).tab, .done)
        XCTAssertEqual(PronoTab.allCases.map(\.title), ["À jouer", "En attente", "Terminés"])
    }

    func testBagHistorySeasonAndTemplatesAreRead() throws {
        let bag = try decode(PronoBag.self, """
        {"balance": 12, "refill_at": "2026-11-23T23:00:00+00:00", "max_stake": 20,
         "season": {"month": "2026-11-01", "harvest_net": 14}}
        """)
        XCTAssertEqual(bag.plantable, 12)
        XCTAssertEqual(bag.season?.harvestNet, 14)
        XCTAssertEqual(PronoFormat.month(bag.season?.month ?? ""), "novembre")

        let moves = try decode([PronoBagMove].self, """
        [{"at": "2026-11-18T10:00:00+00:00", "delta": -5, "reason": "plant", "terrain": {"kind": "group", "id": "g"},
          "prono": {"id": "p", "question": "Qui gagne ?"}},
         {"at": "2026-11-17T23:00:00+00:00", "delta": 100, "reason": "start", "terrain": {"kind": "group", "id": "g"}, "prono": null},
         {"at": "2026-11-18T11:00:00+00:00", "delta": 18, "reason": "harvest", "terrain": {"kind": "event", "id": "e"},
          "prono": {"id": "q", "question": null}}]
        """)
        XCTAssertEqual(moves.count, 3)
        XCTAssertEqual(Set(moves.map(\.id)).count, 3)
        XCTAssertEqual(PronoFormat.move(moves[0]).amount, "−5 🎊")
        XCTAssertEqual(PronoFormat.move(moves[0], compost: true).title, "Lancés · partis au balai")
        XCTAssertEqual(PronoFormat.move(moves[1]).title, "Sac de départ")
        XCTAssertEqual(PronoFormat.move(moves[2]).title, "Ramassés")
        XCTAssertNil(moves[2].prono?.question)

        let season = try decode(PronoSeason.self, """
        {"month": "2026-11-01", "rows": [
          {"user": {"id": "a", "name": "Léa", "avatar_url": null, "me": false}, "harvest_net": 40, "right": 6, "played": 8, "rank": 1, "move": 2},
          {"user": {"id": "b", "name": "Marc", "avatar_url": null, "me": true}, "harvest_net": -5, "right": 2, "played": 7, "rank": 2, "move": null}],
         "me": {"user": {"id": "b", "name": "Marc", "avatar_url": null, "me": true}, "harvest_net": -5, "right": 2, "played": 7, "rank": 2, "move": null}}
        """)
        XCTAssertEqual(season.rows.first?.move, 2)
        XCTAssertEqual(season.me?.user.label, "Toi")
        XCTAssertNil(season.me?.move)

        let templates = try decode([PronoTemplate].self, """
        [{"id": "buts", "kind": "overunder", "emoji": "🥅", "title": "Plus ou moins de buts",
          "question": "Plus ou moins de 2,5 buts dans le match ?", "line": 2.5, "hint": "La ligne se termine par ,5."},
         {"id": "trophee", "kind": "award", "emoji": "🏆", "title": "Trophée de la soirée", "question": "Qui ?",
          "award": "ambiance", "hint": "Vote.", "awards": [{"id": "ambiance", "emoji": "🎉", "label": "Ambianceur·euse"}]},
         {"id": "match", "kind": "choice", "emoji": "⚽", "title": "Le match", "question": "Qui gagne ?",
          "options": ["Équipe A", "Match nul", "Équipe B"], "hint": "Écris le nom des deux équipes."}]
        """)
        XCTAssertEqual(templates[0].line, 2.5)
        XCTAssertEqual(templates[1].awards?.first?.label, "Ambianceur·euse")
        XCTAssertEqual(templates[2].options?.count, 3)

        // Patates éteintes en base : prono_bag / prono_season renvoient null.
        XCTAssertNil(try decode(PronoBag?.self, "null"))
        XCTAssertNil(try decode(PronoBag.self, #"{"balance": 3}"#).season?.month)
        XCTAssertEqual(try PronosStore.decoder.decode(PronoFeatures.self, from: Data(#"{"compagnon": true}"#.utf8)), PronoFeatures(patates: false))
        XCTAssertEqual(try PronosStore.decoder.decode(PronoFeatures.self, from: Data(#"{"patates": true}"#.utf8)).patates, true)
    }

    /// Partage du champ (comme private.prono_split) : somme nulle, arrondi vers le bas, reste au plus fort reste.
    func testTheFieldIsSharedLikeTheDatabase() {
        typealias E = PronoPatates.Entry
        // 120 dans le champ, gagnants 10 + 20 : 40 et 80.
        let a = PronoPatates.split([E(id: "a", stake: 10, winner: true), E(id: "b", stake: 20, winner: true),
                                    E(id: "c", stake: 50, winner: false), E(id: "d", stake: 40, winner: false)])
        XCTAssertEqual(a["a"], PronoPatates.Share(back: 40, refund: false))
        XCTAssertEqual(a["b"], PronoPatates.Share(back: 80, refund: false))
        XCTAssertEqual(a["c"]?.back, 0)
        // Reste : 3 × 3 = 9 + 1 perdant (1) = 10 ; gagnants 3, 3, 3 → 3 × 10 / 9 = 3,33 → 3 + 1 au premier.
        let r = PronoPatates.split([E(id: "x", stake: 3, winner: true), E(id: "y", stake: 3, winner: true),
                                    E(id: "z", stake: 3, winner: true), E(id: "l", stake: 1, winner: false)])
        XCTAssertEqual(r.values.reduce(0) { $0 + $1.back }, 10)
        XCTAssertEqual(r["x"]?.back, 4)
        XCTAssertEqual(r["y"]?.back, 3)
        // Unanimes, personne, un seul planteur, annulé : tout rendu.
        XCTAssertEqual(PronoPatates.split([E(id: "a", stake: 5, winner: true), E(id: "b", stake: 7, winner: true)])["b"], PronoPatates.Share(back: 7, refund: true))
        XCTAssertEqual(PronoPatates.split([E(id: "a", stake: 5, winner: false), E(id: "b", stake: 7, winner: false)])["a"], PronoPatates.Share(back: 5, refund: true))
        XCTAssertEqual(PronoPatates.split([E(id: "a", stake: 5, winner: true), E(id: "b", stake: 0, winner: false)])["a"], PronoPatates.Share(back: 5, refund: true))
        XCTAssertEqual(PronoPatates.split([E(id: "a", stake: 5, winner: true), E(id: "b", stake: 7, winner: false)], cancelled: true)["a"],
                       .init(back: 5, refund: true))
        XCTAssertNil(PronoPatates.split([E(id: "a", stake: 0, winner: true)])["a"])
        // « 6 sur 10 » : ta part du champ.
        XCTAssertEqual(PronoPatates.tenths(part: 18, of: 30), 6)
        XCTAssertEqual(PronoPatates.tenths(part: 1, of: 200), 1)
        XCTAssertEqual(PronoPatates.tenths(part: 0, of: 30), 0)
        XCTAssertEqual(PronoPatates.tenths(part: 30, of: 30), 10)
    }

    func testTexts() {
        XCTAssertEqual(PronoFormat.points(1), "1 point")
        XCTAssertEqual(PronoFormat.points(5), "5 points")
        XCTAssertEqual(PronoFormat.number(25), "25")
        XCTAssertEqual(PronoFormat.number(2.5), "2,5")
        XCTAssertEqual(PronoFormat.stateLine(state: "closed", closesAt: "", revealed: false), "Fermé · résultat attendu")
        XCTAssertEqual(PronoFormat.place(group: nil, event: PronoEventRef(id: "e", title: "Paintball"), creator: PronoFace(id: "a", name: "Léa")), "📅 Paintball")
        XCTAssertEqual(PronoFormat.field(total: 120, planters: 5), "120 🎊 sur la piste · 5 joueurs")
        XCTAssertEqual(PronoFormat.harvest(stake: 10, harvest: 18), "+18 🎊")
        XCTAssertEqual(PronoFormat.harvest(stake: 5, harvest: 0), "5 🎊 au balai")
        XCTAssertEqual(PronoFormat.harvest(stake: 5, harvest: 5, refunded: true), "5 🎊 rendus")
        XCTAssertEqual(PronoFormat.harvest(stake: 5, harvest: nil), "5 🎊 lancés")
        XCTAssertFalse(PronoFormat.harvest(stake: 5, harvest: 0).contains("-"))
        XCTAssertEqual(PronoPatates.noValue, "Les confettis n'ont aucune valeur : ils ne s'achètent pas, ne se vendent pas, ne s'échangent pas.")
        XCTAssertEqual(PronoPatates.refillNote, "Ton sac remonte à 100 🎊 chaque lundi.")
        XCTAssertEqual(PronoKind.label("overunder"), "Plus / Moins")
        XCTAssertEqual(PronoKind.label("majority"), "Devine la bande")
        XCTAssertEqual(PronoShape.at(0), .triangle)
        XCTAssertEqual(PronoShape.at(7), .diamond)
        XCTAssertEqual(PronoFace(id: "x", name: "").initials, "?")
    }

    func testCountdownTiers() {
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        XCTAssertEqual(PronoFormat.tier(until: now.addingTimeInterval(48), now: now), .last)
        XCTAssertEqual(PronoFormat.countdown(until: now.addingTimeInterval(48), now: now), "0:48")
        XCTAssertEqual(PronoFormat.tier(until: now.addingTimeInterval(12 * 60), now: now), .soon)
        XCTAssertEqual(PronoFormat.countdown(until: now.addingTimeInterval(12 * 60), now: now), "12 min")
        XCTAssertEqual(PronoFormat.countdown(until: now.addingTimeInterval(2 * 3600 + 14 * 60), now: now), "Dans 2 h 14")
        XCTAssertEqual(PronoFormat.tier(until: now.addingTimeInterval(3 * 86_400), now: now), .later)
        XCTAssertTrue(PronoFormat.countdown(until: now.addingTimeInterval(3 * 86_400), now: now).hasPrefix("Jusqu'à "))
        XCTAssertEqual(PronoFormat.countdown(until: now.addingTimeInterval(-1), now: now), "Fermé")
        let parts = PronoFormat.countdownParts(until: now.addingTimeInterval(2 * 86_400 + 4 * 3600 + 12 * 60), now: now)
        XCTAssertEqual(parts.map(\.value), ["2", "04", "12"])
        XCTAssertEqual(parts.map(\.unit), ["j", "h", "min"])
        XCTAssertEqual(PronoFormat.countdownSpoken(until: now.addingTimeInterval(2 * 3600 + 14 * 60), now: now),
                       "Fin dans 2 heures et 14 minutes")
    }

    /// Conformité 🔴 8 : aucun mot d'argent ni de jeu d'argent dans les textes des écrans Pronos (web : lib/terms ; ici
    /// les chaînes des fichiers Swift de ios/Party/Pronos, commentaires exclus).
    func testVocabularyHasNoMoneyOrGamblingWords() throws {
        let words = ["pari", "parier", "paris", "mise", "miser", "pot", "cagnotte", "cote", "cotes", "gain", "gains",
                     "jackpot", "balles", "franc", "francs", "chf", "euro", "euros",
                     "coin", "coins", "jeton", "jetons", "pièce", "pièces", "récolte", "compost"]
        let symbols = ["€", "💰", "🎰"]
        let folder = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Party/Pronos")
        let files = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "swift" }
        XCTAssertFalse(files.isEmpty)
        let literal = try NSRegularExpression(pattern: #""(?:[^"\\\n]|\\.)*""#)
        var found: [String] = []
        for file in files {
            for line in try String(contentsOf: file).components(separatedBy: "\n") {
                let code = line.trimmingCharacters(in: .whitespaces)
                if code.hasPrefix("//") { continue }
                let range = NSRange(line.startIndex..., in: line)
                for m in literal.matches(in: line, range: range) {
                    guard let r = Range(m.range, in: line) else { continue }
                    let text = String(line[r])
                    let tokens = text.lowercased().components(separatedBy: CharacterSet.letters.inverted)
                    for w in words where tokens.contains(w) { found.append("\(file.lastPathComponent): \(w) dans \(text)") }
                    for s in symbols where text.contains(s) { found.append("\(file.lastPathComponent): \(s) dans \(text)") }
                }
            }
        }
        XCTAssertEqual(found, [], "Vocabulaire des Pronos (confettis) : lancer, la piste, ramasser, au balai, ton sac, rendus")
        // Les textes fabriqués par le kit non plus.
        for text in [PronoPatates.noValue, PronoPatates.refillNote, PronoFormat.field(total: 3, planters: 2),
                     PronoFormat.harvest(stake: 3, harvest: 9), PronoFormat.harvest(stake: 3, harvest: 0)] {
            XCTAssertFalse(words.contains { text.lowercased().components(separatedBy: CharacterSet.letters.inverted).contains($0) }, text)
        }
    }
}
