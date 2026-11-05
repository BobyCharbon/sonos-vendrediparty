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

/// Avant le premier contenu (message, surnom, nom de groupe) : les conditions d'utilisation à accepter (Google UGC).
struct TermsAcceptSheet: View {
    @ObservedObject var store: ModerationStore
    /// Appelé avec true une fois acceptées.
    var onDone: (Bool) -> Void = { _ in }
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Sur Party, on se respecte : pas de harcèlement, pas de propos haineux ni de contenu sexuel, pas d'arnaque ni de vente. Les objets du jeu n'ont aucune valeur en argent. Tout contenu peut être signalé ; un modérateur peut le masquer, avertir, suspendre ou bannir un compte.")
                    NavigationLink { TermsView(store: store) } label: { Text("Lire les conditions d'utilisation") }
                }
                if let error = store.error {
                    Section { Text(error).foregroundStyle(.red) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle("Avant de publier")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Plus tard") { onDone(false); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("J'accepte") {
                        Task {
                            if await store.acceptTerms() {
                                Haptics.success()
                                onDone(true)
                                dismiss()
                            }
                        }
                    }
                    .disabled(store.busy.contains("accept"))
                    .accessibilityIdentifier("terms-accept")
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
