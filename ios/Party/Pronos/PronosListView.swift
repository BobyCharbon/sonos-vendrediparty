import SwiftUI

/// Couleurs des Pronos (maquette du 17.11) : lavande des réponses cachées, citron des gagnants.
enum PronoLook {
    static let lavender = Color(hex: 0xB9A7FF)
    static let lemon = Color(hex: 0xFFE27A)
    static let mint = Color(hex: 0x5BE3A6)
    static let coral = Color(hex: 0xFFB347)
    static let accent = Color(hex: 0xFF4F9A)
    static let action = Color(hex: 0xD92A73)
    static let surface = Color(hex: 0x221A3D)
    static let surface2 = Color(hex: 0x2C2350)
}

/// Visages qui se chevauchent (qui a joué, les gagnants).
struct PronoFaces: View {
    let faces: [PronoFace]
    var size: CGFloat = 26

    var body: some View {
        HStack(spacing: -size * 0.3) {
            ForEach(faces) { f in
                Initials(name: f.name, photo: f.photo, size: size)
                    .overlay(Circle().stroke(AppConfig.background, lineWidth: 2))
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(faces.map(\.label).joined(separator: ", "))
    }
}

struct PronoChip: View {
    let text: String
    let tone: Color
    var filled = false

    var body: some View {
        Text(text)
            .font(.caption.weight(.bold))
            .foregroundStyle(filled ? .white : tone)
            .padding(.horizontal, 9).padding(.vertical, 4)
            .background(filled ? AnyShapeStyle(PronoLook.action) : AnyShapeStyle(tone.opacity(0.16)), in: Capsule())
    }
}

/// Carte d'un prono dans une liste.
struct PronoCardRow: View {
    let card: PronoCard
    var showPlace = true

    private var chip: (String, Color, Bool) {
        switch card.state {
        case "open": return card.answered ? ("🔒 Réponse cachée · tu as joué", PronoLook.lavender, false) : ("🔮 À toi de jouer", PronoLook.accent, true)
        case "closed": return (card.mine ? "⏳ Donne le résultat" : "⏳ Résultat attendu", PronoLook.coral, false)
        case "done": return (card.won ? "🏆 Tu avais vu juste" : "🏆 Terminé", PronoLook.mint, false)
        default: return ("Annulé", .secondary, false)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                PronoChip(text: chip.0, tone: chip.1, filled: chip.2)
                Spacer()
                Text(PronoFormat.stateLine(state: card.state, closesAt: card.closesAt, revealed: card.revealed))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text(card.question).font(.headline).foregroundStyle(.primary).multilineTextAlignment(.leading)
            if showPlace {
                Text("\(PronoFormat.place(group: card.group, event: card.event, creator: card.creator)) · \(PronoFormat.points(card.points))")
                    .font(.footnote).foregroundStyle(.secondary).lineLimit(1)
            }
            if card.state == "done" {
                if let winners = card.winners, !winners.isEmpty {
                    HStack(spacing: 10) {
                        PronoFaces(faces: winners)
                        Text(winners.count == 1 ? "\(winners[0].label) · +\(card.points)" : "\(card.winnersCount ?? winners.count) gagnants · +\(card.points)")
                            .font(.footnote.weight(.semibold))
                    }
                } else {
                    Text("Personne n'avait vu juste.").font(.footnote).foregroundStyle(.secondary)
                }
            } else {
                HStack(spacing: 10) {
                    if !card.faces.isEmpty { PronoFaces(faces: card.faces) }
                    Text("\(card.answeredCount) sur \(card.players) ont joué").font(.footnote).foregroundStyle(.secondary)
                }
                if card.state == "open" {
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(.white.opacity(0.07))
                            Capsule().fill(LinearGradient(colors: [PronoLook.lavender, PronoLook.accent], startPoint: .leading, endPoint: .trailing))
                                .frame(width: geo.size.width * min(1, Double(card.answeredCount) / Double(max(1, card.players))))
                        }
                    }
                    .frame(height: 6)
                }
            }
        }
        .padding(14)
        .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
            .stroke(card.state == "open" && !card.answered ? PronoLook.accent.opacity(0.55) : .white.opacity(0.06), lineWidth: 1))
        .accessibilityElement(children: .combine)
    }
}

/// App « Pronos » (Réglages › Autres apps) et pronos d'un groupe : la liste, « ＋ Nouveau », et pour un groupe le classement.
struct PronosListView: View {
    @ObservedObject var store: PronosStore
    var group: String?
    var groupName: String?
    @State private var cards: [PronoCard]?
    @State private var board: PronoBoard?
    @State private var error: String?
    @State private var tab = 0
    @State private var creating = false
    @State private var opened: String?

    var body: some View {
        ScrollView { content }
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(group == nil ? "Pronos" : "🔮 Pronos")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { Haptics.tap(); creating = true } label: { Label("Nouveau prono", systemImage: "plus") }
                    .accessibilityIdentifier("pronos-new")
            }
        }
        .refreshable { await load() }
        .task { await load() }
        .navigationDestination(isPresented: $creating) {
            PronoNewView(store: store, group: group, event: nil) { id in
                creating = false
                opened = id
                Task { await load() }
            }
        }
        .navigationDestination(isPresented: openedBinding) {
            if let opened { PronoDetailView(store: store, id: opened) }
        }
    }

    private var openedBinding: Binding<Bool> {
        Binding(get: { opened != nil }, set: { if !$0 { opened = nil; Task { await load() } } })
    }

    private var content: some View {
            VStack(alignment: .leading, spacing: 12) {
                if group != nil {
                    Picker("Vue", selection: $tab) {
                        Text("Pronos").tag(0)
                        Text("Classement").tag(1)
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("pronos-tabs")
                }
                if let error { Text(error).foregroundStyle(.red).font(.footnote) }
                if tab == 1, let board {
                    PronoBoardView(board: board, store: store, group: group ?? "") { await load() }
                } else if let cards {
                    if cards.isEmpty {
                        empty
                    } else if group != nil {
                        cardList(cards)
                    } else {
                        section("À FAIRE", cards.filter(\.todo))
                        section("EN COURS", cards.filter { !$0.todo && ($0.state == "open" || $0.state == "closed") })
                        section("TERMINÉS", cards.filter { $0.state == "done" || $0.state == "cancelled" })
                    }
                    honour
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
                }
            }
            .padding(16)
            .motion(Motion.smooth, value: cards?.count)
    }

    private func cardList(_ list: [PronoCard]) -> some View {
        ForEach(list) { (card: PronoCard) in
            cardButton(card)
        }
    }

    private func cardButton(_ card: PronoCard) -> some View {
        let place = group == nil
        return Button {
            Haptics.tap()
            opened = card.id
        } label: {
            PronoCardRow(card: card, showPlace: place)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("prono-card-" + card.id)
        .transition(.cardInsert)
    }

    @ViewBuilder
    private func section(_ title: String, _ list: [PronoCard]) -> some View {
        if !list.isEmpty {
            Text("\(title) · \(list.count)").font(.footnote.weight(.bold)).foregroundStyle(.secondary).padding(.top, 6)
            cardList(list)
        }
    }

    private var empty: some View {
        VStack(spacing: 8) {
            Text("🔮").font(.system(size: 44))
            Text(group == nil ? "Aucun prono pour l'instant" : "Aucun prono dans ce groupe").font(.headline)
            Text("« Qui arrive en dernier ? », « Le score du match ? »… Les réponses restent cachées jusqu'au dévoilement.")
                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Button { creating = true } label: { Text("Lancer un prono").bold().frame(maxWidth: .infinity) }
                .buttonStyle(.borderedProminent).tint(PronoLook.action).padding(.top, 6)
        }
        .padding(24)
        .frame(maxWidth: .infinity)
        .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var honour: some View {
        PronoHonour(points: nil).padding(.top, 8)
    }

    private func load() async {
        do {
            var args: [String: Any] = [:]
            if let group { args["group_id"] = group }
            let list: [PronoCard] = try await store.call("prono_list", args)
            Motion.animate(Motion.smooth) { cards = list }
            if let group { board = try await store.call("prono_board", ["group_id": group]) }
            error = nil
            await store.refreshBadge()
        } catch {
            self.error = PronosStore.message(error)
            if cards == nil { cards = [] }
        }
    }
}

/// « Pour l'honneur » (revue de conformité) : aucun argent, aucune mise, aucun lot.
struct PronoHonour: View {
    let points: Int?

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Text("🏅")
            (Text("Pour l'honneur. ").bold().foregroundColor(.primary)
             + Text(points.map { "Une bonne réponse = \(PronoFormat.points($0)) au classement du groupe. " } ?? "Des points au classement du groupe, rien d'autre. ")
             + Text("Aucun argent, aucune mise, aucun lot."))
                .font(.footnote).foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(PronoLook.mint.opacity(0.09), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(PronoLook.mint.opacity(0.3), lineWidth: 1))
    }
}

/// Classement du groupe : podium des trois premiers puis la liste, aux points seulement.
struct PronoBoardView: View {
    let board: PronoBoard
    @ObservedObject var store: PronosStore
    let group: String
    let reload: () async -> Void
    @State private var confirmReset = false
    @State private var appeared = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(board.since.map { "Depuis le \(PronoFormat.short($0))" } ?? "Depuis le début") · \(board.pronos) prono\(board.pronos > 1 ? "s" : "")")
                .font(.footnote).foregroundStyle(.secondary)
            if board.rows.isEmpty {
                VStack(spacing: 6) {
                    Text("🏅").font(.system(size: 36))
                    Text("Pas encore de points").font(.headline)
                    Text("Le classement se remplit à chaque résultat donné.").font(.footnote).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity).padding(24)
                .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else {
                podium
                ForEach(Array(board.rows.enumerated()), id: \.element.id) { i, row in
                    HStack(spacing: 12) {
                        Text("\(i + 1)").font(.headline).foregroundStyle(.secondary).frame(width: 22)
                        Initials(name: row.user.name, photo: row.user.photo, size: 34)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(row.user.label).font(.body.weight(.semibold))
                            Text("\(row.right) sur \(row.played)").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text("\(row.points)").font(.headline).foregroundStyle(PronoLook.lemon)
                    }
                    .padding(10)
                    .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(row.user.me == true ? PronoLook.accent : .clear, lineWidth: 1.5))
                    .accessibilityElement(children: .combine)
                }
                if board.manage {
                    Button(role: .destructive) { confirmReset = true } label: { Text("Remettre le classement à zéro").frame(maxWidth: .infinity) }
                        .buttonStyle(.bordered)
                        .confirmationDialog("Repartir de zéro ?", isPresented: $confirmReset, titleVisibility: .visible) {
                            Button("Oui, repartir de zéro", role: .destructive) {
                                Task { try? await store.run("prono_board_reset", ["group_id": group]); await reload() }
                            }
                        } message: { Text("Les points de tout le groupe repartent de zéro. Les pronos restent.") }
                }
            }
        }
        .onAppear { Motion.animate(Motion.bouncy) { appeared = true } }
    }

    private var podium: some View {
        let top = [board.rows.count > 1 ? board.rows[1] : nil, board.rows.first, board.rows.count > 2 ? board.rows[2] : nil]
        let heights: [CGFloat] = [70, 96, 54]
        let places = [2, 1, 3]
        let fills: [[Color]] = [[Color(hex: 0xE8E4F5), Color(hex: 0xB1A8CF)], [Color(hex: 0xFFEA9C), Color(hex: 0xFFB347)], [Color(hex: 0xFFC2A8), Color(hex: 0xFF7A59)]]
        return HStack(alignment: .bottom, spacing: 10) {
            ForEach(0..<3, id: \.self) { i in
                VStack(spacing: 6) {
                    if let row = top[i] {
                        Initials(name: row.user.name, photo: row.user.photo, size: 50)
                            .overlay(Circle().stroke(places[i] == 1 ? PronoLook.lemon : .clear, lineWidth: 3))
                            .shadow(color: places[i] == 1 ? PronoLook.lemon.opacity(0.6) : .clear, radius: 10)
                        Text(row.user.label + (places[i] == 1 ? " 👑" : "")).font(.caption.weight(.bold)).lineLimit(1)
                        Text("\(places[i])").font(.title.weight(.heavy)).foregroundStyle(AppConfig.background)
                            .frame(width: 92, height: appeared ? heights[i] : 0)
                            .background(LinearGradient(colors: fills[i], startPoint: .top, endPoint: .bottom),
                                        in: UnevenRoundedRectangle(topLeadingRadius: 14, bottomLeadingRadius: 4, bottomTrailingRadius: 4, topTrailingRadius: 14))
                            .clipped()
                    } else {
                        Color.clear.frame(width: 92, height: 1)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .accessibilityHidden(true)
    }
}

/// Pronos ouverts par la page web (PartyNative.pronos) ou une notification : liste, prono ou création, par-dessus la page.
struct PronoRouteView: View {
    @ObservedObject var store: PronosStore
    @State var route: PronoRoute
    let close: () -> Void

    var body: some View {
        NavigationStack {
            Group {
                switch route {
                case .list(let group): PronosListView(store: store, group: group)
                case .open(let id): PronoDetailView(store: store, id: id)
                case .create(let group, let event):
                    PronoNewView(store: store, group: group, event: event) { id in Motion.animate(Motion.smooth) { route = .open(id) } }
                }
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { close() } label: { Image(systemName: "xmark").font(.body.weight(.semibold)) }
                        .accessibilityLabel("Fermer les pronos")
                        .accessibilityIdentifier("pronos-close")
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
