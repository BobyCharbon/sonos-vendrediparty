import SwiftUI

/// Rechercher dans la discussion d'un événement (event_chat_search : 50 résultats au plus, sans messages supprimés ni
/// de personnes bloquées). Un toucher sur un résultat ramène au message : store.jumpTo, puis fermeture.
/// onPick : fourni par les infos (ferme toute la feuille) ; sans lui, la vue pose jumpTo et se ferme elle-même.
struct EventChatSearchView: View {
    @ObservedObject var store: ChatsStore
    var onPick: ((String) -> Void)? = nil
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var results: [ChatSearchResult] = []
    @State private var searching = false
    @State private var searched = ""

    private var trimmed: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        List {
            if trimmed.count < 2 {
                hint("magnifyingglass", "Rechercher dans la discussion", "Un mot, un prénom, une adresse… au moins 2 lettres.")
            } else if results.isEmpty && !searching && searched == trimmed {
                hint("text.magnifyingglass", "Aucun message trouvé", "Rien pour « \(trimmed) ».")
            } else {
                Section {
                    ForEach(results) { result in
                        Button {
                            Haptics.tap()
                            pick(result.messageId)
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(result.authorName).font(.subheadline.weight(.semibold))
                                        .foregroundStyle(ChatTimeline.nameColor(for: result.authorName))
                                    Spacer()
                                    Text(ChatDates.short(result.at)).font(.caption).foregroundStyle(.secondary)
                                }
                                Text(Self.highlight(result.snippet, query: searched)).font(.subheadline).lineLimit(3)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityElement(children: .combine)
                        .accessibilityHint("Montre le message dans la discussion")
                        .motionTransition()
                    }
                } header: {
                    if !results.isEmpty {
                        Text(results.count >= 50 ? "50 messages ou plus" : "\(results.count) message\(results.count > 1 ? "s" : "")")
                    }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .overlay { if searching && results.isEmpty { ProgressView() } }
        .motion(Motion.smooth, value: results.map(\.messageId))
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Rechercher")
        .autocorrectionDisabled()
        .navigationTitle("Rechercher")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: trimmed) {
            guard trimmed.count >= 2 else { results = []; searched = ""; return }
            // Frappe en cours : on attend une courte pause avant d'interroger le serveur.
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            searching = true
            let q = trimmed
            let found = await store.search(q)
            guard !Task.isCancelled else { return }
            results = found
            searched = q
            searching = false
        }
    }

    private func pick(_ id: String) {
        if let onPick { onPick(id) } else {
            store.jumpTo = id
            dismiss()
        }
    }

    private func hint(_ icon: String, _ title: String, _ text: String) -> some View {
        Section {
            VStack(spacing: 10) {
                Image(systemName: icon).font(.system(size: 40)).foregroundStyle(.secondary)
                Text(title).font(.headline)
                Text(text).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 40)
            .listRowBackground(Color.clear)
            .accessibilityElement(children: .combine)
        }
    }

    /// Les mots cherchés en gras et en couleur dans l'extrait (sans accents ni casse).
    static func highlight(_ text: String, query: String) -> AttributedString {
        var out = AttributedString(text)
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return out }
        var from = text.startIndex
        while let range = text.range(of: q, options: [.caseInsensitive, .diacriticInsensitive], range: from..<text.endIndex) {
            if let lower = AttributedString.Index(range.lowerBound, within: out),
               let upper = AttributedString.Index(range.upperBound, within: out) {
                out[lower..<upper].foregroundColor = Color(uiColor: AppConfig.uiAccent)
                out[lower..<upper].inlinePresentationIntent = .stronglyEmphasized
            }
            from = range.upperBound
        }
        return out
    }
}
