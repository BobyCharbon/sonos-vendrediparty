import Combine
import Foundation
import UIKit

/// « Gérer la soirée » natif : tout ce que fait la page admin de la musique (app/static/music-admin.js), avec les
/// mêmes appels. Suivi en direct par le flux du serveur ; chaque action renvoie le nouvel état.
@MainActor
final class HostMusicStore: ObservableObject {
    struct Notice: Equatable, Identifiable {
        let id = UUID()
        let text: String
        var isError = false
        /// Retrait annulable : « Annuler » remet les titres à leur place.
        var undo: String?
    }

    enum Phase: Equatable { case loading, ready, failed(String) }

    @Published private(set) var phase: Phase = .loading
    @Published private(set) var state: AdminState?
    @Published private(set) var stateAt = Date()
    @Published var notice: Notice?

    // Démarrage
    @Published private(set) var rooms: [SonosRoom] = []
    @Published private(set) var roomsError: String?
    @Published var chosenRoom = ""
    @Published var chosenSource = "sonos"
    @Published var chosenMode = InsertMode.next.rawValue

    // Ajout
    @Published var query = "" { didSet { scheduleSearch() } }
    @Published private(set) var results: [HostSearchTrack] = []
    @Published private(set) var searching = false
    /// Doublon à confirmer : (titre, où, message).
    @Published var duplicate: (track: HostSearchTrack, place: String, message: String)?

    // Enceintes, playlists Sonos, événements
    @Published private(set) var speakers: [Speaker] = []
    @Published private(set) var speakersError: String?
    @Published private(set) var sonosPlaylists: [SonosPlaylist] = []
    @Published private(set) var eventOptions: [EventOption] = []

    /// Action en cours (bouton désactivé pendant ce temps).
    @Published private(set) var busy: Set<String> = []

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var liveTask: Task<Void, Never>?
    private var searchTask: Task<Void, Never>?
    private var volumeTask: Task<Void, Never>?
    private var speakerVolumeTask: Task<Void, Never>?
    private static let reconnectDelay: Duration = .seconds(3)
    private static let searchDelay: Duration = .milliseconds(350)
    private static let volumeDelay: Duration = .milliseconds(250)

    init(api: PartyAPI, web: WebStorage) {
        self.api = api
        self.web = web
    }

    // MARK: Suivi

    func start() {
        #if DEBUG
        if demo { return }
        #endif
        guard liveTask == nil else { return }
        liveTask = Task { [weak self] in
            await self?.reload()
            while !Task.isCancelled {
                do {
                    guard let api = self?.api else { return }
                    for try await line in try await api.liveEvents().lines where line.hasPrefix("data:") {
                        await self?.reload()
                    }
                } catch {}
                try? await Task.sleep(for: Self.reconnectDelay)
            }
        }
    }

    func stop() {
        liveTask?.cancel()
        liveTask = nil
    }

    func reload() async {
        do {
            apply(try await api.adminState())
            if state?.active == false && rooms.isEmpty { await loadRooms() }
        } catch {
            if state == nil || error as? PartyAPIError == .needsCode { phase = .failed(Self.message(error)) }
        }
    }

    private func apply(_ new: AdminState) {
        state = new
        stateAt = Date()
        phase = .ready
    }

    /// Action de l'hôte : bouton occupé, erreur affichée, état rafraîchi.
    private func run(_ key: String, _ work: () async throws -> Void) async {
        busy.insert(key)
        defer { busy.remove(key) }
        do {
            try await work()
        } catch {
            notice = Notice(text: Self.message(error), isError: true)
            await reload()
        }
    }

    /// Pour l'hôte, un refus 401 veut dire « session d'hôte expirée », pas « code de la soirée ».
    static func message(_ error: Error) -> String {
        if case PartyAPIError.needsCode = error {
            return "Session d'hôte expirée : reconnecte-toi avec ton compte (Réglages) ou le code admin."
        }
        return error.localizedDescription
    }

    // MARK: Démarrer / arrêter

    func loadRooms() async {
        roomsError = nil
        do {
            rooms = try await api.adminRooms()
            if chosenRoom.isEmpty || !rooms.contains(where: { $0.uid == chosenRoom }) { chosenRoom = rooms.first?.uid ?? "" }
        } catch {
            roomsError = Self.message(error)
        }
    }

    func startParty() async {
        if chosenSource == "sonos" && chosenRoom.isEmpty { notice = Notice(text: "Choisis une pièce", isError: true); return }
        if chosenSource == "spotify" && state?.spotifyAccount?.connected != true {
            notice = Notice(text: "Connecte d'abord ton compte Spotify", isError: true); return
        }
        await run("start") {
            apply(try await api.adminStart(roomUID: chosenRoom, mode: chosenMode, source: chosenSource))
            notice = Notice(text: "Soirée démarrée 🎉")
        }
    }

    func stopParty() async {
        await run("stop") {
            apply(try await api.adminStop())
            notice = Notice(text: "Soirée arrêtée")
            await loadRooms()
        }
    }

    // MARK: Lecture

    func togglePlayback() async {
        let action = state?.sonos?.isPlaying == true ? "pause" : "play"
        await run("playback") { apply(try await api.adminPlayback(action)) }
    }

    func skip() async {
        await run("skip") {
            try await api.adminSkip()
            try? await Task.sleep(for: .milliseconds(800))
            await reload()
        }
    }

    /// Curseur du volume : un envoi au plus toutes les 250 ms pendant le glissement, le dernier à la fin.
    func setVolume(_ volume: Int) {
        volumeTask?.cancel()
        volumeTask = Task { [weak self] in
            try? await Task.sleep(for: Self.volumeDelay)
            guard !Task.isCancelled else { return }
            do { try await self?.api.adminVolume(volume) } catch { self?.notice = Notice(text: Self.message(error), isError: true) }
        }
    }

    // MARK: Ajouter

    private func scheduleSearch() {
        searchTask?.cancel()
        let text = query.trimmingCharacters(in: .whitespaces)
        guard text.count >= 2 else { results = []; searching = false; return }
        searching = true
        searchTask = Task { [weak self] in
            try? await Task.sleep(for: Self.searchDelay)
            guard !Task.isCancelled, let self else { return }
            do {
                let found = try await self.api.adminSearch(text)
                guard self.query.trimmingCharacters(in: .whitespaces) == text else { return }
                self.results = found
            } catch {
                self.notice = Notice(text: Self.message(error), isError: true)
            }
            self.searching = false
        }
    }

    func add(_ track: HostSearchTrack, place: String, force: Bool = false) async {
        await run("add.\(track.id)") {
            do {
                apply(try await api.adminAdd(trackID: track.id, where: place, force: force))
            } catch PartyAPIError.duplicate(let message) {
                duplicate = (track, place, message)
                return
            }
            let ext = state?.usesSpotify == true
            notice = Notice(text: "« \(track.title) » " + (ext ? "envoyé à Spotify" : place == "next" ? "passera juste après" : "ajouté à la suite des demandes") + " 🎶")
            query = ""
            results = []
        }
    }

    // MARK: File d'attente

    func queueAction(_ track: AdminState.QueueTrack, _ action: String) async {
        await run("q.\(track.id)") {
            let change = try await api.adminQueue(pos: track.pos, key: track.key, action: action)
            apply(change.state)
            if action == "remove" { notice = Notice(text: "Titre retiré", undo: change.undo) }
        }
    }

    /// Poignée « réorganiser » lâchée : le titre va à la place du titre visé (un seul déplacement côté Sonos).
    func move(_ track: AdminState.QueueTrack, to position: Int) async {
        #if DEBUG
        if demo, var state, let from = state.queue.firstIndex(of: track), let to = state.queue.firstIndex(where: { $0.pos == position }) {
            state.queue = QueueOrder.moving(state.queue, from: from, to: to)
            apply(state)
            return
        }
        #endif
        await run("q.\(track.id)") {
            apply(try await api.adminQueue(pos: track.pos, key: track.key, action: "move", to: position).state)
        }
    }

    func removeRequest(_ request: AdminState.GuestRequest) async {
        await run("r.\(request.id)") {
            let change = try await api.adminRemoveRequest(request.id)
            apply(change.state)
            notice = Notice(text: "Titre retiré", undo: change.undo)
        }
    }

    func undo(_ token: String) async {
        await run("undo") {
            apply(try await api.adminUndo(token))
            notice = Notice(text: "Remis dans la file ↩︎")
        }
    }

    func setMode(_ mode: InsertMode) async {
        guard state?.active == true else { chosenMode = mode.rawValue; return }
        await run("mode") {
            let change = try await api.adminMode(mode.rawValue)
            apply(change.state)
            let moved = change.reordered ?? 0
            notice = Notice(text: "Mode : \(mode.label)" + (moved > 0 ? " · file réorganisée (\(moved) déplacement\(moved > 1 ? "s" : ""))" : ""))
        }
    }

    // MARK: Accès des invités

    func newPin(_ pin: String? = nil) async {
        if let pin, !GuestPin.isValid(pin) { notice = Notice(text: "Le code doit faire 4 chiffres", isError: true); return }
        await run("pin") {
            apply(try await api.adminPin(pin))
            notice = Notice(text: "Nouveau code : \(state?.guestPin ?? "")")
        }
    }

    func loadEventOptions() async {
        guard let token = await web?.accountToken() else { return }
        eventOptions = (try? await api.adminEventOptions(token: token)) ?? eventOptions
    }

    func linkEvent(_ option: EventOption?) async {
        await run("event") {
            apply(try await api.adminLinkEvent(id: option?.id ?? "", title: option?.title ?? ""))
            notice = Notice(text: option.map { "Soirée liée à « \($0.title) »" } ?? "Plus d'événement lié : le code seulement")
        }
    }

    func guestAction(_ guest: AdminState.Guest, _ action: String, name: String? = nil, minutes: Int? = nil) async {
        let messages = ["rename": "Invité renommé", "kick": "Invité déconnecté : il devra ressaisir le code",
                        "ban": minutes == nil ? "Invité banni" : "Bloqué \(minutes ?? 0) minutes", "unban": "Invité débloqué",
                        "purge": "Titres de \(guest.name) retirés"]
        await run("g.\(guest.id)") {
            let change = try await api.adminGuest(action, guestID: guest.guestID, name: name, minutes: minutes)
            apply(change.state)
            notice = Notice(text: messages[action] ?? "", undo: action == "purge" ? change.undo : nil)
        }
    }

    // MARK: Top playlists

    func editTop(_ body: [String: Any], message: String? = nil) async {
        await run("top") {
            apply(try await api.adminTopPlaylists(body))
            if let message { notice = Notice(text: message) }
        }
    }

    func launch(_ playlist: AdminState.TopPlaylist) async {
        await run("launch.\(playlist.id)") {
            apply(try await api.adminLaunchPlaylist(playlist.id))
            notice = Notice(text: "« \(playlist.title) » lancée en aléatoire 🔀")
        }
    }

    func loadSonosPlaylists() async {
        guard sonosPlaylists.isEmpty else { return }
        sonosPlaylists = (try? await api.adminSonosPlaylists()) ?? []
    }

    // MARK: Enceintes

    func loadSpeakers() async {
        guard state?.active == true, state?.hasSpeakers == true else { return }
        do {
            speakers = try await api.adminSpeakers()
            speakersError = nil
        } catch {
            speakersError = Self.message(error)
        }
    }

    func group(_ speaker: Speaker, join: Bool) async {
        await run("sp.\(speaker.uid)") { speakers = try await api.adminGroupSpeaker(uid: speaker.uid, join: join) }
    }

    func setSpeakerVolume(_ speaker: Speaker, _ volume: Int) {
        speakerVolumeTask?.cancel()
        speakerVolumeTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(200))
            guard !Task.isCancelled else { return }
            do { try await self?.api.adminSpeakerVolume(uid: speaker.uid, volume: volume) }
            catch { self?.notice = Notice(text: Self.message(error), isError: true) }
        }
    }

    #if DEBUG
    /// Simulateur : SIMCTL_CHILD_PARTY_DEBUG_HOST_DEMO=<état JSON> affiche l'écran sans serveur (captures, réglages).
    func showDemo(_ state: AdminState) {
        apply(state)
        demo = true
    }
    private(set) var demo = false
    #endif

    // MARK: Pochettes

    private var artworkCache: [String: UIImage] = [:]

    func artwork(_ path: String) async -> UIImage? {
        if let cached = artworkCache[path] { return cached }
        guard let data = await api.imageData(path), let image = UIImage(data: data) else { return nil }
        artworkCache[path] = image
        return image
    }

    // MARK: Spotify

    func spotifyLogout() async {
        await run("spotify") {
            apply(try await api.adminSpotifyLogout())
            notice = Notice(text: "Compte Spotify déconnecté")
        }
    }

    /// Connexion Spotify (OAuth) : dans la page, qui revient ensuite à l'admin.
    func spotifyLogin() {
        if let url = api.url("/api/admin/spotify/login") { web?.openInPage(url) }
    }
}
