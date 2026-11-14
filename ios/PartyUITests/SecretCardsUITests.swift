import XCTest
import UIKit

/// Pyramide (avis 4c55c231a4d2) : une capture d'écran du panneau des cartes à mémoriser est noire.
/// La page confie 4 cartes à l'app (PartyNative.secret.update, ici par PARTY_DEBUG_JS), puis on prend une capture comme
/// le système et on la garde dans le fichier TEST_RUNNER_PARTY_SECRET_SHOT (`xcodebuild test … TEST_RUNNER_PARTY_SECRET_SHOT=/chemin.png`).
final class SecretCardsUITests: XCTestCase {
    func testTheCardsPanelIsHiddenFromScreenshots() throws {
        let out = ProcessInfo.processInfo.environment["PARTY_SECRET_SHOT"] ?? ""
        try XCTSkipIf(out.isEmpty, "Capture du panneau : chemin TEST_RUNNER_PARTY_SECRET_SHOT requis")
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = """
        setTimeout(function () { window.PartyNative && PartyNative.secret.update({ cards: ["TH", "AS", "KD", "7C"], title: "Tes cartes · mémorise-les" }); }, 3000);
        """
        app.launch()
        let panel = app.descendants(matching: .any)["secret-cards"]
        XCTAssertTrue(panel.waitForExistence(timeout: 25), "le panneau des cartes n'apparaît pas")
        sleep(1)
        let shot = XCUIScreen.main.screenshot()
        try shot.pngRepresentation.write(to: URL(fileURLWithPath: out))
        // Au milieu du panneau, sur la capture : du noir, pas les cartes blanches qu'on voit à l'écran.
        let frame = panel.frame
        let points = (1...3).map { CGPoint(x: frame.minX + frame.width * CGFloat($0) / 4, y: frame.midY) }
        for point in points {
            XCTAssertLessThan(try brightness(of: shot.image, at: point), 0.1, "les cartes sont visibles sur la capture")
        }
    }

    /// Luminosité (0 noir … 1 blanc) d'un point de la capture, en points d'écran.
    private func brightness(of image: UIImage, at point: CGPoint) throws -> CGFloat {
        let cg = try XCTUnwrap(image.cgImage)
        let scale = CGFloat(cg.width) / image.size.width
        var pixel = [UInt8](repeating: 0, count: 4)
        let space = CGColorSpaceCreateDeviceRGB()
        let ctx = try XCTUnwrap(CGContext(data: &pixel, width: 1, height: 1, bitsPerComponent: 8, bytesPerRow: 4, space: space,
                                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue))
        ctx.draw(cg, in: CGRect(x: -point.x * scale, y: -(CGFloat(cg.height) - point.y * scale), width: CGFloat(cg.width), height: CGFloat(cg.height)))
        return (CGFloat(pixel[0]) + CGFloat(pixel[1]) + CGFloat(pixel[2])) / (3 * 255)
    }
}
