import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Point d'entrée de l'extension « Partager › Party » (NSExtensionPrincipalClass) : lit le lien partagé
/// et affiche ShareView.
final class ShareViewController: UIViewController {
    private let model = ShareModel()
    /// Fermeture automatique après l'ajout, le temps de lire la confirmation.
    private static let closeDelay: Duration = .milliseconds(1200)

    override func viewDidLoad() {
        super.viewDidLoad()
        let host = UIHostingController(rootView: ShareView(model: model, close: { [weak self] in self?.finish() }))
        addChild(host)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(host.view)
        host.didMove(toParent: self)

        Task { @MainActor in
            await model.start(shared: await sharedText())
            for await phase in model.$phase.values {
                if case .added = phase {
                    try? await Task.sleep(for: Self.closeDelay)
                    finish()
                    break
                }
            }
        }
    }

    private func finish() {
        extensionContext?.completeRequest(returningItems: nil)
    }

    /// Lien (URL) ou texte du premier élément partagé.
    private func sharedText() async -> String {
        let providers = (extensionContext?.inputItems as? [NSExtensionItem] ?? []).flatMap { $0.attachments ?? [] }
        for provider in providers where provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
            if let url = try? await provider.loadItem(forTypeIdentifier: UTType.url.identifier) as? URL {
                return url.absoluteString
            }
        }
        for provider in providers where provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
            if let text = try? await provider.loadItem(forTypeIdentifier: UTType.plainText.identifier) as? String {
                return text
            }
        }
        return ""
    }
}

struct ShareView: View {
    @ObservedObject var model: ShareModel
    let close: () -> Void

    private static let accent = Color(red: 1, green: 79 / 255, blue: 154 / 255)
    private static let card = Color(red: 0.11, green: 0.085, blue: 0.17)
    private static let background = Color(red: 14 / 255, green: 11 / 255, blue: 22 / 255)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) { content }.padding(16)
            }
            .background(Self.background.ignoresSafeArea())
            .navigationTitle("Ajouter à la soirée")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer", action: close) }
            }
        }
        .tint(Self.accent)
        .preferredColorScheme(.dark)
    }

    @ViewBuilder
    private var content: some View {
        switch model.phase {
        case .loading:
            ProgressView("Recherche du titre…").frame(maxWidth: .infinity).padding(.top, 40)
        case .needsApp:
            message("music.note.house", "Ouvre Party ! et rejoins la soirée avec son code, puis partage à nouveau ce titre.")
        case .failed(let reason):
            message("exclamationmark.triangle", reason)
        case .added(let title):
            message("checkmark.circle.fill", "« \(title) » est dans la file 🎶")
        case .choose(let tracks):
            TextField("Ton prénom", text: $model.name)
                .textInputAutocapitalization(.words)
                .padding(12)
                .background(Self.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            ForEach(tracks) { track in row(track) }
        }
    }

    private func row(_ track: SpotifyTrack) -> some View {
        HStack(spacing: 12) {
            AsyncImage(url: URL(string: track.image)) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                Image(systemName: "music.note").foregroundStyle(.secondary)
            }
            .frame(width: 56, height: 56)
            .background(Color.white.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(track.title).font(.headline).lineLimit(2)
                Text(track.artist).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 0)
            Button {
                Task { await model.add(track) }
            } label: {
                if model.adding == track.id { ProgressView() } else { Text("Ajouter").bold() }
            }
            .buttonStyle(.borderedProminent)
            .disabled(model.name.trimmingCharacters(in: .whitespaces).isEmpty || model.adding != nil)
        }
        .padding(12)
        .background(Self.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func message(_ symbol: String, _ text: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: symbol).font(.system(size: 44)).foregroundStyle(Self.accent)
            Text(text).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 32)
    }
}
