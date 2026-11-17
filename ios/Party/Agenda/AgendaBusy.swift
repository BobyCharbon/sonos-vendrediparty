import EventKit
import Foundation

/// Agenda de Party (17.11) : plages « pris » calculées SUR l'iPhone à partir des calendriers cochés « compte dans mes
/// dispos ». Seuls début et fin, arrondis vers l'extérieur à 30 min, coupés à [maintenant, +60 jours] et fusionnés,
/// partent au serveur (agenda_set_busy) : jamais un titre, un lieu, une note ni le nom d'un calendrier.
enum AgendaBusy {
    static let horizonDays = 60
    static let step: TimeInterval = 1800
    static let maxBlocks = 1000

    struct Block: Equatable {
        let start: Date
        let end: Date
    }

    /// Un rendez-vous de l'iPhone, réduit à ce qui décide s'il compte (testable sans EventKit).
    struct Entry {
        let calendarID: String
        let start: Date
        let end: Date
        let allDay: Bool
        let availability: EKEventAvailability
        let url: URL?
        /// UID du fichier .ics (calendarItemExternalIdentifier) : « …@vendredi-party » pour les soirées du calendrier abonné.
        let externalID: String?
    }

    static func floor(_ date: Date) -> Date {
        Date(timeIntervalSince1970: (date.timeIntervalSince1970 / step).rounded(.down) * step)
    }

    static func ceil(_ date: Date) -> Date {
        Date(timeIntervalSince1970: (date.timeIntervalSince1970 / step).rounded(.up) * step)
    }

    /// Soirée Party déjà dans l'iPhone : calendrier abonné « Vendredi Party » (UID @vendredi-party), fichier .ics de Party,
    /// ou date de sondage mise par l'app (NativeCalendar.swift : lien vers /events/event/…). Party la compte déjà elle-même.
    static func isParty(_ entry: Entry, partyHost: String? = AppConfig.baseURL.host) -> Bool {
        if let uid = entry.externalID?.lowercased(), uid.hasSuffix("@vendredi-party") || uid.hasSuffix("@vendredi-party-agenda") {
            return true
        }
        guard let url = entry.url, let host = url.host?.lowercased(), let partyHost else { return false }
        return host == partyHost.lowercased() && url.path.hasPrefix("/events/event/")
    }

    /// Compte comme « pris » : calendrier coché, pas une soirée Party, pas « disponible ». Une journée entière ne compte
    /// que marquée occupée (vacances), jamais un jour férié ni un anniversaire.
    static func counts(_ entry: Entry, busyCalendars: Set<String>, partyHost: String? = AppConfig.baseURL.host) -> Bool {
        guard busyCalendars.contains(entry.calendarID), entry.end > entry.start, !isParty(entry, partyHost: partyHost) else { return false }
        if entry.allDay { return entry.availability == .busy || entry.availability == .unavailable }
        return entry.availability != .free
    }

    /// Plages à envoyer : arrondies vers l'extérieur à 30 min, coupées à [maintenant, +60 jours], fusionnées, 1000 au plus.
    static func blocks(_ entries: [Entry], busyCalendars: Set<String>, now: Date = Date(),
                       partyHost: String? = AppConfig.baseURL.host) -> [Block] {
        let from = floor(now), to = from.addingTimeInterval(Double(horizonDays) * 86_400)
        let rounded = entries
            .filter { counts($0, busyCalendars: busyCalendars, partyHost: partyHost) }
            .compactMap { entry -> Block? in
                let start = max(floor(entry.start), from), end = min(ceil(entry.end), to)
                return end > start ? Block(start: start, end: end) : nil
            }
            .sorted { $0.start < $1.start }
        var merged: [Block] = []
        for block in rounded {
            if let last = merged.last, block.start <= last.end {
                merged[merged.count - 1] = Block(start: last.start, end: max(last.end, block.end))
            } else {
                merged.append(block)
            }
        }
        return Array(merged.prefix(maxBlocks))
    }

    /// Corps de agenda_set_busy : [{"s": ISO, "e": ISO}], rien d'autre.
    static func payload(_ blocks: [Block]) -> [[String: String]] {
        blocks.map { ["s": iso($0.start), "e": iso($0.end)] }
    }

    static func iso(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }
}

/// Calendriers de l'iPhone : ceux que Party n'utilise jamais pour les dispos (le calendrier abonné « Vendredi Party », les
/// anniversaires) ; leur interrupteur « compte dans mes dispos » reste éteint.
enum AgendaCalendars {
    static let partyFeedName = "Vendredi Party"

    static func excluded(type: EKCalendarType, title: String) -> String? {
        if type == .birthday { return "birthdays" }
        if type == .subscription && title.trimmingCharacters(in: .whitespaces) == partyFeedName { return "party" }
        return nil
    }

    /// Origine montrée à l'écran (« iCloud », « Google », « Exchange », « Sur l'iPhone »…).
    static func source(type: EKSourceType?, title: String?) -> String {
        let name = title ?? ""
        switch type {
        case .local?: return "Sur l'iPhone"
        case .exchange?: return "Exchange"
        case .subscribed?: return "Abonnements"
        case .birthdays?: return "Anniversaires"
        default:
            let lower = name.lowercased()
            if lower.contains("gmail") || lower.contains("google") { return "Google" }
            return name.isEmpty ? "Autre" : name
        }
    }
}

/// Préférences des calendriers de l'iPhone (afficher dans l'Agenda / compte dans mes dispos), gardées sur l'iPhone
/// seulement (UserDefaults), jamais envoyées. Par défaut : affiché, ne compte pas (choisi un par un).
struct AgendaPrefs {
    struct Calendar: Equatable {
        var shown: Bool
        var countsBusy: Bool
    }

    private static let key = "party.agenda.calendars.v1"
    private static let syncedKey = "party.agenda.synced.v1"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    func get(_ id: String, excluded: String?) -> Calendar {
        let saved = all()[id]
        // Exclus d'office : « Vendredi Party » n'est pas montré deux fois (Party l'affiche déjà) et ne compte jamais.
        let shown = saved?["shown"] ?? (excluded != "party")
        return Calendar(shown: shown, countsBusy: excluded == nil && (saved?["countsBusy"] ?? false))
    }

    func set(_ id: String, shown: Bool?, countsBusy: Bool?) {
        var everything = all()
        var entry = everything[id] ?? [:]
        if let shown { entry["shown"] = shown }
        if let countsBusy { entry["countsBusy"] = countsBusy }
        everything[id] = entry
        defaults.set(everything, forKey: Self.key)
    }

    /// La page a demandé un envoi au moins une fois sur cet iPhone : l'app le refait seule au retour au premier plan.
    var synced: Bool {
        get { defaults.bool(forKey: Self.syncedKey) }
        nonmutating set { defaults.set(newValue, forKey: Self.syncedKey) }
    }

    private func all() -> [String: [String: Bool]] {
        defaults.dictionary(forKey: Self.key) as? [String: [String: Bool]] ?? [:]
    }
}
