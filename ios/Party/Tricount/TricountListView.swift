import SwiftUI

/// Couleurs du Tricount : vert quand on te doit, corail quand tu dois, lavande pour le neutre.
enum TCColor {
    static let owed = Color(red: 0.24, green: 0.86, blue: 0.59)
    static let owes = Color(red: 1, green: 0.42, blue: 0.42)
    static let even = Color(red: 0.73, green: 0.65, blue: 1)
    static func of(_ cents: Int) -> Color { cents > 0 ? owed : cents < 0 ? owes : even }
    static func phrase(_ cents: Int, _ currency: String) -> String {
        cents > 0 ? "On te doit \(Money.text(cents, currency))" : cents < 0 ? "Tu dois \(Money.text(-cents, currency))" : "Tout est réglé"
    }
}

/// Réglages › Pot commun : mes tricounts (solde de chacun), créer, rejoindre par un lien, mon profil de paiement, le mode.
struct TricountListView: View {
    @ObservedObject var store: TricountStore
    let myName: String
    @State private var creating = false
    @State private var opened: String?

    var body: some View {
        List {
            Section {
                Picker("Affichage", selection: $store.advanced) {
                    Text("Simplifié").tag(false)
                    Text("Avancé").tag(true)
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
                .accessibilityIdentifier("tc-mode")
            } footer: {
                Text(store.advanced ? "Avancé : parts inégales, montants exacts, monnaies, date, catégorie, ticket et statistiques."
                     : "Simplifié : un titre, un montant, qui a payé et pour qui. Tout est partagé à parts égales.")
            }
            if let overview = store.overview {
                let live = overview.tricounts.filter { !$0.archived }
                Section {
                    Button { creating = true } label: {
                        Label("Nouveau pot commun", systemImage: "plus.circle.fill").font(.headline)
                    }
                    .accessibilityIdentifier("tc-new")
                    ForEach(live) { item in
                        NavigationLink { TricountGroupView(store: store, id: item.id) } label: { TricountCard(item: item) }
                    }
                } header: {
                    Text("Mes pots communs")
                } footer: {
                    if live.isEmpty { Text("Crée un pot commun pour un week-end, une coloc ou une soirée, puis partage le lien pour que chacun le rejoigne.") }
                }
                let archived = overview.tricounts.filter(\.archived)
                if !archived.isEmpty {
                    Section("Archivés") {
                        ForEach(archived) { item in
                            NavigationLink { TricountGroupView(store: store, id: item.id) } label: { TricountCard(item: item) }
                        }
                    }
                }
            } else if let error = store.error {
                Section { Text(error).foregroundStyle(.secondary) }
            } else {
                Section { ProgressView().frame(maxWidth: .infinity) }
            }
            Section {
                NavigationLink { PaymentProfileView(store: store) } label: {
                    SettingsRow(symbol: "creditcard.fill", tint: .green, title: "Mon profil de paiement",
                                hint: "IBAN, Revolut, Twint, PayPal : pour qu'on te rembourse facilement")
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background)
        .navigationTitle("Pot commun")
        .refreshable { await store.load() }
        .task { await store.load() }
        .navigationDestination(isPresented: Binding(get: { opened != nil }, set: { if !$0 { opened = nil } })) {
            if let opened { TricountGroupView(store: store, id: opened) }
        }
        .sheet(isPresented: $creating) {
            CreateTricountView(store: store, myName: myName) { opened = $0 }
        }
        .overlay(alignment: .bottom) { TCNotice(text: $store.notice) }
    }
}

struct TricountCard: View {
    let item: TC.Overview.Item

    var body: some View {
        HStack(spacing: 14) {
            Text(item.emoji).font(.system(size: 30)).frame(width: 52, height: 52)
                .background(TCColor.even.opacity(0.18), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                Text(item.name).font(.headline).lineLimit(1)
                Text("\(item.members) personne\(item.members > 1 ? "s" : "") · \(Money.text(item.total_cents, item.currency))")
                    .font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 2) {
                Text(item.my_balance_cents == 0 ? "Réglé ✓" : Money.text(item.my_balance_cents, item.currency, sign: true))
                    .font(.headline.monospacedDigit()).foregroundStyle(TCColor.of(item.my_balance_cents))
                Text(item.my_balance_cents > 0 ? "on te doit" : item.my_balance_cents < 0 ? "tu dois" : "")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

/// Nouveau pot commun : un emoji, un nom, la monnaie et ton prénom dans ce groupe.
struct CreateTricountView: View {
    @ObservedObject var store: TricountStore
    let myName: String
    let created: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var emoji = "💸"
    @State private var currency = "CHF"
    @State private var me = ""
    static let emojis = ["💸", "🏖️", "⛷️", "🏠", "🍕", "🎉", "🚗", "✈️", "🍻", "🎁", "🏕️", "🎂"]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(Self.emojis, id: \.self) { e in
                                Button { emoji = e } label: {
                                    Text(e).font(.system(size: 30)).frame(width: 52, height: 52)
                                        .background(emoji == e ? Palette.accent.opacity(0.3) : Color.white.opacity(0.06),
                                                    in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel("Emoji \(e)")
                            }
                        }
                    }
                    TextField("Nom (ex. : Week-end à Verbier)", text: $name).font(.title3.weight(.semibold))
                        .accessibilityIdentifier("tc-create-name")
                }
                Section("Monnaie") {
                    Picker("Monnaie", selection: $currency) { ForEach(store.currencies, id: \.self) { Text($0).tag($0) } }
                        .pickerStyle(.segmented)
                }
                Section {
                    TextField("Ton prénom dans ce pot commun", text: $me)
                } footer: {
                    Text("Ensuite, partage le lien : chacun le rejoint depuis son téléphone. Tu peux aussi ajouter des prénoms à la main.")
                }
            }
            .navigationTitle("Nouveau pot commun")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Créer") {
                        Task {
                            if let g = await store.create(name: name, emoji: emoji, currency: currency, myName: me) {
                                dismiss()
                                created(g.id)
                            }
                        }
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || me.trimmingCharacters(in: .whitespaces).isEmpty || store.busy)
                    .accessibilityIdentifier("tc-create-go")
                }
            }
            .onAppear { if me.isEmpty { me = myName } }
        }
    }
}

/// Rejoindre par un lien : qui es-tu ? (reprendre un prénom ajouté à la main, ou arriver avec le tien).
struct JoinTricountView: View {
    @ObservedObject var store: TricountStore
    let link: String
    let myName: String
    let joined: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var info: TC.JoinInfo?
    @State private var claim: String?
    @State private var name = ""
    @State private var loaded = false

    var body: some View {
        NavigationStack {
            Group {
                if let info {
                    Form {
                        Section {
                            VStack(spacing: 8) {
                                Text(info.emoji).font(.system(size: 56))
                                Text(info.name).font(.title2.bold()).multilineTextAlignment(.center)
                                Text("\(info.members.count) personne\(info.members.count > 1 ? "s" : "") · \(info.currency)").foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity).padding(.vertical, 8)
                        }
                        let free = info.members.filter { !$0.linked }
                        if !free.isEmpty {
                            Section {
                                ForEach(free) { p in
                                    Button { claim = claim == p.id ? nil : p.id } label: {
                                        HStack {
                                            Text(p.name)
                                            Spacer()
                                            if claim == p.id { Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.accent) }
                                        }
                                    }
                                    .foregroundStyle(.primary)
                                }
                            } header: {
                                Text("Tu es déjà dans la liste ?")
                            } footer: {
                                Text("Choisis ton prénom : les dépenses déjà notées à ce nom deviennent les tiennes.")
                            }
                        }
                        if claim == nil {
                            Section("Ton prénom") { TextField("Prénom", text: $name) }
                        }
                    }
                } else if loaded {
                    VStack(spacing: 12) {
                        Image(systemName: "link.badge.plus").font(.system(size: 44)).foregroundStyle(.secondary)
                        Text("Lien expiré").font(.title3.bold())
                        Text("Demande un nouveau lien à la personne qui t'a invité.").foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }
                    .padding(32)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Rejoindre")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(info?.already == true ? "Ouvrir" : "Rejoindre") {
                        Task {
                            if let g = await store.join(link, myName: name, claim: claim) {
                                dismiss()
                                joined(g.id)
                            }
                        }
                    }
                    .disabled(info == nil || (claim == nil && name.trimmingCharacters(in: .whitespaces).isEmpty) || store.busy)
                }
            }
            .task {
                if name.isEmpty { name = myName }
                info = await store.joinInfo(link)
                loaded = true
            }
        }
    }
}

/// Message bref en bas de l'écran (enregistré, erreur…), qui s'efface tout seul.
struct TCNotice: View {
    @Binding var text: String?

    var body: some View {
        if let text {
            Text(text).font(.callout.weight(.semibold)).padding(.horizontal, 18).padding(.vertical, 12)
                .background(.ultraThinMaterial, in: Capsule()).padding(.bottom, 24)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .task(id: text) {
                    try? await Task.sleep(for: .seconds(3))
                    withAnimation { self.text = nil }
                }
        }
    }
}
