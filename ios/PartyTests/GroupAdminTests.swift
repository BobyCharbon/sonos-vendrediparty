import Foundation
import Testing
@testable import Party

/// Réglages › Administration du groupe : réponses du serveur (app/group_admin.py) et règles appliquées à l'écran.
struct GroupAdminTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Membre au niveau de Guest ; Membre VIP au-dessus")
    func roleRanks() {
        #expect(MemberRole.basic.rank == MemberRole.guest.rank)
        #expect(MemberRole.member.rank == 1 && MemberRole.basic.label == "Membre" && MemberRole.member.label == "Membre VIP")
    }

    @Test("Accueil : droits, propositions, demandes ; date de l'événement lisible")
    func decodesOverview() throws {
        let o: AdminOverview = try decode("""
        {"me": "u1", "perms": ["events.approve", "members.approve"], "rank": 2, "require_approval": null,
         "events": [{"id": "e1", "title": "Raclette", "author": "Tom", "at": "2026-10-29T10:00:00.123+00:00", "summary": "12 places", "starts_at": "2026-11-12T19:00:00+00:00"}],
         "requests": [{"id": "u2", "name": "Léa", "full_name": "Léa M", "phone": "4179", "photo": null, "message": "Coucou", "at": null, "complete": false}]}
        """)
        #expect(o.access.can("events.approve") && !o.access.full && o.requireApproval == nil)
        #expect(o.events[0].details.hasSuffix(" · 12 places") && o.events[0].details.count > " · 12 places".count)
        #expect(!o.requests[0].complete && o.requests[0].fullName == "Léa M")
        #expect(AdminDate.date("2026-10-29T10:00:00.123+00:00") != nil && AdminDate.date("2026-10-29T10:00:00+00:00") != nil)
    }

    @Test("Membres : sections par rôle puis en attente et accès retiré ; recherche")
    func membersSections() throws {
        let m: AdminMembers = try decode("""
        {"me": "me", "perms": [], "rank": 4, "full": true, "people": [
          {"id": "r", "name": "Boby", "role": "admin", "status": "active", "root": true},
          {"id": "a", "name": "Léa", "full_name": "Léa Martin", "role": "basic", "status": "active"},
          {"id": "b", "name": "Tom", "role": "member", "status": "banned"},
          {"id": "c", "name": "", "role": "inconnu", "status": "pending"}]}
        """)
        #expect(m.sections(matching: "").map(\.title) == ["Admin (1)", "Membre (1)", "En attente (1)", "Accès retiré (1)"])
        #expect(m.sections(matching: "martin").flatMap(\.people).map(\.id) == ["a"])
        #expect(m.people[3].role == .guest && m.people[3].displayName == "Profil à compléter")
    }

    @Test("Règles : jamais root, jamais soi-même, seulement en dessous de son rang")
    func memberRules() throws {
        let m: AdminMembers = try decode("""
        {"me": "me", "perms": ["members.roles"], "rank": 2, "full": false, "people": [
          {"id": "r", "name": "Boby", "role": "admin", "status": "active", "root": true},
          {"id": "me", "name": "Moi", "role": "organizer", "status": "active"},
          {"id": "o", "name": "Paul", "role": "organizer", "status": "active"},
          {"id": "v", "name": "Léa", "role": "member", "status": "active", "complete": true},
          {"id": "g", "name": "Tom", "role": "guest", "status": "active", "complete": false}]}
        """)
        let rules = Dictionary(uniqueKeysWithValues: m.people.map { ($0.id, MemberRules(access: m.access, person: $0)) })
        #expect(rules["r"]?.below == false && rules["me"]?.below == false && rules["o"]?.below == false)
        #expect(rules["v"]?.changesRole == true && rules["v"]?.bans == false && rules["v"]?.deletes == false)
        #expect(m.access.assignable == [.guest, .guestplus, .basic, .member])
        #expect(rules["g"]?.allows(.basic) == true && rules["g"]?.allows(.member) == false)
    }

    @Test("Droits : on donne ceux qu'on a, on retire toujours ; rubriques dans l'ordre du catalogue")
    func rolesToggles() throws {
        let r: AdminRoles = try decode("""
        {"me": "me", "perms": ["events.approve"], "rank": 3, "editable": ["organizer", "member", "basic", "guest", "nouveau"],
         "catalog": [{"key": "events.approve", "grp": "Événements", "label": "Valider", "hint": null},
                     {"key": "members.ban", "grp": "Membres", "label": "Retirer l'accès", "hint": null},
                     {"key": "events.edit", "grp": "Événements", "label": "Modifier", "hint": "Le publié"}],
         "grants": {"member": ["events.edit"]}}
        """)
        #expect(r.editable == [.organizer, .member, .basic, .guest])
        #expect(GroupRolesView.initial(r) == .member)
        #expect(r.canToggle("events.approve", for: .member) && !r.canToggle("members.ban", for: .member))
        #expect(r.canToggle("events.edit", for: .member))  // déjà donné : on peut le retirer
        #expect(r.groups.map(\.name) == ["Événements", "Membres"] && r.groups[0].perms.count == 2)
    }

    @Test("Compte relié : droit d'administration du groupe, admins d'office pour un ancien compte")
    func accountGroupAdmin() {
        #expect(AccountSummary.parse(#"{"name": "Léa", "admin": false, "group_admin": true}"#)?.groupAdmin == true)
        #expect(AccountSummary.parse(#"{"name": "Boby", "admin": true}"#)?.groupAdmin == true)
        #expect(AccountSummary.parse(#"{"name": "Tom", "admin": false}"#)?.groupAdmin == false)
    }

    // MARK: Rôles personnalisés (table public.roles)

    private let book = """
    [{"key": "guest", "label": "Guest", "rank": 0, "builtin": true},
     {"key": "r_videurs", "label": "Videurs", "color": "#12ABEF", "icon": "🚪", "rank": 1, "builtin": false},
     {"key": "member", "label": "Membre VIP", "rank": 2, "builtin": true},
     {"key": "organizer", "label": "Organisateur", "rank": 3, "builtin": true},
     {"key": "coadmin", "label": "Co-admin", "rank": 4, "builtin": true},
     {"key": "admin", "label": "Admin", "rank": 5, "builtin": true}]
    """

    @Test("Rôles lus dans la table : rangs, seuils, rôle personnalisé dans les sections et les filtres")
    func customRolesInMembers() throws {
        let m: AdminMembers = try decode("""
        {"me": "me", "perms": ["members.roles"], "rank": 3, "roles": \(book), "people": [
          {"id": "a", "name": "Léa", "role": "r_videurs", "role_label": "Videurs", "role_rank": 1, "status": "active", "complete": false},
          {"id": "b", "name": "Tom", "role": "member", "role_label": "Membre VIP", "role_rank": 2, "status": "active", "complete": true},
          {"id": "c", "name": "Zoé", "role": "coadmin", "role_label": "Co-admin", "role_rank": 4, "status": "active"}]}
        """)
        #expect(!m.access.full && m.access.vipRank == 2)  // Admin = rang 5 : pas la liste complète
        #expect(m.sections(matching: "").map(\.title) == ["Co-admin (1)", "Membre VIP (1)", "Videurs (1)"])
        #expect(m.people[0].role.label == "Videurs" && m.people[0].role.rank == 1)
        #expect(m.access.assignable.map(\.key) == ["guest", "r_videurs", "member"])
        let rules = MemberRules(access: m.access, person: m.people[0])
        #expect(rules.below && rules.allows(MemberRole(rawValue: "guest")) && !rules.allows(m.access.role("member")!))
        let team = UserList.arrange(m.people, search: "", filter: .team, sort: .name, descending: false, vipRank: m.access.vipRank)
        #expect(team.map(\.id) == ["c"])
    }

    @Test("Connexions récentes : aujourd'hui, hier, cette semaine, la plus récente d'abord ; au-delà de 7 jours, rien")
    func recentSignIns() throws {
        let m: AdminMembers = try decode("""
        {"me": "me", "perms": [], "rank": 5, "people": [
          {"id": "a", "name": "Léa", "status": "active", "last_sign_in_at": "2026-11-13T09:00:00Z"},
          {"id": "b", "name": "Tom", "status": "active", "last_sign_in_at": "2026-11-13T11:30:00Z"},
          {"id": "c", "name": "Zoé", "status": "active", "last_sign_in_at": "2026-11-12T20:00:00Z"},
          {"id": "d", "name": "Max", "status": "active", "last_sign_in_at": "2026-11-09T20:00:00Z"},
          {"id": "e", "name": "Ugo", "status": "active", "last_sign_in_at": "2026-10-01T20:00:00Z"},
          {"id": "f", "name": "Ana", "status": "active"}]}
        """)
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let now = ISO8601DateFormatter().date(from: "2026-11-13T12:00:00Z")!
        let groups = UserList.recent(m.people, now: now, calendar: utc)
        #expect(groups.map(\.label) == ["Aujourd'hui", "Hier", "Ces 7 derniers jours"])
        #expect(groups.map { $0.people.map(\.id) } == [["b", "a"], ["c"], ["d"]])
    }

    @Test("Écran Rôles et droits : rôles du plus haut au plus bas, nombre de comptes, gestion permise")
    func customRolesScreen() throws {
        let r: AdminRoles = try decode("""
        {"me": "me", "perms": ["roles.manage"], "rank": 5, "full": true, "can_manage": true,
         "roles": [{"key": "admin", "label": "Admin", "rank": 5, "builtin": true, "members": 1},
                   {"key": "coadmin", "label": "Co-admin", "rank": 4, "builtin": true, "members": 0},
                   {"key": "organizer", "label": "Organisateur", "rank": 3, "builtin": true, "members": 0},
                   {"key": "member", "label": "Membre VIP", "rank": 2, "builtin": true, "members": 4},
                   {"key": "r_videurs", "label": "Videurs", "icon": "🚪", "rank": 1, "builtin": false, "members": 2},
                   {"key": "guest", "label": "Guest", "rank": 0, "builtin": true, "members": 9}],
         "editable": ["coadmin", "organizer", "member", "r_videurs", "guest"], "catalog": [], "grants": {"r_videurs": ["tickets.scan"]}}
        """)
        #expect(!r.canDelete)  // pas de « can_delete » : le bouton Supprimer reste caché
        #expect(r.canManage && r.descending.map(\.key) == ["admin", "coadmin", "organizer", "member", "r_videurs", "guest"])
        let videurs = r.access.role("r_videurs")!
        #expect(videurs.members == 2 && videurs.title == "🚪 Videurs" && !videurs.builtin && r.isEditable(videurs))
        #expect(!r.isEditable(r.access.role("admin")!) && r.granted("tickets.scan", to: videurs))
        #expect(GroupRolesView.initial(r) == .member)
    }

    @Test("Réordonner : Guest en bas, Admin en haut, seulement sous son propre rang")
    func roleOrder() throws {
        let roles: [MemberRole] = try decode(book)
        let descending = Array(roles.reversed())  // admin, coadmin, organizer, member, r_videurs, guest
        // Videurs (index 4) monte au-dessus de Membre VIP (index 3) : permis pour un Admin (rang 5).
        #expect(RoleOrder.moved(descending, from: [4], to: 3, myRank: 5) == ["guest", "member", "r_videurs", "organizer", "coadmin", "admin"])
        #expect(RoleOrder.moved(descending, from: [0], to: 2, myRank: 99) == nil)  // Admin reste en haut
        #expect(RoleOrder.moved(descending, from: [5], to: 4, myRank: 99) == nil)  // Guest reste en bas
        // Organisateur (rang 3) : ne passe pas un rôle au-dessus de lui, ni le sien.
        #expect(RoleOrder.moved(descending, from: [4], to: 1, myRank: 3) == nil)
        #expect(RoleOrder.moved(descending, from: [2], to: 4, myRank: 3) == nil)
        #expect(RoleOrder.moved(descending, from: [4], to: 3, myRank: 3) == ["guest", "member", "r_videurs", "organizer", "coadmin", "admin"])
        #expect(RoleOrder.moved(descending, from: [4], to: 4, myRank: 5) == nil)  // rien n'a bougé
    }

    @Test("Brouillon de rôle : nom nettoyé, 30 caractères au plus, icône facultative")
    func roleDraft() {
        var d = RoleDraft()
        #expect(!d.valid)
        d.label = "  Les   videurs "
        d.icon = " "
        #expect(d.valid && d.cleanLabel == "Les videurs")
        let body = d.body(token: "t")
        #expect(body["label"] as? String == "Les videurs" && body["icon"] == nil && body["color"] as? String == "#007AFF")
        d.label = String(repeating: "x", count: 31)
        #expect(!d.valid)
        #expect(RoleDraft(MemberRole(key: "r_x", label: "X", color: nil, icon: "⭐", rank: 1)).icon == "⭐")
    }

    @Test("Fiche profil : nom d'un rôle personnalisé")
    func memberCardCustomRole() throws {
        let card: MemberCard = try decode(#"{"id": "a", "display_name": "Léa", "role": "r_videurs", "role_label": "Videurs"}"#)
        #expect(card.role.label == "Videurs" && card.role.key == "r_videurs")
        let old: MemberCard = try decode(#"{"id": "a", "display_name": "Léa", "role": "organizer"}"#)
        #expect(old.role == .organizer && old.role.label == "Organisateur")
    }
}
