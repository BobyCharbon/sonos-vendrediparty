import Foundation
import Testing
@testable import PartyTV

/// Les Zicou de la soirée sur la télé : lecture de /api/tv/zicou, rotation des Zicou visibles, figure de victoire.
struct ZicouTests {
    private func json(_ text: String) throws -> JSON { try JSONDecoder().decode(JSON.self, from: Data(text.utf8)) }

    private func dancers(_ n: Int) -> [ZicouDancer] {
        (0..<n).compactMap { ZicouDancer(.object(["key": .string("k\($0)"), "name": .string("Z\($0)"), "stage": .string("adult")])) }
    }

    @Test("Décodage : aspect, tenue, shiny, place ; entrées illisibles ignorées, doublons retirés")
    func decodes() throws {
        let list = ZicouDancer.list(try json(#"""
            {"count": 5, "zicous": [
              {"key":"a1","name":"Léa","stage":"adult","emotion":"party","variant":"star","acc":{"head":"couronne","facets":"facettes-or"},"shiny":true,"pid":"p1"},
              {"key":"b2","name":null,"stage":"egg","emotion":"happy","variant":"classic","acc":{},"shiny":false,"pid":null},
              {"key":"c3","name":"   ","stage":"teen","emotion":"bizarre","variant":"???","acc":[],"shiny":false},
              {"key":"d4","stage":"dead"},
              {"name":"sans clé","stage":"adult"},
              {"key":"a1","name":"Doublon","stage":"baby"}
            ]}
            """#))
        #expect(list.map(\.key) == ["a1", "b2", "c3"])
        let lea = list[0]
        #expect(lea.name == "Léa" && lea.stage == .adult && lea.emotion == "party" && lea.variant == .star)
        #expect(lea.acc == ["head": "couronne", "facets": "facettes-or"] && lea.shiny && lea.pid == "p1")
        #expect(list[1].name == nil && list[1].emotion == "egg" && list[1].pid == nil)   // un œuf a toujours l'air d'un œuf
        #expect(list[2].name == nil && list[2].emotion == "happy" && list[2].variant == .classic && list[2].acc.isEmpty)
        #expect(ZicouDancer.list(.null).isEmpty)
    }

    @Test("Rotation : au plus 6 visibles, pages successives qui reviennent au début, tous vus")
    func rotates() {
        let all = dancers(14)
        let pages = (0..<3).map { ZicouFloor.visible(all, turn: $0).map(\.key) }
        #expect(pages.allSatisfy { $0.count == 6 })
        #expect(pages[0] == (0..<6).map { "k\($0)" } && pages[1] == (6..<12).map { "k\($0)" })
        #expect(pages[2] == ["k12", "k13", "k0", "k1", "k2", "k3"])   // dernière page complétée par le début
        #expect(Set(pages.flatMap { $0 }) == Set(all.map(\.key)))
        #expect(ZicouFloor.visible(all, turn: 3).map(\.key) == pages[0])
        #expect(ZicouFloor.visible(dancers(4), turn: 7).count == 4)   // peu de monde : tous, sans rotation
        #expect(ZicouFloor.visible(all, turn: 0, limit: 3).count == 3)
        #expect(ZicouFloor.visible([], turn: 0).isEmpty)
    }

    @Test("Rotation : le gagnant du moment reste à l'écran, en tête")
    func pinsWinners() {
        let all = dancers(14)
        for turn in 0..<4 {
            let shown = ZicouFloor.visible(all, turn: turn, pinned: ["k13"])
            #expect(shown.first?.key == "k13" && shown.count == 6 && Set(shown.map(\.key)).count == 6)
        }
    }

    @Test("Figure de victoire : le gagnant d'une manche est retrouvé par sa place, sinon par son surnom")
    func victory() throws {
        let zicous = ZicouDancer.list(try json(#"""
            {"zicous":[{"key":"a","name":"Léa","stage":"adult","pid":"p-lea"},
                       {"key":"b","name":"Tom","stage":"adult","pid":null},
                       {"key":"c","name":"Inès","stage":"teen","pid":"p-autre"},
                       {"key":"d","name":null,"stage":"baby"}]}
            """#))
        // « Qui de nous » en mode points : les désignés gagnent 1 point.
        let round = try json(#"""
            {"code":"1234","type":"likely","phase":"reveal","round":2,"options":{"sips":0},
             "likely":{"n":3,"result":{"winners":[{"name":"LEA"},{"name":"tom"}]}},
             "players":[{"pid":"p-lea","name":"LEA"},{"pid":"p-tom","name":"tom"},{"pid":"p-autre","name":"Inès"}]}
            """#)
        #expect(ZicouFloor.winners(round, among: zicous) == ["a", "b"])   // Léa par sa place, Tom par son surnom
        #expect(ZicouFloor.victoryKey(round) != nil)
        // Personne n'a gagné : pas de figure.
        let none = try json(#"{"code":"1234","type":"likely","phase":"vote","players":[]}"#)
        #expect(ZicouFloor.winners(none, among: zicous).isEmpty && ZicouFloor.victoryKey(none) == nil)
        // Fin d'un Quiz : le champion fait sa figure.
        let end = try json(#"""
            {"code":"9","type":"quiz","phase":"end","quiz":{"board":[{"name":"Inès","pts":7},{"name":"Léa","pts":3}]},
             "players":[{"pid":"p-autre","name":"Inès"},{"pid":"p-lea","name":"Léa"}]}
            """#)
        #expect(ZicouFloor.winners(end, among: zicous) == ["c"])
    }

    @Test("Figure de victoire : un saut vrillé d'un tour complet, qui retombe à sa place")
    func figureShape() {
        let start = ZicouMove.figure(0, size: 100), middle = ZicouMove.figure(0.5, size: 100), end = ZicouMove.figure(0.999, size: 100)
        #expect(start.y == 0 && start.spin == 0)
        #expect(middle.y < -25 && middle.spin == 180 && middle.scale > 1.1)
        #expect(abs(end.y) < 1 && end.spin > 359)
    }

    @Test("Tempo : celui du titre s'il est connu, sinon un pas régulier ; la danse suit le temps")
    func tempo() throws {
        #expect(ZicouFloor.beatsPerMinute(try json(#"{"now":{"title":"x"}}"#)) == ZicouFloor.defaultBPM)
        #expect(ZicouFloor.beatsPerMinute(try json(#"{"now":{"tempo":128}}"#)) == 128)
        #expect(ZicouFloor.beatsPerMinute(try json(#"{"now":{"bpm":999}}"#)) == ZicouFloor.defaultBPM)   // valeur absurde ignorée
        let z = dancers(1)[0]
        let onBeat = ZicouMove.dance(beats: 2, style: 0, dancer: z, size: 100), offBeat = ZicouMove.dance(beats: 2.5, style: 0, dancer: z, size: 100)
        #expect(abs(onBeat.y) < 0.01 && offBeat.y < -7)   // posé sur le temps, en l'air entre deux temps
    }

    @Test("Titre de la piste et facettes identiques au navigateur (même tirage mulberry32)")
    func headlineAndRandom() {
        #expect(ZicouFloor.headline(1) == "1 Zicou danse" && ZicouFloor.headline(6) == "6 Zicou dansent")
        // Valeurs de référence de skin.js : rng(21)() puis rng(21)() en JavaScript.
        var r = Mulberry32(21)
        let a = r.next(), b = r.next()
        #expect(abs(a - 0.4322912215720862) < 1e-12 && abs(b - 0.4470290595199913) < 1e-12)
    }

    @Test("Les adresses gardent leur question (?game=…)")
    func urlQuery() {
        let client = TVClient(base: URL(string: "https://party.exemple.ch")!)
        #expect(client.url("api/tv/zicou?game=1234").absoluteString == "https://party.exemple.ch/api/tv/zicou?game=1234")
        #expect(client.url("api/tv").absoluteString == "https://party.exemple.ch/api/tv")
    }

    @Test("Vedette et Salon : lus depuis /api/tv/zicou, sans texte libre ni identifiant de compte")
    func starAndSalon() throws {
        let data = try json(#"""
            {"zicous": [], "count": 0, "star_waiting": 2,
             "star": {"key":"s1","name":"Léa","stage":"adult","emotion":"party","variant":"star","acc":{"head":"couronne"},"shiny":false,"dye":{"couronne":"or"},"left":22,"seconds":30},
             "salon": [{"id":"boule-disco","emoji":"🪩","label":"Boule disco géante au Salon de Party"}, {"id":"x"}]}
            """#)
        let star = try #require(ZicouStar(data))
        #expect(star.dancer.name == "Léa" && star.dancer.acc == ["head": "couronne"] && star.left == 22 && star.waiting == 2)
        #expect(SalonBadge.list(data).map(\.emoji) == ["🪩"])
        let none = try json(#"{"zicous": [], "count": 0, "star": null, "star_waiting": 0, "salon": []}"#)
        #expect(ZicouStar(none) == nil && SalonBadge.list(none).isEmpty)
        // Même vedette, décompte différent : pas une nouvelle entrée (pas d'animation relancée chaque seconde).
        let later = try json(#"{"star": {"key":"s1","name":"Léa","stage":"adult","left":10}, "star_waiting": 1}"#)
        #expect(ZicouStar(later) == ZicouStar(try json(#"{"star": {"key":"s1","name":"Léa","stage":"adult","left":20}}"#)))
    }
}
