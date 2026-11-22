import SwiftUI

/// Conditions d'utilisation (version 2026-11-18) : même texte que le module web (web/events/src/lib/terms.ts).
struct TermsView: View {
    @ObservedObject var store: ModerationStore

    static let updated = "18 novembre 2026"
    /// Responsable et contact de Party (web/events/src/lib/contact.ts) ; l'admin peut en afficher un autre.
    static let supportEmail = "support@vendrediparty.ch"
    static let sections: [(String, [String])] = [
        ("Party, entre amis", [
            "Party sert à organiser des soirées et des événements, à jouer et à discuter entre amis. En créant un compte et en publiant quoi que ce soit (message, surnom, nom de groupe, photo, réponse de jeu), tu acceptes ces conditions.",
        ]),
        ("Réservé aux adultes", [
            "Party est réservée aux personnes de 18 ans ou plus. En acceptant ces conditions, tu confirmes avoir 18 ans ou plus.",
        ]),
        ("Le respect avant tout", [
            "Pas de harcèlement : ni insultes répétées, ni menaces, ni moqueries visant une personne, ni messages insistants à quelqu'un qui ne veut pas te répondre.",
            "Interdits : propos haineux (origine, religion, genre, orientation, handicap…), contenu sexuel ou violent, contenu illégal, photos d'autres personnes sans leur accord, usurpation d'identité, spam et publicité.",
            "Un filtre retire automatiquement certains mots ; il ne remplace pas le bon sens.",
            "Aucune tolérance pour les contenus choquants ou les utilisateurs abusifs : le contenu est retiré et le compte peut être suspendu ou banni.",
        ]),
        ("Messages directs et demandes", [
            "Tu écris directement aux personnes avec qui tu as un vrai lien dans Party : un groupe en commun (hors Membres Vendredi Party), un événement non public en commun, ou l'organisateur d'un événement auquel tu as répondu (et l'organisateur à toi). À tout autre membre, tu envoies une demande de message : un seul message texte, sans photo, vocal, lien ni numéro de téléphone. Tant que la personne ne l'a pas acceptée, tu ne peux rien envoyer d'autre ; si elle la supprime, tu n'en es pas prévenu.",
            "Au plus 10 nouvelles demandes par jour et 30 en attente. Relancer quelqu'un qui ne répond pas ou a supprimé ta demande, ou créer un groupe pour l'obliger à te lire, c'est du harcèlement. Dans Réglages › Confidentialité, « Demandes de message » te permet de n'en recevoir de personne.",
            "Le filtre automatique et ces conditions valent pour tous les messages, messages directs et demandes compris.",
            "Les messages directs, les demandes de message et les groupes privés créés depuis « Nouveau message » ne sont jamais lus par l'administration de Party : un modérateur ne voit que ce qu'on lui signale. Les autres groupes peuvent être lus par l'administrateur principal de Party (Root) pour la modération.",
        ]),
        ("Le jeu n'a aucune valeur en argent", [
            "Les pièces, objets, cartes et récompenses des jeux de Party n'ont aucune valeur monétaire. Ils ne s'achètent pas, ne se vendent pas et ne s'échangent pas contre de l'argent ou un service, ni dans Party ni ailleurs.",
            "Toute vente, achat ou proposition de vente d'un objet ou d'un compte est interdite. Le paiement entre amis et les billets d'événement ne concernent jamais un objet du jeu.",
        ]),
        ("Pronos et confettis", [
            "Les Pronos se jouent entre amis, pour l'honneur : on devine, on marque des points et, dans un groupe ou un événement, on lance des confettis pour rire. Apple et Google ne sont ni organisateurs ni sponsors des Pronos.",
            "Les confettis sont gratuits et n'ont aucune valeur. Ils ne s'achètent pas, ne se vendent pas, ne s'échangent pas et ne se transfèrent pas d'une personne à une autre. Ils ne se convertissent en rien (ni argent, ni boisson, ni objet du jeu) et aucun lot ne récompense le classement.",
            "Il est interdit de régler un prono ou des confettis en argent, en boissons, en objets ou en services, dans Party ou ailleurs, et de proposer d'acheter ou de vendre des confettis. Jamais de prono sur l'alcool ni sur ce que boit quelqu'un.",
            "Un compte qui détourne les Pronos ou les confettis (argent, boissons, vente, triche) peut être suspendu, et ses confettis retirés. Un résultat qui te semble injuste se conteste ou se signale.",
        ]),
        ("Événements publics et groupes", [
            "Un événement public (visible par tous les comptes et par son lien), créé par un membre qui ne publie pas directement, attend l'accord d'un organisateur, d'un co-admin ou d'un admin de Vendredi Party avant d'être visible ; ils peuvent le refuser. Les admins et co-admins de Vendredi Party peuvent aussi, à tout moment, modifier ses informations ou le retirer, même après sa publication.",
            "Dans tes groupes, tu es libre : un événement réservé à tes groupes est publié sans validation de Vendredi Party ; seul un groupe qui le demande fait valider les événements de ses membres par qui le gère. Les administrateurs de Party voient la liste de tous les groupes et de leurs membres, jamais les messages, photos ni vocaux des groupes privés créés depuis « Nouveau message ».",
        ]),
        ("Paiements, billets et bar", [
            "Party ne vend rien et ne touche jamais d'argent : ni paiement, ni portefeuille, ni commission. Un organisateur peut indiquer un prix et un moyen de payer qui est le sien (Revolut, billetterie, sur place) ; le paiement se fait en dehors de Party, entre personnes. Un « J'ai payé » n'est confirmé que par l'organisateur.",
            "Le bar de la soirée est une option de l'organisateur pour une soirée privée entre amis, offerte ou à prix coûtant. Party note seulement qui a pris quoi et qui doit combien ; l'engagement à rembourser est une promesse entre personnes. L'organisateur est seul responsable de ses prix, de ce qu'il sert et du respect de la loi, en particulier sur l'alcool (âge minimum, pas d'alcool à une personne ivre). Tabac et drogues sont interdits.",
            "Boire n'est jamais obligatoire ni récompensé : dans les jeux, un verre d'eau compte toujours et personne n'est classé selon ce qu'il boit.",
        ]),
        ("Signaler et bloquer", [
            "« Signaler » existe sur chaque message, demande de message, profil, groupe, photo et réponse de jeu montrée à la table. Un modérateur reçoit le signalement avec une copie du contenu concerné : pour un message, ce seul message avec sa photo ou son vocal, et les 10 messages précédents seulement si tu coches « Joindre les 10 messages précédents » ; la personne signalée ne sait pas qui l'a signalée. Les signalements sont traités sous 24 heures.",
            "Tu peux bloquer quelqu'un depuis sa fiche ou une conversation : il ne peut plus t'écrire, t'envoyer de demande de message, te citer, t'inviter ni voir ta fiche. La liste « Personnes bloquées » est dans Réglages › Confidentialité.",
        ]),
        ("Sanctions", [
            "Selon la gravité, un modérateur peut masquer un contenu, avertir, suspendre un compte pour une durée choisie ou le bannir. Les sanctions visent le compte, jamais un appareil ou une connexion partagée. Quand un modérateur masque ton contenu, tu en es prévenu avec le motif et l'adresse pour le contester.",
            "Les signalements traités sont gardés un an, puis effacés. Supprimer ton compte efface aussi tes contenus et les signalements qui te visent.",
        ]),
    ]

    var body: some View {
        List {
            Section { Text("Party · Version du \(Self.updated)").font(.footnote).foregroundStyle(.secondary) }
                .listRowBackground(Color.clear)
            ForEach(Self.sections, id: \.0) { title, paragraphs in
                Section(title) { ForEach(paragraphs, id: \.self) { Text($0).font(.subheadline) } }
            }
            Section("Contact") {
                let email = store.terms?.contactEmail.flatMap { $0.isEmpty ? nil : $0 } ?? Self.supportEmail
                Text("Une question, un contenu à signaler en dehors de l'app, une demande sur tes données : écris à \(email).")
                    .font(.subheadline)
                if let url = URL(string: "mailto:\(email)") { Link("Écrire à \(email)", destination: url) }
            }
            if let terms = store.terms {
                Section {
                    if terms.accepted {
                        Label("Tu as accepté ces conditions", systemImage: "checkmark.seal.fill").foregroundStyle(.green)
                    } else {
                        Button("J'accepte les conditions") { Task { _ = await store.acceptTerms() } }
                            .disabled(store.busy.contains("accept"))
                            .accessibilityIdentifier("terms-accept-settings")
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Conditions d'utilisation")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadTerms() }
    }
}

/// Réglages › Confidentialité › Personnes bloquées : blocage commun à toute l'app, avec « Débloquer ».
struct BlockedPeopleView: View {
    @ObservedObject var store: ModerationStore

    var body: some View {
        List {
            Section {
                if let people = store.blocked {
                    if people.isEmpty {
                        Text("Personne n'est bloqué.").foregroundStyle(.secondary)
                    }
                    ForEach(people) { person in
                        HStack(spacing: 12) {
                            Initials(name: person.name, photo: person.photo, size: 40)
                            Text(person.name).font(.body.weight(.semibold))
                            Spacer()
                            Button("Débloquer") { Task { await store.setBlocked(person.id, false) } }
                                .buttonStyle(.bordered)
                                .disabled(store.busy.contains(person.id))
                                .accessibilityIdentifier("unblock-\(person.id)")
                        }
                        .motionTransition(.opacity)
                    }
                } else if store.error == nil {
                    ProgressView()
                }
                if let error = store.error { Text(error).foregroundStyle(.red) }
            } footer: {
                Text("Une personne bloquée ne peut plus t'écrire, te citer, t'inviter ni voir ta fiche. Elle n'en est pas prévenue.")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .motion(Motion.smooth, value: store.blocked)
        .navigationTitle("Personnes bloquées")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadBlocked() }
        .refreshable { await store.loadBlocked() }
    }
}
