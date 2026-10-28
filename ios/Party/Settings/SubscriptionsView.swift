import SwiftUI

/// Réglages › Abonnements : catégories et tags d'événements suivis. Servent aux alertes « Nouvel événement publié ›
/// Si abonné » et au filtre « Mes abonnements » de la liste. Un toucher suit ou ne suit plus, enregistré aussitôt.
struct SubscriptionsView: View {
    @ObservedObject var store: SettingsStore

    var body: some View {
        List {
            if let subs = store.subscriptions {
                Section {
                    Text(summary(subs)).font(.subheadline).foregroundStyle(.secondary)
                }
                topics("Catégories", kind: "category", subs.categories, subs)
                topics("Tags", kind: "tag", subs.tags, subs)
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Abonnements")
        .navigationBarTitleDisplayMode(.inline)
        .overlay {
            if store.subscriptions == nil {
                if let error = store.subscriptionsError {
                    VStack(spacing: 12) {
                        Text(error).multilineTextAlignment(.center).foregroundStyle(.secondary)
                        Button("Réessayer") { Task { await store.loadSubscriptions() } }
                    }
                    .padding()
                } else {
                    ProgressView()
                }
            }
        }
        .overlay(alignment: .bottom) { SettingsNoticeBanner(store: store) }
        .refreshable { await store.loadSubscriptions() }
        .task { await store.loadSubscriptions() }
    }

    @ViewBuilder
    private func topics(_ title: String, kind: String, _ list: [Subscriptions.Topic], _ subs: Subscriptions) -> some View {
        if !list.isEmpty {
            Section(title) {
                ForEach(list) { topic in
                    let on = subs.follows(kind, topic.id)
                    Button {
                        Task { await store.setSubscription(kind, topic.id, !on) }
                    } label: {
                        HStack(spacing: 12) {
                            Circle().fill(Color(hex: topic.color) ?? Palette.accent).frame(width: 12, height: 12)
                            Text(kind == "tag" ? "#\(topic.name)" : [topic.icon, topic.name].compactMap { $0 }.joined(separator: " "))
                            Spacer()
                            Image(systemName: on ? "checkmark.circle.fill" : "circle")
                                .font(.title3)
                                .foregroundStyle(on ? Palette.accent : .secondary)
                        }
                    }
                    .foregroundStyle(.primary)
                    .disabled(store.saving.contains("sub." + topic.id))
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityHint(on ? "Suivi : touche pour ne plus suivre" : "Touche pour suivre")
                }
            }
        }
    }

    private func summary(_ subs: Subscriptions) -> String {
        subs.count == 0
            ? "Tu ne suis encore rien : touche une catégorie ou un tag pour le suivre."
            : "Tu suis \(subs.count) \(subs.count > 1 ? "sujets" : "sujet"). Avec « Si abonné », tu es prévenu d'un nouvel événement qui a au moins une de ces catégories OU un de ces tags."
    }
}

extension Color {
    /// « #ff4f9a » (couleurs des catégories et tags) ; nil si illisible.
    init?(hex: String?) {
        guard let hex, hex.hasPrefix("#"), hex.count == 7, let value = UInt32(hex.dropFirst(), radix: 16) else { return nil }
        self.init(red: Double((value >> 16) & 0xFF) / 255, green: Double((value >> 8) & 0xFF) / 255, blue: Double(value & 0xFF) / 255)
    }
}
