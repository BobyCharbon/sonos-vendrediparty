import CoreGraphics
import Foundation
import SwiftUI
import Testing
@testable import Party

/// Bulle de Zicou native (avis 3cd6d282745b, 08.11) : description de la page, six emplacements, glisser.
struct ZicouBubbleTests {
    private let size = CGSize(width: 390, height: 760)
    private let insets = EdgeInsets(top: 47, leading: 0, bottom: 0, trailing: 0)
    private let side = ZicouBubble.side

    @Test("La description de la page (zicou-home.js) se lit, message du jour compris")
    func decodesThePageState() throws {
        let state = try #require(ZicouBubbleState(message: [
            "visible": true, "stage": "adult", "emotion": "hungry", "red": true, "asleep": false,
            "label": "Zicou : a faim, il a besoin de toi", "hint": "Psst… ton cadeau du jour ! 🎁",
        ] as [String: Any]))
        #expect(state.visible && state.red && state.emotion == "hungry")
        #expect(state.hint == "Psst… ton cadeau du jour ! 🎁")
        let quiet = try #require(ZicouBubbleState(message: [
            "visible": false, "stage": "egg", "emotion": "egg", "red": false, "asleep": false, "label": "Zicou", "hint": NSNull(),
        ] as [String: Any]))
        #expect(!quiet.visible && quiet.hint == nil)
        #expect(ZicouBubbleState(message: ["visible": "oui"]) == nil)   // autre chose : ignoré
    }

    @Test("Chaque emplacement reste dans l'écran, sous l'encoche et le titre", arguments: ZicouSpot.allCases)
    func spotsStayOnScreen(spot: ZicouSpot) {
        let c = spot.center(in: size, insets: insets, side: side)
        #expect(c.x - side / 2 >= ZicouBubble.margin && c.x + side / 2 <= size.width - ZicouBubble.margin)
        #expect(c.y - side / 2 >= insets.top + ZicouBubble.topClearance && c.y + side / 2 <= size.height - ZicouBubble.margin)
    }

    @Test("Le glisser pose la bulle sur l'emplacement le plus proche du doigt lâché")
    func dragSnapsToNearestSpot() {
        let nearest = { (x: CGFloat, y: CGFloat) in ZicouSpot.nearest(to: CGPoint(x: x, y: y), in: size, insets: insets, side: side) }
        #expect(nearest(20, 700) == .bottomLeading)
        #expect(nearest(380, 740) == .bottomTrailing)
        #expect(nearest(10, 130) == .topLeading)
        #expect(nearest(370, 400) == .middleTrailing)
        #expect(nearest(-200, 420) == .middleLeading)     // lancé hors de l'écran : le bord le plus proche
    }

    @Test("Chaque emplacement a son action VoiceOver")
    func everySpotHasAnAccessibleName() {
        let names = Set(ZicouSpot.allCases.map(ZicouBubble.spotName))
        #expect(names.count == ZicouSpot.allCases.count)
        #expect(names.allSatisfy { $0.hasPrefix("Placer ") })
    }
}
