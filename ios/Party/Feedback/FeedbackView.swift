import SwiftUI

/// Onglet « Ton avis » natif : même contenu que la page web (index.html, section data-view="feedback").
struct FeedbackView: View {
    @ObservedObject var store: FeedbackStore
    let topInset: CGFloat
    /// Hôte seulement : les retours reçus (états, réponses, envoi à Claude), à côté de « Mon avis ».
    var admin: FeedbackAdminStore?

    @FocusState private var writing: Bool
    @State private var part: Part = .received

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
                        form.transition(.opacity)
                        mine
                    }
                } else {
                    form
                    mine
                }
            }
            // Retours reçus ↔ Mon avis : fondu enchaîné ; avis envoyé ou réponse reçue : la liste s'écarte.
            .motion(Motion.smooth, value: part)
            .motion(Motion.snappy, value: store.items.map { "\($0.id)|\($0.status)|\($0.reply)" })
            .motion(Motion.smooth, value: store.loaded)
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
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
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
                Text(FeedbackRules.counter(store.trimmedText.count, minimum: store.minimumLength))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                Spacer()
                Button {
                    writing = false
                    Haptics.tap()
                    Task {
                        if let admin { await store.sendAsAdmin(admin) } else { await store.send() }
                    }
                } label: {
                    if store.sending { ProgressView().transition(.opacity) } else { Text("Envoyer").bold().transition(.opacity) }
                }
                .motion(Motion.snappy, value: store.sending)
                .buttonStyle(.borderedProminent)
                .tint(Palette.accent)
                .disabled(!store.canSend)
            }
        }
        .card()
    }

    @ViewBuilder
    private var mine: some View {
        if !store.items.isEmpty {
            Text("Mes retours").font(.title3.weight(.bold)).padding(.top, 4)
            ForEach(store.items) { item in
                let isNew = store.highlighted.contains(item.id)
                VStack(alignment: .leading, spacing: 6) {
                    Text(item.text)
                    Text("\(FeedbackKind.label(for: item.kind)) · \(item.date.formatted(.dateTime.day().month(.abbreviated))) · \(FeedbackStatus.label(for: item.status))")
                        .font(.caption).foregroundStyle(.secondary)
                    if !item.reply.isEmpty {
                        Label(item.reply, systemImage: "arrowshape.turn.up.left.fill").foregroundStyle(Palette.accent)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(isNew ? Palette.mine : Palette.card)
                .motionTransition()
                .accessibilityElement(children: .combine)
                .accessibilityHint(isNew ? "Nouvelle réponse" : "")
            }
        } else if !store.loaded {
            ProgressView().frame(maxWidth: .infinity).transition(.opacity)
        }

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
