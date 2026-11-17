import SwiftUI

/// Réglages de la discussion d'un événement, façon WhatsApp : mes notifications (Tout / Mentions seulement / Rien,
/// Mentions seulement par défaut) et la sourdine (8 h, 1 semaine, toujours) ; pour l'organisation, qui peut écrire et la
/// description (filtrée par la base) ; les messages épinglés. Ouverts depuis les infos (EventChatInfoView) ou la cloche
/// de l'en-tête (feuilles *Sheet).
enum EventChatText {
    static let levels: [ChatNotifyLevel] = [.all, .mentions, .none]

    static func title(_ level: ChatNotifyLevel) -> String {
        switch level {
        case .all: return "Tout"
        case .mentions: return "Mentions seulement"
        case .none: return "Rien"
        }
    }

    static func hint(_ level: ChatNotifyLevel) -> String {
        switch level {
        case .all: return "Une notification pour chaque message."
        case .mentions: return "@ton nom, @toutlemonde, @present, annonces et réponses à tes messages."
        case .none: return "Aucune notification de cette discussion, même quand on te cite."
        }
    }

    static func icon(_ level: ChatNotifyLevel) -> String {
        switch level {
        case .all: return "bell.fill"
        case .mentions: return "at"
        case .none: return "bell.slash.fill"
        }
    }

    /// Fin de la sourdine : nil si la sourdine n'a pas de fin (« Toujours », 'infinity' ou date lointaine).
    static func muteEnd(_ value: String?) -> Date? {
        guard let date = ChatDates.parse(value), date.timeIntervalSinceNow < 10 * 365 * 24 * 3600 else { return nil }
        return date
    }

    static func muteLabel(_ value: String?) -> String {
        guard let end = muteEnd(value) else { return "En sourdine, toujours" }
        let fr = Locale(identifier: "fr_CH")
        let day = Calendar.current.isDateInToday(end) ? "aujourd'hui"
            : Calendar.current.isDateInTomorrow(end) ? "demain"
            : end.formatted(.dateTime.weekday(.wide).day().month(.wide).locale(fr))
        return "En sourdine jusqu'à \(day), \(end.formatted(date: .omitted, time: .shortened))"
    }

    /// Erreur de la base (« forbidden: Seule l'organisation… ») : la phrase seulement.
    static func clean(_ error: String) -> String {
        error.replacingOccurrences(of: "^[a-z_]+: ", with: "", options: .regularExpression)
    }
}

// MARK: Notifications et sourdine

struct EventChatNotificationsView: View {
    @ObservedObject var store: ChatsStore
    /// Choix touché, montré tout de suite (le serveur confirme en relisant la conversation).
    @State private var picked: ChatNotifyLevel?
    @State private var busy = false

    private var level: ChatNotifyLevel { picked ?? store.effectiveLevel }

    var body: some View {
        Form {
            Section {
                ForEach(EventChatText.levels, id: \.self) { option in
                    Button {
                        guard option != level else { return }
                        Haptics.selection()
                        Motion.animate { picked = option }
                        Task {
                            await store.setLevel(option)
                            picked = nil
                        }
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: EventChatText.icon(option))
                                .font(.body.weight(.semibold)).frame(width: 30, height: 30)
                                .foregroundStyle(.white)
                                .background(option == .none ? Color.gray : Color(uiColor: AppConfig.uiAccent), in: RoundedRectangle(cornerRadius: 7))
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text(EventChatText.title(option)).foregroundStyle(.primary)
                                    if option == .mentions {
                                        Text("par défaut").font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
                                            .padding(.horizontal, 6).padding(.vertical, 2).background(.quaternary, in: Capsule())
                                    }
                                }
                                Text(EventChatText.hint(option)).font(.caption).foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                            if option == level {
                                Image(systemName: "checkmark").font(.body.weight(.semibold)).foregroundStyle(.tint)
                                    .transition(.scale.combined(with: .opacity))
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityElement(children: .combine)
                    .accessibilityAddTraits(option == level ? .isSelected : [])
                    .accessibilityIdentifier("event-chat-level-\(option.rawValue)")
                }
            } header: {
                Text("Me prévenir")
            } footer: {
                Text("Pour cette discussion seulement. Les autres discussions suivent Réglages › Notifications.")
            }

            Section {
                if store.isMuted {
                    Label(EventChatText.muteLabel(store.conversation?.mutedUntil), systemImage: "moon.zzz.fill")
                        .foregroundStyle(.secondary)
                    Button {
                        Haptics.tap()
                        run { await store.mute(until: nil) }
                    } label: {
                        Label("Réactiver les notifications", systemImage: "bell.badge")
                    }
                    .accessibilityIdentifier("event-chat-unmute")
                } else {
                    muteButton("8 heures", hours: 8, id: "8h")
                    muteButton("1 semaine", hours: 24 * 7, id: "week")
                    Button {
                        Haptics.tap()
                        run { await store.mute(until: .distantFuture) }
                    } label: {
                        Label("Toujours", systemImage: "infinity")
                    }
                    .accessibilityIdentifier("event-chat-mute-always")
                }
            } header: {
                Text("Sourdine")
            } footer: {
                Text("En sourdine, plus aucune notification de cette discussion, même citée ; les messages restent là, non lus.")
            }
            .disabled(busy)
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .motion(Motion.snappy, value: level)
        .motion(Motion.smooth, value: store.isMuted)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func muteButton(_ title: String, hours: Double, id: String) -> some View {
        Button {
            Haptics.tap()
            run { await store.mute(until: Date().addingTimeInterval(hours * 3600)) }
        } label: {
            Label(title, systemImage: "moon.fill")
        }
        .accessibilityIdentifier("event-chat-mute-\(id)")
    }

    private func run(_ work: @escaping () async -> Void) {
        busy = true
        Task {
            await work()
            busy = false
        }
    }
}

/// La même page en feuille (menu de la cloche de l'en-tête).
struct EventChatNotificationsSheet: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            EventChatNotificationsView(store: store)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
    }
}

// MARK: Réglages de la discussion (organisation)

struct EventChatSettingsView: View {
    @ObservedObject var store: ChatsStore
    @State private var draft = ""
    @State private var loaded = false
    @State private var saving = false
    @State private var saved = false
    @State private var error: String?
    /// Choix touché, montré tout de suite.
    @State private var pickedWrite: String?
    @FocusState private var editing: Bool

    static let maxDescription = 500

    private var chat: Conversation? { store.conversation }
    private var writeMode: String { pickedWrite ?? chat?.writeMode ?? "all" }
    private var current: String { chat?.description ?? "" }
    private var changed: Bool { draft.trimmingCharacters(in: .whitespacesAndNewlines) != current.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        Form {
            if chat?.isStaff == true {
                Section {
                    writeRow("all", title: "Tout le monde", detail: "Invités et participants écrivent.", icon: "person.3.fill")
                    writeRow("staff", title: "Organisation seulement", detail: "Les autres lisent, réagissent et peuvent signaler.", icon: "megaphone.fill")
                } header: {
                    Text("Qui peut écrire")
                } footer: {
                    Text("Comme « Envoyer des messages » dans WhatsApp. L'organisation écrit toujours.")
                }

                Section {
                    TextField("Ajoute une description : programme, code vestimentaire, parking…", text: $draft, axis: .vertical)
                        .lineLimit(3...8)
                        .focused($editing)
                        .onChange(of: draft) { value in
                            if value.count > Self.maxDescription { draft = String(value.prefix(Self.maxDescription)) }
                            saved = false
                            error = nil
                        }
                        .accessibilityIdentifier("event-chat-description")
                    HStack {
                        Text("\(draft.count) / \(Self.maxDescription)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        Spacer()
                        if saved {
                            Label("Enregistrée", systemImage: "checkmark.circle.fill").font(.subheadline).foregroundStyle(.green)
                                .transition(.scale.combined(with: .opacity))
                        } else {
                            Button {
                                Task { await saveDescription() }
                            } label: {
                                if saving { ProgressView() } else { Text("Enregistrer").fontWeight(.semibold) }
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(!changed || saving)
                            .accessibilityIdentifier("event-chat-description-save")
                        }
                    }
                } header: {
                    Text("Description")
                } footer: {
                    Text("Montrée en haut des infos de la discussion. Les mots interdits sont refusés, comme dans les messages.")
                }

                if let error {
                    Section {
                        Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                    }
                    .transition(.opacity)
                }

                Section {
                    Label("@toutlemonde : prévient tous les invités et participants", systemImage: "person.3.fill")
                    Label("@present : prévient les présents et les peut-être", systemImage: "checkmark.circle.fill")
                    Label("Bouton annonce ou @annonce : épinglée en haut, envoyée à tous", systemImage: "megaphone.fill")
                } header: {
                    Text("Réservé à l'organisation")
                } footer: {
                    Text("Tu organises cet événement (ou tu es admin) : tu peux aussi épingler un message ou retirer celui d'un autre, d'un appui long.")
                }
                .font(.subheadline)
            } else {
                Section {
                    Text("Seule l'organisation de l'événement change ces réglages.").foregroundStyle(.secondary)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .motion(Motion.snappy, value: writeMode)
        .motion(Motion.smooth, value: error)
        .motion(Motion.bouncy, value: saved)
        .navigationTitle("Réglages de la discussion")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Terminé") { editing = false }
            }
        }
        .onAppear {
            guard !loaded else { return }
            loaded = true
            draft = current
        }
    }

    private func writeRow(_ mode: String, title: String, detail: String, icon: String) -> some View {
        Button {
            guard mode != writeMode else { return }
            Haptics.selection()
            Motion.animate { pickedWrite = mode }
            Task {
                let ok = await store.saveSettings(write: mode, description: nil)
                if !ok { fail() }
                pickedWrite = nil
            }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: icon).frame(width: 26).foregroundStyle(.tint)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).foregroundStyle(.primary)
                    Text(detail).font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                if mode == writeMode {
                    Image(systemName: "checkmark").font(.body.weight(.semibold)).foregroundStyle(.tint)
                        .transition(.scale.combined(with: .opacity))
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(mode == writeMode ? .isSelected : [])
        .accessibilityIdentifier("event-chat-write-\(mode)")
    }

    private func saveDescription() async {
        editing = false
        saving = true
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        let ok = await store.saveSettings(write: nil, description: text)
        saving = false
        if ok {
            Haptics.success()
            saved = true
        } else {
            fail()
        }
    }

    /// Refus de la base (mot interdit, droit) : dit ici, pas sous la feuille.
    private func fail() {
        Haptics.error()
        error = EventChatText.clean(store.notice ?? "Pas enregistré. Vérifie ta connexion et réessaie.")
        store.notice = nil
    }
}

/// La même page en feuille (« Réglages… » du menu de l'en-tête).
struct EventChatSettingsSheet: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            EventChatSettingsView(store: store)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
        }
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
    }
}

// MARK: Messages épinglés

/// Annonces puis messages épinglés (les plus récents d'abord) ; un toucher ramène au message dans la discussion.
struct EventChatPinnedView: View {
    @ObservedObject var store: ChatsStore
    let onJump: (String) -> Void

    var body: some View {
        List {
            let pins = store.conversation?.pins ?? []
            if pins.isEmpty {
                Section {
                    VStack(spacing: 10) {
                        Image(systemName: "pin.slash").font(.largeTitle).foregroundStyle(.secondary)
                        Text("Aucun message épinglé").font(.headline)
                        Text("L'organisation épingle un message d'un appui long ; les annonces s'y ajoutent d'office.")
                            .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 24)
                    .listRowBackground(Color.clear)
                }
            } else {
                ForEach(pins) { pin in
                    Button {
                        Haptics.tap()
                        onJump(pin.id)
                    } label: {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: pin.announcement ? "megaphone.fill" : "pin.fill")
                                .foregroundStyle(.tint).frame(width: 24).padding(.top, 2)
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(pin.authorName).font(.subheadline.weight(.semibold))
                                        .foregroundStyle(ChatTimeline.nameColor(for: pin.authorName))
                                    Spacer()
                                    Text(ChatDates.short(pin.at)).font(.caption).foregroundStyle(.secondary)
                                }
                                Text(ConversationView.clean(pin.text)).foregroundStyle(.primary).lineLimit(4)
                                if pin.announcement {
                                    Text("Annonce").font(.caption2.weight(.bold)).foregroundStyle(.tint)
                                }
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityElement(children: .combine)
                    .accessibilityHint("Montre le message dans la discussion")
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Messages épinglés")
        .navigationBarTitleDisplayMode(.inline)
    }
}
