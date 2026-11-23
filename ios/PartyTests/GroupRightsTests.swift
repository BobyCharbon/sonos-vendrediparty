import Foundation
import Testing
@testable import Party

/// Réglages du groupe pour son admin (23.11) : décodage de group_admin_panel (relais), textes des rôles et de « Qui peut… »
/// (mêmes que web/events/src/lib/groupRights.ts), écran d'un droit dans la pile des groupes.
struct GroupRightsTests {
    private func panel(_ json: String) throws -> GroupPanel {
        try PeopleStore.decoder.decode(GroupPanel.self, from: Data(json.utf8))
    }

    @Test("Panneau : mes droits, les droits du groupe, les rôles et les demandes")
    func decodesThePanel() throws {
        let p = try panel(#"""
        {"group":{"id":"g1","name":"La bande","emoji":"🎸","color":"mint","photo":null,"system":false,"created_by":"me"},
         "me":{"role":"coadmin","manage":true,"rules":true,"owner":false,"invite":true,"events":true,"announce":true,
               "write":true,"pin":true,"edit":true,"remove":true},
         "rights":{"invite":"members","events":"members","announce":"staff","write":"admins","pin":"admins","edit":"admins","remove":"admins"},
         "events_need_approval":true,"announce_mode":"free","join_approval":true,"link_active":true,
         "members":[{"id":"me","name":"Moi","photo":null,"role":"creator","since":"2026-11-04T10:00:00Z"},
                    {"id":"l","name":"Léa","photo":"https://x/l.jpg","role":"coadmin","since":null},
                    {"id":"m","name":"Malik","photo":null,"role":"organizer","since":null}],
         "requests":[{"id":"i","name":"Inès","photo":null,"at":"2026-11-23T08:00:00Z","via":"link"}]}
        """#)
        #expect(p.me.role == "coadmin" && p.me.manage && p.me.rules && !p.me.owner)
        #expect(p.level("announce") == "staff" && p.level("write") == "admins" && p.eventsNeedApproval && p.joinApproval)
        #expect(p.with("organizer").map(\.name) == ["Malik"] && p.requests.map(\.name) == ["Inès"])
        #expect(GroupRightsText.since(p.members[0].since) == "Dans le groupe depuis le 4 novembre")
    }

    @Test("Un panneau incomplet (serveur d'avant) se lit avec les droits d'avant")
    func missingFieldsKeepTheOldDefaults() throws {
        let p = try panel(#"{"me":{"role":"member"}}"#)
        #expect(!p.me.manage && !p.me.edit && p.level("invite") == "members" && p.level("pin") == "admins")
        #expect(!p.joinApproval && p.members.isEmpty)
    }

    @Test("Textes : qui peut, les choix, les rôles")
    func texts() {
        #expect(GroupRightsText.rights.map(\.label) == [
            "Inviter des personnes", "Créer un événement pour le groupe", "Prévenir tout le groupe (@tout, annonce)",
            "Écrire dans la discussion", "Épingler un message", "Modifier le nom, l’emoji et la photo", "Retirer un membre"])
        #expect(GroupRightsText.who("events", "members", needApproval: true).text == "Membres · à valider par un admin")
        #expect(GroupRightsText.who("events", "members", needApproval: false).text == "Tous les membres")
        #expect(GroupRightsText.who("pin", "staff", needApproval: true).text == "Organisateurs et admins")
        #expect(GroupRightsText.levelDetail("events", "staff") == "Les membres proposent en message, pas d’événement.")
        #expect(GroupRightsText.levelDetail("write", "admins") == "Toi et les co-admins.")
        #expect(GroupRightsText.roleDetail("coadmin") == "Comme toi : réglages, rôles, membres. Sauf supprimer le groupe.")
        #expect(GroupRightsText.myRole("creator") == "tu es l’admin du groupe" && GroupRightsText.myRole(nil).isEmpty)
        #expect(GroupRightsText.editLine("admins").hasPrefix("Seuls l’admin et les co-admins"))
    }

    @Test("Un droit s'ouvre dans la pile des groupes")
    func rightRoute() {
        #expect(GroupScreen.right("g1", "events") == GroupScreen.right("g1", "events"))
        #expect(GroupScreen.right("g1", "events") != GroupScreen.right("g1", "write"))
    }
}
