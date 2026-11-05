import Foundation
import Testing
@testable import Party

/// Liens des textes d'événement (avis 2c221fd8effc) : http(s), e-mail et téléphone cliquables, jamais javascript:.
struct LinkedTextTests {
    private func links(_ text: String) -> [URL] {
        LinkedText.attributed(text).runs.compactMap { $0.link }
    }

    @Test func webAddressesAndPhoneNumbersBecomeLinks() {
        let found = links("Paiement : https://pay.example.ch/a?b=1 ou TWINT au +41 79 123 45 67, infos ana@example.ch")
        #expect(found.contains(URL(string: "https://pay.example.ch/a?b=1")!))
        #expect(found.contains { $0.scheme == "tel" && $0.absoluteString.contains("41791234567") })
        #expect(found.contains { $0.scheme == "mailto" })
    }

    @Test func dangerousSchemesStayPlainText() {
        #expect(links("javascript:alert(1) data:text/html,<b>x</b>").isEmpty)
        #expect(LinkedText.safeURL(URL(string: "javascript:alert(1)")) == nil)
        #expect(LinkedText.safeURL(URL(string: "https://banque.ch@piege.example")) == nil)
        #expect(LinkedText.safeURL(URL(string: "https://example.ch")) != nil)
    }

    @Test func textIsKeptAsIs() {
        let text = "<img src=x onerror=alert(1)> www.example.ch"
        #expect(String(LinkedText.attributed(text).characters) == text)
    }
}
