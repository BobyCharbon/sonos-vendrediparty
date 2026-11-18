# Tutoriel de la revue Apple — version française (pour l'admin)

Même parcours que la partie B de `notes-for-review.md` (en anglais, jointe en PDF pour Apple). À relire avant l'envoi ;
chaque **📸** marque une capture utile (pour les captures App Store ou pour vérifier l'écran avant la revue).
Vérifié dans le code le 16.11.2026 (develop) et sur la prod en lecture seule (`/api/features` : discussions, invites_v2
et bar allumés, Zicou éteint). Ce qui ne l'est pas porte la marque **À VÉRIFIER**.

## 0. Avant la revue

- Compte de démo : **+41 79 000 09 99**, surnom « Apple-test » (Apple Review), rôle **Guest+ (« User+ »)**, profil complet
  avec photo, code fixe (Supabase prod › Auth › Test OTP, valable jusqu'au 31.12.2027). Le code ne s'écrit que dans App
  Store Connect (champ Password), jamais dans le dépôt.
- Données à préparer : voir l'encadré « À FAIRE AVANT ENVOI » de `notes-for-review.md` (événement « Soirée démo » où Apple-test
  est invité, bar ouvert avec des articles sans alcool, groupe « Démo Apple » avec des messages, un message privé, et si
  possible « Démo Apple · Sondage »).
- Second compte de démo **« Apple-test 2 »** (Discussions v2, 18.11) : autre numéro à code fixe, sans groupe ni événement
  privé en commun avec Apple-test, qui lui a envoyé une **demande de message** en attente (point 4 bis de l'encadré).
- Guest+ n'a pas « Publier sans validation » ni « Voir les événements » (il voit les événements publics et ceux où il est
  invité) : ses nouveaux événements attendent une validation. Valider vite pendant la revue.
- Corrections annoncées par le coordinateur (décrites ci-dessous comme en place) — **À VÉRIFIER en prod avant l'envoi** :
  « Bloquer » masque aussitôt les messages et prévient les modérateurs ; bar payant seulement sur un événement non public
  (bar offert partout) ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
  section bar / paiements ; politique de confidentialité avec une section bar.

## 1. Plan de l'app

L'app s'ouvre sur **Événements** (sauf au milieu d'une partie de jeu). Barre d'onglets native :

| Déconnecté | Connecté | Fait en |
|---|---|---|
| Musique | Musique | natif (SwiftUI) |
| Jeux | Jeux | page web du site |
| Événements | Événements | page web du site (module Événements) |
| — | Discussions | natif |
| Se connecter | Réglages | natif |

## 2. Se connecter

1. Onglet **Se connecter** › ligne **Se connecter**.
2. Garder **Suisse +41**, taper `079 000 09 99` › **Recevoir un code par SMS**.
3. Taper le code fixe : la connexion part toute seule au 6e chiffre. 📸 (écran du numéro, sans le code)
4. Le dernier onglet devient **Réglages** (profil en tête) ; l'onglet **Discussions** apparaît.

Un nouveau compte passe ensuite par « Faisons connaissance » (prénom, nom, surnom de 12 caractères au plus, photo facultative).

## 3. Événements

### 3.1 La liste
Pastilles **À venir · Sondages · Brouillons · Passés · Filtres** ; loupe et cloche (Activité) en haut à droite ;
en bas à droite **✨ Avec l'IA** et **+ Proposer**. 📸 (liste avec des événements de démo, sans données réelles)

### 3.2 La fiche
De haut en bas : titre, date, lieu (« Itinéraire › »), « À propos », **Ajouter à mon agenda**, la réponse, le billet,
la carte **Invités**, le covoiturage, le **🍹 Bar de la soirée**, les infos, les participants, les mini-sondages,
« Qui amène quoi », la discussion, **Signaler cet événement**, puis la **ZONE ORGANISATEUR** (organisateurs).
En-tête : **🔔 Sourdine**, **✨ IA** et **Modifier** (organisateurs). La fiche se met à jour en direct ; un nom ouvre la
fiche de la personne. 📸

### 3.3 Créer avec le formulaire
**+ Proposer** › **Simple** / **Avancé** › Titre, Description, Quand, Où › **Envoyer pour validation** (Guest+ ; un
organisateur voit **Publier**) ou **Enregistrer en brouillon**. Premier contenu : feuille des **CGU** à accepter.
La proposition attend dans **Brouillons** (« En attente de validation »).

### 3.4 Créer avec l'IA
**✨ Avec l'IA** › écran natif « Créer avec l'IA » (1 La soirée · 2 Qui est invité · 3 C'est en ligne) ›
**Décris ton événement** (texte, micro, photo d'une affiche) › **Envoyer** › première fois : feuille d'accord IA
(**J'accepte** / **Pas maintenant**) › « L'IA prépare ton événement… » › éventuelles questions « Il me manque quelques
infos » › lieu à confirmer sur la carte › **C'est juste ?** › **Oui, continuer** › page web « Qui est invité » : un
toucher sur **🌍 Public + lien public**, **👥 Des groupes** (cocher puis « Publier pour … ») ou **✉️ Sur invitation
seulement** publie (ou « Envoyer pour validation »). L'IA ne choisit jamais qui est invité ni qui voit l'événement,
n'allume jamais billets, covoiturage ou annonce au groupe, et ne choisit jamais le mode de paiement. 📸 (étape 1)

### 3.5 Inviter
Carte **Invités** › **+ Inviter** › **Une personne** ou **Plusieurs** (sans limite par défaut, − / + pour les places),
nom du lien facultatif › **Partager le lien…**. Chaque invité voit les **chiffres** seulement et gère ses propres liens.
Événement non public : la personne venue par le lien d'un invité attend dans **À accepter**. Groupes : Réglages ›
Groupes › un groupe › **Inviter avec un lien**. 📸 (feuille Inviter)

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
Option « Billets QR » : carte **Ton billet** › **Afficher ›** › QR + badge **Ajouter à Cartes Apple** (feuille PassKit
native). L'organisateur : **Remettre le billet**, ou billet remis tout seul quand il confirme un paiement ;
**📷 Scanner les billets** dans la ZONE ORGANISATEUR. 📸 (billet + badge Cartes)

### 3.11 Paiement d'un événement (hors de l'app)
Prix par personne d'un événement réel ; mode choisi par l'organisateur (jamais par l'IA) : **On me paie** (son lien
Revolut, Twint ou IBAN), **Paiement en ligne** (lien https d'une billetterie), **Sur place** (rien dans l'app).
Côté invité, après **Présent** : **Payer [organisateur] · 10 CHF** › le lien s'ouvre hors de l'app › **J'ai payé** (simple
note). Côté organisateur : **Reçu ✓** / **Pas reçu**. « Paiement ouvert » éteint : « ⏳ paiement bientôt possible ».
Règle Apple : **3.1.3(e)** (biens et services réels consommés hors de l'app ; pas d'achat intégré). NB : la règle 3.1.5
citée dans la demande concerne aujourd'hui les cryptomonnaies ; ne pas la citer à Apple.

### 3.12 Bar de la soirée
Option de l'organisateur, éteinte par défaut ; bar payant seulement sur un événement non public, bar offert partout ;
tabac / drogues refusés.
- Invité « Présent » (Apple-test sur « Soirée démo ») : **🍹 Bar de la soirée** › **Ouvrir le bar ›** (carte, badges 16+ / 18+, QR, solde) ›
  **J'accepte l'engagement** › − / + › **Valider la commande** (ou montrer son QR au comptoir) › rembourser hors de
  l'app › **J'ai remboursé**. 📸 seulement avec des boissons sans alcool
- Organisateur / barman : ZONE ORGANISATEUR › **🍹 Gérer le bar** (Articles · Options · Rembourser · Barmans · Direct,
  **📄 Récapitulatif de la soirée**) et **🍹 Scanner au bar** (il faut un 2e téléphone pour scanner un QR).
- L'âge est vérifié en personne par le barman (aucune date de naissance dans l'app).

### 3.13 Discussion d'un événement
Option « Forum de l'événement » : section **Discussion** › **Ouvrir ›** ; mêmes règles que les Discussions.

## 4. Discussions
Onglet **Discussions** › « Démo Apple » : texte, photos, vocaux, réponses, réactions. Premier message : CGU.
**Appui long** sur un message › **Répondre · Copier · Signaler** (case « Joindre les 10 messages précédents » ; la photo
ou le vocal signalé est copié pour les modérateurs). Message direct seulement avec un vrai lien (groupe en commun hors
Membres Vendredi Party, événement non public en commun, organisateur d'un événement auquel on a répondu) ; sinon une
**demande de message** : un seul texte, sans photo, vocal, lien ni numéro. **Demandes** (en haut de la liste) : mini-profil
+ message, **Accepter · Supprimer · Bloquer · Signaler** ; l'expéditeur n'est jamais prévenu d'un refus. Réglages ›
Confidentialité › **Demandes de message** (Tout membre / Personne) et **Confirmations de lecture**. **Nouveau message**
(bouton rose) : suggestions de vrais liens seulement, recherche par nom (jamais par numéro) ; 2 personnes ou plus = groupe
privé, jamais lu par l'administration. Toucher un nom ou une photo : mini-profil (« Envoyer un message », « Déjà vu N
fois », Bloquer · Signaler). Bloquer masque aussitôt ses messages et prévient les modérateurs ; débloquer : Réglages ›
Confidentialité › **Personnes bloquées**. 📸

## 5. Groupes
Réglages › **Groupes** : mes groupes, **Nouveau groupe**, membres, **Inviter avec un lien**, « Montrer mon numéro dans ce
groupe » (caché par défaut).

## 6. Jeux
Onglet **Jeux** › **Salle de jeux** › **Créer une salle** (ou code à 4 chiffres sous « ou rejoindre ») ; dans la salle, on
vote, l'animateur lance (**Quiz** se joue seul) ; **🎮 Changer de jeu** ramène à la salle. **🧠 Jeux solo** › **Méninges** ›
**Faire chauffer**. **?** = règles. Pyramide : cartes 30 s dans un panneau natif noir en capture. Mode gorgées
facultatif (eau, 0 gorgée = sans alcool, aucun classement par boissons) ; ni mise, ni argent, ni lot ; Casino et
Blackjack absents de l'app App Store. Sans compte : quelques parties (3 par défaut, réglable par l'admin). 📸 (salle ou
Quiz, **sans** la catégorie « 🍻 Alcool » à l'écran)

## 7. Musique
Onglet **Musique** › **Scanner le QR de l'hôte** ou **Code** › **Entrer** › « Titre, artiste ou lien » › ajouter ;
« Me prévenir quand mon titre passe » (Live Activity). Il faut une soirée en cours chez l'hôte (ses enceintes, son compte
de musique). 📸 (pendant une vraie soirée, file avec des titres)

## 8. Réglages
- **Notifications** : un interrupteur par type (Général, Musique, Jeux, Ton avis, Événements, Discussions des groupes,
  Amis, Comptes et modération, Quand j'organise) ; la lune en haut à droite met tout en pause.
- **Pot commun** : dépenses partagées (rien n'est payé dans l'app), scan de ticket (IA facultative, avec accord).
- **Mes amis dans Party**, **Mes stats de jeu**, **Ton avis**.
- **Confidentialité** : Noms de mes contacts, **Personnes bloquées**, **Conditions d'utilisation** (contact
  support@vendrediparty.ch), accord **IA de Party** (retirer / redonner), politique complète.
- **Gérer mon compte** › écrire **SUPPRIMER** › **Supprimer définitivement mon compte** ; **Se déconnecter** dessous.
📸 (Réglages)

## 9. Ce qui vient du serveur (à assumer devant Apple)
Événements et Jeux = le site `party.bobycharbon.ch` dans une WKWebView, même code pour tous ; natif : barre d'onglets,
Musique, Réglages, Discussions, Groupes, Ton avis, assistant IA, Pot commun, écran hors ligne, bandeau d'annonce, QR,
Cartes, Calendrier, Contacts, Live Activity, extension Partager, notifications. La page n'appelle que les fonctions
natives prévues (`window.PartyNative`) ; tout autre site s'ouvre dans Safari. Toute grosse fonction livrée par le site
doit figurer dans les notes AVANT son ouverture en prod (règle CLAUDE.md, Apple 2.3.1(a)).
