import Foundation
import Testing
@testable import Party

/// Messages directs (4.11) : conversation privée à deux, mêlée aux groupes dans Discussions.
struct DirectMessagesTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Liste : un message direct garde l'autre personne, sa photo et le blocage ; un groupe reste un groupe")
    func decodesDirectRow() throws {
        let row: ChatSummary = try decode("""
        {"id":"d1","name":"Léa","kind":"direct","user_id":"u-lea","photo":"https://x/lea.jpg","blocked":true,
         "member":true,"notify":"all","last":"Toi : Salut","last_at":"2026-11-04T10:00:00Z","unread":1}
        """)
        #expect(row.direct && row.userID == "u-lea" && row.photo == "https://x/lea.jpg" && row.blocked && row.notify == .all)
        let group: ChatSummary = try decode(#"{"id":"g1","name":"Les amis","kind":"group","notify":"mentions"}"#)
        #expect(!group.direct && group.userID == nil && !group.blocked)
        // Cache de la liste (encodé puis relu) : le message direct le reste.
        let again: ChatSummary = try JSONDecoder().decode(ChatSummary.self, from: JSONEncoder().encode(row))
        #expect(again == row)
    }

    @Test("Conversation directe : ni citation, ni @tout, ni @annonce ; l'autre personne et le blocage suivent")
    func directConversationHasNoTags() throws {
        let c: Conversation = try decode("""
        {"id":"d1","name":"Léa","direct":true,"user_id":"u-lea","photo":null,"blocked":false,"me":"u-me",
         "member":true,"admin":false,"notify":"all","can_name_admins":false,"organizer":false,"everyone":"staff",
         "reactions":["👍"],"members":[{"id":"u-lea","name":"Léa","photo":null,"admin":false,"creator":false},
                                    {"id":"u-me","name":"Boby","photo":null,"admin":false,"creator":false}],
         "messages":[]}
        """)
        #expect(c.isDirect && c.userID == "u-lea")
        #expect(c.mentions(in: "@Léa salut", me: "u-me").isEmpty)
        #expect(c.tagNote(for: "@annonce @tout") == nil)
        let draft = ChatsStore.draft(id: "m1", body: "@annonce", replyTo: nil, in: c)
        #expect(!draft.pinned && draft.announcement == nil)  // pas d'annonce à deux
        let kept = c.with(messages: [draft])
        #expect(kept.isDirect && kept.userID == "u-lea" && kept.messages.count == 1)
        let group: Conversation = try decode("""
        {"id":"g1","name":"Les amis","member":true,"admin":false,"notify":"mentions","can_name_admins":false,
         "reactions":[],"members":[],"messages":[]}
        """)
        #expect(!group.isDirect)
    }

    @Test("Temps réel : une conversation directe écoute direct_messages ; la liste écoute aussi les messages directs")
    func realtimeForDirect() throws {
        func tables(_ join: [String: Any]) throws -> [[String: Any]] {
            let payload = try #require(join["payload"] as? [String: Any])
            let config = try #require(payload["config"] as? [String: Any])
            return try #require(config["postgres_changes"] as? [[String: Any]])
        }
        let direct = try tables(ChatRealtime.joinMessage(topic: "t", filter: "chat_id=eq.d1", token: "jwt", ref: "1", direct: true))
        #expect(direct.map { $0["table"] as? String } == ["direct_messages", "direct_message_reactions"])
        #expect(direct[0]["filter"] as? String == "chat_id=eq.d1")
        let list = try tables(ChatRealtime.joinMessage(topic: "t", filter: nil, token: "jwt", ref: "1"))
        #expect(list.map { $0["table"] as? String } == ["group_messages", "group_message_reactions", "direct_messages"])
    }

    @Test("Préférences : l'interrupteur « Messages directs » s'applique et se lit")
    @MainActor
    func directMessagesSwitch() throws {
        let p: EventNotificationPrefs = try decode("""
        {"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,
         "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false}
        """)
        #expect(p.directMessages == nil)  // avant la migration : reçus
        #expect(SettingsStore.applying("direct_messages", false, to: p).directMessages == false)
    }

    @Test("Lien d'une notification de message direct : même forme que les groupes (?tab=chats&chat=)")
    func notificationLink() throws {
        let url = try #require(URL(string: "https://partytest.bobycharbon.ch/?tab=chats&chat=22222222-2222-2222-2222-222222222222"))
        #expect(WebModel.chatRequested(in: url) == "22222222-2222-2222-2222-222222222222")
    }
}
