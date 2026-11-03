import CryptoKit
import Foundation

/// Numéros du répertoire → format international E.164 (« +41791234567 »), puis empreinte envoyée à Party.
///
/// Un numéro écrit à l'international (« +41 », « 0041 », « +41 (0)79… ») n'a qu'une forme. Un numéro national
/// (« 079 123 45 67 ») dépend du pays : on essaie d'abord la région du téléphone, puis la Suisse et la France
/// (l'admin vit en France et travaille en Suisse : son répertoire mélange les deux), seulement quand la longueur
/// correspond (9 chiffres après le 0 dans les deux pays).
enum PhoneNumbers {
    /// Indicatifs des pays proches ; une région inconnue retombe sur la Suisse.
    static let callingCodes: [String: String] = [
        "CH": "41", "FR": "33", "DE": "49", "AT": "43", "IT": "39", "BE": "32", "LU": "352", "NL": "31",
        "ES": "34", "PT": "351", "GB": "44", "LI": "423", "MC": "377", "US": "1", "CA": "1",
    ]
    static let fallbackRegion = "CH"
    /// Pays essayés en plus pour un numéro national de 10 chiffres commençant par 0.
    static let neighbours = ["CH", "FR"]
    private static let minDigits = 8
    private static let maxDigits = 15

    /// Région du téléphone (Réglages › Général › Langue et région), ou la Suisse.
    static var deviceRegion: String {
        guard let code = Locale.current.region?.identifier, callingCodes[code] != nil else { return fallbackRegion }
        return code
    }

    /// Formes E.164 possibles d'un numéro, la plus probable en premier ; vide si ce n'est pas un numéro.
    static func candidates(_ raw: String, region: String = deviceRegion) -> [String] {
        let cleaned = raw.replacingOccurrences(of: "(0)", with: "")
        let plus = cleaned.trimmingCharacters(in: .whitespaces).hasPrefix("+")
        let digits = cleaned.filter(\.isASCII).filter(\.isNumber)
        guard !digits.isEmpty else { return [] }
        if plus { return valid(digits) }
        if digits.hasPrefix("00") { return valid(String(digits.dropFirst(2))) }
        let home = callingCodes[region] != nil ? region : fallbackRegion
        if home == "US" || home == "CA" {
            if digits.count == 10 { return valid("1" + digits) }
            if digits.count == 11 && digits.hasPrefix("1") { return valid(digits) }
        }
        if digits.hasPrefix("0") {
            if home == "IT" { return valid("39" + digits) }  // l'Italie garde le 0
            let national = String(digits.dropFirst())
            var regions = [home]
            if national.count == 9 { regions += neighbours.filter { $0 != home } }
            return unique(regions.flatMap { valid(callingCodes[$0, default: "41"] + national) })
        }
        // Sans 0 ni + : déjà international si assez long (« 41791234567 »), sinon national sans le 0.
        if digits.count >= 11 { return valid(digits) }
        return valid(callingCodes[home, default: "41"] + digits)
    }

    /// Forme E.164 la plus probable.
    static func e164(_ raw: String, region: String = deviceRegion) -> String? { candidates(raw, region: region).first }

    /// Empreinte envoyée à Party : HMAC-SHA256(clé, « +41… »), en hexadécimal minuscule (même calcul que la base).
    static func digest(_ e164: String, key: String) -> String {
        let mac = HMAC<SHA256>.authenticationCode(for: Data(e164.utf8), using: SymmetricKey(data: Data(key.utf8)))
        return mac.map { String(format: "%02x", $0) }.joined()
    }

    private static func valid(_ digits: String) -> [String] {
        guard (minDigits...maxDigits).contains(digits.count), !digits.hasPrefix("0") else { return [] }
        return ["+" + digits]
    }

    private static func unique(_ list: [String]) -> [String] {
        var seen = Set<String>()
        return list.filter { seen.insert($0).inserted }
    }
}

/// « Nom du contact · pseudo » : le nom du répertoire en principal, le pseudo Party en plus petit.
struct PersonLabel: Equatable {
    let primary: String
    /// Pseudo Party, quand un nom de contact le remplace (et qu'il est différent).
    let secondary: String?

    init(contact: String?, pseudo: String) {
        let name = contact?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let nick = pseudo.trimmingCharacters(in: .whitespacesAndNewlines)
        if name.isEmpty {
            primary = nick
            secondary = nil
        } else {
            primary = name
            secondary = nick.isEmpty || nick.compare(name, options: [.caseInsensitive, .diacriticInsensitive]) == .orderedSame ? nil : nick
        }
    }

    /// Texte sur une ligne (« Marie Dupont · Mimi »), pour la voix et les textes simples.
    var text: String { secondary.map { "\(primary) · \($0)" } ?? primary }
}
