import Charts
import SwiftUI

/// Mes stats de jeu › Méninges : Température, domaines, évolution, série, forces, vitesse/précision, jeux, classement.
/// Sections posées dans la liste de GameStatsView (chargement et erreur gérés comme le Purify Test).
struct BrainStatsSections: View {
    @ObservedObject var store: AccountStore
    let openGames: () -> Void

    private var catalog: BrainCatalog { store.brainCatalog }

    var body: some View {
        if let stats = store.brain {
            if stats.plays == 0 {
                empty
            } else {
                hero(stats)
                domains(stats)
                evolution(stats)
                strengths(stats)
                balance(stats)
                games(stats)
                board
            }
        } else if let error = store.brainError {
            Section {
                Text(error).foregroundStyle(.secondary)
                Button("Réessayer") { Task { await store.loadBrain() } }
            }
        }
    }

    // MARK: Jamais joué

    private var empty: some View {
        Section {
            VStack(spacing: 10) {
                Text("🧠").font(.system(size: 54))
                Text("Pas encore de partie").font(.headline)
                Text("Lance Méninges dans l'onglet Jeux : ta Température, tes domaines et ta série apparaîtront ici.")
                    .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                Button("Aller aux jeux", action: openGames).buttonStyle(.borderedProminent)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
        }
    }

    // MARK: Température

    private func hero(_ stats: BrainStats) -> some View {
        Section {
            VStack(spacing: 6) {
                Text("Ta Température").font(.subheadline).foregroundStyle(.secondary)
                Text(BrainStats.degrees(stats.temperature))
                    .font(.system(size: 52, weight: .heavy, design: .rounded)).foregroundStyle(Palette.accent)
                    .contentTransition(.numericText())
                    .motion(Motion.smooth, value: stats.temperature)
                if let pct = stats.percentile ?? store.brainBoard?.percentile {
                    Text("Plus chaud que \(pct) % des joueurs Party").font(.headline)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .accessibilityElement(children: .combine)
            LabeledContent("🔥 Série", value: streakText(stats.streak.current))
            LabeledContent("Record de série", value: streakText(stats.streak.best))
            if let progress = stats.monthProgress {
                LabeledContent("Progrès du mois") {
                    Text((progress > 0 ? "+" : "") + BrainStats.degrees(progress))
                        .foregroundStyle(progress > 0 ? .green : progress < 0 ? .red : .secondary)
                }
            }
            LabeledContent("Parties jouées", value: "\(stats.plays)")
        } header: {
            Text(stats.name)
        }
    }

    private func streakText(_ days: Int) -> String {
        days == 0 ? "Aucune" : "\(days) jour\(days > 1 ? "s" : "")"
    }

    // MARK: Domaines

    private struct DomainBar: Identifiable {
        let domain: BrainCatalog.Domain
        let index: Int
        var id: String { domain.id }
        var title: String { "\(domain.icon) \(domain.label)" }
    }

    private func bars(_ stats: BrainStats) -> [DomainBar] {
        catalog.domains.map { DomainBar(domain: $0, index: stats.domains[$0.id]?.index ?? 0) }
    }

    private func domains(_ stats: BrainStats) -> some View {
        Section {
            Chart(bars(stats)) { bar in
                BarMark(x: .value("°M", bar.index), y: .value("Domaine", bar.title))
                    .foregroundStyle(Color(hex: bar.domain.hex) ?? Palette.accent)
                    .cornerRadius(5)
                    .annotation(position: .trailing) {
                        Text(bar.index > 0 ? BrainStats.degrees(bar.index) : "—")
                            .font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                    }
            }
            .chartXScale(domain: 0...2000)
            .chartXAxis(.hidden)
            .frame(height: CGFloat(bars(stats).count) * 34)
            .padding(.vertical, 6)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(bars(stats).map { "\($0.domain.label) \($0.index) degrés M" }.joined(separator: ", "))
        } header: {
            Text("Tes domaines")
        } footer: {
            Text("1 000 °M = une partie typique. Calcul a son indice à part, hors Température.")
        }
    }

    // MARK: Évolution

    @ViewBuilder
    private func evolution(_ stats: BrainStats) -> some View {
        let days = stats.curve
        if days.count >= 2 {
            Section {
                Chart(days) { day in
                    AreaMark(x: .value("Jour", day.date ?? .now, unit: .day), y: .value("°M", day.temperature))
                        .foregroundStyle(LinearGradient(colors: [Palette.accent.opacity(0.35), .clear],
                                                        startPoint: .top, endPoint: .bottom))
                        .interpolationMethod(.monotone)
                    LineMark(x: .value("Jour", day.date ?? .now, unit: .day), y: .value("°M", day.temperature))
                        .foregroundStyle(Palette.accent)
                        .lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                        .interpolationMethod(.monotone)
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.day().month(.abbreviated), centered: false)
                    }
                }
                .environment(\.locale, Locale(identifier: "fr_CH"))
                .frame(height: 180)
                .padding(.vertical, 6)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Évolution de ta Température sur \(days.count) jours, aujourd'hui \(days.last?.temperature ?? 0) degrés M")
            } header: {
                Text("Évolution (30 jours)")
            }
        }
    }

    // MARK: Forces et faiblesses

    private func strengths(_ stats: BrainStats) -> some View {
        Section {
            if !stats.insight.isEmpty {
                Text(stats.insight).font(.subheadline)
            }
            if !stats.strengths.isEmpty {
                LabeledContent("💪 Forces", value: labels(stats.strengths))
            }
            if !stats.weaknesses.isEmpty {
                LabeledContent("🎯 À travailler", value: labels(stats.weaknesses))
            }
        } header: {
            Text("Forces et faiblesses")
        }
    }

    private func labels(_ ids: [String]) -> String {
        ids.map { catalog.domain($0).label }.joined(separator: ", ")
    }

    // MARK: Vitesse et précision

    private func balance(_ stats: BrainStats) -> some View {
        Section {
            meter("⚡ Vitesse", stats.speedVsAccuracy.speed, tint: Color(hex: catalog.domain("vitesse").hex) ?? .blue)
            meter("🎯 Précision", stats.speedVsAccuracy.accuracy, tint: Color(hex: catalog.domain("attention").hex) ?? .teal)
        } header: {
            Text("Vitesse ou précision")
        } footer: {
            Text("Sur tes parties des 30 derniers jours.")
        }
    }

    private func meter(_ title: String, _ value: Int, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title).font(.subheadline.weight(.semibold))
                Spacer()
                Text("\(value) %").font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
            }
            ProgressView(value: Double(value), total: 100).tint(tint)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Jeux

    private func games(_ stats: BrainStats) -> some View {
        Section {
            ForEach(stats.playedGames, id: \.id) { row in
                let domain = catalog.domain(catalog.game(row.id)?.domain ?? "")
                HStack(spacing: 12) {
                    Text(domain.icon).font(.title3)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(catalog.game(row.id)?.name ?? row.id).font(.subheadline.weight(.semibold))
                        Text("Niveau \(row.game.lastLevel) · record \(row.game.best) · \(row.game.plays) partie\(row.game.plays > 1 ? "s" : "")")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(BrainStats.degrees(row.game.index)).font(.subheadline.monospacedDigit().weight(.semibold))
                }
                .accessibilityElement(children: .combine)
            }
        } header: {
            Text("Tes jeux")
        }
    }

    // MARK: Classement

    @ViewBuilder
    private var board: some View {
        if let board = store.brainBoard, !board.board.isEmpty {
            Section {
                ForEach(board.board) { player in
                    HStack(spacing: 12) {
                        Text("\(board.rank(of: player))").font(.subheadline.monospacedDigit().weight(.bold))
                            .foregroundStyle(.secondary).frame(minWidth: 24, alignment: .leading)
                        Text(player.me ? "\(player.name) (toi)" : player.name)
                            .font(.subheadline.weight(player.me ? .bold : .regular))
                        Spacer()
                        Text(BrainStats.degrees(player.temperature)).font(.subheadline.monospacedDigit())
                            .foregroundStyle(player.me ? Palette.accent : .primary)
                    }
                    .listRowBackground(player.me ? Palette.accent.opacity(0.18) : nil)
                    .accessibilityElement(children: .combine)
                }
            } header: {
                Text("Classement des membres")
            } footer: {
                if let rank = board.rank {
                    Text("Tu es \(rank == 1 ? "1er" : "\(rank)e") sur \(board.players) joueur\(board.players > 1 ? "s" : "").")
                }
            }
        }
    }
}
