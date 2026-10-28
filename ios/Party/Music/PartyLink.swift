import Foundation

/// Ce que contient un QR code de l'hôte (app/main.py : /qr.svg et le QR d'une partie) :
/// « <site>/?pin=1234 » pour rejoindre la soirée, « <site>/?game=1234 » pour une partie.
enum PartyLink: Equatable {
    /// Code de la soirée : rejoint directement depuis l'écran natif.
    case party(code: String)
    /// Autre page du site (partie de jeu…) : ouverte dans la page.
    case page(URL)

    /// nil : QR code d'autre chose (site inconnu, texte quelconque).
    static func parse(_ scanned: String, isInternal: (URL) -> Bool) -> PartyLink? {
        let text = scanned.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.count == codeLength, text.allSatisfy(\.isNumber) { return .party(code: text) }  // code seul
        guard let url = URL(string: text), url.scheme == "https", isInternal(url) else { return nil }
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        if let pin = query.first(where: { $0.name == "pin" })?.value, !pin.isEmpty { return .party(code: pin) }
        return .page(url)
    }

    private static let codeLength = 4
}
