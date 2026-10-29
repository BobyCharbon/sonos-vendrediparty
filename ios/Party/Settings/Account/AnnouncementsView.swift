import SwiftUI

/// Annonces admin : lues par tous les membres ; avec le droit « Publier une annonce », un formulaire en tête.
struct AnnouncementsView: View {
    @ObservedObject var store: AccountStore
    let canPublish: Bool
    @State private var title = ""
    @State private var message = ""
    @State private var confirm = false

    var body: some View {
        List {
            if canPublish { compose }
            Section {
                if let page = store.announcements {
                    if page.announcements.isEmpty { Text("Aucune annonce pour le moment.").foregroundStyle(.secondary) }
                    ForEach(page.announcements) { item in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(item.title).font(.headline)
                            Text(item.body)
                            Text("Administration · \(AdminDate.text(item.createdAt) ?? "")").font(.footnote).foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                    }
                    if page.more {
                        Button("Annonces précédentes") { Task { await store.loadOlderAnnouncements() } }.disabled(store.busy)
                    }
                } else if let error = store.error {
                    Text(error).foregroundStyle(.secondary)
                    Button("Réessayer") { Task { await store.loadAnnouncements() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            } header: {
                Text("Annonces")
            } footer: {
                Text("Pour tout le groupe. Les annonces restent accessibles après lecture et ne peuvent pas être masquées.")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Annonces admin")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadAnnouncements() }
        .task { await store.loadAnnouncements() }
        .confirmationDialog("Publier pour tout le groupe ?", isPresented: $confirm, titleVisibility: .visible) {
            Button("Publier") {
                Task {
                    if await store.publish(title: clean(title), body: clean(message)) {
                        title = ""
                        message = ""
                    }
                }
            }
        } message: {
            Text("Tous les membres la recevront, même ceux qui ont coupé leurs notifications (heures de silence respectées).")
        }
    }

    private var compose: some View {
        Section {
            TextField("Titre : l'essentiel en quelques mots", text: $title)
                .onChange(of: title) { if $0.count > 120 { title = String($0.prefix(120)) } }
            TextField("Message", text: $message, axis: .vertical)
                .lineLimit(3...10)
                .onChange(of: message) { if $0.count > 4000 { message = String($0.prefix(4000)) } }
            Button("Publier pour tout le groupe") { confirm = true }
                .disabled(clean(title).isEmpty || clean(message).isEmpty || store.busy)
        } header: {
            Text("Publier une annonce")
        } footer: {
            if let error = store.error, store.announcements != nil { Text(error).foregroundStyle(.red) }
        }
    }

    private func clean(_ text: String) -> String { text.trimmingCharacters(in: .whitespacesAndNewlines) }
}

/// Mes stats de jeu : Purify Test (dernier score, record, profil par catégorie), pour le seul titulaire du compte.
struct GameStatsView: View {
    @ObservedObject var store: AccountStore
    let openGames: () -> Void

    var body: some View {
        List {
            if let stats = store.stats {
                if stats.plays == 0 {
                    Section {
                        VStack(spacing: 10) {
                            Text("😇").font(.system(size: 54))
                            Text("Pas encore de test").font(.headline)
                            Text("Passe le Purify Test dans l'onglet Jeux : ton dernier score et ton profil apparaîtront ici.")
                                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                            Button("Aller aux jeux", action: openGames).buttonStyle(.borderedProminent)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                    }
                } else {
                    score(stats)
                    profile(stats)
                }
            } else if let error = store.statsError {
                Section {
                    Text(error).foregroundStyle(.secondary)
                    Button("Réessayer") { Task { await store.loadStats() } }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Mes stats de jeu")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if store.stats == nil && store.statsError == nil { ProgressView() } }
        .refreshable { await store.loadStats() }
        .task { await store.loadStats() }
    }

    private func score(_ stats: PurityStats) -> some View {
        Section {
            VStack(spacing: 6) {
                Text("Ton dernier score d'impureté").font(.subheadline).foregroundStyle(.secondary)
                Text("\(stats.last) %").font(.system(size: 52, weight: .heavy, design: .rounded)).foregroundStyle(Palette.accent)
                Text(PurityStats.grade(stats.last)).font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .accessibilityElement(children: .combine)
            if stats.lastAt > 0 {
                LabeledContent("Dernier test", value: Date(timeIntervalSince1970: stats.lastAt)
                    .formatted(.dateTime.day().month(.wide).year().locale(Locale(identifier: "fr_CH"))))
            }
            LabeledContent("Record", value: "\(stats.best) %")
            LabeledContent("Tests passés", value: "\(stats.plays)")
        } header: {
            Text("Purify Test")
        }
    }

    private func profile(_ stats: PurityStats) -> some View {
        Section {
            ForEach(stats.ranked) { row in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("\(row.emoji) \(row.label)").font(.subheadline.weight(.semibold))
                        Spacer()
                        Text("\(row.yes)/\(row.total)").font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
                    }
                    ProgressView(value: Double(row.pct), total: 100).tint(Palette.accent)
                }
                .accessibilityElement(children: .combine)
                .accessibilityValue("\(row.pct) %")
            }
        } header: {
            Text("Ton profil d'impureté")
        } footer: {
            Text("🔒 Toi seul le vois.")
        }
    }
}
