import SwiftUI

// FICHIER TEMPORAIRE de l'agent E : bouchons des API que l'agent F écrit en parallèle (contrat « iPhone, données »).
// À SUPPRIMER à la fusion, dès que ChatModels.swift / ChatsStore.swift de F sont là (mêmes noms, mêmes types).

enum ChatNotifyLevel: String, Codable { case all, mentions, none }

struct ChatMediaItem: Codable, Identifiable {
    let messageId: String
    let kind: String
    let url: String
    let at: String
    let authorName: String
    var text: String?
    var id: String { messageId }
}

struct ChatSearchResult: Codable, Identifiable {
    let messageId: String
    let at: String
    let authorName: String
    let snippet: String
    var id: String { messageId }
}

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
    }

    var level: ChatNotifyLevel? { nil }
    var mutedUntil: String? { nil }
    var unread: Int? { nil }
    var writeMode: String? { nil }
    var description: String? { nil }
    var canWrite: Bool? { nil }
    var eventCard: EventCard? { nil }
}

extension ChatsStore {
    func setLevel(_ level: ChatNotifyLevel) async {}
    func mute(until: Date?) async {}
    func markRead() async {}
    func saveSettings(write: String?, description: String?) async -> Bool { false }
    func media(before: String? = nil) async -> [ChatMediaItem] { [] }
    func search(_ q: String) async -> [ChatSearchResult] { [] }
    func loadOlder() async {}
    var jumpTo: String? { get { nil } set {} }
    var isMuted: Bool { false }
    var effectiveLevel: ChatNotifyLevel { .mentions }
}
