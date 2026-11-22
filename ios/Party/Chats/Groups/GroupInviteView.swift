import CoreImage.CIFilterBuiltins
import SwiftUI

/// Inviter dans un groupe (étape 2 de la création, et « Inviter » de la page du groupe), comme le web (GroupInvite.tsx) :
/// le lien du groupe (WhatsApp / Copier / Autre) et son code QR, puis « Ajouter quelqu'un » (avis f0e9bf158133, 22.11) :
/// JAMAIS de liste des membres de Party, seulement une recherche « numéro exact ou nom » (group_people_search : numéro
/// complet, ou 3 lettres d'un nom, prénom ou surnom → 5 personnes au plus, sans leur numéro ; 30 recherches par heure).
/// Chacun reçoit une invitation (invite_to_group) et entre dès qu'il accepte. Qui invite : la base décide.
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
    @State private var found: [GroupFound]?
    @State private var searching = false
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
        /// Personne trouvée par la recherche (nil : un numéro sans compte).
        var face: PronoFace?
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
                             : "« \(page.group.name) » : envoie le lien, ou cherche quelqu’un sur Party.")
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

    // MARK: Ajouter quelqu'un (numéro exact ou nom)

    private var query: String {
        search.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "^@", with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespaces)
    }
    private var typedPhone: String? { GroupText.phone(search) }
    private var ready: Bool { typedPhone != nil || query.count >= GroupText.searchLetters }
    private var shown: [GroupFound] { ready ? found ?? [] : [] }

    /// Les personnes choisies restent visibles quand la recherche change ; puis les résultats (5 au plus).
    private var rows: [(id: String, name: String, face: PronoFace, found: GroupFound?)] {
        let kept = picked.filter { p in p.face != nil && !shown.contains { $0.id == p.id } }
            .map { (id: $0.id, name: $0.name, face: $0.face!, found: GroupFound?.none) }
        return kept + shown.map { (id: $0.id, name: ContactNames.shared.names[$0.id] ?? $0.displayName, face: $0.face, found: Optional($0)) }
    }

    @ViewBuilder private var alreadyOnParty: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Ajouter quelqu’un", systemImage: "person.badge.plus")
            HStack {
                Image(systemName: "magnifyingglass").foregroundStyle(PronoTheme.t3)
                TextField("Numéro, nom, prénom ou surnom", text: $search)
                    .foregroundStyle(PronoTheme.t1)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .onSubmit { if typedPhone != nil, found?.isEmpty == true { addPhone() } }
                    .onChange(of: search) { _ in error = nil }
                    .accessibilityLabel("Chercher une personne")
                    .accessibilityIdentifier("group-invite-search")
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 50)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
            .task(id: search) { await runSearch() }
            if !ready {
                Text("Tape son numéro complet (+41 79…) ou au moins 3 lettres de son nom, prénom ou surnom.")
                    .font(.footnote).foregroundStyle(PronoTheme.t2)
            } else if searching && found == nil {
                Text("Recherche…").font(.footnote).foregroundStyle(PronoTheme.t3)
            } else if !searching, let found, found.isEmpty {
                if typedPhone != nil {
                    Text("Pas trouvé sur Party : la personne trouvera l’invitation en s’inscrivant avec ce numéro.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                    PeopleGhostButton(title: "Inviter le numéro \(search.trimmingCharacters(in: .whitespaces))", systemImage: "phone") {
                        addPhone()
                    }
                } else {
                    Text("Personne trouvé. Vérifie l’orthographe, ou tape son numéro complet.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                }
            }
            ForEach(picked.filter { $0.face == nil }) { p in
                HStack(spacing: 12) {
                    Text("📱").font(.title3).frame(width: 40, height: 40).background(PronoTheme.s1b, in: Circle())
                    Text(p.name).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                    Spacer()
                    Button { picked.removeAll { $0 == p } } label: { PeopleCheck(on: true).frame(width: 44, height: 44) }
                        .accessibilityLabel("Retirer \(p.name)")
                }
            }
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.element.id) { i, row in
                    let on = picked.contains { $0.id == row.id }
                    let done = row.found?.invited == true || sent.contains(row.id)
                    Button { toggle(row) } label: {
                        HStack(spacing: 12) {
                            PronoAvatar(face: row.face, size: 40)
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text(row.name).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                                    if let initial = row.found?.initial {
                                        Text("\(initial).").font(.subheadline).foregroundStyle(PronoTheme.t3)
                                    }
                                }
                                Text(done ? "Invitation envoyée" : on ? "Sera invité" : "Sur Party")
                                    .font(.footnote).foregroundStyle(PronoTheme.t2).lineLimit(1)
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
                    .accessibilityLabel("\(done ? "Déjà invité : " : on ? "Retirer " : "Ajouter ")\(row.name)")
                    .accessibilityAddTraits(on ? .isSelected : [])
                    if i < rows.count - 1 { Divider().overlay(PronoTheme.line).padding(.leading, 64) }
                }
            }
            .background(rows.isEmpty ? Color.clear : PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
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
        do {
            link = try await api.link(groupID)
        } catch {
            linkError = "Le lien n’a pas pu être créé. Réessaie."
        }
        page = await pageJob
    }

    /// Recherche dans la base, 450 ms après la dernière touche (anti-annuaire : 30 recherches par heure).
    private func runSearch() async {
        guard ready, let people else {
            found = nil
            searching = false
            return
        }
        searching = true
        try? await Task.sleep(for: .milliseconds(450))
        if Task.isCancelled { return }
        let q = typedPhone.map { "+" + $0 } ?? query
        do {
            let list = try await GroupsAPI(people: people).search(groupID, q)
            if Task.isCancelled { return }
            found = list
            error = nil
        } catch let failure {
            if Task.isCancelled { return }
            found = []
            error = PeopleStore.message(failure)
        }
        searching = false
    }

    private func toggle(_ row: (id: String, name: String, face: PronoFace, found: GroupFound?)) {
        Haptics.selection()
        if picked.contains(where: { $0.id == row.id }) { picked.removeAll { $0.id == row.id }; return }
        // Trouvé par son numéro : invité par ce numéro (le numéro vaut contact) ; sinon par son compte.
        let phone = typedPhone
        picked.append(Picked(id: row.id, name: row.name, member: phone == nil ? row.id : nil, phone: phone, face: row.face))
    }

    /// Numéro sans compte : l'invitation l'attend (il la trouve en s'inscrivant avec ce numéro).
    private func addPhone() {
        guard let phone = typedPhone, !picked.contains(where: { $0.phone == phone && $0.face == nil }) else { return }
        picked.append(Picked(id: "phone:\(phone)", name: search.trimmingCharacters(in: .whitespaces), phone: phone))
        search = ""
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
        sent.formUnion(done.map(\.id))
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
