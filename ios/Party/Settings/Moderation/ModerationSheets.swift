import SwiftUI

/// « Signaler » (Apple 1.2, Google UGC) : une raison, un commentaire facultatif ; la file des modérateurs le reçoit avec
/// une copie du contenu. La personne signalée n'est pas prévenue.
struct ReportSheet: View {
    @ObservedObject var store: ModerationStore
    let target: ReportTarget
    @Environment(\.dismiss) private var dismiss
    @State private var reason: ReportReason?
    @State private var comment = ""
    @State private var sent = false

    var body: some View {
        NavigationStack {
            Form {
                if sent {
                    Section {
                        Label("Merci, c'est envoyé", systemImage: "checkmark.seal.fill").font(.headline)
                        Text("Un modérateur va regarder. La personne n'est pas prévenue que c'est toi.").foregroundStyle(.secondary)
                    }
                } else {
                    Section {
                        ForEach(ReportReason.allCases) { r in
                            Button {
                                Haptics.selection()
                                reason = r
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(r.label).foregroundStyle(.primary)
                                        Text(r.hint).font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if reason == r { Image(systemName: "checkmark").foregroundStyle(.tint) }
                                }
                            }
                            .accessibilityAddTraits(reason == r ? .isSelected : [])
                            .accessibilityIdentifier("report-\(r.rawValue)")
                        }
                    } header: {
                        Text("Pourquoi signaler \(target.label) ?")
                    }
                    Section {
                        TextField("Commentaire (facultatif)", text: $comment, axis: .vertical)
                            .lineLimit(2...5)
                            .onChange(of: comment) { value in if value.count > 500 { comment = String(value.prefix(500)) } }
                    } footer: {
                        Text("Un modérateur reçoit ton signalement et une copie du contenu.")
                    }
                    if let error = store.error {
                        Section { Text(error).foregroundStyle(.red) }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle("Signaler")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(sent ? "Fermer" : "Annuler") { dismiss() }
                }
                if !sent {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Envoyer") {
                            guard let reason else { return }
                            Task {
                                if await store.report(target, reason: reason, comment: comment) {
                                    Haptics.success()
                                    Motion.animate { sent = true }
                                }
                            }
                        }
                        .disabled(reason == nil || store.busy.contains("report"))
                        .accessibilityIdentifier("report-send")
                    }
                }
            }
            .onAppear { store.error = nil }
        }
        .preferredColorScheme(.dark)
    }
}

/// « Plus tard » sur la feuille des CGU n'est jamais muet (contrôle Apple, tour 3) : la phrase dite à la place de l'action.
/// Même texte que le web (`termsLater`, web/events/src/components/TermsSheet.tsx).
enum TermsLater {
    static func message(_ action: String, button: String? = nil) -> String {
        "Pour \(action), accepte d’abord les conditions d’utilisation de Party : touche "
            + (button.map { "« \($0) »" } ?? "à nouveau le bouton") + " pour les relire."
    }
}

/// Avant le premier contenu (message, surnom, nom de groupe) : les conditions d'utilisation à accepter (Google UGC).
struct TermsAcceptSheet: View {
    @ObservedObject var store: ModerationStore
    /// « Avant d'écrire », « Avant de publier »… : le moment où la feuille s'ouvre.
    var title: String = "Avant de publier"
    /// Appelé avec true une fois acceptées.
    var onDone: (Bool) -> Void = { _ in }
    @Environment(\.dismiss) private var dismiss
    @State private var readAll = false

    /// L'essentiel, en grand (demande de l'admin du 26.11 : « afficher les conditions en grand, que ce soit clair »).
    private static let points: [(String, String)] = [
        ("hand.raised.fill", "On se respecte : ni harcèlement, ni propos haineux, ni contenu sexuel."),
        ("cart.badge.minus", "Pas d'arnaque ni de vente. Les points des jeux n'ont aucune valeur en argent."),
        ("exclamationmark.shield.fill", "Tolérance zéro : un contenu choquant est retiré et son auteur peut être banni."),
        ("flag.fill", "Tout contenu peut être signalé ; un modérateur peut le masquer, avertir, suspendre ou bannir un compte."),
        ("banknote", "Party ne vend rien et ne touche jamais d'argent."),
    ]

    var body: some View {
        NavigationStack {
            ScrollViewReader { scroller in
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(title).font(.largeTitle.bold()).foregroundStyle(PronoTheme.t1)
                        Text("Accepte une seule fois les conditions d'utilisation de Party, puis tu continues tout de suite.")
                            .font(.title3).foregroundStyle(PronoTheme.t2)
                    }
                    // Visible sans défiler, au-dessus des boutons fixés, même sur l'iPhone Air / 18 Pro (e2e du 27.11).
                    Text("Party est réservée aux 18 ans et plus : en touchant « J'accepte », tu confirmes avoir 18 ans ou plus.")
                        .font(.body.bold()).foregroundStyle(PronoTheme.t1)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                        .background(PronoTheme.pink.opacity(0.14), in: RoundedRectangle(cornerRadius: 16))
                        .accessibilityIdentifier("terms-adult")
                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(Self.points, id: \.1) { icon, line in
                            HStack(alignment: .top, spacing: 14) {
                                Image(systemName: icon).font(.title3).foregroundStyle(PronoTheme.pink).frame(width: 30)
                                    .accessibilityHidden(true)
                                Text(line).font(.body).foregroundStyle(PronoTheme.t1).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    DisclosureGroup(isExpanded: $readAll) {
                        VStack(alignment: .leading, spacing: 14) {
                            Text("Version du \(TermsView.updated)").id("terms-start").font(.footnote).foregroundStyle(PronoTheme.t2)
                            ForEach(TermsView.sections, id: \.0) { section, paragraphs in
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(section).font(.headline).foregroundStyle(PronoTheme.t1)
                                    ForEach(paragraphs, id: \.self) {
                                        Text($0).font(.subheadline).foregroundStyle(PronoTheme.t2).fixedSize(horizontal: false, vertical: true)
                                    }
                                }
                            }
                        }
                        .padding(.top, 10)
                    } label: {
                        Text("Lire les conditions complètes").font(.headline).foregroundStyle(PronoTheme.pinkInk)
                    }
                    .tint(PronoTheme.pinkInk)
                    .accessibilityIdentifier("terms-read-all")
                    .id("terms-read-all")
                    if let error = store.error {
                        Text(error).foregroundStyle(.red)
                    }
                }
                .padding(20)
            }
            // Déplié : le texte remonte en haut de l'écran (sinon il commençait juste au-dessus du bouton).
            .onChange(of: readAll) { open in
                guard open else { return }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                    withAnimation { scroller.scrollTo("terms-read-all", anchor: .top) }
                }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 6) {
                    Button {
                        Task {
                            if await store.acceptTerms() {
                                Haptics.success()
                                onDone(true)
                                dismiss()
                            }
                        }
                    } label: {
                        Text("J'accepte les conditions").font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 8)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(PronoTheme.pinkFill)
                    .controlSize(.large)
                    .disabled(store.busy.contains("accept"))
                    .accessibilityIdentifier("terms-accept")
                    Button("Plus tard") { onDone(false); dismiss() }
                        .font(.body).foregroundStyle(PronoTheme.t2).padding(.vertical, 6)
                        .accessibilityIdentifier("terms-later")
                    // Nouvel arrivant : il sait ce qu'il garde sans elles, rien ne le bloque (contrôle du 26.11).
                    Text("Sans elles, tu gardes les jeux. Écrire, publier, choisir ton surnom ou répondre à un événement te les redemanderont.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("terms-later-hint")
                }
                .padding(.horizontal, 20).padding(.top, 12).padding(.bottom, 8)
                .background(AppConfig.background.ignoresSafeArea())
            }
            }
            .background(AppConfig.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            // Barre opaque : le texte défilé ne passe plus sous le ✕ (recette du 26.11).
            .toolbarBackground(AppConfig.background, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button { onDone(false); dismiss() } label: { Image(systemName: "xmark") }
                        .accessibilityLabel("Fermer")
                }
            }
        }
        .presentationDetents([.large])
        .preferredColorScheme(.dark)
    }
}
