import XCTest

/// Recette RÉELLE de l'Agenda dans l'app iPhone (17.11), dans le simulateur en configuration Release : serveur Party local
/// branché sur la base de TEST, compte « Admin test » (code fixe), qui a UNE demande de rendez-vous en attente
/// (RECETTE_BOOKING, préparée avant par un lien de dispo aux demandes allumées).
///   xcrun simctl privacy booted reset calendar ch.bobycharbon.party
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_BOOKING=<id> xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteAgendaUITests
/// Couvre : Réglages › Autres apps › Agenda et sa pastille « 1 », l'ouverture de /events/agenda (onglet Événements), le
/// toucher de la notification (?tab=events&booking=<id>), et le pont PartyNative.agenda depuis la page (accès d'iOS,
/// calendriers, « Ajouter à mon iPhone », rendez-vous de l'iPhone, envoi des plages « pris » au serveur).
final class RecetteAgendaUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_BOOKING"] != nil else {
            throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_BOOKING)")
        }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
    }

    private func shot(_ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "agenda-%02d-%@.png", step, name)))
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 30), "onglet Réglages")
        tab.tap()
        sleep(2)
        guard app.staticTexts["Se connecter"].exists else { return }
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText("0790000004")
        app.buttons["login-send"].tap()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Admin test"].waitForExistence(timeout: 30), "connecté en Admin test")
    }

    /// La page de l'Agenda dans le module Événements (écrans web), ou, tant qu'ils n'existent pas, la page « introuvable »
    /// du module : dans les deux cas, /events/agenda s'est ouvert dans l'onglet Événements.
    private func agendaPageOpened() -> Bool {
        any("label CONTAINS 'Qui est libre' OR label CONTAINS 'Mes liens de dispo' OR label CONTAINS 'Page introuvable'")
            .waitForExistence(timeout: 30)
    }

    func testAgendaRowBadgeOpensTheAgenda() {
        launch()
        signInAdminIfNeeded()

        // 1. Réglages › Autres apps › Agenda, avec la pastille « 1 » (demande en attente lue par le relais).
        let row = any("identifier == 'settings-agenda' OR label BEGINSWITH 'Agenda'")
        // Défilement court : la ligne doit rester à l'écran pour la capture (un grand coup la faisait dépasser).
        for _ in 0..<8 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        if !row.exists {
            try? app.debugDescription.write(to: dir.appendingPathComponent("agenda-reglages-arbre.txt"), atomically: true, encoding: .utf8)
        }
        XCTAssertTrue(row.waitForExistence(timeout: 20), "ligne Agenda dans Autres apps")
        if row.frame.minY < 200 { app.swipeDown(velocity: .slow); sleep(1) }
        XCTAssertTrue(any("label CONTAINS 'Autres apps' OR label CONTAINS 'AUTRES APPS'").exists, "section Autres apps")
        let badge = any("label == '1 demande de rendez-vous'")
        XCTAssertTrue(badge.waitForExistence(timeout: 20), "pastille 1 sur la ligne Agenda")
        shot("reglages-ligne-agenda")

        // 2. Toucher : /events/agenda dans l'onglet Événements.
        row.tap()
        XCTAssertTrue(agendaPageOpened(), "Agenda ouvert dans Événements")
        XCTAssertTrue(app.tabBars.buttons["Événements"].isSelected, "onglet Événements")
        sleep(2)
        shot("agenda-ouvert")
    }

    func testBookingNotificationOpensTheRequest() {
        let booking = env["RECETTE_BOOKING"]!
        // Toucher d'une notification booking_request, app fermée : l'adresse de send-push (tapPath).
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&booking=\(booking)');}")
        XCTAssertTrue(app.tabBars.buttons["Événements"].waitForExistence(timeout: 30))
        XCTAssertTrue(agendaPageOpened(), "la demande s'ouvre dans l'Agenda")
        sleep(2)
        shot("notification-demande")
    }

    func testBridgeFromThePage() {
        // Sonde dans la page : chaque méthode de PartyNative.agenda, résultat écrit à l'écran.
        let probe = """
        if(!sessionStorage.agendaProbe){sessionStorage.agendaProbe='1';addEventListener('load',function(){setTimeout(async function(){\
        var box=document.createElement('div');box.setAttribute('role','status');\
        box.style.cssText='position:fixed;top:110px;left:8px;right:8px;z-index:2147483647;background:#000;color:#0f0;font:13px monospace;padding:8px';\
        document.body.appendChild(box);var out={};function show(){box.textContent='agenda-probe '+JSON.stringify(out);}\
        try{var a=window.PartyNative.agenda;out.before=(await a.status()).access;show();\
        out.access=(await a.requestAccess()).access;show();\
        var cals=await a.calendars();out.calendars=cals.length;out.excluded=cals.filter(function(c){return c.excluded;}).length;show();\
        var t=new Date();t.setDate(t.getDate()+2);t.setHours(14,10,0,0);var e=new Date(t.getTime()+3000000);\
        out.saved=(await a.addToPhone({title:'Recette Agenda',start:t.toISOString(),end:e.toISOString()})).saved;show();\
        var evs=await a.events(new Date().toISOString(),new Date(Date.now()+5*864e5).toISOString());\
        var mine=evs.filter(function(x){return x.title==='Recette Agenda';});out.events=mine.length;show();\
        if(mine[0])out.set=(await a.setCalendar(mine[0].calendarId,{countsBusy:true})).ok;\
        var s=await a.syncBusy();out.sent=s.sent;out.updatedAt=!!s.updatedAt;out.done=true;show();\
        }catch(err){out.error=String(err);show();}},2500);});}
        """
        launch()
        signInAdminIfNeeded()
        app.terminate()
        launch(probe)
        let box = any("label BEGINSWITH 'agenda-probe'")
        XCTAssertTrue(box.waitForExistence(timeout: 40), "sonde de la page")

        // Demande d'iOS (accès complet), puis feuille « Nouvel événement » d'iOS : « Ajouter ».
        var answered = false, added = false
        for _ in 0..<60 where !box.label.contains("\"done\"") && !box.label.contains("\"error\"") {
            if !answered {
                let allow = springboard.alerts.buttons.matching(NSPredicate(
                    format: "label IN {'Autoriser l’accès complet', 'Autoriser l\\'accès complet', 'Allow Full Access', 'OK', 'Autoriser'}")).firstMatch
                if allow.exists {
                    shot("demande-ios")
                    allow.tap()
                    answered = true
                }
            }
            if !added {
                // iOS 26 : « ✓ » à droite de « Nouvel évènement » (libellé selon la version) ; sinon « Ajouter ».
                let sheet = app.navigationBars.matching(NSPredicate(format: "identifier CONTAINS[c] 'nouvel' OR identifier CONTAINS[c] 'new event'")).firstMatch
                var add = app.buttons.matching(NSPredicate(format: "label IN {'Ajouter', 'Add', 'Terminé', 'Done'}")).firstMatch
                if !add.exists && sheet.exists && sheet.buttons.count > 0 { add = sheet.buttons.element(boundBy: sheet.buttons.count - 1) }
                if !add.exists && box.label.contains("\"calendars\"") {
                    try? app.debugDescription.write(to: dir.appendingPathComponent("agenda-feuille-arbre.txt"), atomically: true, encoding: .utf8)
                }
                if add.exists && box.label.contains("\"calendars\"") {
                    sleep(1)
                    shot("feuille-ajouter-ios")
                    add.tap()
                    added = true
                }
            }
            sleep(1)
        }
        let result = box.label
        shot("sonde-resultat")
        XCTAssertTrue(result.contains("\"access\":\"full\""), "accès complet : \(result)")
        XCTAssertTrue(result.contains("\"saved\":true"), "rendez-vous ajouté par la feuille d'iOS : \(result)")
        XCTAssertTrue(result.contains("\"set\":true"), "calendrier coché « compte dans mes dispos » : \(result)")
        XCTAssertTrue(result.contains("\"updatedAt\":true") && !result.contains("\"sent\":0"), "plages envoyées au serveur : \(result)")
    }
}
