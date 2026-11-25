# Vendredi Party — Notes for App Review (iOS 1.0.0)

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
> 2. Refus Apple 1.4.3 (25.11) : le bar est **caché dans l'app App Store** ; la démo n'a plus aucun article alcoolisé ni
>    texte « commander au bar » (`supabase/prod/2026-11-25-demo-sans-alcool-apply.sql`, à appliquer avant l'envoi).
> 3. Groupe **« Démo Apple »** : Apple-test + un admin, **quelques messages** (un vocal et une photo neutre si possible).
> 4. Un **message privé** d'un admin à Apple-test (ils partagent le groupe, donc « Écrire » marche).
> 4 bis. Discussions v2 (18.11) : un **second compte de démo « Apple-test 2 »** (autre numéro à code fixe, Supabase › Test
>    OTP ; numéro dans ce guide exporté, code dans App Store Connect, jamais dans le dépôt), profil complet, CGU acceptées,
>    **aucun groupe ni événement privé en commun** avec Apple-test, et **une demande de message en attente** d'Apple-test 2
>    vers Apple-test (texte neutre : « Salut, on s'est croisés à la soirée démo ? »). Apple voit ainsi « Demandes (1) ».
> 5. Recommandé : **« Démo Apple · Sondage »** (organisé par un admin, Apple-test invité, « Date à définir », 3 créneaux).
> 6. Pendant toute la revue : valider vite toute proposition d'Apple-test (bandeau « … attend ta validation »), garder l'IA
>    sous son plafond mensuel, AUCUNE mise en prod ni maintenance (24-48 h).
> 7. Corrections annoncées par le coordinateur et décrites ici **comme déjà en place** (à contrôler en prod avant l'envoi) :
>    « Bloquer » masque aussitôt les messages et prévient les modérateurs ; aucun jeu à boire, aucune gorgée, aucun mode Hot / Mix
>    ni bar dans l'app App Store (refus 1.4.3, 25.11, `app/store_app.py`) ; CGU « 18 ans et plus ». Si l'une manque en prod : corriger ce
>    texte avant l'envoi (Apple compare les notes et l'app).
> 8. Copier la **partie A** dans App Store Connect › App Review Information › **Notes** (3994 caractères, limite 4 000 ; 25.11 : refus 1.4.3) ET
>    dans `ios/appstore/review-notes.txt` (même texte) (c'est ce fichier que `tools/appstore_submit.py` envoie ; la partie A garde tous
>    les mots exigés par `tests/test_ios_app.py::test_review_notes_describe_every_big_feature_delivered_by_the_web`).
> 9. Exporter la **partie B** en PDF (sans cet encadré) et la joindre dans App Review Information › **Attachment**.

---

## PART A — Text for the "Notes" field (3,994 characters, limit 4,000)

```text
ABOUT
"Vendredi Party" (icon "Party !"): free app by Ludovic Trombert, an individual developer based in France, for anyone organising real-world events with friends: party games, chats. French, 18+. No ads, tracking or in-app purchase. Guide attached (PDF).

CHANGES SINCE THE 1.4.3 REJECTION (new build + server, permanent for this version)
Removed from the App Store app: every game linked to drinking (Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Beer pong, Biskit, Purify Test), every drink option, Hot/Mix questions, the party bar, Casino, Blackjack and the Music tab. Not renamed or re-skinned: our server recognises this app and refuses them, even by code or QR. Our website is separate; the app never opens its games. No drink words, demo included.

SIGN-IN
Phone + 6-digit SMS code. Demo "Apple-test": number and code in the sign-in fields (fixed code, no SMS). Tab "Se connecter" > "Suisse +41" > number > code.

TRY IT
1. Events > "Soirée démo Vendredi Party" (co-organiser): answer "Présent", see who comes, use the event chat.
2. Events > "+ Proposer" or "Avec l'IA" > "Qui est invité" > tick group "Démo Apple" > Publish: live at once. Public events: moderators check first (1.2).
3. Discussions > "Démo Apple": long-press > "Signaler"; "Nouveau message"; "Demandes".
4. Games > "Créer une salle" > Quiz, or Méninges.

NATIVE (4.2)
Native tab bar; SwiftUI Settings, Discussions, Groups, event chat, "Ton avis", AI assistant, "Pot commun". Push (a switch per type), Live Activity (music, host's party only), Wallet (tickets), QR scanner, Calendar, Contacts (optional, hashed), dictation. Share sheet > Party: event from a link (AI).

WEB CONTENT (2.5.2)
Events and Games tabs: our own site in a WKWebView. Other sites: Safari. Games > Code: 4 digits = a game; 6 digits = a host's music party (native Music screen, no tab; needs the host's Sonos: see attached video). Not in this version: Pronos, Agenda, companion. This build never opens them; only a future version, submitted for review, could add them.

EVENTS
Links for one person or "Plusieurs"; guests make, copy and stop own links (counts only). Not public: a guest's guest waits ("À accepter"). Date poll. Calendar feed. Carpool (no money), QR ticket + Wallet: organiser options (Modifier). Groups: "Inviter avec un lien". Sign-in for events (name, nickname of 12 characters max); games stay unlimited without an account. Updates live; tap a name to open the profile; each answer shows its time. Admins: "Nouveau compte", announcement or maintenance.

PAYMENTS (3.1.3(e))
Party never sells, holds or moves money. Events: organiser's own Revolut/Twint/IBAN, ticketing link (Safari) or on site. Paying unlocks nothing in the app; the QR ticket is for door entry. "Pot commun": split real costs; "Rembourser" shows the friend's own IBAN/Revolut/Twint.

DISCUSSIONS (1.2)
Event chats: only guests who answered "Présent" / "Peut-être" and organisers. DMs only with a real link (shared group or event); others send a message request: one text, no photo/link/number: "Accepter / Supprimer / Bloquer / Signaler". Settings > Confidentialité > "Demandes de message". "Nouveau message": real links only, search by name; 2+ people make a private group, not read by admins. Terms first, word filter, "Signaler" on each message (photo/voice kept for moderators, last 10 messages if ticked); "Bloquer" hides messages at once and alerts moderators. Tap a name: mini-profile. Reports within 24 h. Demo "Apple-test 2" (see guide) sees the request from the other side. Contact: support@vendrediparty.ch.

AI (5.1.2(i))
"Avec l'IA", "Ton avis" and receipts go to Anthropic (Claude) only after "J'accepte" (withdraw: Settings > Confidentialité).

GAMES (18+)
No drinking games: quizzes, card, word, party and 3D games, points only; first-party content. No gambling, purchase, prize. Written answers: filter + "Signaler"; anyone can leave, the host can ban.

DELETION
Settings > "Gérer mon compte" > "Supprimer mon compte" (type SUPPRIMER).
```

---

## PART B — Full guide for the App Review team (attach as PDF)

### B1. What Party is

Party ("Vendredi Party" on the App Store, "Party !" under the icon) is a free, non-commercial app published by
**Ludovic Trombert, an individual developer based in France**. Party is for anyone who organises real-world events and game nights with friends. The
in-app terms and privacy policy are up to date (publisher based in France).

What you can do with it:

- **Events** — create an event (form or AI assistant), invite people with a link or a group, answer
  (Présent / Peut-être / Absent), vote on dates, share rides, get a QR ticket in Apple Wallet, pay the organiser
  **outside** the app for a real-world event.
- **Discussions** — group chats and direct messages between people who know each other.
- **Games** — party games played together on everyone's phone in a "game room", plus solo brain games. **No drinking
  games**: quizzes, card, word, party and 3D games with points only.
- **Music** (no tab in the App Store app) — at a party at the host's place, a guest types the host's 6-digit code in
  Jeux › **Code** and adds songs to the host's queue (the host's own speakers and music account).
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
| Demo account | Nickname "Apple-test" (Apple Review), complete profile. Ordinary member role: an event reserved to the group "Démo Apple" is published at once (**Publier**); a public or invitation-only event is sent to our moderators first (**Envoyer pour validation**, see B4.3). |
| Event **"Soirée démo Vendredi Party"** (12 Dec.) | Organised by us, invitation only; the demo account is invited AND co-organiser: answer (**Présent**), see who comes, event discussion; organiser side: ZONE ORGANISATEUR (guests and their answers). Tickets, payment and carpool are off on this event (options of the organiser, described below for completeness). |
| Group **"Démo Apple"** | The demo account + one of our admins, with a few messages. |
| Direct message | One message from our admin to the demo account. |
| Second demo account **"Apple-test 2"** | Number **+41 79 000 00 01**, same fixed code as the first demo account (no SMS). Shares no group or private event with "Apple-test" and has sent it a **message request** (Discussions › **Demandes**). Sign in with it to see the sender side ("Demande envoyée", input closed until accepted). |

If you test account deletion: please do it last. Signing in again with the same number then creates a new, empty
account (the prepared data stays linked to the deleted one).

### B3. Map of the app

When the app opens, it shows the **Événements** (Events) tab. The bottom bar is a native `UITabBar`:

| Tab (signed out) | Tab (signed in) | Built with |
|---|---|---|
| Jeux (Games) | Jeux | Web content (our site) |
| Événements (Events) | Événements | Web content (our site) |
| — | Discussions | Native SwiftUI |
| Se connecter (Sign in) | Réglages (Settings) | Native SwiftUI |

Native screens opened from the web tabs: "Créer avec l'IA" (AI event assistant), Apple QR scanner, "Add to Apple Wallet"
sheet, Calendar, Contacts card, share sheet, and the Music screen (opened from Jeux › Code with a 6-digit party code:
there is no Music tab in the App Store app).

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
  **Ajouter à mon agenda**, your answer, the event's polls (right under the answer), your ticket, the "Invités" card,
  carpool, details, participants, "Qui amène quoi" (who brings what), discussion, **Signaler cet événement**, and for organisers the
  **ZONE ORGANISATEUR**. The page updates live (answers, arrivals, carpool).
- Tap any name to open that person's profile (with **Écrire**, **Bloquer**, **Signaler le profil**).

#### B4.3 Create an event with the form

1. Événements › **+ Proposer**.
2. Choose **Simple** or **Avancé** (advanced: tags, places, price, date poll, polls, who brings what, forum…).
3. Fill in **Titre**, **Description**, **Quand** (date), **Où** (place search or text).
4. To publish at once: in **Qui voit l'événement**, tick the group **Démo Apple** (and nothing else), then tap **Publier**.
   A public or invitation-only event shows **Envoyer pour validation** instead (our moderators check it first, 1.2).
   **Enregistrer en brouillon** keeps it as a draft.
5. The first time you publish content, the **Terms of use** sheet appears: accept to continue.
6. An event sent for approval waits in **Brouillons** with the badge "En attente de validation". Once a moderator
   approves it, it is online. We approve demo-account proposals quickly during the review.

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
6. Step 2 "**Qui est invité**" (web page): **👥 Des groupes** › tick "Démo Apple" › "Publier pour …" publishes it at once;
   for the demo account, a public or invitation-only event is sent for approval (moderators check it first):
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
Absent removes you from the carpool. The event's polls sit right under the answer; on an event with a fixed date,
voting in them is open once you answered **Présent** or **Peut-être**.

#### B4.7 Vote on a date poll

On an event whose date is still a poll (none is prepared in the demo data) › for each date **Oui** / **Si besoin** / **Non** ›
**Valider mes dates**. The organiser later taps **Fixer cette date**: "Oui" and "Si besoin" become "Présent".

#### B4.8 Add to calendar

On an event: **Ajouter à mon agenda**. The first time, iOS asks to subscribe to a personal calendar "Vendredi Party"
(a private feed for this account); afterwards the event follows any change on its own. In a date poll, the native app
can also put the proposed dates in the iPhone calendar (permission asked at that moment) and remove the unused ones once
the date is fixed.

#### B4.9 Carpool

On an event where the organiser turned it on (option off by default; off on the demo event), card **Covoiturage**: **🚗 Je conduis** (offer seats, optional
departure town) or **🙋 Je cherche une place**, then **Monter** / **Prendre**. Only participants and organisers take
part. No money, no cost sharing.

#### B4.10 QR ticket and Apple Wallet

On an event with the option "Billets QR" (off on the demo event), once your ticket is handed to you, card **Ton billet** › **Afficher ›**: the QR
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

Guest side, on a priced event after **Présent** (the demo event is free): **Payer [organiser] · 10 CHF** opens the organiser's details; a payment
link opens **outside the app (Safari or the provider's app)**. Back in Party, **J'ai payé** is only a note to the organiser.
With **On me paie**, the organiser confirms it: **Reçu ✓** / **Pas reçu**. With **Paiement en ligne**, the organiser
simply sees who noted they paid (the third-party site is not theirs to check). While "Paiement ouvert" is off, guests only see "paiement bientôt possible".

Party never sells anything, never processes, holds or transfers money, and offers no digital goods: these are payments
between real people for real-world goods and services consumed outside the app (guideline 3.1.3(e)). No in-app purchase
is involved.

#### B4.13 Discussions (group chats, direct messages, message requests)

Tab **Discussions** (signed-in accounts):
1. Open **Démo Apple**: group conversation (text, photos, voice messages, replies, reactions, mentions).
2. The first message you send asks you to accept the **Terms of use**.
3. **Long-press a message** › **Répondre**, **Copier**, **Signaler** (report: choose a reason, optional comment, optional
   box "Joindre les 10 messages précédents"; a reported photo or voice message is copied for our moderators).
4. **Who can write to whom** (decided by the database): people with a real link (a shared group other than "Membres
   Vendredi Party", a shared private event, or the organiser of an event you answered) write directly. Anyone else can
   only send a **message request**: one text message, no photo, voice, link or phone number, nothing more until accepted.
5. **Demandes** (top of the list): each request shows the sender's mini-profile and message with **Accepter**,
   **Supprimer**, **Bloquer**, **Signaler**. The sender is never told of a refusal. Settings › Confidentialité ›
   **Demandes de message**: "Tout membre" (default) or "Personne". Limits: 10 new requests a day, 30 pending.
6. **Nouveau message** (pink button): suggestions come only from real links (your groups, people met at an event in the
   last 60 days, your phone contacts already on Party if you allow Contacts); search by first name, last name or nickname,
   never by phone number. Choosing 2 or more people creates a **private group** (name, emoji, colour, invitations to
   accept), which our administrators never read; it is moderated through reports, like direct messages.
7. **Mini-profile**: tap any name or photo (chats, guest lists, groups…) › **Envoyer un message** (disabled with
   the reason when not allowed), "Déjà vu N fois" (past parties attended together), upcoming events in common,
   **Bloquer** · **Signaler**.
8. Blocking hides that person's messages at once (groups, direct messages, event discussions), removes their requests,
   notifies our moderators, and stops them writing to you, mentioning, inviting you or seeing your profile; they are not
   told. Unblock: Réglages › Confidentialité › **Personnes bloquées**.
9. Read receipts ("Vu") in direct chats only if both people keep **Confirmations de lecture** on; "écrit…" is a live
   signal, never stored. Neither appears in a request or with a blocked person.

Each event can also have its own **Discussion** (organiser's option "Forum de l'événement"), with the same rules.

#### B4.14 Groups

Réglages › **Groupes**: your groups, **Nouveau groupe**, members, **Inviter avec un lien** (QR, copy, share),
"Montrer mon numéro dans ce groupe" (hidden by default), leave a group.

**Event guests in a group (organiser option, off by default).** In step 2 "Qui est invité" or in the event's guest card
("Régler"), the organiser can pick one group they manage and belong to, or "Nouveau groupe" (name filtered, terms
required); "Membres Vendredi Party" can never be chosen. Each guest then sees, right under the answer buttons, a large
**unticked** box "Rejoindre aussi le groupe « … » de …" that explains what members will see (nickname, name, photo; the
phone number stays hidden), that they can write in the group chat and invite them to future events, and that they can
leave at any time. Only a guest who ticks the box joins (whatever the answer); the answer never depends on the box.
A guest who answered without ticking keeps a "Rejoindre le groupe" button on the event page (no reminder, no
notification). After joining, a personal notification "Tu es dans le groupe X" (own switch in Réglages › Notifications)
and a banner in the group chat with **Quitter**; group members are not notified. Someone who left is never put back
without their own action; blocked people are never added. Day after the event, the organiser may see "🎉 Garder cette
bande ?": it only sends **invitations** to the group, once per event, which each person accepts or declines. No reward
of any kind is attached to joining.

#### B4.15 Games

Tab **Jeux**:
- **Salle de jeux** (game room): **Créer une salle** (or type a friend's 4-digit code in **Code** › **Rejoindre**). Others
  join with the QR or the code. In the room, everyone votes for the next game; the host taps a game to launch it, and
  **🎮 Changer de jeu** brings everyone back to the room. **Quiz** can be played alone; most other games need 2+ phones.
- **🧠 Jeux solo** › **Méninges** › **Faire chauffer**: daily brain warm-up (speed, memory, logic), 3 lives.
- Each game has a **?** with its rules.
- **No drinking games** (since the 1.4.3 review, 25.11). Removed from the App Store app, permanently for this version:
  every game linked to drinking by its origin, rules or texts (**Pyramide, Je n'ai jamais, Qui de nous ?, Roulette,
  Beer pong, Biskit, Purify Test**), every drink option of the other games, the "Hot" / "Mix" question modes and the
  "WTF" theme of Pour ou contre. They are not renamed or turned into points: they are simply absent. The remaining games
  are Quiz, Qui est le plus… ?, L'Intrus, Président, Pour ou contre, Le Divan, Tu me connais ?, Le Masque, Le Reflet,
  Qui es-tu vraiment ?, the 3D games and Méninges; their questions and words never mention alcohol, drunkenness or
  drugs. Our server refuses the removed games to the App Store app at creation, by code, by QR, in a game room and
  when reading a game.
- There is **no gambling**: no bets, no money, no prizes, no purchases. Casino and Blackjack are hidden and refused by
  our server in the App Store app.
- In the App Store app, games stay **unlimited without an account**; an account (phone number) is needed only for
  events, groups and chats.
- **Players**: any player can leave a game at any time; the host can remove and ban a player; written answers can be
  reported ("Signaler") and are then hidden for the whole table.
- **Index of games (4.7.4)**: all games are first-party, written and hosted by the developer; there are no third-party
  mini apps or games. Universal link to the games: https://party.bobycharbon.ch/?tab=games (opens the **Jeux** tab of
  the app). Games offered in the App Store app: Quiz, Qui est le plus… ?, L'Intrus, Président, Pour ou contre, Le Divan,
  Tu me connais ?, Le Masque, Le Reflet, Qui es-tu vraiment ?, the 3D games Néon Knockout, L’île qui s’effondre and
  Braquage en miniature (13 games), and Méninges (solo).

#### B4.16 Music

There is **no Music tab** in the App Store app. At a party at the host's place (the host's speakers and music account),
a guest opens **Jeux**, types the host's **6-digit** party code in **Code** (4 digits = a game) or scans the host's QR:
the native Music screen opens. Search a song ("Titre, artiste ou lien") and add it to the shared queue; "Me prévenir
quand mon titre passe" starts a Live Activity. Without a running party there is nothing to join: Music needs a host
playing on Sonos at home, so it cannot be opened without one: a short video recorded on a real iPhone is attached to
the submission (Jeux › Code with 6 digits, search, add a song, Live Activity). Search
results are credited to Spotify ("Résultats Spotify", each song opens in Spotify); song suggestions never require an
account. The share extension ("Party" in the share sheet) does not touch Music in this app: it only offers "Créer
l'événement" from a shared link (the AI assistant drafts the event, you review it before publishing).

#### B4.17 Shared expenses ("Pot commun")

Réglages › **Pot commun**: private shared expense lists between friends, joined only by link (who paid, who owes
what); names, titles and notes pass the app's word filter. Receipts can be scanned
(VisionKit; optional AI reading with consent). It only records amounts; repayments happen outside the app: "Rembourser"
only shows the friend's own IBAN, Revolut, PayPal or Twint (opens Safari or copies it). No money goes through Party and
nothing digital is unlocked.

#### B4.18 Feedback ("Ton avis")

Réglages › **Ton avis**: send an idea or a bug report to the organisers; optional AI writing help (consent required).

#### B4.19 Notifications

Réglages › **Notifications**: one switch per type, grouped as Général, Jeux, Ton avis, Événements (new event,
reminders, event discussions…), Discussions des groupes, Amis, Comptes et modération, Quand j'organise (Musique only once a music party is joined). The moon icon
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
`https://party.bobycharbon.ch`, displayed in a `WKWebView`, maintained by us. Our server recognises the App Store app
(its User-Agent) and always gives **every user of this app** the same dedicated version: no drinking game or drink
option, no party bar, no Casino / Blackjack, no Hot / Mix questions, no Music tab. Our public website and other
platforms are separate; the app never opens their games.

- What comes from the server: the whole Events module (lists, event pages, invitations, date polls, tickets, payments,
  carpool, event discussions, activity), all multiplayer games and Méninges, the admin "Annonce et
  maintenance" page.
- What is native in the binary: tab bar, Music screen (guest and host, opened from Jeux › Code), Settings and all its pages, Discussions, Groups,
  "Ton avis", the AI event assistant, "Pot commun", offline screen, announcement banner, QR scanner, Wallet, Calendar,
  Contacts, Live Activity, share extension, quick action, push notifications.
- The page can only call a fixed set of native features exposed by the app (`window.PartyNative`: tabs, push, Wallet,
  calendar, contacts names, QR scan, AI screen, announcement, haptics). Server content never adds or
  changes native features, and no executable code is downloaded into the binary (2.5.2).
- Only our domain, our authentication provider and the host's music sign-in open inside the app; **every other link
  opens in Safari** (no unrestricted web browsing).
- Because the Events and Games tabs are web content, they can be improved without a new binary; any **major new
  feature** delivered this way is described in these notes before it is turned on in production (2.3.1(a)). Pronos,
  Agenda and the companion are not available in this app, and the removed games stay removed for version 1.0.0. They
  would only come in a future app version submitted for review and approved, never for this version.

### B6. User-generated content and safety (1.2)

- **Who can post**: only signed-in people with a verified phone number (answers and votes also need a complete profile:
  first name, last name, nickname).
- **Terms of use** must be accepted before the first content (message, event, group, nickname…); they forbid harassment,
  hate, sexual or violent content, illegal content, spam; zero tolerance. Users must be **18 or older**.
- **Word filter** on messages, nicknames, names, group names, places and texts shown in games.
- **Signaler** (report) on every message, profile, profile photo, event and poll, and on the players' written answers
  shown to the table in Le Masque, Tu me connais ? and the dilemmas proposed in Pour ou contre (hidden at once for
  everyone, logged for moderators). In every game the host can remove or ban a player.
- **Bloquer** (block) from a profile, a mini-profile, a direct chat or a message request; blocked people disappear from
  your conversations at once and the block is reported to moderators.
- **Message requests**: people without a real link can only send one text message, which the recipient accepts or not;
  "Demandes de message: Personne" turns them off. Direct messages and private groups are never read by our admins;
  reported content (with its photo or voice message) is copied for moderators.
- **Moderation**: our moderators receive each report with a copy of the content; they hide content (the author is told
  why and how to appeal), warn, suspend or ban accounts. Reports are handled within 24 hours.
- **Contact** published in the app (Settings › Confidentialité › Conditions d'utilisation) and on the support page:
  support@vendrediparty.ch.

### B7. Changes since the 1.4.3 rejection (25.11.2026)

New build, and our server, permanent for this version of the App Store app:
- Removed from the App Store app: every game linked to drinking — **Pyramide, Je n'ai jamais, Qui de nous ?, Roulette,
  Beer pong, Biskit, Purify Test** — and the former "Alcohol" games category; every drink option of the other games;
  the "Hot" and "Mix" question modes and the "WTF" theme of Pour ou contre; the party bar (menu, orders, notifications,
  settings); Casino and Blackjack; the Music tab (a music party is joined from Jeux › Code, 6 digits).
- Nothing was renamed or converted: the removed games and options are simply absent from the app.
- Remaining games use points only; their questions and words never mention alcohol, drunkenness or drugs, and texts
  typed by players in a game of the app are refused if they do.
- Our server recognises the App Store app and refuses the removed games to all its users: creation, code, QR, game
  room and reading. Our public website is separate.
- The demo event lists no alcohol and no longer asks you to order at a bar.
- Party is for adults (18+) and is rated 18+. Our App Store texts show no alcohol.
- In this build, the in-app terms and privacy policy show no bar, no drink and no Pronos; "Mes stats de jeu" shows
  Méninges only; the camera prompt names party, game and ticket codes only; no drink emoji in the group or "Pot commun"
  pickers; no "Ajouter un titre" shortcut on the icon; Music notification settings only appear once a music party is
  joined; the Music screen credits Spotify ("Résultats Spotify", "Open in Spotify").
- Pronos, Agenda and the companion are not available in this app (only a future version, submitted for review,
  could add them); the
  "bar" tag is not listed in Settings › Notifications; song suggestions at a music party never require an account.
- Le Masque and Tu me connais ? draw no question about drinks; Tu me connais ? answers can be reported ("Signaler").
- Support URL: a dedicated support page (contact, publisher, FAQ); privacy URL: the app version of the policy.
- Wallet tickets show the issuer's contact on the back (publisher, support e-mail, support page).
- The share extension ("Partager dans Party") only offers "Créer l'événement" (an event drafted from a link by the AI
  assistant); it no longer adds songs to a music queue.
- A report made inside a game ("Signaler") also notifies our moderator at once, besides the moderation log.
- The demo organiser's nickname no longer contains a special character shown as a logo, nor a flag.
- Terms version of 25 November 2026: every account accepts the displayed text again before its next content.
- Notifications already received no longer show that special character either.
- Events created with the demo account and reserved to the group "Démo Apple" are published at once; public events
  are checked by our moderators first (anti-abuse, 1.2).
- The privacy policy confirms that each processor protects data at least as well as the policy, describes the data
  of "Pot commun" and says what stays for others, without any link to you, after an account is deleted.
- Quiz questions naming another phone platform are not drawn in the app.
- Music: a short video recorded on a real iPhone is attached (a music party needs the host's Sonos).
- Pronos, Agenda and the companion stay off in this build even if our server turns them on for the website; the
  "Pot commun" button that shows a friend's payment details is now "Rembourser" (no card icon).
- The privacy policy states that Party's server is hosted in France by the publisher (database by Supabase, Zurich),
  and the AI consent sheet says that feedback given to the AI may be published on GitHub, where anyone can read it,
  without name or number, to fix the app; that consent is asked again (new version of the text).
- Only the iOS app is submitted: no tvOS version is attached to this submission.
- Public events whose title, description, place or polls mention a drink, a bar outing (happy hour, afterwork, pub crawl…),
  tobacco, shisha or vaping are not listed in the app (only their guests and organisers see them).
- An index of the games (all first-party, with a universal link) is in B4.15 (4.7.4).
- "Pot commun" names, expense titles and notes now pass the same word filter as the rest of the app (1.2).
- The App Store description now lists both extensions: "Partager › Party" (an event from a link) and the Live Activity
  of a music party.

### B8. Permissions (asked only when needed)

| Permission | When it is asked |
|---|---|
| Notifications | When you turn notifications on (Settings or the event banner) |
| Camera | Scanning a QR code (party, game, ticket) or taking a profile / event photo |
| Photos | Choosing a photo; "Add to Photos" on a long-press of an image |
| Microphone + Speech recognition | Only while you dictate (AI assistant, feedback) or record a voice message |
| Calendars | "Add the poll dates to my calendar" in a date poll |
| Contacts | Optional "Noms de mes contacts" or "Tes contacts sur Party" in Nouveau message: numbers are hashed on the iPhone, names never leave it |

No location, no tracking, no App Tracking Transparency prompt (nothing to track).

### B9. What is not in this app

No in-app purchase, no subscription, no ads, no tracking or analytics SDK, no gambling or simulated gambling, no loot
box, no prize, sweepstake or lottery, no cryptocurrency, no virtual currency for sale, no rewards for ratings or reviews, no drinking game, no
party bar, no Music tab. Paying an organiser never unlocks anything in the app; the QR
ticket is for door entry only. No
third-party sign-in (phone + SMS code only, so Sign in with Apple is not required by 4.8). The Apple TV app shares this
record but is not part of this submission.

### B10. Contact

support@vendrediparty.ch — we answer during the review and can approve the demo account's proposals or prepare more
data on request.
