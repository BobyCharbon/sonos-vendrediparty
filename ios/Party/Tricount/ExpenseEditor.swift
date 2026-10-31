import PhotosUI
import SwiftUI

/// Ajouter ou modifier une dépense. Simplifié (par défaut) : le montant en grand, le titre, qui a payé, pour qui
/// (parts égales). Avancé : partage par parts ou par montants exacts, catégorie, date, monnaie et taux, note,
/// photo du ticket, et « remboursement » (un virement entre deux personnes).
struct ExpenseEditor: View {
    @ObservedObject var store: TricountStore
    let group: TC.Group
    @State var draft: TricountDraft
    @Environment(\.dismiss) private var dismiss
    @State private var photo: PhotosPickerItem?
    @State private var receipt: Data?
    @State private var confirmDelete = false
    @FocusState private var amountFocused: Bool

    private var advanced: Bool { store.advanced || draft.split != .equal || draft.transfer }
    private var guessed: TC.Overview.Category? {
        store.category(draft.category.isEmpty ? Self.guess(draft.title) : draft.category)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        TextField("0.00", text: $draft.amount)
                            .keyboardType(.decimalPad).font(.system(size: 44, weight: .heavy, design: .rounded))
                            .multilineTextAlignment(.trailing).focused($amountFocused)
                            .accessibilityIdentifier("tc-amount")
                        Text(draft.currency.isEmpty ? group.currency : draft.currency).font(.title2.weight(.semibold)).foregroundStyle(.secondary)
                    }
                    HStack {
                        Text(draft.transfer ? "🔁" : guessed?.emoji ?? "💸").font(.title2)
                        TextField(draft.transfer ? "Remboursement" : "Titre (ex. : Courses Migros)", text: $draft.title)
                            .font(.title3.weight(.semibold)).accessibilityIdentifier("tc-title")
                    }
                }
                Section(draft.transfer ? "Qui a remboursé ?" : "Payé par") {
                    chips(single: true)
                }
                Section {
                    chips(single: false)
                    if !draft.transfer {
                        HStack {
                            Button("Tout le monde") { draft.forWhom = Set(group.active.map(\.id)) }
                            Spacer()
                            Button("Personne") { draft.forWhom = [] }
                        }
                        .font(.footnote).buttonStyle(.borderless)
                    }
                } header: {
                    Text(draft.transfer ? "À qui ?" : "Pour qui ?")
                } footer: {
                    if !draft.transfer, draft.split == .equal, let total = Money.cents(draft.amount), !draft.forWhom.isEmpty {
                        Text("\(Money.text(total / draft.forWhom.count, draft.currency.isEmpty ? group.currency : draft.currency)) chacun environ")
                    }
                }
                if advanced && !draft.transfer { splitSection }
                if store.advanced { advancedSection }
                if draft.id != nil {
                    Section {
                        Button("Supprimer cette dépense", role: .destructive) { confirmDelete = true }
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle(draft.id == nil ? (draft.transfer ? "Remboursement" : "Nouvelle dépense") : "Modifier")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Enregistrer") {
                        Task { if await store.save(draft, receipt: receipt) { dismiss() } }
                    }
                    .bold().disabled(store.busy)
                    .accessibilityIdentifier("tc-save")
                }
            }
            .onAppear { if draft.id == nil { amountFocused = true } }
            .onChange(of: photo) { item in
                Task { receipt = try? await item?.loadTransferable(type: Data.self).flatMap(Self.jpeg) }
            }
            .confirmationDialog("Supprimer cette dépense ?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Supprimer", role: .destructive) {
                    if let id = draft.id { Task { await store.delete(id); dismiss() } }
                }
            }
            .overlay(alignment: .bottom) { TCNotice(text: $store.notice) }
        }
    }

    /// Pastilles des membres : un seul choix (payeur) ou plusieurs (pour qui).
    private func chips(single: Bool) -> some View {
        let columns = [GridItem(.adaptive(minimum: 96), spacing: 8)]
        return LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
            ForEach(group.active) { m in
                let on = single ? draft.payer == m.id : draft.forWhom.contains(m.id)
                Button {
                    if single { draft.payer = m.id }
                    else if draft.transfer { draft.forWhom = [m.id] }
                    else if on { draft.forWhom.remove(m.id) } else { draft.forWhom.insert(m.id) }
                } label: {
                    Text(m.name + (m.me ? " (toi)" : "")).font(.subheadline.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.7)
                        .frame(maxWidth: .infinity).padding(.vertical, 10).padding(.horizontal, 8)
                        .background(on ? Palette.accent : Color.white.opacity(0.07), in: Capsule())
                        .foregroundStyle(on ? Color.black : Color.primary)
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
        .padding(.vertical, 4)
    }

    private var splitSection: some View {
        Section {
            Picker("Partage", selection: $draft.split) { ForEach(TricountDraft.Split.allCases) { Text($0.label).tag($0) } }
                .pickerStyle(.segmented)
            if draft.split == .shares {
                ForEach(group.active.filter { draft.forWhom.contains($0.id) }) { m in
                    Stepper(value: Binding(get: { draft.weights[m.id] ?? 1 }, set: { draft.weights[m.id] = $0 }), in: 0...20, step: 0.5) {
                        HStack { Text(m.name); Spacer(); Text("\((draft.weights[m.id] ?? 1).formatted()) part\((draft.weights[m.id] ?? 1) > 1 ? "s" : "")").foregroundStyle(.secondary) }
                    }
                }
            }
            if draft.split == .amounts {
                ForEach(group.active.filter { draft.forWhom.contains($0.id) }) { m in
                    HStack {
                        Text(m.name)
                        Spacer()
                        TextField("0.00", text: Binding(get: { draft.amounts[m.id] ?? "" }, set: { draft.amounts[m.id] = $0 }))
                            .keyboardType(.decimalPad).multilineTextAlignment(.trailing).frame(width: 110)
                    }
                }
                let sum = group.active.compactMap { Money.cents(draft.amounts[$0.id] ?? "") }.reduce(0, +)
                let total = Money.cents(draft.amount) ?? 0
                Text(sum == total ? "✓ Le compte est bon" : "Reste \(Money.text(total - sum, draft.currency))")
                    .font(.footnote.weight(.semibold)).foregroundStyle(sum == total ? TCColor.owed : TCColor.owes)
            }
        } header: { Text("Partage") } footer: {
            Text(draft.split == .shares ? "Ex. : 2 parts pour un couple, 1 pour une personne seule." :
                 draft.split == .amounts ? "Le montant exact de chacun ; le total doit tomber juste." : "À parts égales entre les personnes choisies.")
        }
    }

    private var advancedSection: some View {
        Section("Détails") {
            Toggle("C'est un remboursement", isOn: $draft.transfer.animation())
                .onChange(of: draft.transfer) { on in
                    if on, let first = draft.forWhom.first { draft.forWhom = [first] }
                    if on { draft.split = .equal }
                }
            if !draft.transfer {
                Picker("Catégorie", selection: $draft.category) {
                    Text("Automatique\(guessed.map { " (\($0.emoji) \($0.label))" } ?? "")").tag("")
                    ForEach(store.categories) { c in Text("\(c.emoji) \(c.label)").tag(c.id) }
                }
            }
            DatePicker("Date", selection: $draft.date, displayedComponents: .date).environment(\.locale, Locale(identifier: "fr_CH"))
            Picker("Monnaie", selection: $draft.currency) { ForEach(store.currencies, id: \.self) { Text($0).tag($0) } }
            if draft.currency != group.currency {
                HStack {
                    Text("1 \(draft.currency) =")
                    TextField("1", text: $draft.rate).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    Text(group.currency)
                }
            }
            TextField("Note", text: $draft.note, axis: .vertical).lineLimit(1...4)
            PhotosPicker(selection: $photo, matching: .images) {
                Label(receipt != nil ? "Ticket ajouté ✓" : draft.receiptPath != nil ? "Remplacer le ticket" : "Photo du ticket",
                      systemImage: "doc.text.viewfinder")
            }
        }
    }

    /// Catégorie devinée côté app pour l'aperçu (le serveur a la même règle et tranche).
    static func guess(_ title: String) -> String {
        let t = " \(title.lowercased()) "
        let rules: [(String, [String])] = [("food", ["migros", "coop", "denner", "aldi", "lidl", "courses", "épicerie", "boulangerie"]),
                                           ("restaurant", ["resto", "restaurant", "pizza", "burger", "kebab", "sushi", "repas"]),
                                           ("drinks", ["bière", "bar", "apéro", "vin", "alcool", "cocktail"]),
                                           ("transport", ["essence", "train", "cff", "bus", "taxi", "uber", "parking", "avion"]),
                                           ("lodging", ["airbnb", "hôtel", "hotel", "chalet", "camping", "loyer"]),
                                           ("leisure", ["cinéma", "concert", "musée", "ski", "billet", "bowling", "karting"])]
        return rules.first { _, words in words.contains { t.contains($0) } }?.0 ?? "other"
    }

    /// Photo du ticket : réduite (1600 px) et en JPEG, pour un envoi rapide.
    static func jpeg(_ data: Data) -> Data? {
        guard let image = UIImage(data: data) else { return nil }
        let side: CGFloat = 1600
        let scale = min(1, side / max(image.size.width, image.size.height))
        let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        let resized = UIGraphicsImageRenderer(size: size).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        return resized.jpegData(compressionQuality: 0.75)
    }
}

/// Mon profil de paiement : ce que voient les membres de mes tricounts pour me rembourser.
struct PaymentProfileView: View {
    @ObservedObject var store: TricountStore
    @State private var p = TC.Payment.empty
    @State private var loaded = false

    var body: some View {
        Form {
            Section {
                TextField("CH93 0076 2011 6238 5295 7", text: Binding(get: { p.iban ?? "" }, set: { p.iban = $0 }))
                    .font(.body.monospaced()).textInputAutocapitalization(.characters).autocorrectionDisabled()
                    .accessibilityIdentifier("tc-iban")
                TextField("Titulaire du compte", text: Binding(get: { p.holder ?? "" }, set: { p.holder = $0 }))
            } header: { Text("IBAN") } footer: { Text("Vérifié automatiquement (clé de contrôle).") }
            Section {
                link("revolut", "Revolut (nom d'utilisateur ou lien revolut.me)", "person.crop.circle.badge.checkmark")
                link("twint", "Twint (numéro de téléphone)", "iphone")
                link("paypal", "PayPal (nom ou lien paypal.me)", "p.circle")
                link("other", "Autre lien de paiement (https://…)", "link")
            } header: { Text("Paiement rapide") }
            Section("Note") {
                TextField("Ex. : Twint de préférence", text: Binding(get: { p.note ?? "" }, set: { p.note = $0 }))
            }
            Section {
                Button { Task { _ = await store.savePayment(p) } } label: {
                    Label("Enregistrer", systemImage: "checkmark.circle.fill").frame(maxWidth: .infinity)
                }
                .disabled(store.busy)
                .accessibilityIdentifier("tc-payment-save")
            } footer: {
                Text("Visible seulement des personnes qui partagent un tricount avec toi, quand elles te remboursent.")
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background)
        .navigationTitle("Profil de paiement")
        .task {
            await store.loadPayment()
            if !loaded, let saved = store.payment { p = saved; loaded = true }
        }
        .onChange(of: store.payment) { saved in if let saved { p = saved } }
        .overlay(alignment: .bottom) { TCNotice(text: $store.notice) }
    }

    private func link(_ kind: String, _ placeholder: String, _ symbol: String) -> some View {
        HStack {
            Image(systemName: symbol).foregroundStyle(.secondary).frame(width: 24)
            TextField(placeholder, text: Binding(get: { p.links[kind] ?? "" }, set: { p.links[kind] = $0.isEmpty ? nil : $0 }))
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .keyboardType(kind == "twint" ? .phonePad : .URL)
        }
    }
}
