import SwiftUI

/// Réglages › Notifications : un interrupteur par type, rangés par catégorie (cet iPhone, Musique, Jeux, Ton avis,
/// Événements). Chaque choix est enregistré tout de suite ; un échec remet l'interrupteur et l'explique.
struct NotificationSettingsView: View {
    @ObservedObject var store: SettingsStore

    var body: some View {
        List {
            device
            music
            games
            feedback
            events
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        // Réglages relus après l'affichage (autorisation iOS, invité reconnu, mode hôte) : les lignes qui
        // apparaissent ou s'en vont glissent en place au lieu de faire sauter la liste.
        .motion(Motion.smooth, value: store.permission)
        .motion(Motion.smooth, value: store.hostMode)
        .motion(Motion.smooth, value: store.guest == nil)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await store.loadNotifications() }
        .task { await store.loadNotifications() }
        .overlay(alignment: .bottom) { SettingsNoticeBanner(store: store) }
    }

    // MARK: Général

    @ViewBuilder
    private var device: some View {
        Section {
            if store.permission == "denied" {
                Button(action: store.openSystemSettings) {
                    SettingsRow(symbol: "exclamationmark.triangle.fill", tint: .orange, title: "Notifications bloquées",
                                hint: "Touche ici pour les autoriser dans les réglages de l'iPhone")
                }
                .foregroundStyle(.primary)
            }
            toggle("device", "iphone.radiowaves.left.and.right", .green, "Notifications sur cet iPhone",
                   "Musique, jeux et réponses à tes avis arrivent ici", isOn: store.deviceSubscribed,
                   enabled: store.guest != nil) { on in await store.setDevice(on) }
        } header: {
            Text("Général")
        } footer: {
            Text(store.guest == nil && !store.hostMode
                 ? "Entre le code de la soirée (onglet Musique) pour choisir les notifications de la soirée."
                 : "Chaque type se choisit ci-dessous. Les événements ont leurs propres réglages, plus bas.")
        }
    }

    // MARK: Soirée

    private var music: some View {
        Section {
            guestToggle("track", "music.note", .pink, "Mon titre passe", "Quand le titre que tu as ajouté démarre")
            Toggle(isOn: Binding(get: { store.liveActivities }, set: { store.setLiveActivities($0) })) {
                SettingsRow(symbol: "timer", tint: .purple, title: "Décompte dans la Dynamic Island",
                            hint: "« Ton titre arrive » sur l'écran verrouillé et en haut de l'écran, avant ton titre")
            }
            if store.hostMode {
                hostToggle("messages", "bubble.left.fill", .blue, "Messages des invités", "Un invité t'écrit depuis l'écran Musique")
            }
        } header: {
            Text("🎵 Musique")
        } footer: {
            Text("Le décompte est un réglage de cet iPhone ; il ne dépend pas des notifications.")
        }
    }

    private var games: some View {
        Section("🎮 Jeux") {
            // L'hôte reçoit déjà chaque nouvelle partie en tant qu'hôte : un seul réglage, pas de doublon.
            if store.hostMode {
                hostToggle("games", "gamecontroller.fill", .orange, "Quelqu'un lance une partie", "Le jeu et son code, pour suivre ou fermer la partie")
            } else {
                guestToggle("games", "gamecontroller.fill", .orange, "Nouvelle partie lancée", "Quelqu'un lance un jeu : rejoins-le d'un toucher")
            }
        }
    }

    private var feedback: some View {
        Section("💬 Ton avis") {
            guestToggle("feedback", "arrowshape.turn.up.left.fill", .green, "Réponse à mes avis",
                        "Ton idée ou ton bug est terminé, ou l'organisateur te répond")
            if store.hostMode {
                hostToggle("feedback", "lightbulb.fill", .yellow, "Nouvel avis reçu", "Un invité envoie une idée ou signale un bug")
            }
        }
    }

    // MARK: Événements

    @ViewBuilder
    private var events: some View {
        switch store.events {
        case .signedOut:
            Section {
                NavigationLink { SignInView(store: store.session) } label: {
                    SettingsRow(symbol: "calendar", tint: .red, title: "Se connecter pour les événements",
                                hint: "Nouveaux événements, sondages, rappels et discussions")
                }
            } header: {
                Text("📅 Événements")
            }
        case .loading:
            Section("📅 Événements") { ProgressView().frame(maxWidth: .infinity) }
        case .failed(let message):
            Section("📅 Événements") {
                Text(message).foregroundStyle(.secondary)
                Button("Réessayer") { Task { await store.loadNotifications() } }
            }
        case .ready(let state):
            eventSections(state)
        }
    }

    @ViewBuilder
    private func eventSections(_ state: EventNotifyState) -> some View {
        let p = state.prefs
        Section {
            eventToggle("push_enabled", "bell.fill", .red, "Recevoir mes alertes d'événements",
                        "Éteins pour couper les alertes ci-dessous sans perdre tes choix", p.pushEnabled)
            toggle("events.quiet", "moon.fill", .indigo, "Heures de silence",
                   "Rien ne sonne pendant cette plage, pas même les annonces : tout arrive à la fin",
                   isOn: p.hasQuietHours) { on in await store.setQuietHours(on) }
            if p.hasQuietHours {
                quietPicker("De", start: true, p.quietStart)
                quietPicker("À", start: false, p.quietEnd)
            }
        } header: {
            Text("📅 Événements · général")
        }

        Section {
            Picker("Me prévenir", selection: choice("new_event", p.newEvent)) {
                ForEach(EventChoices.newEvent, id: \.key) { Text($0.label).tag($0.key) }
            }
            .pickerStyle(.segmented)
            .disabled(store.saving.contains("events.new_event"))
            if p.newEvent == "subscribed" {
                NavigationLink {
                    SubscriptionsView(store: store)
                } label: {
                    SettingsRow(symbol: "tag.fill", tint: .orange, title: "Choisir mes catégories et tags",
                                hint: store.subscriptions.map { "\($0.count) suivi\($0.count > 1 ? "s" : "")" })
                }
            }
        } header: {
            Text("Nouvel événement publié")
        } footer: {
            Text(EventChoices.hint(EventChoices.newEvent, for: p.newEvent))
        }

        Section("Événements où je suis inscrit") {
            eventToggle("event_changed", "calendar.badge.exclamationmark", .red, "Modifié ou annulé", "Date, heure ou lieu changé, ou annulation", p.eventChanged)
            eventToggle("poll_new", "chart.bar.fill", .blue, "Nouveau sondage", "L'organisateur ajoute un sondage", p.pollNew)
            eventToggle("date_fixed", "calendar.badge.checkmark", .green, "Date choisie", "Le sondage de dates est terminé, la date est fixée", p.dateFixed)
            eventToggle("poll_nudge", "hand.raised.fill", .orange, "Rappel pour voter", "24 h avant la fin d'un sondage de dates, si tu n'as pas voté", p.pollNudge)
            eventToggle("waitlist", "person.crop.circle.badge.plus", .teal, "Place libérée", "Tu es sur liste d'attente et une place se libère", p.waitlist)
            eventToggle("rsvp_set", "person.crop.circle.badge.checkmark", .indigo, "Un organisateur répond pour moi",
                        "Il te note présent, peut-être ou absent à ta place", p.rsvpSet != false)
            eventToggle("invites", "envelope.fill", .purple, "Invitation à un événement privé", "On t'invite à un événement réservé aux invités", p.invites != false)
            eventToggle("ticket_pay_confirmed", "checkmark.seal.fill", .green, "Paiement de ma place confirmé",
                        "L'organisateur a reçu ton paiement (ou ne l'a pas reçu) après ton « J'ai payé »", p.ticketPayConfirmed != false)
        }

        Section {
            ForEach(EventChoices.reminders, id: \.key) { reminder in
                toggle("events.reminders." + reminder.key, "alarm.fill", .orange, reminder.label, nil,
                       isOn: p.reminders.contains(reminder.key)) { on in await store.toggleReminder(reminder.key, on) }
            }
        } header: {
            Text("Rappels avant l'événement")
        } footer: {
            Text("Pour les événements où tu as répondu Présent ou Peut-être. Coche-en autant que tu veux.")
        }

        Section {
            Picker("Messages", selection: choice("chat", p.chat)) {
                ForEach(EventChoices.chat, id: \.key) { Text($0.label).tag($0.key) }
            }
            .pickerStyle(.segmented)
            .disabled(store.saving.contains("events.chat"))
            // Deux sourdines distinctes (avis de l'admin) : discussions des événements ici, groupes plus bas.
            ChatsPauseRow(store: store.pause, scope: .eventChats)
        } header: {
            Text("Discussions des événements")
        } footer: {
            Text(EventChoices.hint(EventChoices.chat, for: p.chat))
        }

        Section("💬 Discussions des groupes") {
            eventToggle("group_messages", "bubble.left.and.bubble.right.fill", .green, "Messages des groupes",
                        "Selon le choix de chaque groupe : tous, si on me cite ou rien", p.groupMessages != false)
            ChatsPauseRow(store: store.pause, scope: .chats)
            // Groupes de Discussions : @tout et @annonce préviennent tout le groupe ; chacun peut le couper ici.
            eventToggle("group_broadcasts", "megaphone.fill", .pink, "Annonces et @tout des groupes",
                        "Quand quelqu'un écrit @tout ou fait une annonce dans un de tes groupes", p.groupBroadcasts != false)
            eventToggle("group_invites", "person.badge.plus", .blue, "Invitation dans un groupe", "Quelqu'un t'ajoute à un groupe", p.groupInvites != false)
            eventToggle("group_joins", "person.2.fill", .teal, "Quelqu'un rejoint mon groupe", "Un membre entre dans un groupe que tu as créé", p.groupJoins != false)
        }

        Section("Quand j'organise") {
            eventToggle("rsvp_mine", "person.3.fill", .blue, "Réponses à mes événements", "Quelqu'un répond Présent, Peut-être ou Absent", p.rsvpMine)
            eventToggle("link_join", "link", .blue, "Quelqu'un rejoint par le lien", "Une personne s'inscrit avec le lien d'invitation", p.linkJoin != false)
            eventToggle("ticket_pay_declared", "banknote.fill", .orange, "Quelqu'un dit avoir payé",
                        "Sur un événement payant que j'organise : à confirmer quand tu as reçu l'argent", p.ticketPayDeclared != false)
            eventToggle("proposal_result", "checkmark.circle.fill", .green, "Ma proposition validée ou refusée",
                        "Un admin publie ou refuse l'événement que tu as proposé", p.proposalResult != false)
            if state.approver {
                eventToggle("proposals", "checkmark.seal.fill", .indigo, "Proposition à valider", "Un membre propose un événement à valider", p.proposals)
            }
        }

        Section {
            eventToggle("announcements", "megaphone.fill", .pink, "Annonces des admins",
                        "Les messages des admins à tout le groupe ; coupées, elles restent lisibles", p.announcements != false)
            NavigationLink { AnnouncementsView(store: store.session, canPublish: false) } label: {
                SettingsRow(symbol: "text.bubble.fill", tint: .gray, title: "Lire les annonces des admins")
            }
        } footer: {
            Text("Pour couper un seul événement, utilise « Sourdine » sur sa page.")
        }
    }

    // MARK: Éléments

    private func guestToggle(_ kind: String, _ symbol: String, _ tint: Color, _ title: String, _ hint: String) -> some View {
        toggle(kind, symbol, tint, title, hint, isOn: store.deviceSubscribed && store.guest?.prefs[kind] == true,
               enabled: store.guest != nil) { on in await store.setGuest(kind, on) }
    }

    private func hostToggle(_ kind: String, _ symbol: String, _ tint: Color, _ title: String, _ hint: String) -> some View {
        toggle("host." + kind, symbol, tint, title, hint + " · hôte",
               isOn: store.permission == "granted" && store.host?.prefs[kind] == true) { on in await store.setHost(kind, on) }
    }

    private func eventToggle(_ key: String, _ symbol: String, _ tint: Color, _ title: String, _ hint: String, _ value: Bool) -> some View {
        toggle("events." + key, symbol, tint, title, hint, isOn: value) { on in await store.setEvents(key, on) }
    }

    private func toggle(_ key: String, _ symbol: String, _ tint: Color, _ title: String, _ hint: String?, isOn: Bool,
                        enabled: Bool = true, change: @escaping (Bool) async -> Void) -> some View {
        Toggle(isOn: Binding(get: { isOn }, set: { on in Task { await change(on) } })) {
            SettingsRow(symbol: symbol, tint: tint, title: title, hint: hint)
        }
        .disabled(!enabled || store.saving.contains(key))
    }

    private func choice(_ key: String, _ value: String) -> Binding<String> {
        Binding(get: { value }, set: { new in Task { await store.setEvents(key, new) } })
    }

    private func quietPicker(_ label: String, start: Bool, _ value: String?) -> some View {
        DatePicker(label, selection: Binding(get: { QuietTime.date(value) },
                                             set: { date in Task { await store.setQuietTime(start: start, date) } }),
                   displayedComponents: .hourAndMinute)
            .disabled(store.saving.contains(start ? "events.quiet_start" : "events.quiet_end"))
    }
}

/// Confirmation ou erreur d'enregistrement des Réglages, en bas de l'écran, 3 secondes.
struct SettingsNoticeBanner: View {
    @ObservedObject var store: SettingsStore

    var body: some View {
        NoticeBanner(notice: store.notice.map { NoticeBanner.Notice(text: $0.text, isError: $0.isError) }) { store.notice = nil }
    }

}
