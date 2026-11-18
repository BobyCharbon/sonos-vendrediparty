import SwiftUI

/// Nouveau groupe (maquette 1-neon/2b), depuis « Nouveau message » avec plusieurs personnes : couverture vivante (couleur
/// et emoji changent en direct), nom (filtré par la base), 16 emojis et 6 couleurs (listes fermées, comme la base),
/// règles de Party (CGU) ; `create_chat_group` crée un groupe PRIVÉ (Root ne le lit pas) et invite seulement les
/// personnes en lien direct ; les autres reçoivent d'abord un message (« écris-leur d'abord »).
struct NewChatGroupView: View {
    let members: [ChatPerson]
    var event: ChatEventCard? = nil
    /// Groupe créé : la vue qui m'a ouvert ferme tout et ouvre la discussion.
    let done: (String) -> Void

    /// Mêmes listes que la base (member_groups_emoji_check / _color_check) et que web/events/src/lib/groups.ts.
    static let emojis = ["👯", "🎉", "🪩", "⚽", "🏡", "🎲", "🥾", "🎸", "🍕", "🍻", "🍷", "🎂", "🌴", "🎮", "🎤", "🏀"]
    static let colors: [(key: String, name: String)] = [("pink", "Rose"), ("coral", "Orange"), ("mint", "Vert"),
                                                       ("sky", "Bleu"), ("lavender", "Lavande"), ("lemon", "Citron")]
    static let maxName = 40

    @Environment(\.people) private var people
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var name = ""
    @State private var emoji = "🪩"
    @State private var color = "pink"
    @State private var busy = false
    @State private var error: String?
    @State private var askTerms = false
    @State private var refused: (group: String, names: String)?
    @FocusState private var nameFocused: Bool

    private var trimmed: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                coverPreview
                nameField
                emojiGrid
                colorRow
                if let error {
                    Text(error).font(.footnote).foregroundStyle(PronoTheme.pinkInk).accessibilityIdentifier("new-group-error")
                }
            }
            .padding(.horizontal, PronoTheme.Space.screen)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom) { footer }
        .background(PeopleBackground(tint: GroupLook.gradient(color).to))
        .navigationTitle("Nouveau groupe")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $askTerms) {
            if let people { TermsAcceptSheet(store: people.moderation) { accepted in if accepted { create() } } }
        }
        .alert("Groupe créé", isPresented: Binding(get: { refused != nil }, set: { if !$0, let r = refused { refused = nil; done(r.group) } })) {
            Button("OK") {}
        } message: {
            Text("\(refused?.names ?? "") n'a pas encore été invité·e : écris-lui d'abord un message, puis invite-le·la depuis le groupe.")
        }
        .motion(Motion.snappy, value: color)
        .motion(Motion.snappy, value: emoji)
    }

    // MARK: Parties

    /// Couverture vivante : dégradé de la couleur, nom, visages « Toi, Léa et Noé », tuile emoji penchée.
    private var coverPreview: some View {
        let g = GroupLook.gradient(color)
        let shape = RoundedRectangle(cornerRadius: 28, style: .continuous)
        return ZStack(alignment: .topTrailing) {
            shape.fill(LinearGradient(colors: [g.to, g.to.opacity(0.55), PronoTheme.s1], startPoint: .topLeading, endPoint: .bottom))
            Text(emoji).font(.system(size: 48))
                .frame(width: 104, height: 104)
                .background(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 26, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 26, style: .continuous).strokeBorder(.white.opacity(0.35), lineWidth: 2))
                .rotationEffect(.degrees(reduceMotion ? 0 : 6))
                .shadow(color: g.to.opacity(0.5), radius: 16, y: 8)
                .padding(16)
                .id(emoji)
                .transition(.scale(scale: 0.8).combined(with: .opacity))
            VStack(alignment: .leading, spacing: 12) {
                Spacer(minLength: 0)
                Text(trimmed.isEmpty ? "Ton groupe" : trimmed)
                    .font(.system(size: 34, weight: .heavy, design: .rounded))
                    .foregroundStyle(trimmed.isEmpty ? PronoTheme.t1.opacity(0.55) : PronoTheme.t1)
                    .lineLimit(2).minimumScaleFactor(0.6)
                HStack(spacing: 10) {
                    PronoAvatarStack(faces: members.map(\.face), size: 30, ring: g.to, max: 4)
                    Text("Toi, \(PeopleText.names(members))").font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(height: 200)
        .clipShape(shape)
        .overlay(shape.strokeBorder(PronoTheme.line2, lineWidth: 1))
        .shadow(color: g.to.opacity(0.35), radius: 24, y: 12)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Aperçu : \(trimmed.isEmpty ? "groupe sans nom" : trimmed), \(emoji), avec toi, \(PeopleText.names(members))")
    }

    private var nameField: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Nom du groupe")
            HStack {
                TextField("La bande du vendredi", text: $name)
                    .font(.title3)
                    .foregroundStyle(PronoTheme.t1)
                    .tint(PronoTheme.pink)
                    .focused($nameFocused)
                    .submitLabel(.done)
                    .onChange(of: name) { value in if value.count > Self.maxName { name = String(value.prefix(Self.maxName)) } }
                    .accessibilityIdentifier("new-group-name")
                Text("\(name.count)/\(Self.maxName)").font(.footnote.monospacedDigit()).foregroundStyle(PronoTheme.t3)
                    .accessibilityHidden(true)
            }
            .padding(.horizontal, 18)
            .frame(minHeight: 60)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(nameFocused ? PronoTheme.lavB.opacity(0.7) : PronoTheme.line2, lineWidth: nameFocused ? 2 : 1))
        }
    }

    private var emojiGrid: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Emoji")
            GroupEmojiGrid(selection: $emoji)
        }
    }

    private var colorRow: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Couleur")
            GroupColorRow(selection: $color)
        }
    }

    private var footer: some View {
        VStack(spacing: 12) {
            if let people {
                NavigationLink { TermsView(store: people.moderation) } label: {
                    (Text("Tu crées le groupe et tu le gères. En le créant, tu acceptes les ") + Text("règles de Party").bold().foregroundColor(PronoTheme.lavA) + Text("."))
                        .font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                }
                .buttonStyle(.plain)
            }
            PeoplePinkButton(title: "Créer le groupe", systemImage: "sparkle", busy: busy) { create() }
                .disabled(trimmed.count < 2)
                .accessibilityIdentifier("new-group-create")
        }
        .padding(.horizontal, PronoTheme.Space.screen)
        .padding(.top, 12)
        .padding(.bottom, 8)
        .background(PronoTheme.bg.opacity(0.92).ignoresSafeArea(edges: .bottom))
    }

    // MARK: Création

    private func create() {
        guard let people, !busy, trimmed.count >= 2 else { return }
        Haptics.tap()
        busy = true
        error = nil
        Task {
            defer { busy = false }
            do {
                let created = try await people.createGroup(name: trimmed, emoji: emoji, color: color, members: members.map(\.id))
                if let event { try? await people.sendEvent(event, to: created.group, direct: false) }
                Haptics.success()
                let left = members.filter { created.refused.contains($0.id) }
                if left.isEmpty { done(created.group) } else { refused = (created.group, PeopleText.names(left)) }
            } catch PartyAPIError.termsRequired {
                askTerms = true
            } catch {
                self.error = PeopleStore.message(error)
            }
        }
    }
}
