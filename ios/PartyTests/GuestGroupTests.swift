import Foundation
import Testing
@testable import Party

/// « Réunir les invités dans un groupe » (17.11) : bandeau « Tu es dans le groupe X · Quitter » de la discussion native,
/// et l'interrupteur de la notification « Tu es dans le groupe X ».
struct GuestGroupTests {
    private static let conversation = """
    {"id":"g1","name":"Raclette chez Ludo","member":true,"admin":false,"notify":"mentions","can_name_admins":false,
     "reactions":["👍"],"members":[],"messages":[],
     "join_note":{"event_id":"e1","event_title":"Raclette chez Ludo","group_name":"Raclette chez Ludo","owner":"Ludo","creator":false}}
    """

    @Test("Le serveur rend le bandeau d'entrée : décodé, gardé quand la conversation change de messages")
    func decodesTheJoinNote() throws {
        let c = try JSONDecoder().decode(Conversation.self, from: Data(Self.conversation.utf8))
        #expect(c.joinNote?.groupName == "Raclette chez Ludo" && c.joinNote?.owner == "Ludo" && c.joinNote?.creator == false)
        #expect(c.with(messages: []).joinNote == c.joinNote)
        #expect(ConversationView.joinLine(c.joinNote!) == "Ajouté avec ta réponse à « Raclette chez Ludo » de Ludo")
    }

    @Test("Ancien serveur (sans join_note) : pas de bandeau, la discussion s'ouvre")
    func oldServerHasNoNote() throws {
        let json = """
        {"id":"g1","name":"Raclette chez Ludo","member":true,"admin":false,"notify":"mentions","can_name_admins":false,
         "reactions":["👍"],"members":[],"messages":[]}
        """
        let c = try JSONDecoder().decode(Conversation.self, from: Data(json.utf8))
        #expect(c.joinNote == nil && c.name == "Raclette chez Ludo")
    }

    @Test("Sans organisateur nommé : la phrase reste juste")
    func lineWithoutOwner() {
        let note = Conversation.JoinNote(eventTitle: "Paintball", groupName: "Les footeux", owner: nil, creator: nil)
        #expect(ConversationView.joinLine(note) == "Ajouté avec ta réponse à « Paintball »")
    }

    @Test("Réglages › Notifications : « Ajouté à un groupe avec ta réponse » a son interrupteur")
    @MainActor
    func theNotificationHasItsSwitch() throws {
        let p = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(#"""
        {"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,
         "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false}
        """#.utf8))
        #expect(p.groupAdded == nil)  // avant la migration : reçue (interrupteur allumé)
        #expect(SettingsStore.applying("group_added", false, to: p).groupAdded == false)
        let off = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(#"""
        {"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,
         "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false,
         "group_added": false}
        """#.utf8))
        #expect(off.groupAdded == false)
    }
}
