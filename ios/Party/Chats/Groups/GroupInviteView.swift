import CoreImage.CIFilterBuiltins
import SwiftUI

/// Inviter dans un groupe (étape 2 de la création, et « Inviter » de la page du groupe), comme le web (GroupInvite.tsx) :
/// le lien du groupe (WhatsApp / Copier / Autre) et son code QR, puis « Déjà sur Party » : seulement des personnes déjà
/// croisées à un événement (group_invite_suggestions, jamais tout le site), un surnom exact ou un numéro. Chacun reçoit
/// une invitation (invite_to_group) et entre dès qu'il accepte. Droits de la base inchangés (créateur, Admin du site).
struct GroupInviteView: View {
    let groupID: String
    var fresh = false
    /// Dans une page qui défile déjà (création) : pas de ScrollView à soi.
    var embedded = false

    @Environment(\.people) private var people
    @Environment(\.openURL) private var openURL
    @State private var page: GroupPage?
    @State private var link: GroupLinkURL?
    @State private var linkError: String?
    @State private var suggestions: [GroupSuggestion]?
    @State private var search = ""
    @State private var picked: [Picked] = []
    @State private var sent: Set<String> = []
    @State private var busy = false
    @State private var error: String?
    @State private var note: String?

    struct Picked: Equatable, Identifiable {
        let id: String
        let name: String
        var member: String?
        var phone: String?
    }

    var body: some View {
        Group {
            if embedded { content } else {
                ScrollView { content.padding(.horizontal, PronoTheme.Space.screen).padding(.bottom, 32) }
                    .background(PeopleBackground(tint: GroupLook.gradient(page?.group.color).to))
                    .navigationTitle("Inviter")
                    .navigationBarTitleDisplayMode(.inline)
            }
        }
        .task { await load() }
        .overlay(alignment: .bottom) {
            if let note {
                Text(note).font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                    .padding(.horizontal, 16).padding(.vertical, 12)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 12)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task(id: note) {
                        try? await Task.sleep(for: .seconds(2.5))
                        Motion.animate(Motion.smooth) { self.note = nil }
                    }
                    .accessibilityAddTraits(.updatesFrequently)
            }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 18) {
            if let page {
                HStack(spacing: 12) {
                    GroupTile(emoji: page.group.emoji, color: page.group.color, photo: page.group.photo, system: page.group.system, size: 52)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(fresh ? "Invite ta bande" : "Inviter dans le groupe")
                            .font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                            .accessibilityAddTraits(.isHeader)
                        Text(fresh ? "« \(page.group.name) » est prêt. Invite maintenant ou plus tard."
                             : "« \(page.group.name) » : envoie le lien ou choisis des gens déjà croisés.")
                            .font(.subheadline).foregroundStyle(PronoTheme.t2)
                    }
                }
            }
            linkCard
            alreadyOnParty
        }
    }

    // MARK: Lien et code QR

    private var message: String? {
        guard let link, let page else { return nil }
        return GroupText.inviteMessage(host: page.myName, group: page.group, url: link.url)
    }

    private var linkCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Le lien du groupe", systemImage: "link").font(.headline).foregroundStyle(PronoTheme.t1)
            Text("Qui l’ouvre rejoint le groupe (avec son numéro s’il n’a pas encore de compte). Tu es prévenu à chaque arrivée.")
                .font(.footnote).foregroundStyle(PronoTheme.t2)
            Group {
                if let link {
                    Text(link.url.replacingOccurrences(of: "https://", with: "")).font(.subheadline.monospaced().weight(.semibold))
                        .foregroundStyle(PronoTheme.t1).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                } else if let linkError {
                    Text(linkError).font(.footnote).foregroundStyle(PronoTheme.pinkInk)
                } else {
                    Text("Préparation du lien…").font(.footnote).foregroundStyle(PronoTheme.t3)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 46, alignment: .leading)
            .padding(.horizontal, 14)
            .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            HStack(spacing: 8) {
                Button {
                    guard let message, let url = URL(string: "https://wa.me/?text=" + (message.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""))
                    else { return }
                    Haptics.tap()
                    openURL(url)
                } label: { shareLabel("WhatsApp", systemImage: "message.fill", whatsapp: true) }
                .accessibilityIdentifier("group-invite-whatsapp")
                Button {
                    guard let link else { return }
                    UIPasteboard.general.string = link.url
                    Haptics.success()
                    Motion.animate(Motion.smooth) { note = "Lien copié" }
                } label: { shareLabel("Copier", systemImage: "doc.on.doc") }
                .accessibilityIdentifier("group-invite-copy")
                if let message, let link {
                    ShareLink(item: message, subject: Text(page?.group.name ?? "Party"), message: Text(link.url)) {
                        shareLabel("Autre", systemImage: "square.and.arrow.up")
                    }
                    .accessibilityIdentifier("group-invite-share")
                } else {
                    shareLabel("Autre", systemImage: "square.and.arrow.up").opacity(0.5)
                }
            }
            .buttonStyle(PronoKitPressStyle())
            .disabled(link == nil)
            .opacity(link == nil ? 0.5 : 1)
            if let link, let qr = GroupQR.image(link.url) {
                HStack(spacing: 14) {
                    Image(uiImage: qr).interpolation(.none).resizable().scaledToFit()
                        .frame(width: 112, height: 112)
                        .padding(6)
                        .background(.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .accessibilityLabel("Code QR du lien du groupe")
                        .accessibilityIdentifier("group-invite-qr")
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Montre ce code").font(.headline).foregroundStyle(PronoTheme.t1)
                        Text("La personne le vise avec l’appareil photo, s’inscrit et rejoint le groupe.").font(.footnote).foregroundStyle(PronoTheme.t2)
                    }
                }
                .padding(12)
                .background(PronoTheme.s1b, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
        }
        .padding(16)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
    }

    private func shareLabel(_ title: String, systemImage: String, whatsapp: Bool = false) -> some View {
        Label(title, systemImage: systemImage)
            .font(.subheadline.weight(.bold)).lineLimit(1).minimumScaleFactor(0.8)
            .foregroundStyle(whatsapp ? .white : PronoTheme.t1)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(whatsapp ? PronoTheme.fixed(0x1FA855) : PronoTheme.s1b, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    // MARK: Déjà sur Party

    private var query: String { search.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "^@", with: "", options: .regularExpression) }
    private var typedPhone: String? { GroupText.phone(search) }

    private var shown: [GroupSuggestion] {
        let q = query.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "fr_CH"))
        guard !q.isEmpty, typedPhone == nil else { return suggestions ?? [] }
        return (suggestions ?? []).filter {
            $0.displayName.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "fr_CH")).contains(q)
                || ContactNames.shared.names[$0.id].map { $0.localizedCaseInsensitiveContains(q) } == true
        }
    }

    @ViewBuilder private var alreadyOnParty: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Déjà sur Party", systemImage: "person.2")
            HStack {
                Image(systemName: "magnifyingglass").foregroundStyle(PronoTheme.t3)
                TextField("Prénom, surnom ou numéro", text: $search)
                    .foregroundStyle(PronoTheme.t1)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .onSubmit { Task { await addTyped() } }
                    .onChange(of: search) { _ in error = nil }
                    .accessibilityLabel("Chercher une personne")
                    .accessibilityIdentifier("group-invite-search")
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 50)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
            if typedPhone != nil {
                PeopleGhostButton(title: "Inviter le numéro \(search.trimmingCharacters(in: .whitespaces))", systemImage: "phone") {
                    Task { await addTyped() }
                }
            } else if !query.isEmpty && shown.isEmpty {
                PeopleGhostButton(title: "Inviter le surnom « \(search.trimmingCharacters(in: .whitespaces)) »", systemImage: "at") {
                    Task { await addTyped() }
                }
            }
            ForEach(picked.filter { $0.member == nil }) { p in
                HStack(spacing: 12) {
                    Text("📱").font(.title3).frame(width: 40, height: 40).background(PronoTheme.s1b, in: Circle())
                    Text(p.name).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                    Spacer()
                    Button { picked.removeAll { $0 == p } } label: { PeopleCheck(on: true).frame(width: 44, height: 44) }
                        .accessibilityLabel("Retirer \(p.name)")
                }
            }
            if let suggestions, suggestions.isEmpty, query.isEmpty {
                Text("Personne croisée à un événement pour l’instant : envoie le lien du groupe, ou tape un surnom ou un numéro.")
                    .font(.footnote).foregroundStyle(PronoTheme.t2)
            }
            VStack(spacing: 0) {
                ForEach(Array(shown.prefix(30).enumerated()), id: \.element.id) { i, p in
                    let on = picked.contains { $0.member == p.id }
                    let done = p.invited || sent.contains(p.id)
                    Button { toggle(p) } label: {
                        HStack(spacing: 12) {
                            PronoAvatar(face: p.face, size: 40)
                            VStack(alignment: .leading, spacing: 2) {
                                PersonName(id: p.id, pseudo: p.displayName).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                                Text(GroupText.suggestion(p, sent: sent.contains(p.id))).font(.footnote).foregroundStyle(PronoTheme.t2).lineLimit(1)
                            }
                            Spacer(minLength: 8)
                            PeopleCheck(on: on || done).opacity(done ? 0.5 : 1)
                        }
                        .padding(.horizontal, 12)
                        .frame(minHeight: 60)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .disabled(done)
                    .accessibilityLabel("\(done ? "Déjà invité : " : on ? "Retirer " : "Ajouter ")\(p.displayName)")
                    .accessibilityAddTraits(on ? .isSelected : [])
                    if i < min(shown.count, 30) - 1 { Divider().overlay(PronoTheme.line).padding(.leading, 64) }
                }
            }
            .background(shown.isEmpty ? Color.clear : PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
            if !picked.isEmpty {
                PeoplePinkButton(title: "Inviter \(GroupText.names(picked.map(\.name)))", systemImage: "paperplane.fill", busy: busy) {
                    Task { await invite() }
                }
                .accessibilityIdentifier("group-invite-send")
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pinkInk) }
            Text("Ils reçoivent une invitation et entrent dans le groupe d’un toucher.")
                .font(.footnote).foregroundStyle(PronoTheme.t3).frame(maxWidth: .infinity).multilineTextAlignment(.center)
        }
        .motion(Motion.snappy, value: picked)
    }

    // MARK: Actions

    private func load() async {
        guard let people else { return }
        let api = GroupsAPI(people: people)
        async let pageJob = try? api.page(groupID)
        async let suggestionsJob = try? api.suggestions(groupID)
        do {
            link = try await api.link(groupID)
        } catch {
            linkError = "Le lien n’a pas pu être créé. Réessaie."
        }
        page = await pageJob
        suggestions = await suggestionsJob ?? []
    }

    private func toggle(_ p: GroupSuggestion) {
        Haptics.selection()
        if picked.contains(where: { $0.member == p.id }) { picked.removeAll { $0.member == p.id } }
        else { picked.append(Picked(id: p.id, name: ContactNames.shared.names[p.id] ?? p.displayName, member: p.id)) }
    }

    /// Surnom exact (compte existant) ou numéro (inscrit ou pas : l'invitation l'attend), comme le web.
    private func addTyped() async {
        let typed = query
        guard !typed.isEmpty, let people else { return }
        if let phone = typedPhone {
            if !picked.contains(where: { $0.phone == phone }) {
                picked.append(Picked(id: "phone:\(phone)", name: search.trimmingCharacters(in: .whitespaces), phone: phone))
            }
            search = ""
            return
        }
        do {
            guard let found = try await GroupsAPI(people: people).find(typed) else {
                error = "Personne avec ce surnom. Essaie son numéro de téléphone."
                return
            }
            error = nil
            if !picked.contains(where: { $0.member == found.id }) { picked.append(Picked(id: found.id, name: found.name, member: found.id)) }
            search = ""
        } catch {
            self.error = PeopleStore.message(error)
        }
    }

    private func invite() async {
        guard let people, !busy, !picked.isEmpty else { return }
        busy = true
        error = nil
        var done: [Picked] = []
        let api = GroupsAPI(people: people)
        for p in picked {
            do {
                try await api.invite(groupID, member: p.member, phone: p.phone)
                done.append(p)
            } catch {
                self.error = "\(p.name) : \(PeopleStore.message(error))"
                break
            }
        }
        sent.formUnion(done.compactMap { $0.member ?? $0.phone })
        picked.removeAll { done.contains($0) }
        busy = false
        if !done.isEmpty {
            Haptics.success()
            Motion.animate(Motion.smooth) { note = "\(GroupText.names(done.map(\.name))) : invitation envoyée" }
            search = ""
        }
    }
}

enum GroupQR {
    /// Code QR net (agrandi sans lissage) du lien du groupe.
    static func image(_ text: String) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let out = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 10, y: 10)),
              let cg = CIContext().createCGImage(out, from: out.extent) else { return nil }
        return UIImage(cgImage: cg)
    }
}
