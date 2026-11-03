import Charts
import SwiftUI

/// Mes stats de jeu › Méninges : Température, domaines, évolution, série, forces, vitesse/précision, jeux, classement.
/// Sections posées dans la liste de GameStatsView (chargement et erreur gérés comme le Purify Test).
struct BrainStatsSections: View {
    @ObservedObject var store: AccountStore
    let openGames: () -> Void
    @Environment(\.dynamicTypeSize) private var typeSize
    /// Courbe plus haute avec un texte agrandi (libellés des axes plus grands).
    @ScaledMetric(relativeTo: .caption) private var curveHeight: CGFloat = 180

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
                    .lineLimit(1).minimumScaleFactor(0.4)
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
            LabeledContent("Parties jouées", value: BrainStats.number(stats.plays))
        } header: {
            Text(stats.name)
        }
    }

    private func streakText(_ days: Int) -> String {
        days <= 0 ? "Aucune" : "\(BrainStats.number(days)) jour\(days > 1 ? "s" : "")"
    }

    // MARK: Domaines

    private struct DomainBar: Identifiable {
        let domain: BrainCatalog.Domain
        let index: Int
        var id: String { domain.id }
        /// Longueur de la barre, dans l'échelle 0–2000 du graphique (une valeur hors bornes ne déborde pas).
        var plotted: Int { min(max(index, 0), Int(BrainCompareSection.maxIndex)) }
    }

    private func bars(_ stats: BrainStats) -> [DomainBar] {
        catalog.domains.map { DomainBar(domain: $0, index: stats.domains[$0.id]?.index ?? 0) }
    }

    private func domains(_ stats: BrainStats) -> some View {
        Section {
            // Lignes plutôt qu'un graphique Charts : à hauteur fixe, le plus grand texte faisait chevaucher libellés
            // et barres, et la valeur d'une barre pleine (≈ 2 000 °M) était coupée au bord droit.
            VStack(spacing: 10) {
                ForEach(bars(stats)) { bar in BrainDomainRow(icon: bar.domain.icon, label: bar.domain.label, index: bar.index, color: Color(hex: bar.domain.hex) ?? Palette.accent) }
            }
            .padding(.vertical, 6)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(bars(stats).map { "\($0.domain.label) \(BrainStats.number($0.index)) degrés M" }.joined(separator: ", "))
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
                    // 4 dates au plus : avec un an d'historique, une marque par semaine se chevauchait (52 dates).
                    AxisMarks(values: .automatic(desiredCount: typeSize.isAccessibilitySize ? 2 : 4)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.day().month(.abbreviated), centered: false)
                    }
                }
                .environment(\.locale, Locale(identifier: "fr_CH"))
                .frame(height: curveHeight)
                .padding(.vertical, 6)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Évolution de ta Température sur \(days.count) jours, aujourd'hui \(BrainStats.number(days.last?.temperature ?? 0)) degrés M")
            } header: {
                Text("Évolution (\(days.count) jours)")
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
                Text("\(BrainStats.number(value)) %").font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
            }
            ProgressView(value: Double(min(max(value, 0), 100)), total: 100).tint(tint)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Jeux

    private func games(_ stats: BrainStats) -> some View {
        Section {
            ForEach(stats.playedGames, id: \.id) { row in
                let domain = catalog.domain(catalog.game(row.id)?.domain ?? "")
                rowLayout {
                    if !typeSize.isAccessibilitySize { Text(domain.icon).font(.title3) }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(catalog.game(row.id)?.name ?? row.id).font(.subheadline.weight(.semibold))
                        Text(detail(row.game))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    if !typeSize.isAccessibilitySize { Spacer() }
                    Text(BrainStats.degrees(row.game.index)).font(.subheadline.monospacedDigit().weight(.semibold))
                }
                .accessibilityElement(children: .combine)
            }
        } header: {
            Text("Tes jeux")
        }
    }

    /// Ligne en colonne avec un texte très grand : côte à côte, nom et chiffres étaient coupés syllabe par syllabe.
    private var rowLayout: AnyLayout {
        typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4)) : AnyLayout(HStackLayout(spacing: 12))
    }

    /// « Niveau 12 · palier 3 · record 12 450 · 7 parties » (palier affiché dès le 2e, comme la page).
    private func detail(_ game: BrainStats.Game) -> String {
        let tier = game.maxTier > 1 ? " · palier \(BrainStats.number(game.maxTier))" : ""
        let plays = "\(BrainStats.number(game.plays)) partie\(game.plays > 1 ? "s" : "")"
        return "Niveau \(BrainStats.number(game.lastLevel))\(tier) · record \(BrainStats.number(game.best)) · \(plays)"
    }

    // MARK: Classement

    @ViewBuilder
    private var board: some View {
        if let board = store.brainBoard, !board.board.isEmpty {
            Section {
                ForEach(board.board) { player in
                    rowLayout {
                        Text("\(board.rank(of: player))").font(.subheadline.monospacedDigit().weight(.bold))
                            .foregroundStyle(.secondary).frame(minWidth: 24, alignment: .leading)
                        Text(player.me ? "\(player.name) (toi)" : player.name)
                            .font(.subheadline.weight(player.me ? .bold : .regular))
                        if !typeSize.isAccessibilitySize { Spacer() }
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
                    Text("Tu es \(rank == 1 ? "1er" : "\(BrainStats.number(rank))e") sur \(BrainStats.number(board.players)) joueur\(board.players > 1 ? "s" : "").")
                }
            }
        }
    }
}

/// Un domaine : libellé, barre (0–2 000 °M, valeur hors bornes ramenée) et valeur, jamais tronqués.
/// Texte très grand (tailles d'accessibilité) : libellé au-dessus de la barre.
private struct BrainDomainRow: View {
    let icon: String
    let label: String
    let index: Int
    let color: Color
    @Environment(\.dynamicTypeSize) private var typeSize
    @ScaledMetric(relativeTo: .subheadline) private var labelWidth: CGFloat = 122

    var body: some View {
        let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4))
            : AnyLayout(HStackLayout(spacing: 10))
        layout {
            // Largeur commune : toutes les barres partent du même bord.
            HStack(spacing: 6) {
                Text(icon)
                Text(label).lineLimit(1).minimumScaleFactor(0.8)
            }
            .font(.subheadline)
            .frame(width: typeSize.isAccessibilitySize ? nil : labelWidth, alignment: .leading)
            HStack(spacing: 8) {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.primary.opacity(0.08))
                        Capsule().fill(color).frame(width: geo.size.width * CGFloat(BrainCompareSection.ratio(index)))
                    }
                }
                .frame(height: 10)
                Text(index > 0 ? BrainStats.degrees(index) : "—").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    .lineLimit(1).fixedSize()
            }
        }
    }
}
