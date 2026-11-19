import SwiftUI

/// Recherche de la liste (« Personnes, groupes, messages ») : Personnes (chat_people_search, jamais par numéro),
/// Discussions (mes discussions, par leur nom), Événements (les miens, même sans message : y lancer la discussion,
/// chat_event_search), Messages (chat_search, seulement mes conversations).
struct ChatSearchResults: View {
    let query: String
    @ObservedObject var store: ChatsStore
    let open: (ChatSummary) -> Void
    let openHit: (ChatMessageHit) -> Void

    @State private var people: [ChatPerson] = []
    @State private var messages: [ChatMessageHit] = []
    @State private var events: [ChatSummary] = []
    @State private var searched = ""

    private var trimmed: String { query.trimmingCharacters(in: .whitespaces) }

    var body: some View {
        let chats = ChatListLogic.matching(store.chats ?? [], query: trimmed)
        let newEvents = events.filter { event in !chats.contains { $0.id == event.id } }
        List {
            if !people.isEmpty {
                Section {
                    ForEach(people) { person in
                        Button { Task { await store.openDirect(person.id) } } label: { ChatPersonRow(person: person) }
                            .buttonStyle(ChatRowPressStyle())
                            .neonRow()
                    }
                } header: { ChatSectionHeader(title: "Personnes") }
            }
            if !chats.isEmpty {
                Section {
                    ForEach(chats.prefix(20)) { chat in
                        Button { open(chat) } label: { ChatListRow(chat: chat).padding(.horizontal, 16) }
                            .buttonStyle(ChatRowPressStyle())
                            .neonRow()
                    }
                } header: { ChatSectionHeader(title: "Discussions") }
            }
            if !newEvents.isEmpty {
                Section {
                    ForEach(newEvents) { event in
                        Button { open(event) } label: { ChatListRow(chat: event).padding(.horizontal, 16) }
                            .buttonStyle(ChatRowPressStyle())
                            .neonRow()
                            .accessibilityIdentifier("chat-search-event")
                    }
                } header: { ChatSectionHeader(title: "Événements") }
            }
            if !messages.isEmpty {
                Section {
                    ForEach(messages) { hit in
                        Button { openHit(hit) } label: { ChatHitRow(hit: hit, chat: store.chat(hit.chatID), query: trimmed) }
                            .buttonStyle(ChatRowPressStyle())
                            .neonRow()
                    }
                } header: { ChatSectionHeader(title: "Messages") }
            }
            if people.isEmpty && chats.isEmpty && newEvents.isEmpty && messages.isEmpty {
                Text(searched == trimmed && trimmed.count >= 2 ? "Rien trouvé pour « \(trimmed) »." : trimmed.count < 2 ? "Tape au moins 2 lettres." : "Recherche…")
                    .font(.subheadline).foregroundStyle(ChatNeon.t2)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 40)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .scrollDismissesKeyboard(.immediately)
        .task(id: trimmed) {
            let q = trimmed
            guard q.count >= 2 else { people = []; messages = []; events = []; searched = q; return }
            try? await Task.sleep(for: .milliseconds(280))  // on tape encore : une seule recherche
            guard !Task.isCancelled else { return }
            async let p = store.searchPeople(q)
            async let m = store.searchMessages(q)
            async let e = store.searchEvents(q)
            let (foundPeople, foundMessages, foundEvents) = await (p, m, e)
            guard !Task.isCancelled else { return }
            Motion.animate(Motion.smooth) {
                people = foundPeople
                messages = foundMessages
                events = foundEvents
                searched = q
            }
        }
    }
}

struct ChatSectionHeader: View {
    let title: String

    var body: some View {
        Text(title)
            .font(ChatNeon.label).kerning(0.9).textCase(.uppercase)
            .foregroundStyle(ChatNeon.t3)
            .padding(.horizontal, 16).padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ChatNeon.bg.opacity(0.92))
            .listRowInsets(EdgeInsets())
            .accessibilityAddTraits(.isHeader)
    }
}

/// Une personne trouvée : « Déjà vu 3 fois » ou ce qu'on a en commun ; « Écrire » ou « Demande ».
struct ChatPersonRow: View {
    let person: ChatPerson

    var body: some View {
        HStack(spacing: 12) {
            NeonAvatar(id: person.id, name: person.name, photo: person.photo, size: 44)
            VStack(alignment: .leading, spacing: 2) {
                Text(person.name).font(ChatNeon.name).foregroundStyle(ChatNeon.t1).lineLimit(1)
                if let detail = person.detail {
                    Text(detail).font(.footnote).foregroundStyle(ChatNeon.t2).lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            Label(person.link == "request" ? "Demande" : "Écrire", systemImage: person.link == "request" ? "paperplane" : "bubble.left")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(ChatNeon.lav)
                .padding(.horizontal, 12).frame(minHeight: 36)
                .background(ChatNeon.glass, in: Capsule())
                .overlay(Capsule().strokeBorder(ChatNeon.lav.opacity(0.35), lineWidth: 1))
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel([person.name, person.detail, person.link == "request" ? "Écrire : ce sera une demande de message" : "Écrire"]
            .compactMap { $0 }.joined(separator: ", "))
        .accessibilityAddTraits(.isButton)
    }
}

/// Un message trouvé : la discussion, l'extrait (mot cherché en lavande), l'heure.
private struct ChatHitRow: View {
    let hit: ChatMessageHit
    let chat: ChatSummary?
    let query: String

    var body: some View {
        HStack(spacing: 12) {
            if let chat { ChatAvatar(chat: chat, size: 44) } else {
                Image(systemName: "text.bubble").font(.title3).foregroundStyle(ChatNeon.lav).frame(width: 44, height: 44)
            }
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(hit.title).font(ChatNeon.name).foregroundStyle(ChatNeon.t1).lineLimit(1)
                    Spacer(minLength: 4)
                    Text(ChatListText.time(hit.at)).font(ChatNeon.time).foregroundStyle(ChatNeon.t3)
                }
                Text(highlighted).font(.subheadline).lineLimit(2)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }

    private var highlighted: AttributedString {
        var text = AttributedString(hit.excerpt)
        text.foregroundColor = ChatNeon.t2
        if let range = text.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) {
            text[range].foregroundColor = ChatNeon.lav
            text[range].font = .subheadline.weight(.bold)
        }
        return text
    }
}

extension View {
    /// Ligne de liste sans fond ni marges, séparateur fin aligné sur le texte.
    func neonRow() -> some View {
        listRowInsets(EdgeInsets())
            .listRowBackground(Color.clear)
            .listRowSeparatorTint(ChatNeon.line)
            .alignmentGuide(.listRowSeparatorLeading) { _ in 82 }
    }
}
