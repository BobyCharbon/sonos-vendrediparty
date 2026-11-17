// FICHIER TEMPORAIRE de l'agent C (fil de messages) : remplace les API écrites en parallèle par l'agent F
// (ChatsStore / Conversation) pour compiler seul. L'intégrateur le SUPPRIME à la fusion.
import Foundation

extension ChatsStore {
    func loadOlder() async {}
    func markRead() async {}
    var jumpTo: String? {
        get { nil }
        set {}
    }
}

extension Conversation {
    var unread: Int? { nil }
    var canWrite: Bool? { nil }
}
