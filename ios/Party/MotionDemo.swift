#if DEBUG
import SwiftUI

/// Simulateur : SIMCTL_CHILD_PARTY_DEBUG_MOTION=music|chat|chats rejoue une petite scène (états successifs, sans
/// serveur) pour filmer et vérifier les animations : chargement → contenu, titre ajouté, titre suivant,
/// bulle qui arrive, envoi confirmé, réactions, épingle, liste de discussions qui se réordonne.
struct MotionDemo: View {
    @ObservedObject var model: WebModel
    @State private var scene: String?

    var body: some View {
        GeometryReader { proxy in
            Group {
                switch scene {
                case "music":
                    if let music = model.music { MusicView(store: music, topInset: proxy.safeAreaInsets.top) }
                case "chat":
                    if let chats = model.chats {
                        NavigationStack { ConversationView(store: chats, group: "demo") }
                            .tint(Palette.accent)
                            .padding(.top, proxy.safeAreaInsets.top)
                    }
                case "eventchat":
                    if let chats = model.eventChats {
                        NavigationStack { ConversationView(store: chats, group: "event-demo") }
                            .tint(Palette.accent)
                            .padding(.top, proxy.safeAreaInsets.top)
                    }
                case "chats":
                    if let chats = model.chats { ChatsView(store: chats, topInset: proxy.safeAreaInsets.top) }
                default:
                    EmptyView()
                }
            }
            .background(scene == nil ? Color.clear : AppConfig.background)
            .ignoresSafeArea()
        }
        .task {
            guard let wanted = ProcessInfo.processInfo.environment["PARTY_DEBUG_MOTION"] else { return }
            try? await Task.sleep(for: .seconds(1))
            switch wanted {
            case "music": await playMusic()
            case "chat": await playChat()
            case "chats": await playList()
            case "eventchat", "eventchat-top": playEventChat(top: wanted == "eventchat-top")
            default: assertionFailure("PARTY_DEBUG_MOTION inconnu : \(wanted)")
            }
        }
    }

    private func pause(_ seconds: Double) async { try? await Task.sleep(for: .seconds(seconds)) }

    // MARK: Musique

    private func playMusic() async {
        guard let store = model.music else { return }
        store.showDemo(.loading)
        scene = "music"
        await pause(1.5)
        let queue = [Self.item("Blinding Lights", "The Weeknd", by: "Léa", eta: 120),
                     Self.item("Alors on danse", "Stromae", by: "Tom", eta: 320)]
        store.showDemo(.ready(Self.party(now: ("Sapés comme jamais", "Maître Gims"), queue: queue)))
        await pause(2.5)
        let mine = Self.item("Tout oublier", "Angèle", by: "Moi", eta: 520, rid: "r1")
        store.showDemo(.ready(Self.party(now: ("Sapés comme jamais", "Maître Gims"), queue: queue + [mine])),
                       notice: .init(text: "« Tout oublier » ajouté 🎶", isError: false))
        await pause(3)
        store.showDemo(.ready(Self.party(now: ("Blinding Lights", "The Weeknd"), queue: Array(queue.dropFirst()) + [mine],
                                         messages: [("m1", "Tu peux mettre du Stromae ?", nil)])))
        await pause(2.5)
        store.showDemo(.ready(Self.party(now: ("Blinding Lights", "The Weeknd"), queue: Array(queue.dropFirst()) + [mine],
                                         messages: [("m1", "Tu peux mettre du Stromae ?", "C'est le prochain !")])))
        await pause(2.5)
        store.showDemo(.closed)
        await pause(2)
        store.showDemo(.ready(Self.party(now: ("Blinding Lights", "The Weeknd"), queue: [mine])))
    }

    private static func item(_ title: String, _ artist: String, by: String, eta: Double, rid: String? = nil) -> [String: Any] {
        var item: [String: Any] = ["title": title, "artist": artist, "art": "", "by": by, "eta": eta, "track_id": title]
        if let rid { item["rid"] = rid }
        return item
    }

    private static func party(now: (String, String), queue: [[String: Any]],
                              messages: [(String, String, String?)] = []) -> PartyState {
        let json: [String: Any] = [
            "active": true, "room": "Salon", "state": "PLAYING",
            "now": ["title": now.0, "artist": now.1, "art": "", "by": "Tom"],
            "upcoming": queue, "upcoming_total": queue.count,
            "messages": messages.map { ["id": $0.0, "text": $0.1, "reply": $0.2 as Any] },
        ]
        return decode(json)
    }

    // MARK: Conversation

    private func playChat() async {
        guard let store = model.chats else { return }
        var messages: [[String: Any]] = [
            Self.message("1", "Léa", "Qui vient samedi ?", minutesAgo: 30),
            Self.message("2", "Moi", "Moi ! J'amène les chips 🥔", minutesAgo: 28, mine: true),
            Self.message("3", "Tom", "Je serai là vers 20 h", minutesAgo: 20),
        ]
        scene = "chat"
        await pause(1.5)
        store.showDemo(conversation: Self.conversation(messages))
        await pause(2)
        messages.append(Self.message("4", "Léa", "Top, je prends le dessert 🍰", minutesAgo: 0))
        store.showDemo(conversation: Self.conversation(messages))
        await pause(2)
        messages.append(Self.message("5", "Moi", "Parfait, à samedi !", minutesAgo: 0, mine: true, pending: true))
        store.showDemo(conversation: Self.conversation(messages))
        await pause(1.5)
        messages[4]["pending"] = false
        store.showDemo(conversation: Self.conversation(messages))
        await pause(2)
        messages[4]["reactions"] = [["emoji": "🎉", "count": 1, "mine": false]]
        store.showDemo(conversation: Self.conversation(messages))
        await pause(1.5)
        messages[4]["reactions"] = [["emoji": "🎉", "count": 2, "mine": false], ["emoji": "❤️", "count": 1, "mine": true]]
        store.showDemo(conversation: Self.conversation(messages))
        await pause(2)
        messages[2]["pinned"] = true
        store.showDemo(conversation: Self.conversation(messages))
        await pause(2)
        messages.append(Self.message("6", "Tom", "", minutesAgo: 0, audio: 12))
        store.showDemo(conversation: Self.conversation(messages))
    }

    private static func message(_ id: String, _ author: String, _ body: String, minutesAgo: Double, mine: Bool = false,
                                pending: Bool = false, audio: Double? = nil) -> [String: Any] {
        let at = ISO8601DateFormatter().string(from: Date().addingTimeInterval(-minutesAgo * 60))
        var m: [String: Any] = ["id": id, "author": author, "author_name": author, "mine": mine, "at": at, "edited": false,
                                "body": body, "deleted": false, "pinned": false, "reactions": [Any](), "pending": pending]
        if let audio { m["audio_seconds"] = audio; m["audio"] = "https://example.invalid/voice.m4a" }
        return m
    }

    private static func conversation(_ messages: [[String: Any]]) -> Conversation {
        let json: [String: Any] = [
            "id": "demo", "name": "Vendredi Party", "member": true, "admin": true, "notify": "all", "can_name_admins": true,
            "me": "Moi", "reactions": ["👍", "❤️", "😂", "🎉"],
            "members": [["id": "Moi", "name": "Moi", "admin": true, "creator": true]],
            "messages": messages.map { m in m.filter { $0.key != "pending" } },
        ]
        var chat: Conversation = decode(json)
        // « pending » n'existe pas côté serveur : remis ici, comme ChatsStore le fait pour un envoi en cours.
        let pendingIDs = Set(messages.filter { $0["pending"] as? Bool == true }.compactMap { $0["id"] as? String })
        chat = chat.with(messages: chat.messages.map { m in
            var copy = m
            copy.pending = pendingIDs.contains(m.id)
            return copy
        })
        return chat
    }

    // MARK: Discussion d'un événement (16.11) : annonce, épinglé, citations, réponse, réactions, plusieurs jours

    /// top : seulement le début (annonce, épinglé, changement de jour), pour le voir sans défiler.
    private func playEventChat(top: Bool = false) {
        guard let store = model.eventChats else { return }
        func m(_ id: String, _ who: String, _ body: String, _ minutes: Double, mine: Bool = false) -> [String: Any] {
            var row = Self.message(id, who, body, minutesAgo: minutes, mine: mine)
            row["author"] = "id-" + who
            return row
        }
        var a = m("a1", "Léa", "@annonce Rendez-vous 19 h devant la salle, parking derrière 🚗", 1500)
        a["pinned"] = true
        a["announcement"] = true
        var p = m("p1", "Tom", "Code de la porte : 4521", 1450)
        p["pinned"] = true
        var r = m("r3", "Moi", "Je prends les verres et la glace 🧊", 30, mine: true)
        r["reply"] = ["id": "q2", "author": "id-Zoé", "name": "Zoé", "text": "Qui amène les verres ?"]
        var t = m("t1", "Tom", "@toutlemonde on lance le blind test à 21 h, préparez vos playlists !", 3)
        t["reactions"] = [["emoji": "🔥", "count": 3, "mine": true], ["emoji": "😂", "count": 1, "mine": false]]
        let messages: [[String: Any]] = [
            a, p,
            m("q1", "Zoé", "Trop hâte !!", 1440),
            m("q2", "Zoé", "Qui amène les verres ?", 34),
            m("q3", "Zoé", "Et des pailles si possible", 33),
            r,
            m("r4", "Moi", "@Léa tu as encore la sono ?", 29, mine: true),
            m("l1", "Léa", "Oui, je la prends 👍", 12),
            t,
        ]
        let json: [String: Any] = [
            "id": "event-demo", "name": "Soirée blind test", "member": true, "admin": true, "organizer": true, "event": true,
            "notify": "all", "can_name_admins": false, "me": "Moi", "reactions": ["👍", "❤️", "😂", "😮", "😢", "🔥"],
            "tags": [["tag": "toutlemonde", "hint": "Tout le monde : invités et participants"],
                     ["tag": "present", "hint": "Les présents et les peut-être"], ["tag": "annonce", "hint": "Annonce épinglée"]],
            "members": [["id": "Moi", "name": "Moi", "admin": false, "creator": false, "rsvp": "yes"],
                        ["id": "id-Léa", "name": "Léa", "admin": false, "creator": false, "organizer": true],
                        ["id": "id-Tom", "name": "Tom", "admin": false, "creator": false, "rsvp": "yes"],
                        ["id": "id-Zoé", "name": "Zoé", "admin": false, "creator": false, "rsvp": "maybe"]],
            "messages": top ? Array(messages.prefix(5)) : messages,
        ]
        store.showDemo(conversation: Self.decode(json) as Conversation)
        scene = "eventchat"
    }

    // MARK: Liste des discussions

    private func playList() async {
        guard let store = model.chats else { return }
        scene = "chats"
        await pause(1.5)
        var list = [Self.summary("a", "Vendredi Party", "Léa : à samedi !", unread: 0),
                    Self.summary("b", "Ski 2027", "Tom : forfaits réservés", unread: 2),
                    Self.summary("c", "Raclette", "Zoé : j'amène le fromage", unread: 0)]
        store.showDemo(list: list.map(Self.decodeSummary))
        await pause(2)
        list[1]["unread"] = 3
        list[1]["last"] = "Tom : on part à 7 h"
        store.showDemo(list: list.map(Self.decodeSummary))
        await pause(2)
        var raclette = list.remove(at: 2)
        raclette["unread"] = 1
        raclette["last"] = "Léa : il reste de la place ?"
        list.insert(raclette, at: 0)
        store.showDemo(list: list.map(Self.decodeSummary))
    }

    private static func summary(_ id: String, _ name: String, _ last: String, unread: Int) -> [String: Any] {
        ["id": id, "name": name, "member": true, "notify": "all", "last": last, "unread": unread,
         "last_at": ISO8601DateFormatter().string(from: Date())]
    }

    private static func decodeSummary(_ json: [String: Any]) -> ChatSummary { decode(json) }

    private static func decode<T: Decodable>(_ json: [String: Any]) -> T {
        do {
            let data = try JSONSerialization.data(withJSONObject: json)
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            fatalError("MotionDemo : \(T.self) illisible : \(error)")
        }
    }
}
#endif
