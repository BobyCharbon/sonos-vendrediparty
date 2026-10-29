import Foundation

/// Réglages natifs › compte : connexion par SMS, déconnexion, suppression, annonces admin, stats de jeu.
/// La session vit dans la page (localStorage) : la page, les jeux et les Réglages natifs partagent le même compte.
@MainActor
final class AccountStore: ObservableObject {
    enum Step: Equatable {
        case phone
        case code(String)
    }

    @Published var step: Step = .phone
    @Published private(set) var busy = false
    @Published var error: String?
    @Published var notice: String?
    @Published private(set) var announcements: AnnouncementPage?
    @Published private(set) var stats: PurityStats?
    @Published private(set) var statsError: String?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private weak var settings: SettingsStore?

    init(api: PartyAPI, web: WebStorage?, settings: SettingsStore?) {
        self.api = api
        self.web = web
        self.settings = settings
    }

    // MARK: Connexion

    func sendCode(_ phone: String) async {
        await work {
            try await api.sendLoginCode(phone: phone)
            step = .code(phone)
        }
    }

    /// true : connecté (la page a relié le compte, la carte des Réglages le montre).
    func verify(_ code: String) async -> Bool {
        guard case .code(let phone) = step else { return false }
        var done = false
        await work {
            let signIn = try await api.verifyLoginCode(phone: phone, code: code)
            await web?.storeSession(key: signIn.storageKey, json: signIn.sessionJSON)
            await settings?.accountSwitched()
            step = .phone
            done = true
        }
        return done
    }

    // MARK: Déconnexion et suppression

    func signOut() async {
        busy = true
        defer { busy = false }
        await settings?.accountWillSignOut()
        if let token = await web?.accountToken() { try? await api.signOut(token: token) }
        await web?.clearSession()
        await settings?.accountSwitched()
        announcements = nil
        stats = nil
        notice = "Tu es déconnecté"
    }

    func deleteAccount() async -> Bool {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi d'abord"
            return false
        }
        var done = false
        await work {
            await settings?.accountWillSignOut()
            try await api.deleteAccount(token: token)
            await web?.clearSession()
            await settings?.accountSwitched()
            done = true
        }
        return done
    }

    // MARK: Annonces admin

    func loadAnnouncements() async {
        await withToken { token in announcements = try await api.announcements(token: token) }
    }

    func loadOlderAnnouncements() async {
        guard let current = announcements, let last = current.announcements.last else { return }
        await withToken { token in
            let page = try await api.announcements(token: token, after: last)
            announcements = AnnouncementPage(announcements: current.announcements + page.announcements, more: page.more)
        }
    }

    func publish(title: String, body: String) async -> Bool {
        var done = false
        await withToken { token in
            announcements = try await api.publishAnnouncement(token: token, title: title, body: body)
            notice = "Annonce publiée pour tout le groupe"
            done = true
        }
        return done
    }

    // MARK: Mes stats de jeu

    func loadStats() async {
        guard let token = await web?.accountToken() else {
            statsError = "Connecte-toi avec ton numéro pour retrouver tes stats Purify Test."
            return
        }
        do {
            stats = try await api.purityStats(token: token)
            statsError = nil
        } catch PartyAPIError.needsCode {
            statsError = "Ta connexion a expiré : reconnecte-toi."
        } catch {
            statsError = "Impossible de charger tes stats : \(error.localizedDescription)"
        }
    }

    private func withToken(_ job: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi d'abord"
            return
        }
        await work { try await job(token) }
    }

    private func work(_ job: () async throws -> Void) async {
        busy = true
        defer { busy = false }
        do {
            try await job()
            error = nil
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi."
        } catch {
            self.error = error.localizedDescription
        }
    }
}

