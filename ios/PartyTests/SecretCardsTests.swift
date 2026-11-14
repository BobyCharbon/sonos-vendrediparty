import SwiftUI
import Testing
import UIKit
@testable import Party

/// Pyramide (avis 4c55c231a4d2) : les cartes à mémoriser confiées par la page (PartyNative.secret.update), montrées
/// dans un panneau qu'une capture d'écran rend noir.
@MainActor
struct SecretCardsTests {
    @Test("Les 4 cartes de la page se lisent : 10 de cœur, As de pique…")
    func readsTheCards() throws {
        let state = try #require(SecretCardsState(message: ["cards": ["TH", "AS", "kd", "7C"], "title": "Tes cartes"]))
        #expect(state.cards.map(\.rank) == ["10", "A", "K", "7"])
        #expect(state.cards.map(\.symbol) == ["♥", "♠", "♦", "♣"])
        #expect(state.cards.map(\.isRed) == [true, false, true, false])
        #expect(state.cards[0].spoken == "10 de cœur" && state.title == "Tes cartes")
    }

    @Test("Rien, une carte cachée ou illisible : pas de panneau ; jamais plus de 4 cartes")
    func refusesWhatIsNotACard() throws {
        #expect(SecretCardsState(message: NSNull()) == nil)
        #expect(SecretCardsState(message: ["cards": ["??", "ZZ", ""]]) == nil)
        let state = try #require(SecretCardsState(message: ["cards": ["2S", "3S", "4S", "5S", "6S"]]))
        #expect(state.cards.count == 4 && state.title == "Tes cartes")
    }

    @Test("Le panneau est posé dans la zone qu'iOS retire des captures (champ de mot de passe)")
    func usesTheSecureCanvas() throws {
        let canvas = try #require(ScreenshotProof<EmptyView>.secureCanvas(of: UITextField()))
        #expect(String(describing: type(of: canvas)).contains("Canvas"))
    }
}
