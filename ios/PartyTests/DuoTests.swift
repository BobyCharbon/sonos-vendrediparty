import CoreGraphics
import Testing
import UIKit
@testable import Party

/// iPhone Duo : posture transmise à la page (Fold.swift) et barre d'onglets partagée avec la barre verticale.
struct DuoTests {
    @Test("Autre iPhone (pas de charnière) : aucun état, rien n'est envoyé à la page")
    func noHingeNoState() {
        #expect(FoldState(hinge: nil, fold: CGRect(x: 1, y: 2, width: 3, height: 4)) == nil)
    }

    @Test("Postures : fermé, à plat, livre (pli vertical), portable (pli horizontal), entrouvert sans pli")
    func postures() {
        let book = CGRect(x: 320, y: 0, width: 30, height: 900)
        let laptop = CGRect(x: 0, y: 320, width: 900, height: 30)
        #expect(FoldState(hinge: .closed, fold: nil)?.posture == .closed)
        #expect(FoldState(hinge: .closed, fold: book)?.posture == .closed)
        #expect(FoldState(hinge: .fullyOpen, fold: nil)?.posture == .flat)
        #expect(FoldState(hinge: .partiallyOpen, fold: book)?.posture == .book)
        #expect(FoldState(hinge: .partiallyOpen, fold: laptop)?.posture == .laptop)
        #expect(FoldState(hinge: .partiallyOpen, fold: nil)?.posture == .half)
        #expect(FoldState(hinge: .partiallyOpen, fold: .zero)?.fold == nil)
    }

    @Test("Script de la page : attribut data-posture, variables --fold-*, window.PartyFold et événement party-fold")
    func pageScript() throws {
        let book = try #require(FoldState(hinge: .partiallyOpen, fold: CGRect(x: 319.6, y: 0, width: 30.2, height: 900)))
        let script = book.script
        #expect(book.fold == CGRect(x: 319, y: 0, width: 31, height: 900))
        #expect(script.contains(#"{"posture":"book","fold":{"x":319,"y":0,"width":31,"height":900}}"#))
        #expect(script.contains("setAttribute('data-posture'"))
        #expect(script.contains("'--fold-' + k"))
        #expect(script.contains("window.PartyFold = d"))
        #expect(script.contains("new CustomEvent('party-fold'"))
        // Écran d'un seul tenant : les variables du pli sont retirées.
        let flat = try #require(FoldState(hinge: .fullyOpen, fold: nil)).script
        #expect(flat.contains(#"{"posture":"flat","fold":null}"#))
        #expect(flat.contains("removeProperty('--fold-' + k)"))
    }

    @Test("Barre du bas et barre verticale : mêmes libellés, pastilles et « Bientôt »")
    @MainActor
    func barItemsAreShared() {
        let tabs = [
            TabBarState.Tab(id: "games", label: "Jeux", active: false, badge: "", soon: false),
            TabBarState.Tab(id: "events", label: "Événements", active: true, badge: "3", soon: true),
        ]
        let items = tabs.enumerated().map { NativeTabBar.item(for: $1, tag: $0) }
        NativeTabBar.refresh(items, with: tabs)
        #expect(items.map(\.title) == ["Jeux", "Événements"])
        #expect(items[0].badgeValue == "" && items[0].badgeColor == nil)
        #expect(items[1].badgeValue == "Bientôt" && items[1].badgeColor == .systemGray)
    }
}
