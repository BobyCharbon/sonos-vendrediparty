import SwiftUI

/// Mini-profil (maquette 1-neon/3) : feuille à deux hauteurs au toucher d'un nom ou d'une photo, partout dans l'app
/// native. Couverture à la couleur de la personne, grande photo, « Jamais rencontré » / « Déjà vu N fois », les 3
/// dernières soirées vécues ensemble, « Envoyer un message » (principal ; désactivé avec la raison si la base dit
/// « none »), Fiche, groupes en commun, « À venir ensemble », Bloquer · Signaler. Données : `member_mini`.
struct MiniProfileSheet: View {
    let userID: String

    @Environment(\.people) private var people
    @Environment(\.writeDirect) private var writeDirect
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ObservedObject private var contacts = ContactNames.shared

    @State private var mini: MemberMini?
    @State private var error: String?
    @State private var writing = false
    @State private var problem: String?
    @State private var needsTerms = false
    @State private var askTerms = false
    @State private var showCard = false
    @State private var confirmBlock = false
    @State private var reporting: ReportTarget?

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                cover
                if let mini { content(mini) } else if let error { failed(error) } else {
                    ProgressView().tint(PronoTheme.lav).padding(.top, 40)
                }
            }
            .padding(.bottom, 24)
        }
        .background(PronoTheme.bg.ignoresSafeArea())
        .overlay(alignment: .topTrailing) { closeButton }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
        .task { await load() }
        .sheet(isPresented: $askTerms) {
            if let people { TermsAcceptSheet(store: people.moderation, title: "Avant d'écrire") { accepted in
                if accepted { afterTerms() } else { problem = TermsLater.message("écrire", button: "Envoyer un message") }
            } }
        }
        .sheet(isPresented: $showCard) {
            if let people { MemberCardView(store: people.privacy, memberID: userID).environment(\.writeDirect, nil) }
        }
        .sheet(item: $reporting) { target in if let people { ReportSheet(store: people.moderation, target: target) } }
        .confirmationDialog("Bloquer \(shownName) ?", isPresented: $confirmBlock, titleVisibility: .visible) {
            Button("Bloquer", role: .destructive) { Task { await setBlocked(true) } }
        } message: {
            Text("Elle ne pourra plus t'écrire, te citer ni t'inviter ; elle n'en est pas prévenue.")
        }
        .accessibilityIdentifier("mini-profile")
    }

    // MARK: Parties

    private var color: String { PronoAvatar.color(for: userID) }

    /// Nom court (boutons, VoiceOver) : le nom de mon répertoire, sinon son surnom, sinon son nom.
    private var shownName: String {
        guard let mini else { return "cette personne" }
        let shown = contacts.label(for: mini.id, pseudo: mini.person.short).primary
        return shown.isEmpty ? "cette personne" : shown
    }

    /// Titre : le nom de mon répertoire s'il existe, sinon son nom complet (ou son surnom).
    private func title(_ m: MemberMini) -> String {
        if let contact = contacts.names[m.id], !contact.isEmpty { return contact }
        return m.name.isEmpty ? (m.nickname ?? shownName) : m.name
    }

    /// Couverture à la couleur de la personne, qui se fond dans la nuit ; parallaxe douce au glisser.
    private var cover: some View {
        GeometryReader { proxy in
            let pull = max(0, proxy.frame(in: .global).minY)
            LinearGradient(colors: [GroupLook.gradient(color).from.opacity(0.85), GroupLook.gradient(color).to.opacity(0.45), PronoTheme.bg],
                           startPoint: .top, endPoint: .bottom)
                .frame(height: 150 + (reduceMotion ? 0 : pull))
                .offset(y: reduceMotion ? 0 : -pull)
        }
        .frame(height: 96)
        .accessibilityHidden(true)
    }

    private var closeButton: some View {
        Button { dismiss() } label: {
            Image(systemName: "xmark").font(.body.weight(.bold)).foregroundStyle(PronoTheme.t1)
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial, in: Circle())
                .overlay(Circle().strokeBorder(PronoTheme.line2, lineWidth: 1))
        }
        .padding(16)
        .accessibilityLabel("Fermer")
        .accessibilityIdentifier("mini-profile-close")
    }

    @ViewBuilder
    private func content(_ m: MemberMini) -> some View {
        VStack(spacing: 18) {
            VStack(spacing: 8) {
                PronoAvatar(face: m.person.face, size: 112)
                    .opensProfilePhoto(m.person.face.photo, name: title(m))
                    .padding(4)
                    .background(PronoTheme.bg, in: Circle())
                    .overlay(Circle().strokeBorder(PronoTheme.line2, lineWidth: 1))
                    .offset(y: -40)
                    .padding(.bottom, -40)
                Text(title(m))
                    .font(.system(.title, design: .rounded).weight(.heavy))
                    .foregroundStyle(PronoTheme.t1)
                    .multilineTextAlignment(.center)
                if let sub = subtitle(m) {
                    Text(sub).font(.body).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                }
                if !m.restricted {
                    Label(PeopleText.met(m.metCount), systemImage: "sparkle")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(PronoTheme.lav)
                        .padding(.horizontal, 16).frame(minHeight: 36)
                        .background(PronoTheme.lavB.opacity(0.14), in: Capsule())
                        .overlay(Capsule().strokeBorder(PronoTheme.lavB.opacity(0.4), lineWidth: 1))
                        .accessibilityIdentifier("mini-profile-met")
                }
            }
            .accessibilityElement(children: .contain)  // la photo reste un bouton (voir en grand)

            actions(m)

            PrivateNoteCard(userID: m.id, name: shownName)  // ma note privée (avis ede29a5bb24e), visible par moi seul

            if !m.restricted {
                if !m.met.isEmpty {
                    section("Soirées ensemble") {
                        ForEach(m.met) { e in
                            eventRow(id: e.id, title: e.title, start: e.start, sub: PeopleDate.spoken(e.start)?.capitalizedFirst, past: true)
                        }
                    }
                }
                if !m.groups.isEmpty { groups(m) }
                if !m.events.isEmpty {
                    section("À venir ensemble") {
                        ForEach(m.events) { e in
                            eventRow(id: e.id, title: e.title, start: e.start, sub: PeopleText.together(e, them: shownName), past: false)
                        }
                    }
                }
            }

            safety(m).padding(.top, 8)
        }
        .padding(.horizontal, PronoTheme.Space.screen)
        .transition(.opacity)
    }

    /// « Noé », « Noé · dans tes contacts » : son surnom Party sous le titre.
    private func subtitle(_ m: MemberMini) -> String? {
        var parts: [String] = []
        if let nick = m.nickname, !nick.isEmpty, nick != title(m) { parts.append(nick) }
        if contacts.names[m.id] != nil { parts.append("dans tes contacts") }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    @ViewBuilder
    private func actions(_ m: MemberMini) -> some View {
        VStack(spacing: 8) {
            HStack(spacing: 10) {
                if writeDirect != nil && !m.restricted {
                    PeoplePinkButton(title: "Envoyer un message", systemImage: "bubble.left", busy: writing) {
                        // CGU pas encore acceptées : la base répond « none » ; le bouton ouvre les conditions en grand.
                        if needsTerms { Haptics.tap(); askTerms = true } else { write() }
                    }
                        .disabled((!m.canWrite && !needsTerms) || m.blocked)
                        .accessibilityIdentifier("mini-profile-write")
                }
                PeopleGhostButton(title: "Fiche", systemImage: "person") { showCard = true }
                    .accessibilityIdentifier("mini-profile-card")
            }
            if let reason = disabledReason(m) ?? problem {
                Text(reason).font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                    .accessibilityIdentifier("mini-profile-reason")
            } else if writeDirect != nil, m.link == "request", m.chat == nil {
                Text("Ce sera une demande de message : \(shownName) choisira de l'accepter.")
                    .font(.footnote).foregroundStyle(PronoTheme.t3).multilineTextAlignment(.center)
            }
        }
    }

    /// Bouton désactivé : la raison (jamais « elle t'a bloqué »).
    private func disabledReason(_ m: MemberMini) -> String? {
        if m.blocked { return "Tu as bloqué \(shownName) : elle ne peut plus t'écrire, te citer ni t'inviter. Débloque-la pour lui écrire." }
        guard writeDirect != nil, !m.restricted else { return nil }
        if needsTerms { return TermsLater.message("écrire", button: "Envoyer un message") }
        if !m.canWrite { return "Tu ne peux pas lui écrire pour l'instant." }
        return nil
    }

    private func section<C: View>(_ title: String, @ViewBuilder rows: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: title)
            rows()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func eventRow(id: String, title: String, start: String?, sub: String?, past: Bool) -> some View {
        Button {
            Haptics.tap()
            dismiss()
            people?.openEvent(id)
        } label: {
            HStack(spacing: 14) {
                PeopleDateTile(start: start, past: past)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.headline).foregroundStyle(PronoTheme.t1).lineLimit(2).multilineTextAlignment(.leading)
                    if let sub { Text(sub).font(.subheadline).foregroundStyle(PronoTheme.t2).lineLimit(1) }
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t3)
            }
            .padding(12)
            .frame(minHeight: 72)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(PronoTheme.line, lineWidth: 1))
        }
        .buttonStyle(PronoKitPressStyle())
        .accessibilityLabel([title, PeopleDate.spoken(start), sub].compactMap { $0 }.joined(separator: ", "))
        .accessibilityHint("Ouvre la fiche de la soirée")
    }

    private func groups(_ m: MemberMini) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "En commun")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(m.groups) { g in
                        HStack(spacing: 10) {
                            GroupTile(emoji: g.emoji ?? "👯", color: g.color, photo: g.photo, size: 32)
                            Text(g.name).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                        }
                        .padding(.leading, 8).padding(.trailing, 16)
                        .frame(minHeight: 48)
                        .background(PronoTheme.s1, in: Capsule())
                        .overlay(Capsule().strokeBorder(PronoTheme.line2, lineWidth: 1))
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            .accessibilityLabel("Groupes en commun : " + m.groups.map(\.name).joined(separator: ", "))
        }
    }

    @ViewBuilder
    private func safety(_ m: MemberMini) -> some View {
        HStack(spacing: 6) {
            if m.blocked {
                Button { Task { await setBlocked(false) } } label: { Label("Débloquer", systemImage: "circle.slash") }
                    .accessibilityIdentifier("mini-profile-unblock")
            } else {
                Button { confirmBlock = true } label: { Label("Bloquer", systemImage: "circle.slash") }
                    .accessibilityIdentifier("mini-profile-block")
            }
            Text("·").foregroundStyle(PronoTheme.t3).accessibilityHidden(true)
            Button { reporting = ReportTarget(kind: .profile, id: m.id, label: shownName) } label: { Label("Signaler", systemImage: "flag") }
                .accessibilityIdentifier("mini-profile-report")
        }
        .font(.body)
        .foregroundStyle(PronoTheme.t2)
        .buttonStyle(.plain)
        .frame(minHeight: 44)
        .labelStyle(.titleAndIcon)
    }

    private func failed(_ error: String) -> some View {
        VStack(spacing: 12) {
            Text(error).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
            Button("Réessayer") { self.error = nil; Task { await load() } }.foregroundStyle(PronoTheme.lav).frame(minHeight: 44)
        }
        .padding(.top, 24)
        .padding(.horizontal, PronoTheme.Space.screen)
    }

    // MARK: Actions

    private func load() async {
        guard let people else { error = "Les profils ne sont pas disponibles pour l'instant."; return }
        do {
            let m = try await people.mini(userID)
            if m.link == "none" && !m.restricted {
                needsTerms = !(await people.moderation.termsAccepted())
            } else {
                needsTerms = false
            }
            Motion.animate(Motion.smooth) { mini = m }
        } catch {
            self.error = PeopleStore.message(error)
        }
    }

    /// Conditions acceptées : on relit le lien (la base ne disait « none » qu'à cause d'elles), puis on écrit.
    private func afterTerms() {
        Task {
            await load()
            if let m = mini, m.canWrite, !m.blocked { write() }
        }
    }

    private func write() {
        guard let writeDirect, !writing else { return }
        Haptics.tap()
        writing = true
        problem = nil
        Task {
            let result = await writeDirect.open(userID)
            writing = false
            switch result {
            case .opened: dismiss()
            case .termsRequired: askTerms = true
            case .refused(let message): problem = message
            }
        }
    }

    private func setBlocked(_ on: Bool) async {
        guard let people else { return }
        people.moderation.error = nil
        await people.moderation.setBlocked(userID, on)
        if let failure = people.moderation.error {
            problem = failure  // refus ou réseau : on le dit, l'écran ne prétend rien
            return
        }
        problem = nil
        // L'écran change aussitôt (« Débloquer », raison), sans attendre la relecture (recette du 26.11 : rien ne bougeait).
        Motion.animate(Motion.smooth) { mini?.blocked = on }
        if on { Haptics.success() }
        NotificationCenter.default.post(name: .partyBlockChanged, object: userID)  // la liste des Discussions se relit
        await load()
        if mini?.blocked != on { mini?.blocked = on }  // relecture en retard : le geste fait foi
    }
}

extension Notification.Name {
    /// Blocage posé ou levé depuis un mini-profil : la liste des Discussions se relit (conversation masquée aussitôt).
    static let partyBlockChanged = Notification.Name("PartyBlockChanged")
}

private extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}

// MARK: - Câblage

/// Toucher d'un nom / d'une photo → mini-profil. Sans Discussions (`\.people` nil) ou sans personne : rien ne change.
private struct MiniProfileTap: ViewModifier {
    let userID: String?
    @Environment(\.people) private var people
    @State private var shown = false

    func body(content: Content) -> some View {
        if let userID, people != nil {
            content
                .contentShape(Rectangle())
                .onTapGesture { Haptics.tap(); shown = true }
                .accessibilityAddTraits(.isButton)
                .accessibilityHint("Ouvre son profil")
                .sheet(isPresented: $shown) { MiniProfileSheet(userID: userID) }
        } else {
            content
        }
    }
}

extension View {
    /// Ouvre le mini-profil de cette personne au toucher (nil : moi, ou personne).
    func opensMiniProfile(_ userID: String?) -> some View { modifier(MiniProfileTap(userID: userID)) }
}

/// Feuille « profil » des écrans natifs (Mes amis, Réglages › Groupes) : le mini-profil quand Discussions est là,
/// sinon la fiche native d'avant.
struct PersonProfileSheet: View {
    let userID: String
    let privacy: PrivacyStore
    @Environment(\.people) private var people

    var body: some View {
        if people != nil { MiniProfileSheet(userID: userID) } else { MemberCardView(store: privacy, memberID: userID) }
    }
}
