import SwiftUI

/// Ma note privée sur une personne (`member_note_get` / `member_note_set`, avis ede29a5bb24e) : lue par moi seul.
struct MemberNote: Codable, Equatable {
    let body: String
}

extension PeopleStore {
    func note(_ user: String) async throws -> String {
        try await call("member_note_get", ["target": user], as: MemberNote?.self)?.body ?? ""
    }

    /// Un texte vide efface la note ; rend la note enregistrée.
    func setNote(_ user: String, _ body: String) async throws -> String {
        try await call("member_note_set", ["target": user, "body": body], as: MemberNote?.self)?.body ?? ""
    }
}

/// Bloc « 📝 Ma note privée » du mini-profil : « où on s'est rencontrés… », 500 caractères, modifiable et effaçable.
/// Visible par moi seul (RLS de member_notes) : jamais montrée à la personne, ni partagée.
struct PrivateNoteCard: View {
    static let max = 500
    let userID: String
    let name: String

    @Environment(\.people) private var people
    @State private var saved: String?
    @State private var draft = ""
    @State private var busy = false
    @State private var problem: String?
    @State private var done = false
    @FocusState private var focused: Bool

    private var dirty: Bool { draft.trimmingCharacters(in: .whitespacesAndNewlines) != (saved ?? "") }

    var body: some View {
        Group {
            if saved != nil { card }
        }
        .task(id: userID) { await load() }
    }

    private var card: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text("📝 Ma note privée").font(.headline).foregroundStyle(PronoTheme.t1).accessibilityAddTraits(.isHeader)
                Spacer(minLength: 8)
                Label("Visible par toi seul", systemImage: "lock.fill")
                    .font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.lav)
            }
            TextField("Où tu as rencontré \(name), un détail à retenir…", text: $draft, axis: .vertical)
                .lineLimit(3...8)
                .focused($focused)
                .foregroundStyle(PronoTheme.t1)
                .padding(12)
                .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
                .onChange(of: draft) { value in if value.count > Self.max { draft = String(value.prefix(Self.max)) } }
                .accessibilityLabel("Ma note privée sur \(name)")
                .accessibilityIdentifier("private-note-input")
            HStack(spacing: 8) {
                Text("\(draft.count)/\(Self.max)" + (done ? " · Enregistrée ✓" : ""))
                    .font(.caption).foregroundStyle(PronoTheme.t3)
                Spacer(minLength: 8)
                if let saved, !saved.isEmpty, !dirty {
                    Button("Effacer") { Task { await store("") } }
                        .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                        .frame(minHeight: 44)
                        .accessibilityLabel("Effacer ma note")
                        .accessibilityIdentifier("private-note-erase")
                }
                if dirty {
                    Button { Task { await store(draft) } } label: {
                        Group { if busy { ProgressView().tint(PeopleNeon.pinkInk) } else { Text("Enregistrer").font(.headline) } }
                            .foregroundStyle(PeopleNeon.pinkInk)
                            .padding(.horizontal, 16).frame(minHeight: 44)
                            .background(PronoTheme.pink, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .buttonStyle(.plain)
                    .disabled(busy)
                    .accessibilityIdentifier("private-note-save")
                }
            }
            if let problem {
                Text(problem).font(.footnote).foregroundStyle(PronoTheme.retract)
            }
        }
        .padding(14)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(PronoTheme.line, lineWidth: 1))
        .accessibilityIdentifier("private-note")
    }

    private func load() async {
        guard let people else { return }
        // Base sans notes (ou erreur) : pas de bloc.
        if let n = try? await people.note(userID) { saved = n; draft = n }
    }

    private func store(_ text: String) async {
        guard let people, !busy else { return }
        busy = true
        problem = nil
        defer { busy = false }
        do {
            let n = try await people.setNote(userID, text)
            saved = n
            draft = n
            focused = false
            Haptics.success()
            done = true
            try? await Task.sleep(for: .seconds(1.6))
            done = false
        } catch {
            problem = "Ta note n'a pas pu être enregistrée. Réessaie."
        }
    }
}
