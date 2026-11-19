import XCTest

extension XCUIApplication {
    /// « Recevoir un code par SMS » pour un numéro de test (code fixe). La base de TEST, partagée entre les recettes,
    /// n'envoie qu'un code par minute et par numéro : « Trop de codes demandés » → on attend la minute et on redemande.
    func sendLoginCode() {
        let send = buttons["login-send"]
        let code = textFields["login-code"]
        for attempt in 0..<3 {
            send.tap()
            if code.waitForExistence(timeout: 20) { return }
            let tooMany = staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Trop de codes'")).firstMatch
            guard tooMany.exists, attempt < 2 else { return }
            sleep(62)
        }
    }
}
