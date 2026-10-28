import SwiftUI

/// Onglet « Ton avis » natif : même contenu que la page web (index.html, section data-view="feedback").
struct FeedbackView: View {
    @ObservedObject var store: FeedbackStore
    let topInset: CGFloat
    /// Hôte seulement : rouvre « Retours » dans la page (états, réponses, envoi à Claude).
    var manage: (() -> Void)?

    @FocusState private var writing: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                form
                mine
            }
            .padding(.horizontal, 16)
            .padding(.top, topInset + 8)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .refreshable { await store.appear() }
        .background(AppConfig.background.ignoresSafeArea())
        .overlay(alignment: .bottom) { noticeBanner }
        .task { await store.appear() }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Ton avis").font(.largeTitle.weight(.heavy))
                Text("Une idée, un bug ? Dis ce que tu aimerais voir changer, ajouter ou corriger. L'organisateur lit chaque message.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            if let manage {
                Button(action: manage) {
                    Label("Gérer les retours", systemImage: "tray.full")
                }
                .buttonStyle(.bordered)
                .tint(Palette.accent)
                .accessibilityHint("Ouvre la gestion des retours ; « Vue invité » pour revenir")
            }
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

            HStack {
                Text("\(store.text.count) / \(FeedbackRules.maximumLength)")
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                Spacer()
                Button {
                    writing = false
                    Task { await store.send() }
                } label: {
                    if store.sending { ProgressView() } else { Text("Envoyer").bold() }
                }
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
                .accessibilityElement(children: .combine)
                .accessibilityHint(isNew ? "Nouvelle réponse" : "")
            }
        } else if !store.loaded {
            ProgressView().frame(maxWidth: .infinity)
        }
    }

    @ViewBuilder
    private var noticeBanner: some View {
        if let notice = store.notice {
            Text(notice.text)
                .font(.subheadline.weight(.semibold))
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(notice.isError ? Color.red.opacity(0.9) : Palette.card, in: Capsule())
                .padding(.bottom, 12)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .task(id: notice) {
                    try? await Task.sleep(for: .seconds(3))
                    withAnimation { store.notice = nil }
                }
        }
    }
}
