import Combine
import Foundation
import UIKit

/// Réglages natifs : le compte relié (carte du haut) et Réglages › Notifications, rangées par catégorie.
/// Trois sources : le serveur Party (invité, hôte), Supabase via le serveur (événements du compte),
/// et cet iPhone (autorisation iOS, Live Activity).
@MainActor
final class SettingsStore: ObservableObject {
    struct Notice: Equatable {
        let text: String
        let isError: Bool
    }

    enum EventsPhase: Equatable {
        case signedOut
        case loading
        case ready(EventNotifyState)
        case failed(String)
    }

    @Published private(set) var account: AccountSummary?
    /// Autorisation iOS : granted, denied ou default (jamais demandée).
    @Published private(set) var permission = "default"
    /// nil : code de la soirée pas encore saisi (le serveur refuse) ou hors ligne.
    @Published private(set) var guest: GuestNotifyState?
    /// nil : pas l'hôte.
    @Published private(set) var host: AdminNotifyState?
    @Published private(set) var events: EventsPhase = .signedOut
    @Published private(set) var liveActivities = LiveActivitySetting.isEnabled
    /// Mon profil ; nil tant qu'il n'est pas lu (ou pas connecté).
    @Published private(set) var profile: MemberProfile?
    @Published private(set) var profileError: String?
    @Published private(set) var savingProfile = false
    /// Type en cours d'enregistrement (interrupteur désactivé pendant ce temps).
    @Published private(set) var saving: Set<String> = []
    @Published var notice: Notice?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private let isHost: () -> Bool
    /// L'interrupteur de l'écran Musique suit le type « titre qui passe ».
    private let trackChanged: (Bool, Bool) -> Void

    init(api: PartyAPI, web: WebStorage, isHost: @escaping () -> Bool, trackChanged: @escaping (Bool, Bool) -> Void) {
        self.api = api
        self.web = web
        self.isHost = isHost
        self.trackChanged = trackChanged
    }

    var hostMode: Bool { host != nil }
    var deviceSubscribed: Bool { permission == "granted" && guest?.subscribed == true }

    // MARK: Chargement

    /// Écran affiché : le compte seulement (rapide), la carte du haut en dépend.
    func refreshAccount() async {
        account = AccountSummary.parse(await web?.readLocal("vp_account"))
    }

    func loadNotifications() async {
        await refreshAccount()
        permission = await PushRegistrar.shared.status()
        liveActivities = LiveActivitySetting.isEnabled
        async let party: Void = loadParty()
        async let member: Void = loadEvents()
        _ = await (party, member)
    }

    private func loadParty() async {
        if let me = await web?.guestIdentity() {
            guest = try? await api.notifyPrefs(guestID: me.id)
        }
        host = isHost() ? try? await api.adminNotifyPrefs() : nil
    }

    private func loadEvents() async {
        guard account != nil, let token = await web?.accountToken() else {
            events = .signedOut
            return
        }
        if case .ready = events {} else { events = .loading }
        do {
            events = .ready(try await api.eventNotifyPrefs(token: token))
        } catch {
            events = .failed(Self.accountMessage(error))
        }
    }

    // MARK: Mon profil

    func loadProfile() async {
        guard let token = await web?.accountToken() else {
            profileError = "Connecte-toi pour modifier ton profil"
            return
        }
        do {
            profile = try await api.profile(token: token)
            profileError = nil
        } catch {
            profileError = Self.accountMessage(error)
        }
    }

    /// true : enregistré. La page relit le compte (surnom et photo partout : jeux, carte des Réglages).
    func saveProfile(first: String, last: String, nickname: String, photo: Data?) async -> Bool {
        guard let token = await web?.accountToken() else { return false }
        savingProfile = true
        defer { savingProfile = false }
        do {
            profile = try await api.updateProfile(token: token, firstName: ProfileRules.clean(first), lastName: ProfileRules.clean(last),
                                                  nickname: ProfileRules.clean(nickname), photo: photo)
            await web?.accountChanged()
            await refreshAccount()
            notice = Notice(text: "✓ Profil enregistré", isError: false)
            return true
        } catch {
            notice = Notice(text: Self.accountMessage(error), isError: true)
            return false
        }
    }

    // MARK: Cet iPhone

    /// Notifications de la soirée sur cet iPhone (musique, jeux, avis) : abonnement de l'appareil.
    func setDevice(_ on: Bool) async {
        guard let me = await web?.guestIdentity() else { return }
        await save("device") {
            if on {
                try await subscribeDevice(me)
            } else if let endpoint = await savedEndpoint() {
                try await api.unsubscribePush(endpoint: endpoint)
                web?.writeLocal(PushRegistrar.pageKey, nil)
            }
            guest = try await api.notifyPrefs(guestID: me.id)
            permission = await PushRegistrar.shared.status()
            trackChanged(guest?.prefs["track"] ?? true, deviceSubscribed)
        }
    }

    func setLiveActivities(_ on: Bool) {
        LiveActivitySetting.isEnabled = on
        liveActivities = on
        if !on { TrackActivities.endAll() }
        notice = Notice(text: on ? "Le décompte de ton titre s'affichera dans la Dynamic Island"
                                 : "Plus de décompte dans la Dynamic Island", isError: false)
    }

    func openSystemSettings() {
        if let url = URL(string: UIApplication.openNotificationSettingsURLString) { UIApplication.shared.open(url) }
    }

    // MARK: Soirée (invité, hôte)

    /// Un type choisi alors que l'iPhone n'est pas abonné : on l'abonne d'abord, sinon rien n'arriverait.
    func setGuest(_ kind: String, _ on: Bool) async {
        guard let me = await web?.guestIdentity() else { return }
        await save(kind) {
            if on && !deviceSubscribed { try await subscribeDevice(me) }
            guest = try await api.setNotify(guestID: me.id, kind: kind, on: on)
            if kind == "track" { trackChanged(on, deviceSubscribed) }
        }
    }

    func setHost(_ kind: String, _ on: Bool) async {
        await save("host." + kind) {
            if on {
                let device = try await PushRegistrar.shared.device()
                try await api.subscribeAdminPush(device: device)
                permission = await PushRegistrar.shared.status()
            }
            host = try await api.setAdminNotify(kind: kind, on: on)
        }
    }

    // MARK: Événements (compte)

    func setEvents(_ key: String, _ value: Any) async {
        guard case .ready(var state) = events, let token = await web?.accountToken() else { return }
        let before = state
        state.prefs = Self.applying(key, value, to: state.prefs)
        events = .ready(state)  // tout de suite à l'écran ; remis comme avant si l'enregistrement échoue
        await save("events." + key) {
            do {
                events = .ready(try await api.updateEventNotifyPrefs(token: token, patch: [key: value]))
            } catch {
                events = .ready(before)
                throw PartyAPIError.server(Self.accountMessage(error))
            }
        }
    }

    func setQuietHours(_ on: Bool) async {
        guard case .ready(var state) = events, let token = await web?.accountToken() else { return }
        let before = state
        state.prefs.quietStart = on ? QuietTime.defaultStart : nil
        state.prefs.quietEnd = on ? QuietTime.defaultEnd : nil
        events = .ready(state)
        let patch: [String: Any] = on ? ["quiet_start": QuietTime.defaultStart, "quiet_end": QuietTime.defaultEnd]
                                      : ["quiet_start": NSNull(), "quiet_end": NSNull()]
        await save("events.quiet") {
            do {
                events = .ready(try await api.updateEventNotifyPrefs(token: token, patch: patch))
            } catch {
                events = .ready(before)
                throw PartyAPIError.server(Self.accountMessage(error))
            }
        }
    }

    /// Début ou fin des heures de silence ; début = fin refusé (la plage serait vide).
    func setQuietTime(start: Bool, _ date: Date) async {
        guard case .ready(let state) = events else { return }
        let text = QuietTime.text(date)
        if QuietTime.same(text, start ? state.prefs.quietEnd : state.prefs.quietStart) {
            notice = Notice(text: "Le début et la fin des heures de silence doivent être différents", isError: true)
            return
        }
        await setEvents(start ? "quiet_start" : "quiet_end", text)
    }

    func toggleReminder(_ key: String, _ on: Bool) async {
        guard case .ready(let state) = events else { return }
        await setEvents("reminders", EventChoices.reminders(state.prefs.reminders, toggling: key, on: on))
    }

    // MARK: Outils

    private func subscribeDevice(_ me: GuestIdentity) async throws {
        let device = try await PushRegistrar.shared.device()
        try await api.subscribePush(guestID: me.id, device: device, keepPrefs: true)
        web?.writeLocal(PushRegistrar.pageKey, String(data: try JSONSerialization.data(withJSONObject: device), encoding: .utf8))
        if isHost() { try? await api.subscribeAdminPush(device: device) }
        permission = await PushRegistrar.shared.status()
    }

    private func savedEndpoint() async -> String? {
        guard let saved = await web?.readLocal(PushRegistrar.pageKey), let data = saved.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["endpoint"] as? String
    }

    private func save(_ key: String, _ work: () async throws -> Void) async {
        saving.insert(key)
        defer { saving.remove(key) }
        do {
            try await work()
        } catch PartyAPIError.needsCode {
            notice = Notice(text: "Entre d'abord le code de la soirée (onglet Musique)", isError: true)
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
        }
    }

    /// Le serveur répond 401 quand la session du compte a expiré (PartyAPI le lit comme « code requis »).
    private static func accountMessage(_ error: Error) -> String {
        if case PartyAPIError.needsCode = error { return "Ta connexion a expiré : reconnecte-toi dans Événements" }
        return error.localizedDescription
    }

    static func applying(_ key: String, _ value: Any, to prefs: EventNotificationPrefs) -> EventNotificationPrefs {
        var p = prefs
        switch (key, value) {
        case ("push_enabled", let v as Bool): p.pushEnabled = v
        case ("new_event", let v as String): p.newEvent = v
        case ("event_changed", let v as Bool): p.eventChanged = v
        case ("poll_new", let v as Bool): p.pollNew = v
        case ("date_fixed", let v as Bool): p.dateFixed = v
        case ("poll_nudge", let v as Bool): p.pollNudge = v
        case ("waitlist", let v as Bool): p.waitlist = v
        case ("reminders", let v as [String]): p.reminders = v
        case ("chat", let v as String): p.chat = v
        case ("rsvp_mine", let v as Bool): p.rsvpMine = v
        case ("proposals", let v as Bool): p.proposals = v
        case ("quiet_start", let v as String): p.quietStart = v
        case ("quiet_end", let v as String): p.quietEnd = v
        default: break
        }
        return p
    }
}
