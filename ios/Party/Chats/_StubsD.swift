// TEMPORAIRE (agent D) : à SUPPRIMER à la fusion. Remplace, pour compiler seul, ce qu'écrivent en parallèle
// l'agent F (ChatNotifyLevel, Conversation.eventCard / level / mutedUntil, ChatsStore.setLevel / mute / isMuted /
// effectiveLevel) et l'agent C (ConversationView(store:group:embedded:)).
import Foundation

enum ChatNotifyLevel: String, Codable { case all, mentions, none }

extension Conversation {
    struct EventCard: Codable, Equatable {
        var title: String?
        var startsAt: String?
        var endsAt: String?
        var place: String?
        var cover: String?
        var going: Int?
        var maybe: Int?
        var organizerName: String?

        enum CodingKeys: String, CodingKey {
            case title, place, cover, going, maybe
            case startsAt = "starts_at", endsAt = "ends_at", organizerName = "organizer_name"
        }
    }

    var eventCard: EventCard? { nil }
    var level: ChatNotifyLevel? { nil }
    var mutedUntil: String? { nil }
}

extension ChatsStore {
    func setLevel(_ level: ChatNotifyLevel) async {}
    func mute(until: Date?) async {}
    var isMuted: Bool { false }
    var effectiveLevel: ChatNotifyLevel { .mentions }
}

extension ConversationView {
    init(store: ChatsStore, group: String, embedded: Bool) { self.init(store: store, group: group) }
}
