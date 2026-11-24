import UIKit
import XCTest
@testable import Party

/// Souvenirs (avis 74d36b93e7bd, 24.11) : pont de la page, toucher des notifications, textes de l'appareil et de la story,
/// refus lisibles de la base, envoi de la photo (JPEG, Bearer) et relais (souvenir_*), bulles des Discussions.
@MainActor
final class SouvenirsTests: XCTestCase {
    private static let event = "0a0b0c0d-0000-4000-8000-000000000024"

    // MARK: Pont et liens

    func testBridgeAcceptsCameraStoryAndSaveOnly() {
        XCTAssertEqual(SouvenirBridgeRequest.parse(["action": "camera", "eventId": Self.event.uppercased()]), .open(.camera(Self.event)))
        XCTAssertEqual(SouvenirBridgeRequest.parse(["action": "story", "eventId": Self.event]), .open(.story(Self.event)))
        XCTAssertNil(SouvenirBridgeRequest.parse(["action": "camera", "eventId": "../admin"]))
        XCTAssertNil(SouvenirBridgeRequest.parse(["action": "delete", "eventId": Self.event]))
        XCTAssertNil(SouvenirBridgeRequest.parse("camera:\(Self.event)"))
        let signed = "https://ewromqfsmcqsthftyhzm.supabase.co/storage/v1/object/sign/souvenirs/\(Self.event)/a/b.jpg?token=x"
        XCTAssertEqual(SouvenirBridgeRequest.parse(["action": "save", "url": signed]), .save(URL(string: signed)!))
        // Jamais une autre adresse ni un autre compartiment.
        XCTAssertNil(SouvenirBridgeRequest.parse(["action": "save", "url": "https://evil.example/storage/v1/object/sign/souvenirs/x.jpg"]))
        XCTAssertNil(SouvenirBridgeRequest.parse(["action": "save", "url": "https://x.supabase.co/storage/v1/object/sign/chat-photos/x.jpg"]))
        XCTAssertNil(SouvenirBridgeRequest.parse(["action": "save", "url": "http://x.supabase.co/storage/v1/object/sign/souvenirs/x.jpg"]))
    }

    func testTheBridgeScriptIsInstalledInThePage() {
        XCTAssertTrue(SouvenirsBridge.script.contains("camera: function (id)"))
        XCTAssertTrue(SouvenirsBridge.script.contains("story: function (id)"))
        XCTAssertTrue(SouvenirsBridge.script.contains("save: function (url)"))
        XCTAssertTrue(SouvenirsBridge.script.contains("messageHandlers.partySouvenirs"))
    }

    func testRevealedNotificationOpensTheStoryAndReviewStaysInThePage() throws {
        let revealed = try XCTUnwrap(URL(string: "https://party.test/?tab=events&event=\(Self.event)&souvenirs=1"))
        XCTAssertEqual(SouvenirLinks.storyRequested(in: revealed), Self.event)
        XCTAssertEqual(SouvenirLinks.withoutStory(revealed).absoluteString, "https://party.test/?tab=events&event=\(Self.event)")
        let review = try XCTUnwrap(URL(string: "https://party.test/?tab=events&event=\(Self.event)&souvenirs=review"))
        XCTAssertNil(SouvenirLinks.storyRequested(in: review))
        XCTAssertEqual(SouvenirLinks.withoutStory(review), review)  // la fiche s'ouvre en relecture (page)
        XCTAssertNil(SouvenirLinks.storyRequested(in: URL(string: "https://party.test/?tab=events&event=x&souvenirs=1")!))
    }

    func testThePageIsToldWhenTheScreenCloses() throws {
        let script = try XCTUnwrap(SouvenirLinks.changedScript(Self.event.uppercased()))
        XCTAssertTrue(script.contains("PartySouvenirs.changed(id)") && script.contains("'\(Self.event)'"))
        XCTAssertTrue(script.contains("eventsFrame"))  // le module Événements tourne dans un cadre
        XCTAssertNil(SouvenirLinks.changedScript("');alert(1);('"))
    }

    // MARK: Textes

    func testPosesVisibleTimeAndCountdown() {
        XCTAssertEqual(SouvenirText.poses(3), "3 poses")
        XCTAssertEqual(SouvenirText.poses(1), "1 pose")
        XCTAssertEqual(SouvenirText.poses(0), "0 pose")
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        let iso = { (d: Date) in ISO8601DateFormatter().string(from: d) }
        XCTAssertEqual(SouvenirText.visibleFor(until: iso(now.addingTimeInterval(23.5 * 3600)), now: now), "Visible encore 23 h")
        XCTAssertEqual(SouvenirText.visibleFor(until: iso(now.addingTimeInterval(40 * 60 + 5)), now: now), "Visible encore 40 min")
        XCTAssertEqual(SouvenirText.countdown(to: iso(now.addingTimeInterval(13.5 * 3600)), now: now), "13:30:00")
        XCTAssertEqual(SouvenirText.countdown(to: iso(now.addingTimeInterval(-10)), now: now), "00:00:00")
    }

    func testPostgresTimestampsAreRead() {
        XCTAssertNotNil(SouvenirDates.parse("2026-11-24T21:15:03.123456+00:00"))
        XCTAssertNotNil(SouvenirDates.parse("2026-11-24 21:15:03.12+01"))
        XCTAssertNotNil(SouvenirDates.parse("2026-11-24T21:15:03Z"))
        XCTAssertEqual(SouvenirDates.parse("2026-11-24T21:15:03.999+00:00"), SouvenirDates.parse("2026-11-24T21:15:03Z"))
        XCTAssertNil(SouvenirDates.parse("demain"))
    }

    func testTheCameraSaysWhatHappensToThePhotos() {
        XCTAssertTrue(SouvenirText.cameraPromise(keep: true).contains("pendant 24 h"))
        XCTAssertTrue(SouvenirText.cameraPromise(keep: true).contains("garder ses préférées"))
        // Enregistrement éteint : il faut le souligner, rien ne reste.
        XCTAssertTrue(SouvenirText.cameraPromise(keep: false).contains("rien ne sera gardé"))
    }

    func testRefusalsAreReadable() {
        XCTAssertEqual(SouvenirRefusal(code: "full", detail: "tu as déjà pris tes 3 photos").message, "Tu as déjà pris tes 3 photos.")
        XCTAssertEqual(SouvenirRefusal(code: "closed", detail: "l'appareil photo est ouvert du début de l'événement à 2 h après sa fin").message,
                       "L'appareil photo est ouvert du début de l'événement à 2 h après sa fin")
        XCTAssertTrue(SouvenirRefusal(code: "profile_required", detail: "").message.contains("Complète ton profil"))
        XCTAssertTrue(SouvenirRefusal(code: "terms_required", detail: "").message.contains("conditions d'utilisation"))
        XCTAssertEqual(SouvenirText.closedCamera(SouvenirCounter(enabled: true, phase: "open", left: 0, taken: 3, canTake: false)),
                       "Tes 3 photos sont au labo. Profite de la soirée, on s'occupe du reste ✨")
        XCTAssertTrue(SouvenirText.closedCamera(SouvenirCounter(enabled: true, phase: "soon", left: 3, taken: 0, canTake: false, member: true))
            .contains("début de l'événement"))
        XCTAssertTrue(SouvenirText.closedCamera(SouvenirCounter(enabled: true, phase: "open", left: 0, taken: 0, canTake: false, member: false))
            .contains("Présent ou Peut-être"))
    }

    func testReportReasonsStartWithMyImage() {
        XCTAssertEqual(SouvenirReportReason.allCases.first, .myImage)
        XCTAssertEqual(SouvenirReportReason.myImage.rawValue, "my_image")
        XCTAssertEqual(SouvenirReportReason.myImage.label, "Je suis sur la photo et je ne veux pas qu'elle soit montrée")
    }

    // MARK: Photo envoyée

    func testThePhotoIsARedrawnJPEGOfAtMost1600px() throws {
        let image = UIGraphicsImageRenderer(size: CGSize(width: 4032, height: 3024)).image { ctx in
            UIColor.orange.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 4032, height: 3024))
        }
        let jpeg = try XCTUnwrap(SouvenirCameraSensor.jpeg(image))
        XCTAssertEqual(Array(jpeg.prefix(2)), [0xFF, 0xD8])  // JPEG
        let back = try XCTUnwrap(UIImage(data: jpeg))
        XCTAssertEqual(max(back.size.width * back.scale, back.size.height * back.scale), 1600)
        let test = try XCTUnwrap(SouvenirCameraSensor.testImage(front: false))
        XCTAssertEqual(Array(test.prefix(2)), [0xFF, 0xD8])
    }

    // MARK: Serveur simulé

    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private final class SignedIn: WebStorage {
        func guestIdentity() async -> GuestIdentity? { nil }
        func readLocal(_ key: String) async -> String? { nil }
        func writeLocal(_ key: String, _ value: String?) {}
        func shareSession() async {}
        func refreshFeedbackBadge() {}
        func openInPage(_ url: URL) {}
        func accountToken() async -> String? { "jeton" }
        func accountChanged() async {}
        func storeSession(key: String, json: String) async {}
        func clearSession() async {}
    }

    /// Serveur simulé : rend la réponse de `SouvenirsServer.reply` et retient chaque requête.
    final class SouvenirsServer: URLProtocol {
        nonisolated(unsafe) static var requests: [(path: String, query: String?, auth: String?, body: Data?)] = []
        nonisolated(unsafe) static var reply: (Int, String) = (200, "{}")

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

        override func startLoading() {
            var body = request.httpBody
            if body == nil, let stream = request.httpBodyStream {
                stream.open()
                var data = Data()
                var buffer = [UInt8](repeating: 0, count: 4096)
                while stream.hasBytesAvailable {
                    let n = stream.read(&buffer, maxLength: buffer.count)
                    if n <= 0 { break }
                    data.append(buffer, count: n)
                }
                stream.close()
                body = data
            }
            Self.requests.append((request.url?.path ?? "", request.url?.query, request.value(forHTTPHeaderField: "Authorization"), body))
            let (status, json) = Self.reply
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(json.utf8))
            client?.urlProtocolDidFinishLoading(self)
        }

        override func stopLoading() {}
    }

    private let web = SignedIn()

    private func makeStore(_ status: Int, _ json: String) -> SouvenirsStore {
        SouvenirsServer.requests = []
        SouvenirsServer.reply = (status, json)
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies(), protocolClasses: [SouvenirsServer.self])
        return SouvenirsStore(api: api, web: web, protocolClasses: [SouvenirsServer.self])
    }

    func testThePhotoGoesToTheServerAsRawJPEGWithTheBearerToken() async throws {
        let store = makeStore(200, #"{"id":"p1","path":"e/u/p1.jpg","taken":1,"left":2,"cancel_until":"2026-11-24T21:15:08+00:00"}"#)
        let taken = try await store.upload(Data([0xFF, 0xD8, 0xFF]), event: Self.event)
        XCTAssertEqual(taken, SouvenirTaken(id: "p1", taken: 1, left: 2, cancelUntil: "2026-11-24T21:15:08+00:00"))
        let sent = try XCTUnwrap(SouvenirsServer.requests.first)
        XCTAssertEqual(sent.path, "/api/account/souvenirs/photo")
        XCTAssertEqual(sent.query, "event_id=\(Self.event)")
        XCTAssertEqual(sent.auth, "Bearer jeton")
        XCTAssertEqual(sent.body, Data([0xFF, 0xD8, 0xFF]))
    }

    func testRefusalsKeepTheirCode() async {
        for (status, code) in [(409, "full"), (409, "closed"), (403, "profile_required"), (403, "terms_required")] {
            let store = makeStore(status, #"{"code":"\#(code)","detail":"raison de la base"}"#)
            do {
                _ = try await store.upload(Data([1]), event: Self.event)
                XCTFail("refus attendu : \(code)")
            } catch let refusal as SouvenirRefusal {
                XCTAssertEqual(refusal.code, code)
            } catch {
                XCTFail("refus attendu : \(error)")
            }
        }
    }

    func testRelayCallsAndStoryDecoding() async throws {
        let story = #"""
        {"result":{"event_id":"e1","title":"Chez Maé","keep":true,"until":"2026-11-25T23:00:00+00:00","photos":[
          {"id":"p1","event_id":"e1","path":"a","taken_at":"2026-11-20T20:31:00.5+00:00","mine":false,
           "author":{"id":"u2","name":"Inès","avatar_url":null,"photo":null},"kept":false,"can_keep":true,"url":"https://x.supabase.co/s"}]}}
        """#
        let store = makeStore(200, story)
        let s = try await store.story(Self.event)
        XCTAssertEqual(s.title, "Chez Maé")
        XCTAssertEqual(s.photos.first?.author?.label, "Inès")
        XCTAssertEqual(s.photos.first?.canKeep, true)
        let body = try XCTUnwrap(SouvenirsServer.requests.first?.body)
        let sent = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(sent["fn"] as? String, "souvenir_story")
        XCTAssertEqual(sent["token"] as? String, "jeton")
        XCTAssertEqual((sent["args"] as? [String: String])?["e"], Self.event)

        let keep = makeStore(200, #"{"result":{"kept":true}}"#)
        let kept = try await keep.setKept("p1", true)
        XCTAssertTrue(kept)
        let keepBody = try XCTUnwrap(SouvenirsServer.requests.first?.body)
        let keepSent = try XCTUnwrap(JSONSerialization.jsonObject(with: keepBody) as? [String: Any])
        XCTAssertEqual(keepSent["fn"] as? String, "souvenir_keep")

        let report = makeStore(200, #"{"result":"r1"}"#)
        try await report.report("p1", reason: .myImage)
        let reportBody = try XCTUnwrap(SouvenirsServer.requests.first?.body)
        let reportSent = try XCTUnwrap(JSONSerialization.jsonObject(with: reportBody) as? [String: Any])
        XCTAssertEqual(reportSent["fn"] as? String, "report_content")
        XCTAssertEqual(reportSent["args"] as? [String: String], ["p_kind": "souvenir", "p_target": "p1", "p_reason": "my_image"])
    }

    func testBubblesWaitingAndStory() async {
        let store = makeStore(200, #"""
        {"result":[{"event_id":"e1","title":"Chez Maé","phase":"story","until":"2026-11-25T23:00:00+00:00","count":31,"seen":false},
                   {"event_id":"e2","title":"Bowling","phase":"waiting","reveal_at":"2026-11-25T22:00:00+00:00","until":"x","count":4,"seen":false},
                   {"event_id":"e3","title":"Ancienne","until":"x","count":2,"seen":true}]}
        """#)
        await store.refreshBubbles()
        XCTAssertEqual(store.bubbles.map(\.id), ["e1", "e2", "e3"])
        XCTAssertEqual(store.bubbles.map(\.waiting), [false, true, false])  // sans « phase » (base d'avant) : une story
        var opened: String?
        store.openStory = { opened = $0 }
        store.openStory("e1")
        XCTAssertEqual(opened, "e1")
    }
}
