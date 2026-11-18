import Foundation
import Testing
import UIKit
@testable import Party

/// Groupes en natif (18.11, « tout en natif ») : décodage de la page et de la liste (relais group_page / groups_home),
/// droits affichés comme les pages web, Membres Vendredi Party sans photo ni « Quitter », textes, routes.
struct GroupsNativeTests {
    private func page(_ json: String) throws -> GroupPage {
        try PeopleStore.decoder.decode(GroupPage.self, from: Data(json.utf8))
    }

    private let me = "aaaaaaaa-0000-4000-8000-000000000001"

    @Test("Page : le groupe, mes droits, les membres et les événements visibles")
    func decodesAPage() throws {
        let p = try page(#"""
        {"group":{"id":"g1","name":"La bande","emoji":"🎸","color":"mint","photo":"https://x/sign/g1.jpg","system":false,
          "created_by":"aaaaaaaa-0000-4000-8000-000000000001","created_by_name":"Moi","created_at":"2026-11-17T10:00:00Z",
          "events_need_approval":true,"announce_mode":"free"},
         "me":"aaaaaaaa-0000-4000-8000-000000000001","member":true,"manage":true,"creator":true,"can_create_event":true,
         "can_set_rules":true,"phone_shared":true,"unread":4,
         "members":[{"id":"aaaaaaaa-0000-4000-8000-000000000001","name":"Moi","photo":null,"creator":true,"me":true},
                    {"id":"b","name":"Léa","photo":"https://x/sign/lea.jpg","creator":false,"me":false}],
         "upcoming":[{"id":"e1","title":"Fondue","start":"2026-11-27T18:00:00Z","place":"Chalet","going":5,"mine":"yes"}],
         "past":[{"id":"e0","title":"Bowling"}]}
        """#)
        #expect(p.group.eventsNeedApproval && p.group.announceMode == "free" && p.group.title == "La bande")
        #expect(p.canCreateEvent && p.canSetRules && p.phoneShared && p.unread == 4)
        #expect(p.members.map(\.name) == ["Moi", "Léa"] && p.myName == "Moi")
        #expect(p.upcoming.first?.going == 5 && p.past.first?.title == "Bowling")
        // Créateur : il gère, invite, joue aux pronos, mais ne quitte pas son groupe (il le supprime).
        #expect(p.showsSettings && p.showsInvite && p.showsPronos && !p.canLeave && !p.canReportPhoto)
        #expect(GroupText.subtitle(p) == "2 membres · créé par toi")
    }

    @Test("Membres Vendredi Party : jamais de photo, ni Inviter, ni Quitter, ni Pronos ; son nom affiché")
    func systemGroup() throws {
        let p = try page(#"""
        {"group":{"id":"vp","name":"Vendredi Party","emoji":"🎉","color":"lavender","photo":null,"system":true},
         "me":"m","member":true,"manage":false,"creator":false,"members":[{"id":"m","name":"Moi","creator":false,"me":true}]}
        """#)
        #expect(p.group.title == "Membres Vendredi Party")
        #expect(!p.showsInvite && !p.canLeave && !p.showsPronos && !p.canReportPhoto && p.showsSettings)
        #expect(GroupText.subtitle(p) == "Toute la communauté · 1 membre")
        #expect(p.upcoming.isEmpty && p.past.isEmpty && p.group.announceMode == "request")
    }

    @Test("Simple membre : ni Inviter ni réglages des événements ; il quitte et peut signaler la photo")
    func simpleMember() throws {
        let p = try page(#"""
        {"group":{"id":"g1","name":"Foot","emoji":"⚽","color":"sky","photo":"https://x/sign/p.jpg","system":false,
          "created_by":"c","created_by_name":"Chloé"},
         "me":"m","member":true,"manage":false,"creator":false,"can_create_event":false,"can_set_rules":false,
         "members":[{"id":"c","name":"Chloé","creator":true,"me":false},{"id":"m","name":"Moi","creator":false,"me":true}]}
        """#)
        #expect(!p.showsInvite && !p.canSetRules && !p.canCreateEvent && p.canLeave && p.canReportPhoto && p.showsPronos)
        #expect(GroupText.subtitle(p) == "2 membres · créé par Chloé")
    }

    @Test("Liste : mes groupes, invitations et autres groupes (admin) ; photos et visages signés")
    func decodesHome() throws {
        let home = try PeopleStore.decoder.decode(GroupsHome.self, from: Data(#"""
        {"groups":[{"id":"vp","name":"Vendredi Party","emoji":"🎉","color":"lavender","system":true,"members":40,"unread":0,"faces":[]},
                   {"id":"g1","name":"Foot","emoji":"⚽","color":"sky","photo":"https://x/g1.jpg","system":false,"creator":true,
                    "manage":true,"member":true,"members":3,"faces":[{"id":"b","name":"Léa","photo":"https://x/b.jpg"}],
                    "last":"On y va ?","last_by":"Léa","last_at":"2026-11-18T19:00:00Z","unread":2,
                    "next_event":{"id":"e1","title":"Match","starts_at":"2026-11-20T18:00:00Z","date_mode":"fixed"}}],
         "invitations":[{"id":"i1","group_id":"g2","group":"Rando","emoji":"🥾","color":"mint","invited_by":"Noé"}],
         "others":[{"id":"g3","name":"Autre","emoji":"🎲","color":"coral","photo":null,"system":false,"members":5}]}
        """#.utf8))
        #expect(home.groups.first?.title == "Membres Vendredi Party" && home.groups[1].unread == 2)
        #expect(home.groups[1].faces.first?.photo == "https://x/b.jpg" && home.groups[1].nextEvent?.title == "Match")
        #expect(home.invitations.first?.groupId == "g2" && home.invitations.first?.invitedBy == "Noé")
        #expect(home.others.first?.members == 5)
        let empty = try PeopleStore.decoder.decode(GroupsHome.self, from: Data("{}".utf8))
        #expect(empty.groups.isEmpty && empty.invitations.isEmpty && empty.others.isEmpty)
    }

    @Test("Personnes croisées et liens uniques")
    func suggestionsAndLinks() throws {
        let s = try PeopleStore.decoder.decode([GroupSuggestion].self, from: Data(#"""
        [{"id":"b","display_name":"Léa","photo":"https://x/b.jpg","together":3,"last_title":"Fondue","invited":false},
         {"id":"c","display_name":"Noé","together":1,"last_title":"Bowling","invited":true}]
        """#.utf8))
        #expect(GroupText.suggestion(s[0], sent: false) == "3 soirées ensemble")
        #expect(GroupText.suggestion(s[0], sent: true) == "Invitation envoyée")
        #expect(GroupText.suggestion(s[1], sent: false) == "Invitation envoyée")
        let links = try PeopleStore.decoder.decode([GroupLinkRow].self, from: Data(#"""
        [{"token":"t1","created_at":"2026-11-18T10:00:00Z","expires_at":"2026-11-25T10:00:00Z","used_by":"Léa","status":"used"},
         {"token":"t2","status":"pending"},{"token":"t3","status":"revoked"}]
        """#.utf8))
        #expect(links.map(GroupText.linkStatus) == ["Utilisé par Léa", "En attente", "Annulé"])
    }

    @Test("Textes : noms, numéros tapés, message d'invitation, date de création")
    func texts() throws {
        #expect(GroupText.names(["Chloé"]) == "Chloé")
        #expect(GroupText.names(["Chloé", "Malik"]) == "Chloé et Malik")
        #expect(GroupText.names(["Chloé", "Malik", "Inès"]) == "Chloé, Malik et Inès")
        #expect(GroupText.names(["A", "B", "C", "D", "E"]) == "A, B et 3 autres")
        #expect(GroupText.phone("079 123 45 67") == "41791234567")
        #expect(GroupText.phone("+41 79 123 45 67") == "41791234567")
        #expect(GroupText.phone("Léa") == nil && GroupText.phone("1234") == nil)
        let p = try page(#"{"group":{"id":"g","name":"Foot","emoji":"⚽"},"me":"m","members":[]}"#)
        #expect(GroupText.inviteMessage(host: "", group: p.group, url: "https://p/x")
                == "Hello ! Moi t’invite dans le groupe « ⚽ Foot » sur Party. Rejoins-le ici : https://p/x")
        #expect(GroupText.createdLine("2026-11-17T10:00:00Z") == "Groupe créé le 17 novembre 2026")
        #expect(GroupText.emojis.count == 16 && GroupText.colors.count == 6 && GroupText.nameMax == 60)
    }

    @Test("Routes : liste, création, page d'un UUID ; rien d'autre")
    func routes() {
        #expect(GroupRoute.from(nil) == .list)
        #expect(GroupRoute.from("new") == .create)
        #expect(GroupRoute.from("5E0D6A51-8F1C-4C51-9A6B-2B8F1E4C0A02") == .page("5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a02"))
        #expect(GroupRoute.from("../admin") == nil)
        #expect(ReportTarget.Kind.groupPhoto.rawValue == "group_photo")
    }

    @Test("Photo : recadrée en carré, 1024 au plus, en JPEG")
    func photoCrop() throws {
        let image = UIGraphicsImageRenderer(size: CGSize(width: 2000, height: 1000)).image { ctx in
            UIColor.systemPink.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 2000, height: 1000))
        }
        let data = try #require(GroupPhotoCrop.squareJPEG(image))
        let out = try #require(UIImage(data: data))
        #expect(out.size.width == out.size.height && out.size.width <= 1024)
        #expect(data.starts(with: [0xFF, 0xD8, 0xFF]))
    }
}
