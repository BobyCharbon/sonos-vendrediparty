import Foundation

/// Souvenirs (avis 74d36b93e7bd, 24.11.2026, migration 20261124090000) : l'appareil photo de la soirée. La fiche de
/// l'événement (page web) passe la main à l'app (contrat pont-ios.md) :
/// - `PartyNative.souvenirs.camera(eventId)` : appareil photo natif, 3 poses, jamais d'aperçu, « Annuler » 5 s ;
/// - `PartyNative.souvenirs.story(eventId)` : la story de 24 h, protégée des captures (comme SecretCardsView) ;
/// - `PartyNative.souvenirs.save(url)` : une photo de « Mes souvenirs » dans la Photothèque (ajout seulement).
/// À la fermeture de l'appareil ou de la story, l'app appelle `window.PartySouvenirs?.changed(eventId)` dans la page.
/// La base décide de tout (cercle, fenêtre, 3 photos, CGU, blocage) ; l'app passe par le serveur (app/souvenirs.py).

struct SouvenirAuthor: Decodable, Hashable {
    let id: String
    let name: String?
    /// Lien signé de sa photo de profil (ajouté par le serveur).
    var photo: String?

    var label: String {
        let n = (name ?? "").trimmingCharacters(in: .whitespaces)
        return n.isEmpty ? "Quelqu'un" : n
    }

    var initials: String {
        let letters = label.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
        return letters.isEmpty ? "?" : letters
    }
}

struct SouvenirPhoto: Decodable, Hashable, Identifiable {
    let id: String
    let takenAt: String?
    let mine: Bool?
    let author: SouvenirAuthor?
    /// Lien signé de 10 min (null si la base ne la montre plus).
    var url: String?
    var kept: Bool?
    var canKeep: Bool?
}

struct SouvenirStory: Decodable, Equatable {
    let eventId: String
    let title: String?
    let keep: Bool?
    let until: String?
    var photos: [SouvenirPhoto]
}

/// Bulle des Discussions (souvenir_stories) : « waiting » (au labo, cadenas, compte à rebours) ou « story » (néon).
struct SouvenirBubble: Decodable, Hashable, Identifiable {
    let eventId: String
    let title: String?
    /// Absente d'une base d'avant la migration 20261124120000 : c'est une story.
    var phase: String?
    var revealAt: String?
    let until: String?
    let count: Int
    let seen: Bool?

    var id: String { eventId }
    var waiting: Bool { phase == "waiting" }
}

/// État de la fiche (souvenir_counter) : le NOMBRE seulement, jamais qui ni quoi.
struct SouvenirCounter: Decodable, Equatable {
    let enabled: Bool
    var keep: Bool?
    var phase: String?
    var left: Int?
    var taken: Int?
    var max: Int?
    var canTake: Bool?
    var member: Bool?
    var revealAt: String?
    /// Bandeau de la discussion de l'événement (le nombre seulement, jamais qui ni quoi).
    var count: Int?
    var staff: Bool?
    var storyUntil: String?
    var seen: Bool?
}

/// Photo enregistrée par la base (souvenir_take) : « Annuler » jusqu'à `cancel_until`.
struct SouvenirTaken: Decodable, Equatable {
    let id: String
    let taken: Int?
    let left: Int?
    let cancelUntil: String?
}

/// Refus de la base ou du serveur ({"code", "detail"}) : `full`, `closed`, `profile_required`, `terms_required`…
struct SouvenirRefusal: Error, Equatable {
    let code: String
    let detail: String

    /// Phrase à montrer : la base dit déjà pourquoi ; quelques codes ont une phrase à nous, plus claire à l'écran.
    var message: String { SouvenirText.refusal(code: code, detail: detail) }
}

/// Écran natif demandé : l'appareil photo ou la story d'un événement.
enum SouvenirRoute: Hashable, Identifiable {
    case camera(String)
    case story(String)

    var id: String {
        switch self {
        case .camera(let e): return "camera:\(e)"
        case .story(let e): return "story:\(e)"
        }
    }

    var eventID: String {
        switch self {
        case .camera(let e), .story(let e): return e
        }
    }
}

/// Messages du pont `partySouvenirs` : { action: "camera" | "story", eventId } ou { action: "save", url }.
enum SouvenirBridgeRequest: Equatable {
    case open(SouvenirRoute)
    case save(URL)

    static func parse(_ body: Any) -> SouvenirBridgeRequest? {
        guard let message = body as? [String: Any], let action = message["action"] as? String else { return nil }
        switch action {
        case "camera", "story":
            guard let raw = message["eventId"] as? String, let id = UUID(uuidString: raw)?.uuidString.lowercased() else { return nil }
            return .open(action == "camera" ? .camera(id) : .story(id))
        case "save":
            guard let raw = message["url"] as? String, let url = URL(string: raw), SouvenirLinks.savable(url) else { return nil }
            return .save(url)
        default:
            return nil
        }
    }
}

enum SouvenirLinks {
    /// Toucher de la notification « Les souvenirs sont dévoilés » : « /?tab=events&event=<id>&souvenirs=1 » → la story.
    /// (« souvenirs=review », photo signalée, reste à la page : la fiche s'ouvre en relecture.)
    static func storyRequested(in url: URL) -> String? {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: true)?.queryItems ?? []
        func value(_ name: String) -> String? { items.first { $0.name == name }?.value }
        guard value("tab") == "events", value("souvenirs") == "1",
              let id = value("event").flatMap(UUID.init(uuidString:)) else { return nil }
        return id.uuidString.lowercased()
    }

    /// « souvenirs=1 » devient « souvenirs=native » : la fiche derrière la story native, sans qu'elle la redemande ni
    /// n'ouvre d'office le didacticiel par-dessus (ouverte par un lien).
    static func withoutStory(_ url: URL) -> URL {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: true) else { return url }
        parts.queryItems = parts.queryItems?.map { $0.name == "souvenirs" && $0.value == "1" ? URLQueryItem(name: "souvenirs", value: "native") : $0 }
        return parts.url ?? url
    }

    /// « Enregistrer » : seulement une photo du compartiment souvenirs (lien signé de la base), jamais une autre adresse.
    static func savable(_ url: URL) -> Bool {
        // https seulement (le serveur local de la recette, http, est l'adresse même de l'app) ; base ou serveur de Party.
        let local = url.host?.lowercased() == AppConfig.baseURL.host?.lowercased()
        guard url.scheme == "https" || local, AppConfig.isInternal(url) else { return false }
        return url.path.contains("/storage/v1/object/sign/souvenirs/")
    }

    /// `window.PartySouvenirs?.changed(id)` dans la page et dans le cadre du module Événements.
    static func changedScript(_ eventID: String) -> String? {
        guard let id = UUID(uuidString: eventID)?.uuidString.lowercased() else { return nil }
        return "(function(){var id='\(id)';try{window.PartySouvenirs&&window.PartySouvenirs.changed&&window.PartySouvenirs.changed(id);}catch(e){}"
            + "var f=document.getElementById('eventsFrame');try{var w=f&&f.contentWindow;w&&w.PartySouvenirs&&w.PartySouvenirs.changed&&w.PartySouvenirs.changed(id);}catch(e){}})()"
    }
}

enum SouvenirDates {
    private static let plain: ISO8601DateFormatter = ISO8601DateFormatter()

    /// « 2026-11-24T21:15:03.123456+00:00 » (Postgres) ou sans fraction : les fractions sont ignorées.
    static func parse(_ value: String?) -> Date? {
        guard var text = value?.trimmingCharacters(in: .whitespaces), !text.isEmpty else { return nil }
        text = text.replacingOccurrences(of: " ", with: "T")
        if let dot = text.firstIndex(of: ".") {
            let rest = text[text.index(after: dot)...]
            let zone = rest.firstIndex { !$0.isNumber } ?? rest.endIndex
            text = String(text[..<dot]) + String(rest[zone...])
        }
        if text.hasSuffix("+00") || text.range(of: #"[+-]\d\d$"#, options: .regularExpression) != nil { text += ":00" }
        return plain.date(from: text)
    }
}

enum SouvenirText {
    static let maxPoses = 3

    /// « 31 photos », « 1 photo ».
    static func photos(_ n: Int) -> String { "\(n) photo\(n > 1 ? "s" : "")" }

    /// « 3 poses », « 1 pose », « 0 pose ».
    static func poses(_ n: Int) -> String { "\(max(0, n)) pose\(n > 1 ? "s" : "")" }

    /// « Visible encore 23 h », « Visible encore 40 min », « Visible encore quelques instants ».
    static func visibleFor(until: String?, now: Date = Date()) -> String? {
        guard let end = SouvenirDates.parse(until) else { return nil }
        let left = end.timeIntervalSince(now)
        if left <= 60 { return "Visible encore quelques instants" }
        if left < 3600 { return "Visible encore \(Int(left / 60)) min" }
        return "Visible encore \(Int(left / 3600)) h"
    }

    /// Compte à rebours de la bulle grise : « 13:30:00 », « 2 j » au-delà de 48 h.
    static func countdown(to value: String?, now: Date = Date()) -> String {
        guard let end = SouvenirDates.parse(value) else { return "" }
        let left = max(0, Int(end.timeIntervalSince(now)))
        if left >= 48 * 3600 { return "\(left / 86400) j" }
        return String(format: "%02d:%02d:%02d", left / 3600, left % 3600 / 60, left % 60)
    }

    /// Heure d'une photo : « ven. 20.11 · 20:31 ».
    static func takenAt(_ value: String?) -> String {
        guard let date = SouvenirDates.parse(value) else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich")
        f.dateFormat = "EEE dd.MM · HH:mm"
        return f.string(from: date)
    }

    /// Sous le déclencheur : ce que deviennent les photos (enregistrement autorisé ou non : à dire clairement).
    static func cameraPromise(keep: Bool) -> String {
        keep
            ? "Une seule chance : pas d'aperçu, la photo part au labo. Tes 3 photos seront montrées à tous les participants pendant 24 h. Chacun pourra garder ses préférées dans ses souvenirs."
            : "Une seule chance : pas d'aperçu, la photo part au labo. Tes 3 photos seront montrées à tous les participants pendant 24 h, puis effacées : rien ne sera gardé, ni par toi ni par les autres."
    }

    /// Appareil ouvert sur une fiche où l'on ne peut pas (ou plus) prendre de photo : pourquoi, en clair.
    static func closedCamera(_ c: SouvenirCounter) -> String {
        if (c.taken ?? 0) >= maxPoses { return "Tes 3 photos sont au labo. Profite de la soirée, on s'occupe du reste ✨" }
        if c.member == false { return refusal(code: "forbidden", detail: "") }
        switch c.phase {
        case "soon": return "L'appareil photo s'ouvre au début de l'événement."
        case "waiting": return "L'appareil photo est fermé : les photos sont au labo jusqu'au dévoilement."
        case "story", "after": return "L'appareil photo est fermé : les souvenirs sont dévoilés."
        default: return refusal(code: "closed", detail: "")
        }
    }

    static func refusal(code: String, detail: String) -> String {
        switch code {
        case "full": return "Tu as déjà pris tes 3 photos."
        case "closed":
            return detail.isEmpty ? "L'appareil photo n'est pas ouvert pour toi en ce moment." : capitalized(detail)
        case "profile_required": return "Complète ton profil (prénom, nom, surnom) pour prendre des photos : Réglages › Mon profil."
        case "terms_required": return "Accepte les conditions d'utilisation de Party pour prendre des photos."
        case "forbidden":
            return detail.isEmpty ? "Les photos sont réservées aux participants (Présent ou Peut-être) et à l'organisation." : capitalized(detail)
        default: return detail.isEmpty ? "Ça n'a pas marché. Réessaie dans un instant." : capitalized(detail)
        }
    }

    private static func capitalized(_ text: String) -> String {
        guard let first = text.first else { return text }
        return first.uppercased() + text.dropFirst()
    }
}

/// Motifs de « Signaler » une photo (maquette v2) : « Je suis sur la photo… » en tête (droit à l'image, 24.11).
enum SouvenirReportReason: String, CaseIterable, Identifiable {
    case myImage = "my_image", shocking, harassment, other

    var id: String { rawValue }

    var emoji: String {
        switch self {
        case .myImage: return "🙋"
        case .shocking: return "🔞"
        case .harassment: return "😠"
        case .other: return "💬"
        }
    }

    var label: String {
        switch self {
        case .myImage: return "Je suis sur la photo et je ne veux pas qu'elle soit montrée"
        case .shocking: return "Choquante ou sexuelle"
        case .harassment: return "Moquerie ou harcèlement"
        case .other: return "Autre chose"
        }
    }
}
