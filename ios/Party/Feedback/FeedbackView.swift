import SwiftUI

/// Onglet « Ton avis » natif : même contenu que la page web (index.html, section data-view="feedback").
struct FeedbackView: View {
    @ObservedObject var store: FeedbackStore
    let topInset: CGFloat
    /// Hôte seulement : les retours reçus (états, réponses, envoi à Claude), à côté de « Mon avis ».
    var admin: FeedbackAdminStore?
    /// Ouvert depuis Réglages (sorti de la barre d'onglets le 4.11 pour l'onglet Zicou) : « ‹ Réglages ».
    var back: (() -> Void)?

    @FocusState private var writing: Bool
    /// Dictée (même reconnaissance vocale que l'assistant des événements, AIEventStore.swift).
    @StateObject private var dictation = Dictation()
    @State private var dictationBase = ""
    @State private var dictatingExtra = false
    @State private var part: Part = .received
    @State private var editing: FeedbackItem?
    @State private var editText = ""
    @State private var editBusy = false
    @State private var editError: String?

    private enum Part: String, CaseIterable, Identifiable {
        case received, mine
        var id: String { rawValue }
        var label: String { self == .received ? "Retours reçus" : "Mon avis" }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                if let admin {
                    Picker("Partie", selection: $part) {
                        ForEach(Part.allCases) { Text($0.label).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    if part == .received {
                        FeedbackAdminSection(store: admin).transition(.opacity)
                    } else {
                        if store.aiStep == .none { form.transition(.opacity) } else { aiReview.transition(.opacity) }
                        aiRow
                        mine
                    }
                } else {
                    if store.aiStep == .none { form.transition(.opacity) } else { aiReview.transition(.opacity) }
                    aiRow
                    mine
                }
            }
            // Retours reçus ↔ Mon avis : fondu enchaîné ; avis envoyé ou réponse reçue : la liste s'écarte.
            .motion(Motion.smooth, value: part)
            .motion(Motion.snappy, value: store.items.map { "\($0.id)|\($0.status)|\($0.reply)" })
            .motion(Motion.smooth, value: store.loaded)
            .motion(Motion.smooth, value: store.aiStep)
            .onChange(of: part) { _ in Haptics.selection() }
            .padding(.horizontal, 16)
            .padding(.top, topInset + 8)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable {
            await store.appear()
            if part == .received { await admin?.load() }
        }
        .background(AppConfig.background.ignoresSafeArea())
        .overlay(alignment: .bottom) {
            if let admin { AdminNoticeHost(store: admin) }
            noticeBanner
        }
        .task {
            store.asAdmin = admin != nil
            await store.appear()
            await store.refreshAI()
        }
        .sheet(isPresented: $store.askingConsent, onDismiss: store.consentDismissed) { consentSheet }
        .sheet(item: $editing) { item in editSheet(item) }
        .onChange(of: dictation.text) { heard in
            guard dictation.listening else { return }
            let joined = [dictationBase, heard].filter { !$0.isEmpty }.joined(separator: " ")
            if dictatingExtra { store.aiExtra = joined } else { store.text = String(joined.prefix(FeedbackRules.maximumLength)) }
        }
        .onDisappear { dictation.finish() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let back {
                Button(action: back) {
                    Label("Réglages", systemImage: "chevron.left").font(.body.weight(.medium))
                }
                .tint(Palette.accent)
                .padding(.leading, -4)
                .accessibilityHint("Revient aux Réglages de l'app")
                .accessibilityIdentifier("feedback-back")
            }
            Text(admin == nil ? "Ton avis" : "Retours").font(.largeTitle.weight(.heavy))
            Text(admin == nil || part == .mine
                 ? "Une idée, un bug ? Dis ce que tu aimerais voir changer, ajouter ou corriger. L'organisateur lit chaque message."
                 : "Les idées et bugs envoyés par les invités : traite-les, confie-les à Claude, réponds-leur.")
                .font(.subheadline).foregroundStyle(.secondary)
        }
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Type de retour", selection: $store.kind) {
                ForEach(FeedbackKind.allCases) { kind in Text(kind.label).tag(kind) }
            }
            .pickerStyle(.segmented)

            micButton

            ZStack(alignment: .topLeading) {
                if store.text.isEmpty {
                    Text(store.kind.placeholder).foregroundStyle(.secondary).padding(.top, 8).padding(.leading, 5)
                }
                TextEditor(text: $store.text)
                    .focused($writing)
                    .frame(minHeight: 110)
                    .scrollContentBackground(.hidden)
                    .onChange(of: store.text) { new in
                        if new.count > FeedbackRules.maximumLength { store.text = String(new.prefix(FeedbackRules.maximumLength)) }
                    }
            }
            .padding(8)
            .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 12, style: .continuous))

            if let admin {  // hôte : son avis est classé dès l'envoi, comme « ＋ Nouvel avis »
                DisclosureGroup("Classement (statut, priorité, zone…)") {
                    VStack(alignment: .leading, spacing: 6) {
                        FeedbackClassifyFields(draft: $store.draft, meta: admin.meta, creating: true)
                        TextField("Note / instructions pour Claude", text: $store.draft.note, axis: .vertical).lineLimit(1...6)
                    }
                    .padding(.top, 6)
                }
                .tint(Palette.accent)
            }

            HStack {
                Text(FeedbackRules.counter(store.trimmedText.count, minimum: admin != nil && !store.aiReady ? store.minimumLength : store.counterMinimum))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                Spacer()
                Button {
                    writing = false
                    Haptics.tap()
                    Task {
                        // Hôte : avec l'IA, comme les invités ; sans elle, son avis classé d'office.
                        if let admin, !store.aiReady { await store.sendAsAdmin(admin) } else { await store.submit() }
                    }
                } label: {
                    if store.sending { ProgressView().transition(.opacity) } else { Text("Envoyer").bold().transition(.opacity) }
                }
                .motion(Motion.snappy, value: store.sending)
                .buttonStyle(.borderedProminent)
                .tint(Palette.accent)
                .disabled(admin != nil && !store.aiReady ? !store.canSend : !store.canSubmit)
            }
        }
        .card()
    }

    // MARK: IA (FeedbackAI.swift)

    /// Mode vocal mis en avant : on parle, puis on touche à nouveau pour envoyer (comme l'assistant des événements).
    private var micButton: some View {
        Button {
            Haptics.tap()
            toggleDictation(extra: false)
        } label: {
            Label(dictation.listening && !dictatingExtra ? "Je t'écoute… touche pour finir" : "Dis-le à voix haute",
                  systemImage: dictation.listening && !dictatingExtra ? "stop.circle.fill" : "mic.fill")
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: 44)
        }
        .buttonStyle(.borderedProminent)
        .tint(dictation.listening && !dictatingExtra ? .red : Palette.accent)
        .accessibilityIdentifier("feedback-mic")
    }

    private func toggleDictation(extra: Bool) {
        if dictation.listening {
            Task {
                _ = await dictation.stopAndCollect()
                if dictatingExtra { await store.sendExtra() } else if let admin, !store.aiReady { await store.sendAsAdmin(admin) } else { await store.submit() }
            }
            return
        }
        writing = false
        dictatingExtra = extra
        dictationBase = extra ? store.aiExtra.trimmingCharacters(in: .whitespaces) : store.trimmedText
        Task { await dictation.start() }
    }

    @ViewBuilder
    private var aiReview: some View {
        VStack(alignment: .leading, spacing: 12) {
            if store.aiStep == .loading {
                HStack(spacing: 10) { ProgressView(); Text("✨ L'IA met ton avis au propre…").foregroundStyle(.secondary) }
            } else if let draft = store.aiDraft {
                HStack(spacing: 6) {
                    ForEach([FeedbackAI.kinds[draft.kind], FeedbackAI.areas[draft.area]].compactMap { $0 }, id: \.self) {
                        Text($0).font(.caption.weight(.semibold)).padding(.horizontal, 8).padding(.vertical, 4)
                            .background(Color.white.opacity(0.08), in: Capsule())
                    }
                }
                Text(draft.title).font(.headline)
                Text(draft.description)
                ForEach(draft.rows, id: \.label) { row in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.label.uppercased()).font(.caption2.weight(.bold)).foregroundStyle(.secondary)
                        Text(row.text)
                    }
                }
            }
            switch store.aiStep {
            case .question(let question):
                Text(question).font(.headline).accessibilityIdentifier("feedback-ai-question")
                extraField(placeholder: "Ta réponse")
            case .correcting:
                extraField(placeholder: "Ce qui n'est pas juste, ou ce qui manque")
            case .ready:
                Text("C'est bien ça ?").font(.headline)
                Button { Task { await store.sendAI(useDraft: true) } } label: {
                    Text("Oui, envoyer").bold().frame(maxWidth: .infinity, minHeight: 36)
                }
                .buttonStyle(.borderedProminent).tint(Palette.accent).accessibilityIdentifier("feedback-ai-ok")
                Button { store.startCorrection() } label: { Text("Corriger").frame(maxWidth: .infinity, minHeight: 36) }
                    .buttonStyle(.bordered)
            default:
                EmptyView()
            }
            if store.aiStep != .loading {
                Button { Task { await store.sendAI(useDraft: false) } } label: {
                    Text("Envoyer mon texte tel quel").frame(maxWidth: .infinity, minHeight: 36)
                }
                .buttonStyle(.bordered)
                Button("Reprendre mon texte") { dictation.finish(); store.cancelAI() }
                    .frame(maxWidth: .infinity).tint(Palette.accent)
            }
        }
        .disabled(store.sending)
        .card()
    }

    private func extraField(placeholder: String) -> some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField(placeholder, text: $store.aiExtra, axis: .vertical)
                .lineLimit(1...4)
                .submitLabel(.send)
                .onSubmit { Task { await store.sendExtra() } }
                .padding(10)
                .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            Button { toggleDictation(extra: true) } label: {
                Image(systemName: dictation.listening && dictatingExtra ? "stop.circle.fill" : "mic.circle.fill").font(.title)
            }
            .tint(dictation.listening && dictatingExtra ? .red : Palette.accent)
            .accessibilityLabel(dictation.listening && dictatingExtra ? "Arrêter et envoyer" : "Dicter")
            Button { Task { await store.sendExtra() } } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                .tint(Palette.accent)
                .disabled(store.aiExtra.trimmingCharacters(in: .whitespaces).isEmpty)
                .accessibilityLabel("Reformuler")
        }
    }

    /// Accord : où en est la personne, et le retirer (ou le donner) ici, dans Réglages › Ton avis.
    @ViewBuilder
    private var aiRow: some View {
        if let ai = store.ai, ai.configured {
            HStack {
                Text(ai.accepted ? "✨ L'IA t'aide à écrire ton avis" : "✨ L'IA peut t'aider à écrire ton avis")
                    .font(.footnote).foregroundStyle(.secondary)
                Spacer()
                if ai.accepted {
                    Button("Retirer mon accord") { Task { await store.setConsent(false) } }.font(.footnote.weight(.semibold))
                } else if ai.consent == "declined" {
                    Button("Activer l'IA") { store.askingConsent = true }.font(.footnote.weight(.semibold))
                }
            }
            .tint(Palette.accent)
        }
    }

    private var consentSheet: some View {
        AIConsentSheet(copy: .feedback) { accept in Task { await store.answerConsent(accept) } }
    }

    @ViewBuilder
    private var mine: some View {
        if !store.items.isEmpty {
            Text("Mes retours").font(.title3.weight(.bold)).padding(.top, 4)
            ForEach(store.items) { item in
                let isNew = store.highlighted.contains(item.id)
                VStack(alignment: .leading, spacing: 6) {
                    // Le texte de l'avis lu d'un bloc ; « Modifier » reste un bouton à part (VoiceOver et toucher).
                    VStack(alignment: .leading, spacing: 6) {
                        Text(item.title ?? item.text)
                        if item.title != nil { Text(item.text).font(.subheadline).foregroundStyle(.secondary) }
                        Text("\(FeedbackKind.label(for: item.kind)) · \(item.date.formatted(.dateTime.day().month(.abbreviated))) · \(FeedbackStatus.label(for: item.status))"
                             + (item.editedDate.map { " · modifié le " + $0.formatted(.dateTime.day().month(.abbreviated).hour().minute()) } ?? ""))
                            .font(.caption).foregroundStyle(.secondary)
                        if !item.reply.isEmpty {
                            Label(item.reply, systemImage: "arrowshape.turn.up.left.fill").foregroundStyle(Palette.accent)
                        }
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityHint(isNew ? "Nouvelle réponse" : "")
                    if item.editable {
                        Button { editing = item; editText = item.text; editError = nil } label: { Label("Modifier", systemImage: "pencil") }
                            .font(.footnote.weight(.semibold)).tint(Palette.accent)
                            .accessibilityIdentifier("feedback-edit")
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(isNew ? Palette.mine : Palette.card)
                .motionTransition()
            }
        } else if !store.loaded {
            ProgressView().frame(maxWidth: .infinity).transition(.opacity)
        }

    }

    /// Modifier son avis : le texte entier, comme à l'envoi ; l'ancien reste dans la trace de l'avis (serveur).
    private func editSheet(_ item: FeedbackItem) -> some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 8) {
                TextEditor(text: $editText)
                    .padding(8)
                    .scrollContentBackground(.hidden)
                    .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                if let editError {
                    Label(editError, systemImage: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(.red)
                        .accessibilityIdentifier("feedback-edit-error")
                }
            }
            .padding()
                .navigationTitle("Modifier mon avis")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Annuler") { editing = nil } }
                    ToolbarItem(placement: .confirmationAction) {
                        if editBusy {
                            ProgressView()
                        } else {
                            Button("Enregistrer") {
                                let text = editText.trimmingCharacters(in: .whitespacesAndNewlines)
                                editBusy = true
                                editError = nil
                                Task {
                                    editError = await store.edit(item, text: text)
                                    editBusy = false
                                    if editError == nil { editing = nil }
                                }
                            }
                            .disabled(editText.trimmingCharacters(in: .whitespacesAndNewlines).count < FeedbackAI.minimumLength)
                        }
                    }
                }
        }
        .presentationDetents([.medium, .large])
    }

    private var noticeBanner: some View {
        NoticeBanner(notice: store.notice.map { NoticeBanner.Notice(text: $0.text, isError: $0.isError) }) { store.notice = nil }
    }

}

/// Bandeau des retours reçus (le store de l'hôte est observé à part).
private struct AdminNoticeHost: View {
    @ObservedObject var store: FeedbackAdminStore

    var body: some View { AdminNotice(notice: $store.notice) }
}
