import SwiftUI

/// Champs de classement d'un avis (création, « Mon avis » de l'hôte, Modifier) : mêmes valeurs que la page.
struct FeedbackClassifyFields: View {
    @Binding var draft: FeedbackDraft
    let meta: FeedbackMeta
    /// Création : pas « Terminé » / « Pas retenu », et la zone peut suivre l'onglet.
    var creating = false

    var body: some View {
        Picker("Statut", selection: $draft.status) {
            ForEach(meta.manualStatuses.filter { !creating || !$0.adminOnly }) { status in
                Label(status.label, systemImage: status.symbol).tag(status.key)
            }
        }
        Picker("Priorité", selection: $draft.priority) {
            Text("Sans").tag("")
            ForEach(meta.priorities) { Text($0.label).tag($0.key) }
        }
        Picker("Zone", selection: $draft.area) {
            if creating { Text("Selon l'onglet").tag("") }
            ForEach(meta.areas) { Text($0.label).tag($0.key) }
        }
        Picker("Effort", selection: $draft.effort) {
            Text("Pas estimé").tag("")
            ForEach(meta.efforts) { Text($0.label).tag($0.key) }
        }
        ForEach(meta.platforms) { platform in
            Toggle(platform.label, isOn: Binding(
                get: { draft.platforms.contains(platform.key) },
                set: { on in if on { draft.platforms.insert(platform.key) } else { draft.platforms.remove(platform.key) } }))
        }
        TextField("Étiquettes (séparées par des virgules, \(meta.maxTags) max)", text: $draft.tags)
            .textInputAutocapitalization(.never)
    }
}

/// Un retour : classement, instructions pour Claude (enregistrer, copier le prompt, envoyer), mot pour l'invité,
/// fil admin ↔ Claude et historique.
struct FeedbackEditor: View {
    @ObservedObject var store: FeedbackAdminStore
    let itemID: String
    @State private var draft = FeedbackDraft()
    @State private var message = ""
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
                    Section("Classement") { FeedbackClassifyFields(draft: $draft, meta: store.meta) }
                    Section {
                        TextField("Avis liés (#id, virgules)", text: $draft.related)
                        TextField("Doublon de (#id)", text: $draft.duplicateOf)
                        TextField("Bloqué par (#id)", text: $draft.blockedBy)
                    } header: { Text("Liens") }
                    .textInputAutocapitalization(.never)
                    claude(item)
                    guestWord(item)
                    thread(item)
                    if !item.history.isEmpty { history(item) }
                }
            }
            .navigationTitle("Retour")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Enregistrer") {
                        guard let item = store.item(itemID) else { return }
                        Task { if await store.save(item, draft) { store.notice = "💾 Enregistré" } }
                    }
                }
            }
            .disabled(store.busy.contains(itemID))
            .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
            .onAppear {
                guard !loaded, let item = store.item(itemID) else { return }
                draft = FeedbackDraft(item)
                loaded = true
            }
            .confirmationDialog("Confier ce retour à Claude ?", isPresented: $confirmClaude, titleVisibility: .visible) {
                Button("Envoyer à Claude") {
                    guard let item = store.item(itemID) else { return }
                    Task { if await store.sendToClaude(item, draft: draft) { dismiss() } }
                }
            } message: {
                Text("Il corrigera selon tes instructions et commitera sur develop.")
            }
        }
    }

    private func claude(_ item: AdminFeedback.Item) -> some View {
        Section {
            TextField("Ex. : sur iPhone, le bouton Révéler reste grisé avec 2 joueurs ; il doit être actif dès qu'une personne a validé.",
                      text: $draft.note, axis: .vertical)
                .lineLimit(3...10)
                .onChange(of: draft.note) { if $0.count > 2000 { draft.note = String($0.prefix(2000)) } }
            Button("Copier le prompt") { Task { await store.copyPrompt(item, draft: draft) } }
            Button("Envoyer à Claude") { confirmClaude = true }
                .disabled(!(store.payload?.claudeReady ?? false) || item.claudePending
                          || draft.note.trimmingCharacters(in: .whitespacesAndNewlines).count < AdminFeedback.minimumNote)
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
    }

    private func guestWord(_ item: AdminFeedback.Item) -> some View {
        Section {
            TextField("Ex. : c'est corrigé, merci ! / Pas prévu pour l'instant, mais on garde l'idée.", text: $draft.reply, axis: .vertical)
                .lineLimit(2...6)
                .onChange(of: draft.reply) { if $0.count > 500 { draft.reply = String($0.prefix(500)) } }
            Button("✅ Terminé") { finish(item, "done") }
            Button("🚫 Pas retenu") { finish(item, "declined") }
                .disabled(draft.reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } header: {
            Text("Mot pour l'invité")
        } footer: {
            Text("Affiché avec « Terminé » ou « Pas retenu » ; l'invité reçoit une notification. Les autres statuts restent internes : il voit « Envoyé » ou « En cours ».")
        }
    }

    private func thread(_ item: AdminFeedback.Item) -> some View {
        Section {
            if item.comments.isEmpty {
                Text("Aucun message. Une question pour Claude, ou sa réponse, s'écrit ici.").foregroundStyle(.secondary)
            }
            ForEach(item.comments) { c in
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(c.author) · \(Date(timeIntervalSince1970: c.at).formatted(.dateTime.day().month(.abbreviated).hour().minute().locale(Locale(identifier: "fr_CH"))))")
                        .font(.caption.weight(.semibold)).foregroundStyle(c.by == "claude" ? Palette.accent : .secondary)
                    Text(c.text)
                }
            }
            TextField("Réponds à Claude ou pose une question…", text: $message, axis: .vertical)
                .lineLimit(1...6)
            Button("Envoyer le message") { Task { if await store.comment(item, message) { message = "" } } }
                .disabled(message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } header: { Text("Discussion avec Claude") }
    }

    private func history(_ item: AdminFeedback.Item) -> some View {
        Section {
            DisclosureGroup("Historique") {
                ForEach(Array(item.history.reversed().enumerated()), id: \.offset) { _, h in
                    Text(describe(h)).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func describe(_ h: AdminFeedback.Change) -> String {
        let when = Date(timeIntervalSince1970: h.at).formatted(.dateTime.day().month(.abbreviated).hour().minute().locale(Locale(identifier: "fr_CH")))
        let who = h.by == "claude" ? "Claude" : "Toi"
        let value = { (v: String?) in h.field == "status" ? store.meta.status(v ?? "").label : ((v ?? "").isEmpty ? "—" : v ?? "") }
        let change = h.field == "created" ? "créé (\(value(h.to)))"
            : (h.to != nil || h.from != nil) ? "\(h.field) : \(value(h.from)) → \(value(h.to))" : "\(h.field) modifié"
        return "\(when) · \(who) · \(change)"
    }

    private func finish(_ item: AdminFeedback.Item, _ action: String) {
        Task {
            var final = draft
            final.status = action
            if action == "declined" && final.reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                store.notice = "Écris d'abord un mot pour l'invité : il verra pourquoi ce n'est pas retenu"
                return
            }
            if await store.save(item, final) {
                store.notice = action == "done" ? "✅ Terminé : l'invité est averti" : "🚫 Pas retenu : l'invité voit ton mot"
                dismiss()
            }
        }
    }
}

/// « ＋ Nouvel avis » de l'hôte : texte, type et classement dès la création.
struct FeedbackCreator: View {
    @ObservedObject var store: FeedbackAdminStore
    @State private var kind: FeedbackKind = .idea
    @State private var text = ""
    @State private var draft = FeedbackDraft()
    @Environment(\.dismiss) private var dismiss

    private var trimmed: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Type", selection: $kind) { ForEach(FeedbackKind.allCases) { Text($0.label).tag($0) } }
                        .pickerStyle(.segmented)
                    TextField("Ton idée, le bug, ce qu'il faut retravailler…", text: $text, axis: .vertical)
                        .lineLimit(3...10)
                }
                Section("Classement") { FeedbackClassifyFields(draft: $draft, meta: store.meta, creating: true) }
                Section("Note / instructions pour Claude") {
                    TextField("Ce qu'il faut faire, ce qu'il reste à décider…", text: $draft.note, axis: .vertical).lineLimit(2...8)
                }
            }
            .navigationTitle("Nouvel avis")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Créer") {
                        Task { if await store.create(kind: kind.rawValue, text: trimmed, draft: draft) { dismiss() } }
                    }
                    .disabled(trimmed.count < FeedbackRules.adminMinimumLength || store.busy.contains("new"))
                }
            }
            .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        }
    }
}
