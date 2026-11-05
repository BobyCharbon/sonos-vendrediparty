import Foundation
import Testing
@testable import Party

/// Réglages natifs : connexion (numéro, session rendue à la page), stats, utilisateurs, invités et journal de la soirée.
struct AccountNativeTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Numéro : Suisse et France avec ou sans zéro, + ou 00 gardent leur indicatif")
    func parsesPhones() {
        #expect(LoginPhone.parse("079 000 00 03", country: .ch) == "+41790000003")
        #expect(LoginPhone.parse("790000003", country: .ch) == "+41790000003")
        #expect(LoginPhone.parse("06 12 34 56 78", country: .fr) == "+33612345678")
        #expect(LoginPhone.parse("0032 470 12 34 56", country: .ch) == "+32470123456")
        #expect(LoginPhone.parse("+41 79 000 00 03", country: .fr) == "+41790000003")
        #expect(LoginPhone.parse("470 12 34 56", country: .other) == nil)  // indicatif obligatoire
        #expect(LoginPhone.parse("079 000", country: .ch) == nil)
        #expect(LoginPhone.parse("079abc", country: .ch) == nil)
        #expect(LoginPhone.pretty("+41790000003") == "+41 79 000 00 03")
    }

    @Test("Session : rendue intacte à la page, expires_at reste un entier")
    func keepsSessionAsIs() throws {
        let signIn: AccountSignIn = try decode(#"{"storage_key": "sb-x-auth-token", "session": {"access_token": "a", "expires_at": 1800000000, "expires_in": 3600, "user": {"id": "u", "phone": "41790000003", "app_metadata": {"providers": ["phone"]}}, "weak_password": null}}"#)
        #expect(signIn.storageKey == "sb-x-auth-token")
        let back = try JSONSerialization.jsonObject(with: Data(signIn.sessionJSON.utf8)) as? [String: Any]
        #expect(back?["expires_at"] as? Int == 1_800_000_000)
        #expect((back?["user"] as? [String: Any])?["phone"] as? String == "41790000003")
        #expect(back?["weak_password"] is NSNull)
    }

    @Test("Purify : barème de la page, catégories de la plus impure à la plus sage")
    func purityStats() throws {
        #expect(PurityStats.grade(0).hasSuffix("Sainte-Nitouche certifiée") && PurityStats.grade(100).hasSuffix("Le Diable en personne"))
        #expect(PurityStats.grade(36).hasSuffix("Bon vivant·e"))
        let stats: PurityStats = try decode(#"{"plays": 2, "best": 40, "last": 30, "last_at": 1800000000, "categories": [{"id": "a", "label": "Amour", "emoji": "💘", "yes": 1, "total": 4, "pct": 25}, {"id": "b", "label": "Boisson", "emoji": "🍻", "yes": 3, "total": 4, "pct": 75}]}"#)
        #expect(stats.ranked.map(\.id) == ["b", "a"])
        let none: PurityStats = try decode(#"{"plays": 0}"#)
        #expect(none.plays == 0 && none.categories.isEmpty)
    }

    @Test("Méninges : réponse complète de /api/brain/me, classement et catalogue")
    func brainStatsFull() throws {
        let stats: BrainStats = try decode("""
        {"name": "Méninges", "temperature": 1234,
         "domains": {"vitesse": {"index": 1300, "played": 4}, "memoire": {"index": 1100, "played": 2}, "calcul": {"index": 0, "played": 0}},
         "games": {"pareil": {"index": 1320, "best": 9800, "plays": 3, "last_level": 4}, "motif": {"index": 1280, "best": 9100, "plays": 1, "last_level": 2},
                   "grille": {"index": 1100, "best": 6100, "plays": 2, "last_level": 5}, "gouttes": {"index": 0, "best": 0, "plays": 0, "last_level": 0}},
         "streak": {"current": 3, "best": 7},
         "history": [{"day": "2026-11-01", "temperature": 1200}, {"day": "2026-11-02", "temperature": 1234}],
         "strengths": ["vitesse"], "weaknesses": ["memoire"], "insight": "Ta force : Vitesse.",
         "percentile": 73, "speed_vs_accuracy": {"speed": 61, "accuracy": 88}, "month_progress": 42}
        """)
        #expect(stats.temperature == 1234 && stats.plays == 6)
        #expect(stats.domains["vitesse"] == BrainStats.Domain(index: 1300, played: 4))
        #expect(stats.playedGames.map(\.id) == ["pareil", "motif", "grille"])
        #expect(stats.games["pareil"]?.lastLevel == 4)
        #expect(stats.streak == BrainStats.Streak(current: 3, best: 7))
        #expect(stats.curve.count == 2 && stats.history.last?.temperature == 1234)
        #expect(stats.strengths == ["vitesse"] && stats.weaknesses == ["memoire"])
        #expect(stats.percentile == 73 && stats.monthProgress == 42)
        #expect(stats.speedVsAccuracy == BrainStats.Balance(speed: 61, accuracy: 88))
        #expect(BrainStats.degrees(1234) == "1\u{202F}234 °M" && BrainStats.degrees(980) == "980 °M")

        let board: BrainBoard = try decode(#"{"board": [{"id": "a", "name": "Léa", "temperature": 1300, "me": false}, {"id": "b", "name": "Toi", "temperature": 1234, "me": true}, {"id": "c", "name": "Max", "temperature": 1234, "me": false}], "rank": 2, "players": 3, "percentile": 50.0, "target": null}"#)
        #expect(board.rank == 2 && board.players == 3 && board.percentile == 50)
        #expect(board.board.map { board.rank(of: $0) } == [1, 2, 2])
        #expect(board.board.filter(\.me).map(\.id) == ["b"])

        let catalog: BrainCatalog = try decode(#"{"name": "Méninges", "domains": [{"id": "vitesse", "label": "Vitesse", "icon": "⚡", "in_temperature": true}], "games": [{"id": "pareil", "name": "Pareil ?", "domain": "vitesse", "seconds": 45}]}"#)
        #expect(catalog.game("pareil")?.name == "Pareil ?")
        #expect(catalog.domain("calcul").label == "Calcul")  // repli intégré
    }

    @Test("Méninges : champs null ou absents → valeurs neutres, écran « jamais joué »")
    func brainStatsNulls() throws {
        let stats: BrainStats = try decode(#"{"name": "Méninges", "temperature": 0, "domains": {}, "games": {}, "streak": null, "history": [], "strengths": [], "weaknesses": [], "insight": null, "percentile": null, "speed_vs_accuracy": null, "month_progress": null}"#)
        #expect(stats.plays == 0 && stats.temperature == 0)
        #expect(stats.percentile == nil && stats.monthProgress == nil)
        #expect(stats.streak == BrainStats.Streak() && stats.speedVsAccuracy == BrainStats.Balance())
        #expect(stats.insight.isEmpty && stats.playedGames.isEmpty)
        let bare: BrainStats = try decode("{}")
        #expect(bare.name == "Méninges" && bare.plays == 0)
        let board: BrainBoard = try decode(#"{"board": [], "rank": null, "players": 0, "percentile": null, "target": null}"#)
        #expect(board.rank == nil && board.board.isEmpty)
    }

    @Test("Utilisateurs : filtres et tris comme le module web")
    func userList() throws {
        let m: AdminMembers = try decode("""
        {"me": "me", "perms": [], "rank": 4, "full": true, "people": [
          {"id": "a", "name": "Zoé", "role": "basic", "status": "active", "complete": true, "last_sign_in_at": "2026-10-28T10:00:00+00:00", "sign_in_count": 9, "rsvp_count": 1, "message_count": 1},
          {"id": "b", "name": "Léa", "role": "member", "status": "active", "complete": true, "beta": true, "last_sign_in_at": "2026-08-01T10:00:00+00:00", "sign_in_count": 2, "rsvp_count": 5, "message_count": 4},
          {"id": "c", "name": "Max", "role": "guest", "status": "banned", "complete": false}]}
        """)
        let now = AdminDate.date("2026-10-29T10:00:00+00:00") ?? Date()
        let ids = { (rows: [AdminMembers.Person]) in rows.map(\.id) }
        #expect(ids(UserList.arrange(m.people, search: "", filter: .all, sort: .lastSignIn, descending: true, now: now)) == ["a", "b", "c"])
        #expect(ids(UserList.arrange(m.people, search: "", filter: .all, sort: .name, descending: false, now: now)) == ["b", "c", "a"])
        #expect(ids(UserList.arrange(m.people, search: "", filter: .all, sort: .activity, descending: true, now: now)) == ["b", "a", "c"])
        #expect(ids(UserList.arrange(m.people, search: "", filter: .never, sort: .name, descending: false, now: now)) == ["b", "c"])
        #expect(ids(UserList.arrange(m.people, search: "", filter: .basic, sort: .name, descending: false, now: now)) == ["a"])
        #expect(ids(UserList.arrange(m.people, search: "", filter: .incomplete, sort: .name, descending: false, now: now)) == ["c"])
        #expect(ids(UserList.arrange(m.people, search: "lé", filter: .all, sort: .name, descending: false, now: now)) == ["b"])
        #expect(!UserList.Sort.name.descendingByDefault && UserList.Sort.signIns.descendingByDefault)
        let unnamed: AdminMembers = try decode(#"{"me": "me", "perms": [], "rank": 4, "people": [{"id": "x", "name": "", "role": "guest", "status": "active"}, {"id": "y", "name": "Émile", "role": "guest", "status": "active"}, {"id": "z", "name": "", "full_name": "Ana B", "role": "guest", "status": "active"}]}"#)
        #expect(ids(UserList.arrange(unnamed.people, search: "", filter: .all, sort: .name, descending: false, now: now)) == ["z", "y", "x"])
    }

    @Test("Invités et messages : décodés avec l'état d'hôte ; bannis d'avant à part")
    func hostPeople() throws {
        let state: AdminState = try decode("""
        {"active": true, "guests": [{"guest_id": "g1", "name": "Léa", "joined_at": 1, "total": 1, "queued": 0, "via": ["music"], "active_at": 1, "last_seen": 1, "ban": null}],
         "messages": [{"id": "m1", "guest_id": "g1", "name": "Léa", "text": "Coucou", "at": 1800000000, "read": false, "reply": null}],
         "bans": [{"guest_id": "g1", "name": "Léa", "until": 1800000600}, {"guest_id": "g9", "name": "Tom", "until": 0}],
         "games": [{"code": "1234", "type": "quiz", "name": "Quiz", "phase": "play", "round": 1, "players": ["Léa", "Tom"], "host": "Léa", "elapsed": 600}]}
        """)
        #expect(state.people.unread == 1 && state.people.messages[0].text == "Coucou")
        #expect(state.people.otherBans(listed: state.guests, active: state.active).map(\.name) == ["Tom"])
        #expect(state.people.bans[1].label == "⛔ banni")
        #expect(state.people.games[0].summary.contains("depuis 10 min") && state.people.games[0].summary.contains("Léa, Tom"))
    }

    @Test("Journal de la soirée : phrases comme la page")
    func partyJournal() throws {
        let page: PartyJournal = try decode("""
        {"entries": [
          {"id": "1", "at": 1800000000, "action": "admin.ban", "actor": "Boby", "target": {"id": "g1", "name": "Tom"}, "details": {"minutes": 10}, "ip": "1.2.3.4"},
          {"id": "2", "at": 1800000000, "action": "admin.rename", "actor": "Boby", "target": {"id": "g1", "name": "Tom"}, "details": {"to": "Thomas"}, "ip": null},
          {"id": "3", "at": 1800000000, "action": "admin.login", "actor": "Boby", "target": null, "details": {"method": "compte"}, "ip": null},
          {"id": "4", "at": 1800000000, "action": "admin.ban", "actor": "Boby", "target": {"name": "Max"}, "details": {"minutes": "sans limite"}, "ip": null}]}
        """)
        #expect(page.entries.map(\.text) == ["Boby a bloqué Tom (10 min)", "Boby a renommé Tom → « Thomas »",
                                             "Boby s'est connecté à l'admin (compte)", "Boby a bloqué Max (sans limite)"])
    }

    @Test("Catégories et tags : couleur suivante dans la palette du site")
    func taxonomy() throws {
        let t: Taxonomy = try decode(##"{"categories": [{"id": "c", "name": "Soirée", "color": "#FF9ECF", "archived": false}], "tags": []}"##)
        #expect(t.items(.categories)[0].nextColor == "#FF7A59")
        #expect(GroupTaxonomyView.next("#FF7A59") == "#D4F24A")
    }

    @Test("Retours reçus : vues, compteurs, d'où vient le retour ; un serveur sans « meta » utilise le secours")
    func feedbackAdmin() throws {
        let p: AdminFeedback = try decode("""
        {"items": [
          {"id": "a", "at": 1800000000, "kind": "bug", "name": "Léa", "text": "Bouton gris", "status": "new", "context": {"game": "undercover", "site": "Test"}},
          {"id": "b", "at": 1800000000, "kind": "idea", "name": "Tom", "text": "Mode équipe", "status": "sent", "note": "Ajoute un mode", "context": {"tab": "music"},
           "claude": {"number": 12, "url": "https://github.com/x/y/issues/12", "state": "pending", "at": 1}},
          {"id": "c", "at": 1800000000, "kind": "other", "name": "Zoé", "text": "Merci", "status": "verify",
           "claude": {"number": 13, "url": "https://github.com/x/y/issues/13", "state": "fixed", "migrations": ["20261029_x.sql"]}},
          {"id": "d", "at": 1800000000, "kind": "idea", "name": "Max", "text": "Non", "status": "declined", "reply": "Pas prévu"}],
         "kinds": {"bug": "🐞 Bug", "idea": "💡 Idée", "other": "💬 Autre"}, "claude_ready": true, "games": {"undercover": "Undercover"}}
        """)
        #expect(p.meta == .fallback)
        #expect(p.shown(view: "mine").map(\.id) == ["a", "c"] && p.shown(view: "claude").map(\.id) == ["b"])
        #expect(p.shown(view: "finished").map(\.id) == ["d"] && p.count(view: "all") == 4)
        #expect(p.pending == 2)
        #expect(p.meta(p.items[0]).hasPrefix("🐞 Bug · Léa · ") && p.meta(p.items[0]).hasSuffix("jeu : Undercover · 🧪 site de test"))
        #expect(p.meta(p.items[1]).hasSuffix("depuis Musique"))
        #expect(p.items[1].claudePending && p.items[1].claude?.label == "🤖 Claude corrige" && p.items[2].claude?.migrations == ["20261029_x.sql"])
        // Anciens avis sans classement : zone déduite du jeu ou de l'onglet, le reste vide.
        #expect(p.items[0].area == "games" && p.items[1].area == "music" && p.items[2].area == "general")
        #expect(p.items[0].platforms.isEmpty && p.items[0].tags.isEmpty && p.items[0].comments.isEmpty)
        #expect(p.meta.status("sent").technical && !p.meta.manualStatuses.contains { $0.key == "sent" })
    }

    @Test("Retours classés : meta du serveur, champs, fil, historique, filtres, tris et brouillon")
    func feedbackTriage() throws {
        let p: AdminFeedback = try decode("""
        {"items": [
          {"id": "a", "at": 1800000300, "kind": "idea", "name": "Admin", "text": "Retravailler le Quiz", "status": "think",
           "priority": "high", "area": "games", "platforms": ["web", "iphone"], "effort": "m", "tags": ["quiz"],
           "related": ["b"], "duplicate_of": "", "blocked_by": "b",
           "comments": [{"id": "x1", "at": 1800000400, "by": "claude", "text": "Combien d'équipes ?"}],
           "history": [{"at": 1800000300, "by": "admin", "field": "created", "to": "think"},
                       {"at": 1800000350, "by": "admin", "field": "platforms", "from": [], "to": ["web", "iphone"]},
                       {"at": 1800000360, "by": "admin", "field": "note"}]},
          {"id": "b", "at": 1800000100, "kind": "bug", "name": "Léa", "text": "Bouton gris", "status": "questions", "area": "music"},
          {"id": "c", "at": 1800000200, "kind": "bug", "name": "Tom", "text": "Écran figé", "status": "ready", "area": "tv", "effort": "xs"}],
         "kinds": {}, "claude_ready": false, "games": {},
         "meta": {"statuses": [{"key": "new", "label": "À trier", "icon": "📥", "symbol": "tray", "color": "#8fb4ff", "guest": "new", "mine": true},
                               {"key": "think", "label": "Idée à mûrir", "icon": "💭", "symbol": "lightbulb", "color": "#c9a8ff", "guest": "new"},
                               {"key": "questions", "label": "Questions à poser", "icon": "❓", "symbol": "questionmark.bubble", "color": "#ffb46b", "guest": "new", "mine": true},
                               {"key": "ready", "label": "Prêt à faire", "icon": "🟢", "symbol": "flag.checkered", "color": "#7be0a6", "guest": "new"},
                               {"key": "sent", "label": "Chez Claude (CI)", "icon": "🤖", "symbol": "cpu", "color": "#ffd27a", "guest": "progress", "technical": true}],
                  "priorities": [{"key": "high", "label": "🔴 Haute"}], "areas": {"tv": "📺 TV", "music": "🎵 Musique", "games": "🎲 Jeux", "lune": "🌙 Lune"},
                  "platforms": {"iphone": "📱 iPhone", "web": "🌐 Web"}, "efforts": {"m": "🟠 Moyen", "xs": "⚡ 5 min"},
                  "views": [{"key": "mine", "label": "À moi", "statuses": ["new", "questions"]},
                            {"key": "thinking", "label": "En réflexion", "statuses": ["think"]},
                            {"key": "all", "label": "Tout", "statuses": []}],
                  "mine": ["new", "questions"], "max_tags": 8}}
        """)
        #expect(p.meta.status("think").symbol == "lightbulb" && p.meta.status("questions").mine)
        #expect(p.meta.areas.map(\.key) == ["music", "games", "tv", "lune"])  // ordre du secours, inconnues à la fin
        #expect(p.meta.efforts.map(\.key) == ["xs", "m"])
        let a = p.items[0]
        #expect(a.platforms == ["web", "iphone"] && a.effort == "m" && a.tags == ["quiz"] && a.related == ["b"] && a.blockedBy == "b")
        #expect(a.comments.first?.author == "Claude 🤖" && a.comments.first?.text == "Combien d'équipes ?")
        #expect(a.history[1].to == "web, iphone" && a.history[2].to == nil)
        #expect(p.pending == 1 && p.shown(view: "mine").map(\.id) == ["b"] && p.shown(view: "thinking").map(\.id) == ["a"])
        #expect(p.shown(view: "all", filters: .init(area: "tv")).map(\.id) == ["c"])
        #expect(p.shown(view: "all", filters: .init(platform: "iphone")).map(\.id) == ["a"])
        #expect(p.shown(view: "all", filters: .init(effort: "none")).map(\.id) == ["b"])
        #expect(p.shown(view: "all", filters: .init(search: "QUIZ")).map(\.id) == ["a"])
        #expect(p.shown(view: "all", sort: .priority).first?.id == "a")
        #expect(p.shown(view: "all", sort: .oldest).map(\.id) == ["b", "c", "a"])
        #expect(p.shown(view: "all", sort: .effort).map(\.id) == ["c", "a", "b"])
        // Brouillon : seuls les champs changés partent au serveur.
        var draft = FeedbackDraft(a)
        #expect(draft.changes(from: a, p.meta).isEmpty)
        draft.status = "ready"
        draft.platforms.insert("web")
        draft.tags = "quiz, #équipes"
        let changes = draft.changes(from: a, p.meta)
        #expect(Set(changes.keys) == ["status", "tags"] && (changes["tags"] as? [String]) == ["quiz", "équipes"])
        let created = FeedbackDraft().fields(p.meta, creating: true)
        #expect(created["area"] == nil && created["reply"] == nil && (created["status"] as? String) == "new")
    }

    @Test("Ton avis : 30 caractères au moins, le compteur dit combien il en manque")
    func feedbackMinimum() {
        #expect(FeedbackRules.minimumLength == 30)
        #expect(FeedbackRules.counter(12) == "12 / 1000 · encore 18 caractères minimum")
        #expect(FeedbackRules.counter(29) == "29 / 1000 · encore 1 caractère minimum")
        #expect(FeedbackRules.counter(30) == "30 / 1000")
        #expect(FeedbackRules.counter(3, minimum: FeedbackRules.adminMinimumLength) == "3 / 1000 · encore 2 caractères minimum")
    }

    @Test("Guest+ : au niveau de Guest ; « Ton avis » suit le droit « Écrire un avis » du compte")
    func guestPlus() throws {
        #expect(MemberRole.guestplus.rank == 0 && MemberRole.guestplus.label == "Guest+")
        #expect(MemberRole.allCases.map(\.rawValue) == ["guest", "guestplus", "basic", "member", "organizer", "coadmin", "admin"])
        #expect(AccountSummary.parse(#"{"name": "Léa", "admin": false, "feedback": true}"#)?.feedback == true)
        #expect(AccountSummary.parse(#"{"name": "Tom", "admin": false, "feedback": false}"#)?.feedback == false)
        #expect(AccountSummary.parse(#"{"name": "Tom", "admin": false}"#)?.feedback == false)  // ancien compte relié : relu à l'ouverture
        let m: AdminMembers = try decode(#"{"me": "me", "perms": [], "rank": 4, "people": [{"id": "a", "name": "Léa", "role": "guestplus", "status": "active"}, {"id": "b", "name": "Tom", "role": "guest", "status": "active"}]}"#)
        #expect(UserList.arrange(m.people, search: "", filter: .guestplus, sort: .name, descending: false).map(\.id) == ["a"])
        #expect(m.sections(matching: "").map(\.title) == ["Guest+ (1)", "Guest (1)"])
    }

    @Test("Fiche profil : nom et numéro seulement s'ils sont fournis ; numéro composable ; groupes en commun")
    func memberCard() throws {
        let hidden: MemberCard = try decode(#"{"id": "u2", "display_name": "Léa", "photo": null, "role": "guestplus", "root": false, "me": false, "first_name": null, "last_name": null, "phone": null, "groups": ["Les footeux"]}"#)
        #expect(hidden.fullName.isEmpty && hidden.dialable == nil && hidden.role == .guestplus && hidden.groups == ["Les footeux"])
        let shown: MemberCard = try decode(#"{"id": "u2", "display_name": "Léa", "role": "member", "first_name": "Léa", "last_name": "Martin", "phone": "41791234567"}"#)
        #expect(shown.fullName == "Léa Martin" && shown.dialable == "+41791234567" && !shown.me)
        let privacy: Privacy = try decode(#"{"show_name": true, "phone_groups": ["g1"]}"#)
        #expect(privacy.showName && privacy.phoneGroups == ["g1"])
        let list: GroupList = try decode(#"{"groups": [{"id": "g1", "name": "Les footeux", "system": false, "mine": false, "inside": true, "members": []}, {"id": "g2", "name": "Autre", "system": false, "mine": true, "members": []}], "people": []}"#)
        #expect(list.groups[0].inside && !list.groups[1].inside)
    }

    @Test("Invitations de groupe : décodées avec le groupe et la personne qui invite")
    func groupInvitations() throws {
        let list: [GroupInvitation] = try decode(#"[{"id": "i1", "group_id": "g1", "group": "Les footeux", "invited_by": "Tom", "at": "2026-10-30T10:00:00Z"}, {"id": "i2", "group_id": "g2", "group": "Rando", "invited_by": null}]"#)
        #expect(list.map(\.group) == ["Les footeux", "Rando"] && list[0].invitedBy == "Tom" && list[1].invitedBy == nil)
        #expect(LoginPhone.parse("079 000 00 03", country: .ch).map { String($0.dropFirst()) } == "41790000003")
    }
}
