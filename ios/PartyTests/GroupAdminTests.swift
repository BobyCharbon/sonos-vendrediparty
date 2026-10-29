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
        #expect(m.access.assignable == [.guest, .basic, .member])
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
}
