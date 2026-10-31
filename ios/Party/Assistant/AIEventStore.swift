import AVFoundation
import Foundation
import MapKit
import Speech

/// Créer un événement avec l'IA : ce que la personne dit (ou écrit) part au serveur, qui renvoie le brouillon rempli par
/// Claude et ses questions ; l'adresse est cherchée sur le téléphone (Plans d'Apple) et le lien ouvre Google Maps.
enum AIEvent {
    struct Draft: Codable, Equatable {
        var status: String
        var questions: [String]
        var title: String
        var description: String
        var start: String
        var end: String
        var place_query: String
        var place_name: String
        var price_chf: Double
        var max_participants: Int
        var category: String
        var audience: String
        var pot: Bool
        var bring: [String]
        var summary: String

        var ready: Bool { status == "ready" && questions.isEmpty }
    }

    struct Place: Codable, Equatable {
        let name: String
        let address: String
        let url: String
        var latitude: Double
        var longitude: Double
    }

    struct Created: Decodable, Equatable { let id: String; let status: String; let title: String }

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
    @Published private(set) var thinking = false
    @Published private(set) var creating = false
    @Published private(set) var created: AIEvent.Created?
    @Published var error: String?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var lastQuery = ""

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    func reset() {
        turns = []
        draft = nil
        place = nil
        lastQuery = ""
        created = nil
        error = nil
    }

    /// Description, réponse à une question ou correction : l'IA reprend le tout et renvoie le brouillon à jour.
    func send(_ text: String) async {
        let said = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !said.isEmpty, !thinking else { return }
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi dans Réglages pour utiliser l'assistant"
            return
        }
        turns.append(said)
        thinking = true
        error = nil
        defer { thinking = false }
        do {
            let next = try await api.aiEventDraft(token: token, turns: turns, previous: draft)
            draft = next
            if next.place_query != lastQuery { await findPlace(next.place_query) }
        } catch {
            turns.removeLast()
            self.error = error.localizedDescription
        }
    }

    /// Lieu dit par la personne → adresse trouvée sur la carte (Plans d'Apple, en Suisse d'abord).
    func findPlace(_ query: String) async {
        lastQuery = query
        guard !query.isEmpty else {
            place = nil
            return
        }
        searchingPlace = true
        defer { searchingPlace = false }
        // En Suisse d'abord (« Villeneuve » = Villeneuve VD, pas la France) ; ailleurs seulement si rien n'y est trouvé.
        let foreign = ["france", "italie", "allemagne", "espagne", "portugal", "autriche"].contains { query.lowercased().contains($0) }
        var found: [MKMapItem] = []
        for q in foreign ? [query] : [query + ", Suisse", query] where found.isEmpty {
            let request = MKLocalSearch.Request()
            request.naturalLanguageQuery = q
            request.region = Self.switzerland
            let items = (try? await MKLocalSearch(request: request).start().mapItems) ?? []
            found = foreign ? items : items.filter { Self.inSwitzerland($0.placemark.coordinate) }
            if found.isEmpty && q == query { found = items }
        }
        guard let item = found.first else {
            place = nil
            return
        }
        let p = item.placemark
        let street = [p.thoroughfare, p.subThoroughfare].compactMap { $0 }.joined(separator: " ")
        let town = [p.postalCode, p.locality].compactMap { $0 }.joined(separator: " ")
        let address = [street, town].filter { !$0.isEmpty }.joined(separator: ", ")
        // Seule la ville est trouvée : le nom dit par la personne (« Fun Planet ») reste le nom du lieu.
        let said = draft?.place_name ?? ""
        let name = p.thoroughfare == nil && !said.isEmpty ? said : (item.name ?? (said.isEmpty ? query : said))
        place = AIEvent.Place(name: name, address: address.isEmpty ? (p.title ?? "") : address,
                              url: AIEvent.googleMapsURL([name, address].filter { !$0.isEmpty }.joined(separator: ", ")),
                              latitude: p.coordinate.latitude, longitude: p.coordinate.longitude)
    }

    #if DEBUG
    /// Captures sur simulateur : une fiche figée, sans appeler le serveur (l'adresse est cherchée pour de vrai).
    func showDemo(_ demo: AIEvent.Draft, said: String) async {
        turns = said.isEmpty ? [] : [said]
        draft = demo
        await findPlace(demo.place_query)
    }
    #endif

    static let switzerland = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 46.8, longitude: 8.2),
                                                span: MKCoordinateSpan(latitudeDelta: 2.2, longitudeDelta: 4.8))

    static func inSwitzerland(_ c: CLLocationCoordinate2D) -> Bool {
        (45.8...47.85).contains(c.latitude) && (5.95...10.5).contains(c.longitude)
    }

    /// « Pas ce lieu » : seul le nom dit est gardé, sans adresse.
    func dropPlace() { place = nil }

    func create() async {
        guard let draft, draft.ready, !creating else { return }
        guard let token = await web?.accountToken() else { return }
        creating = true
        defer { creating = false }
        do {
            created = try await api.aiEventCreate(token: token, draft: draft, place: place)
        } catch {
            self.error = error.localizedDescription
        }
    }
}

extension PartyAPI {
    func aiEventDraft(token: String, turns: [String], previous: AIEvent.Draft?) async throws -> AIEvent.Draft {
        var body: [String: Any] = ["token": token, "turns": turns]
        if let previous, let data = try? JSONEncoder().encode(previous),
           let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        return try await postDecoding("/api/account/ai/event/draft", body: body)
    }

    func aiEventCreate(token: String, draft: AIEvent.Draft, place: AIEvent.Place?) async throws -> AIEvent.Created {
        var body: [String: Any] = ["token": token]
        if let data = try? JSONEncoder().encode(draft), let json = try? JSONSerialization.jsonObject(with: data) { body["draft"] = json }
        if let place { body["place"] = ["name": place.name, "address": place.address, "url": place.url] }
        return try await postDecoding("/api/account/ai/event/create", body: body)
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

    /// Arrête l'écoute ; le texte reconnu reste dans `text`.
    func finish() {
        guard listening || engine.isRunning else { return }
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.finish()
        request = nil
        task = nil
        listening = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
