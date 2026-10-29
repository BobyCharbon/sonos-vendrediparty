import SwiftUI

/// Se connecter, en natif : pays, numéro, code reçu par SMS. Même compte que le module Événements.
struct SignInView: View {
    @ObservedObject var store: AccountStore
    @State private var country: LoginPhone.Country = .ch
    @State private var phone = ""
    @State private var code = ""
    @FocusState private var focused: Bool
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Form {
            Section {
                Text("Connecte-toi par SMS : ton surnom et ta photo te suivent dans les jeux, et tu peux demander à rejoindre les événements du groupe.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            .listRowBackground(Color.clear)
            switch store.step {
            case .phone: phoneStep
            case .code(let number): codeStep(number)
            }
            if let error = store.error {
                Section { Text(error).foregroundStyle(.red) }
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Se connecter")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { focused = true }
        .onDisappear { store.error = nil }
    }

    private var phoneStep: some View {
        Section {
            Picker("Pays et indicatif", selection: $country) {
                ForEach(LoginPhone.Country.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .listRowSeparator(.hidden)
            TextField(country.placeholder, text: $phone)
                .keyboardType(.phonePad)
                .textContentType(.telephoneNumber)
                .focused($focused)
                .accessibilityLabel("Ton numéro de téléphone")
                .accessibilityIdentifier("login-phone")
            Button {
                guard let number = LoginPhone.parse(phone, country: country) else {
                    store.error = country == .other ? "Saisis le numéro complet avec son indicatif, par exemple +32…"
                                                    : "Vérifie le pays et saisis un numéro complet, avec ou sans le zéro initial."
                    return
                }
                Task {
                    await store.sendCode(number)
                    code = ""
                    focused = true
                }
            } label: {
                HStack {
                    Text("Recevoir un code par SMS")
                    if store.busy { Spacer(); ProgressView() }
                }
            }
            .disabled(phone.trimmingCharacters(in: .whitespaces).isEmpty || store.busy)
            .accessibilityIdentifier("login-send")
        } header: {
            Text("Ton numéro")
        } footer: {
            Text("Un numéro commençant par + ou 00 garde son propre indicatif.")
        }
    }

    private func codeStep(_ number: String) -> some View {
        Section {
            TextField("123456", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .focused($focused)
                .accessibilityLabel("Code reçu par SMS")
                .accessibilityIdentifier("login-code")
                .onChange(of: code) { value in
                    let digits = String(value.filter(\.isNumber).prefix(6))
                    if digits != value { code = digits }
                    if digits.count == 6 { verify() }
                }
            Button {
                verify()
            } label: {
                HStack {
                    Text("Se connecter")
                    if store.busy { Spacer(); ProgressView() }
                }
            }
            .disabled(code.count < 6 || store.busy)
            .accessibilityIdentifier("login-verify")
            Button("Changer de numéro") {
                store.step = .phone
                store.error = nil
            }
            .foregroundStyle(.secondary)
        } header: {
            Text("Code reçu au \(LoginPhone.pretty(number))")
        }
    }

    private func verify() {
        guard !store.busy else { return }
        Task { if await store.verify(code) { dismiss() } else { code = "" } }
    }
}

/// Gérer mon compte : suppression définitive, confirmée en écrivant SUPPRIMER.
struct DeleteAccountView: View {
    @ObservedObject var store: AccountStore
    let isAdmin: Bool
    @State private var confirmation = ""
    @Environment(\.dismiss) private var dismiss

    private static let word = "SUPPRIMER"

    var body: some View {
        Form {
            Section {
                Text("Cette action est définitive. Ton profil, tes messages, tes votes, tes réponses et tes préférences seront supprimés.")
                Text("Les événements que tu as créés et leurs discussions seront également supprimés pour le groupe.")
                if isAdmin {
                    Text("Si tu es le dernier administrateur, désigne d'abord un autre administrateur dans Membres.")
                        .foregroundStyle(.secondary)
                }
            } header: {
                Text("Supprimer mon compte")
            }
            Section {
                TextField("Écris \(Self.word) pour confirmer", text: $confirmation)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .accessibilityIdentifier("delete-confirm")
                Button(role: .destructive) {
                    Task { if await store.deleteAccount() { dismiss() } }
                } label: {
                    HStack {
                        Text("Supprimer définitivement mon compte")
                        if store.busy { Spacer(); ProgressView() }
                    }
                }
                .disabled(confirmation != Self.word || store.busy)
                .accessibilityIdentifier("delete-account")
            } footer: {
                if let error = store.error { Text(error).foregroundStyle(.red) }
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Gérer mon compte")
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear { store.error = nil }
    }
}

/// Confidentialité : le texte du module web, en natif.
struct PrivacyView: View {
    private static let sections: [(String, [String])] = [
        ("Un espace pour le groupe", [
            "Vendredi Party organise les événements d'un groupe privé. Un administrateur valide l'accès des nouveaux membres.",
        ]),
        ("Données utilisées", [
            "Ton numéro de téléphone sert à recevoir un code de connexion. Ton prénom, tes événements, tes réponses, tes votes et tes messages permettent au groupe d'organiser les événements.",
            "Les catégories et tags auxquels tu t'abonnes servent à filtrer les événements et les notifications. L'application enregistre tes préférences pour les notifications des événements.",
        ]),
        ("Qui peut voir quoi ?", [
            "Les membres autorisés voient les événements et les contributions selon leur visibilité. Ton numéro de téléphone est visible par toi et par les administrateurs qui gèrent les accès au groupe.",
            "Un sondage anonyme affiche les totaux. Un sondage nominatif peut afficher les votants. Les messages d'une discussion sont visibles aux membres autorisés à consulter l'événement.",
        ]),
        ("Services techniques", [
            "Supabase héberge la base du projet en région Zurich et gère la connexion. Twilio reçoit le numéro nécessaire à l'envoi du code SMS. Le module événements est hébergé sur le même site que Party.",
            "Si tu actives les notifications sur cet iPhone, son adresse de notification est enregistrée avec ton compte et ta session. Apple transmet les notifications.",
            "Les préférences des événements et de la musique sont distinctes. Les annonces admin restent lisibles et ne peuvent pas être désactivées dans les préférences.",
        ]),
        ("Tes choix et la conservation", [
            "Tu peux modifier ton profil, tes abonnements et tes préférences de notifications dans les Réglages. Les notifications de l'historique sont purgées après 90 jours ; les annonces admin sont conservées. Une déconnexion retire les notifications des événements de cet iPhone.",
            "Tu peux supprimer ton compte dans Réglages › Gérer mon compte. Cette action supprime tes contributions et les événements que tu as créés. Les textes rédigés par d'autres membres peuvent encore contenir des références à ton prénom.",
            "Pour toute question sur les données du groupe, contacte son administrateur par le canal habituel du groupe.",
        ]),
    ]

    var body: some View {
        List {
            Section {
                Text("Vendredi Party · Mise à jour du 19 octobre 2026").font(.footnote).foregroundStyle(.secondary)
            }
            .listRowBackground(Color.clear)
            ForEach(Self.sections, id: \.0) { title, paragraphs in
                Section(title) {
                    ForEach(paragraphs, id: \.self) { Text($0).font(.subheadline) }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Confidentialité")
        .navigationBarTitleDisplayMode(.inline)
    }
}
