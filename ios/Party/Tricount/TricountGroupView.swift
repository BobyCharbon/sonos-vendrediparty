import SwiftUI

/// Un pot commun : en tête, le total et MON solde en grand ; puis les dépenses (par jour), les soldes de chacun avec
/// « pour tout régler » (le moins de virements possible), et en mode avancé les statistiques par catégorie.
struct TricountGroupView: View {
    @ObservedObject var store: TricountStore
    let id: String
    @State private var tab = Tab.expenses
    @State private var editing: TricountDraft?
    @State private var paying: TC.Settle?
    @State private var showMembers = false
    @State private var showSettings = false
    @State private var confirmLeave = false
    @Environment(\.dismiss) private var dismiss

    enum Tab: String, CaseIterable, Identifiable {
        case expenses, balances, stats
        var id: String { rawValue }
        var label: String { ["expenses": "Dépenses", "balances": "Soldes", "stats": "Stats"][rawValue] ?? rawValue }
    }

    var body: some View {
        Group {
            if let g = store.group, g.id == id {
                content(g)
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary).padding()
            } else {
                ProgressView()
            }
        }
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(store.group?.name ?? "Pot commun")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.open(id) }
        .refreshable { await store.open(id) }
        .overlay(alignment: .bottom) { TCNotice(text: $store.notice) }
    }

    private func content(_ g: TC.Group) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                header(g)
                Picker("Vue", selection: $tab) {
                    ForEach(Tab.allCases.filter { store.advanced || $0 != .stats }) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
                switch tab {
                case .expenses: expenses(g)
                case .balances: balances(g)
                case .stats: stats(g)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 110)
        }
        .overlay(alignment: .bottom) {
            if !g.archived {
                Button { editing = TricountDraft(group: g) } label: {
                    Label("Ajouter une dépense", systemImage: "plus").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 16)
                }
                .buttonStyle(.borderedProminent)
                .buttonBorderShape(.capsule)
                .padding(.horizontal, 24).padding(.bottom, 18)
                .shadow(color: .black.opacity(0.35), radius: 12, y: 6)
                .accessibilityIdentifier("tc-add")
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    if let link = g.link.flatMap(URL.init(string:)) {
                        ShareLink(item: link, subject: Text("Rejoins « \(g.name) »"),
                                  message: Text("Rejoins mon pot commun « \(g.name) » dans l'app Party : ")) {
                            Label("Partager le lien", systemImage: "square.and.arrow.up")
                        }
                    }
                    Button { showMembers = true } label: { Label("Membres", systemImage: "person.2") }
                    Button { showSettings = true } label: { Label("Réglages du pot commun", systemImage: "gearshape") }
                    Button(role: .destructive) { confirmLeave = true } label: { Label("Quitter ce pot commun", systemImage: "rectangle.portrait.and.arrow.right") }
                } label: { Image(systemName: "ellipsis.circle") }
                .accessibilityIdentifier("tc-menu")
            }
        }
        .sheet(item: Binding(get: { editing.map(EditingBox.init) }, set: { editing = $0?.draft })) { box in
            ExpenseEditor(store: store, group: g, draft: box.draft)
        }
        .sheet(item: $paying) { t in PaySheet(store: store, group: g, transfer: t) }
        .sheet(isPresented: $showMembers) { MembersSheet(store: store) }
        .sheet(isPresented: $showSettings) { GroupSettingsSheet(store: store, group: g) }
        .confirmationDialog("Quitter ce pot commun ?", isPresented: $confirmLeave, titleVisibility: .visible) {
            Button("Quitter", role: .destructive) { Task { if await store.leave() { dismiss() } } }
        } message: {
            Text("Tes dépenses restent dans le pot commun. Tu pourras revenir avec le lien.")
        }
    }

    // ── En-tête : total et mon solde ──
    private func header(_ g: TC.Group) -> some View {
        VStack(spacing: 10) {
            Text(g.emoji).font(.system(size: 44))
            Text(TCColor.phrase(g.my_balance_cents, g.currency))
                .font(.system(size: 30, weight: .heavy, design: .rounded)).foregroundStyle(TCColor.of(g.my_balance_cents))
                .contentTransition(.numericText()).multilineTextAlignment(.center)
                .accessibilityIdentifier("tc-my-balance")
            HStack(spacing: 18) {
                stat("Total", Money.text(g.total_cents, g.currency))
                Divider().frame(height: 30)
                stat("Ma part", Money.text(g.my_spent_cents, g.currency))
                Divider().frame(height: 30)
                stat("Personnes", "\(g.active.count)")
            }
            if g.archived { Text("Archivé : lecture seule").font(.caption.weight(.semibold)).foregroundStyle(.secondary) }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20).padding(.horizontal, 12)
        .background(LinearGradient(colors: [TCColor.of(g.my_balance_cents).opacity(0.22), Palette.card],
                                   startPoint: .top, endPoint: .bottom), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
        .padding(.top, 8)
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: g.my_balance_cents)
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.headline.monospacedDigit()).lineLimit(1).minimumScaleFactor(0.7)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
    }

    // ── Dépenses, par jour ──
    @ViewBuilder private func expenses(_ g: TC.Group) -> some View {
        if g.expenses.isEmpty {
            VStack(spacing: 10) {
                Text("🧾").font(.system(size: 44))
                Text("Aucune dépense pour l'instant").font(.headline)
                Text("Ajoute la première : courses, essence, resto… On calcule qui doit quoi.").font(.subheadline)
                    .foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(30)
        } else {
            let days = Dictionary(grouping: g.expenses) { $0.spent_on ?? "" }
            ForEach(days.keys.sorted(by: >), id: \.self) { day in
                VStack(alignment: .leading, spacing: 8) {
                    Text(Self.dayLabel(day)).font(.footnote.weight(.semibold)).foregroundStyle(.secondary).textCase(.uppercase)
                    VStack(spacing: 0) {
                        ForEach(days[day] ?? []) { e in
                            Button { if !g.archived { editing = TricountDraft(expense: e, group: g) } } label: { ExpenseRow(store: store, expense: e, group: g) }
                                .buttonStyle(.plain)
                            if e.id != days[day]?.last?.id { Divider().padding(.leading, 62) }
                        }
                    }
                    .background(Palette.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
            }
        }
    }

    static func dayLabel(_ day: String) -> String {
        guard let date = TricountDraft.day.date(from: day) else { return day }
        if Calendar.current.isDateInToday(date) { return "Aujourd'hui" }
        if Calendar.current.isDateInYesterday(date) { return "Hier" }
        return date.formatted(.dateTime.weekday(.wide).day().month(.wide).locale(Locale(identifier: "fr_CH")))
    }

    // ── Soldes et remboursements ──
    @ViewBuilder private func balances(_ g: TC.Group) -> some View {
        let biggest = max(1, g.members.map { abs($0.balance_cents) }.max() ?? 1)
        VStack(spacing: 10) {
            ForEach(g.members.filter { $0.left != true || $0.balance_cents != 0 }) { m in
                HStack(spacing: 12) {
                    Text(m.name + (m.me ? " (toi)" : "")).font(.subheadline.weight(.semibold)).frame(width: 110, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        let half = geo.size.width / 2
                        let w = half * CGFloat(abs(m.balance_cents)) / CGFloat(biggest)
                        ZStack(alignment: .leading) {
                            Rectangle().fill(Color.white.opacity(0.08)).frame(width: 2).offset(x: half - 1)
                            RoundedRectangle(cornerRadius: 6).fill(TCColor.of(m.balance_cents))
                                .frame(width: max(3, w)).offset(x: m.balance_cents >= 0 ? half : half - w)
                        }
                    }
                    .frame(height: 22)
                    Text(m.balance_cents == 0 ? "0" : Money.text(m.balance_cents, g.currency, sign: true))
                        .font(.subheadline.monospacedDigit().weight(.bold)).foregroundStyle(TCColor.of(m.balance_cents))
                        .frame(width: 104, alignment: .trailing).lineLimit(1).minimumScaleFactor(0.7)
                }
            }
        }
        .padding(16)
        .background(Palette.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        VStack(alignment: .leading, spacing: 10) {
            Text("Pour tout régler").font(.headline)
            if g.settle.isEmpty {
                Label("Personne ne doit rien à personne 🎉", systemImage: "checkmark.seal.fill").foregroundStyle(TCColor.owed)
            } else {
                Text("\(g.settle.count) virement\(g.settle.count > 1 ? "s" : "") suffi\(g.settle.count > 1 ? "sent" : "t")")
                    .font(.caption).foregroundStyle(.secondary)
                ForEach(g.settle, id: \.self) { t in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("\(t.from_name)").bold() + Text(" → ") + Text("\(t.to_name)").bold()
                            Spacer()
                            Text(Money.text(t.amount_cents, g.currency)).font(.headline.monospacedDigit())
                        }
                        HStack(spacing: 10) {
                            if t.from == g.me {
                                Button { paying = t } label: { Label("Payer", systemImage: "creditcard") }.buttonStyle(.borderedProminent)
                            }
                            Button { Task { await store.settle(t) } } label: { Label("C'est remboursé", systemImage: "checkmark") }
                                .buttonStyle(.bordered)
                                .disabled(g.archived || store.busy)
                        }
                        .controlSize(.small)
                    }
                    .padding(14)
                    .background(Color.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Palette.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    // ── Statistiques (mode avancé) ──
    @ViewBuilder private func stats(_ g: TC.Group) -> some View {
        let top = max(1, g.by_category.first?.amount_cents ?? 1)
        VStack(alignment: .leading, spacing: 12) {
            Text("Par catégorie").font(.headline)
            if g.by_category.isEmpty { Text("Pas encore de dépense.").foregroundStyle(.secondary) }
            ForEach(g.by_category, id: \.category) { c in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("\(c.emoji) \(c.label)")
                        Spacer()
                        Text(Money.text(c.amount_cents, g.currency)).monospacedDigit().bold()
                        Text("\(Int((Double(c.amount_cents) / Double(max(1, g.total_cents)) * 100).rounded())) %").font(.caption).foregroundStyle(.secondary)
                            .frame(width: 44, alignment: .trailing)
                    }
                    GeometryReader { geo in
                        Capsule().fill(Palette.accent.gradient).frame(width: max(4, geo.size.width * CGFloat(c.amount_cents) / CGFloat(top)))
                    }
                    .frame(height: 8)
                }
            }
        }
        .padding(16)
        .background(Palette.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        VStack(alignment: .leading, spacing: 8) {
            Text("Qui a payé quoi").font(.headline)
            ForEach(g.active) { m in
                let paid = g.expenses.filter { !$0.isTransfer && $0.paid_by == m.id }.reduce(0) { $0 + $1.group_amount_cents }
                HStack { Text(m.name); Spacer(); Text(Money.text(paid, g.currency)).monospacedDigit() }
            }
        }
        .padding(16)
        .background(Palette.card, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

/// Une dépense dans la liste : catégorie, titre, qui a payé, montant, et ma part.
struct ExpenseRow: View {
    @ObservedObject var store: TricountStore
    let expense: TC.Expense
    let group: TC.Group

    var body: some View {
        HStack(spacing: 12) {
            Text(expense.isTransfer ? "🔁" : store.category(expense.category)?.emoji ?? "💸").font(.system(size: 24))
                .frame(width: 42, height: 42).background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(expense.isTransfer ? "\(expense.paid_by_name) a remboursé \(expense.parts.first?.name ?? "?")" : expense.title)
                    .font(.body.weight(.semibold)).lineLimit(1)
                Text(expense.isTransfer ? "Remboursement" : "Payé par \(expense.paid_by_name)\(expense.receipt_url != nil ? " · 📎 ticket" : "")")
                    .font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 2) {
                Text(Money.text(expense.group_amount_cents, group.currency)).font(.body.monospacedDigit().weight(.semibold))
                if !expense.isTransfer {
                    Text(expense.my_part_cents > 0 ? "ta part \(Money.text(expense.my_part_cents, group.currency))" : "pas pour toi")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .contentShape(Rectangle())
    }
}

/// Feuille d'une dépense : modifier ↔ Identifiable pour .sheet(item:).
private struct EditingBox: Identifiable {
    let draft: TricountDraft
    var id: String { draft.id ?? "new" }
}

/// « Payer » : les coordonnées de celui qu'on rembourse (IBAN copiable, lien Revolut / PayPal…, Twint).
struct PaySheet: View {
    @ObservedObject var store: TricountStore
    let group: TC.Group
    let transfer: TC.Settle
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var copied = false

    var body: some View {
        let creditor = group.member(transfer.to)
        let pay = creditor?.payment
        NavigationStack {
            List {
                Section {
                    VStack(spacing: 6) {
                        Text("Tu rembourses \(transfer.to_name)").font(.headline)
                        Text(Money.text(transfer.amount_cents, group.currency)).font(.system(size: 40, weight: .heavy, design: .rounded))
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 8)
                }
                if let pay, !pay.isEmpty {
                    if let iban = pay.iban, !iban.isEmpty {
                        Section("Virement bancaire") {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(iban).font(.body.monospaced()).textSelection(.enabled)
                                if let holder = pay.holder, !holder.isEmpty { Text(holder).font(.caption).foregroundStyle(.secondary) }
                            }
                            Button {
                                UIPasteboard.general.string = iban.replacingOccurrences(of: " ", with: "")
                                copied = true
                            } label: { Label(copied ? "IBAN copié" : "Copier l'IBAN", systemImage: copied ? "checkmark" : "doc.on.doc") }
                        }
                    }
                    let links = pay.links.sorted { $0.key < $1.key }
                    if !links.isEmpty {
                        Section("Paiement rapide") {
                            ForEach(links, id: \.key) { kind, value in
                                if kind == "twint" {
                                    Button { UIPasteboard.general.string = value } label: { Label("Twint : \(value) (copier)", systemImage: "iphone") }
                                } else if let url = URL(string: value) {
                                    Button { openURL(url) } label: { Label(Self.label(kind), systemImage: "arrow.up.right.square") }
                                }
                            }
                        }
                    }
                    if let note = pay.note, !note.isEmpty { Section { Text(note).foregroundStyle(.secondary) } }
                } else {
                    Section {
                        Text("\(transfer.to_name) n'a pas encore rempli son profil de paiement. Demande-lui son IBAN ou un lien Revolut, Twint…")
                            .foregroundStyle(.secondary)
                    }
                }
                Section {
                    Button {
                        Task { await store.settle(transfer); dismiss() }
                    } label: { Label("J'ai remboursé \(transfer.to_name)", systemImage: "checkmark.circle.fill") }
                }
            }
            .navigationTitle("Rembourser")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Fermer") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }

    static func label(_ kind: String) -> String {
        ["revolut": "Payer avec Revolut", "paypal": "Payer avec PayPal", "lydia": "Payer avec Lydia", "other": "Ouvrir le lien de paiement"][kind] ?? kind
    }
}

/// Membres : ajouter un prénom (quelqu'un sans compte), renommer, retirer ; qui a rejoint avec son compte.
struct MembersSheet: View {
    @ObservedObject var store: TricountStore
    @Environment(\.dismiss) private var dismiss
    @State private var newName = ""
    @State private var renaming: TC.Member?
    @State private var renameText = ""

    var body: some View {
        NavigationStack {
            List {
                if let g = store.group {
                    Section {
                        ForEach(g.active) { m in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(m.name + (m.me ? " (toi)" : "")).font(.body.weight(.semibold))
                                    Text(m.linked == true ? "A rejoint avec son compte" : "Ajouté à la main (peut reprendre son prénom avec le lien)")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if !(m.payment?.isEmpty ?? true) { Image(systemName: "creditcard.fill").foregroundStyle(TCColor.owed) }
                            }
                            .swipeActions {
                                if !m.me {
                                    Button(role: .destructive) { Task { await store.removeMember(m.id) } } label: { Label("Retirer", systemImage: "trash") }
                                }
                                Button { renaming = m; renameText = m.name } label: { Label("Renommer", systemImage: "pencil") }.tint(.blue)
                            }
                        }
                    } footer: { Text("Glisse une ligne pour renommer ou retirer. Une personne qui a des dépenses reste dans les comptes.") }
                    Section("Ajouter quelqu'un") {
                        HStack {
                            TextField("Prénom", text: $newName)
                            Button("Ajouter") {
                                let name = newName
                                newName = ""
                                Task { await store.addMember(name) }
                            }
                            .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                    if let link = g.link.flatMap(URL.init(string:)) {
                        Section {
                            ShareLink(item: link, message: Text("Rejoins mon pot commun « \(g.name) » dans l'app Party : ")) {
                                Label("Partager le lien pour rejoindre", systemImage: "square.and.arrow.up")
                            }
                            Button { Task { await store.renewLink() } } label: { Label("Nouveau lien (l'ancien ne marchera plus)", systemImage: "arrow.clockwise") }
                        }
                    }
                }
            }
            .navigationTitle("Membres")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .alert("Renommer", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
                TextField("Prénom", text: $renameText)
                Button("Annuler", role: .cancel) {}
                Button("OK") { if let m = renaming { Task { await store.renameMember(m.id, renameText) } } }
            }
        }
    }
}

/// Réglages d'un pot commun : nom, emoji, monnaie, archiver.
struct GroupSettingsSheet: View {
    @ObservedObject var store: TricountStore
    let group: TC.Group
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var emoji = ""
    @State private var currency = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Nom") { TextField("Nom", text: $name) }
                Section("Emoji") {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack { ForEach(CreateTricountView.emojis, id: \.self) { e in
                            Button { emoji = e } label: {
                                Text(e).font(.system(size: 28)).frame(width: 46, height: 46)
                                    .background(emoji == e ? Palette.accent.opacity(0.3) : .clear, in: RoundedRectangle(cornerRadius: 12))
                            }.buttonStyle(.plain)
                        } }
                    }
                }
                Section {
                    Picker("Monnaie", selection: $currency) { ForEach(store.currencies, id: \.self) { Text($0).tag($0) } }
                } footer: { Text("Les montants déjà saisis gardent leur monnaie ; les totaux s'affichent dans la monnaie du pot commun.") }
                Section {
                    Button(group.archived ? "Désarchiver" : "Archiver (lecture seule)") {
                        Task { await store.update(archived: !group.archived); dismiss() }
                    }
                }
            }
            .navigationTitle("Réglages du pot commun")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Enregistrer") { Task { await store.update(name: name, emoji: emoji, currency: currency); dismiss() } }
                }
            }
            .onAppear { name = group.name; emoji = group.emoji; currency = group.currency }
        }
    }
}
