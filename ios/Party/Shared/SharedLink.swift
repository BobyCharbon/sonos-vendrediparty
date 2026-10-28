import Foundation

/// Ce que l'extension « Partager » recherche : le premier lien du texte partagé (Spotify envoie
/// « Écoute … https://open.spotify.com/track/… »), sinon le texte lui-même (recherche Spotify).
enum SharedLink {
    static func query(from shared: String) -> String {
        let text = shared.trimmingCharacters(in: .whitespacesAndNewlines)
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let range = NSRange(text.startIndex..., in: text)
        if let link = detector?.firstMatch(in: text, range: range)?.url, link.scheme?.hasPrefix("http") == true {
            return link.absoluteString
        }
        return text
    }
}
