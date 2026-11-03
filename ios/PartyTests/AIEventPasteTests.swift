import UIKit
import UniformTypeIdentifiers
import XCTest
@testable import Party

/// Retour du 03.11 : une image collée (Safari, Messages, capture) arrive en pièce jointe dans « Créer avec l'IA »,
/// réduite comme les photos, 3 au plus avec un message clair.
@MainActor
final class AIEventPasteTests: XCTestCase {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private func image(_ width: CGFloat, _ height: CGFloat, color: UIColor = .systemPink) -> UIImage {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        return UIGraphicsImageRenderer(size: CGSize(width: width, height: height), format: format).image { context in
            color.setFill()
            context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        }
    }

    private func store() -> AIEventStore { AIEventStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil) }

    // ── Données du presse-papiers ──

    func testEachCopiedItemGivesOneImageWhateverItsFormat() throws {
        let png = try XCTUnwrap(image(20, 10).pngData())
        let jpeg = try XCTUnwrap(image(30, 30).jpegData(compressionQuality: 0.8))
        let items: [[String: Any]] = [
            [UTType.png.identifier: png, UTType.url.identifier: URL(string: "https://example.com/affiche.png")!],
            [UTType.jpeg.identifier: jpeg],
            [UTType.image.identifier: image(5, 5)],
        ]
        let found = AIEvent.pastedImages(fromItems: items)
        XCTAssertEqual(found.map(\.size), [CGSize(width: 20, height: 10), CGSize(width: 30, height: 30), CGSize(width: 5, height: 5)])
    }

    func testTextAndUnreadableDataAreNotImages() {
        let items: [[String: Any]] = [
            [UTType.utf8PlainText.identifier: "Raclette samedi"],
            [UTType.png.identifier: Data("pas une image".utf8)],
        ]
        XCTAssertTrue(AIEvent.pastedImages(fromItems: items).isEmpty)
    }

    func testImagesAreReadFromARealPasteboard() throws {
        let board = try XCTUnwrap(UIPasteboard(name: UIPasteboard.Name("party-test-\(UUID())"), create: true))
        defer { UIPasteboard.remove(withName: board.name) }
        board.images = [image(40, 20), image(10, 10)]
        XCTAssertEqual(AIEvent.pastedImages(from: board).count, 2)
        board.string = "juste du texte"
        XCTAssertTrue(AIEvent.pastedImages(from: board).isEmpty)
    }

    // ── Collage dans le champ de texte ──

    func testPastingAnImageInTheTextFieldAttachesItInsteadOfText() throws {
        let board = try XCTUnwrap(UIPasteboard(name: UIPasteboard.Name("party-test-\(UUID())"), create: true))
        defer { UIPasteboard.remove(withName: board.name) }
        let field = PasteImageTextView()
        field.pasteboard = board
        var received: [UIImage] = []
        field.onImages = { received += $0 }

        board.images = [image(50, 50)]
        XCTAssertTrue(field.canPerformAction(#selector(UIResponder.paste(_:)), withSender: nil))
        field.paste(nil)
        XCTAssertEqual(received.count, 1)
        XCTAssertEqual(field.text, "")
    }

    // ── Réduction et compression ──

    func testAPastedScreenshotIsReducedTo1600PixelsLikePhotos() throws {
        let shot = try XCTUnwrap(AIEvent.Shot(image(3200, 1000)))
        XCTAssertEqual(shot.thumbnail.size, CGSize(width: 1600, height: 500))
        XCTAssertEqual(shot.thumbnail.scale, 1)
        XCTAssertTrue(shot.dataURL.hasPrefix("data:image/jpeg;base64,"))
        XCTAssertLessThanOrEqual(shot.dataURL.count, AIEvent.Shot.maxBase64 + 30)
        let small = try XCTUnwrap(AIEvent.Shot(image(300, 200)))
        XCTAssertEqual(small.thumbnail.size, CGSize(width: 300, height: 200))  // jamais agrandie
    }

    func testAnEmptyImageIsRefused() {
        XCTAssertNil(AIEvent.Shot(UIImage()))
    }

    // ── Limite de 3 images ──

    func testSeveralImagesPastedAtOnceStopAtThreeWithAClearMessage() {
        let store = store()
        XCTAssertEqual(store.attach([image(10, 10), image(10, 10)]), 2)
        XCTAssertNil(store.notice)
        XCTAssertEqual(store.attach([image(10, 10), image(10, 10), image(10, 10)]), 1)
        XCTAssertEqual(store.images.count, AIEvent.maxShots)
        XCTAssertEqual(store.notice, "3 images au plus : 2 images n'ont pas été ajoutées.")
        XCTAssertEqual(store.attach([image(10, 10)]), 0)
        XCTAssertEqual(store.notice, AIEvent.fullNotice)
        store.detach(store.images[0])
        XCTAssertNil(store.notice)
        XCTAssertEqual(store.images.count, 2)
    }

    func testOneImageTooManyIsSaidInTheSingular() {
        XCTAssertEqual(AIEvent.overflowNotice(dropped: 1), "3 images au plus : 1 image n'a pas été ajoutée.")
    }

    func testAnUnreadableImageIsSaid() {
        let store = store()
        XCTAssertEqual(store.attach([UIImage()]), 0)
        XCTAssertEqual(store.notice, AIEvent.unreadableNotice)
    }
}
