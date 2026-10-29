import SwiftUI

/// Réglages › Administration du groupe : données et actions, avec la session du compte.
/// Chaque action renvoie l'écran à jour (le serveur relit après avoir écrit).
@MainActor
final class GroupAdminStore: ObservableObject {
    @Published private(set) var overview: AdminOverview?
    @Published private(set) var members: AdminMembers?
    @Published private(set) var roles: AdminRoles?
    @Published private(set) var error: String?
    @Published private(set) var busy: Set<String> = []
    @Published var notice: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    #if DEBUG
    /// Simulateur : PARTY_DEBUG_GROUP_ADMIN={"overview": …, "members": …, "roles": …} affiche l'écran sans serveur.
    struct Demo: Decodable {
        let overview: AdminOverview
        let members: AdminMembers
        let roles: AdminRoles
    }

    func showDemo(_ demo: Demo) {
        overview = demo.overview
        members = demo.members
        roles = demo.roles
    }
    #endif

    // MARK: Accueil

    func loadOverview() async {
        await run("overview", loading: overview == nil) { token in overview = try await api.groupAdmin(token: token) }
    }

    func decide(_ proposal: AdminOverview.Proposal, approve: Bool, reason: String? = nil) async {
        await run(proposal.id) { token in
            overview = try await api.decideProposal(token: token, id: proposal.id, approve: approve, reason: reason)
            notice = approve ? "« \(proposal.title) » publié" : "« \(proposal.title) » refusé"
        }
    }

    func decide(_ request: AdminOverview.JoinRequest, accept: Bool) async {
        await run(request.id) { token in
            overview = try await api.decideJoin(token: token, id: request.id, accept: accept)
            notice = accept ? "\(request.name) a rejoint le groupe" : "Demande refusée"
        }
    }

    func setRequireApproval(_ on: Bool) async {
        await run("approval") { token in overview = try await api.setRequireApproval(token: token, on: on) }
    }

    // MARK: Membres

    func loadMembers() async {
        await run("members", loading: members == nil) { token in members = try await api.adminMembers(token: token) }
    }

    func setRole(_ role: MemberRole, of person: AdminMembers.Person) async {
        await run(person.id) { token in members = try await api.updateMember(token: token, id: person.id, role: role) }
    }

    func setBanned(_ banned: Bool, _ person: AdminMembers.Person) async {
        await run(person.id) { token in
            members = try await api.updateMember(token: token, id: person.id, status: banned ? "banned" : "active")
            notice = banned ? "Accès retiré à \(person.displayName)" : "\(person.displayName) est réintégré"
        }
    }

    func setBeta(_ on: Bool, _ person: AdminMembers.Person) async {
        await run(person.id) { token in members = try await api.updateMember(token: token, id: person.id, beta: on) }
    }

    func delete(_ person: AdminMembers.Person, confirmName: String) async -> Bool {
        var done = false
        await run(person.id) { token in
            members = try await api.deleteMember(token: token, id: person.id, confirmName: confirmName)
            notice = "Compte de \(person.displayName) supprimé"
            done = true
        }
        return done
    }

    // MARK: Rôles et droits

    func loadRoles() async {
        await run("roles", loading: roles == nil) { token in roles = try await api.adminRoles(token: token) }
    }

    func toggle(_ perm: String, for role: MemberRole, on: Bool) async {
        await run("\(role.rawValue).\(perm)") { token in roles = try await api.setPermission(token: token, role: role, perm: perm, on: on) }
    }

    // MARK: Journal (lu à la demande, page par page)

    func journal(member: String?, before: Int?) async -> AdminJournal? {
        var page: AdminJournal?
        await run("journal") { token in page = try await api.adminJournal(token: token, member: member, before: before) }
        return page
    }

    /// loading : premier chargement d'un écran, l'erreur prend sa place ; sinon elle s'affiche en bandeau.
    private func run(_ key: String, loading: Bool = false, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi pour administrer le groupe"
            return
        }
        busy.insert(key)
        defer { busy.remove(key) }
        do {
            try await work(token)
            if loading { error = nil }
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi dans Événements"
        } catch {
            if loading { self.error = error.localizedDescription } else { notice = error.localizedDescription }
        }
    }
}
