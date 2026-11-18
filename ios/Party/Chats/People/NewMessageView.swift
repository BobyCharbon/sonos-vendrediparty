import SwiftUI
import UIKit

/// « Nouveau message » (maquette 1-neon/2) : « À : » + puces des personnes choisies, recherche (prénom, nom, surnom ;
/// jamais par numéro), « Croisés récemment », « Dans tes groupes », « Tes contacts sur Party » (autorisation Contacts
/// demandée seulement au toucher de cette section ; accès limité accepté ; empreintes calculées sur l'iPhone).
/// Une personne → « Écrire à Léa » (demande de message si la base le dit) ; plusieurs → le groupe qui existe déjà avec
/// exactement elles, sinon « Créer un groupe avec … ». `eventID` : « Envoyer à un ami » depuis la fiche d'une soirée,
/// la carte de la soirée part dans la conversation.
struct NewMessageView: View {
    var eventID: String? = nil

    @Environment(\.people) private var people
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @ObservedObject private var contacts = ContactNames.shared

    @State private var suggestions: PeopleSuggestions?
    @State private var loadError: String?
    @State private var query = ""
    @State private var results: [ChatPerson]?
    @State private var selected: [ChatPerson] = []
    @State private var contactPeople: [ChatPerson]?
    @State private var loadingContacts = false
    @State private var event: ChatEventCard?
    @State private var busy = false
    @State private var problem: String?
    @State private var askTerms = false
    @State private var creatingGroup = false
    @FocusState private var searchFocused: Bool

    private var plan: NewMessagePlan { NewMessagePlan(selected) }
    private var searching: Bool { query.trimmingCharacters(in: .whitespaces).count >= 2 }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 26) {
                    toField
                    if let event { eventPreview(event) }
                    if people == nil {
                        note("Les Discussions ne sont pas disponibles pour l'instant.")
                    } else if searching {
                        searchResults
                    } else {
                        suggestionSections
                        contactsSection
                    }
                }
                .padding(.horizontal, PronoTheme.Space.screen)
                .padding(.top, 8)
                .padding(.bottom, 24)
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) { footer }
            .background(PeopleBackground())
            .navigationTitle(eventID == nil ? "Nouveau message" : "Envoyer à un ami")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }.foregroundStyle(PronoTheme.lav).accessibilityIdentifier("new-message-cancel")
                }
            }
            .navigationDestination(isPresented: $creatingGroup) {
                NewChatGroupView(members: selected, event: event) { group in finish(group) }
            }
            .sheet(isPresented: $askTerms) {
                if let people { TermsAcceptSheet(store: people.moderation) { accepted in if accepted { go() } } }
            }
            .task { await load() }
            .task(id: query) { await search() }
            .motion(Motion.snappy, value: selected)
            .motion(Motion.smooth, value: suggestions)
        }
        .tint(PronoTheme.lavA)
        .preferredColorScheme(.dark)
        .accessibilityIdentifier("new-message")
    }

    // MARK: « À : »

    private var toField: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text("À").font(.title3.weight(.semibold)).foregroundStyle(PronoTheme.t3).accessibilityHidden(true)
                PeopleFlow(spacing: 8) {
                    ForEach(selected) { p in chip(p) }
                }
            }
            TextField("Ajouter quelqu'un…", text: $query)
                .font(.title3)
                .foregroundStyle(PronoTheme.t1)
                .tint(PronoTheme.pink)
                .focused($searchFocused)
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .submitLabel(.search)
                .frame(minHeight: 44)
                .accessibilityLabel("Ajouter quelqu'un : prénom, nom ou surnom")
                .accessibilityIdentifier("new-message-search")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous)
            .strokeBorder(searchFocused ? PronoTheme.lavB.opacity(0.7) : PronoTheme.line2, lineWidth: searchFocused ? 2 : 1))
    }

    private func chip(_ p: ChatPerson) -> some View {
        Button { toggle(p) } label: {
            HStack(spacing: 8) {
                PronoAvatar(face: p.face, size: 30)
                Text(contacts.label(for: p.id, pseudo: p.short).primary).font(.body.weight(.semibold)).lineLimit(1)
                Image(systemName: "xmark").font(.footnote.weight(.bold))
            }
            .foregroundStyle(PronoTheme.fixed(0x1D1530))
            .padding(.leading, 6).padding(.trailing, 14)
            .frame(minHeight: 44)
            .background(PeopleNeon.lavenderTile, in: Capsule())
        }
        .buttonStyle(PronoKitPressStyle())
        .accessibilityLabel("Retirer \(p.short)")
        .transition(.scale(scale: 0.6).combined(with: .opacity))
    }

    private func eventPreview(_ e: ChatEventCard) -> some View {
        HStack(spacing: 14) {
            PeopleDateTile(start: e.start)
            VStack(alignment: .leading, spacing: 2) {
                Text(e.title).font(.headline).foregroundStyle(PronoTheme.t1).lineLimit(2)
                Text([PeopleDate.spoken(e.start), e.place].compactMap { $0 }.joined(separator: " · "))
                    .font(.subheadline).foregroundStyle(PronoTheme.t2).lineLimit(1)
            }
            Spacer(minLength: 0)
            Image(systemName: "paperplane.fill").foregroundStyle(PronoTheme.pinkInk).accessibilityHidden(true)
        }
        .padding(12)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(PronoTheme.amber.opacity(0.35), lineWidth: 1))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Soirée à envoyer : \(e.title)")
    }

    // MARK: Sections

    @ViewBuilder
    private var searchResults: some View {
        VStack(alignment: .leading, spacing: 4) {
            PeopleSectionLabel(text: "Résultats", systemImage: "magnifyingglass")
            if let results {
                if results.isEmpty {
                    note("Personne ne correspond. Cherche par prénom, nom ou surnom.")
                } else {
                    ForEach(results) { row($0) }
                }
            } else {
                ProgressView().tint(PronoTheme.lav).frame(maxWidth: .infinity).padding(.vertical, 20)
            }
        }
    }

    @ViewBuilder
    private var suggestionSections: some View {
        if let suggestions {
            let crossed = suggestions.row
            if !crossed.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    PeopleSectionLabel(text: "Croisés récemment", systemImage: "sparkle")
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(crossed) { bubble($0) }
                        }
                        .padding(.vertical, 4)
                        .padding(.horizontal, PronoTheme.Space.screen)
                    }
                    .padding(.horizontal, -PronoTheme.Space.screen)
                }
            }
            if !suggestions.groups.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    PeopleSectionLabel(text: "Dans tes groupes", systemImage: "person.2")
                    ForEach(suggestions.groups) { row($0) }
                }
            }
            if suggestions.isEmpty {
                note("Cherche quelqu'un par son prénom, son nom ou son surnom. Party te propose seulement les personnes que tu as croisées.")
            }
        } else if let loadError {
            note(loadError)
        } else {
            ProgressView().tint(PronoTheme.lav).frame(maxWidth: .infinity).padding(.vertical, 20)
        }
    }

    /// « Tes contacts sur Party » : rien n'est demandé à iOS avant le toucher.
    @ViewBuilder
    private var contactsSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            PeopleSectionLabel(text: "Tes contacts sur Party", systemImage: "person.crop.square.filled.and.at.rectangle")
            switch contacts.access {
            case .authorized, .limited:
                if let contactPeople {
                    if contactPeople.isEmpty {
                        note("Aucun de tes contacts n'est encore sur Party.")
                    } else {
                        ForEach(contactPeople) { row($0) }
                    }
                } else {
                    ProgressView().tint(PronoTheme.lav).frame(maxWidth: .infinity).padding(.vertical, 12)
                }
                if contacts.access == .limited {
                    note("Accès limité : seulement les contacts que tu as choisis pour Party.")
                }
            case .notDetermined:
                Button { Task { await askContacts() } } label: {
                    actionRow(icon: "person.crop.circle.badge.questionmark", title: "Trouver mes contacts sur Party",
                              sub: "Les numéros sont comparés sur ton iPhone, sous forme d'empreintes : rien n'est gardé.")
                }
                .buttonStyle(.plain)
                .disabled(loadingContacts)
                .accessibilityIdentifier("new-message-contacts")
            case .denied, .restricted:
                Button { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } } label: {
                    actionRow(icon: "gearshape", title: "Autoriser l'accès aux contacts",
                              sub: "Dans les Réglages d'iOS › Party › Contacts. Tout marche aussi sans.")
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func actionRow(icon: String, title: String, sub: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon).font(.title3).foregroundStyle(PronoTheme.lav)
                .frame(width: 48, height: 48)
                .background(PronoTheme.lavB.opacity(0.16), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.headline).foregroundStyle(PronoTheme.t1)
                Text(sub).font(.subheadline).foregroundStyle(PronoTheme.t2).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            if loadingContacts { ProgressView().tint(PronoTheme.lav) }
        }
        .padding(.vertical, 8)
        .contentShape(Rectangle())
    }

    /// Bulle de « Croisés récemment » : visage, prénom, soirée.
    private func bubble(_ p: ChatPerson) -> some View {
        let on = isSelected(p)
        return Button { toggle(p) } label: {
            VStack(spacing: 6) {
                PeopleFace(person: p, size: 64, selected: on)
                Text(contacts.label(for: p.id, pseudo: p.short).primary).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                Text(PeopleText.sub(p) ?? " ").font(.subheadline).foregroundStyle(PronoTheme.t3).lineLimit(1)
            }
            .frame(width: 84)
        }
        .buttonStyle(PronoKitPressStyle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11y(p))
        .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
    }

    /// Ligne : visage, nom (« Nom du contact · pseudo »), sous-titre, rond de sélection.
    private func row(_ p: ChatPerson) -> some View {
        let on = isSelected(p)
        let label = contacts.label(for: p.id, pseudo: p.name.isEmpty ? p.short : p.name)
        return Button { toggle(p) } label: {
            HStack(spacing: 14) {
                PronoAvatar(face: p.face, size: 48)
                VStack(alignment: .leading, spacing: 2) {
                    (Text(label.primary).foregroundColor(PronoTheme.t1)
                     + Text(label.secondary.map { " · \($0)" } ?? "").foregroundColor(PronoTheme.t2))
                        .font(.headline).lineLimit(1)
                    HStack(spacing: 6) {
                        if let sub = PeopleText.sub(p) { Text(sub).lineLimit(1) }
                        if p.isRequest {
                            Label("demande", systemImage: "envelope").labelStyle(.titleAndIcon).font(.caption.weight(.semibold))
                                .foregroundStyle(PronoTheme.t3)
                        }
                    }
                    .font(.subheadline).foregroundStyle(PronoTheme.t2)
                }
                Spacer(minLength: 8)
                PeopleCheck(on: on)
            }
            .padding(.vertical, 8)
            .frame(minHeight: 64)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11y(p))
        .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("new-message-person-\(p.id)")
    }

    private func note(_ text: String) -> some View {
        Text(text).font(.subheadline).foregroundStyle(PronoTheme.t2).fixedSize(horizontal: false, vertical: true)
            .padding(.vertical, 8)
    }

    private func a11y(_ p: ChatPerson) -> String {
        [contacts.label(for: p.id, pseudo: p.name.isEmpty ? p.short : p.name).primary, PeopleText.sub(p),
         p.isRequest ? "demande de message" : nil].compactMap { $0 }.joined(separator: ", ")
    }

    // MARK: Bas de l'écran

    @ViewBuilder
    private var footer: some View {
        if let title = plan.title {
            VStack(spacing: 10) {
                if let problem {
                    Text(problem).font(.footnote).foregroundStyle(PronoTheme.pinkInk).multilineTextAlignment(.center)
                        .accessibilityIdentifier("new-message-problem")
                }
                if let note = plan.note {
                    HStack(spacing: 10) {
                        if case .group(let people) = plan {
                            PronoAvatarStack(faces: people.map(\.face), size: 26, ring: PronoTheme.bg, max: 3)
                        } else {
                            Image(systemName: "envelope").foregroundStyle(PronoTheme.lav)
                        }
                        Text(note).font(.subheadline).foregroundStyle(PronoTheme.t2).lineLimit(2)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("new-message-note")
                }
                PeoplePinkButton(title: title, systemImage: selected.count > 1 ? "person.2" : "bubble.left", busy: busy) { go() }
                    .id(selected.count > 1)
                    .transition(.opacity)
                    .accessibilityIdentifier("new-message-go")
            }
            .padding(.horizontal, PronoTheme.Space.screen)
            .padding(.top, 12)
            .padding(.bottom, 8)
            .background(PronoTheme.bg.opacity(0.94).ignoresSafeArea(edges: .bottom))
            .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    // MARK: Actions

    private func isSelected(_ p: ChatPerson) -> Bool { selected.contains { $0.id == p.id } }

    private func toggle(_ p: ChatPerson) {
        Haptics.selection()
        problem = nil
        if let i = selected.firstIndex(where: { $0.id == p.id }) {
            selected.remove(at: i)
        } else if selected.count < NewMessagePlan.maxPeople {
            selected.append(p)
            query = ""
        }
    }

    private func load() async {
        guard let people else { return }
        if let eventID { event = await people.eventCard(eventID) }
        do {
            suggestions = try await people.suggestions()
        } catch {
            loadError = PeopleStore.message(error)
        }
        if contacts.access.canRead, contactPeople == nil { contactPeople = await people.contactPeople() }
    }

    private func search() async {
        guard let people else { return }
        guard searching else { results = nil; return }
        results = nil
        try? await Task.sleep(nanoseconds: 250_000_000)  // on attend la fin de la frappe
        guard !Task.isCancelled else { return }
        let found = (try? await people.search(query)) ?? []
        guard !Task.isCancelled else { return }
        results = found
    }

    /// Le toucher de la section demande l'accès (fenêtre d'iOS), puis la comparaison sur l'iPhone.
    private func askContacts() async {
        guard let people else { return }
        loadingContacts = true
        defer { loadingContacts = false }
        await contacts.requestAccess()
        if contacts.access.canRead { contactPeople = await people.contactPeople() }
    }

    private func go() {
        guard let people, !busy else { return }
        Haptics.tap()
        problem = nil
        switch plan {
        case .none: return
        case .direct(let p, _):
            busy = true
            Task {
                defer { busy = false }
                switch await people.resolveDirect(p.id) {
                case .chat(let chat):
                    if let event {
                        do { try await people.sendEvent(event, to: chat, direct: true) } catch {
                            problem = "La soirée n'est pas partie : \(PeopleStore.message(error))"
                            return
                        }
                    }
                    finish(chat)
                case .terms: askTerms = true
                case .refused(let message): problem = message
                }
            }
        case .group(let list):
            busy = true
            Task {
                defer { busy = false }
                do {
                    if let existing = try await people.groupWith(list.map(\.id)) {
                        if let event { try? await people.sendEvent(event, to: existing, direct: false) }
                        finish(existing)
                    } else {
                        creatingGroup = true
                    }
                } catch {
                    problem = PeopleStore.message(error)
                }
            }
        }
    }

    /// La conversation s'ouvre dans l'onglet Discussions natif ; cet écran se ferme.
    private func finish(_ chat: String) {
        Haptics.success()
        people?.openChat(chat)
        dismiss()
    }
}
