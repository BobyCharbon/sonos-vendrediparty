import SwiftUI

/// Nouveau groupe en 2 étapes (comme web/events/src/app/group/new.tsx) : 1. nom, emoji, couleur et photo facultative,
/// avec l'aperçu vivant de sa couverture ; 2. Inviter (lien du groupe, code QR, personnes croisées) ou « Plus tard ».
/// Le groupe est créé en quittant l'étape 1 (CGU d'abord : son nom est un contenu ; nom filtré par la base) ; « Retour »
/// depuis l'étape 2 le modifie. Ensuite, la page du groupe s'ouvre.
struct NewGroupView: View {
    let done: (String) -> Void

    @Environment(\.people) private var people
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var name = ""
    @State private var emoji = "🪩"
    @State private var color = "pink"
    @State private var photo: Data?
    @State private var sentPhoto: Data?
    @State private var created: String?
    @State private var step = 1
    @State private var busy = false
    @State private var error: String?
    @State private var askTerms = false
    @FocusState private var nameFocused: Bool

    private var trimmed: String { name.split(whereSeparator: \.isWhitespace).joined(separator: " ") }

    var body: some View {
        Group {
            if step == 1 { form.transition(.move(edge: .leading).combined(with: .opacity)) }
            else if let created {
                ScrollView {
                    VStack(spacing: 16) {
                        steps
                        GroupInviteView(groupID: created, fresh: true, embedded: true)
                        PeopleGhostButton(title: "Ouvrir le groupe", systemImage: "arrow.right.circle") { done(created) }
                            .accessibilityIdentifier("new-group-open")
                    }
                    .padding(.horizontal, PronoTheme.Space.screen)
                    .padding(.bottom, 32)
                }
                .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .background(PeopleBackground(tint: GroupLook.gradient(color).to))
        .navigationTitle(step == 1 ? "Nouveau groupe" : "Inviter")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                if let created {
                    Button("Plus tard") { done(created) }
                        .font(.body.weight(step == 2 ? .bold : .regular))
                        .accessibilityIdentifier("new-group-later")
                }
            }
            ToolbarItem(placement: .bottomBar) {
                if step == 2 {
                    Button { Motion.animate(Motion.smooth) { step = 1 } } label: { Label("Retour", systemImage: "chevron.backward") }
                }
            }
        }
        .sheet(isPresented: $askTerms) {
            if let people {
                TermsAcceptSheet(store: people.moderation) { accepted in
                    if accepted { next() } else {
                        error = TermsLater.message("créer le groupe", button: created == nil ? "Continuer" : "Enregistrer et continuer")
                    }
                }
            }
        }
        .motion(Motion.snappy, value: color)
        .motion(Motion.snappy, value: emoji)
    }

    /// Étapes : deux traits, le second s'allume à l'étape Inviter.
    private var steps: some View {
        HStack(spacing: 6) {
            Capsule().fill(PronoTheme.pink).frame(height: 4)
            Capsule().fill(step == 2 ? PronoTheme.pink : PronoTheme.line2).frame(height: 4)
        }
        .padding(.top, 8)
        .accessibilityElement()
        .accessibilityLabel("Étape \(step) sur 2")
    }

    private var form: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                steps
                preview
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        PeopleSectionLabel(text: "Nom du groupe")
                        Text("\(name.count)/\(GroupText.nameMax)").font(.footnote.monospacedDigit()).foregroundStyle(PronoTheme.t3)
                            .accessibilityHidden(true)
                    }
                    TextField("Ex. Soirées du vendredi", text: $name)
                        .font(.title3)
                        .foregroundStyle(PronoTheme.t1)
                        .tint(PronoTheme.pink)
                        .focused($nameFocused)
                        .submitLabel(.next)
                        .onSubmit { next() }
                        .onChange(of: name) { value in if value.count > GroupText.nameMax { name = String(value.prefix(GroupText.nameMax)) } }
                        .padding(.horizontal, 18)
                        .frame(minHeight: 60)
                        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous)
                            .strokeBorder(nameFocused ? PronoTheme.lavB.opacity(0.7) : PronoTheme.line2, lineWidth: nameFocused ? 2 : 1))
                        .accessibilityLabel("Nom du groupe")
                        .accessibilityIdentifier("group-new-name")
                }
                VStack(alignment: .leading, spacing: 10) {
                    PeopleSectionLabel(text: "Un emoji")
                    GroupEmojiGrid(selection: $emoji)
                }
                VStack(alignment: .leading, spacing: 10) {
                    PeopleSectionLabel(text: "Une couleur")
                    GroupColorRow(selection: $color)
                }
                GroupPhotoField(has: photo != nil, busy: busy, picked: { photo = $0 }, remove: { photo = nil })
                if let error {
                    Text(error).font(.footnote).foregroundStyle(PronoTheme.pinkInk).accessibilityIdentifier("group-new-error")
                }
            }
            .padding(.horizontal, PronoTheme.Space.screen)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 10) {
                if let people {
                    NavigationLink { TermsView(store: people.moderation) } label: {
                        (Text("Tu crées le groupe et tu le gères. En le créant, tu acceptes les ") + Text("règles de Party").bold()
                            .foregroundColor(PronoTheme.lavA) + Text("."))
                            .font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                    }
                    .buttonStyle(.plain)
                }
                PeoplePinkButton(title: created == nil ? "Continuer" : "Enregistrer et continuer", systemImage: "arrow.right", busy: busy) { next() }
                    .disabled(trimmed.isEmpty)
                    .accessibilityIdentifier("group-new-continue")
                Text("Ensuite : inviter ta bande (ou plus tard).").font(.footnote).foregroundStyle(PronoTheme.t3)
            }
            .padding(.horizontal, PronoTheme.Space.screen)
            .padding(.top, 10)
            .padding(.bottom, 8)
            .background(PronoTheme.bg.opacity(0.92).ignoresSafeArea(edges: .bottom))
        }
    }

    /// Aperçu vivant de la couverture : couleur, emoji, photo et nom suivent la saisie.
    private var preview: some View {
        let g = GroupLook.gradient(color)
        let shape = RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous)
        return VStack(alignment: .leading, spacing: 0) {
            ZStack {
                LinearGradient(colors: [g.from, g.to, g.to.opacity(0.6)], startPoint: .topLeading, endPoint: .bottomTrailing)
                if let photo, let image = UIImage(data: photo) {
                    Image(uiImage: image).resizable().scaledToFill()
                } else {
                    HStack(spacing: 40) { ForEach(0..<3, id: \.self) { _ in Text(emoji).font(.system(size: 18)).opacity(0.35) } }
                }
            }
            .frame(height: 82)
            .clipped()
            HStack(alignment: .bottom, spacing: 12) {
                GroupTile(emoji: emoji, color: color, size: 60)
                    .overlay { if let photo, let image = UIImage(data: photo) {
                        Image(uiImage: image).resizable().scaledToFill().frame(width: 60, height: 60)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    } }
                    .padding(3)
                    .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 21, style: .continuous))
                    .id("\(emoji)-\(color)")
                    .transition(.scale(scale: 0.8).combined(with: .opacity))
                VStack(alignment: .leading, spacing: 2) {
                    Text(trimmed.isEmpty ? "Ton groupe" : trimmed).font(.title3.weight(.bold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                    Text("1 membre · toi").font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 14)
            .padding(.top, -30)
        }
        .background(PronoTheme.s1, in: shape)
        .clipShape(shape)
        .overlay(shape.strokeBorder(PronoTheme.line, lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Aperçu : \(trimmed.isEmpty ? "groupe sans nom" : trimmed), \(emoji)")
    }

    private func next() {
        guard let people, !busy, !trimmed.isEmpty else { return }
        Haptics.tap()
        busy = true
        error = nil
        Task {
            defer { busy = false }
            let api = GroupsAPI(people: people)
            do {
                let id: String
                if let created {
                    try await api.update(created, name: trimmed, emoji: emoji, color: color)
                    id = created
                } else {
                    id = try await api.create(name: trimmed, emoji: emoji, color: color)
                    created = id
                }
                if photo != sentPhoto {
                    if let photo { try await people.uploadGroupPhoto(id, jpeg: photo) } else { try await api.removePhoto(id) }
                    sentPhoto = photo
                }
                Haptics.success()
                nameFocused = false
                Motion.animate(Motion.smooth) { step = 2 }
            } catch PartyAPIError.termsRequired {
                askTerms = true
            } catch {
                Haptics.error()
                self.error = PeopleStore.message(error)
            }
        }
    }
}
