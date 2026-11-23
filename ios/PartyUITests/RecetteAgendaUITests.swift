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
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Admin test"].waitForExistence(timeout: 30), "connecté en Admin test")
    }

    /// La page de l'Agenda dans le module Événements (écrans web), jamais « Page introuvable ».
    private func agendaPageOpened() -> Bool {
        let opened = any("label CONTAINS 'Qui est libre' OR label CONTAINS 'Mes liens de dispo'").waitForExistence(timeout: 30)
        return opened && !any("label CONTAINS 'Page introuvable'").exists
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

    /// « Qui est libre ? » en calendrier du mois (maquette A, avis du 23.11) : groupe « [QA] Qui est libre 2311 » de la base de
    /// TEST (4 personnes qui partagent), jours dans l'ordre, « n/4 », le meilleur encadré ; toucher un jour ouvre la feuille,
    /// puis le soir / la journée (18 h – 23 h, 8 h – 17 h) et le vote à cocher.
    /// Testeur 1 (0790000001), membre du groupe de recette qui partage ses dispos ; puis Réglages › Autres apps › Agenda.
    private func signInTesteur1AndOpenAgenda() {
        launch()
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        tab.tap()
        sleep(2)
        if app.staticTexts["Se connecter"].exists {
            app.staticTexts["Se connecter"].firstMatch.tap()
            let field = app.textFields["login-phone"]
            XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
            field.tap()
            app.typeText("0790000001")
            app.sendLoginCode()
            let code = app.textFields["login-code"]
            XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
            code.tap()
            app.typeText("123456")
            // Le prénom du compte de recette change sur la base de TEST (« Agenda Léa ») : on attend la ligne « Mon profil ».
            XCTAssertTrue(app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS 'Mon profil'")).firstMatch.waitForExistence(timeout: 30), "connecté (Testeur 1)")
            sleep(3)
            // Relancée une fois connectée : les drapeaux (/api/features, Agenda) et la session de la page sont relus.
            app.terminate()
            launch()
        }
        reopenAgenda()
    }

    /// Réglages › Autres apps › Agenda (app déjà connectée).
    private func reopenAgenda() {
        XCTAssertTrue(app.tabBars.buttons["Réglages"].waitForExistence(timeout: 40), "onglet Réglages")
        app.tabBars.buttons["Réglages"].tap()
        sleep(3)
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Agenda, ")).firstMatch
        for _ in 0..<10 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        if !row.exists { try? app.debugDescription.write(to: dir.appendingPathComponent("agenda-arbre.txt"), atomically: true, encoding: .utf8) }
        XCTAssertTrue(row.waitForExistence(timeout: 20), "Réglages › Autres apps › Agenda")
        row.tap()
        XCTAssertTrue(agendaPageOpened(), "Agenda ouvert")
    }

    /// Le tutoriel de l'Agenda (avis du 23.11) : s'ouvre à chaque arrivée tant que « Ne plus me le rappeler » n'est pas touché ;
    /// 5 cartes, puis l'assistant en 3 étapes ; « Passer » le ferme pour cette fois, « Ne plus me le rappeler » pour de bon.
    /// Préparer avant (base de TEST) : prefs de l'agenda de Testeur 1 sans `tutorial_off`.
    func testAgendaTutorialAndSetup() {
        signInTesteur1AndOpenAgenda()
        let tutorial = any("identifier == 'agenda-tutorial' OR label == 'Tutoriel de l’agenda'")
        XCTAssertTrue(any("label CONTAINS 'Ton agenda Party'").waitForExistence(timeout: 30), "tutoriel, carte 1")
        sleep(1)
        shot("tuto-1")
        for n in 2...5 {
            any("label == 'Suivant'").tap()
            sleep(1)
            shot("tuto-\(n)")
        }
        XCTAssertTrue(any("label CONTAINS 'Liens de dispo'").exists, "carte 5")
        // L'assistant : 3 étapes, chacune peut être passée.
        app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Configurer mon agenda en 3 étapes")).firstMatch.tap()
        XCTAssertTrue(any("label CONTAINS 'étape 1 sur 3'").waitForExistence(timeout: 20), "étape 1/3")
        sleep(2)
        shot("assistant-1")
        // Sur l'iPhone, l'étape 1 explique d'abord l'accès au calendrier (« Rien n'est envoyé »), puis iOS demande.
        let go = app.buttons["Continuer"]
        if go.waitForExistence(timeout: 5) {
            go.tap()
            let allow = springboard.buttons.matching(NSPredicate(format: "label CONTAINS 'Autoriser' OR label CONTAINS 'Allow'")).firstMatch
            if allow.waitForExistence(timeout: 10) {
                let full = springboard.buttons.matching(NSPredicate(format: "label CONTAINS 'complet' OR label CONTAINS 'Full'")).firstMatch
                (full.exists ? full : allow).tap()
            }
            sleep(3)
            shot("assistant-1-iphone-relie")
        }
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Suivant'")).firstMatch.tap()
        XCTAssertTrue(any("label CONTAINS 'étape 2 sur 3'").waitForExistence(timeout: 20), "étape 2/3")
        sleep(2)
        shot("assistant-2")
        any("label == 'Passer cette étape'").tap()
        XCTAssertTrue(any("label CONTAINS 'est prêt'").waitForExistence(timeout: 20), "étape 3/3")
        sleep(2)
        shot("assistant-3")
        // Revenir : le tutoriel revient à la prochaine arrivée ; « Ne plus me le rappeler » l'arrête.
        app.terminate()
        launch()
        reopenAgenda()
        XCTAssertTrue(any("label CONTAINS 'Ton agenda Party'").waitForExistence(timeout: 30), "le tutoriel revient")
        any("label == 'Ne plus me le rappeler'").tap()
        sleep(2)
        XCTAssertFalse(tutorial.exists, "tutoriel fermé")
        shot("tuto-ferme-pour-de-bon")
        app.terminate()
        launch()
        reopenAgenda()
        sleep(5)
        XCTAssertFalse(any("label CONTAINS 'Ton agenda Party'").exists, "le tutoriel ne revient plus")
        XCTAssertTrue(any("label CONTAINS 'Revoir le tutoriel'").exists || { app.swipeUp(); return any("label CONTAINS 'Revoir le tutoriel'").waitForExistence(timeout: 5) }(), "« Revoir le tutoriel »")
        shot("accueil-sans-tuto")
    }

    func testWhoIsFreeMonthView() {
        signInTesteur1AndOpenAgenda()
        // Tutoriel encore affiché (compte de recette) : on le passe pour cette fois.
        let skip = any("label == 'Passer'")
        if skip.waitForExistence(timeout: 8) { skip.tap(); sleep(1) }
        let free = any("label CONTAINS 'Qui est libre'")
        free.tap()
        let group = any("label == '[QA] Qui est libre 2311'")
        XCTAssertTrue(group.waitForExistence(timeout: 30), "bulle du groupe de recette")
        group.tap()
        XCTAssertTrue(any("label BEGINSWITH 'Le mieux'").waitForExistence(timeout: 30), "carte « Le mieux »")
        XCTAssertTrue(any("label CONTAINS '18 h – 23 h'").exists, "le soir 18 h – 23 h")
        XCTAssertTrue(any("label CONTAINS 'aujourd’hui'").exists, "aujourd'hui marqué")
        sleep(2)
        shot("qui-est-libre-mois")
        app.swipeUp(velocity: .slow); sleep(1)
        shot("qui-est-libre-mois-suite")
        // Toucher le meilleur jour : la feuille, qui est libre en mots, Organiser.
        let best = any("label BEGINSWITH 'Le mieux : '")
        XCTAssertTrue(best.waitForExistence(timeout: 10), "case du meilleur jour")
        best.tap()
        XCTAssertTrue(any("label BEGINSWITH 'Organiser le'").waitForExistence(timeout: 15), "feuille du jour")
        XCTAssertTrue(any("label CONTAINS '4 / 4 disponibles'").exists, "4 / 4 disponibles")
        sleep(1)
        shot("qui-est-libre-jour")
        any("label == 'Fermer la fenêtre'").tap()
        sleep(1)
        // La journée : 8 h – 17 h.
        app.swipeDown(velocity: .fast); sleep(1)
        let day = any("label CONTAINS 'La journée'")
        if day.exists { day.tap() }
        XCTAssertTrue(any("label CONTAINS '8 h – 17 h'").waitForExistence(timeout: 10), "la journée 8 h – 17 h")
        sleep(2)
        shot("qui-est-libre-journee")
        any("label CONTAINS 'Le soir'").tap()
        sleep(1)
        // Faire voter : 3 jours cochés d'office, le bouton les compte.
        for _ in 0..<12 where !any("label == '🗳️ Faire voter le groupe'").isHittable { app.swipeUp(velocity: .slow) }
        any("label == '🗳️ Faire voter le groupe'").tap()
        XCTAssertTrue(any("label BEGINSWITH '🗳️ Faire voter le groupe (3 dates)'").waitForExistence(timeout: 10), "vote à 3 dates")
        sleep(1)
        shot("qui-est-libre-vote")
    }

    func testBookingNotificationOpensTheRequest() {
        let booking = env["RECETTE_BOOKING"]!
        // Toucher d'une notification booking_request, app fermée : l'adresse de send-push (tapPath).
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&booking=\(booking)');}")
        XCTAssertTrue(app.tabBars.buttons["Événements"].waitForExistence(timeout: 30))
        XCTAssertTrue(any("label CONTAINS 'Accepter'").waitForExistence(timeout: 30), "la demande s'ouvre (Accepter / Refuser)")
        XCTAssertFalse(any("label CONTAINS 'Page introuvable'").exists)
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
            // Chaque demande d'iOS (l'accès complet peut se confirmer en deux temps) : on autorise tant qu'il en reste.
            let allow = springboard.alerts.buttons.matching(NSPredicate(
                format: "label IN {'Autoriser l’accès complet', 'Autoriser l\\'accès complet', 'Allow Full Access', 'OK', 'Autoriser'}")).firstMatch
            if allow.exists {
                if !answered { shot("demande-ios") }
                sleep(1)  // fin de l'animation : un toucher pendant l'apparition ne compte pas
                if allow.exists { allow.tap() }
                answered = true
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
