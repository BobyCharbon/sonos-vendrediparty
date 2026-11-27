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
                Text("Connecte-toi par SMS : ton surnom et ta photo te suivent dans les jeux, et tu retrouves les événements où tu es invité.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            .listRowBackground(Color.clear)
            // Erreur (code faux ou expiré, numéro incomplet) AU-DESSUS du champ : sous le champ, le pavé numérique la
            // cachait (recette du 19.11 : le code s'effaçait sans explication visible).
            if let error = store.error {
                Section { Text(error).foregroundStyle(.red) }
                    .accessibilityIdentifier("login-error")
            }
            switch store.step {
            case .phone: phoneStep
            case .code(let number): codeStep(number)
            }
        }
        .scrollContentBackground(.hidden)
        // Numéro → code reçu, erreur qui apparaît : les sections glissent en place au lieu de sauter.
        .motion(Motion.smooth, value: store.step)
        .motion(Motion.snappy, value: store.error)
        .onChange(of: store.error) { error in if error != nil { Haptics.error() } }
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
        Task { if await store.verify(code) { Haptics.success(); dismiss() } else { code = "" } }

    }
}

/// Gérer mon compte : suppression définitive, confirmée en écrivant SUPPRIMER.
struct DeleteAccountView: View {
    @ObservedObject var store: AccountStore
    let isAdmin: Bool
    @State private var confirmation = ""
    @FocusState private var typing: Bool
    @Environment(\.dismiss) private var dismiss

    private static let word = "SUPPRIMER"

    var body: some View {
        Form {
            Section {
                Text("Cette action est définitive. Ton profil, tes messages, tes votes, tes réponses et tes préférences seront supprimés.")
                Text("Les événements que tu as créés et leurs discussions seront également supprimés, pour tout le monde.")
                if isAdmin {
                    Text("Si tu es le dernier administrateur, désigne d'abord un autre administrateur dans Membres.")
                        .foregroundStyle(.secondary)
                }
            } header: {
                Text("Supprimer mon compte")
            }
            // Refus (recette iPhone du 28.11) : le message rouge en entier, dans sa propre section au-dessus du champ,
            // jamais coupé dans le pied de section sous le clavier.
            if let error = store.error {
                Section {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("delete-error")
                }
            }
            Section {
                TextField("Écris \(Self.word) pour confirmer", text: $confirmation)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .focused($typing)
                    .accessibilityIdentifier("delete-confirm")
                Button(role: .destructive) {
                    typing = false  // clavier fermé : la réponse (ou le refus) se lit en entier
                    Task { if await store.deleteAccount() { dismiss() } }
                } label: {
                    HStack {
                        Text("Supprimer définitivement mon compte")
                        if store.busy { Spacer(); ProgressView() }
                    }
                }
                .disabled(confirmation != Self.word || store.busy)
                .accessibilityIdentifier("delete-account")
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Gérer mon compte")
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear { store.error = nil }
    }
}

/// Confidentialité : le texte du module web, en natif, et l'accord pour l'IA (tous les comptes connectés).
struct PrivacyView: View {
    /// Même texte que la politique du module web (web/events/src/app/privacy.tsx) : changer les deux ensemble.
    static let updated = "27 novembre 2026"
    /// App App Store (refus Apple 1.4.3, 25.11) : ni le bar, ni le Purify Test, ni les Pronos (éteints dans cette version),
    /// absents de l'app (même filtre que privacy.tsx).
    static var shown: [(String, [String])] {
        guard AppConfig.isStoreApp else { return sections }
        let cuts = [
            ("(Quiz, Méninges, Purify Test)", "(Quiz, Méninges)"),
            (" Bar de la soirée : 6 mois après sa fermeture.", ""),
            (" Pronos (réponses, confettis lancés, contestations, réactions) : jusqu'à la suppression du prono, de son groupe ou de son événement. Ton sac de confettis et son historique : jusqu'à la suppression de ton compte.", ""),
            (", pronos et confettis,", ","),
        ]
        return sections.map { title, paragraphs in
            (title, paragraphs.filter { !$0.hasPrefix("Bar de la soirée") && !$0.hasPrefix("Purify Test") && !$0.hasPrefix("Pronos :") }
                .map { p in cuts.reduce(p) { $0.replacingOccurrences(of: $1.0, with: $1.1) } })
        }
    }

    static let sections: [(String, [String])] = [
        ("Qui est responsable ?", [
            "Party (Vendredi Party : l'app iPhone, l'app Apple TV et le site) est édité par Ludovic Trombert, établi en France (Union européenne), responsable du traitement de tes données au sens du règlement général sur la protection des données (RGPD).",
            "Pour toute question ou demande sur tes données : support@vendrediparty.ch. Réponse en principe sous 30 jours.",
            "Party est réservé aux personnes de 18 ans et plus. Party ne fait aucune publicité, ne revend aucune donnée et n'utilise aucun outil tiers de mesure d'audience ni de suivi (« tracking »).",
        ]),
        ("Ton compte", [
            "Numéro de téléphone : il sert à te connecter avec un code reçu par SMS et à te reconnaître. Il est visible par toi, par les administrateurs qui gèrent les accès et, si tu le choisis dans tes réglages, par les membres de tes groupes.",
            "Surnom, prénom, nom et, si tu veux, photo de profil : ils te présentent aux autres dans les jeux, les événements et les groupes. Tu les modifies à tout moment dans Réglages › Mon profil.",
            "Rôle, groupes, amis et invitations : ils décident de ce que tu vois et de ce que tu peux faire.",
            "Origine de ton inscription : à la création de ton compte, Party note d'où tu viens (lien d'invitation d'un événement et la personne dont c'est le lien, lien d'un groupe et qui l'a créé, lien personnel d'un membre, lien « Partager » d'un événement, ou inscription directe) et si c'était dans l'app iPhone ou sur le site. Seuls les administrateurs qui ont le droit « Voir l'origine des inscriptions » le voient, sur ta fiche et dans un compte par source. Rien n'est noté pour les comptes créés avant le 22 novembre 2026 ; tout est effacé avec ton compte.",
            "Nouveau compte : quand tu as fini de créer ton compte (prénom, nom et surnom), les personnes qui valident les membres reçoivent une seule fois une notification avec ton surnom, ton prénom et ton nom. Elles peuvent couper cette notification dans leurs réglages.",
        ]),
        ("Événements, groupes et messages", [
            "Tes événements, réponses (présent, absent…), votes, sondages, ce que tu amènes et tes messages servent à organiser les événements avec les personnes concernées. Ils sont visibles selon la visibilité de chaque événement ou groupe. Le jour et l'heure de chaque réponse et de chaque vote de date sont notés et se voient avec eux.",
            "Présences notées à la main : l'organisation d'un événement (organisateurs, co-organisateurs et administrateurs de Party) peut noter le nom (60 caractères au plus) et la réponse (Présent, Peut-être ou Absent) d'une personne qui n'a pas de compte, pour la compter. Seule l'organisation voit ce nom ; les autres ne voient que des nombres. La personne n'est jamais prévenue. Tout est effacé avec l'événement.",
            "Messages, photos et messages vocaux : envoyés seulement quand tu le décides. Le micro n'est utilisé que pendant que tu enregistres un vocal ou que tu dictes un texte ; ta voix dictée est transcrite en texte par le service vocal de ton système, pas par Party : Apple (Dictée) sur iPhone, Google ou Apple selon ton navigateur sur le web. Party et l'IA ne reçoivent que le texte. Les photos ne sont lues que celles que tu choisis.",
            "Discussion d'un événement : pour chaque discussion, Party garde ton niveau de notification (tout, mentions seulement, rien), ta sourdine et l'heure de ta dernière lecture, pour compter tes messages non lus ; personne d'autre ne les voit. La recherche dans une discussion n'est jamais gardée. Tout part avec l'événement ou avec ton compte.",
            "Organisateurs d'événements payants : les coordonnées de paiement que tu enregistres (IBAN, titulaire, liens de paiement comme Twint, note) sont montrées aux personnes qui ont répondu « Présent » à tes événements payants en « On me paie » (jamais en paiement en ligne ni sur place), pour qu'elles te paient. Party ne traite jamais l'argent lui-même.",
            "Billets : un billet QR personnel est créé pour tes événements à billets ; son passage à l'entrée est noté.",
            "Pot commun : les dépenses, les membres du pot (leur nom), les photos de tickets et ton profil de paiement, si tu choisis d'en indiquer un (IBAN, titulaire, liens de paiement comme Revolut, Twint ou PayPal) et s'il est montré dans ce pot (voir plus bas), sont vus par les membres du pot, pour se rembourser entre eux. On entre dans un pot par son lien, ou par un événement : quand l'organisateur d'un événement a choisi un pot commun, répondre « Présent » à cet événement, ou être noté « Présent » par l'organisateur, t'ajoute d'office à ce pot ; tu peux le quitter à tout moment dans Réglages › Pot commun › « Quitter ce pot commun » ; les autres membres voient ton nom tant que tu en fais partie. Tes moyens de paiement sont montrés aux autres membres si tu as créé le pot ou si tu l'as rejoint toi-même par son lien ; si tu y as été ajouté d'office (par un événement ou par un autre membre), ils restent cachés tant que tu ne choisis pas « Montrer mes moyens de paiement dans ce pot ». Tu changes ce choix à tout moment, pot par pot. Party ne touche jamais l'argent. Tout part avec le pot ; ton profil de paiement part aussi avec ton compte.",
            "Bar de la soirée, seulement si l'organisateur l'ouvre : tes commandes (articles, quantités, prix, heure), ce qui t'a été servi et par quel barman, ton engagement à rembourser, ton solde et tes remboursements sont vus par toi, les organisateurs et les barmans de l'événement. Les organisateurs peuvent en exporter un récapitulatif en PDF. Ta carte Apple Wallet du bar montre ton solde. Party ne vend rien et ne traite jamais l'argent : tu rembourses l'organisateur en dehors de l'app. Tout est effacé 6 mois après la fermeture du bar ; avec ton compte, ton nom en est retiré.",
            "Covoiturage, seulement si l'organisateur l'ouvre et si tu y prends part : les participants et les organisateurs de l'événement voient ton surnom, ta photo, si tu conduis ou cherches une place, tes places libres, la ville de départ que tu indiques (facultative) et qui monte avec qui. Tu le quittes quand tu veux ; répondre « Pas présent » t'en retire. Party ne gère ni argent ni partage de frais.",
            "Invitation par lien : la page de l'invitation se lit sans compte et ne montre que le titre, la date, le nom du lieu, le prénom de la personne qui invite et au plus trois prénoms de ceux qui viennent (aucun si l'organisateur cache la liste). Pour répondre, tu te connectes avec ton numéro (code par SMS) et tu complètes ton profil (prénom, nom et surnom ; photo facultative) : l'organisateur voit ton surnom, ta réponse, par quel lien tu es venu et quand le lien a été ouvert, jamais ton numéro. Les relances de l'organisateur passent par une notification (si tu as l'app, avec son interrupteur « Invitations ») ou par un message qu'il t'envoie lui-même.",
            "Liens nommés et accord de l'organisateur : chaque lien d'invitation porte le nom que lui donne celui qui le crée (organisateur ou invité) ; l'organisateur voit qui est venu par quel lien. Pour un événement sans lien public, si tu viens par le lien d'un invité, l'organisateur et ses co-organisateurs voient ta demande (ton surnom, ta photo, ta réponse et qui t'a invité) jusqu'à ce qu'ils l'acceptent ou la refusent.",
            "Photo de groupe : facultative, choisie par qui gère le groupe ; seuls ses membres la voient et peuvent la signaler. Elle appartient au groupe : elle reste tant que le groupe la garde (son créateur la change ou la retire, la modération peut la retirer) et part avec le groupe.",
            "Lien d'un groupe : sans compte, la page du lien ne montre que le nom, l'emoji et la couleur du groupe et le surnom de la personne qui invite, jamais ses membres (ni leur nombre, ni la photo du groupe).",
            "Ajouter quelqu'un à un groupe : la recherche se fait par numéro de téléphone exact ou par au moins 3 lettres d'un nom, et ne montre que le surnom, la photo et l'initiale du nom (5 personnes au plus, jamais le numéro). Une recherche par numéro exact révèle qu'une personne qui a ce numéro est sur Party : elle est limitée à 30 recherches par heure, ne montre ni les personnes bloquées ni celles qui refusent les demandes, et la personne trouvée reçoit une invitation qu'elle accepte ou non.",
            "Groupe d'un événement : si tu coches « Rejoindre aussi le groupe », tu entres dans le groupe choisi par l'organisateur ; ses membres voient ton surnom, ton nom et ta photo (jamais ton numéro, sauf si tu le montres), lisent et écrivent dans sa discussion et peuvent t'inviter à ses événements. Base : ta demande. Tu quittes le groupe à tout moment ; nous gardons seulement la date de ton départ pour ne jamais t'y remettre sans toi, jusqu'à la suppression du groupe ou de ton compte.",
        ]),
        ("Discussions et messages directs", [
            "Qui peut t'écrire : une personne avec qui tu as un groupe en commun (hors Membres Vendredi Party), un événement non public en commun, ou l'organisateur d'un événement auquel tu as répondu t'écrit directement. Les autres membres (seulement Membres Vendredi Party en commun, le même événement public, ton numéro dans leurs contacts, ou trouvés par la recherche) ne peuvent t'envoyer qu'une demande de message : un seul message texte, sans photo, vocal, lien ni numéro. Tu l'acceptes, la supprimes, bloques ou signales la personne sans lui répondre ; elle n'est jamais prévenue d'un refus. Une personne bloquée, dans un sens ou dans l'autre, ne peut ni t'écrire ni t'envoyer de demande.",
            "Demandes de message : dans Réglages › Confidentialité, tu choisis d'en recevoir de tout membre (par défaut) ou de personne. Une demande te prévient par une notification « … veut t'écrire », sans son contenu, une seule fois par personne, avec son interrupteur « Demandes de message » dans Réglages › Notifications.",
            "Le filtre automatique des mots et les conditions d'utilisation s'appliquent à tous les messages : groupes, événements, messages directs et demandes compris.",
            "Ce que l'administration de Party lit : les messages directs, les demandes de message et les groupes privés créés depuis « Nouveau message » ne sont jamais lus par l'administration ni par l'administrateur principal (Root) ; un modérateur ne voit que ce qu'on lui signale. Les autres groupes (créés depuis Groupes, groupe d'un événement, Membres Vendredi Party), y compris ceux qui existaient déjà, peuvent être lus par l'administrateur principal (Root) pour la modération. Les discussions d'événement sont lues par les personnes de l'événement et son organisation (organisateurs, administrateurs de Party). Les administrateurs de Party voient la liste de tous les groupes, groupes privés compris (nom, emoji, couleur, créateur et membres), jamais les messages, photos ni vocaux d'un groupe privé.",
            "Nouveau message : pour te proposer à qui écrire, Party utilise seulement tes vrais liens : tes conversations, les membres de tes groupes (hors Membres Vendredi Party), les personnes croisées à un événement des 60 derniers jours et, sur iPhone si tu l'autorises, tes contacts déjà inscrits. Jamais de personnes prises au hasard sur tout le site. La recherche se fait par prénom, nom ou surnom, jamais par numéro.",
            "« Déjà vu N fois » : sur la fiche d'un membre et dans Nouveau message, Party compte les soirées passées où vous étiez tous les deux présents (réponse « Présent », organisation de l'événement ou billet scanné) et montre les trois dernières, seulement parmi les événements que tu peux voir. Ce nombre est calculé à chaque affichage à partir des réponses ; rien n'est gardé à part.",
            "Note privée : sur le profil d'une personne, tu peux écrire une note pour toi (500 caractères au plus, par exemple où vous vous êtes rencontrés). Elle n'est visible que par toi : jamais par la personne, ni par l'administration de Party à l'écran, et elle n'est jamais partagée. Tu la modifies ou l'effaces quand tu veux ; elle est effacée avec ton compte ou celui de la personne.",
            "Confirmations de lecture : dans un message direct, l'autre voit « Vu » quand tu as lu son dernier message, seulement si vous avez tous les deux laissé « Confirmations de lecture » allumé (Réglages › Confidentialité) ; si tu le coupes, tu ne vois plus celles des autres. « écrit… » passe en direct, seulement pendant que tu écris, et n'est jamais enregistré. Ni l'un ni l'autre dans une demande ni avec une personne bloquée.",
        ]),
        ("Contacts de ton iPhone", [
            "Seulement si tu l'autorises : l'app transforme chaque numéro de tes contacts en une empreinte (un code calculé à partir du numéro : le numéro n'y est pas écrit en clair, mais quelqu'un qui connaît déjà un numéro peut reconnaître son empreinte), sur ton iPhone, et l'envoie pour reconnaître les personnes déjà inscrites. Les noms de tes contacts ne quittent jamais ton iPhone et le serveur ne garde pas ces empreintes. Ces personnes te sont aussi proposées quand tu écris un nouveau message. Les personnes qui ont ton numéro dans leurs contacts peuvent voir que tu es sur Party et t'envoyer une demande de message.",
        ]),
        ("Ton agenda", [
            "Quand tu ajoutes un événement à ton agenda, ton agenda s'abonne à ton calendrier « Vendredi Party », un lien secret propre à toi : il n'y lit que les événements que tu y as ajoutés et, une fois l'agenda activé, ceux où tu réponds Présent ou Peut-être (ou votes Oui / Si besoin pour une date), jamais un événement que tu ne vois plus dans Party (titre, description, lieu, date, ou tes dates votées tant que la date n'est pas fixée) et suit leurs changements. Party note seulement quand ton agenda l'a relu pour la dernière fois, pour savoir qu'il est abonné. Tout disparaît avec ton compte.",
            "App iPhone, seulement si tu l'autorises, si l'agenda abonné n'est pas disponible : l'app met elle-même les dates d'un sondage dans ton calendrier, puis, une fois la date fixée, garde la bonne et retire les autres. Elle ne garde ni n'envoie rien d'autre ; rien de ton calendrier ne quitte ton iPhone.",
        ]),
        ("Jeux, musique et stats", [
            "Pendant une soirée, ton prénom et tes réponses de jeu sont visibles par les joueurs de la partie (et sur l'écran de la soirée). Les titres que tu proposes sont envoyés à Spotify pour être recherchés et joués sur le compte de l'hôte, avec ton prénom visible dans la file.",
            "Stats de jeux (Quiz, Méninges, Purify Test) : gardées avec ton compte pour te montrer tes progrès et les classements.",
            "Prénoms d'invités du Quiz : le prénom d'un joueur sans compte (appareil d'invité, ou ajouté par l'animateur pour un joueur sans téléphone) apparaît avec ses points dans le classement général du Quiz, visible de tous les joueurs ; il est effacé après 6 mois sans jouer.",
            "Purify Test : tes réponses aux questions ne sont jamais enregistrées. Seul ton score global l'est ; ton profil par catégorie se voit à la fin du test, puis disparaît. Tu n'apparais dans le classement général que si tu l'actives (Réglages › Mes stats de jeu).",
            "Pronos : tes pronos, tes réponses, les confettis que tu lances et ceux que tu ramasses, l'historique de ton sac (toi seul le vois), tes contestations, tes avis sur un résultat contesté et tes réactions. Avant le dévoilement, les autres joueurs voient seulement que tu as joué ; après, ils voient ta réponse et ce que tu as ramassé. Le classement de la saison montre le rang et les confettis de chacun, jamais ce que l'un a pris à l'autre. Rien de tout cela n'est envoyé à un tiers.",
            "Invités sans compte : un compteur de parties jouées est gardé avec l'identifiant de ton appareil (jamais ton adresse IP), effacé après 6 mois sans visite.",
        ]),
        ("L'IA (Anthropic, Claude)", [
            "Seulement après ton accord exprès (une feuille te le demande avant la première fois), Party envoie à Anthropic ce que tu confies à l'IA : le texte de ton avis (et la transcription de ta voix) pour le mettre au propre ; avec l'assistant des événements, ta description, tes captures d'écran, tes photos, les liens que tu donnes, ton surnom, les noms de tes groupes, des catégories et des étiquettes, et les personnes déjà choisies, sous un alias ; la liste des membres n'est jamais envoyée ; pour modifier un événement (« Modifier » avec l'IA), aussi son contenu actuel (titre, description, date, lieu, sondages, qui amène quoi, prix et infos de paiement), les personnes toujours sous un alias ; pour un ticket du pot commun, sa photo. La première capture peut devenir la couverture de l'événement ; elle est effacée avec lui.",
            "Ton numéro n'est jamais envoyé. Anthropic traite ces données pour répondre et ne les utilise pas pour entraîner ses modèles. Tu vois, retires ou redonnes ton accord à tout moment dans Réglages › Confidentialité ; sans accord, tout marche sans l'IA.",
            "Chaque appel est noté (date, coût, ce que tu as demandé) pour les plafonds mensuels et le contrôle des coûts ; chaque appel est effacé au bout de 12 mois, et tout part avec ton compte.",
        ]),
        ("Tes avis sur l'app (« Ton avis »)", [
            "Quand tu écris un avis (idée, bug), l'administrateur reçoit ton texte, ton prénom, l'écran où tu étais et ton appareil (modèle, version du système et de l'app). Il peut te répondre dans l'app.",
            "Si tu modifies ton avis, les versions précédentes sont gardées avec leur date (au plus les 20 dernières) pour que l'administrateur voie ce qui a changé. Elles partent avec l'avis.",
            "Pour corriger l'app, l'administrateur peut confier un avis à une IA de développement : l'avis est alors publié sur GitHub (où le code de Party est gardé, visible par tous), puis lu par Claude (Anthropic). Cela n'arrive que si tu as donné ton accord pour l'IA, et toujours sans ton prénom ni ton numéro. Sans accord, ton avis reste chez l'administrateur.",
        ]),
        ("Notifications, Apple Wallet et appareils", [
            "Notifications : l'adresse de notification de ton appareil (Apple Push Notification service pour l'iPhone, service push de ton navigateur sur le web) est enregistrée avec ton compte. Chaque type de notification a son interrupteur dans Réglages › Notifications. L'historique des notifications est effacé après 90 jours.",
            "Apple Wallet : si tu ajoutes un billet, le pass contient ton surnom, l'événement et ton QR ; ton iPhone s'inscrit auprès de Party pour recevoir ses mises à jour.",
            "Identifiant de l'appareil : Party enregistre un identifiant d'invité tiré au hasard (pour te reconnaître à la soirée sans compte), le jeton de notifications de ton appareil et, si tu ajoutes un billet à Wallet, l'identifiant d'inscription de ton iPhone. Ils servent seulement à faire marcher l'app, jamais à te suivre ni à faire de la publicité.",
            "Journaux techniques : le serveur garde les connexions et les actions d'administration (date, compte, adresse IP) pour la sécurité, pendant 12 mois, et des journaux d'erreurs sans contenu de message, effacés à chaque mise à jour du serveur. Quand tu cherches quelqu'un pour l'ajouter à un groupe, Party garde une trace de la recherche pendant 1 heure, pour limiter les abus.",
        ]),
        ("Qui reçoit tes données (sous-traitants)", [
            "Supabase (société américaine) : base de données et connexion, hébergées en Suisse (Zurich).",
            "Twilio : envoi du code de connexion par SMS (ton numéro).",
            "Anthropic : l'IA, seulement avec ton accord (voir plus haut).",
            "GitHub : garde le code de Party ; y sont publiés, visibles par tous et sans ton prénom, les avis confiés à l'IA de développement, seulement avec ton accord pour l'IA.",
            "Spotify : recherche et lecture des titres de la soirée.",
            "Apple : notifications de l'iPhone (APNs), billets Apple Wallet, app Apple TV, et la dictée vocale sur iPhone (transcription de ta voix, seulement quand tu dictes).",
            "Google : la recherche d'un lieu, dans l'assistant et dans le formulaire d'un événement (le texte tapé et l'adresse IP de ton appareil), et la dictée vocale dans Chrome (transcription de ta voix, seulement quand tu dictes).",
            "Infomaniak (Suisse) : messagerie de l'adresse de contact, quand tu nous écris.",
            "Le serveur de Party est hébergé en France, chez l'éditeur lui-même (hébergeur : l'éditeur) ; la base de données (Supabase) est à Zurich, en Suisse. Supabase, société américaine, ainsi que Twilio, Anthropic, GitHub, Spotify, Apple et Google peuvent traiter des données hors de l'Union européenne et de Suisse, notamment aux États-Unis, avec les garanties prévues par le RGPD et la nLPD (Data Privacy Framework ou clauses contractuelles types).",
            "Chacun de ces sous-traitants est tenu, par contrat, d'offrir à tes données une protection au moins égale à celle décrite dans cette politique.",
        ]),
        ("Combien de temps", [
            "Ton compte et ce qui s'y rattache : jusqu'à ce que tu le supprimes. Notifications : 90 jours. Signalements traités : un an. Compteur des invités : 6 mois sans visite. Ancien compte d'invité au prénom seul (créé avant le 10.11.2026, profil jamais complété ; depuis, le profil complet est toujours demandé) : effacé avec ses réponses 7 jours après le dernier événement auquel il était invité. Activité de la soirée : le temps de la soirée et au plus 3 jours. Covoiturage, demandes d'accord et liens d'invitation : jusqu'à la suppression de l'événement (ou de ton compte). Bar de la soirée : 6 mois après sa fermeture. Pronos (réponses, confettis lancés, contestations, réactions) : jusqu'à la suppression du prono, de son groupe ou de son événement. Ton sac de confettis et son historique : jusqu'à la suppression de ton compte. Messages directs : jusqu'à la suppression du compte de l'un des deux. Photos et messages vocaux des discussions : 90 jours. Demandes de message refusées ou supprimées : effacées aussitôt ; ignorées : effacées au bout de 30 jours. Copies jointes à un signalement (message, photo, vocal, 10 messages précédents) : effacées avec le signalement, au plus tard un an après. Pot commun (dépenses, membres, photos de tickets) : jusqu'à la suppression de la dépense ou du pot ; ton profil de paiement : jusqu'à ce que tu le retires ou que tu supprimes ton compte. Journal des connexions et des actions d'administration : 12 mois. Journal des appels à l'IA : 12 mois. Recherches de personnes : 1 heure.",
            "Les textes écrits par d'autres membres peuvent encore citer ton surnom après la suppression de ton compte.",
        ]),
        ("Tes droits", [
            "Tu peux à tout moment : voir et corriger tes données dans l'app ; retirer un accord (IA, contacts, notifications) ; supprimer ton compte dans Réglages › Gérer mon compte. La suppression efface ton compte, tes photos de profil, tes contenus (réponses, votes, messages directs avec leurs photos et vocaux, demandes de message, réglages des discussions, pronos et confettis, covoiturage, demandes, ton calendrier abonné), les événements que tu as créés, tes stats de jeux, tes accords pour l'IA et le journal de tes appels à l'IA ; tes avis sur l'app restent, sans ton nom.",
            "Restent pour les autres, sans lien avec toi, après la suppression de ton compte : les groupes que tu as créés (nom, emoji, couleur), les sondages, les choix proposés, les étiquettes et les lignes « qui amène quoi » que tu as ajoutés aux événements des autres, et les dépenses d'un Pot commun (ton nom y reste, pour que les comptes des autres restent justes).",
            "Pour obtenir une copie de tes données ou toute autre demande : support@vendrediparty.ch. Tu peux aussi te plaindre auprès de la CNIL (France), l'autorité de contrôle de l'éditeur ; si tu vis en Suisse, auprès du Préposé fédéral à la protection des données et à la transparence (PFPDT).",
        ]),
        ("Droit applicable (RGPD, nLPD, DSA)", [
            "Party est édité en France : le règlement général sur la protection des données (RGPD) s'applique à tous ses utilisateurs. Pour les personnes qui vivent en Suisse, la loi fédérale sur la protection des données (nLPD) s'applique aussi.",
            "Bases légales : le service que tu demandes (compte, événements, jeux, notifications que tu actives) ; ton consentement, que tu retires à tout moment (IA, contacts, calendrier de l'iPhone, photo) ; l'intérêt légitime de Party (sécurité, journaux techniques, modération et signalements) ; une obligation légale quand une autorité le demande. Aucune décision automatisée ni profilage ne produit d'effet juridique sur toi.",
            "Tes droits : accès, rectification, effacement, limitation, opposition et portabilité (une copie de tes données dans un format lisible), à demander à support@vendrediparty.ch. L'autorité de contrôle de l'éditeur est la CNIL (France) ; tu peux aussi te plaindre auprès de l'autorité de ton pays : l'Autorité de protection des données (Belgique), la CNPD (Luxembourg) ou le PFPDT (Suisse).",
            "Transferts : le serveur de Party est en France, dans l'Union européenne ; l'Union européenne reconnaît que la Suisse, où est hébergée la base de données, protège les données de façon adéquate ; pour les sous-traitants hors de l'Union européenne et de Suisse, voir « Qui reçoit tes données ».",
            "Règlement sur les services numériques (DSA) : point de contact unique pour les utilisateurs et les autorités : support@vendrediparty.ch, en français. Un contenu illicite se signale dans l'app (« Signaler ») ou à cette adresse.",
            "Éditeur : Ludovic Trombert, 420 route des Rosellets, 01170 Segny, France ; support@vendrediparty.ch. Établi dans l'Union européenne, il n'a pas de représentant à désigner (RGPD art. 27, DSA art. 13).",
        ]),
        ("Signalements et blocages", [
            "Quand tu signales un contenu, les modérateurs reçoivent ta raison, ton commentaire et une copie de ce contenu. Pour un message : ce seul message, avec sa photo ou son vocal copiés dans un espace réservé aux modérateurs, et les 10 messages précédents (texte, auteur, heure) seulement si tu coches « Joindre les 10 messages précédents ». La personne signalée ne sait pas qui l'a signalée. Si un modérateur masque ton contenu, une notification te dit pourquoi et où le contester. Les blocages restent jusqu'à ce que tu débloques.",
        ]),
    ]

    /// Compte connecté : Personnes bloquées et conditions d'utilisation (modération commune).
    var moderation: ModerationStore?
    /// Compte connecté, Discussions ouvertes : « Demandes de message » et « Confirmations de lecture ».
    var chatPrefs: ChatPrefsStore?

    var body: some View {
        List {
            Section {
                Text("Vendredi Party · Mise à jour du \(Self.updated)").font(.footnote).foregroundStyle(.secondary)
            }
            .listRowBackground(Color.clear)
            Section {
                NavigationLink { ContactNamesSettingsView() } label: {
                    SettingsRow(symbol: "person.crop.circle.badge.checkmark", tint: .green, title: "Noms de mes contacts",
                                hint: ContactNames.shared.access.canRead ? "Activé" : "Reconnaître les membres de ton répertoire")
                }
                .accessibilityIdentifier("contacts-settings")
                if let moderation {
                    NavigationLink { BlockedPeopleView(store: moderation) } label: {
                        SettingsRow(symbol: "hand.raised.fill", tint: .red, title: "Personnes bloquées",
                                    hint: "Elles ne peuvent plus t'écrire, te citer, t'inviter ni voir ta fiche")
                    }
                    .accessibilityIdentifier("blocked-people")
                    NavigationLink { TermsView(store: moderation) } label: {
                        SettingsRow(symbol: "doc.text.fill", tint: .gray, title: "Conditions d'utilisation",
                                    hint: "Respect, contenus interdits, sanctions, contact")
                    }
                    .accessibilityIdentifier("terms")
                }
            } header: {
                Text("Mes choix")
            }
            if let chatPrefs { ChatPrefsSection(store: chatPrefs) }
            if let moderation { AIConsentSection(store: moderation) }
            ForEach(Self.shown, id: \.0) { title, paragraphs in
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
        .task { await chatPrefs?.load() }
    }
}
