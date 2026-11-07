import UIKit
import XCTest
@testable import Party

/// Taille du texte d'iOS (Dynamic Type) dans la vue web (campagne 2, rapport 09) : le texte des pages suit la
/// préférence, borné pour que les mises en page tiennent.
final class TextScaleTests: XCTestCase {
    func testDefaultSizeKeepsTheTextAsIs() {
        XCTAssertEqual(TextScale.percent(for: .large), 100)
    }

    func testLargerTextGrowsAndSmallerTextShrinks() {
        XCTAssertGreaterThan(TextScale.percent(for: .extraLarge), 100)
        XCTAssertGreaterThan(TextScale.percent(for: .extraExtraExtraLarge), TextScale.percent(for: .extraLarge))
        XCTAssertLessThan(TextScale.percent(for: .small), 100)
    }

    func testAccessibilitySizesAreCappedSoLayoutsHold() {
        XCTAssertEqual(TextScale.factor(for: .accessibilityExtraExtraExtraLarge), TextScale.maxScale)
        XCTAssertGreaterThanOrEqual(TextScale.factor(for: .extraSmall), TextScale.minScale)
    }

    func testTheScriptRunsInEveryFrameAndSetsTheRootTextSize() {
        let script = TextScale.userScript(percent: 135)
        XCTAssertFalse(script.isForMainFrameOnly)  // l'iframe du module Événements aussi
        XCTAssertEqual(script.injectionTime, .atDocumentStart)
        XCTAssertTrue(script.source.contains("-webkit-text-size-adjust: ' + p + '%"))
        XCTAssertTrue(script.source.contains("__partyTextScale(135)"))
        XCTAssertTrue(script.source.contains("addEventListener('load'"))  // jamais avant le chargement (page blanche)
    }
}
