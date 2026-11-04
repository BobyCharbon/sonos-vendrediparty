import Foundation
import Testing
@testable import Party

/// Widgets Zicou et Live Activity de l'éclosion (maquettes E et H du 4.11) : lecture de la réponse du serveur,
/// chronologie calculée sur l'iPhone, début et fin de l'éclosion, actions rapides de l'icône.
struct ZicouWidgetTests {
    private let now = Date(timeIntervalSince1970: 1_793_800_000)   // 2026-11-04, l'après-midi à Zurich

    private func state(stage: String = "adult", emotion: String = "happy", food: Double = 80, joy: Double = 80,
                       energy: Double = 80, care: Double = 80, asleep: Bool = false, hatchAt: Date? = nil,
                       chest: Bool = false, diesAt: Date? = nil) -> PetWidgetState {
        PetWidgetState(name: "Paillette", stage: stage, variant: "classic", emotion: emotion, asleep: asleep, sick: false,
                       gauges: .init(food: food, joy: joy, energy: energy, care: care), streak: 12, chestReady: chest,
                       hatchAt: hatchAt, diesAt: diesAt, at: now)
    }

    // MARK: Décodage

    @Test("Décodage : champs du serveur, cadeau du jour, série, éclosion")
    func decoding() throws {
        let json = #"""
        {"name":"Paillette","stage":"egg","variant":"classic","emotion":"egg","asleep":false,"sick":false,
         "gauges":{"food":80,"joy":80,"energy":90,"care":90},"streak":3,"next_stage_in":150,"dies_at":null,
         "daily":{"chest":{"state":"ready"},"streak":{"count":4}}}
        """#
        let pet = try #require(PetWidgetState.decode(Data(json.utf8), receivedAt: now))
        #expect(pet.name == "Paillette" && pet.stage == "egg" && pet.isEgg)
        #expect(pet.chestReady && pet.streak == 4)
        #expect(pet.hatchAt == now.addingTimeInterval(150))
        #expect(pet.gauges == .init(food: 80, joy: 80, energy: 90, care: 90))
    }

    @Test("Décodage : réponse illisible ou stade inconnu → rien")
    func decodingRejects() {
        #expect(PetWidgetState.decode(Data("{}".utf8), receivedAt: now) == nil)
        #expect(PetWidgetState.decode(Data(#"{"stage":"dragon"}"#.utf8), receivedAt: now) == nil)
    }

    @Test("Décodage : valeurs hors bornes ramenées, humeur inconnue → va bien, coffre ouvert")
    func decodingClamps() throws {
        let json = #"{"stage":"adult","emotion":"???","gauges":{"food":140,"joy":-3},"dies_at":"2026-11-07T10:00:00+00:00","daily":{"chest":{"state":"opened"}}}"#
        let pet = try #require(PetWidgetState.decode(Data(json.utf8), receivedAt: now))
        #expect(pet.gauges.food == 100 && pet.gauges.joy == 0 && pet.gauges.energy == 0)
        #expect(pet.emotion == "happy" && !pet.chestReady && pet.name == "Zicou")
        #expect(pet.diesAt != nil)
    }

    @Test("Nom : celui du serveur (filtré) ; vide, trop long ou sur plusieurs lignes → « Zicou »")
    func names() {
        #expect(PetWidgetState.displayName("  Paillette ") == "Paillette")
        #expect(PetWidgetState.displayName(nil) == "Zicou")
        #expect(PetWidgetState.displayName("") == "Zicou")
        #expect(PetWidgetState.displayName(String(repeating: "a", count: 21)) == "Zicou")
        #expect(PetWidgetState.displayName("a\nb") == "Zicou")
    }

    // MARK: Chronologie

    @Test("Chronologie : une entrée toutes les 30 min sur 12 h, dans l'ordre")
    func timelineSpacing() {
        let moments = PetForecast.moments(from: state(), now: now)
        #expect(moments.first?.date == now)
        #expect(moments.count >= 25)
        #expect(moments.map(\.date) == moments.map(\.date).sorted())
        #expect(moments.last!.date <= now.addingTimeInterval(PetForecast.horizon))
    }

    @Test("Les jauges baissent comme sur le serveur (adulte : ventre 2,4 × 0,9 par heure)")
    func gaugesDecay() {
        let m = PetForecast.moment(of: state(), at: now.addingTimeInterval(10 * 3600))
        #expect(abs(m.gauges.food - (80 - 2.4 * 0.9 * 10)) < 0.001)
        #expect(abs(m.gauges.joy - (80 - 1.8 * 10)) < 0.001)
        #expect(abs(m.gauges.energy - (80 - 3.0 * 0.9 * 10)) < 0.001)
        #expect(abs(m.gauges.care - (80 - 1.5 * 10)) < 0.001)
    }

    @Test("Humeur : il finit par avoir un petit creux, sans soins")
    func becomesHungry() {
        let start = state(food: 30)
        #expect(PetForecast.moment(of: start, at: now).emotion == "happy")
        #expect(PetForecast.moment(of: start, at: now.addingTimeInterval(4 * 3600)).emotion == "hungry")
    }

    @Test("Endormi : l'énergie remonte et il se réveille seul")
    func sleepsThenWakes() {
        let tired = state(emotion: "sleep", energy: 50, asleep: true)
        #expect(PetForecast.moment(of: tired, at: now.addingTimeInterval(3600)).emotion == "sleep")
        let later = PetForecast.moment(of: tired, at: now.addingTimeInterval(6 * 3600))
        #expect(later.emotion != "sleep" && later.gauges.energy < 100)
    }

    @Test("Œuf : « egg » jusqu'à l'éclosion, une entrée pile à l'éclosion, puis bébé")
    func eggHatches() {
        let hatch = now.addingTimeInterval(130)
        let egg = state(stage: "egg", emotion: "egg", hatchAt: hatch)
        let moments = PetForecast.moments(from: egg, now: now)
        #expect(moments.first?.emotion == "egg")
        let atHatch = moments.first { $0.date == hatch }
        #expect(atHatch?.stage == "baby" && atHatch?.emotion != "egg")
    }

    @Test("Cadeau du jour : de nouveau prêt après minuit à Zurich")
    func chestAtMidnight() {
        let opened = state(chest: false)
        let midnight = PetForecast.nextMidnight(after: now)
        #expect(!PetForecast.moment(of: opened, at: midnight.addingTimeInterval(-60)).chestReady)
        #expect(PetForecast.moment(of: opened, at: midnight).chestReady)
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = PetForecast.zurich
        #expect(calendar.component(.hour, from: midnight) == 0)
    }

    @Test("« En fête » n'est gardé qu'à la lecture (sa fin n'est pas connue)")
    func partyOnlyAtReading() {
        let party = state(emotion: "party")
        #expect(PetForecast.moment(of: party, at: now).emotion == "party")
        #expect(PetForecast.moment(of: party, at: now.addingTimeInterval(1800)).emotion == "happy")
    }

    @Test("Au-delà de la date annoncée par le serveur : envolé")
    func gone() {
        let danger = state(food: 0, diesAt: now.addingTimeInterval(3600))
        #expect(PetForecast.moment(of: danger, at: now.addingTimeInterval(2 * 3600)).emotion == "ghost")
    }

    // MARK: Live Activity de l'éclosion

    @Test("Éclosion : démarre pour un œuf frais, rien si le réglage est coupé")
    func hatchStarts() {
        let hatch = now.addingTimeInterval(170)
        let egg = state(stage: "egg", emotion: "egg", hatchAt: hatch)
        #expect(HatchActivityStep.plan(egg, now: now, enabled: true, running: [])
                == [.start(name: "Paillette", laidAt: hatch.addingTimeInterval(-180), hatchAt: hatch)])
        #expect(HatchActivityStep.plan(egg, now: now, enabled: false, running: []).isEmpty)
        // Presque éclos : on ne démarre plus rien.
        let late = state(stage: "egg", emotion: "egg", hatchAt: now.addingTimeInterval(10))
        #expect(HatchActivityStep.plan(late, now: now, enabled: true, running: []).isEmpty)
    }

    @Test("Éclosion : même œuf suivi une seule fois, un autre œuf remplace l'ancien")
    func hatchFollowsOneEgg() {
        let hatch = now.addingTimeInterval(170)
        let egg = state(stage: "egg", emotion: "egg", hatchAt: hatch)
        let same = HatchActivityStep.Running(id: "a", hatchAt: hatch.addingTimeInterval(1), hatched: false)
        #expect(HatchActivityStep.plan(egg, now: now, enabled: true, running: [same]).isEmpty)
        let old = HatchActivityStep.Running(id: "old", hatchAt: now.addingTimeInterval(-600), hatched: true)
        #expect(HatchActivityStep.plan(egg, now: now, enabled: true, running: [old])
                == [.end(id: "old"), .start(name: "Paillette", laidAt: hatch.addingTimeInterval(-180), hatchAt: hatch)])
    }

    @Test("Fin de la Live Activity : à l'éclosion « est né », puis plus rien ; coupée → retirée")
    func hatchEnds() {
        let running = HatchActivityStep.Running(id: "a", hatchAt: now.addingTimeInterval(-5), hatched: false)
        let baby = state(stage: "baby")
        #expect(HatchActivityStep.plan(baby, now: now, enabled: true, running: [running]) == [.hatched(id: "a")])
        // Lecture encore « œuf » mais l'heure est passée (app rouverte) : terminée quand même.
        let staleEgg = state(stage: "egg", emotion: "egg", hatchAt: now.addingTimeInterval(-5))
        #expect(HatchActivityStep.plan(staleEgg, now: now, enabled: true, running: [running]) == [.hatched(id: "a")])
        let done = HatchActivityStep.Running(id: "a", hatchAt: now.addingTimeInterval(-5), hatched: true)
        #expect(HatchActivityStep.plan(baby, now: now, enabled: true, running: [done]).isEmpty)
        #expect(HatchActivityStep.plan(baby, now: now, enabled: false, running: [running]) == [.end(id: "a")])
        #expect(HatchActivityStep.plan(nil, now: now, enabled: true, running: [running]) == [.end(id: "a")])
        // Épisode borné : jamais plus de 3 min de décompte, « est né » retiré après 10 min.
        #expect(HatchActivityStep.eggDuration == 180 && HatchActivityStep.dismissAfter <= 8 * 3600)
    }

    // MARK: Liens et actions rapides

    @Test("Liens : le panneau du Compagnon, avec l'origine de l'ouverture")
    func links() throws {
        let base = try #require(URL(string: "https://partytest.bobycharbon.ch"))
        #expect(PetLinks.zicou(src: "widget", base: base).absoluteString
                == "https://partytest.bobycharbon.ch/?tab=games&pet=1&src=widget")
        #expect(QuickAction.gift.target(base: base)
                == .page(URL(string: "https://partytest.bobycharbon.ch/?tab=games&pet=1&src=link&screen=chest")!))
        #expect(QuickAction.addTrack.target(base: base) == .addTrack)
        #expect(QuickAction(type: "inconnu") == nil)
        #expect(QuickAction(type: "ch.bobycharbon.party.zicou") == .zicou)
    }

    @Test("Compagnon en bêta : seule « Ajouter un titre » est fixe ; Zicou et Cadeau du jour sont ajoutées par l'app")
    func staticShortcuts() {
        let items = Bundle.main.object(forInfoDictionaryKey: "UIApplicationShortcutItems") as? [[String: Any]] ?? []
        #expect(items.compactMap { $0["UIApplicationShortcutItemType"] as? String } == [QuickAction.addTrack.rawValue])
        #expect(QuickAction.companion == [.zicou, .gift])
    }

    @Test("Widgets rechargés seulement quand le dessin change")
    func reloadOnlyOnChange() {
        let a = state()
        var b = a
        b.at = a.at.addingTimeInterval(60)
        b.gauges.food += 1
        #expect(PetWidgetBridge.sameLook(a, b))
        b.emotion = "hungry"
        #expect(!PetWidgetBridge.sameLook(a, b))
    }
}
