# Tutoriel de la revue Apple — version française (pour l'admin)

Même parcours que la partie B de `notes-for-review.md` (en anglais, jointe en PDF pour Apple). À relire avant l'envoi ;
chaque **📸** marque une capture utile (pour les captures App Store ou pour vérifier l'écran avant la revue).
Vérifié dans le code le 16.11.2026 (develop) et sur la prod en lecture seule (`/api/features` : discussions et invites_v2
allumés ; Zicou éteint ; `bar: false` pour l'app App Store, 25.11). Ce qui ne l'est pas porte la marque **À VÉRIFIER**.

## 0. Avant la revue

- Compte de démo : **+41 79 000 09 99**, surnom « Apple-test » (Apple Review), rôle **Guest+ (« User+ »)**, profil complet
  avec photo, code fixe (Supabase prod › Auth › Test OTP, valable jusqu'au 31.12.2027). Le code ne s'écrit que dans App
  Store Connect (champ Password), jamais dans le dépôt.
- Données à préparer : voir l'encadré « À FAIRE AVANT ENVOI » de `notes-for-review.md` (événement « Soirée démo » où Apple-test
  est invité (le bar est caché dans l'app App Store depuis le 25.11), groupe « Démo Apple » avec des messages, un message privé, et si
  possible « Démo Apple · Sondage »).
- Second compte de démo **« Apple-test 2 »** (Discussions v2, 18.11) : autre numéro à code fixe, sans groupe ni événement
  privé en commun avec Apple-test, qui lui a envoyé une **demande de message** en attente (point 4 bis de l'encadré).
- Guest+ n'a pas « Publier sans validation » ni « Voir les événements » (il voit les événements publics et ceux où il est
  invité). Groupes libres (22.11) : un événement réservé à « Démo Apple » est publié aussitôt ; un événement public ou
  « Sur invitation » sans groupe attend une validation. Valider vite pendant la revue.
- Corrections annoncées par le coordinateur (décrites ci-dessous comme en place) — **À VÉRIFIER en prod avant l'envoi** :
  « Bloquer » masque aussitôt les messages et prévient les modérateurs ; bar caché dans l'app App Store (refus 1.4.3, 25.11 ; le web
  garde ses règles : bar payant seulement sur un événement non public) ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
  section paiements. Les sections bar des CGU et de la politique n'existent que sur le web : jamais avec `?app=ios`
  ni dans le nouveau build (contrôle Apple, tour 2).

## 1. Plan de l'app

L'app s'ouvre sur **Événements** (sauf au milieu d'une partie de jeu). Barre d'onglets native :

| Déconnecté | Connecté | Fait en |
|---|---|---|
| Jeux | Jeux | page web du site |
| Événements | Événements | page web du site (module Événements) |
| — | Discussions | natif |
| Se connecter | Réglages | natif |

## 2. Se connecter

1. Onglet **Se connecter** › ligne **Se connecter**.
2. Garder **Suisse +41**, taper `079 000 09 99` › **Recevoir un code par SMS**.
3. Taper le code fixe : la connexion part toute seule au 6e chiffre. 📸 (écran du numéro, sans le code)
4. Le dernier onglet devient **Réglages** (profil en tête) ; l'onglet **Discussions** apparaît.

Un nouveau compte complète ensuite son profil : en haut des Réglages, la ligne « Profil à compléter » ouvre « Mon profil » (sur le web, l'étape s'appelle « Faisons connaissance ») : prénom, nom, surnom de 12 caractères au plus, photo facultative.
Pourquoi le nom : Party sert à des soirées réelles, souvent chez quelqu'un ; le nom complet permet aux admins de savoir à
qui est un compte (validation des nouveaux comptes, signalements). Prénom et nom ne sont visibles que par la personne et
les admins (« 🔒 Ton prénom et ton nom ne sont visibles que par toi et les admins »), sauf si elle allume **Afficher mon
nom et prénom** (Réglages › Mon profil, éteint par défaut).

## 3. Événements

### 3.1 La liste
Pastilles **À venir · Sondages · Brouillons · Passés · Filtres** ; en haut à droite **+ Proposer** (« + » seul sur les
petits iPhone ; il passe en bas à droite dès qu'on fait défiler), loupe et cloche (Activité) ; en bas à droite
**✨ Avec l'IA**. 📸 (liste avec des événements de démo, sans données réelles)

### 3.2 La fiche
De haut en bas : titre, date, lieu (« Itinéraire › »), « À propos », **Ajouter à mon agenda**, la réponse, les sondages de
l'événement (juste sous la réponse), le billet, la carte **Invités**, le covoiturage, les infos, les participants,
« Qui amène quoi », la discussion, **Signaler cet événement**, puis la **ZONE ORGANISATEUR** (organisateurs).
En-tête : **🔔 Sourdine** et **Modifier** (organisateurs ; « ✨ IA » n'est pas sur la fiche dans l'app App Store). La fiche se met à jour en direct ; un nom ouvre la
fiche de la personne. 📸

### 3.3 Créer avec le formulaire
**+ Proposer** › **Simple** / **Avancé** › Titre, Description, Quand, Où. Le formulaire s'ouvre en « Publique + lien » :
pour publier aussitôt, dans **Qui** › « Qui est invité ? », toucher **Sur invitation**, cocher **Démo Apple · 2**, puis
**Publier**. Public, ou sur invitation sans groupe : **Envoyer pour validation** (Guest+ ; un organisateur voit
**Publier**). Sinon **Enregistrer en brouillon**. Premier contenu : feuille des **CGU** à accepter.
La proposition attend dans **Brouillons** (« En attente de validation »).

### 3.4 Créer avec l'IA
**✨ Avec l'IA** › écran natif « Créer avec l'IA » (1 La soirée · 2 Qui est invité · 3 C'est en ligne) ›
**Décris ton événement** (texte, micro, photo d'une affiche) › **Envoyer** › première fois : feuille d'accord IA
(**J'accepte** / **Pas maintenant**) › « L'IA prépare ton événement… » › éventuelles questions « Il me manque quelques
infos » › lieu à confirmer sur la carte › **C'est juste ?** › **Oui, continuer** › page web « Qui est invité » : un
toucher sur **🌍 Public + lien public**, **👥 Des groupes** (cocher puis « Publier pour … ») ou **✉️ Sur invitation
seulement** publie (ou « Envoyer pour validation »). L'IA ne choisit jamais qui est invité ni qui voit l'événement,
n'allume jamais billets, covoiturage ou annonce au groupe, et ne choisit jamais le mode de paiement. L'IA reçoit
ton surnom, les noms de tes groupes, catégories et étiquettes, les personnes déjà choisies sous un alias (P1, P2…),
jamais la liste des membres. 📸 (étape 1)

### 3.5 Inviter
Carte **Invités** › **+ Inviter** › **Une personne** ou **Plusieurs** (sans limite par défaut, − / + pour les places),
nom du lien facultatif › **Partager le lien…**. Chaque invité voit les **chiffres** seulement et gère ses propres liens.
Événement non public : la personne venue par le lien d'un invité attend : la carte **Invités** affiche « … attend ton accord » (**Accepter** / **Refuser**). Groupes : Réglages ›
Groupes › un groupe › **Inviter** › **Le lien du groupe** (WhatsApp, Copier, Autre, code QR). Amis : Réglages › **Mes amis dans Party** (facultatif, Contacts
demandé après une explication) : contacts déjà sur Party (empreinte des numéros faite sur l'iPhone, aucun nom ne sort),
et contacts pas encore sur Party, chacun avec son bouton qui ouvre Messages d'Apple avec mon lien personnel : je relis et
j'envoie moi-même, un contact à la fois. Aucun « tout sélectionner » ; Party n'envoie rien. 📸 (feuille Inviter)
**↻ Relancer** (organisation, carte Invités repliée) : une notification par jour au plus aux invités sans réponse ;
sans app ni notification, un lien que l'organisateur partage lui-même. Événement complet avec liste d'attente :
« Complet · liste d'attente ouverte », la place libérée va au suivant, prévenu. Lien d'un groupe ouvert sans compte :
nom, emoji, couleur du groupe et surnom de qui invite, jamais les membres. Une personne bloquée ne peut être ni notée
présente ni ajoutée en co-organisatrice ; co-organisateurs proposés seulement parmi les personnes liées.

### 3.6 Répondre
**Présent** · **Peut-être** · **Absent** (le libellé à l'écran est « Absent »). L'heure de chaque réponse s'affiche.

### 3.7 Sondage de dates
**Sondages** › l'événement › **Oui / Si besoin / Non** sur chaque date › **Valider mes dates**. L'organisateur :
**Fixer cette date**. 📸

### 3.8 Agenda
**Ajouter à mon agenda** : abonnement au calendrier personnel « Vendredi Party » (iOS propose de s'abonner), qui suit
ensuite tout changement. Sondage : l'app peut aussi mettre les dates dans le calendrier de l'iPhone (autorisation
demandée à ce moment-là).

### 3.9 Covoiturage
Carte **Covoiturage** (option de l'organisateur) : **🚗 Je conduis** / **🙋 Je cherche une place**, ville de départ
facultative, **Monter** / **Prendre**. Aucun argent.

### 3.10 Billet QR et Cartes Apple
Option « Billets QR » (allumée sur la Soirée démo, AUCUN billet remis d'avance : répondre **Présent**, puis carte
**Billets QR** de la fiche, côté organisateur › **Remettre à tous les présents** ; Apple-test est co-organisateur) :
carte **Ton billet** › **Afficher ›** › QR + badge **Ajouter à l'app Cartes Apple** (feuille PassKit native).
L'organisateur : **Remettre le billet** (une personne) ou **Remettre à tous les présents**, ou billet remis tout seul
quand il confirme un paiement ;
**📷 Scanner les billets** dans la ZONE ORGANISATEUR. 📸 (billet + badge Cartes)

### 3.11 Paiement d'un événement (hors de l'app)
Prix par personne d'un événement réel ; mode choisi par l'organisateur (jamais par l'IA) : **On me paie** (son lien
Revolut, Twint ou IBAN), **Paiement en ligne** (lien https d'une billetterie), **Sur place** (rien dans l'app).
Côté invité, après **Présent** : **Payer [organisateur] · 10 CHF** › le lien s'ouvre hors de l'app › **J'ai payé** (simple
note). Côté organisateur : **Reçu ✓** / **Pas reçu**. « Paiement ouvert » éteint : « ⏳ paiement bientôt possible ».
Règle Apple : **3.1.3(e)** (biens et services réels consommés hors de l'app ; pas d'achat intégré). NB : la règle 3.1.5
citée dans la demande concerne aujourd'hui les cryptomonnaies ; ne pas la citer à Apple.

### 3.12 Bar de la soirée
**Caché dans l'app App Store** (refus 1.4.3, 25.11) : ni menu, ni commande, ni notification du bar. Le site le garde.

### 3.13 Discussion d'un événement
Option « Forum de l'événement » : section **Discussion** › **Ouvrir ›** ; mêmes règles que les Discussions. Réservée
à l'organisation et aux **Présent** / **Peut-être** ; sondage de dates : ouverte une fois la date fixée.
**@toutlemonde** et les annonces (📣, épinglées) : organisation seulement.

## 4. Discussions
Onglet **Discussions** › « Démo Apple » : texte, photos, vocaux, réponses, réactions. Premier message dans un groupe : CGU ; message direct : CGU dès « Écrire à … ».
**Appui long** sur un message › **Répondre · Copier · Signaler** (case « Joindre les 10 messages précédents » ; la photo
ou le vocal signalé est copié pour les modérateurs). Message direct seulement avec un vrai lien (groupe en commun hors
Membres Vendredi Party, événement non public en commun, organisateur d'un événement auquel on a répondu) ; sinon une
**demande de message** : un seul texte, sans photo, vocal, lien ni numéro. **Demandes** (en haut de la liste) : mini-profil
+ message, **Accepter · Supprimer · Bloquer · Signaler** ; l'expéditeur n'est jamais prévenu d'un refus. Réglages ›
Confidentialité › **Demandes de message** (Tout membre / Personne) et **Confirmations de lecture**. **Nouveau message**
(bouton rose) : suggestions de vrais liens seulement, recherche par nom (jamais par numéro) ; 2 personnes ou plus = groupe
privé, jamais lu par l'administration. Toucher un nom ou une photo : mini-profil (« Envoyer un message », « Déjà vu N
fois », Bloquer · Signaler). Bloquer : les messages de la personne bloquée disparaissent aussitôt, les modérateurs sont prévenus ; débloquer : Réglages ›
Confidentialité › **Personnes bloquées**. **Ma note privée** (mini-profil ou fiche d'un membre) : 500 caractères, vue
par moi seul, jamais par la personne ni par l'administration. Après « Signaler » : contact pour l'urgent, traité sous 24 h. 📸

## 5. Groupes
Réglages › **Groupes** : mes groupes, **Nouveau groupe**, membres, **Inviter** › **Le lien du groupe** (WhatsApp, Copier, Autre, code QR), « Montrer mon numéro dans ce
groupe » (caché par défaut). Page d'un groupe : **Signaler le groupe** (son nom) et
**Signaler la photo du groupe**. Réglages du groupe (23.11) : l'admin du groupe donne des rôles (co-admin,
organisateur) et choisit qui peut inviter, créer des événements, écrire ou épingler ; accord facultatif de chaque
nouveau membre.

## 6. Jeux
Onglet **Jeux** › **Salle de jeux** › **Créer une salle** (ou **Code** › **Rejoindre** : 4 chiffres = un jeu) ; dans la
salle, on vote, l'animateur lance (**Quiz** se joue seul) ; **🎮 Changer de jeu** ramène à la salle. **🧠 Jeux solo** ›
**Méninges** › **Faire chauffer**. **?** = règles. Dans l'app App Store (refus 1.4.3, décision du 25.11), **retirés pour la
1.0.0** : Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Beer pong, Biskit, Purify Test, Casino, Blackjack, toute
option de gorgées (aucun « mode points » à la place), modes Hot / Mix, thème WTF de Pour ou contre, paquet « Entre amis »
de Qui est le plus… ; ni mise, ni argent, ni lot. Chaque joueur coche d'abord « J'ai 18 ans ou plus et j'accepte les
conditions d'utilisation » (lien vers les conditions) : sans elle, le serveur refuse tout texte montré à la table ;
prénoms (même changés en cours de partie) et réponses écrites passent le filtre ; « Signaler » sur les réponses écrites.
**Plus tard · jouer seul à Méninges** : le joueur ne voit que Méninges (rien de ce qu'il écrit n'est montré à personne) ;
**👥 Jouer avec les autres** rouvre « Comment tu t'appelles ? ». Pour ou contre, dans l'app App Store : seulement les
dilemmes de Party, aucun dilemme écrit ou proposé par un joueur.
Sans compte : parties illimitées dans l'app. 📸 (salle ou Quiz, **sans**
catégorie « 🍻 Alcool »)

## 7. Musique
**Pas d'onglet Musique par défaut dans l'app App Store** (27.11). Pendant une soirée chez l'hôte : Jeux › **Code** › le code
de la soirée à **6 chiffres** (ou le QR de l'hôte) : l'onglet **Musique** apparaît dans la barre et l'écran natif Musique
s'ouvre › « Titre, artiste ou lien » › ajouter. L'onglet part (retour sur Jeux) dès qu'on n'est plus dans la soirée :
« Quitter la soirée » en bas de l'écran Musique, soirée arrêtée ou code changé par l'hôte, invité retiré, app relancée
après la soirée. Il faut une soirée en cours (enceintes et compte de musique de l'hôte) : aucune vidéo n'est jointe (26.11) ; les notes proposent à Apple de lancer une soirée sur demande (code donné seulement dans la réponse App Review). Activité en direct : elle EST dans le build App Store
(PartyWidgets, `TrackLiveActivity`) ; contrôle Apple, tour 2 : on la DÉCRIT comme facultative (« optional Live Activity
for your song; it ends by itself ») plutôt que de la taire : décompte « Ton titre arrive » tant qu'un de mes titres est
dans la file, qui se termine seul une fois le titre passé, à couper dans Réglages de l'iPhone › Party. « Me prévenir
quand mon titre passe » est une notification (interrupteur sur l'écran Musique). La Musique reste décrite (sans démo)
pour ne rien cacher (2.3.1).

## 8. Réglages
- **Notifications** : un interrupteur par type (Général, Jeux (hôte de la soirée seulement), Ton avis, Événements, Discussions des groupes,
  Amis, Comptes et modération, Quand j'organise ; Musique seulement chez l'hôte d'une soirée Musique, l'invité a ses interrupteurs sur l'écran Musique) ; la lune en haut à droite met tout en pause.
- **Pot commun** : dépenses partagées (rien n'est payé dans l'app), scan de ticket (IA facultative, avec accord). On y
  entre par son lien, ou d'office en répondant **Présent** (ou noté Présent par l'organisateur) à un événement dont l'organisateur a choisi le
  pot (on le quitte
  à tout moment : Réglages › Pot commun › **Quitter ce pot commun**) ; les membres voient le nom de chacun ; les moyens de paiement de qui a créé le pot ou l'a rejoint par son lien sont montrés ; ajouté d'office (événement ou
  autre membre), ils restent cachés tant qu'il ne choisit pas **Montrer mes moyens de paiement dans ce pot**. Aucun pot
  préparé : Réglages › Pot commun › **Nouveau pot commun** ; « Rembourser » apparaît sur un virement que tu dois : dans le pot, ⋯ (en haut à droite) › **Membres** › « Ajouter quelqu'un » › un prénom › **Ajouter**, puis **Ajouter une dépense** « Payé par » ce membre. Un membre ajouté à la main n'a aucun moyen de paiement : la feuille « Rembourser » dit qu'il n'a pas encore rempli son profil de paiement ; IBAN et liens Revolut / Twint n'apparaissent que pour un membre entré avec son propre compte (lien du pot) qui a rempli « Mon profil de paiement ». Ajouter une dépense ou
  une photo de ticket demande les CGU ; chaque dépense et photo de ticket a **Signaler**.
- **Mes amis dans Party**, **Mes stats de jeu**, **Ton avis** (selon le rôle ; écrit à l'équipe de Party, l'éditeur).
- **Confidentialité** : Noms de mes contacts, **Personnes bloquées**, **Conditions d'utilisation** (contact
  support@vendrediparty.ch), accord **IA de Party** (retirer / redonner), politique complète.
- **Gérer mon compte** › écrire **SUPPRIMER** › **Supprimer définitivement mon compte** ; **Se déconnecter** dessous.
📸 (Réglages)

## 9. Ce qui vient du serveur (à assumer devant Apple)
Événements et Jeux = le site `party.bobycharbon.ch` dans une WKWebView ; l'app App Store y reçoit toujours sa version à elle
(sans jeux à boire, bar ni Casino / Blackjack ; onglet Musique seulement pendant une soirée rejointe), pour tous ses utilisateurs ; Pronos, Agenda, Zicou et
Souvenirs ne s'ouvrent jamais dans ce build (« Not in this version » ; 2.5.19 : Pronos, Agenda et Souvenirs ne sont pas compilés ; ce qui reste dans le binaire sans jamais s'ouvrir est listé en B5 des notes : Zicou, le panneau des cartes de la Pyramide, les interrupteurs de notification du bar, de l'Agenda et des Pronos, la Musique des invités (extension Partager, raccourci « Ajouter un titre », interrupteurs Musique), l'onglet Purify Test des stats, le bouton « Ouvrir l'admin du site (secours) » de l'hôte ; quoi que dise le serveur) ; natif : barre d'onglets,
écran Musique (onglet affiché après Jeux › Code, le temps de la soirée), Réglages, Discussions, Groupes, Ton avis, assistant IA, Pot commun, écran hors ligne, bandeau d'annonce, QR,
Cartes, Calendrier, Contacts, extension Partager (« Party ! » dans le menu Partager), notifications. La page n'appelle que les fonctions
natives prévues (`window.PartyNative`) ; tout autre site s'ouvre dans Safari. Toute grosse fonction livrée par le site
doit figurer dans les notes AVANT son ouverture en prod (règle CLAUDE.md, Apple 2.3.1(a)).
