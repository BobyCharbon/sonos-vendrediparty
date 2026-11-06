import AVFoundation
import Foundation
import MapKit
import Speech
import UIKit

/// Créer un événement avec l'IA : ce que la personne dit (ou écrit) part au serveur, qui renvoie le brouillon rempli par
/// Claude et ses questions ; l'adresse est cherchée sur le téléphone (Plans d'Apple) et le lien ouvre Google Maps.
enum AIEvent {
    /// Feuille d'accord (AIConsentSheet) : ce que l'assistant envoie à l'IA (Apple 5.1.2(i)).
    static let consentText = FeedbackAI.consentText
    static let consentDeclined = "Sans ton accord, l'assistant ne peut rien envoyer à l'IA. Tu peux créer l'événement à la main."

    /// 403 du serveur « accord requis » (assistant des événements sans accord) : la feuille d'accord s'ouvre.
    static func needsConsent(_ error: Error) -> Bool {
        guard case PartyAPIError.server(let message) = error else { return false }
        return message.lowercased().contains("accord")
    }

    struct Poll: Codable, Equatable {
        var question: String
        var options: [String]
        var multiple: Bool
        var anonymous: Bool
        var add_options: Bool
    }

    /// Tout le formulaire d'événement, rempli et modifié par l'IA (mêmes champs que le formulaire web).
    struct Draft: Codable, Equatable {
        var status: String
        var questions: [String]
        var title: String
        var description: String
        var date_mode: String
        var start: String
        var end: String
        var date_options: [String]
        var poll_deadline: String
        /// « home » : chez un particulier (cherché parmi les adresses) ; « venue » : établissement ; « none » : pas de lieu.
        var place_kind: String
        var place_query: String
        var place_name: String
        var place_broad: String
        var address_complete: Bool
        var price_chf: Double
        var payment_info: String
        var max_participants: Int
        var waitlist: Bool
        var plus_ones: Bool
        var max_plus_ones: Int
        var allow_maybe: Bool
        var rsvp_deadline: String
        var show_participants: Bool
        var forum: Bool
        var notify: Bool
        var category: String
        var tags: [String]
        var audience: String
        var invitees: [String]
        var organizers: [String]
        var polls: [Poll]
        var bring: [String]
        var pot: Bool
        var summary: String
        /// Image de la page lue (flyer) : couverture de l'événement ; vide si aucune.
        var cover_url: String
        var not_understood: [String]

        var ready: Bool { status == "ready" && questions.isEmpty }

        /// Champs absents (serveur plus ancien ou plus récent que l'app) : valeurs vides, jamais une erreur.
        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            func text(_ key: CodingKeys) -> String { (try? c.decodeIfPresent(String.self, forKey: key)) ?? nil ?? "" }
            func list(_ key: CodingKeys) -> [String] { (try? c.decodeIfPresent([String].self, forKey: key)) ?? nil ?? [] }
            func flag(_ key: CodingKeys, _ fallback: Bool) -> Bool { (try? c.decodeIfPresent(Bool.self, forKey: key)) ?? nil ?? fallback }
            func number(_ key: CodingKeys) -> Int { (try? c.decodeIfPresent(Int.self, forKey: key)) ?? nil ?? 0 }
            status = text(.status)
            questions = list(.questions)
            title = text(.title)
            description = text(.description)
            date_mode = text(.date_mode).isEmpty ? "fixed" : text(.date_mode)
            start = text(.start)
            end = text(.end)
            date_options = list(.date_options)
            poll_deadline = text(.poll_deadline)
            place_query = text(.place_query)
            place_kind = text(.place_kind).isEmpty ? (place_query.isEmpty ? "none" : "venue") : text(.place_kind)
            place_name = text(.place_name)
            place_broad = text(.place_broad)
            address_complete = flag(.address_complete, true)
            price_chf = (try? c.decodeIfPresent(Double.self, forKey: .price_chf)) ?? nil ?? 0
            payment_info = text(.payment_info)
            max_participants = number(.max_participants)
            waitlist = flag(.waitlist, true)
            plus_ones = flag(.plus_ones, true)
            max_plus_ones = number(.max_plus_ones)
            allow_maybe = flag(.allow_maybe, true)
            rsvp_deadline = text(.rsvp_deadline)
            show_participants = flag(.show_participants, true)
            forum = flag(.forum, true)
            notify = flag(.notify, true)
            category = text(.category)
            tags = list(.tags)
            audience = text(.audience)
            invitees = list(.invitees)
            organizers = list(.organizers)
            polls = (try? c.decodeIfPresent([Poll].self, forKey: .polls)) ?? nil ?? []
            bring = list(.bring)
            pot = flag(.pot, false)
            summary = text(.summary)
            cover_url = text(.cover_url)
            not_understood = list(.not_understood)
        }
    }

    struct Place: Codable, Equatable {
        let name: String
        let address: String
        let url: String
        var latitude: Double
        var longitude: Double
        /// Google n'a trouvé que la rue ou la commune, pas le numéro : à ne pas prendre pour l'adresse exacte.
        var approximate = false
    }

    /// Personne citée à l'IA : proposée, cochée, à l'étape « Qui est invité » (jamais invitée par l'IA).
    struct Suggested: Decodable, Equatable {
        let id: String
        let name: String
    }

    /// Pré-réglage de « qui voit » (app/ai_events.py : preset) : public, vip, group (avec ses groupes) ou invite.
    struct Preset: Decodable, Equatable {
        let audience: String
        var group_ids: [String] = []

        static let kinds = ["public", "vip", "group", "invite"]
    }

    struct Created: Decodable, Equatable {
        let id: String
        /// « draft » : étape 1 confirmée, brouillon enregistré (étape 2 : les invités) ; « published » / « pending » :
        /// ancien parcours ; « updated » : événement modifié.
        let status: String
        let title: String
        /// Ce qui n'a pas pu être ajouté (un sondage, les tags…) : l'événement existe, à compléter à la main.
        var problems: [String] = []
        /// Événement modifié : ce qui a changé.
        var changes: [String] = []
        var suggested: [Suggested] = []
        /// Ce que la personne a dit spontanément de qui voit l'événement : pré-réglage de l'étape 2 (public par défaut).
        var preset: Preset?

        var isDraft: Bool { status == "draft" }

        init(id: String, status: String, title: String, suggested: [Suggested] = []) {
            self.id = id
            self.status = status
            self.title = title
            self.suggested = suggested
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            status = (try? c.decodeIfPresent(String.self, forKey: .status)) ?? nil ?? "updated"  // modification : pas de statut
            title = try c.decode(String.self, forKey: .title)
            problems = (try? c.decodeIfPresent([String].self, forKey: .problems)) ?? nil ?? []
            changes = (try? c.decodeIfPresent([String].self, forKey: .changes)) ?? nil ?? []
            suggested = (try? c.decodeIfPresent([Suggested].self, forKey: .suggested)) ?? nil ?? []
            preset = (try? c.decodeIfPresent(Preset.self, forKey: .preset)) ?? nil
        }

        private enum CodingKeys: String, CodingKey { case id, status, title, problems, changes, suggested, preset }
    }

    /// Les trois étapes de « Créer avec l'IA » (demande de l'admin, 06.11), mêmes mots que la page web (AIEventSteps.tsx).
    static let steps = ["La soirée", "Qui est invité", "C'est en ligne"]

    /// Étape en cours : 1 tant que la soirée n'est pas confirmée, 2 une fois le brouillon enregistré, 3 publié.
    static func step(_ created: Created?) -> Int {
        guard let created else { return 1 }
        return created.isDraft ? 2 : 3
    }

    static let idPattern = "^[0-9a-fA-F-]{36}$"

    /// Étape 2, page web : « /events/event/<id>/invite?audience=…&groups=…&suggested=… » (pré-réglage de qui voit,
    /// personnes citées à l'IA cochées d'avance). Seulement des identifiants et des mots connus.
    static func invitePath(_ id: String, suggested: [String], preset: Preset? = nil) -> String? {
        guard isId(id) else { return nil }
        var query: [String] = []
        if let preset, Preset.kinds.contains(preset.audience), preset.audience != "public" {
            query.append("audience=" + preset.audience)
            let groups = preset.group_ids.filter(isId)
            if !groups.isEmpty { query.append("groups=" + groups.joined(separator: ",")) }
        }
        let ids = suggested.filter(isId)
        if !ids.isEmpty { query.append("suggested=" + ids.joined(separator: ",")) }
        return "/events/event/\(id)/invite" + (query.isEmpty ? "" : "?" + query.joined(separator: "&"))
    }

    static func isId(_ value: String) -> Bool { value.range(of: idPattern, options: .regularExpression) != nil }

    /// Publics connus du serveur (app/ai_events.py : PUBLIC_AUDIENCE, VIP_AUDIENCE, ONLY_INVITEES).
    static let publicAudience = "Public (lien)"
    static let vipAudience = "Vendredi Party"
    static let onlyInvitees = "Seulement les personnes invitées"

    /// Début et fin : « samedi 14 novembre à 20:00, jusqu'à 23:30 » (la date n'est répétée que si elle change).
    static func span(_ start: String, _ end: String) -> String {
        guard !end.isEmpty else { return when(start) }
        let sameDay = start.prefix(10) == end.prefix(10)
        return when(start) + "\njusqu'à " + (sameDay ? String(end.suffix(5)) : when(end))
    }

    /// « 2026-11-07T20:00 » (heure de Suisse) → « samedi 7 novembre à 20:00 ».
    static func when(_ value: String) -> String {
        let parse = DateFormatter()
        parse.locale = Locale(identifier: "en_US_POSIX")
        parse.timeZone = TimeZone(identifier: "Europe/Zurich")
        parse.dateFormat = "yyyy-MM-dd'T'HH:mm"
        guard let date = parse.date(from: value) else { return value }
        let show = DateFormatter()
        show.locale = Locale(identifier: "fr_CH")
        show.timeZone = parse.timeZone
        show.dateFormat = "EEEE d MMMM 'à' HH:mm"
        return show.string(from: date)
    }

    static let maxShots = 3

    /// Capture d'écran jointe à la demande : réduite pour l'envoi (1600 px, JPEG), avec sa miniature.
    struct Shot: Identifiable, Equatable {
        let id = UUID()
        let thumbnail: UIImage
        let dataURL: String

        static let side: CGFloat = 1600
        /// Taille acceptée par le serveur (MAX_IMAGE_B64, app/ai_events.py) ; au-delà, l'image est recompressée.
        static let maxBase64 = 3_000_000
        static let qualities: [CGFloat] = [0.7, 0.5, 0.35]

        init?(_ image: UIImage) {
            guard image.size.width > 0, image.size.height > 0 else { return nil }
            let scale = min(1, Self.side / max(image.size.width, image.size.height))
            let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
            let format = UIGraphicsImageRendererFormat.default()
            format.scale = 1  // 1600 px réels, pas 1600 points × 3 (4800 px refusés par le serveur)
            format.opaque = true  // JPEG : une image collée avec transparence (PNG) a un fond blanc, pas noir
            let small = UIGraphicsImageRenderer(size: size, format: format).image { context in
                UIColor.white.setFill()
                context.fill(CGRect(origin: .zero, size: size))
                image.draw(in: CGRect(origin: .zero, size: size))
            }
            let encoded = Self.qualities.lazy
                .compactMap { small.jpegData(compressionQuality: $0)?.base64EncodedString() }
                .first { $0.count <= Self.maxBase64 }
            guard let encoded else { return nil }
            thumbnail = small
            dataURL = "data:image/jpeg;base64," + encoded
        }

        static func == (a: Shot, b: Shot) -> Bool { a.id == b.id }
    }

    /// L'IA réfléchit souvent 20 à 40 secondes : on l'attend jusqu'à 2 minutes et demie.
    static let thinkingTimeout: TimeInterval = 150

    /// Lien Google Maps pour un lieu trouvé : s'ouvre dans l'app Google Maps si elle est installée.
    static func googleMapsURL(_ query: String) -> String {
        var c = URLComponents(string: "https://www.google.com/maps/search/")!
        c.queryItems = [URLQueryItem(name: "api", value: "1"), URLQueryItem(name: "query", value: query)]
        return c.url?.absoluteString ?? "https://www.google.com/maps"
    }
}

@MainActor
final class AIEventStore: ObservableObject {
    @Published private(set) var turns: [String] = []
    @Published private(set) var draft: AIEvent.Draft?
    @Published private(set) var place: AIEvent.Place?
    @Published private(set) var searchingPlace = false
    /// Lieux trouvés pour ce qui a été dit ; la personne choisit le bon (rien n'est choisi pour elle).
    @Published private(set) var candidates: [AIEvent.Place] = []
    @Published private(set) var placeSource = ""
    @Published private(set) var thinking = false
    @Published private(set) var creating = false
    @Published private(set) var created: AIEvent.Created?
    /// Brouillon tout juste enregistré : l'étape 2 (les invités) s'ouvre d'elle-même dans un instant.
    @Published private(set) var openInviteSoon = false
    /// Modifier un événement publié (« ✨ Modifier avec l'IA ») : son id ; nil = créer un événement.
    @Published private(set) var editingId: String?
    /// Ce que la demande change, en mots simples (montré avant d'enregistrer).
    @Published private(set) var changes: [String] = []
    /// Un message dans la discussion de l'événement résume les changements aux invités.
    @Published var announce = true
    @Published var error: String?
    /// Captures d'écran jointes (affiche, page d'un site) : réduites, envoyées avec chaque demande, 3 au plus.
    @Published private(set) var images: [AIEvent.Shot] = []
    /// Petit mot sous les images jointes (limite de 3 atteinte, image illisible) ; effacé à l'action suivante.
    @Published var notice: String?
    /// Ce que la personne a dit quand l'envoi a échoué : remis dans le champ, rien n'est perdu.
    @Published var unsent: String?
    /// Feuille d'accord (AIConsentSheet.Copy.event) : avant la 1re demande, ou après un 403 « accord requis ».
    @Published var askingConsent = false
    private var consentAnswer: CheckedContinuation<Bool, Never>?
    /// Accord déjà vu accepté pendant cette ouverture de l'app (pas de nouvelle question au serveur).
    private(set) var consentAccepted = false
    /// CGU exigées par la base (terms_enforced) et pas encore acceptées : la feuille « Avant de publier » s'ouvre, puis
    /// l'enregistrement repart tout seul une fois acceptées.
    @Published var askingTerms = false
    private var termsAnswer: CheckedContinuation<Bool, Never>?
    /// Conditions d'utilisation (même store que Réglages › Confidentialité) ; posé par SettingsStore.
    var moderation: ModerationStore?

    private let api: PartyAPI
    private weak var web: WebStorage?
    /// Dernière recherche faite (lieu et type) : on ne recherche que si l'IA a changé l'un des deux.
    private var lastSearch = ""
    /// Lieu actuel de l'événement modifié : renvoyé seulement si la personne en choisit un autre.
    private var loadedPlace: AIEvent.Place?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    /// Change à chaque « Recommencer » : la réponse d'une demande d'avant est ignorée (jamais une ancienne fiche qui
    /// réapparaît, jamais un tour retiré d'une conversation déjà vidée).
    private var generation = 0

    func reset() {
        generation += 1
        thinking = false
        turns = []
        draft = nil
        place = nil
        candidates = []
        lastSearch = ""
        created = nil
        openInviteSoon = false
        error = nil
        editingId = nil
        images = []
        notice = nil
        changes = []
        loadedPlace = nil
        announce = true
    }

    /// « ✨ Modifier avec l'IA » : l'événement publié revient en fiche, prêt à être changé en parlant.
    func startEditing(_ id: String) async {
        reset()
        editingId = id
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi dans Réglages pour utiliser l'assistant"
            return
        }
        thinking = true
        defer { thinking = false }
        do {
            let loaded = try await api.aiEventEditLoad(token: token, id: id)
            draft = loaded.draft
            lastSearch = loaded.draft.place_kind + "|" + loaded.draft.place_query
            if !loaded.place.name.isEmpty || !loaded.place.address.isEmpty {
                let current = AIEvent.Place(name: loaded.place.name, address: loaded.place.address, url: loaded.place.url,
                                            latitude: 0, longitude: 0)
                place = current
                loadedPlace = current
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Description, réponse à une question ou correction : l'IA reprend le tout et renvoie le brouillon à jour.
    /// Ajoute une capture d'écran (réduite à 1600 px, JPEG) ; 3 au plus.
    func attach(_ image: UIImage) {
        attach([image])
    }

    /// Images choisies, collées ou glissées (plusieurs d'un coup) : réduites comme les photos, 3 au plus ; ce qui
    /// dépasse ou ne se lit pas est dit en clair. Renvoie le nombre d'images ajoutées.
    @discardableResult
    func attach(_ incoming: [UIImage]) -> Int {
        guard !incoming.isEmpty else { return 0 }
        guard editingId == nil else { notice = AIEvent.editingNotice; return 0 }
        let room = AIEvent.maxShots - images.count
        guard room > 0 else { notice = AIEvent.fullNotice; return 0 }
        let kept = Array(incoming.prefix(room))
        let shots = kept.compactMap(AIEvent.Shot.init)
        images += shots
        notice = incoming.count > room ? AIEvent.overflowNotice(dropped: incoming.count - room)
            : shots.count < kept.count ? AIEvent.unreadableNotice : nil
        return shots.count
    }

    /// « Partager › Party › Créer l'événement » : l'app vient peut-être de s'ouvrir, la page (et la session) se charge
    /// encore ; on attend la session (15 s au plus) au lieu d'afficher « Connecte-toi », et le lien n'est jamais perdu.
    func start(link: String) async {
        reset()
        for _ in 0..<30 {
            if await web?.accountToken() != nil { break }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        guard await web?.accountToken() != nil else {
            SharedSession.savePendingEvent(link)
            error = "Connecte-toi dans Réglages, puis rouvre Party : l'événement sera créé à partir du lien."
            return
        }
        await send(link)
    }

    func detach(_ shot: AIEvent.Shot) {
        images.removeAll { $0.id == shot.id }
        notice = nil
    }

    func send(_ text: String) async {
        var said = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if said.isEmpty && !images.isEmpty && turns.isEmpty && editingId == nil { said = "Crée l'événement à partir de ma capture d'écran." }
        guard !said.isEmpty, !thinking else { return }
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi dans Réglages pour utiliser l'assistant"
            return
        }
        guard await ensureConsent(token: token) else {
            unsent = said
            error = AIEvent.consentDeclined
            return
        }
        turns.append(said)
        thinking = true
        error = nil
        notice = nil
        let round = generation
        defer { if round == generation { thinking = false } }
        do {
            let next: AIEvent.Draft
            if let editingId {
                let edited = try await api.aiEventEditDraft(token: token, id: editingId, turns: turns)
                next = edited.draft
                changes = edited.changes
            } else {
                next = try await api.aiEventDraft(token: token, turns: turns, previous: draft, images: images.map(\.dataURL))
            }
            guard round == generation else { return }  // « Recommencer » touché pendant la réflexion
            draft = next
            if next.place_kind + "|" + next.place_query != lastSearch {
                await findPlace(next.place_query, broad: next.place_broad, kind: next.place_kind)
            }
        } catch {
            guard round == generation else { return }
            if !turns.isEmpty { turns.removeLast() }
            unsent = said
            if AIEvent.needsConsent(error) {
                // Accord absent ou retiré côté serveur : on le redemande ; le texte reste prêt à renvoyer.
                consentAccepted = false
                self.error = await askConsent(token: token) ? "Merci ! Renvoie ta demande (ton texte est gardé en bas)."
                                                            : AIEvent.consentDeclined
                return
            }
            self.error = error is DecodingError ? "Réponse inattendue du serveur : réessaie dans un instant (ton texte est gardé en bas)."
                                                : error.localizedDescription + " Ton texte est gardé en bas."
        }
    }

    /// Avant la 1re demande : accord déjà donné (serveur, par compte), sinon la feuille d'accord.
    func ensureConsent(token: String) async -> Bool {
        if consentAccepted { return true }
        if await api.aiConsentAccepted(web: web, token: token) {
            consentAccepted = true
            return true
        }
        return await askConsent(token: token)
    }

    private func askConsent(token: String) async -> Bool {
        consentAnswer?.resume(returning: false)
        askingConsent = true
        let accepted = await withCheckedContinuation { consentAnswer = $0 }
        guard accepted else { return false }
        do {
            consentAccepted = try await api.acceptAIConsent(web: web, token: token)
        } catch {
            self.error = error.localizedDescription
            return false
        }
        return consentAccepted
    }

    /// « J'accepte » / « Pas maintenant » de la feuille.
    func answerConsent(_ accept: Bool) {
        let answer = consentAnswer
        consentAnswer = nil
        askingConsent = false
        answer?.resume(returning: accept)
    }

    /// Feuille fermée d'un geste : pas d'accord, rien d'enregistré.
    func consentDismissed() {
        answerConsent(false)
    }

    /// Lieu dit par la personne → lieux possibles (Google Maps, sinon Plans d'Apple) ; la personne choisit le bon.
    /// Chez un particulier (« home »), seules des adresses sont proposées, jamais les commerces voisins.
    func findPlace(_ query: String, broad: String = "", kind: String = "venue") async {
        lastSearch = kind + "|" + query
        place = nil
        candidates = []
        guard !query.isEmpty else { return }
        searchingPlace = true
        defer { searchingPlace = false }
        if let token = await web?.accountToken(),
           let google = try? await api.aiPlaces(token: token, query: query, broad: broad, kind: kind),
           !google.places.isEmpty {
            placeSource = "Google Maps"
            candidates = google.places.map { p in
                AIEvent.Place(name: p.name, address: p.address,
                              url: p.url.isEmpty ? AIEvent.googleMapsURL([p.name, p.address].joined(separator: ", ")) : p.url,
                              latitude: p.latitude, longitude: p.longitude, approximate: p.exact == false)
            }
            return
        }
        placeSource = "Plans"
        candidates = await appleMaps(query, addressesOnly: kind == "home")
    }

    /// Plans d'Apple (sans clé Google) : en Suisse d'abord, ailleurs seulement si rien n'y est trouvé.
    private func appleMaps(_ query: String, addressesOnly: Bool) async -> [AIEvent.Place] {
        let foreign = ["france", "italie", "allemagne", "espagne", "portugal", "autriche"].contains { query.lowercased().contains($0) }
        var found: [MKMapItem] = []
        for q in foreign ? [query] : [query + ", Suisse", query] where found.isEmpty {
            let request = MKLocalSearch.Request()
            request.naturalLanguageQuery = q
            request.region = Self.switzerland
            if addressesOnly { request.resultTypes = .address }
            let items = (try? await MKLocalSearch(request: request).start().mapItems) ?? []
            found = foreign ? items : items.filter { Self.inSwitzerland($0.placemark.coordinate) }
            if found.isEmpty && q == query { found = items }
        }
        return found.prefix(5).map { item in
            let p = item.placemark
            let street = [p.thoroughfare, p.subThoroughfare].compactMap { $0 }.joined(separator: " ")
            let town = [p.postalCode, p.locality].compactMap { $0 }.joined(separator: " ")
            let address = [street, town].filter { !$0.isEmpty }.joined(separator: ", ")
            let name = item.name ?? address
            return AIEvent.Place(name: name, address: address == name ? "" : address,
                                 url: AIEvent.googleMapsURL([name, address].filter { !$0.isEmpty }.joined(separator: ", ")),
                                 latitude: p.coordinate.latitude, longitude: p.coordinate.longitude)
        }
    }

    /// La personne confirme le bon lieu (ou change d'avis).
    func choose(_ chosen: AIEvent.Place?) {
        place = chosen
    }

    /// Aucune proposition ne convient : l'adresse telle que la personne l'a dite (corrigée par l'IA) devient le lieu,
    /// avec un lien Google Maps qui la cherche. La carte se centre sur la rue ou la localité trouvée, sinon pas de carte.
    var asSaid: AIEvent.Place? {
        guard let draft, !draft.place_query.isEmpty, draft.address_complete else { return nil }
        let near = candidates.first
        return AIEvent.Place(name: draft.place_name.isEmpty ? draft.place_query : draft.place_name,
                             address: draft.place_query, url: AIEvent.googleMapsURL(draft.place_query),
                             latitude: near?.latitude ?? 0, longitude: near?.longitude ?? 0)
    }

    /// « Créer » n'est possible que si le brouillon est complet et que le lieu a été confirmé sur la carte : les invités
    /// ont toujours une adresse où se rendre.
    var canCreate: Bool {
        guard let draft, draft.ready else { return false }
        if editingId != nil { return !changes.isEmpty && (place != nil || draft.place_query.isEmpty) }
        return place != nil
    }

    #if DEBUG || E2E_HOOKS
    /// Captures sur simulateur : brouillon déjà enregistré (étape 2), sans appeler le serveur.
    func showDemoCreated(_ demo: AIEvent.Created) {
        created = demo
    }

    /// Tests : une fiche prête, lieu déjà choisi sur la carte (rien n'est cherché).
    func showDemoReady(_ demo: AIEvent.Draft, place: AIEvent.Place) {
        draft = demo
        self.place = place
    }

    /// Captures sur simulateur : une fiche figée, sans appeler le serveur (l'adresse est cherchée pour de vrai).
    func showDemo(_ demo: AIEvent.Draft, said: String) async {
        turns = said.isEmpty ? [] : [said]
        draft = demo
        await findPlace(demo.place_query, broad: demo.place_broad, kind: demo.place_kind)
    }
    #endif

    static let switzerland = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 46.8, longitude: 8.2),
                                                span: MKCoordinateSpan(latitudeDelta: 2.2, longitudeDelta: 4.8))

    static func inSwitzerland(_ c: CLLocationCoordinate2D) -> Bool {
        (45.8...47.85).contains(c.latitude) && (5.95...10.5).contains(c.longitude)
    }

    /// L'étape 2 s'ouvre (ou la personne a choisi « Ouvrir l'événement ») : plus d'ouverture automatique.
    func inviteOpened() {
        openInviteSoon = false
    }

    func create() async {
        guard let draft, canCreate, !creating else { return }
        guard let token = await web?.accountToken() else { return }
        creating = true
        defer { creating = false }
        do {
            try await save(draft, token: token)
        } catch PartyAPIError.termsRequired(let message) {
            // CGU exigées en prod : la feuille, puis le même enregistrement, sans rien retaper.
            guard await askTerms() else { return self.error = message }
            do { try await save(draft, token: token) } catch { self.error = error.localizedDescription }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func save(_ draft: AIEvent.Draft, token: String) async throws {
        if let editingId {
            created = try await api.aiEventEditSave(token: token, id: editingId, draft: draft,
                                                    place: place == loadedPlace ? nil : place, announce: announce)
        } else {
            // Étape 1 confirmée : brouillon, sans invité ; l'étape 2 (les invités) s'ouvre ensuite.
            created = try await api.aiEventSaveDraft(token: token, draft: draft, place: place)
            openInviteSoon = created?.isDraft == true
        }
    }

    /// Feuille des CGU (TermsAcceptSheet) : true une fois acceptées, false si la personne renonce.
    func askTerms() async -> Bool {
        guard moderation != nil else { return false }
        termsAnswer?.resume(returning: false)
        askingTerms = true
        return await withCheckedContinuation { termsAnswer = $0 }
    }

    /// « J'accepte » (après l'enregistrement de l'acceptation) ou « Plus tard » / feuille fermée d'un geste.
    func answerTerms(_ accepted: Bool) {
        let answer = termsAnswer
        termsAnswer = nil
        askingTerms = false
        answer?.resume(returning: accepted)
    }
}

extension PartyAPI {
    struct FoundPlaces: Decodable {
        struct Found: Decodable {
            let name: String; let address: String; let latitude: Double; let longitude: Double; let url: String
            let exact: Bool?  // absent d'un ancien serveur
        }
        let source: String
        let places: [Found]
    }

    func aiPlaces(token: String, query: String, broad: String, kind: String) async throws -> FoundPlaces {
        try await postDecoding("/api/account/ai/places", body: ["token": token, "query": query, "broad": broad,
                                                                "kind": kind == "home" ? "home" : "venue"])
    }

    func aiEventDraft(token: String, turns: [String], previous: AIEvent.Draft?, images: [String] = []) async throws -> AIEvent.Draft {
        var body: [String: Any] = ["token": token, "turns": turns]
        if !images.isEmpty { body["images"] = images }
        if let previous, let data = try? JSONEncoder().encode(previous),
           let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        return try await postDecoding("/api/account/ai/event/draft", body: body, timeout: AIEvent.thinkingTimeout)
    }

    struct LoadedEvent: Decodable {
        struct Where: Decodable { let name: String; let address: String; let url: String }
        let draft: AIEvent.Draft
        let place: Where
    }

    struct EditedEvent: Decodable {
        let draft: AIEvent.Draft
        let changes: [String]
    }

    func aiEventEditLoad(token: String, id: String) async throws -> LoadedEvent {
        try await postDecoding("/api/account/ai/event/edit/load", body: ["token": token, "event_id": id])
    }

    func aiEventEditDraft(token: String, id: String, turns: [String]) async throws -> EditedEvent {
        try await postDecoding("/api/account/ai/event/edit/draft", body: ["token": token, "event_id": id, "turns": turns],
                               timeout: AIEvent.thinkingTimeout)
    }

    /// place nil : le lieu ne change pas.
    func aiEventEditSave(token: String, id: String, draft: AIEvent.Draft, place: AIEvent.Place?, announce: Bool) async throws -> AIEvent.Created {
        var body: [String: Any] = ["token": token, "event_id": id, "announce": announce]
        if let data = try? JSONEncoder().encode(draft), let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        if let place { body["place"] = ["name": place.name, "address": place.address, "url": place.url] }
        return try await postDecoding("/api/account/ai/event/edit/save", body: body, timeout: 60)
    }

    /// « Oui, continuer » : l'événement en brouillon, sans aucun invité (étape 2 : la personne invite elle-même).
    func aiEventSaveDraft(token: String, draft: AIEvent.Draft, place: AIEvent.Place?) async throws -> AIEvent.Created {
        var body: [String: Any] = ["token": token]
        if let data = try? JSONEncoder().encode(draft), let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        if let place { body["place"] = ["name": place.name, "address": place.address, "url": place.url] }
        return try await postDecoding("/api/account/ai/event/draft/save", body: body, timeout: 60)
    }

    func aiEventCreate(token: String, draft: AIEvent.Draft, place: AIEvent.Place?) async throws -> AIEvent.Created {
        var body: [String: Any] = ["token": token]
        if let data = try? JSONEncoder().encode(draft), let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        if let place { body["place"] = ["name": place.name, "address": place.address, "url": place.url] }
        return try await postDecoding("/api/account/ai/event/create", body: body, timeout: 60)
    }
}

/// Dictée en français (reconnaissance vocale d'iOS) : le texte s'affiche pendant qu'on parle ; on touche à nouveau
/// le micro pour envoyer.
@MainActor
final class Dictation: ObservableObject {
    @Published private(set) var text = ""
    @Published private(set) var listening = false
    @Published var problem: String?

    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "fr-CH")) ?? SFSpeechRecognizer(locale: Locale(identifier: "fr-FR"))

    func start() async {
        problem = nil
        text = ""
        let speech = await withCheckedContinuation { go in SFSpeechRecognizer.requestAuthorization { go.resume(returning: $0) } }
        let mic = await withCheckedContinuation { go in AVAudioSession.sharedInstance().requestRecordPermission { go.resume(returning: $0) } }
        guard speech == .authorized, mic else {
            problem = "Autorise le micro et la reconnaissance vocale dans Réglages › Party, ou écris ta description."
            return
        }
        guard let recognizer, recognizer.isAvailable else {
            problem = "La dictée n'est pas disponible pour l'instant : écris ta description."
            return
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let request = SFSpeechAudioBufferRecognitionRequest()
            request.shouldReportPartialResults = true
            request.addsPunctuation = true
            self.request = request
            let input = engine.inputNode
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
                request.append(buffer)
            }
            engine.prepare()
            try engine.start()
            listening = true
            task = recognizer.recognitionTask(with: request) { [weak self] result, error in
                let heard = result?.bestTranscription.formattedString
                let over = error != nil || result?.isFinal == true
                Task { @MainActor in
                    guard let self else { return }
                    if let heard { self.text = heard }
                    if over { self.finish() }
                }
            }
        } catch {
            problem = "Le micro n'a pas pu démarrer : écris ta description."
            finish()
        }
    }

    /// « J'ai fini de parler » : laisse la reconnaissance terminer les derniers mots (jusqu'à 1,5 s), puis renvoie
    /// tout le texte. Envoyer tout de suite coupait la fin de la phrase.
    func stopAndCollect() async -> String {
        guard listening else { return text }
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        for _ in 0..<15 where listening {
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        finish()
        return text
    }

    /// Arrête l'écoute ; le texte reconnu reste dans `text`.
    func finish() {
        guard listening || engine.isRunning || task != nil else { return }
        if engine.isRunning {
            engine.stop()
            engine.inputNode.removeTap(onBus: 0)
        }
        request?.endAudio()
        task?.finish()
        request = nil
        task = nil
        listening = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
