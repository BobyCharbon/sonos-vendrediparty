import SwiftUI

/// Onglet Discussions natif : la liste des groupes et la conversation ouverte, mises à jour EN DIRECT (WebSocket
/// Supabase Realtime, ChatRealtime) ; un rafraîchissement lent reste en secours. Un message envoyé s'affiche tout de
/// suite (horloge) puis prend sa place quand le serveur l'a enregistré, comme Snapchat ou WhatsApp.
@MainActor
final class ChatsStore: ObservableObject {
    /// Secours si le temps réel est coupé (réseau capricieux) : la conversation, puis la liste.
    static let conversationEvery: Duration = .seconds(10)
    static let listEvery: Duration = .seconds(30)

    @Published private(set) var chats: [ChatSummary]?
    @Published private(set) var conversation: Conversation?
    @Published private(set) var error: String?
    @Published private(set) var sending = false
    @Published var notice: String?
    /// Conversation à ouvrir (toucher d'une notification) : la liste la pousse dès qu'elle s'affiche.
    @Published var requested: String?
    /// Message à montrer (recherche, bandeau des épinglés) : le fil y défile puis le remet à nil.
    @Published var jumpTo: String?
    /// Discussion d'un événement : page plus ancienne en cours ; false quand le début de la discussion est atteint.
    @Published private(set) var loadingOlder = false
    @Published private(set) var hasOlder = true
    /// Messages plus anciens chargés (loadOlder) : gardés au-dessus du fil à chaque relecture.
    private var older: [Conversation.Message] = []
    /// Réglage changé à l'écran, pas encore confirmé : appliqué par-dessus une relecture arrivée entre-temps.
    private var prefsOverride: ((Conversation) -> Conversation)?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var endpoint: ChatRealtime.Endpoint?
    private var listLive: ChatRealtime?
    private var chatLive: ChatRealtime?
    /// Messages envoyés pas encore revenus du serveur, par conversation : gardés en bas de la conversation (« Envoi… »,
    /// envoyé, ou « Pas envoyé »), même quand l'écran se ferme : un message n'est jamais perdu.
    private var outgoing: [String: [Conversation.Message]] = [:]
    /// Envoi à rejouer (« Toucher pour réessayer », réseau revenu), par message.
    private var resend: [String: (chat: String, work: (String) async throws -> Void)] = [:]
    /// Compte qui a écrit chaque message en attente.
    private var authors: [String: String] = [:]
    /// Réseau absent : nouveaux essais tout seuls avant « Pas envoyé ».
    static var retryDelays: [Duration] = [.milliseconds(800), .milliseconds(2500)]
    /// Conversations préchargées depuis la liste (dernier message connu) : une seule lecture par nouveau message.
    private var prefetched: [String: String] = [:]
    /// Conversation ouverte pas encore notée lue par le serveur (réseau absent à l'ouverture : au prochain essai).
    private var readOnOpen: String?
    /// Dernière version de chaque conversation, en mémoire (compte memoryAccount) : affichée dès le toucher, sans même
    /// relire le fichier du cache. Oubliée quand un autre compte se connecte.
    private var memory: [String: Conversation] = [:]
    private var memoryAccount: String?

    /// Compte du jeton : un autre compte qu'avant → rien de l'ancien n'est gardé (mémoire, préchargements).
    private func owner(_ token: String) -> String? {
        let account = ChatsCache.account(of: token)
        if account != memoryAccount {
            memory = [:]
            prefetched = [:]
            memoryAccount = account
        }
        return account
    }

    private var pending: [Conversation.Message] {
        get { conversation.flatMap { outgoing[$0.id] } ?? [] }
        set { if let id = conversation?.id { outgoing[id] = newValue.isEmpty ? nil : newValue } }
    }
    private var refreshing: Task<Void, Never>?

    /// Discussion d'un événement (écran natif ouvert depuis sa fiche) : mêmes écrans, routes /api/account/event-chat/*.
    let forEvents: Bool

    init(api: PartyAPI, web: WebStorage?, forEvents: Bool = false) {
        self.api = api
        self.web = web
        self.forEvents = forEvents
    }

    /// Pause des notifications de toutes les Discussions (bouton en haut de la liste) ; même réglage que
    /// Réglages › Notifications.
    private(set) lazy var pause = PauseStore(api: api, web: web)

    /// Groupes (mêmes données et actions que Réglages › Groupes) : créer un groupe depuis Discussions, le gérer
    /// depuis les infos d'une discussion.
    private(set) lazy var groups = GroupsStore(api: api, web: web)
    private(set) lazy var privacy = PrivacyStore(api: api, web: web)
    /// « Signaler » un message, conditions d'utilisation avant le premier message (modération commune).
    private(set) lazy var moderation = ModerationStore(api: api, web: web)

    /// Nouveau groupe depuis Discussions : même création que Réglages › Groupes, le créateur dedans d'office ;
    /// la liste est relue et la discussion du groupe s'ouvre (requested).
    func createGroup(_ name: String) async -> Bool {
        guard let id = await groups.create(name, join: true) else {
            if let problem = groups.notice ?? groups.error { notice = problem; groups.notice = nil }
            return false
        }
        await loadList()
        requested = id
        return true
    }

    /// Pastille des Discussions (`chat_badge` : non lus hors archivées et sourdine + demandes reçues).
    var unread: Int { badge }
    @Published private(set) var badge = 0
    /// Personnes croisées (état vide : « Croisés à la soirée… »), lues une fois quand la liste est vide.
    @Published private(set) var suggestions: ChatPeopleSuggestions?
    /// Discussions d'événement ouvertes depuis la liste : l'écran natif existant, avec ses routes /event-chat/*.
    private(set) lazy var events = ChatsStore(api: api, web: web, forEvents: true)
    /// Relais v2 (/api/account/chats/rpc) présent sur ce serveur ; un serveur plus ancien : liste my_chats.
    private var listV2 = true

    /// Conversation privée à deux (d'après la liste ou la conversation ouverte) ; inconnue : le serveur la reconnaît.
    func isDirect(_ id: String) -> Bool {
        conversation?.id == id ? conversation?.isDirect == true : chats?.first { $0.id == id }?.direct == true
    }

    /// « Écrire » (Mes amis, fiche d'un membre) : LA conversation privée avec cette personne, ouverte dans Discussions.
    /// Rend false (et un message dans notice) si on ne peut pas lui écrire.
    func write(to user: String, contactHash: String? = nil) async -> Bool {
        var chat: String?
        await run { token in chat = try await api.startDirectChat(token: token, user: user, contactHash: contactHash) }
        guard let chat else { return false }
        requested = chat
        return true
    }

    /// Bloquer / débloquer l'autre personne d'un message direct (elle n'en est pas prévenue).
    func setBlocked(_ on: Bool) async {
        guard let user = conversation?.userID, conversation?.isDirect == true else { return }
        await act { token in try await api.blockDirect(token: token, user: user, on: on) }
    }

    func loadList() async {
        #if DEBUG
        if demo { return }
        #endif
        if chats == nil, let account = await account() {
            chats = ChatsCache.load([ChatSummary].self, account: account, name: "list")  // tout de suite, puis à jour
        }
        await run(loading: chats == nil) { token in
            var list: [ChatSummary]?
            if listV2 {
                do {
                    // Tout d'un coup (archivées et demandes comprises) : la liste, Demandes et Archivées en découlent ;
                    // l'adresse du temps réel vient avec (plus de deuxième appel à l'ancienne liste pour elle).
                    let reply: ChatListReply = try await api.postDecoding("/api/account/chats/rpc", body: [
                        "token": token, "fn": "chat_list", "args": ["include_archived": true]])
                    list = reply.result
                    if let live = reply.realtime { endpoint = live }
                } catch PartyAPIError.server(let detail) {
                    // Serveur d'avant les Discussions v2 (route absente) : l'ancienne liste. Panne passagère de la base
                    // (503) : la liste affichée reste — avant, l'app passait pour toute la session à l'ancienne liste
                    // (sans événements, épingles ni « non lu » manuel ; recette du 19.11).
                    if detail == "Not Found" { listV2 = false } else if chats != nil { return }
                }
            }
            if list == nil || endpoint == nil {
                let (old, endpoint) = try await api.chats(token: token)
                if list == nil { list = old }
                if let endpoint { self.endpoint = endpoint }
            }
            guard let list else { return }
            if list != chats { showList(list) }
            if let account = owner(token) { ChatsCache.save(list, account: account, name: "list") }
            prefetch(list, token: token)
            if listV2, let n: Int = try? await api.chatsRPC(token: token, fn: "chat_badge") { setBadge(n) }
        }
        if chats?.isEmpty == true, suggestions == nil { await loadSuggestions() }
    }

    /// Les 3 premières discussions (hors soirées, demandes reçues et archivées) se préchargent dans le cache du téléphone
    /// quand leur dernier message a changé : un toucher les ouvre sans attendre (lecture seule, rien n'est marqué lu).
    private func prefetch(_ list: [ChatSummary], token: String) {
        guard !forEvents, let account = ChatsCache.account(of: token) else { return }
        for chat in list.filter({ !$0.isEvent && !$0.incomingRequest && !$0.archived }).prefix(3) {
            let last = chat.lastMessage?.id ?? chat.lastAt ?? ""
            guard prefetched[chat.id] != last, conversation?.id != chat.id else { continue }
            prefetched[chat.id] = last
            Task(priority: .utility) { [api] in
                let kept = ChatsCache.load(Conversation.self, account: account, name: "chat-" + chat.id)
                if !last.isEmpty, kept?.messages.last?.id == last { return }
                guard let fresh = try? await api.openChat(token: token, group: chat.id, direct: chat.direct, prefetch: true) else {
                    self.prefetched[chat.id] = nil
                    return
                }
                ChatsCache.save(fresh, account: account, name: "chat-" + chat.id)
                if self.memoryAccount == account { self.memory[chat.id] = fresh }
            }
        }
    }

    /// Nouvelle liste à l'écran (et pastille recalculée d'après elle, en attendant chat_badge).
    private func showList(_ list: [ChatSummary]) {
        chats = list
        setBadge(ChatListLogic.badge(list))
    }

    private func setBadge(_ n: Int) {
        guard n != badge else { return }
        badge = n
        onBadge?(n)
    }

    /// Pastille changée (lu, nouveau message) : l'onglet Discussions de la barre (décrit par la page) la reprend aussitôt.
    var onBadge: ((Int) -> Void)?

    /// Change une ligne tout de suite (avant la réponse du serveur) ; la relecture suivante la corrige au besoin.
    private func update(_ id: String, _ change: (inout ChatSummary) -> Void) {
        guard var list = chats, let i = list.firstIndex(where: { $0.id == id }) else { return }
        change(&list[i])
        Motion.animate(Motion.snappy) { showList(list) }
    }

    // MARK: Gestes de la liste (Discussions v2)

    func chat(_ id: String) -> ChatSummary? { chats?.first { $0.id == id } }

    /// Épingler (5 au plus, `pin_limit`), archiver, marquer non lu : set_chat_state.
    func setState(_ chat: ChatSummary, pinned: Bool? = nil, archived: Bool? = nil, unread: Bool? = nil) async {
        var args: [String: Any] = ["kind": chat.kind.rawValue, "chat": chat.id]
        if let pinned { args["pinned"] = pinned }
        if let archived { args["archived"] = archived }
        if let unread { args["unread"] = unread }
        update(chat.id) { row in
            if let pinned { row.pinnedAt = pinned ? ISO8601DateFormatter().string(from: Date()) : nil }
            if let archived { row.archived = archived; if archived { row.pinnedAt = nil } }
            if let unread { row.markedUnread = unread }
        }
        await listAct { token in try await api.chatsRPCRun(token: token, fn: "set_chat_state", args: args) }
    }

    /// Lu : les messages lus (groupe, direct) et la marque « non lu » retirée.
    func markRead(_ chat: ChatSummary) async {
        update(chat.id) { $0.unread = 0; $0.markedUnread = false }
        await listAct { token in
            if chat.kind == .event { try await api.chatsRPCRun(token: token, fn: "mark_event_chat_read", args: ["e": chat.id]) }
            else { try await api.readChat(token: token, group: chat.id, direct: chat.direct) }
            if chat.markedUnread {
                try await api.chatsRPCRun(token: token, fn: "set_chat_state", args: ["kind": chat.kind.rawValue, "chat": chat.id, "unread": false])
            }
        }
    }

    /// Menu « … » › Tout marquer comme lu.
    func markAllRead() async {
        for chat in ChatListLogic.main(chats ?? []) where chat.needsReading { await markRead(chat) }
    }

    /// Sourdine depuis la liste : set_chat_state(muted_until) ; 1 h / 8 h / 1 semaine = une date, « Toujours » =
    /// 'infinity'. nil : réactiver (une date passée l'annule ; une discussion réglée sur « Rien » repasse à son défaut).
    func mute(_ chat: ChatSummary, _ span: ChatMuteSpan?) async {
        let until = span.map { ChatListLogic.muteEnd($0) ?? ChatListLogic.muteForever }
        update(chat.id) { row in
            row.mutedUntil = until
            if span == nil && row.notify == .none { row.notify = row.kind == .group ? .mentions : .all }
        }
        await listAct { token in
            let end = until ?? ISO8601DateFormatter().string(from: Date().addingTimeInterval(-60))
            try await api.chatsRPCRun(token: token, fn: "set_chat_state",
                                      args: ["kind": chat.kind.rawValue, "chat": chat.id, "muted_until": end])
            guard span == nil, chat.notify == .none else { return }
            let level: ChatNotify = chat.kind == .group ? .mentions : .all
            if chat.kind == .event { try await api.notifyEventChat(token: token, event: chat.id, level: level) }
            else { try await api.notifyChat(token: token, group: chat.id, level: level, direct: chat.direct) }
        }
    }

    /// Discussion d'événement ouverte depuis la liste : lue (mark_event_chat_read), comme groupes et directs.
    func markEventRead(_ id: String) async {
        update(id) { $0.unread = 0; $0.markedUnread = false }
        guard listV2, let token = await web?.accountToken() else { return }
        try? await api.chatsRPCRun(token: token, fn: "mark_event_chat_read", args: ["e": id])
    }

    /// Bloquer l'autre personne d'un message direct depuis la liste (signalée d'office aux modérateurs par la base).
    func block(_ chat: ChatSummary) async {
        guard chat.direct, let user = chat.userID else { return }
        update(chat.id) { $0.blocked = true }
        await listAct { token in try await api.blockDirect(token: token, user: user, on: true) }
    }

    /// Demande reçue : Accepter (la conversation devient normale et s'ouvre).
    func accept(_ chat: ChatSummary) async -> Bool {
        var done = false
        await listAct { token in
            try await api.chatsRPCRun(token: token, fn: "accept_message_request", args: ["chat": chat.id])
            done = true
        }
        if done { update(chat.id) { $0.request = nil }; requested = chat.id }
        return done
    }

    /// Demande reçue : Supprimer (elle disparaît ; l'autre n'est pas prévenu).
    func decline(_ chat: ChatSummary) async {
        update(chat.id) { $0.request = "declined" }
        await listAct { token in try await api.chatsRPCRun(token: token, fn: "decline_message_request", args: ["chat": chat.id]) }
    }

    /// Demande reçue : Bloquer (la demande part avec).
    func blockRequest(_ chat: ChatSummary) async {
        await block(chat)
        await decline(chat)
    }

    /// Qui veut t'écrire (member_mini) : nom, photo, « Déjà vu », groupes et soirées en commun.
    func requester(_ user: String) async -> ChatRequester? {
        guard let token = await web?.accountToken() else { return nil }
        return try? await api.chatsRPC(token: token, fn: "member_mini", args: ["target": user])
    }

    /// Écrire à une personne (recherche, état vide) : open_direct_chat, puis la conversation s'ouvre ; sinon la raison.
    func openDirect(_ user: String) async {
        var opened: ChatOpenResult?
        await run { token in
            opened = try await api.chatsRPC(token: token, fn: "open_direct_chat", args: ["target": user])
        }
        guard let opened else { return }
        if let chat = opened.chat, opened.status != "none" { requested = chat } else { notice = opened.refusal }
    }

    func searchPeople(_ q: String) async -> [ChatPerson] {
        guard q.count >= 2, let token = await web?.accountToken() else { return [] }
        return (try? await api.chatsRPC(token: token, fn: "chat_people_search", args: ["q": q])) ?? []
    }

    /// Mes événements par leur titre, même sans message (chat_event_search, 19.11) : y lancer la discussion.
    func searchEvents(_ q: String) async -> [ChatSummary] {
        guard q.count >= 2, let token = await web?.accountToken() else { return [] }
        return (try? await api.chatsRPC(token: token, fn: "chat_event_search", args: ["q": q])) ?? []
    }

    func searchMessages(_ q: String) async -> [ChatMessageHit] {
        guard q.count >= 2, let token = await web?.accountToken() else { return [] }
        return (try? await api.chatsRPC(token: token, fn: "chat_search", args: ["q": q])) ?? []
    }

    func loadSuggestions() async {
        guard listV2, let token = await web?.accountToken() else { return }
        if let s: ChatPeopleSuggestions = try? await api.chatsRPC(token: token, fn: "chat_people_suggestions") { suggestions = s }
    }

    /// Geste de la liste : erreur en bandeau, puis liste relue (l'état réel du serveur).
    private func listAct(_ work: (String) async throws -> Void) async {
        await run(work)
        await loadList()
    }

    /// Au lancement de l'app : la liste est prête avant même d'ouvrir l'onglet (sans compte, rien).
    func preload() async {
        guard await web?.accountToken() != nil else { return }
        await loadList()
    }

    private func account() async -> String? {
        guard let token = await web?.accountToken() else { return nil }
        return ChatsCache.account(of: token)
    }

    /// Liste à l'écran : temps réel sur tous mes groupes (nouveau message → liste relue).
    func startListLive() async {
        guard listLive == nil, let endpoint, let token = await web?.accountToken() else { return }
        let live = ChatRealtime(endpoint: endpoint, token: token, group: nil) { [weak self] in self?.refreshSoon(nil) }
        listLive = live
        live.start()
    }

    func stopListLive() {
        listLive?.stop()
        listLive = nil
    }

    #if DEBUG || E2E_HOOKS
    /// Simulateur : PARTY_DEBUG_MOTION=chat rejoue une conversation figée (MotionDemo) pour regarder les animations.
    private(set) var demo = false

    func showDemo(list: [ChatSummary]? = nil, conversation: Conversation? = nil) {
        demo = true
        error = nil
        // SIMCTL_CHILD_PARTY_DEBUG_CHATS=neon : la liste des maquettes Néon (épinglées, Demandes, soirée, VP…).
        if list != nil, ProcessInfo.processInfo.environment["PARTY_DEBUG_CHATS"] == "neon" {
            showList(Self.neonDemo())
        } else if let list { chats = list }
        if let conversation { self.conversation = conversation }
    }

    private static func neonDemo() -> [ChatSummary] {
        let f = ISO8601DateFormatter()
        func ago(_ minutes: Double) -> String { f.string(from: Date().addingTimeInterval(-minutes * 60)) }
        func last(_ m: Double, _ author: String?, _ text: String?, type: String = "text", me: Bool = false) -> [String: Any] {
            var l: [String: Any] = ["id": UUID().uuidString, "at": ago(m), "from_me": me, "type": type]
            if let author { l["author"] = author }
            if let text { l["text"] = text }
            return l
        }
        let rows: [[String: Any]] = [
            ["kind": "direct", "id": "d-lea", "title": "Léa", "user_id": "u-lea", "last": last(3, "Léa", "Tu viens samedi ?"), "unread": 2, "pinned_at": ago(1)],
            ["kind": "event", "id": "e-raclette", "title": "Raclette chez Léa", "event_start": f.string(from: Date().addingTimeInterval(3 * 86400)),
             "last": last(6, "Julien", "J'amène le vin blanc"), "unread": 12, "pinned_at": ago(2)],
            ["kind": "group", "id": "g-coloc", "title": "Coloc' de la Cité", "emoji": "🏡", "color": "coral", "last": last(80, "Zoé", "Courses faites"), "pinned_at": ago(3)],
            ["kind": "direct", "id": "d-maman", "title": "Maman", "user_id": "u-maman", "last": last(200, nil, "Bisous", me: true), "pinned_at": ago(4)],
            ["kind": "direct", "id": "d-mathieu", "title": "Mathieu Favre", "user_id": "u-mat", "last": last(2, "Mathieu", "On se retrouve où ?"), "unread": 2],
            ["kind": "group", "id": "g-jura", "title": "Les Copains du Jura", "emoji": "🥾", "color": "mint",
             "last": last(10, "Noé", "@Sam tu prends la voiture samedi ?"), "unread": 3, "mention": true, "notify": "mentions"],
            ["kind": "direct", "id": "d-chloe", "title": "Chloé Bonvin", "user_id": "u-chloe", "last": last(19, "Chloé", nil, type: "audio"), "unread": 1],
            ["kind": "event", "id": "e-paintball", "title": "Paintball à Bulle", "color": "mint", "event_start": f.string(from: Date().addingTimeInterval(4 * 86400)),
             "last": last(52, "Julien", nil, type: "photo"), "unread": 6, "notify": "none"],
            ["kind": "direct", "id": "d-anais", "title": "Anaïs Perrin", "user_id": "u-anais", "last": last(158, nil, "Merci pour hier soir, c'était top 🙏", me: true),
             "seen_by_other": true],
            ["kind": "group", "id": "g-basket", "title": "Basket du mardi", "emoji": "🏀", "color": "sky", "last": last(1500, "Kevin", "Salle 3 à Malley, même heure")],
            ["kind": "group", "id": "g-vp", "title": "Membres Vendredi Party", "is_vp": true, "last": last(3000, "Party", "📣 Annonce : nouvelle saison de jeux")],
            ["kind": "direct", "id": "d-req", "title": "Tom", "user_id": "u-tom", "last": last(30, "Tom", "Salut ! On s'est vus à la raclette"), "request": "incoming", "unread": 1],
            ["kind": "group", "id": "g-old", "title": "Ski 2025", "emoji": "⛷️", "color": "lavender", "last": last(90000, "Léo", "Photos en ligne"), "archived": true],
        ]
        return rows.compactMap { try? JSONDecoder().decode(ChatSummary.self, from: JSONSerialization.data(withJSONObject: $0)) }
    }
    #endif

    /// Ouvre (ou relit) une conversation ; la marque comme lue à l'ouverture, puis à chaque nouveau message.
    func open(_ group: String) async {
        #if DEBUG
        if demo { return }
        #endif
        if conversation?.id != group {
            // Lue dès l'ouverture, même préchargée (ses messages déjà sur le téléphone : rien de « nouveau ») — bug du
            // 19.11 : la conversation restait non lue dans la liste et la pastille.
            readOnOpen = group
            // Ligne non lue de la liste : « lu » part tout de suite, sans attendre la relecture de la conversation ni
            // dépendre de l'écran (retour avant la réponse du serveur : la lecture était annulée avec lui).
            if !forEvents, let row = chat(group), row.needsReading, !row.incomingRequest {
                Task { await self.sendRead(group, direct: row.direct) }
            }
            older = []
            hasOlder = true
            jumpTo = nil
            // Dernière version gardée sur le téléphone : la conversation s'affiche sans attendre le serveur (avec les
            // messages pas encore partis de cette conversation).
            var kept = memory[group]
            if kept == nil { kept = await account().flatMap { ChatsCache.load(Conversation.self, account: $0, name: "chat-" + group) } }
            let waiting = outgoing[group] ?? []
            conversation = kept.map { waiting.isEmpty ? $0 : $0.with(messages: $0.messages.filter { m in !waiting.contains { $0.id == m.id } } + waiting) }
        }
        await run(loading: conversation == nil) { token in
            let fresh = forEvents ? try await api.openEventChat(token: token, event: group)
                                  : try await api.openChat(token: token, group: group, direct: isDirect(group))
            if let live = fresh.realtime { endpoint = live }
            if let account = owner(token) { ChatsCache.save(fresh, account: account, name: "chat-" + group) }
            memory[group] = fresh
            let changed = fresh.messages.last?.id != conversation?.messages.filter { !$0.pending }.last?.id || conversation == nil
            // Revenus du serveur : ils quittent la file ; les autres restent en bas (envoi, envoyé, pas envoyé).
            var waiting = outgoing[group] ?? []
            waiting.removeAll { p in fresh.messages.contains { $0.id == p.id } }
            outgoing[group] = waiting.isEmpty ? nil : waiting
            ChatTiming.mark("conv.fresh")
            for m in fresh.messages where !m.mine && conversation?.messages.contains(where: { $0.id == m.id }) == false {
                ChatTiming.mark("recv." + m.id)
            }
            // Pages plus anciennes déjà chargées (discussion d'un événement) : gardées au-dessus du fil.
            var shown = waiting.isEmpty && older.isEmpty ? fresh
                : fresh.with(messages: Conversation.merge(older: older, into: fresh.messages) + waiting)
            if let prefsOverride { shown = prefsOverride(shown) }
            if shown != conversation { conversation = shown }
            if (changed || readOnOpen == group) && fresh.member && !forEvents { await sendRead(group, direct: fresh.isDirect) }
            // Le serveur répond : les messages restés « pas envoyés » repartent.
            for m in waiting where m.failed { Task { await self.retry(m) } }
        }
        if chatLive == nil, conversation?.id == group { await startChatLive(group) }
    }

    /// « Lu » (groupe, message direct) : la ligne et la pastille passent à 0 aussitôt ; refusé ou réseau absent : la
    /// conversation encore ouverte le renvoie à sa prochaine relecture.
    private func sendRead(_ group: String, direct: Bool) async {
        if readOnOpen == group { readOnOpen = nil }
        guard let token = await web?.accountToken(),
              (try? await api.readChat(token: token, group: group, direct: direct)) != nil else {
            if conversation?.id == group { readOnOpen = group }
            return
        }
        update(group) { $0.unread = 0; $0.markedUnread = false }
    }

    private func startChatLive(_ group: String) async {
        if endpoint == nil && !forEvents { await loadList() }
        guard let endpoint, let token = await web?.accountToken() else { return }
        let live = forEvents
            ? ChatRealtime(endpoint: endpoint, token: token, event: group) { [weak self] in self?.refreshSoon(group) }
            : ChatRealtime(endpoint: endpoint, token: token, group: group, direct: isDirect(group)) { [weak self] in self?.refreshSoon(group) }
        chatLive = live
        live.start()
    }

    /// Plusieurs changements dans la même seconde (message + réaction…) : une seule relecture.
    private func refreshSoon(_ group: String?) {
        refreshing?.cancel()
        refreshing = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(120))
            guard let self, !Task.isCancelled else { return }
            if let group, self.conversation?.id == group { await self.open(group) } else if group == nil { await self.loadList() }
        }
    }

    func close() {
        chatLive?.stop()
        chatLive = nil
        conversation = nil
        older = []
        hasOlder = true
        jumpTo = nil
    }

    /// Texte : affiché tout de suite, envoyé en un seul appel (citations calculées ici). Photo : envoyée d'abord.
    /// announce : interrupteur 📣 de l'organisation d'un événement (vaut « @annonce »).
    /// false seulement si le message est refusé (filtre, demande, CGU…) : le texte revient alors dans le champ ;
    /// réseau absent : la bulle reste (« Pas envoyé · Toucher pour réessayer »), rien n'est perdu.
    func send(_ text: String, replyTo: String?, photo: Data? = nil, announce: Bool = false) async -> Bool {
        guard let chat = conversation else { return false }
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty || photo != nil else { return false }
        let id = UUID().uuidString.lowercased()
        let mentions = chat.mentions(in: body, me: chat.me)
        let (api, forEvents) = (api, forEvents)
        if let photo {
            sending = true
            defer { sending = false }
            var sent = false
            await run { token in
                if forEvents {
                    let path = try await api.uploadEventChatFile(token: token, event: chat.id, data: photo, audio: false)
                    try await api.sendEventChat(token: token, event: chat.id, body: body, replyTo: replyTo, photoPath: path,
                                                mentions: mentions, id: id, announcement: announce)
                } else {
                    let path = try await api.uploadChatPhoto(token: token, group: chat.id, jpeg: photo)
                    try await api.sendChat(token: token, group: chat.id, body: body, replyTo: replyTo, photoPath: path,
                                           mentions: mentions, id: id, direct: chat.isDirect)
                }
                sent = true
            }
            await open(chat.id)
            return sent
        }
        guard let sending = sendNow(body, replyTo: replyTo, announce: announce) else { return false }
        return await sending.value
    }

    /// Texte : la bulle est affichée tout de suite, dans le geste même (synchrone), puis l'envoi part ; rend la tâche
    /// d'envoi (false : refusé). nil : rien à envoyer.
    func sendNow(_ text: String, replyTo: String?, announce: Bool = false) -> Task<Bool, Never>? {
        guard let chat = conversation else { return nil }
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return nil }
        let id = UUID().uuidString.lowercased()
        let mentions = chat.mentions(in: body, me: chat.me)
        let (api, forEvents) = (api, forEvents)
        show(Self.draft(id: id, body: body, replyTo: replyTo, in: chat, announce: announce))
        return Task {
            await deliver(id, chat: chat.id) { token in
                if forEvents {
                    try await api.sendEventChat(token: token, event: chat.id, body: body, replyTo: replyTo, photoPath: nil,
                                                mentions: mentions, id: id, announcement: announce)
                } else {
                    try await api.sendChat(token: token, group: chat.id, body: body, replyTo: replyTo, photoPath: nil,
                                           mentions: mentions, id: id, direct: chat.isDirect)
                }
            }
        }
    }

    /// Vocal : bulle affichée tout de suite (« Envoi… »), fichier envoyé puis message ; le fichier local est effacé
    /// (l'enregistrement reste en mémoire pour un nouvel essai, le fichier n'est déposé qu'une fois).
    func sendVoice(_ file: URL, seconds: TimeInterval, replyTo: String?) async {
        guard let chat = conversation, let data = try? Data(contentsOf: file) else { return }
        try? FileManager.default.removeItem(at: file)
        let id = UUID().uuidString.lowercased()
        var draft = Self.draft(id: id, body: "", replyTo: replyTo, in: chat)
        draft.audioSeconds = seconds
        show(draft)
        let (api, forEvents) = (api, forEvents)
        let uploaded = UploadedPath()
        _ = await deliver(id, chat: chat.id) { token in
            if forEvents {
                let path = try await uploaded.value { try await api.uploadEventChatFile(token: token, event: chat.id, data: data, audio: true) }
                try await api.sendEventChat(token: token, event: chat.id, body: "", replyTo: replyTo, photoPath: nil, mentions: [],
                                            id: id, audioPath: path, audioSeconds: seconds)
            } else {
                let path = try await uploaded.value { try await api.uploadChatAudio(token: token, group: chat.id, audio: data) }
                try await api.sendChat(token: token, group: chat.id, body: "", replyTo: replyTo, photoPath: nil, mentions: [],
                                       id: id, audioPath: path, audioSeconds: seconds, direct: chat.isDirect)
            }
        }
    }

    /// « Pas envoyé · Toucher pour réessayer » (ou réseau revenu) : le même message, avec le même identifiant.
    func retry(_ message: Conversation.Message) async {
        // État actuel (pas celui du toucher) : un message déjà reparti n'est pas envoyé deux fois.
        guard let job = resend[message.id], outgoing[job.chat]?.first(where: { $0.id == message.id })?.failed == true else { return }
        mark(message.id, in: job.chat) { $0.failed = false; $0.pending = true }
        _ = await deliver(message.id, chat: job.chat, job.work)
    }

    /// Envoie (dans l'ordre d'appel) ; réseau absent : nouveaux essais, puis « Pas envoyé ». Rend false si refusé.
    private func deliver(_ id: String, chat: String, _ work: @escaping (String) async throws -> Void) async -> Bool {
        resend[id] = (chat, work)
        var attempt = 0
        while true {
            guard let token = await web?.accountToken() else {
                mark(id, in: chat) { $0.pending = false; $0.failed = true }
                return true
            }
            // Écrit avec un compte : jamais renvoyé avec un autre (déconnexion, autre compte entre deux essais).
            let account = ChatsCache.account(of: token) ?? ""
            if let author = authors[id], author != account {
                resend[id] = nil
                authors[id] = nil
                forget(id, in: chat)
                return true
            }
            authors[id] = account
            do {
                try await work(token)
                resend[id] = nil
                authors[id] = nil
                ChatTiming.mark("send.ok")
                // Envoyé : ✓ tout de suite ; la relecture (temps réel, ou juste après) le remplace par la version du serveur.
                mark(id, in: chat) { $0.pending = false; $0.failed = false }
                if conversation?.id == chat { refreshSoon(chat) }
                return true
            } catch PartyAPIError.offline {
                if attempt < Self.retryDelays.count {
                    try? await Task.sleep(for: Self.retryDelays[attempt])
                    attempt += 1
                    continue
                }
                mark(id, in: chat) { $0.pending = false; $0.failed = true }
                return true
            } catch PartyAPIError.needsCode {
                mark(id, in: chat) { $0.pending = false; $0.failed = true }
                notice = "Ta connexion a expiré : reconnecte-toi dans Réglages"
                return true
            } catch {
                resend[id] = nil
                authors[id] = nil
                forget(id, in: chat)
                notice = error.localizedDescription
                return false
            }
        }
    }

    private func show(_ message: Conversation.Message) {
        pending.append(message)
        if let chat = conversation { conversation = chat.with(messages: chat.messages + [message]) }
        ChatTiming.mark("send.bubble")
    }

    /// Change l'état d'un message en attente (dans sa conversation, et à l'écran si elle est ouverte).
    private func mark(_ id: String, in chat: String, _ change: (inout Conversation.Message) -> Void) {
        if var list = outgoing[chat], let i = list.firstIndex(where: { $0.id == id }) {
            change(&list[i])
            outgoing[chat] = list
        }
        if let open = conversation, open.id == chat, let i = open.messages.firstIndex(where: { $0.id == id }) {
            var messages = open.messages
            change(&messages[i])
            conversation = open.with(messages: messages)
        }
    }

    private func forget(_ id: String, in chat: String) {
        outgoing[chat]?.removeAll { $0.id == id }
        if outgoing[chat]?.isEmpty == true { outgoing[chat] = nil }
        if let open = conversation, open.id == chat { conversation = open.with(messages: open.messages.filter { $0.id != id }) }
    }

    nonisolated static func draft(id: String, body: String, replyTo: String?, in chat: Conversation,
                                  announce: Bool = false) -> Conversation.Message {
        let quoted = replyTo.flatMap { r in chat.messages.first { $0.id == r } }
        let me = chat.members.first { $0.id == chat.me }
        let announced = chat.isStaff && (announce || Mentions.isAnnouncement(body))  // d'un simple membre : message normal
        return Conversation.Message(
            id: id, author: chat.me ?? "", authorName: me?.name ?? "Moi", authorPhoto: me?.photo, mine: true,
            at: ISO8601DateFormatter().string(from: Date()), edited: false, body: body, deleted: false, photo: nil,
            pinned: announced, reply: quoted.map { Conversation.Reply(name: $0.authorName, text: $0.preview) }, reactions: [],
            announcement: announced ? true : nil, pending: true)
    }

    func react(_ message: Conversation.Message, _ emoji: String) async {
        let on = !message.reactions.contains { $0.emoji == emoji && $0.mine }
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.reactEventChat(token: token, message: message.id, emoji: emoji, on: on) }
            else { try await api.reactChat(token: token, message: message.id, emoji: emoji, on: on, direct: direct) }
        }
    }

    func pin(_ message: Conversation.Message) async {
        await setPinned(message.id, !message.pinned)
    }

    /// Retire une annonce (ou un épinglé) du bandeau : admins du groupe, d'un appui long sur le bandeau.
    func unpin(_ id: String) async {
        await setPinned(id, false)
    }

    private func setPinned(_ id: String, _ pin: Bool) async {
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.pinEventChat(token: token, message: id, pin: pin) }
            else { try await api.pinChat(token: token, message: id, pin: pin, direct: direct) }
        }
    }

    func delete(_ message: Conversation.Message) async {
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.deleteEventChat(token: token, message: message.id) }
            else { try await api.deleteChat(token: token, message: message.id, direct: direct) }
        }
    }

    func setNotify(_ level: ChatNotify) async {
        if forEvents { return await setLevel(ChatNotifyLevel(rawValue: level.rawValue) ?? .mentions) }
        guard let group = conversation?.id else { return }
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.notifyEventChat(token: token, event: group, level: level) }
            else { try await api.notifyChat(token: token, group: group, level: level, direct: direct) }
        }
    }

    /// Quitter le groupe depuis le bandeau d'entrée par un événement (17.11) : on n'y est plus remis sans son accord.
    func leaveGroup() async -> Bool {
        guard let group = conversation?.id, let me = conversation?.me, conversation?.isDirect != true, !forEvents else { return false }
        var done = false
        await act { token in
            try await api.leaveGroup(token: token, group: group, me: me)
            done = true
        }
        return done
    }

    func setOrganizer(_ member: Conversation.Member, _ on: Bool) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatOrganizer(token: token, group: group, member: member.id, on: on) }
    }

    func setEveryone(_ who: String) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatEveryone(token: token, group: group, who: who) }
    }

    func setAdmin(_ member: Conversation.Member, _ on: Bool) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatAdmin(token: token, group: group, member: member.id, on: on) }
    }

    // MARK: Discussion d'un événement : réglages, lecture, médias, recherche (17.11). Rien pour une discussion de groupe.

    /// Sourdine en cours (date à venir ou « toujours »).
    var isMuted: Bool { conversation?.isMuted() ?? false }
    /// Ce qui me prévient vraiment : rien en sourdine, sinon mon niveau (Mentions seulement par défaut).
    var effectiveLevel: ChatNotifyLevel { conversation?.effectiveLevel() ?? .mentions }

    /// Serveur à jour (17.11) : il donne le niveau ou les non-lus. Sinon ses routes read / older n'existent pas.
    private var modern: Bool { conversation.map { $0.level != nil || $0.unread != nil } ?? false }

    /// Tout / Mentions seulement / Rien : changé tout de suite à l'écran, remis comme avant si le serveur refuse.
    func setLevel(_ level: ChatNotifyLevel) async {
        await changePrefs({ $0.level = level }) { token, event in
            try await self.api.setEventChatLevel(token: token, event: event, level: level)
        }
    }

    /// Sourdine jusqu'à `until` ; nil = réactiver ; `.distantFuture` (ou plus de 50 ans) = toujours.
    func mute(until: Date?) async {
        let always = until.map { $0.timeIntervalSinceNow > 50 * 365 * 86_400 } ?? false
        let iso = until.map { ISO8601DateFormatter().string(from: $0) }
        await changePrefs({ $0.mutedUntil = always ? "infinity" : iso }) { token, event in
            try await self.api.muteEventChat(token: token, event: event, until: always ? "always" : iso)
        }
    }

    private func changePrefs(_ change: @escaping (inout Conversation) -> Void,
                             _ work: (String, String) async throws -> Void) async {
        guard forEvents, let chat = conversation else { return }
        let apply: (Conversation) -> Conversation = { var c = $0; change(&c); return c }
        prefsOverride = apply
        conversation = apply(chat)
        var done = false
        await run { token in
            try await work(token, chat.id)
            done = true
        }
        prefsOverride = nil
        guard conversation?.id == chat.id, var now = conversation else { return }
        if done {
            memory[chat.id] = now
            if let account = await account() { ChatsCache.save(now, account: account, name: "chat-" + chat.id) }
        } else {
            now.level = chat.level
            now.mutedUntil = chat.mutedUntil
            conversation = now
        }
    }

    /// Discussion lue : les non-lus passent à 0 tout de suite ; l'écran l'appelle quand le fil est affiché.
    func markRead() async {
        guard forEvents, modern, let chat = conversation, (chat.unread ?? 0) > 0,
              let token = await web?.accountToken() else { return }
        conversation?.unread = 0
        try? await api.readEventChat(token: token, event: chat.id)
    }

    /// Organisation de l'événement : qui peut écrire ("all" | "staff") et description ; nil = inchangé.
    func saveSettings(write: String?, description: String?) async -> Bool {
        guard forEvents, let chat = conversation else { return false }
        var saved = false
        await run { token in
            try await api.eventChatSettings(token: token, event: chat.id, write: write, description: description)
            saved = true
        }
        guard saved else { return false }
        if conversation?.id == chat.id {
            if let write { conversation?.writeMode = write }
            if let description { conversation?.description = description }
        }
        await open(chat.id)
        return true
    }

    /// Photos, vocaux et liens, les plus récents d'abord ; `before` : page suivante (date du dernier élément reçu).
    func media(before: String? = nil) async -> [ChatMediaItem] {
        guard forEvents, let event = conversation?.id else { return [] }
        var items: [ChatMediaItem] = []
        await run { token in items = try await api.eventChatMedia(token: token, event: event, before: before) }
        return items
    }

    func search(_ q: String) async -> [ChatSearchResult] {
        let query = q.trimmingCharacters(in: .whitespacesAndNewlines)
        guard forEvents, !query.isEmpty, let event = conversation?.id else { return [] }
        var results: [ChatSearchResult] = []
        await run { token in results = try await api.searchEventChat(token: token, event: event, query: query) }
        return results
    }

    /// Page précédente, ajoutée au-dessus sans doublon (l'écran garde son message de référence à l'écran).
    func loadOlder() async {
        guard forEvents, modern, hasOlder, !loadingOlder, let chat = conversation,
              let first = chat.messages.first(where: { !$0.pending }) else { return }
        loadingOlder = true
        defer { loadingOlder = false }
        var page: [Conversation.Message]?
        await run { token in page = try await api.olderEventChat(token: token, event: chat.id, before: first.id) }
        guard let page, conversation?.id == chat.id, let current = conversation else { return }
        let added = Conversation.merge(older: page, into: current.messages)
        if added.count == current.messages.count { hasOlder = false; return }
        older = Conversation.merge(older: page, into: older)
        conversation = current.with(messages: added)
    }

    /// Montre un message (résultat de recherche, épinglé) : charge les pages plus anciennes s'il le faut, puis jumpTo.
    func reveal(_ id: String) async {
        for _ in 0..<20 {
            if conversation?.messages.contains(where: { $0.id == id }) == true { break }
            let count = conversation?.messages.count
            await loadOlder()
            if !hasOlder || conversation?.messages.count == count { break }
        }
        if conversation?.messages.contains(where: { $0.id == id }) == true { jumpTo = id }
        else { notice = "Ce message n'est plus dans la discussion." }
    }

    private func act(_ work: (String) async throws -> Void) async {
        guard let group = conversation?.id else { return }
        var done = false
        await run { token in
            try await work(token)
            done = true
        }
        if done { await open(group) }
    }

    /// loading : premier chargement, l'erreur prend la place de l'écran ; sinon bandeau.
    private func run(loading: Bool = false, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = forEvents ? "Connecte-toi pour discuter avec les invités" : "Connecte-toi pour discuter avec tes groupes"
            return
        }
        do {
            try await work(token)
            if loading { error = nil }
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi dans Réglages"
        } catch is CancellationError {
            return
        } catch {
            if loading { self.error = error.localizedDescription } else { notice = error.localizedDescription }
        }
    }
}

private extension Optional {
    func asyncMap<T>(_ transform: (Wrapped) async throws -> T) async rethrows -> T? {
        guard let value = self else { return nil }
        return try await transform(value)
    }
}

/// Chemin du vocal déposé : gardé d'un essai à l'autre (le fichier n'est déposé qu'une fois).
private final class UploadedPath: @unchecked Sendable {
    private var path: String?

    func value(_ upload: () async throws -> String) async throws -> String {
        if let path { return path }
        let fresh = try await upload()
        path = fresh
        return fresh
    }
}

/// Réponse de chat_list par le relais : la liste et l'adresse du temps réel.
private struct ChatListReply: Decodable {
    let result: [ChatSummary]
    let realtime: ChatRealtime.Endpoint?
}
