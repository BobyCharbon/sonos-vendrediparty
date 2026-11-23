import SwiftUI

// Réglages du groupe pour son admin (demande du 23.11, maquette « Réglages du groupe ») : rôles dans le groupe, « Qui
// peut… » (un écran par droit), entrée dans le groupe, transmettre. Mêmes textes que le web (web/events/src/lib/
// groupRights.ts) ; la base décide de tout (migration 20261123110000 : group_admin_panel, set_group_right, set_group_role,
// set_group_join_approval, decide_group_join, transfer_group). Jamais Membres Vendredi Party.

// MARK: - Modèle

/// L'écran des réglages en une lecture (`group_admin_panel`).
struct GroupPanel: Decodable, Equatable {
    struct Me: Decodable, Equatable {
        var role: String?
        var manage = false
        var rules = false
        var owner = false
        var invite = false
        var events = false
        var announce = false
        var write = false
        var pin = false
        var edit = false
        var remove = false
    }

    struct Member: Decodable, Equatable, Identifiable {
        let id: String
        var name: String
        var photo: String?
        var role: String
        var since: String?

        var face: PronoFace { PronoFace(id: id, name: name, photo: photo) }
    }

    struct Request: Decodable, Equatable, Identifiable {
        let id: String
        var name: String
        var photo: String?
        var at: String?

        var face: PronoFace { PronoFace(id: id, name: name, photo: photo) }
    }

    var me: Me
    var rights: [String: String]
    var eventsNeedApproval: Bool
    var announceMode: String
    var joinApproval: Bool
    var linkActive: Bool
    var members: [Member]
    var requests: [Request]

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        me = try c.decodeIfPresent(Me.self, forKey: .me) ?? Me()
        rights = try c.decodeIfPresent([String: String].self, forKey: .rights) ?? [:]
        eventsNeedApproval = try c.decodeIfPresent(Bool.self, forKey: .eventsNeedApproval) ?? false
        announceMode = try c.decodeIfPresent(String.self, forKey: .announceMode) ?? "request"
        joinApproval = try c.decodeIfPresent(Bool.self, forKey: .joinApproval) ?? false
        linkActive = try c.decodeIfPresent(Bool.self, forKey: .linkActive) ?? false
        members = try c.decodeIfPresent([Member].self, forKey: .members) ?? []
        requests = try c.decodeIfPresent([Request].self, forKey: .requests) ?? []
    }

    private enum CodingKeys: String, CodingKey {
        case me, rights, eventsNeedApproval, announceMode, joinApproval, linkActive, members, requests
    }

    func level(_ key: String) -> String { rights[key] ?? GroupRightsText.defaults[key] ?? "admins" }
    func with(_ role: String) -> [Member] { members.filter { $0.role == role } }
}

extension GroupPanel.Me {
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Key.self)
        func flag(_ k: Key) -> Bool { (try? c.decodeIfPresent(Bool.self, forKey: k)) ?? false }
        role = try c.decodeIfPresent(String.self, forKey: .role)
        manage = flag(.manage); rules = flag(.rules); owner = flag(.owner); invite = flag(.invite); events = flag(.events)
        announce = flag(.announce); write = flag(.write); pin = flag(.pin); edit = flag(.edit); remove = flag(.remove)
    }

    private enum Key: String, CodingKey { case role, manage, rules, owner, invite, events, announce, write, pin, edit, remove }
}

// MARK: - Textes (testés : GroupRightsTests ; mêmes que web/events/src/lib/groupRights.ts)

enum GroupRightsText {
    struct Right { let key: String; let label: String; let about: String; let members: String; var staff: String? = nil }

    static let rights: [Right] = [
        Right(key: "invite", label: "Inviter des personnes", about: "Ajouter quelqu’un au groupe et partager le lien du groupe.",
              members: "Chaque membre peut inviter et partager le lien du groupe."),
        Right(key: "events", label: "Créer un événement pour le groupe", about: "L’événement est réservé au groupe et apparaît sur sa page.",
              members: "Chaque membre peut créer un événement du groupe.", staff: "Les membres proposent en message, pas d’événement."),
        Right(key: "announce", label: "Prévenir tout le groupe (@tout, annonce)",
              about: "@tout prévient chaque membre ; une annonce (@annonce) est épinglée en haut de la discussion.",
              members: "Chaque membre peut écrire @tout. Les annonces restent aux organisateurs et aux admins."),
        Right(key: "write", label: "Écrire dans la discussion", about: "Les autres lisent la discussion, réagissent et signalent.",
              members: "Chaque membre écrit dans la discussion."),
        Right(key: "pin", label: "Épingler un message", about: "Un message épinglé reste en haut de la discussion.",
              members: "Chaque membre peut épingler un message."),
        Right(key: "edit", label: "Modifier le nom, l’emoji et la photo", about: "Le nom, l’emoji, la couleur et la photo du groupe.",
              members: "Chaque membre peut les changer."),
        Right(key: "remove", label: "Retirer un membre",
              about: "Un membre ou un organisateur ne retire jamais un admin, un co-admin ni un organisateur.",
              members: "Chaque membre peut retirer un simple membre."),
    ]
    static let defaults = ["invite": "members", "events": "members", "announce": "members", "write": "members",
                           "pin": "admins", "edit": "admins", "remove": "admins"]
    static let levels = ["admins", "staff", "members"]

    static func right(_ key: String) -> Right { rights.first { $0.key == key } ?? rights[0] }

    static func levelTitle(_ level: String) -> String {
        switch level {
        case "admins": return "Admins seulement"
        case "staff": return "Organisateurs et admins"
        default: return "Tous les membres"
        }
    }

    static func levelColor(_ level: String) -> Color {
        switch level {
        case "admins": return PronoTheme.pinkInk
        case "staff": return PronoTheme.lavA
        default: return PronoTheme.mint
        }
    }

    static func levelDetail(_ key: String, _ level: String) -> String {
        switch level {
        case "admins": return "Toi et les co-admins."
        case "staff": return right(key).staff ?? "Les organisateurs, toi et les co-admins."
        default: return right(key).members
        }
    }

    /// Ligne de « Qui peut… » : « Tous les membres », « Membres · à valider par un admin »…
    static func who(_ key: String, _ level: String, needApproval: Bool) -> (text: String, color: Color) {
        if key == "events" && level == "members" && needApproval { return ("Membres · à valider par un admin", PronoTheme.amber) }
        return (levelTitle(level), levelColor(level))
    }

    static func roleTitle(_ role: String) -> String {
        switch role {
        case "creator": return "Admin du groupe"
        case "coadmin": return "Co-admin"
        case "organizer": return "Organisateur"
        default: return "Membre"
        }
    }

    static func roleDetail(_ role: String) -> String {
        switch role {
        case "coadmin": return "Comme toi : réglages, rôles, membres. Sauf supprimer le groupe."
        case "organizer": return "Crée des événements sans validation et prévient le groupe (@annonce)."
        default: return "Ce que tu permets aux membres dans « Qui peut… »."
        }
    }

    /// « tu es l’admin du groupe », « tu es co-admin »…
    static func myRole(_ role: String?) -> String {
        switch role {
        case "creator": return "tu es l’admin du groupe"
        case "coadmin": return "tu es co-admin"
        case "organizer": return "tu es organisateur"
        case "member": return "tu es membre"
        default: return ""
        }
    }

    /// Qui change le nom, l'emoji et la photo, pour qui ne le peut pas.
    static func editLine(_ level: String) -> String {
        level == "staff"
            ? "Seuls les organisateurs et les admins du groupe changent son nom, son emoji, sa couleur et sa photo."
            : "Seuls l’admin et les co-admins du groupe changent son nom, son emoji, sa couleur et sa photo."
    }

    /// « Dans le groupe depuis le 4 novembre ».
    static func since(_ iso: String?) -> String? {
        guard let d = PeopleDate.parse(iso) else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich") ?? .current
        f.setLocalizedDateFormatFromTemplate("dMMMM")
        return "Dans le groupe depuis le \(f.string(from: d))"
    }
}

// MARK: - Sections des réglages

/// « Rôles dans le groupe » : Admin du groupe (créateur), Co-admins, Organisateurs, Membres.
struct GroupRolesSection: View {
    let panel: GroupPanel
    let me: String

    var body: some View {
        Section {
            row("A", PronoTheme.pinkInk, "Admin du groupe", creator)
            row("CO", PronoTheme.lavA, "Co-admins", names("coadmin", suffix: " · tous les droits sauf supprimer le groupe"))
            row("OR", PronoTheme.amber, "Organisateurs", names("organizer", suffix: " · événements et annonces"))
            row("M", PronoTheme.mint, "Membres", panel.with("member").count == 1 ? "1 personne" : "\(panel.with("member").count) personnes")
        } header: {
            Text("Rôles dans le groupe")
        } footer: {
            Text("Touche un membre pour changer son rôle. Le créateur reste toujours admin du groupe.")
        }
        .listRowBackground(ConvNeon.surface)
    }

    private var creator: String {
        guard let c = panel.with("creator").first else { return "Personne" }
        return c.id == me ? "Toi (créateur)" : "\(c.name) (créateur)"
    }

    private func names(_ role: String, suffix: String) -> String {
        let list = panel.with(role)
        guard !list.isEmpty else { return "Personne pour l’instant" }
        return list.map { $0.id == me ? "Toi" : $0.name }.joined(separator: ", ") + suffix
    }

    private func row(_ short: String, _ tint: Color, _ title: String, _ who: String) -> some View {
        HStack(spacing: 12) {
            Text(short).font(.footnote.weight(.heavy)).foregroundStyle(PronoTheme.fixed(0x15102A))
                .frame(width: 36, height: 36).background(tint, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                Text(who).font(.footnote).foregroundStyle(PronoTheme.t2)
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
    }
}

/// « Qui peut… » : une ligne par droit, avec qui l'a ; un toucher ouvre le droit.
struct GroupRightsSection: View {
    let groupID: String
    let panel: GroupPanel

    var body: some View {
        Section {
            ForEach(GroupRightsText.rights, id: \.key) { r in
                let who = GroupRightsText.who(r.key, panel.level(r.key), needApproval: panel.eventsNeedApproval)
                NavigationLink(value: GroupScreen.right(groupID, r.key)) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(r.label).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                        Text(who.text).font(.footnote.weight(.semibold)).foregroundStyle(who.color)
                    }
                    .padding(.vertical, 4)
                }
                .accessibilityLabel("\(r.label) : \(who.text)")
                .accessibilityIdentifier("group-right-\(r.key)")
            }
        } header: {
            Text("Qui peut…")
        }
        .listRowBackground(ConvNeon.surface)
    }
}

// MARK: - Un droit

/// « Qui peut… » un droit : Admins seulement / Organisateurs et admins / Tous les membres ; créer un événement : « À valider
/// par un admin » ; prévenir le groupe : notifications des événements. Enregistrer → set_group_right.
struct GroupRightView: View {
    let groupID: String
    let key: String

    @Environment(\.people) private var people
    @Environment(\.dismiss) private var dismiss
    @State private var panel: GroupPanel?
    @State private var level: String?
    @State private var approval: Bool?
    @State private var mode: String?
    @State private var busy = false
    @State private var error: String?

    private var right: GroupRightsText.Right { GroupRightsText.right(key) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(right.label).font(.system(size: 26, weight: .heavy, design: .rounded)).foregroundStyle(PronoTheme.t1)
                    Text(right.about).font(.subheadline).foregroundStyle(PronoTheme.t2)
                }
                if let panel {
                    let chosen = level ?? panel.level(key)
                    VStack(spacing: 10) {
                        ForEach(GroupRightsText.levels, id: \.self) { l in
                            GroupChoiceRow(title: GroupRightsText.levelTitle(l), detail: GroupRightsText.levelDetail(key, l), on: chosen == l) {
                                Haptics.selection()
                                level = l
                            }
                        }
                    }
                    if key == "events" && chosen == "members" {
                        Toggle(isOn: Binding(get: { approval ?? panel.eventsNeedApproval }, set: { approval = $0 })) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text("À valider par un admin").font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                                Text("Celui d’un membre attend ton accord (ou celui d’un co-admin) avant d’être visible. Les organisateurs publient directement.")
                                    .font(.footnote).foregroundStyle(PronoTheme.t2)
                            }
                        }
                        .tint(PronoTheme.mint)
                        .padding(14)
                        .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                        .accessibilityIdentifier("group-right-approval")
                    }
                    if key == "events" {
                        Text("Un événement PUBLIC passe toujours par l’équipe de Vendredi Party, quel que soit ce réglage.")
                            .font(.footnote).foregroundStyle(PronoTheme.t2)
                    }
                    if key == "announce" {
                        let m = mode ?? panel.announceMode
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Notifications des événements").font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                            Picker("Notifications", selection: Binding(get: { m }, set: { mode = $0 })) {
                                Text("Sur demande").tag("request")
                                Text("Libres").tag("free")
                            }
                            .pickerStyle(.segmented)
                            Text(m == "request"
                                 ? "« Prévenir le groupe » d’un membre devient une demande : toi, les admins et les organisateurs du groupe l’acceptez ou la refusez. Sans réponse sous 48 h, l’annonce part automatiquement."
                                 : "Chaque membre décide lui-même de prévenir le groupe quand il publie un événement.")
                                .font(.footnote).foregroundStyle(PronoTheme.t2)
                        }
                        .padding(14)
                        .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    }
                    if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pinkInk) }
                    Button { save(panel) } label: {
                        Text("Enregistrer").font(.headline).foregroundStyle(.white).frame(maxWidth: .infinity, minHeight: 54)
                            .background(PronoTheme.pinkFill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .buttonStyle(.plain)
                    .disabled(busy)
                    .accessibilityIdentifier("group-right-save")
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .padding(16)
        }
        .background(ZStack { ConvNeon.bg; ConvNeon.halo }.ignoresSafeArea())
        .navigationTitle("Qui peut…")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        guard let people else { return }
        do {
            panel = try await GroupsAPI(people: people).panel(groupID)
        } catch {
            self.error = PeopleStore.message(error)
        }
    }

    private func save(_ panel: GroupPanel) {
        guard let people, !busy else { return }
        busy = true
        let api = GroupsAPI(people: people)
        let chosen = level ?? panel.level(key)
        let need = approval ?? panel.eventsNeedApproval
        let m = mode ?? panel.announceMode
        Task {
            defer { busy = false }
            do {
                if chosen != panel.level(key) { try await api.setRight(groupID, key: key, level: chosen) }
                if (key == "events" && need != panel.eventsNeedApproval) || (key == "announce" && m != panel.announceMode) {
                    try await api.setRules(groupID, needApproval: need, mode: m)
                }
                Haptics.success()
                dismiss()
            } catch {
                Haptics.error()
                self.error = PeopleStore.message(error)
            }
        }
    }
}

/// Un choix (cercle + titre + détail), comme la maquette (bord rose quand il est choisi).
struct GroupChoiceRow: View {
    let title: String
    let detail: String
    let on: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                ZStack {
                    Circle().strokeBorder(on ? PronoTheme.pinkInk : PronoTheme.t3, lineWidth: 2).frame(width: 24, height: 24)
                    if on { Circle().fill(PronoTheme.pinkInk).frame(width: 12, height: 12) }
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.body.weight(.bold)).foregroundStyle(PronoTheme.t1)
                    Text(detail).font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
            }
            .padding(14)
            .frame(minHeight: 64)
            .background(on ? PronoTheme.fixed(0x2A1A3D) : ConvNeon.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(on ? PronoTheme.pinkInk : ConvNeon.line2, lineWidth: 2))
            .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
    }
}

// MARK: - Rôle d'un membre

/// Rôle de … dans le groupe : Membre / Organisateur / Co-admin, « Voir sa fiche », « Retirer du groupe ».
struct GroupRoleSheet: View {
    let member: GroupPanel.Member
    let manage: Bool
    let setRole: (String) -> Void
    let profile: (() -> Void)?
    let remove: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var confirmRemove = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 14) {
                    PronoAvatar(face: member.face, size: 56)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(member.name).font(.title3.weight(.heavy)).foregroundStyle(PronoTheme.t1)
                        if let since = GroupRightsText.since(member.since) {
                            Text(since).font(.footnote).foregroundStyle(PronoTheme.t2)
                        }
                    }
                    Spacer()
                }
                if manage {
                    Text("RÔLE DANS LE GROUPE").font(.footnote.weight(.bold)).tracking(1.4).foregroundStyle(PronoTheme.t2)
                    VStack(spacing: 10) {
                        ForEach(["member", "organizer", "coadmin"], id: \.self) { r in
                            GroupChoiceRow(title: GroupRightsText.roleTitle(r), detail: GroupRightsText.roleDetail(r), on: member.role == r) {
                                Haptics.selection()
                                if member.role != r { setRole(r) }
                                dismiss()
                            }
                            .accessibilityIdentifier("group-role-\(r)")
                        }
                    }
                }
                VStack(spacing: 10) {
                    if let profile {
                        Button { dismiss(); profile() } label: {
                            Text("Voir sa fiche").font(.body.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 50)
                        }
                        .buttonStyle(.bordered).tint(PronoTheme.lavA)
                    }
                    Button(role: .destructive) { confirmRemove = true } label: {
                        Text("Retirer du groupe").font(.body.weight(.bold)).frame(maxWidth: .infinity, minHeight: 50)
                    }
                    .buttonStyle(.bordered)
                    .tint(PronoTheme.fixed(0xFF6363))
                    .accessibilityIdentifier("group-role-remove")
                }
            }
            .padding(16)
            .padding(.top, 8)
        }
        .background(PronoTheme.fixed(0x1C1535).ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .confirmationDialog("Retirer \(member.name) du groupe ?", isPresented: $confirmRemove, titleVisibility: .visible) {
            Button("Retirer", role: .destructive) { dismiss(); remove() }
        }
    }
}

/// « Transmettre le groupe à un autre admin » : un membre devient l'admin ; l'ancien admin reste co-admin.
struct GroupHandOverSheet: View {
    let members: [GroupPanel.Member]
    let pick: (GroupPanel.Member) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var picked: GroupPanel.Member?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Transmettre le groupe").font(.title3.weight(.heavy)).foregroundStyle(PronoTheme.t1)
                Text("La personne choisie devient l’admin du groupe : elle seule pourra le supprimer ou le transmettre. Tu restes co-admin.")
                    .font(.subheadline).foregroundStyle(PronoTheme.t2)
                if members.isEmpty {
                    Text("Personne d’autre dans le groupe pour l’instant.").foregroundStyle(PronoTheme.t2)
                }
                ForEach(members) { m in
                    GroupChoiceRow(title: m.name, detail: GroupRightsText.roleTitle(m.role), on: picked?.id == m.id) { picked = m }
                }
                Button {
                    if let picked { dismiss(); pick(picked) }
                } label: {
                    Text(picked.map { "Transmettre à \($0.name)" } ?? "Choisis un membre").font(.headline).foregroundStyle(.white)
                        .frame(maxWidth: .infinity, minHeight: 54)
                        .background(picked == nil ? PronoTheme.t3 : PronoTheme.pinkFill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(picked == nil)
                .accessibilityIdentifier("group-handover-confirm")
            }
            .padding(16)
            .padding(.top, 8)
        }
        .background(PronoTheme.fixed(0x1C1535).ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}
