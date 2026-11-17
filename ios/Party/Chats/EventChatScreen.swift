import SwiftUI

/// Discussion DANS un événement (17.11.2026), façon WhatsApp : l'écran arrive de la droite par-dessus la fiche, comme une
/// page poussée ; « ‹ » ou un glissé depuis le bord gauche y ramène. En-tête sur mesure : couverture ronde de l'événement,
/// titre, « sam. 21 nov. · 12 participants » (un toucher ouvre les infos), cloche du niveau de notifications à droite
/// (Tout, Mentions seulement par défaut, Rien ; sourdine). Le fil et la barre de saisie : ConversationView embarquée.
struct EventChatScreen: View {
    @ObservedObject var store: ChatsStore
    let eventID: String
    let onClose: () -> Void
    /// « Réglages » demandés par la page (PartyNative.chat.openEventSettings) : les infos s'ouvrent d'emblée.
    var info: Binding<Bool>? = nil

    @State private var localInfo = false
    /// Glissé depuis le bord gauche : déplacement de l'écran vers la droite.
    @State private var dragX: CGFloat = 0

    private var showInfo: Binding<Bool> { info ?? $localInfo }
    private var chat: Conversation? { store.conversation?.id == eventID ? store.conversation : nil }
    private var title: String { chat?.eventCard?.title ?? chat?.name ?? "Discussion" }

    var body: some View {
        GeometryReader { proxy in
            VStack(spacing: 0) {
                header
                ConversationView(store: store, group: eventID, embedded: true)
            }
            .background(AppConfig.background.ignoresSafeArea())
            .overlay(alignment: .leading) { edgeSwipe(width: proxy.size.width) }
            .shadow(color: .black.opacity(dragX > 0 ? 0.35 : 0), radius: 12, x: -4)
            .offset(x: dragX)
        }
        .sheet(isPresented: showInfo) { EventChatInfoView(store: store) }
        // Pas de bannière pour la discussion qu'on lit (agent G).
        .onAppear { ChatNotificationActions.visibleThread = "event-chat:\(eventID)" }
        .onDisappear { ChatNotificationActions.visibleThread = nil }
    }

    // MARK: En-tête façon WhatsApp

    private var header: some View {
        HStack(spacing: 6) {
            Button(action: close) {
                Image(systemName: "chevron.backward")
                    .font(.title3.weight(.semibold))
                    .frame(width: 36, height: 44)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("Retour à l'événement")
            .accessibilityIdentifier("event-chat-close")

            Button { showInfo.wrappedValue = true } label: {
                HStack(spacing: 10) {
                    Initials(name: title, photo: chat?.eventCard?.cover, size: 38)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(title).font(.headline).lineLimit(1)
                        Text(subtitle).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(chat == nil)
            // Libellé gardé pour la recette (RecetteDiscussionUITests) : le titre et la date suivent en valeur.
            .accessibilityLabel("Participants et notifications")
            .accessibilityValue("\(title), \(subtitle)")
            .accessibilityHint("Ouvre les infos de la discussion")
            .accessibilityIdentifier("event-chat-info")

            bell
        }
        .padding(.leading, 4)
        .padding(.trailing, 8)
        .padding(.vertical, 4)
        .tint(Palette.accent)
        .background(.bar, ignoresSafeAreaEdges: .top)
        .overlay(alignment: .bottom) { Divider() }
    }

    private var subtitle: String {
        guard let chat else { return "Discussion de l'événement" }
        let card = chat.eventCard
        return Self.subtitle(startsAt: card?.startsAt,
                             participants: Self.participants(going: card?.going, maybe: card?.maybe, members: chat.members))
    }

    // MARK: Cloche : niveau de notifications et sourdine

    private var bell: some View {
        let level = store.effectiveLevel
        let muted = store.isMuted
        return Menu {
            Picker("Notifications", selection: Binding(get: { level }, set: { new in
                Haptics.selection()
                Task { await store.setLevel(new) }
            })) {
                Text("Tout").tag(ChatNotifyLevel.all)
                Text("Mentions seulement").tag(ChatNotifyLevel.mentions)
                Text("Rien").tag(ChatNotifyLevel.none)
            }
            Section {
                if muted {
                    Button {
                        Task { await store.mute(until: nil) }
                    } label: { Label("Réactiver", systemImage: "bell") }
                }
                Menu {
                    Button("8 heures") { mute(for: 8 * 3600) }
                    Button("1 semaine") { mute(for: 7 * 86400) }
                    Button("Toujours") { Task { await store.mute(until: .distantFuture) } }
                } label: {
                    Label(Self.muteNote(mutedUntil: chat?.mutedUntil).map { "Sourdine · \($0)" } ?? "Sourdine", systemImage: "moon.zzz")
                }
            }
            Section {
                Button { showInfo.wrappedValue = true } label: { Label("Réglages…", systemImage: "gearshape") }
            }
        } label: {
            Image(systemName: Self.bellSymbol(level: level, muted: muted))
                .font(.title3)
                .frame(width: 40, height: 44)
                .contentShape(Rectangle())
        }
        .disabled(chat == nil)
        .accessibilityLabel(Self.bellLabel(level: level, muted: muted))
        .accessibilityIdentifier("event-chat-bell")
    }

    private func mute(for seconds: TimeInterval) {
        Haptics.selection()
        Task { await store.mute(until: Date().addingTimeInterval(seconds)) }
    }

    // MARK: Retour

    private func close() {
        Haptics.tap()
        onClose()
    }

    /// Bande au bord gauche : glisser vers la droite ramène à la fiche, comme le retour d'une page iOS.
    private func edgeSwipe(width: CGFloat) -> some View {
        Color.clear
            .frame(width: 20)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 8, coordinateSpace: .global)
                    .onChanged { dragX = max(0, $0.translation.width) }
                    .onEnded { value in
                        if Self.closesOnRelease(translation: value.translation.width,
                                                predicted: value.predictedEndTranslation.width, width: width) {
                            onClose()
                        } else {
                            Motion.animate(Motion.snappy) { dragX = 0 }
                        }
                    }
            )
            .accessibilityHidden(true)
    }
}

// MARK: Logique pure (EventChatScreenTests)

extension EventChatScreen {
    /// Icône de la cloche : bell (Tout), bell.badge (Mentions seulement), bell.slash (Rien, ou en sourdine).
    static func bellSymbol(level: ChatNotifyLevel, muted: Bool) -> String {
        if muted || level == .none { return "bell.slash" }
        return level == .all ? "bell" : "bell.badge"
    }

    static func bellLabel(level: ChatNotifyLevel, muted: Bool) -> String {
        if muted { return "Notifications en sourdine" }
        switch level {
        case .all: return "Notifications : tous les messages"
        case .mentions: return "Notifications : mentions seulement"
        case .none: return "Notifications : aucune"
        }
    }

    /// Participants = Présent + Peut-être (compteurs de la fiche ; sinon les réponses des personnes de la discussion).
    static func participants(going: Int?, maybe: Int?, members: [Conversation.Member]) -> Int {
        if going != nil || maybe != nil { return (going ?? 0) + (maybe ?? 0) }
        return members.filter { $0.rsvp == "yes" || $0.rsvp == "maybe" }.count
    }

    private static let zurich = TimeZone(identifier: "Europe/Zurich") ?? .current

    private static func formatter(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = zurich
        f.dateFormat = format
        return f
    }

    private static let dayFormat = formatter("EEE d MMM")
    private static let dayYearFormat = formatter("EEE d MMM yyyy")
    private static let hourFormat = formatter("HH:mm")

    /// « sam. 21 nov. · 12 participants » ; l'année seulement si ce n'est pas celle d'aujourd'hui ; sans date : « Date à
    /// définir » ; sans participant : la date seule.
    static func subtitle(startsAt: String?, participants: Int, now: Date = Date()) -> String {
        var day = "Date à définir"
        if let date = ChatDates.parse(startsAt) {
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = zurich
            let sameYear = calendar.component(.year, from: date) == calendar.component(.year, from: now)
            day = (sameYear ? dayFormat : dayYearFormat).string(from: date)
        }
        guard participants > 0 else { return day }
        return "\(day) · \(participants) participant\(participants > 1 ? "s" : "")"
    }

    /// Sourdine en cours : « jusqu'à 22:30 » (aujourd'hui), « jusqu'au sam. 21 nov. », « toujours » ; nil sinon.
    static func muteNote(mutedUntil: String?, now: Date = Date()) -> String? {
        guard let until = ChatDates.parse(mutedUntil) ?? (mutedUntil == "infinity" ? .distantFuture : nil), until > now else { return nil }
        if until.timeIntervalSince(now) > 10 * 365 * 86400 { return "toujours" }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zurich
        if calendar.isDate(until, inSameDayAs: now) { return "jusqu'à \(hourFormat.string(from: until))" }
        return "jusqu'au \(dayFormat.string(from: until))"
    }

    /// Fin du glissé : retour si l'écran a été tiré au-delà du tiers, ou lancé assez fort vers la droite.
    static func closesOnRelease(translation: CGFloat, predicted: CGFloat, width: CGFloat) -> Bool {
        translation > width / 3 || (translation > 20 && predicted > width / 2)
    }
}
