import Foundation

/// Liens cliquables dans un texte d'événement (avis 2c221fd8effc), même règle que le module web
/// (web/events/src/lib/links.ts) : seuls http(s), mailto: et tel: deviennent des liens, jamais javascript:/data:.
/// SwiftUI ouvre le lien avec l'environnement openURL : Safari pour une adresse web, Mail ou Téléphone sinon.
enum LinkedText {
    static let safeSchemes: Set<String> = ["http", "https", "mailto", "tel"]

    /// Adresse sûre ou nil (schéma autorisé, hôte présent pour http(s), pas d'identifiants « banque.ch@piège.com »).
    static func safeURL(_ url: URL?) -> URL? {
        guard let url, let scheme = url.scheme?.lowercased(), safeSchemes.contains(scheme) else { return nil }
        if scheme.hasPrefix("http") {
            guard let host = url.host, !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        }
        return url
    }

    /// Le texte avec ses liens (souligné, couleur du lien par défaut). Le texte lui-même n'est jamais interprété.
    static func attributed(_ text: String) -> AttributedString {
        var out = AttributedString(text)
        let types: NSTextCheckingResult.CheckingType = [.link, .phoneNumber]
        guard let detector = try? NSDataDetector(types: types.rawValue) else { return out }
        let ns = text as NSString
        for match in detector.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            let url: URL?
            switch match.resultType {
            case .phoneNumber:
                let digits = (match.phoneNumber ?? "").filter { $0.isNumber || $0 == "+" }
                url = digits.count >= 9 ? URL(string: "tel:\(digits)") : nil
            default:
                url = match.url
            }
            guard let safe = safeURL(url), let range = Range(match.range, in: text),
                  let lower = AttributedString.Index(range.lowerBound, within: out),
                  let upper = AttributedString.Index(range.upperBound, within: out) else { continue }
            out[lower..<upper].link = safe
            out[lower..<upper].underlineStyle = .single
        }
        return out
    }
}
