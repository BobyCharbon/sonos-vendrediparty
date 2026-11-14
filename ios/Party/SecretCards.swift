import SwiftUI
import UIKit
import WebKit

/// Pyramide (avis 4c55c231a4d2) : après la distribution, chacun mémorise ses 4 cartes au moins 30 secondes, puis elles se
/// retournent pour le test de mémoire. Dans l'app, la page ne les dessine pas : elle les confie à l'app
/// (`PartyNative.secret.update`), qui les montre dans un panneau qu'une capture ou un enregistrement d'écran rend noir.
struct SecretCardsState: Equatable {
    struct Card: Equatable, Hashable {
        let rank: String
        let suit: String

        /// "TH" → 10 ♥ ; nil si la carte est illisible.
        init?(code: String) {
            let letters = Array(code.uppercased())
            guard letters.count == 2, "A23456789TJQK".contains(letters[0]), "SHDC".contains(letters[1]) else { return nil }
            rank = letters[0] == "T" ? "10" : String(letters[0])
            suit = String(letters[1])
        }

        var symbol: String { ["S": "♠", "H": "♥", "D": "♦", "C": "♣"][suit] ?? "?" }
        var isRed: Bool { suit == "H" || suit == "D" }
        var spoken: String { "\(rank) de \(["S": "pique", "H": "cœur", "D": "carreau", "C": "trèfle"][suit] ?? "")" }
    }

    static let maxCards = 4

    let cards: [Card]
    let title: String

    /// `{ cards: ["AS", "TH", …], title }` envoyé par games.js ; null ou rien de lisible : plus de panneau.
    init?(message: Any) {
        guard let body = message as? [String: Any], let codes = body["cards"] as? [String] else { return nil }
        let cards = codes.prefix(Self.maxCards).compactMap(Card.init(code:))
        guard !cards.isEmpty else { return nil }
        self.cards = cards
        let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.title = title.isEmpty ? "Tes cartes" : String(title.prefix(60))
    }
}

/// `PartyNative.secret.update(state | null)` (page principale de Party seulement) → panneau natif protégé.
final class SecretCardsHandler: NSObject, WKScriptMessageHandler {
    static let handler = "partySecret"
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return }
        model?.showSecretCards(SecretCardsState(message: message.body))
    }
}

/// Contenu absent des captures et des enregistrements d'écran (et de la recopie AirPlay) : il est posé dans la zone de
/// dessin d'un champ de mot de passe, qu'iOS retire de toute capture. Si iOS change cette zone, le contenu reste
/// affiché normalement (simplement sans protection).
struct ScreenshotProof<Content: View>: UIViewRepresentable {
    let content: Content

    final class Coordinator {
        let field = UITextField()
        var host: UIHostingController<Content>?
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    /// La zone de dessin d'un champ de mot de passe (celle qu'iOS retire des captures) ; nil si iOS n'en a plus.
    static func secureCanvas(of field: UITextField) -> UIView? {
        field.isSecureTextEntry = true
        field.layoutIfNeeded()
        return field.subviews.first
    }

    func makeUIView(context: Context) -> UIView {
        let canvas = Self.secureCanvas(of: context.coordinator.field) ?? UIView()
        canvas.subviews.forEach { $0.removeFromSuperview() }
        canvas.isUserInteractionEnabled = true
        canvas.backgroundColor = .clear
        let host = UIHostingController(rootView: content)
        host.view.backgroundColor = .clear
        host.view.translatesAutoresizingMaskIntoConstraints = false
        canvas.addSubview(host.view)
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: canvas.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: canvas.trailingAnchor),
            host.view.topAnchor.constraint(equalTo: canvas.topAnchor),
            host.view.bottomAnchor.constraint(equalTo: canvas.bottomAnchor),
        ])
        context.coordinator.host = host
        return canvas
    }

    func updateUIView(_ view: UIView, context: Context) {
        context.coordinator.host?.rootView = content
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UIView, context: Context) -> CGSize? {
        guard let host = context.coordinator.host else { return nil }
        let width = proposal.width ?? UIView.layoutFittingExpandedSize.width
        return host.sizeThatFits(in: CGSize(width: width, height: UIView.layoutFittingCompressedSize.height))
    }
}

/// Les 4 cartes à mémoriser, en bas de l'écran de jeu.
struct SecretCardsView: View {
    let state: SecretCardsState

    var body: some View {
        ScreenshotProof(content: panel)
            // Sous le panneau, hors de la zone protégée : c'est ce noir qu'on retrouve sur une capture d'écran.
            .background(Color.black, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .frame(maxWidth: 460)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(state.title) : \(state.cards.map(\.spoken).joined(separator: ", "))")
            .accessibilityIdentifier("secret-cards")
    }

    private var panel: some View {
        VStack(spacing: 12) {
            Text(state.title)
                .font(.headline)
                .foregroundStyle(.white)
            HStack(spacing: 10) {
                ForEach(Array(state.cards.enumerated()), id: \.offset) { _, card in
                    VStack(spacing: 2) {
                        Text(card.rank).font(.title2.weight(.heavy))
                        Text(card.symbol).font(.title2)
                    }
                    .foregroundStyle(card.isRed ? Color.red : Color.black)
                    .frame(maxWidth: .infinity, minHeight: 84)
                    .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
            Label("Capture d'écran : écran noir", systemImage: "eye.slash")
                .font(.footnote)
                .foregroundStyle(.white.opacity(0.7))
        }
        .padding(16)
        .background(Palette.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}
