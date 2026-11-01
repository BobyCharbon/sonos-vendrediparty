import SwiftUI
import UIKit

/// Retours reçus (hôte) : filtre, statuts, instructions pour Claude, mot pour l'invité. Session d'hôte (cookie).
@MainActor
final class FeedbackAdminStore: ObservableObject {
    @Published private(set) var payload: AdminFeedback?
    @Published private(set) var error: String?
    @Published private(set) var busy: Set<String> = []
    @Published var filter: AdminFeedback.Filter = .new
    /// Tri gardé d'une ouverture à l'autre.
    @Published var sort: AdminFeedback.Sort = AdminFeedback.Sort(rawValue: UserDefaults.standard.string(forKey: "feedbackSort") ?? "") ?? .recent {
        didSet { UserDefaults.standard.set(sort.rawValue, forKey: "feedbackSort") }
    }
    @Published var notice: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

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
        if action == "declined" && reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            notice = "Écris d'abord un mot pour l'invité : il verra pourquoi ce n'est pas retenu"
            return false
        }
        let done = await run(item.id) {
            payload = try await api.adminFeedbackAction(item.id, action, reply: reply.trimmingCharacters(in: .whitespacesAndNewlines))
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

    @discardableResult
    func saveNote(_ item: AdminFeedback.Item, _ note: String) async -> Bool {
        guard note != item.note else { return true }
        return await run(item.id) { payload = try await api.adminFeedbackAction(item.id, "note", note: note) }
    }

    func copyPrompt(_ item: AdminFeedback.Item, note: String) async {
        guard await saveNote(item, note) else { return }
        await run(item.id) {
            UIPasteboard.general.string = try await api.adminFeedbackPrompt(item.id)
            notice = "📋 Prompt copié"
        }
    }

    @discardableResult
    func sendToClaude(_ item: AdminFeedback.Item, note: String) async -> Bool {
        guard await saveNote(item, note) else { return false }
        let done = await run(item.id) { payload = try await api.adminFeedbackToClaude(item.id) }
        if done { notice = "🤖 Envoyé à Claude : suis-le dans « En cours »" }
        return done
    }

    func setPriority(_ item: AdminFeedback.Item, _ priority: String) async {
        await run(item.id) { payload = try await api.adminFeedbackPriority(item.id, priority) }
    }

    func item(_ id: String) -> AdminFeedback.Item? { payload?.items.first { $0.id == id } }

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

/// Liste des retours reçus, filtrée par état.
struct FeedbackAdminSection: View {
    @ObservedObject var store: FeedbackAdminStore
    @State private var editing: AdminFeedback.Item?
    @State private var deleting: AdminFeedback.Item?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Filtrer", selection: $store.filter) {
                ForEach(AdminFeedback.Filter.allCases) { filter in
                    let n = store.payload?.count(filter) ?? 0
                    Text(n > 0 && filter != .finished && filter != .all ? "\(filter.label) \(n)" : filter.label).tag(filter)
                }
            }
            .pickerStyle(.menu)
            .tint(Palette.accent)
            Picker("Trier", selection: $store.sort) {
                ForEach(AdminFeedback.Sort.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            if let payload = store.payload {
                let shown = payload.shown(store.filter, sort: store.sort)
                if shown.isEmpty {
                    Text(store.filter.empty).foregroundStyle(.secondary).frame(maxWidth: .infinity).card()
                }
                ForEach(shown) { item in row(item, payload: payload) }
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
        .sheet(item: $editing) { item in
            FeedbackEditor(store: store, itemID: item.id)
        }
        .confirmationDialog("Supprimer ce retour ?", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }),
                            titleVisibility: .visible) {
            Button("Supprimer", role: .destructive) {
                guard let item = deleting else { return }
                Task { await store.set(item, "delete") }
            }
        }
    }

    private func row(_ item: AdminFeedback.Item, payload: AdminFeedback) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if !item.priority.isEmpty {
                Text(item.priorityLabel).font(.caption.weight(.heavy))
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(Color.white.opacity(0.1), in: Capsule())
            }
            Text(item.text)
            HStack(spacing: 6) {
                Text("\(payload.meta(item)) · \(item.statusLabel)").font(.caption).foregroundStyle(.secondary)
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
            actions(item)
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
                Button("↩︎ Pas corrigé") { Task { await store.set(item, "new") } }.buttonStyle(.bordered)
            }
            .controlSize(.small)
        }
        .padding(8)
        .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 8))
    }

    private func actions(_ item: AdminFeedback.Item) -> some View {
        HStack(spacing: 8) {
            Button { editing = item } label: { Label("Modifier", systemImage: "pencil") }
                .buttonStyle(.bordered)
            Menu {
                if item.canStart { Button { Task { await store.set(item, "progress") } } label: { Label("En cours", systemImage: "wrench.and.screwdriver") } }
                if item.canVerify { Button { Task { await store.set(item, "verify") } } label: { Label("À vérifier", systemImage: "checklist") } }
                if item.canFinish {
                    Button { Task { await store.set(item, "done", reply: item.reply) } } label: { Label("Terminé (l'invité est averti)", systemImage: "checkmark.circle") }
                }
                if item.canReopen { Button { Task { await store.set(item, "new") } } label: { Label("Remettre à traiter", systemImage: "arrow.uturn.backward") } }
                Menu {
                    ForEach(AdminFeedback.priorities, id: \.id) { p in
                        Button { Task { await store.setPriority(item, p.id) } } label: {
                            if item.priority == p.id { Label(p.label, systemImage: "checkmark") } else { Text(p.label) }
                        }
                    }
                    if !item.priority.isEmpty { Button("Sans priorité") { Task { await store.setPriority(item, "") } } }
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
}

/// Un retour : instructions pour Claude (enregistrer, copier le prompt, envoyer), mot pour l'invité, fin.
private struct FeedbackEditor: View {
    @ObservedObject var store: FeedbackAdminStore
    let itemID: String
    @State private var note = ""
    @State private var reply = ""
    @State private var loaded = false
    @State private var confirmClaude = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                if let item = store.item(itemID) {
                    Section {
                        Text(item.text)
                        Text(store.payload?.meta(item) ?? "").font(.caption).foregroundStyle(.secondary)
                    }
                    Section {
                        TextField("Ex. : sur iPhone, le bouton Révéler reste grisé avec 2 joueurs ; il doit être actif dès qu'une personne a validé.",
                                  text: $note, axis: .vertical)
                            .lineLimit(3...10)
                            .onChange(of: note) { if $0.count > 2000 { note = String($0.prefix(2000)) } }
                        Button("Enregistrer") { Task { if await store.saveNote(item, note) { store.notice = "💾 Enregistré" } } }
                        Button("Copier le prompt") { Task { await store.copyPrompt(item, note: note) } }
                        Button("Envoyer à Claude") { confirmClaude = true }
                            .disabled(!(store.payload?.claudeReady ?? false) || item.claudePending
                                      || note.trimmingCharacters(in: .whitespacesAndNewlines).count < AdminFeedback.minimumNote)
                    } header: {
                        Text("Instructions pour Claude")
                    } footer: {
                        if store.payload?.claudeReady == false {
                            Text("GitHub n'est pas configuré sur le serveur : copie le prompt pour le donner à Claude toi-même.")
                        } else if item.claudePending {
                            Text("Déjà confié à Claude : la correction est en cours.")
                        } else {
                            Text("Claude corrige selon tes instructions (\(AdminFeedback.minimumNote) caractères au moins) et commite sur develop ; le retour passe ensuite « À vérifier ».")
                        }
                    }
                    Section {
                        TextField("Ex. : c'est corrigé, merci ! / Pas prévu pour l'instant, mais on garde l'idée.", text: $reply, axis: .vertical)
                            .lineLimit(2...6)
                            .onChange(of: reply) { if $0.count > 500 { reply = String($0.prefix(500)) } }
                        Button("✅ Terminé") { finish(item, "done") }
                        Button("🚫 Pas retenu") { finish(item, "declined") }
                            .disabled(reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    } header: {
                        Text("Mot pour l'invité")
                    } footer: {
                        Text("Affiché avec « Terminé » ou « Pas retenu » ; l'invité reçoit une notification.")
                    }
                }
            }
            .navigationTitle("Retour")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { dismiss() } }
            }
            .disabled(store.busy.contains(itemID))
            .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
            .onAppear {
                guard !loaded, let item = store.item(itemID) else { return }
                note = item.note
                reply = item.reply
                loaded = true
            }
            .confirmationDialog("Confier ce retour à Claude ?", isPresented: $confirmClaude, titleVisibility: .visible) {
                Button("Envoyer à Claude") {
                    guard let item = store.item(itemID) else { return }
                    Task { if await store.sendToClaude(item, note: note) { dismiss() } }
                }
            } message: {
                Text("Il corrigera selon tes instructions et commitera sur develop.")
            }
        }
    }

    private func finish(_ item: AdminFeedback.Item, _ action: String) {
        Task {
            guard await store.saveNote(item, note) else { return }
            if await store.set(item, action, reply: reply) { dismiss() }
        }
    }
}
