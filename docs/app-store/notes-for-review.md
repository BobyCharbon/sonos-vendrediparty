# Party entre amis — Notes for App Review (iOS 1.0.0)

> ## ⚠️ À FAIRE AVANT ENVOI (pour l'admin — à retirer avant d'exporter ce fichier en PDF)
>
> Vérifié le 16.11.2026 en lecture seule : en prod, le numéro de démo à code fixe **+41 79 000 09 99** existe
> (Supabase › Auth › « Test OTP », valable jusqu'au 31.12.2027) ; son compte **« Apple-test »** (Apple Review) est actif,
> rôle **Guest+ (« User+ »)**, profil complet avec photo, **CGU pas encore acceptées** (la feuille des CGU s'affichera au
> premier contenu : c'est bien, Apple la verra). Le code fixe n'est écrit nulle part dans le dépôt ; le fichier
> `~/sb-work/apple/demo.txt` cité par `ios/appstore/app-store-connect.md` **n'existe pas sur ce Mac** (peut-être sur un autre ordinateur) : sinon retrouver le code
> dans Supabase (prod › Authentication › Providers › Phone › Test OTP) et le saisir seulement dans App Store Connect.
>
> Données à préparer en PRODUCTION (le coordinateur s'en charge ; les notes y renvoient sous CES noms exacts) :
> 1. Événement **« Soirée démo »** (organisé par un admin), **sur invitation** (un bar payant n'existe que sur un événement
>    non public), date fixée dans 2 à 3 semaines, lieu fictif, Apple-test **invité** (et de préférence déjà noté **Présent**,
>    billet remis). Conseillé pour que tout s'essaie côté invité : prix 10 CHF « On me paie » + « Paiement ouvert »,
>    « Billets QR », « Covoiturage », « Forum de l'événement ».
> 2. Le **bar** de cet événement : **ouvert**, « Les invités commandent dans l'app » allumé, articles dont des **sans alcool**
>    au nom neutre (ex. « 🥤 Sirop », « 🧃 Jus de pomme ») ; un article « 18+ » au plus, pour montrer le badge d'âge.
>    Facultatif : Apple-test **barman** (onglet « Barmans ») pour qu'il voie « 🍹 Scanner au bar ».
> 3. Groupe **« Démo Apple »** : Apple-test + un admin, **quelques messages** (un vocal et une photo neutre si possible).
> 4. Un **message privé** d'un admin à Apple-test (ils partagent le groupe, donc « Écrire » marche).
> 5. Recommandé : **« Démo Apple · Sondage »** (organisé par un admin, Apple-test invité, « Date à définir », 3 créneaux).
> 6. Pendant toute la revue : valider vite toute proposition d'Apple-test (bandeau « … attend ta validation »), garder l'IA
>    sous son plafond mensuel, ne PAS fermer le bar « Soirée démo », AUCUNE mise en prod ni maintenance (24-48 h).
> 7. Corrections annoncées par le coordinateur et décrites ici **comme déjà en place** (à contrôler en prod avant l'envoi) :
>    « Bloquer » masque aussitôt les messages et prévient les modérateurs ; bar payant réservé aux événements non publics,
>    bar offert partout ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
>    section bar / paiements ; politique de confidentialité avec une section bar. Si l'une manque en prod : corriger ce
>    texte avant l'envoi (Apple compare les notes et l'app).
> 8. Copier la **partie A** dans App Store Connect › App Review Information › **Notes** (3 807 caractères, limite 4 000) ET
>    dans `ios/appstore/review-notes.txt` (pas modifié par ce travail) (c'est ce fichier que `tools/appstore_submit.py` envoie ; la partie A garde tous
>    les mots exigés par `tests/test_ios_app.py::test_review_notes_describe_every_big_feature_delivered_by_the_web`).
> 9. Exporter la **partie B** en PDF (sans cet encadré) et la joindre dans App Review Information › **Attachment**.

---

## PART A — Text for the "Notes" field (3,807 characters, limit 4,000)

```text
ABOUT
"Party entre amis" (icon "Party"): free app by friends in Switzerland (our association "Vendredi Party" lives inside): real-world events, party games, party music, group chats. French, 18+. No ads, no tracking, no in-app purchase. Full step-by-step guide attached (PDF).

SIGN-IN
Phone + 6-digit SMS code, no password. Demo account "Apple-test": number and code: see the App Review Information sign-in fields (fixed code, no SMS). Last tab "Se connecter" > "Se connecter" > "Suisse +41" > number > code. Please keep the account.

TRY IT
1. Events > "Soirée démo Vendredi Party" (invited, co-organiser): answer "Présent", order at the bar (Wallet card); "Gérer le bar".
2. Events > "Avec l'IA" or "+ Proposer" (new events of the demo account wait for our approval).
3. Discussions > "Démo Apple": long-press a message > "Signaler".
4. Games > "Créer une salle" > Quiz (works alone), or Méninges > "Faire chauffer".

NATIVE (4.2)
Native tab bar; SwiftUI: Music, Settings, Discussions, Groups, "Ton avis", event AI assistant, "Pot commun", banners, offline screen. Push (one switch per type), Live Activity, Apple Wallet (tickets, bar card), QR scanner, VisionKit, Calendar, optional Contacts (hashed), dictation, share extension, universal links. Pyramide: cards in a native panel hidden from screenshots.

WEB CONTENT (2.5.2)
Events and Games tabs are our own site (party.bobycharbon.ch) in a WKWebView, same HTML/JS for all users, calling only the native features above. Other sites open in Safari. Everything described here is on in production.

EVENTS
"+ Proposer" or "Avec l'IA", then "Qui est invité": public, invitation or groups. Links for one person or "Plusieurs"; guests create, copy and stop own links, see counts only. Not public: someone coming through a guest's link waits ("À accepter"). Date poll (Oui / Si besoin / Non). "Ajouter à mon agenda": personal calendar feed. Carpool (no money). QR ticket + Wallet. Groups: "Inviter avec un lien". Everyone signs in (first/last name, nickname of 12 characters max). The page updates live; tap a name to open the profile; each answer shows its time. Admins: "Nouveau compte" alert, announcement or maintenance message.

PAYMENTS (3.1.3(e))
Party never sells, holds or transfers money; no digital goods. Real-world events only: "On me paie" (organiser's Revolut/Twint/IBAN), "Paiement en ligne" (ticketing link, opens in Safari) or "Sur place". "J'ai payé" is a note; the organiser confirms "Reçu ✓" (then the QR ticket). "Pot commun" only records who owes what.

PARTY BAR
Organiser's option, off by default; a paid bar only on private events (a free bar anywhere). Physical drinks; items 16+/18+, the barman checks age in person; tobacco/drugs refused; no ranking or prompt to drink. Barman scans the guest's QR; balance in a Wallet card. Party only records who owes what, repaid to the organiser outside the app.

DISCUSSIONS (1.2)
Group chats and DMs between people sharing a group or event; verified phone. Terms before the first message, word filter, "Signaler" on messages, profiles, photos, events, polls. "Bloquer" hides that person's messages at once and notifies moderators (Settings > Confidentialité > "Personnes bloquées"). Reports handled within 24 h. Contact: support@vendrediparty.ch.

AI (5.1.2(i))
"Avec l'IA", "Ton avis" and receipt reading send data to Anthropic (Claude) only after "J'accepte"; all works without AI; phone never sent. Withdraw: Settings > Confidentialité > "IA de Party".

GAMES (18+)
Drinking modes are optional: water always counts, 0 sips = alcohol-free, never ranked by drinks. No gambling, bets, purchases or prizes; no Casino/Blackjack in this app.

MUSIC
Needs a live party (host's QR or 4-digit code); songs play on the host's speakers.

DELETION
Settings > "Gérer mon compte" > type SUPPRIMER > "Supprimer définitivement mon compte".
```

---

## PART B — Full guide for the App Review team (attach as PDF)

### B1. What Party is

Party ("Party entre amis" on the App Store, "Party" under the icon) is a free, non-commercial app made by a group of
friends in Switzerland. Our association, **Vendredi Party**, uses it to organise its evenings, and anyone can use it to
organise their own real-world events with friends.

What you can do with it:

- **Events** — create an event (form or AI assistant), invite people with a link or a group, answer
  (Présent / Peut-être / Absent), vote on dates, share rides, get a QR ticket in Apple Wallet, pay the organiser
  **outside** the app for a real-world event, and use the **party bar** the organiser sets up.
- **Discussions** — group chats and direct messages between people who know each other.
- **Games** — party games played together on everyone's phone in a "game room", plus solo brain games.
- **Music** — at a party, guests add songs to the host's queue (the host's own speakers and music account).
- **Settings** — profile, notifications (one switch per type), groups, shared expenses ("Pot commun"), privacy, terms,
  account deletion.

The app is in **French only**, rated **18+**, distributed in French-speaking countries. **No ads, no tracking, no
third-party analytics SDK, no in-app purchase, nothing is sold.**

Button labels below are given in French exactly as on screen, with an English explanation.

### B2. Demo account and prepared data

Sign-in is by phone number + a 6-digit code received by SMS (no password). The demo number in "Sign-in information"
has a **fixed code** (also in "Sign-in information", Password field): no SMS is sent.

| Item | What it is |
|---|---|
| Demo account | Nickname "Apple-test" (Apple Review), complete profile. Ordinary member role (its new events wait for an admin's approval, see B4.3). |
| Event **"Soirée démo"** | Organised by us, invitation only, the demo account is invited: answer, ticket and Wallet, payment, carpool, event discussion, and an **open party bar** (order a drink). |
| Event **"Démo Apple · Sondage"** | Organised by us, the demo account is invited: a date poll to vote on. |
| Group **"Démo Apple"** | The demo account + one of our admins, with a few messages. |
| Direct message | One message from our admin to the demo account. |

If you test account deletion: please do it last. Signing in again with the same number then creates a new, empty
account (the prepared data stays linked to the deleted one).

### B3. Map of the app

When the app opens, it shows the **Événements** (Events) tab. The bottom bar is a native `UITabBar`:

| Tab (signed out) | Tab (signed in) | Built with |
|---|---|---|
| Musique (Music) | Musique | Native SwiftUI |
| Jeux (Games) | Jeux | Web content (our site) |
| Événements (Events) | Événements | Web content (our site) |
| — | Discussions | Native SwiftUI |
| Se connecter (Sign in) | Réglages (Settings) | Native SwiftUI |

Native screens opened from the web tabs: "Créer avec l'IA" (AI event assistant), Apple QR scanner, "Add to Apple Wallet"
sheet, Calendar, Contacts card, share sheet, Pyramide secret cards panel.

### B4. Step-by-step tutorials

#### B4.1 Sign in

1. Tap the last tab, **Se connecter**.
2. Tap the row **Se connecter** ("With your number: events, games with an account, your stats").
3. Keep **Suisse +41** selected, type the demo number (with or without the leading 0).
4. Tap **Recevoir un code par SMS** (Get a code by SMS).
5. Type the fixed 6-digit code: the app signs in automatically at the 6th digit (or tap **Se connecter**).
6. The last tab is now **Réglages** (Settings) with the profile at the top, and the **Discussions** tab appears.

A new account (not the demo one) then fills in "Faisons connaissance": first name, last name, nickname
(12 characters max); the photo is optional.

#### B4.2 Browse events

Tab **Événements**:
- Pills: **À venir** (upcoming), **Sondages** (date polls), **Brouillons** (drafts and proposals waiting for approval),
  **Passés** (past), **Filtres** (categories, tags).
- Top right: magnifier (search) and bell (activity).
- Bottom right: **✨ Avec l'IA** (AI assistant) and **+ Proposer** (create with a form).
- Tap a card to open the event page. Its sections, top to bottom: title, date, place (tap: directions in Maps), "À propos",
  **Ajouter à mon agenda**, your answer, your ticket, the "Invités" card, carpool, party bar, details, participants,
  polls, "Qui amène quoi" (who brings what), discussion, **Signaler cet événement**, and for organisers the
  **ZONE ORGANISATEUR**. The page updates live (answers, arrivals, carpool, bar).
- Tap any name to open that person's profile (with **Écrire**, **Bloquer**, **Signaler le profil**).

#### B4.3 Create an event with the form

1. Événements › **+ Proposer**.
2. Choose **Simple** or **Avancé** (advanced: tags, places, price, date poll, polls, who brings what, forum…).
3. Fill in **Titre**, **Description**, **Quand** (date), **Où** (place search or text).
4. Tap **Envoyer pour validation** (the demo account's role needs an admin's approval; an organiser sees **Publier**),
   or **Enregistrer en brouillon**.
5. The first time you publish content, the **Terms of use** sheet appears: accept to continue.
6. While waiting, the event is in **Brouillons** with the badge "En attente de validation". Once an admin approves it,
   it is online. We approve demo-account proposals quickly during the review.

#### B4.4 Create an event with the AI assistant ("Créer avec l'IA")

1. Événements › **✨ Avec l'IA**: a native screen opens ("Créer avec l'IA", steps 1 La soirée · 2 Qui est invité ·
   3 C'est en ligne).
2. **Décris ton événement**: type or dictate (microphone, Apple dictation) e.g. "Raclette chez moi vendredi 20 h",
   optionally attach a photo or screenshot of a poster.
3. **Envoyer**. The first time, a consent sheet explains what is sent to Anthropic (Claude): **J'accepte** or
   **Pas maintenant** (then the form remains available).
4. "L'IA prépare ton événement…" (20–40 s). If something is missing, "Il me manque quelques infos": answer below.
   A place must be confirmed on the map ("Touche le bon").
5. Summary "**C'est juste ?**" › **Oui, continuer** (or **Corriger**).
6. Step 2 "**Qui est invité**" (web page): one tap on a visibility option publishes it — or sends it for approval for the
   demo account:
   - **🌍 Public + lien public**, **👥 Des groupes** (tick groups, then "Publier pour …"),
     **✉️ Sur invitation seulement**.
   The AI never chooses who is invited or who sees the event, never turns on tickets, carpool or group announcements,
   and never chooses a payment method.
7. Step 3: the event page opens. On the page, **✨ IA** (top right) edits the event the same way.

#### B4.5 Invite people

On an online event you organise (e.g. one you create), card **Invités** › **+ Inviter**:
- **Une personne** (one person) or **Plusieurs** (several people: unlimited by default, − / + to set places), optional
  link name ("Nom du lien"), then **Partager le lien…** (iOS share sheet: Messages, WhatsApp…) or copy it.
- The person opens the link, signs in with their phone like everyone, and answers.
- Each guest has the same "Invités" card with **counts only** (never names) and can create, copy and stop **their own**
  links. On a non-public event, someone who comes through a *guest's* link waits for the organiser: section
  **À accepter** in the organiser's "Invités" card.
- Groups: Réglages › Groupes › a group › **Inviter avec un lien** (reusable group link).

#### B4.6 Answer an event

On an event page: **Présent** (going), **Peut-être** (maybe), **Absent** (not going). Each answer shows its time.
Absent removes you from the carpool.

#### B4.7 Vote on a date poll

Événements › **Sondages** › "Démo Apple · Sondage" › for each date **Oui** / **Si besoin** / **Non** ›
**Valider mes dates**. The organiser later taps **Fixer cette date**: "Oui" and "Si besoin" become "Présent".

#### B4.8 Add to calendar

On an event: **Ajouter à mon agenda**. The first time, iOS asks to subscribe to a personal calendar "Vendredi Party"
(a private feed for this account); afterwards the event follows any change on its own. In a date poll, the native app
can also put the proposed dates in the iPhone calendar (permission asked at that moment) and remove the unused ones once
the date is fixed.

#### B4.9 Carpool

On "Soirée démo" (organiser's option, off by default), card **Covoiturage**: **🚗 Je conduis** (offer seats, optional
departure town) or **🙋 Je cherche une place**, then **Monter** / **Prendre**. Only participants and organisers take
part. No money, no cost sharing.

#### B4.10 QR ticket and Apple Wallet

On "Soirée démo" (option "Billets QR"), once your ticket is handed to you, card **Ton billet** › **Afficher ›**: the QR
code to show at the door, and the badge **Ajouter à Cartes Apple** (native PassKit sheet). Organisers hand a ticket with
**Remettre le billet**, or it arrives automatically when they confirm a payment; they check tickets at the door with
**📷 Scanner les billets** (ZONE ORGANISATEUR, Apple's native QR reader). A ticket never exists unless the organiser
turned tickets on.

#### B4.11 Paying for a real-world event (outside the app)

An organiser may set a price per person for a **real-world** event (a dinner, a seat, an activity) and choose how
people pay:
- **On me paie** (pay me): the organiser's own payment link (e.g. Revolut), Twint number or IBAN, shown to participants;
- **Paiement en ligne**: a ticketing / payment page of a third party (https link);
- **Sur place**: cash or card on the day — nothing to do in the app.

Guest side, on "Soirée démo" after **Présent**: **Payer [organiser] · 10 CHF** opens the organiser's details; a payment
link opens **outside the app (Safari or the provider's app)**. Back in Party, **J'ai payé** is only a note to the organiser.
Organiser side: **Reçu ✓** / **Pas reçu**. While "Paiement ouvert" is off, guests only see "paiement bientôt possible".

Party never sells anything, never processes, holds or transfers money, and offers no digital goods: these are payments
between real people for real-world goods and services consumed outside the app (guideline 3.1.3(e)). No in-app purchase
is involved.

#### B4.12 Party bar ("Bar de la soirée")

An organiser's option, off by default, for the **physical drinks served at the party**. A paid bar exists only on
non-public events; a free bar ("bar offert") is possible on any event. Tobacco and drug items are refused.

Guest side (you are "Présent" on "Soirée démo"):
1. Card **🍹 Bar de la soirée** › **Ouvrir le bar ›**: the menu (price, "16+"/"18+" badge, stock), your QR code, your
   balance.
2. Before the first drink, read and accept the commitment to repay (**J'accepte l'engagement**).
3. Order with − / + › **Valider la commande** (or simply show your QR at the counter). Nothing is owed until a drink is
   actually served.
4. Repay the organiser **outside the app** (Revolut, Twint or IBAN shown in the card) › **J'ai remboursé**.

Organiser / barman side (on an event you organise; on "Soirée démo" you are a guest):
- ZONE ORGANISATEUR › **🍹 Gérer le bar**: tabs **Articles** (name, price, stock, minimum age **Aucun / 16+ / 18+**,
  limits per person), **Options**, **Rembourser**, **Barmans**, **Direct** (live orders), and
  **📄 Récapitulatif de la soirée** (who owes what, export to PDF).
- **🍹 Scanner au bar**: scan a guest's QR, then **Servir**. Scanning needs a second phone showing a guest's QR; all
  other bar screens can be tried with the demo account alone.

The barman checks age **in person** (the app stores no date of birth). There is no ranking, reward or prompt to drink.
The app only records who owes what to the organiser; the money is repaid outside the app.

#### B4.13 Discussions (group chats and direct messages)

Tab **Discussions** (signed-in accounts):
1. Open **Démo Apple**: group conversation (text, photos, voice messages, replies, reactions, mentions).
2. The first message you send asks you to accept the **Terms of use**.
3. **Long-press a message** › **Répondre**, **Copier**, **Signaler** (report: choose a reason, optional comment).
4. Direct message: open the conversation with our admin (from the list), or tap a person's name › **Écrire**. A direct
   message is only possible between people who share a group or an event, or whose number is in your contacts.
5. In a direct chat, **ⓘ** › **Bloquer [name]** / **Signaler [name]**. Blocking hides that person's messages at once
   (groups, direct messages, event discussions), notifies our moderators, and stops them writing to you, mentioning,
   inviting you or seeing your profile; they are not told. Unblock: Réglages › Confidentialité › **Personnes bloquées**.
6. Top right **✎** creates a new group (same groups as Réglages › Groupes); top left pauses chat notifications.

Each event can also have its own **Discussion** (organiser's option "Forum de l'événement"), with the same rules.

#### B4.14 Groups

Réglages › **Groupes**: your groups, **Nouveau groupe**, members, **Inviter avec un lien** (QR, copy, share),
"Montrer mon numéro dans ce groupe" (hidden by default), leave a group.

#### B4.15 Games

Tab **Jeux**:
- **Salle de jeux** (game room): **Créer une salle** (or type a friend's 4-digit room code under "ou rejoindre"). Others
  join with the QR or the code. In the room, everyone votes for the next game; the host taps a game to launch it, and
  **🎮 Changer de jeu** brings everyone back to the room. **Quiz** can be played alone; most other games need 2+ phones.
- **🧠 Jeux solo** › **Méninges** › **Faire chauffer**: daily brain warm-up (speed, memory, logic), 3 lives.
- Each game has a **?** with its rules.
- **Pyramide** (card game): your cards are shown for 30 s in a native panel that screenshots and screen recordings
  turn black.
- Some games (category "🍻 Alcool" and a 🍻 tag on a few others) have an **optional sips mode for adults**: nobody has to
  drink, a glass of water always counts, **0 sips = the alcohol-free version**, and scores/rankings never count drinks.
  There is **no gambling**: no bets, no money, no prizes, no purchases. Casino and Blackjack are hidden and refused by
  our server in the App Store app.
- Without an account you can play a few games per party (then a phone number is asked, anti-abuse).

#### B4.16 Music

Tab **Musique**: **Scanner le QR de l'hôte** or type the party's 4-digit **Code** › **Entrer**, then search a song
("Titre, artiste ou lien") and add it to the shared queue; "Me prévenir quand mon titre passe" starts a Live Activity.
Music requires a **party running at the host's place** (the host's speakers and music account): outside a party, the
screen only shows how to join. A short message to the host is possible ("Un message pour l'hôte ?").

#### B4.17 Shared expenses ("Pot commun")

Réglages › **Pot commun**: shared expense lists between friends (who paid, who owes what). Receipts can be scanned
(VisionKit; optional AI reading with consent). It only records amounts; repayments happen outside the app.

#### B4.18 Feedback ("Ton avis")

Réglages › **Ton avis**: send an idea or a bug report to the organisers; optional AI writing help (consent required).

#### B4.19 Notifications

Réglages › **Notifications**: one switch per type, grouped as Général, Musique, Jeux, Ton avis, Événements (new event,
reminders, event discussions…), Discussions des groupes, Amis, Comptes et modération, Quand j'organise. The moon icon
(top right of Réglages) pauses notifications for a while. Each event page has **🔔 Sourdine** (mute). The app works
without notifications. iOS permission is asked only when you turn them on (e.g. the banner "Ne rate rien de cet
événement" on an event page).

#### B4.20 Privacy, AI consent, blocked people, terms

Réglages › **Confidentialité**: "Noms de mes contacts" (optional), **Personnes bloquées**, **Conditions d'utilisation**
(terms, contact), the **IA de Party** consent (withdraw or give again), then the full privacy policy.

#### B4.21 Delete the account

Réglages › **Gérer mon compte** › type **SUPPRIMER** › **Supprimer définitivement mon compte**. It deletes the profile,
photos, answers, votes, messages, the events the person created, game stats, AI consents and AI usage log.
**Se déconnecter** (sign out) is just below.

### B5. Content that is loaded from our server

Honestly stated: the **Events** and **Games** tabs (and a few settings pages for admins) are our own website,
`https://party.bobycharbon.ch`, displayed in a `WKWebView`. It is the same HTML/JavaScript for every user and every
platform (web, iPhone), maintained by us.

- What comes from the server: the whole Events module (lists, event pages, invitations, date polls, tickets, payments,
  carpool, party bar, event discussions, activity), all multiplayer games and Méninges, the admin "Annonce et
  maintenance" page.
- What is native in the binary: tab bar, Music (guest and host), Settings and all its pages, Discussions, Groups,
  "Ton avis", the AI event assistant, "Pot commun", offline screen, announcement banner, QR scanner, Wallet, Calendar,
  Contacts, Live Activity, share extension, quick action, push notifications.
- The page can only call a fixed set of native features exposed by the app (`window.PartyNative`: tabs, push, Wallet,
  calendar, contacts names, QR scan, AI screen, announcement, Pyramide cards, haptics). Server content never adds or
  changes native features, and no executable code is downloaded into the binary (2.5.2).
- Only our domain, our authentication provider and the host's music sign-in open inside the app; **every other link
  opens in Safari** (no unrestricted web browsing).
- Because the Events and Games tabs are web content, they can be improved without a new binary; any **major new
  feature** delivered this way is described in these notes before it is turned on in production (2.3.1(a)).

### B6. User-generated content and safety (1.2)

- **Who can post**: only signed-in people with a verified phone number (answers and votes also need a complete profile:
  first name, last name, nickname).
- **Terms of use** must be accepted before the first content (message, event, group, nickname…); they forbid harassment,
  hate, sexual or violent content, illegal content, spam; zero tolerance. Users must be **18 or older**.
- **Word filter** on messages, nicknames, names, group names, places and texts shown in games.
- **Signaler** (report) on every message, profile, profile photo, event, poll and game answer shown to others.
- **Bloquer** (block) from a profile or a direct chat; blocked people disappear from your conversations at once and the
  block is reported to moderators.
- **Moderation**: our moderators receive each report with a copy of the content; they hide content, warn, suspend or ban
  accounts. Reports are handled within 24 hours.
- **Contact** published in the app (Settings › Confidentialité › Conditions d'utilisation) and on the support page:
  support@vendrediparty.ch.

### B7. Alcohol and age (1.4.3)

Party is for adults (18+) and is rated 18+. Drinking modes in games are optional, water always counts, 0 sips is the
alcohol-free version, and nothing ranks, rewards or pushes people to drink. The party bar lists the drinks the
organiser serves at a private party, with age badges checked in person by the barman; tobacco and drug items are refused.
Our screenshots and App Store texts show no alcohol.

### B8. Permissions (asked only when needed)

| Permission | When it is asked |
|---|---|
| Notifications | When you turn notifications on (Settings or the event banner) |
| Camera | Scanning a QR code (host, ticket, bar) or taking a profile / event photo |
| Photos | Choosing a photo; "Add to Photos" on a long-press of an image |
| Microphone + Speech recognition | Only while you dictate (AI assistant, feedback) or record a voice message |
| Calendars | "Add the poll dates to my calendar" in a date poll |
| Contacts | Optional "Noms de mes contacts": numbers are hashed on the iPhone, names never leave it |

No location, no tracking, no App Tracking Transparency prompt (nothing to track).

### B9. What is not in this app

No in-app purchase, no subscription, no ads, no tracking or analytics SDK, no gambling or simulated gambling, no loot
box, no contest or prize, no cryptocurrency, no virtual currency for sale, no rewards for ratings or reviews. No
third-party sign-in (phone + SMS code only, so Sign in with Apple is not required by 4.8). The Apple TV app shares this
record but is not part of this submission.

### B10. Contact

support@vendrediparty.ch — we answer during the review and can approve the demo account's proposals or prepare more
data on request.
