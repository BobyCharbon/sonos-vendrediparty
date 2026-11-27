# Topo : la version Apple (27.11.2026)

Pour l'admin, en deux listes. Base : ce que `develop` a de plus que la prod (`git log 0785957c..03357b5c`, 64 commits),
ce qui est déjà en prod depuis le build 216 refusé (`9de754ed..0785957c`), et les coupures « App Store » relues une à
une dans le code (iPhone, serveur, module Événements).

Trois façons de couper, à ne pas confondre :
- **Hors de l'app iPhone** : le code n'est même pas dans l'app envoyée à Apple (fichiers compilés seulement dans la BETA).
- **Présent mais jamais ouvert** : le code est dans l'app, mais l'app App Store ne l'ouvre jamais, quoi que dise le serveur.
- **Refusé par le serveur / caché à l'écran** : Party reconnaît l'app App Store (« PartyStore ») et ne lui envoie pas la
  fonction, ou la page ne l'affiche pas. Le site web, l'app BETA et Android gardent tout.

## A. Enlevé ou caché dans la version Apple

| Quoi | Comment | Où (pour vérifier) |
|---|---|---|
| Jeux à boire : Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Beer pong, Biskit, Purify Test | Refusés par le serveur (création, salle, code, QR : 403) ; leur code (scripts, styles, textes) n'est même pas envoyé à l'app (`/static-store/`, blocs coupés) | `app/store_app.py` (HIDDEN_GAMES), `app/store_static.py`, `app/main.py` |
| Casino et Blackjack | Même chose (refusés + cachés) | idem, `style.css` |
| Gorgées, « 🍻 Alcool », « ⭐ Mode points », modes Hot / Mix, thème WTF de Pour ou contre, paquet « Entre amis » de Qui est le plus… | Toute partie de l'app est marquée « store » : 0 gorgée, réglage refusé ; une partie du web avec gorgées est refusée à l'app | `store_app.flag`, `refused`, `refused_settings` |
| Questions et mots qui parlent de boisson, drogue, tabac ; questions sur Android | Retirés des banques tirées dans l'app (Quiz, L'Intrus, Divan, Pour ou contre, Masque…) | `store_app.clean`, `clean_platforms` |
| Prénoms et textes de joueurs insultants, drogue, haine | Refusés ou remplacés par « Joueur » dans les parties de l'app | `store_app.check_text`, `quiz.py` |
| Code des jeux cachés et fichiers de Zicou | Jamais servis à l'app, même par une adresse bricolée | `store_static.blocked` |
| Bar de la soirée | Pas d'écran bar natif ; serveur : `bar: false` pour l'app, page sans bar, pas de notification du bar (send-push), cloche sans `bar_…`, billet Wallet sans bar ; l'app ne l'ouvre jamais même si le serveur dit oui | `/api/features`, `bar_page`, `SettingsStore.loadFeatures`, `activity.tsx` |
| Onglet Musique | Caché (barre web et barre native). La musique reste joignable par le code à 6 chiffres de l'hôte (Jeux › Code) ou son QR | `index.html` (STORE_APP), `native-tabs.js` |
| « Ajouter un titre » (action rapide) et extension Partager pour la musique | Absents de l'app App Store ; Partager › Party ne propose que « Créer l'événement » | `QuickActions.swift`, `project.yml` |
| Réglages de notification Musique | Cachés, sauf chez l'hôte d'une soirée | `NotificationSettingsView.swift` |
| Zicou | Présent dans l'app mais jamais lancé (`zicouBuild` faux hors BETA) ; serveur : routes en 404, page sans Zicou, ni réactions ni zone « 🐾 Zicou » de Ton avis | `AppConfig.zicouBuild`, `features.compagnon_enabled` |
| Agenda | Hors de l'app iPhone (3 fichiers en `#if BETA`) ; serveur : routes en 404 pour l'app ; page : ni entrée ni écran | `ios/Party/Agenda/`, `apps_off`, `agendaOn` |
| Pronos | Hors de l'app iPhone (6 fichiers en `#if BETA`) ; serveur : 404 ; page : ni carte ni bouton | `ios/Party/Pronos/`, `pronosOn` |
| Confettis (des Pronos) | Éteints avec les Pronos : `patates: false` pour l'app | `/api/features` |
| Souvenirs | Hors de l'app iPhone (6 fichiers en `#if BETA`, pont à `null`, ni bulles ni bandeau) ; serveur : éteints pour l'app quoi qu'il arrive ; page : rien | `ios/Party/Souvenirs/`, `souvenirs_enabled`, `souvenirsOn` |
| Couverture d'événement (« Changer la couverture ») | Serveur : éteinte pour l'app ; page : aucun bouton | `covers_enabled`, `coversOn` |
| Cartes secrètes de la Pyramide (panneau natif) | Présent mais jamais ouvert (`storeLocked`) — la Pyramide est de toute façon refusée | `NativeBridge.swift` |
| Stats Purify Test | Hors de l'app iPhone (`#if BETA`) ; serveur : 404 ; « Mes stats de jeu » n'a que Méninges | `AnnouncementsView.swift`, `no_purity_in_store`, `Settings.tsx` |
| Bouton « ✨ IA » sur la fiche d'un événement | Caché dans l'app (l'exemple citait du vin). « ✨ Avec l'IA » pour CRÉER un événement reste | `event/[id]/index.tsx` |
| Événements publics « à boisson » (apéro, bière, chicha, vapotage…) | Ni dans la liste ni dans la recherche de l'app, sauf pour leurs invités et organisateurs | `storeEvents.ts` (DRINK_RE) |
| Étiquettes à boisson (« #bar »…) | Cachées des filtres, de la fiche et des abonnements | `data.ts`, `main.py` (abonnements) |
| Emojis 🍻 🍷 des groupes et du Pot commun | Montrés en 🎉, absents du choix | `groups.ts`, `NewChatGroupView.swift`, `TricountListView.swift`, `neutral_emojis` |
| Notifications qui parlent de boisson | Texte neutre (push et cloche) | `send-push`, `activity.tsx` |
| CGU et confidentialité | Version de l'app sans sections bar, Pronos, Agenda | `terms.ts`, `privacy.tsx` |
| Site de test et base de TEST | Jamais ouverts dans l'app App Store, pont natif réservé au site de prod | `AppConfig.internalHosts`, `bridgeHosts` |
| Mini-sondages | Retirés seulement du TEXTE de la fiche App Store ; ils restent dans le formulaire de l'événement (rien de caché) | `fiche-app-store.md` |
| Vidéo d'aperçu | Plus de vidéo pour cet envoi : l'ancienne est à SUPPRIMER dans App Store Connect (à faire par toi) | `checklist-envoi.md` |
| Apple TV | Pas envoyée avec cette version (elle montre encore des gorgées) | `checklist-envoi.md` |

## B. Nouveau et visible depuis le build 216

« En prod » = déjà sur party.bobycharbon.ch ; « avec ce lot » = sur `develop`, arrive en prod avec les migrations
ci-dessous et le serveur ; « nouveau build » = seulement dans la nouvelle app iPhone.

| Nouveau | Arrive | Dans les notes (partie A) / le guide (partie B) ? |
|---|---|---|
| Jeux à boire, bar, Musique (onglet) retirés, musique par code à 6 chiffres | En prod (refus 1.4.3) + nouveau build | Oui : A « Changes since the 1.4.3 rejection » et « Web content » ; B4.14, B4.15, B7 |
| Présences à la main, avec des personnes sans compte (« Théo du bar ») | En prod (27.11, migration 20261126150000) | A : non (plus de place) ; B : **oui, ajouté le 27.11** (B4.5, PDF régénéré) |
| Conditions d'utilisation en grand avant d'écrire dans une discussion | En prod (web) + nouveau build | En partie : B4.12 point 2 (« the first message asks you to accept the Terms ») ; A « Terms first ». Le « en grand » n'est pas décrit |
| Réglages des groupes : rôles (co-admin, organisateur), « Qui peut… », accepter chaque nouveau membre, transmettre | Avec ce lot (20261123110000) + nouveau build | B4.13 : oui (une phrase) ; A : non |
| Recherche d'une personne par numéro, tous les formats suisses | Avec ce lot (20261123090000) | Non décrit (B4.13 ne parle pas d'« Ajouter quelqu'un ») |
| Pot commun : moyens de paiement cachés tant qu'on ne touche pas « Montrer mes moyens de paiement dans ce pot » | Avec ce lot (20261126140000) + nouveau build | Oui : A « Payments », B4.16, B7 |
| Pot commun : CGU avant d'ajouter une dépense, « Signaler » une dépense ou un ticket | Avec ce lot (20261126130000) + nouveau build | Oui : A « Payments », B4.16, B6 |
| Pot commun : « Rembourser » (montre l'IBAN / le lien de l'ami) | Nouveau build | Oui : A, B4.16 |
| Pot commun dit sur la page d'invitation (« Je viens ! ») et après « Pas présent » | Avec ce lot (20261126120000) | Non décrit (B4.16 dit seulement qu'on entre dans le pot en répondant Présent) |
| Profil de paiement filtré (titulaire, note) ; IBAN de l'organisateur seulement en « On me paie » | Avec ce lot (20261126160000) | Rien à montrer à Apple (B4.11 / B4.16 disent déjà « On me paie ») |
| « Signaler le groupe » (son nom) | Avec ce lot (20261126140000) + nouveau build | Oui : B4.13, B6 ; A : non |
| Case « J'ai 18 ans ou plus et j'accepte les conditions » avant de jouer, vérifiée par le serveur | Avec ce lot (serveur) | Oui : A « Games », B4.14, B6 |
| Bloquer : effet immédiat (messages qui disparaissent, mini-profil « Débloquer ») | Avec ce lot (web) + nouveau build | Oui pour les messages (A « Discussions », B4.12 point 8) ; « Débloquer » dans le mini-profil non décrit (B4.12 dit Réglages › Personnes bloquées) |
| « Plus tard » des CGU jamais muet (une phrase dit pourquoi on ne peut pas continuer) | Avec ce lot (web) + nouveau build | Non décrit |
| Photo de profil facultative (« complète ton profil » ne la demande plus) | Avec ce lot (20261126130000) | Oui : B4.1 |
| Billets QR de la Soirée démo : à se remettre soi-même (« Remettre à tous les présents ») | Avec ce lot (nettoyage de la démo) | Oui : A « Try it » 1, B2, B4.10 |
| Discussions d'événement : photos et vocaux effacés à 90 jours | Avec ce lot (20261126160000) | Politique de confidentialité ; rien à montrer |
| Recherches de personnes gardées 1 h en empreinte | Avec ce lot (20261126100000) | Politique de confidentialité ; rien à montrer |
| Phrases d'autorisation propres à l'app App Store (caméra sans Souvenirs, calendrier limité aux sondages) | Nouveau build | Oui : B8 |

Les « non décrit » ci-dessus sont de petites choses visibles sans explication ; la partie A est pleine (3 977 caractères
sur 4 000), donc rien n'y a été ajouté.

## C. Depuis 03357b5c (27.11)

| Commit | Quoi | Dans le guide ? |
|---|---|---|
| `f8f8f897` | Co-organisateurs proposés seulement parmi les personnes liées (admin du site : tout) ; feuille des CGU avec « 18 ans et plus » toujours visible au-dessus de « J'accepte » ; « Installe Party ! » jamais par-dessus Événements avant la fin de l'inscription ; lien de groupe sans compte (nom, emoji, couleur, qui invite) ; fiche publiée plus vite ; « + Proposer » dans l'en-tête en haut de la liste ; petits textes. Migration 20261127100000 (fichiers prod prêts, pas en prod) | Oui : B4.2, B4.5, B7 ; tutoriel 3.1, 3.5 |
| `112ef30b` | Suppression du compte : un refus du serveur est dit tel quel (plus « vérifie ta connexion »), contact support | B4.20 inchangé ; recette du jour de l'envoi (checklist) |
| `3592adf8` | iPhone : la feuille « J'accepte les conditions » montre les conditions de l'app App Store (sans bar ni Pronos) | Rien à dire à Apple (B7 dit déjà que les CGU de l'app n'ont ni bar ni Pronos) |
| lot 6 (textes) | Politique du 27 novembre 2026 (web = iPhone) : présences notées à la main, aperçu d'un lien de groupe, moyens de paiement du Pot commun (montrés si on a créé le pot ou l'a rejoint par son lien, sinon par « Montrer mes moyens de paiement dans ce pot »), IA en mode Modifier ; guide : B2 (Pot commun à créer), B4.2, B4.5 (Relancer, liste d'attente), B4.12 (discussion réservée, @toutlemonde, Ma note privée), B4.16, B7 ; App Privacy à 17 types ; plan de prod (9e fichier) | — |
| `56493e6a` | Suppression du compte jamais bloquée par une garde (approved_by, qui amène quoi, groupes d'un événement, photo de groupe) et blocage respecté (co-organisateur, présence notée, notifications) ; migration 20261127110000 **prête** (apply / rollback), pas en prod | Oui : B4.5, B7, tutoriel 3.5 (phrase du blocage, à garder seulement si la migration passe en prod) |
| `d7d4fddf` | iPhone : « 18 ans et plus » dans le bas fixe des conditions, Signaler « Traité sous 24 h · support@ », notifications coupées après la suppression du compte, écran Contacts à un seul bouton (5.1.1(iv)), Zicou du profil réservé à la BETA, Search History au manifeste | App Privacy à 17 types (§ 6 de la checklist) ; rien d'autre à dire |
| `97a34e0e` | Contrôle Apple, tour 4 (jeux de l'app) : prénoms nettoyés (« Joueur 1 »…), filtre à chaque entrée de prénom, Pour ou contre sur la banque de Party seule, argot et contournements filtrés, pages HTML brutes et /admin en 404 pour l'app, « Plus tard » vers Méninges seul, classement du Quiz numéroté | Oui : A « Games » (Méninges seul, nos dilemmes), B4.14, B6, tutoriel 6 |
| `6bbe45c9` | Lot 7 (recette iPhone) : « Publier » rend la main après 20 s sans seconde publication, lien de groupe → page du groupe, suppression du compte (clavier fermé, refus en entier), Mon profil, feuille « Avant de choisir ton surnom » | Rien à dire à Apple |
| `7daf1b9c` | Politique (web et iPhone) : accent cassé « montrÃ© » corrigé, test contre tout texte mal encodé | Rien à dire à Apple |
| lot 8 (textes) | Contrôle Apple, tour 5 : partie A (3 977 caractères : Méninges seul après « Plus tard », nos dilemmes, moyens de paiement des membres ajoutés d'office, numéro d'Apple-test 2), B2 / tutoriel 8 (« Rembourser » quand on doit à un membre), B4.3 (sans « polls » : un Guest+ n'a pas `polls.create`), B4.14, B4.18, B6 ; iPhone : bouton « Ouvrir l'admin du site (secours) » caché dans l'app App Store (/admin y répond 404) ; PDF régénéré | — |

`20261127090000` (présences, suppression du compte) est **déjà en prod** ; `20261127110000` (suppression-blocage) est
**prêt** (fichiers apply / rollback dans `supabase/prod/`, testé sur TEST, pas encore en prod) : sans lui, la phrase « une personne bloquée ne peut être ni notée présente ni ajoutée en co-organisatrice »
sort du guide (checklist).

## Reste à faire par l'admin

- [ ] Clé `storage_secret_key` à ajouter dans le coffre Supabase de prod (contrôle : une ligne dans `private.chat_files_gc_runs`).
- [ ] Dépôt GitHub `BobyCharbon/sonos-vendrediparty` à passer en PRIVÉ (ou `GITHUB_REPO` sur un dépôt privé à part).
- [ ] App Store Connect : AUCUNE version tvOS jointe ; App Privacy = les **17 types** (Search History ajouté le 27.11 ; manifeste : lot 6 iPhone, d7d4fddf), ni plus ni moins ;
      anciennes captures et ancienne vidéo d'aperçu SUPPRIMÉES (6,9" et Duo), nouvelles captures faites avec l'app App Store.
- [ ] Guide PDF : rejoindre `docs/app-store/guide-revue-apple.pdf` régénéré le 27.11 (lot 6 : B2, B4.2, B4.5, B4.12, B4.16, B7 ; lot 8, tour 5 : B2, B4.3, B4.14, B4.18, B6).
- [ ] Couverture de l'événement « Verknipt » : la vérifier / remplacer (aucune boisson visible).
- [ ] Lien Shotgun de « Hard Boat » : le nettoyer (sans `uhandle` ni `utm_*`).
- [ ] Relire le classement du Quiz dans l'app App Store (points seulement, aucun mot de boisson ni gorgée) ; au passage,
      relire à l'écran le classement par âge 18+ (§ 5 de la checklist).
- [ ] Mise en prod du lot dans l'ordre de la checklist (§ « Plan de mise en prod du 27.11 ») : ancres revérifiées le 27.11, toutes bonnes.
