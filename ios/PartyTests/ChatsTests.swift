import Foundation
import Testing
import UIKit
@testable import Party

/// Discussions natives (avis n°10) : réponses du serveur, lien d'une notification, dates, photos.
struct ChatsTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Liste : non lus, dernier message, réglage inconnu ramené à « mentions »")
    func decodesList() throws {
        let chat: ChatSummary = try decode("""
        {"id":"g1","name":"Les amis","member":true,"notify":"bizarre","last":"Léa : Salut","last_at":"2026-10-29T10:00:00.123Z","unread":3}
        """)
        #expect(chat.notify == .mentions && chat.unread == 3 && chat.last == "Léa : Salut")
        let empty: ChatSummary = try decode(#"{"id":"g2","name":"Vide","notify":"none","last":null,"last_at":null}"#)
        #expect(empty.unread == 0 && empty.lastAt == nil && empty.notify == .none && !empty.member)
    }

    @Test("Conversation : réponse, réactions, message supprimé, dernier épinglé en bandeau")
    func decodesConversation() throws {
        let c: Conversation = try decode("""
        {"id":"g1","name":"Les amis","member":true,"admin":true,"notify":"all","can_name_admins":false,
         "reactions":["👍","❤️"],"members":[{"id":"u1","name":"Léa","photo":null,"admin":false,"creator":true}],
         "messages":[
          {"id":"m1","author":"u1","author_name":"Léa","author_photo":null,"mine":false,"at":"2026-10-29T10:00:00Z","edited":false,
           "body":"Tu viens ?","deleted":false,"photo":null,"pinned":true,"reply":null,"reactions":[{"emoji":"👍","count":2,"mine":true}]},
          {"id":"m2","author":"u2","author_name":"Boby","author_photo":null,"mine":true,"at":"2026-10-29T10:01:00Z","edited":true,
           "body":"","deleted":false,"photo":"https://x/p.jpg","pinned":false,"reply":{"name":"Léa","text":"Tu viens ?"},"reactions":[]},
          {"id":"m3","author":"u1","author_name":"Léa","author_photo":null,"mine":false,"at":"2026-10-29T10:02:00Z","edited":false,
           "body":"Message supprimé par un admin","deleted":true,"photo":null,"pinned":false,"reply":null,"reactions":[]}]}
        """)
        #expect(c.pinned?.id == "m1")
        #expect(c.messages[0].reactions == [.init(emoji: "👍", count: 2, mine: true)])
        #expect(c.messages[1].preview == "📷 Photo" && c.messages[1].reply?.name == "Léa")
        #expect(c.messages[2].deleted && c.messages[2].body == "Message supprimé par un admin")
        #expect(c.messages[0].date != nil && c.members.first?.creator == true)
    }

    @Test("Infos du groupe : le numéro montré dans le groupe devient un lien d'appel, rien sinon")
    func callLinks() throws {
        let m: Conversation.Member = try decode(#"{"id":"u1","name":"Léa","photo":null,"admin":false,"creator":false,"phone":"+41790000001"}"#)
        #expect(m.call?.absoluteString == "tel:+41790000001")
        let hidden: Conversation.Member = try decode(#"{"id":"u2","name":"Tom","photo":null,"admin":false,"creator":false}"#)
        #expect(hidden.phone == nil && hidden.call == nil)
        let odd: Conversation.Member = try decode(#"{"id":"u3","name":"X","photo":null,"admin":false,"creator":false,"phone":"tel:evil"}"#)
        #expect(odd.call == nil)
    }

    @Test("Liens uniques d'un groupe : état lisible (en attente, utilisé par…, expiré, annulé)")
    func inviteLinkStates() throws {
        let links: [InviteLinkState] = try decode("""
        [{"token":"a","status":"pending","used_by":null,"created_at":"2026-10-30T07:00:00Z","expires_at":"2026-11-06T07:00:00Z","used_at":null},
         {"token":"b","status":"used","used_by":"Léa","created_at":"2026-10-30T07:00:00Z","expires_at":"2026-11-06T07:00:00Z","used_at":"2026-10-30T08:00:00Z"},
         {"token":"c","status":"expired","used_by":null,"created_at":"2026-10-20T07:00:00Z","expires_at":"2026-10-27T07:00:00Z","used_at":null},
         {"token":"d","status":"revoked","used_by":null,"created_at":"2026-10-30T07:00:00Z","expires_at":"2026-11-06T07:00:00Z","used_at":null}]
        """)
        #expect(links.map(\.label) == ["En attente", "Utilisé par Léa", "Expiré", "Annulé"])
    }

    @Test("Notification : ?tab=chats&chat=<groupe> ouvre la conversation, rien d'autre")
    func readsNotificationLink() {
        let id = "11111111-2222-3333-4444-555555555555"
        #expect(WebModel.chatRequested(in: URL(string: "https://party.bobycharbon.ch/?tab=chats&chat=\(id.uppercased())")!) == id)
        #expect(WebModel.chatRequested(in: URL(string: "https://party.bobycharbon.ch/?tab=events&event=\(id)")!) == nil)
        #expect(WebModel.chatRequested(in: URL(string: "https://party.bobycharbon.ch/?tab=chats&chat=../admin")!) == nil)
        #expect(WebModel.chatRequested(in: URL(string: "https://party.bobycharbon.ch/?tab=chats")!) == nil)
    }

    @Test("Dates de la liste : heure aujourd'hui, « hier », sinon jour.mois")
    func shortDates() {
        let now = ChatDates.parse("2026-10-29T15:00:00Z")!
        #expect(ChatDates.short("2026-10-28T12:00:00Z", now: now) == "hier")
        #expect(ChatDates.short("2026-10-20T12:00:00Z", now: now).contains("20"))
        #expect(!ChatDates.short("2026-10-29T14:00:00.5Z", now: now).isEmpty)
        #expect(ChatDates.short(nil) == "" && ChatDates.short("n'importe quoi") == "")
    }

    @Test("Photo : réduite à 1600 px au plus, en JPEG")
    func shrinksPhotos() throws {
        let big = UIGraphicsImageRenderer(size: CGSize(width: 3200, height: 1600), format: {
            let f = UIGraphicsImageRendererFormat(); f.scale = 1; return f
        }()).image { ctx in UIColor.red.setFill(); ctx.fill(CGRect(x: 0, y: 0, width: 3200, height: 1600)) }
        let jpeg = try #require(ChatPhoto.jpeg(from: big))
        let back = try #require(UIImage(data: jpeg))
        #expect(back.size.width == 1600 && back.size.height == 800)
        #expect(jpeg.starts(with: [0xFF, 0xD8, 0xFF]))
    }
}
