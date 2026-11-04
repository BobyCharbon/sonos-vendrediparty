import SwiftUI
import UIKit

/// Retours reçus (hôte) : vues, filtres, tris, classement, instructions pour Claude, fil, mot pour l'invité.
/// Session d'hôte (cookie). Mêmes appels et mêmes mots que feedback-admin.js.
@MainActor
final class FeedbackAdminStore: ObservableObject {
    @Published private(set) var payload: AdminFeedback?
    @Published private(set) var error: String?
    @Published private(set) var busy: Set<String> = []
    @Published var view = "mine"
    @Published var filters = AdminFeedback.Filters()
    /// Tri et regroupement gardés d'une ouverture à l'autre.
    @Published var sort: AdminFeedback.Sort = AdminFeedback.Sort(rawValue: UserDefaults.standard.string(forKey: "feedbackSort") ?? "") ?? .recent {
        didSet { UserDefaults.standard.set(sort.rawValue, forKey: "feedbackSort") }
    }
    @Published var groupByArea = UserDefaults.standard.bool(forKey: "feedbackGroup") {
        didSet { UserDefaults.standard.set(groupByArea, forKey: "feedbackGroup") }
    }
    @Published var notice: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    var meta: FeedbackMeta { payload?.meta ?? .fallback }

    func load() async {
        do {
            payload = try await api.adminFeedback()
            error = nil
            web?.refreshFeedbackBadge()
        } catch {
            if payload == nil { self.error = HostMusicStore.message(error) } else { notice = HostMusicStore.message(error) }
        }
    }

    /// Statut ou suppression ; « Terminé » et « Pas retenu » emportent le mot pour l'invité (il est averti).
    @discardableResult
    func set(_ item: AdminFeedback.Item, _ action: String, reply: String = "") async -> Bool {
        let word = reply.trimmingCharacters(in: .whitespacesAndNewlines)
        if action == "declined" && word.isEmpty {
            notice = "Écris d'abord un mot pour l'invité : il verra pourquoi ce n'est pas retenu"
            return false
        }
        let done = await run(item.id) {
            if action == "delete" {
                payload = try await api.adminFeedbackAction(item.id, "delete")
            } else {
                var fields: [String: Any] = ["status": action]
                if !word.isEmpty { fields["reply"] = word }
                payload = try await api.adminFeedbackEdit([item.id], fields: fields)
            }
        }
        if done {
            switch action {
            case "done": notice = "✅ Terminé : l'invité est averti"
            case "declined": notice = "🚫 Pas retenu : l'invité voit ton mot"
            case "delete": notice = "Retour supprimé"
            default: break
            }
        }
        return done
    }

    /// Enregistre ce qui a changé dans le classement (un seul appel, historique côté serveur).
    @discardableResult
    func save(_ item: AdminFeedback.Item, _ draft: FeedbackDraft) async -> Bool {
        let changes = draft.changes(from: item, meta)
        guard !changes.isEmpty else { return true }
        return await run(item.id) { payload = try await api.adminFeedbackEdit([item.id], fields: changes) }
    }

    func comment(_ item: AdminFeedback.Item, _ text: String) async -> Bool {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return false }
        return await run(item.id) { payload = try await api.adminFeedbackComment(item.id, text: text) }
    }

    /// Avis écrit par l'hôte (« ＋ Nouvel avis » ou « Mon avis »), classé dès la création.
    func create(kind: String, text: String, draft: FeedbackDraft, tab: String? = nil) async -> Bool {
        let me = await web?.guestIdentity()
        let done = await run("new") {
            payload = try await api.adminFeedbackNew(kind: kind, text: text, name: me?.name ?? "", guestID: me?.id ?? "",
                                                     tab: tab, fields: draft.fields(meta, creating: true))
        }
        if done { notice = "＋ Avis créé" }
        return done
    }

    func copyPrompt(_ item: AdminFeedback.Item, draft: FeedbackDraft) async {
        guard await save(item, draft) else { return }
        await run(item.id) {
            UIPasteboard.general.string = try await api.adminFeedbackPrompt(item.id)
            notice = "📋 Prompt copié"
        }
    }

    @discardableResult
    func sendToClaude(_ item: AdminFeedback.Item, draft: FeedbackDraft) async -> Bool {
        guard await save(item, draft) else { return false }
        let done = await run(item.id) { payload = try await api.adminFeedbackToClaude(item.id) }
        if done { notice = "🤖 Envoyé à Claude : suis-le dans « Pour Claude »" }
        return done
    }

    func item(_ id: String) -> AdminFeedback.Item? { payload?.items.first { $0.id == id } }

    @discardableResult
    private func run(_ key: String, _ work: () async throws -> Void) async -> Bool {
        busy.insert(key)
        defer { busy.remove(key) }
        do {
            try await work()
            web?.refreshFeedbackBadge()
            return true
        } catch {
            notice = HostMusicStore.message(error)
            return false
        }
    }
}

/// Liste des retours reçus : vues rapides, filtres fins, tri, regroupement par zone, recherche.
struct FeedbackAdminSection: View {
    @ObservedObject var store: FeedbackAdminStore
    @State private var editing: AdminFeedback.Item?
    @State private var deleting: AdminFeedback.Item?
    @State private var creating = false
    @State private var showFilters = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Button { creating = true } label: { Label("Nouvel avis", systemImage: "plus") }
                    .buttonStyle(.borderedProminent).tint(Palette.accent)
                TextField("Rechercher (texte, #id, étiquette)", text: $store.filters.search)
                    .textFieldStyle(.roundedBorder)
                    .submitLabel(.search)
            }
            Picker("Vue", selection: $store.view) {
                ForEach(store.meta.views) { view in
                    let n = store.payload?.count(view: view.key) ?? 0
                    Text(n > 0 && !["finished", "all"].contains(view.key) ? "\(view.label) \(n)" : view.label).tag(view.key)
                }
            }
            .pickerStyle(.menu)
            .tint(Palette.accent)
            DisclosureGroup(isExpanded: $showFilters) {
                FeedbackFilters(store: store)
            } label: {
                Text(store.filters.isEmpty ? "Filtres et tri" : "Filtres et tri · actifs").font(.subheadline.weight(.semibold))
            }
            .tint(Palette.accent)
            if let payload = store.payload {
                list(payload)
            } else if let error = store.error {
                VStack(spacing: 10) {
                    Text(error).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    Button("Réessayer") { Task { await store.load() } }
                }
                .frame(maxWidth: .infinity).card()
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .task { await store.load() }
        .sheet(item: $editing) { item in FeedbackEditor(store: store, itemID: item.id) }
        .sheet(isPresented: $creating) { FeedbackCreator(store: store) }
        .confirmationDialog("Supprimer ce retour ?", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }),
                            titleVisibility: .visible) {
            Button("Supprimer", role: .destructive) {
                guard let item = deleting else { return }
                Task { await store.set(item, "delete") }
            }
        }
    }

    @ViewBuilder
    private func list(_ payload: AdminFeedback) -> some View {
        let shown = payload.shown(view: store.view, filters: store.filters, sort: store.sort)
        if shown.isEmpty {
            Text(store.view == "mine" ? "Rien à faire de ton côté pour l'instant 🎉" : "Aucun retour.")
                .foregroundStyle(.secondary).frame(maxWidth: .infinity).card()
        } else if store.groupByArea {
            ForEach(store.meta.areas) { area in
                let group = shown.filter { $0.area == area.key }
                if !group.isEmpty {
                    Text("\(area.label) · \(group.count)").font(.headline).padding(.top, 6)
                    ForEach(group) { row($0, payload: payload) }
                }
            }
        } else {
            ForEach(shown) { row($0, payload: payload) }
        }
    }

    private func row(_ item: AdminFeedback.Item, payload: AdminFeedback) -> some View {
        let meta = payload.meta
        return VStack(alignment: .leading, spacing: 8) {
            if !item.priority.isEmpty {
                Text(meta.label(meta.priorities, item.priority)).font(.caption.weight(.heavy))
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(Color.white.opacity(0.1), in: Capsule())
            }
            Text(item.text)
            HStack(spacing: 6) {
                Text(payload.meta(item)).font(.caption).foregroundStyle(.secondary)
                // Identifiant unique de l'avis : un toucher le copie, à donner à Claude (avis 73d690300d60).
                Button {
                    UIPasteboard.general.string = item.id
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                } label: {
                    Label("#\(item.id)", systemImage: "doc.on.doc").font(.caption2.monospaced())
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Color.white.opacity(0.08), in: Capsule())
                }
                .buttonStyle(.borderless)
                .accessibilityLabel("Copier l'identifiant \(item.id)")
            }
            FeedbackChips(item: item, meta: meta)
            if !item.note.isEmpty { Label(item.note, systemImage: "note.text").font(.footnote).foregroundStyle(.secondary) }
            if !item.reply.isEmpty {
                Label(item.reply, systemImage: "arrowshape.turn.up.left.fill").font(.footnote).foregroundStyle(Palette.accent)
            }
            if let claude = item.claude, let url = claude.url.flatMap(URL.init(string:)) {
                Link("\(claude.label) · #\(claude.number ?? 0)", destination: url).font(.footnote.weight(.semibold))
            }
            if item.status == "verify" { verify(item) }
            if item.claude?.state == "failed" {
                VStack(alignment: .leading, spacing: 4) {
                    Text("⚠️ Problème à corriger").font(.footnote.weight(.bold))
                    Text(item.claude?.error ?? "Raison en cours de récupération…").font(.caption.monospaced())
                    Text("Corrige la cause (réglage, instructions plus précises…), puis Modifier → Envoyer à Claude.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                .padding(8)
                .background(Color.orange.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
            }
            actions(item, meta: meta)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
        .disabled(store.busy.contains(item.id))
        .opacity(store.busy.contains(item.id) ? 0.6 : 1)
    }

    private func verify(_ item: AdminFeedback.Item) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("🧪 À vérifier").font(.footnote.weight(.bold))
            if let migrations = item.claude?.migrations, !migrations.isEmpty {
                Text("⚠️ Migration Supabase à appliquer d'abord : \(migrations.joined(separator: ", "))")
                    .font(.caption).foregroundStyle(.orange)
            }
            Text(item.claude?.state == "fixed"
                 ? "Claude a commité sa correction sur develop. Teste-la sur le site de test, puis :"
                 : "Vérifie que c'est bien corrigé, puis :")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("✅ Validé, c'est corrigé") { Task { await store.set(item, "done", reply: item.reply) } }
                    .buttonStyle(.borderedProminent)
                Button("↩︎ Pas corrigé") { Task { await store.set(item, "ready") } }.buttonStyle(.bordered)
            }
            .controlSize(.small)
        }
        .padding(8)
        .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
    }

    private func actions(_ item: AdminFeedback.Item, meta: FeedbackMeta) -> some View {
        HStack(spacing: 8) {
            Button { editing = item } label: { Label("Modifier", systemImage: "pencil") }
                .buttonStyle(.bordered)
            Menu {
                // « Pas retenu » demande un mot pour l'invité : dans Modifier.
                ForEach(meta.manualStatuses.filter { $0.key != "declined" && $0.key != item.status }) { status in
                    Button { Task { await store.set(item, status.key, reply: item.reply) } } label: {
                        Label(status.label, systemImage: status.symbol)
                    }
                }
                Menu {
                    ForEach(meta.priorities) { p in
                        Button { Task { await store.save(item, with(item) { $0.priority = p.key }) } } label: {
                            if item.priority == p.key { Label(p.label, systemImage: "checkmark") } else { Text(p.label) }
                        }
                    }
                    if !item.priority.isEmpty { Button("Sans priorité") { Task { await store.save(item, with(item) { $0.priority = "" }) } } }
                } label: { Label("Priorité", systemImage: "flag") }
                Button(role: .destructive) { deleting = item } label: { Label("Supprimer", systemImage: "trash") }
            } label: {
                Label("Statut", systemImage: "ellipsis.circle")
            }
            .buttonStyle(.bordered)
        }
        .controlSize(.small)
        .tint(Palette.accent)
    }

    private func with(_ item: AdminFeedback.Item, _ change: (inout FeedbackDraft) -> Void) -> FeedbackDraft {
        var draft = FeedbackDraft(item)
        change(&draft)
        return draft
    }
}

/// Filtres fins, tri et regroupement.
private struct FeedbackFilters: View {
    @ObservedObject var store: FeedbackAdminStore

    var body: some View {
        let meta = store.meta
        VStack(alignment: .leading, spacing: 4) {
            picker("Statut", $store.filters.status, meta.statuses.map { ($0.key, $0.title) })
            picker("Zone", $store.filters.area, meta.areas.map { ($0.key, $0.label) })
            picker("Plateforme", $store.filters.platform, meta.platforms.map { ($0.key, $0.label) })
            picker("Effort", $store.filters.effort, meta.efforts.map { ($0.key, $0.label) } + [("none", "Pas estimé")])
            picker("Priorité", $store.filters.priority, meta.priorities.map { ($0.key, $0.label) } + [("none", "Sans priorité")])
            picker("Étiquette", $store.filters.tag, (store.payload?.allTags ?? []).map { ($0, "#\($0)") })
            Picker("Tri", selection: $store.sort) {
                ForEach(AdminFeedback.Sort.allCases) { Text($0.label).tag($0) }
            }
            Toggle("Regrouper par zone", isOn: $store.groupByArea)
            if !store.filters.isEmpty {
                Button("Effacer les filtres") { store.filters = AdminFeedback.Filters() }
            }
        }
        .padding(.top, 6)
    }

    private func picker(_ title: String, _ value: Binding<String>, _ options: [(String, String)]) -> some View {
        Picker(title, selection: value) {
            Text("Tous").tag("")
            ForEach(options, id: \.0) { Text($0.1).tag($0.0) }
        }
    }
}

/// Pastilles d'un avis : statut (couleur et symbole du serveur), zone, plateformes, effort, étiquettes, fil, liens.
struct FeedbackChips: View {
    let item: AdminFeedback.Item
    let meta: FeedbackMeta

    var body: some View {
        let status = meta.status(item.status)
        let color = Color(hex: status.color) ?? .white
        FlowChips {
            Label(status.label, systemImage: status.symbol)
                .font(.caption.weight(.heavy)).foregroundStyle(color)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(color.opacity(0.15), in: Capsule())
                .overlay(Capsule().strokeBorder(color.opacity(0.45)))
            chip(meta.label(meta.areas, item.area))
            ForEach(item.platforms, id: \.self) { chip(meta.label(meta.platforms, $0)) }
            if !item.effort.isEmpty { chip(meta.label(meta.efforts, item.effort)) }
            ForEach(item.tags, id: \.self) { chip("#\($0)") }
            if !item.comments.isEmpty { chip("💬 \(item.comments.count)") }
            ForEach(item.related, id: \.self) { chip("🔗 #\($0)") }
            if !item.duplicateOf.isEmpty { chip("♊ doublon de #\(item.duplicateOf)") }
            if !item.blockedBy.isEmpty { chip("⛔ bloqué par #\(item.blockedBy)") }
        }
        .accessibilityElement(children: .combine)
    }

    private func chip(_ text: String) -> some View {
        Text(text).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Color.white.opacity(0.07), in: Capsule())
    }
}

/// Pastilles qui passent à la ligne.
private struct FlowChips: Layout {
    var spacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(proposal.width ?? .infinity, subviews)
        return CGSize(width: proposal.width ?? rows.width, height: rows.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX && x + size.width > bounds.maxX { x = bounds.minX; y += line + spacing; line = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            line = max(line, size.height)
        }
    }

    private func arrange(_ width: CGFloat, _ subviews: Subviews) -> (width: CGFloat, height: CGFloat) {
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width { y += line + spacing; x = 0; line = 0 }
            x += size.width + spacing
            line = max(line, size.height)
            widest = max(widest, x)
        }
        return (widest, y + line)
    }
}
