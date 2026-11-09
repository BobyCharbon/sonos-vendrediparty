import SwiftUI

/// Modération commune : signaler, bloquer, conditions d'utilisation, file des modérateurs ; avec la session du compte.
@MainActor
final class ModerationStore: ObservableObject {
    @Published private(set) var blocked: [BlockedPerson]?
    @Published private(set) var terms: TermsStatus?
    @Published private(set) var queue: ModerationQueue?
    /// Accord « IA de Party » du compte (Réglages › Confidentialité), pour tous les comptes ; nil tant qu'il n'est pas lu.
    @Published private(set) var aiConsent: AIConsentState?
    @Published private(set) var busy: Set<String> = []
    @Published var error: String?
    @Published var notice: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    #if DEBUG
    /// Tests et aperçus : un état sans serveur.
    func showDemo(blocked: [BlockedPerson]? = nil, terms: TermsStatus? = nil, queue: ModerationQueue? = nil) {
        self.blocked = blocked
        self.terms = terms
        self.queue = queue
    }
    #endif

    // MARK: Signaler

    /// true si le signalement est parti ; sinon `error` dit pourquoi (limite anti-abus, contenu disparu…).
    func report(_ target: ReportTarget, reason: ReportReason, comment: String) async -> Bool {
        var sent = false
        await run("report") { token in
            try await api.report(token: token, target: target, reason: reason, comment: comment)
            sent = true
        }
        return sent
    }

    // MARK: Personnes bloquées

    func loadBlocked() async {
        await run("blocks") { token in blocked = try await api.blockedPeople(token: token) }
    }

    func setBlocked(_ user: String, _ on: Bool) async {
        await run(user) { token in blocked = try await api.setBlock(token: token, user: user, on: on) }
    }

    // MARK: Conditions d'utilisation

    func loadTerms() async {
        await run("terms") { token in terms = try await api.terms(token: token) }
    }

    /// Avant le premier contenu : true si les conditions sont déjà acceptées (relues au besoin).
    func termsAccepted() async -> Bool {
        if terms?.accepted == true { return true }
        await loadTerms()
        // Serveur injoignable : on laisse passer, la base reste la garde (« Exiger les CGU »).
        return terms?.accepted ?? true
    }

    func acceptTerms() async -> Bool {
        if terms == nil { await loadTerms() }
        guard let version = terms?.version else { return false }
        await run("accept") { token in terms = try await api.acceptTerms(token: token, version: version) }
        return terms?.accepted == true
    }

    // MARK: Accord IA

    func loadAIConsent() async {
        await run("ai") { token in aiConsent = try await api.accountAIConsent(token: token) }
    }

    /// Retirer (false) ou donner (true, après la feuille d'accord) : le même accord que « Ton avis » et l'assistant.
    func setAIConsent(_ accept: Bool) async {
        await run("ai") { token in aiConsent = try await api.setAccountAIConsent(token: token, accept: accept) }
    }

    // MARK: Signalements (modérateurs)

    func loadQueue(_ status: String) async {
        await run("queue") { token in queue = try await api.moderationQueue(token: token, status: status) }
    }

    func act(_ report: ModerationReport, _ action: ModerationAction, note: String, days: Int?, status: String) async {
        await run(report.id) { token in
            queue = try await api.moderate(token: token, report: report.id, action: action, note: note, days: days, status: status)
            notice = ModerationReport.resolutions[action.rawValue]
        }
    }

    func lift(_ report: ModerationReport) async {
        guard let user = report.user?.id else { return }
        await run(report.id) { token in
            queue = try await api.liftSanction(token: token, user: user)
            notice = "\(report.user?.name ?? "Le compte") est réintégré"
        }
    }

    func saveSettings(contactEmail: String?, termsEnforced: Bool?) async {
        await run("settings") { token in
            queue = try await api.moderationSettings(token: token, contactEmail: contactEmail, termsEnforced: termsEnforced)
            notice = "Enregistré"
        }
    }

    private func run(_ key: String, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi d'abord"
            return
        }
        busy.insert(key)
        defer { busy.remove(key) }
        do {
            try await work(token)
            error = nil
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi"
        } catch is CancellationError {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }
}
