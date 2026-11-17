# Agenda de Party face à iCal et aux outils de rendez-vous : inventaire et écarts

17.11.2026, soir. Demande de l'admin : « exactement les mêmes fonctionnalités qu'iCal, tout ». Exemple qu'il donne : « 30 minutes
de non-disponibilité après la fin d'un rendez-vous, et 30 minutes avant quand un rendez-vous commence ».

Ce document compare quatre références à ce que fait notre Agenda aujourd'hui (code lu le 17.11 au soir, branche develop) :
- le Calendrier d'Apple (iPhone, Mac, iCloud.com) ;
- Google Agenda, « Agendas de rendez-vous » ;
- Calendly ;
- Microsoft Bookings et « Bookings with me ».

Apple n'a **aucune page de prise de rendez-vous**, même dans iOS 27. Les réglages de liens viennent donc de Google, Calendly et
Microsoft. Le détail des fonctions d'iCal est dans `fonctions-calendrier.md` (même dossier, 122 lignes, sources Apple).

Légende :
- **Oui** / **Partiel** / **Non** : ce que fait notre Agenda aujourd'hui ;
- **P1** : indispensable pour des liens de dispo sérieux. **P2** : utile. **P3** : accessoire, ou hors sujet pour Party ;
- effort **S** (moins d'un jour), **M** (2 à 4 jours), **L** (une semaine ou plus, ou un service nouveau).

Fichiers cités en abrégé :
- `M1` = supabase/migrations/20261117140000_agenda.sql ;
- `M2` = supabase/migrations/20261117150000_agenda_liens_calendriers.sql ;
- `M3` = supabase/migrations/20261117160000_agenda_liens_marges.sql. **Ce fichier n'est pas encore commité** : un autre
  travail en cours ajoute les marges, avec LinkEditor.tsx, lib/agenda.ts et des tests ;
- `LE` = web/events/src/components/agenda/LinkEditor.tsx ;
- `V` = web/events/src/components/agenda/Views.tsx ;
- `IT` = web/events/src/app/agenda/item.tsx ;
- `PUB` = app/agenda.py, page publique `/d/<jeton>` ;
- `iOS` = ios/Party/Agenda/ (AgendaBusy, AgendaStore, AgendaBridge).

---

## 1. Les P1 manquants, dans l'ordre à suivre

Chaque point donne une conception adaptée à notre modèle. Tout passe par `private.agenda_link_free` et
`private.agenda_link_busy`. Les migrations restent additives et rejouables.

1. **Marges avant / après chaque rendez-vous** : c'est l'exemple de l'admin. **En cours (M3, non commité)**.
   - Colonnes `buffer_before_min` / `buffer_after_min` sur `private.agenda_links` : de 0 à 240, par 5 minutes.
   - Dans `private.agenda_link_busy`, chaque plage « pris » est élargie : `[début − avant, fin + après]`. Cela vaut pour les
     calendriers choisis, les soirées et les demandes en attente ou acceptées. Calendly fait pareil : la marge vaut aussi
     autour des rendez-vous des agendas reliés.
   - Le choix est le bon. Il reste deux points à régler :
     a) Les plages sont arrondies à 30 minutes **avant** d'ajouter la marge, et les créneaux tombent sur une grille de
        30 minutes. Une marge de 10 ou 15 minutes vaut donc 30 minutes en pratique. Il faut, soit proposer seulement 0, 30,
        60, 90 ou 120 minutes, soit passer la grille à 15 minutes (point 3).
     b) Une marge peut déborder des heures d'ouverture du lien (Calendly l'accepte aussi). Il faut seulement l'écrire dans
        l'aperçu.
2. **Nombre maximum de rendez-vous par jour** (Google, Calendly, et Calendly aussi par semaine).
   - Colonne `max_per_day smallint null` (de 1 à 20, vide = sans limite).
   - Dans `agenda_link_free` (mode demandes), on retire les jours de Suisse qui comptent déjà N demandes `pending`,
     `to_confirm` ou `accepted`.
   - Option « tous mes liens » : compter par `owner_id` plutôt que par `link_id`.
   - Le même contrôle se refait dans `agenda_booking_request`, sous le verrou `for update` qui existe déjà.
3. **Pas des créneaux séparé de la durée**. Microsoft : de 5 minutes à 4 heures. Calendly : « Start time increments ».
   - Aujourd'hui, un rendez-vous de 90 minutes ne se propose qu'à 9 h 00, 10 h 30, 12 h 00 (`generate_series(w0, w1 - dur, dur)`).
   - Colonne `slot_step_min` (15, 30 ou 60 ; vide = la durée, comme aujourd'hui).
   - Remplacer le pas `dur` par `make_interval(mins => coalesce(slot_step_min, duration_min))`.
   - Avec 15, il faut aussi passer `agenda_floor30` / `agenda_ceil30` à 15 minutes **pour ce lien seulement**. Les plages
     envoyées par l'iPhone restent arrondies à 30 minutes : rien ne change pour la vie privée.
4. **Exceptions de dates : fermé, ou d'autres heures** (Google « Adjusted availability », Calendly « date-specific hours »).
   - Colonne `date_overrides jsonb` : `[{date:'2026-12-24', closed:true} | {date, ranges:[{from,to}]}]`, 60 au plus, dates
     dans l'horizon.
   - `agenda_link_windows` et la branche « demandes » de `agenda_link_free` remplacent les règles de la semaine par l'exception
     de ce jour-là.
   - Écran : « Dates à part » sous les plages, avec un mini-mois.
   - Contournement possible aujourd'hui : un rendez-vous « Pris » dans « Juste pour moi », si ce calendrier est coché pour le
     lien. Il passe mal et salit l'agenda.
5. **Lieu du rendez-vous** : adresse, téléphone, visio ou « à convenir » (Google : Meet, sur place, téléphone, à préciser ;
   Microsoft : Teams ou lieu).
   - Colonnes `place_kind` (`none`, `address`, `phone`, `video`, `later`) et `place_text` (200 caractères, filtré ; lien
     https seulement pour `video`).
   - La page publique annonce le **type** (« En visio », « À Lausanne »).
   - Le **détail** (adresse exacte, lien de visio, numéro) n'apparaît que sur `/d/r/<secret>` **après l'acceptation**, et dans
     le `.ics` (`LOCATION:`).
   - Le rendez-vous accepté recopie le lieu dans `agenda_items.place`.
6. **Prévenir l'inconnu par e-mail** : accusé de réception, acceptation, refus, rappel la veille (Google : 5 rappels ;
   Calendly et Microsoft : e-mails avec liens d'annulation et de report).
   - Aujourd'hui, l'inconnu doit revenir lui-même sur son lien secret. C'est le plus gros manque d'un lien « sérieux ».
   - L'accroche existe déjà : `agenda_bookings.mail_state` (`to_send` / `sent` / `failed`), `to_confirm` et
     `agenda_settings.double_opt_in`.
   - À faire :
     - un envoyeur côté serveur (app/, file d'attente lue par pg_cron ou par le serveur) ;
     - une adresse d'envoi sur le futur domaine `vendrediparty.ch`, construite depuis `PARTY_PUBLIC_URL` ;
     - des modèles sans texte libre de l'inconnu ;
     - le double opt-in allumé dès que l'e-mail part : on confirme l'adresse avant tout autre envoi.
   - Effort L : domaine, SPF/DKIM/DMARC, prestataire, tests.
7. **Accepter tout seul (option du lien, éteinte par défaut)**. Google et Calendly confirment d'office ; Microsoft aussi.
   - Colonne `auto_accept boolean default false`.
   - `agenda_booking_request` appelle alors la même suite que `agenda_booking_decide(id, true)` : rendez-vous dans
     « Juste pour moi », notification « Nouveau rendez-vous ».
   - Les garde-fous restent les mêmes : 3 demandes par heure et par IP, 20 par jour et par lien, filtre, blocage.
   - Ajouter un plafond propre à ce mode (par exemple `max_per_day` obligatoire).
   - L'inconnu voit « Confirmé » tout de suite.

> Pourquoi pas plus de P1 ? Le reste de la page publique tient déjà : plusieurs plages par jour, fuseau du visiteur, vérification
> de plusieurs calendriers, champs à la carte, annulation par l'inconnu, .ics, signalement. Voir le tableau.

---

## 2. Tableau complet

### 2.1 Liens de dispo et prise de rendez-vous (Google, Calendly, Microsoft)

| # | Fonction | Référence (source) | Notre Agenda aujourd'hui | Prio | Effort |
|---|---|---|---|---|---|
| B1 | Marge avant / après chaque rendez-vous | Calendly avant et/ou après, autour des agendas reliés aussi [C-buf]. Microsoft pré / post [MS-graph]. Google : une seule marge « entre rendez-vous » [G-av] | **Partiel** : en cours, M3 + LE (non commité). Effet réel par pas de 30 min (§1.1) | P1 | S |
| B2 | Délai de prévenance minimal | Google 4 h par défaut [G-av]. Calendly [C-av]. Microsoft en heures [MS-pol] | **Partiel** : fixé à « dès demain et ≥ 12 h » (M1 `agenda_link_windows`). Choix de vie privée voulu, non réglable | P2 (rendre réglable **vers le haut** : 24 h, 48 h, 1 semaine) | S |
| B3 | Horizon (jusqu'à quand) | Google « maximum time in advance » [G-av]. Calendly : jours glissants, entre deux dates, ou sans fin [C-av]. Microsoft jusqu'à 365 jours et plus [MS-pol] | **Partiel** : 14 jours, 4 semaines ou 60 jours (LE `HORIZONS`, M1 entre 7 et 60). Pas de « entre deux dates » | P2 (dates de début et de fin du lien) ; au-delà de 60 jours : P3 (règle de conformité) | S |
| B4 | Rendez-vous maximum par jour (semaine, mois) | Google par jour [G-av]. Calendly jour / semaine / mois, par type ou pour tout le compte [C-lim] | **Non** | P1 | S |
| B5 | Pas des créneaux (heures de début) | Microsoft de 5 min à 4 h [MS-pol]. Calendly « Start time increments » [C-av] | **Non** : pas = durée (M2 `agenda_link_free`) | P1 | S/M |
| B6 | Plusieurs durées au choix de l'invité | Calendly : jusqu'à 4 durées, offres payantes [C-dur] | **Non** : une durée par lien, 30 / 60 / 90 / 120 min (LE `DURATIONS`). Contournement : un lien par durée | P2 | M |
| B7 | Durée libre (autre que 30 à 120 min) | Google : durée sur mesure [G-cr] | **Partiel** : la base accepte 30 à 240 min par 30 (M1). L'écran propose 4 valeurs | P3 | S |
| B8 | Plages par jour de la semaine | Google « Weekly hours » [G-cr] | **Oui** : `rules` (M1 `agenda_rules_ok`) et modèles (LE) | — | — |
| B9 | Plusieurs plages le même jour | Google « Add another time period » [G-cr] | **Oui** : jusqu'à 7 règles (« + Ajouter une plage », LE) | — | — |
| B10 | Copier les heures d'un jour sur tous | Google « Copy to all days » [G-cr] | **Partiel** : une règle couvre plusieurs jours, sans bouton « copier » | P3 | S |
| B11 | Dates à part : fermé, ou autres heures (vacances) | Google « Adjusted availability » [G-cr][G-av]. Calendly « date-specific hours » | **Non** (contournement : rendez-vous « Pris ») | P1 | M |
| B12 | Vérifier plusieurs agendas (conflits) | Google « Check calendars for availability » [G-cr]. Calendly : calendriers à vérifier [C-av] | **Oui** : chaque lien choisit ses calendriers (soirées Party, Juste pour moi, .ics, iPhone) (M2 `calendars`, LE) | — | — |
| B13 | Peut-être / provisoire ne bloque pas | Google : événements non acceptés ou provisoires ignorés [G-av] | **Partiel** : l'iPhone compte tout sauf « libre » (iOS `AgendaBusy.counts`). Soirées : Présent et Peut-être (M1 `agenda_party_spans`) | P2 (case « les Peut-être me gardent libre ») | S |
| B14 | Fuseau de l'invité | Calendly détecte les deux fuseaux, ou verrouille [C-av]. Google : fuseau du planning [G-cr] | **Oui** : heure de Suisse + fuseau de l'appareil + liste (PUB, l. 250-343) | — | — |
| B15 | Durée de vie du lien : date de début, fin, sans fin | Google : dates de début et de fin du planning [G-av]. Calendly « indefinitely » [C-av] | **Oui** : 90 jours, Prolonger, permanent (M2 `expires_at` null), Arrêter / Rallumer | — | — |
| B16 | Plusieurs liens (types de rendez-vous) | Calendly : types d'événements. Microsoft : types de réunion [MS-me] | **Oui** : 10 liens au plus (M1 `links_max`) | — | — |
| B17 | Lien secret / caché d'une page publique | Calendly « Make secret » [C-av]. Microsoft : type privé [MS-me] | **Oui de fait** : chaque lien est un jeton de 144 bits, sans page d'index | — | — |
| B18 | Lien à usage unique | Microsoft : lien unique pour un type privé, expiré après une réservation [MS-me] | **Non** | P2 | S |
| B19 | Formulaire : prénom, nom, e-mail | Google : prénom, nom et e-mail obligatoires [G-cr] | **Oui** : chaque champ est non demandé, facultatif ou obligatoire. Prénom toujours (M1, LE) | — | — |
| B20 | Questions personnalisées | Google : champs en plus [G-cr]. Calendly [C-q]. Microsoft [MS-me] | **Partiel** : un message libre avec son intitulé (`message_label`). Pas de question à choix | P2 (1 à 3 questions courtes, à choix, filtrées) | M |
| B21 | Vérifier l'e-mail (code / double opt-in) | Google : code pour les personnes sans compte Google [G-cr] | **Partiel** : accroche `to_confirm` / `double_opt_in`, éteinte. Pas d'e-mail en v1 | P1 (avec B23) | dans B23 |
| B22 | Confirmation automatique ou manuelle | Google et Calendly : automatique. Microsoft : idem (notif. au propriétaire) [MS-pol] | **Partiel** : toujours manuelle, 48 h, puis le créneau se libère (M1) | P1 (option `auto_accept`) | S/M |
| B23 | E-mail de confirmation et rappels à l'invité | Google : jusqu'à 5 rappels [G-cr]. Calendly : liens d'annulation et de report dans les e-mails [C-cxl] | **Non** : lien de suivi secret `/d/r/<secret>` et .ics seulement (PUB). Accroche `mail_state` | P1 | L |
| B24 | Notification au propriétaire | Microsoft : e-mail à chaque création ou changement [MS-pol] | **Oui** : push `booking_request` / `booking_cancelled`, interrupteur, pastille, temps réel (M1) | — | — |
| B25 | Annulation par l'invité | Google : lien dans l'e-mail [G-cxl]. Calendly [C-cxl] | **Oui** : « Annuler » + « Effacer mes données » sur `/d/r/<secret>` (PUB) | — | — |
| B26 | Report (changer d'heure) par l'invité | Calendly : lien « Reschedule » [C-cxl]. Microsoft : délai d'annulation / report [MS-pol] | **Non** : il faut annuler, puis redemander | P2 | M |
| B27 | Délai limite pour annuler ou reporter | Microsoft : même délai minimal pour réserver et annuler [MS-pol]. Calendly : politique affichée, non imposée [C-pol] | **Non** | P3 | S |
| B28 | Annulation par le propriétaire, avec motif | Google « Cancel appointment » [G-cxl] | **Partiel** : `agenda_booking_owner_cancel`, sans message à l'inconnu (il le voit sur son lien) | P2 (motif choisi dans une liste, sans texte libre) | S |
| B29 | Proposer une autre heure à l'invité | Microsoft / Outlook : contre-proposition | **Non** | P3 | M |
| B30 | Lieu : sur place, téléphone, visio, à préciser | Google : Meet, sur place, téléphone, aucun [G-cr]. Microsoft : Teams activé par défaut [MS-me] | **Non** : aucun lieu sur le lien ni dans le .ics | P1 | S/M |
| B31 | Description / consignes du rendez-vous | Google : description sur la page et dans l'e-mail [G-cr] | **Partiel** : nom affiché, intitulé du message. Pas de description | P2 (200 caractères, filtrés, sans lien) | S |
| B32 | Photo / nom de l'hôte | Google : photo et nom du compte [G-cr] | **Partiel** : nom affiché filtré (`display_name`), sans photo (choix de vie privée) | P3 | S |
| B33 | Invités en plus (l'invité ajoute des gens) | Google « Guest permissions » [G-cr] | **Non** | P3 | M |
| B34 | Co-hôtes / disponibilité de plusieurs personnes | Google : co-hôtes du domaine [G-cr]. Calendly : rendez-vous à plusieurs | **Non** sur les liens. « Qui est libre ? » existe pour les groupes (M1 `agenda_group_free`) | P3 | L |
| B35 | Paiement à la réservation | Google : Stripe [G-cr]. Calendly : paiement | **Non** | P3 (déconseillé, §3) | — |
| B36 | Page de confirmation / redirection | Calendly : redirection après réservation | **Partiel** : page de suivi propre (PUB `status_page`), sans redirection | P3 (déconseillé : redirection = lien externe) | — |
| B37 | Ajouter à son agenda (.ics) | Les trois | **Oui** : `/d/r/<secret>/rendez-vous.ics` (PUB) | — | — |
| B38 | Anti-abus | Google : vérification par e-mail. Calendly : rien de visible | **Oui** : 3 demandes / h / IP hachée, 20 / jour, 5 en attente, 1 par e-mail ou téléphone, piège + 3 s, filtre, Signaler, Bloquer (M1) | — | — |
| B39 | Statistiques du lien | Calendly : analyses | **Partiel** : nombre de vues et dernière vue, pour le propriétaire seul (M1) | P3 | S |
| B40 | Aperçu de la page avant partage | Calendly : aperçu | **Oui** : `agenda_link_preview`, aperçu dans LE | — | — |
| B41 | Partage : copier, partager, QR, intégrer à un site | Calendly : lien, widget intégré | **Partiel** : Copier, Partager, QR (LE). Pas d'intégration (iframe) | P3 | S |
| B42 | Mode « dispos seulement » (sans réservation) | Absent chez Google et Calendly. Proche du partage libre / occupé d'Exchange | **Oui** : demandes éteintes par défaut, grille + liste texte (PUB) | — | — |
| B43 | Rendez-vous le jour même | Les trois l'acceptent (délai réglable) | **Non, voulu** : « rien le jour même » (CLAUDE.md) | P3 (garder) | — |

### 2.2 Vues (iCal)

| # | Fonction | iCal (source) | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| V1 | Jour | iPhone et Mac [A-view] | **Oui** : avec les trous « Libre · 1 h + Ajouter » (V) | — | — |
| V2 | Semaine | [A-view] | **Oui** : jours empilés (V) | — | — |
| V3 | Mois (compact, empilé, détails) | iOS 18 et plus [A-view] | **Partiel** : un seul mode (V) | P3 | S |
| V4 | Année / carte de densité (Mac) | [A-mac] | **Non** | P3 | M |
| V5 | Liste des événements à venir | [A-view] | **Partiel** : semaine empilée, sans liste continue | P2 | S |
| V6 | Multi-jours / Planificateur (iPad, Mac) | [A-view] | **Non** | P3 | M |
| V7 | Bouton « Aujourd'hui » | [A-view] | **Oui** (index.tsx) | — | — |
| V8 | Ligne de l'heure actuelle | [A-view] | **Oui** (V) | — | — |
| V9 | Numéros de semaine | Réglage [A-set] | **Oui** : `prefs.week_numbers` | — | — |
| V10 | Premier jour de la semaine | [A-set] | **Partiel** : lundi fixe (heure de Suisse) | P3 | S |
| V11 | Pincer pour zoomer les heures | [A-view] | **Non** | P3 | M |
| V12 | Afficher / masquer les refus | [A-set] | **Oui** : `prefs.show_declined`, `show_polls` | — | — |
| V13 | Calendriers chinois, hébreu, hijri | [A-set] | **Non** | P3 | — |
| V14 | Fiche superposée (iOS 27) | [A-27] | **Oui de fait** : écrans / feuilles Party | — | — |
| V15 | Mini-mois de navigation (Mac) | [A-mac] | **Non** | P3 | S |

### 2.3 Créer et modifier un rendez-vous (iCal)

| # | Fonction | iCal (source) | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| C1 | Création rapide | [A-ev] | **Oui** : titre, jour, heures ; « Plus d'options » (IT) | — | — |
| C2 | Créer en touchant ou en glissant un créneau | [A-ev] | **Partiel** : « + Ajouter » dans un trou de la vue Jour ; pas de glisser | P2 | M |
| C3 | Glisser pour déplacer, poignées pour la durée | « touch and hold, then drag » [A-ev] | **Non** | P2 | M/L |
| C4 | Copier / coller / dupliquer | [A-ev] | **Non** | P2 | S |
| C5 | Journée entière | [A-ev] | **Oui** : `all_day` (M1, IT) | — | — |
| C6 | Plusieurs jours | [A-ev] | **Partiel** : la base l'accepte ; l'écran est à vérifier sur plusieurs jours | P2 | S |
| C7 | Lieu (suggestions de Plans) | [A-ev] | **Partiel** : texte libre, sans suggestion ni carte | P3 | M |
| C8 | Lien FaceTime / visio | [A-ev] | **Non** | P3 | S |
| C9 | Occupé / Libre | iOS 27 l'ouvre à iCloud [A-27] | **Oui** : `busy` (M1, IT) | — | — |
| C10 | Événement privé (détails cachés) | Exchange | **Oui de fait** : rien ne quitte le propriétaire, sauf « pris » | — | — |
| C11 | Changer de calendrier | [A-ev] | **Oui** : `calendar_id` | — | — |
| C12 | Notes | [A-ev] | **Oui** : `notes`, 2000 caractères | — | — |
| C13 | URL | [A-ev] | **Non** | P3 | S |
| C14 | Pièces jointes | « Add attachment » [A-ev] | **Non** | P3 (déconseillé, §3) | — |
| C15 | Invités sur un rendez-vous personnel | [A-inv] | **Non, voulu** : renvoi vers « En faire une soirée Party » (IT l. 219) | P3 | — |
| C16 | Temps de trajet (bloque avant) | [A-ev] | **Non** | P2 (pour les dispos, B1 couvre l'essentiel) | M |
| C17 | Fuseau par événement / heure flottante | [A-tz] | **Non** : tout en `Europe/Zurich` | P3 | M |
| C18 | Durée par défaut | Réglage [A-set] | **Non** | P3 | S |
| C19 | Calendrier par défaut | [A-set] | **Partiel** : « Juste pour moi » par défaut (M1 `agenda_builtin`) | P3 | S |
| C20 | Annuler / rétablir | [A-ev] | **Non** | P3 | M |
| C21 | Langage naturel / IA | iOS 27 [A-27] | **Non** dans l'Agenda (oui pour les soirées) | P3 | M |
| C22 | Ajouter depuis une capture / une affiche | iOS 26-27 [A-26] | **Non** | P3 | — |
| C23 | Écrire dans le calendrier de l'iPhone | EventKit | **Oui**, avec accord à chaque fois : `EKEventEditViewController` (iOS `AgendaBridge`) | — | — |

### 2.4 Répétitions (iCal)

| # | Fonction | iCal | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| R1 | Chaque jour, semaine, 2 semaines, mois, année | [A-ev] | **Oui** : `repeat` (M1) | — | — |
| R2 | Personnalisée : tous les N, jours choisis, « 1er vendredi », « dernier » | iCal « Personnaliser » | **Non** | P2 | M |
| R3 | Fin : à une date / après N fois | iCal | **Partiel** : `repeat_until` en base ; l'écran web ne le propose pas (aucun usage dans app/agenda) | P2 | S |
| R4 | Supprimer « celui-ci » / « celui-ci et les suivants » | iCal | **Oui** : `agenda_item_delete` all / one / following (IT l. 116) | — | — |
| R5 | Modifier une seule date de la série | iCal | **Non** : la modification change toute la série | P2 | M |
| R6 | Lire les exceptions des .ics (EXDATE, RECURRENCE-ID) | iCal | **Partiel** : à vérifier dans app/agenda_ics.py | P2 | S |

### 2.5 Alertes (iCal)

| # | Fonction | iCal | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| A1 | Alerte par rendez-vous | [A-ev] | **Partiel** : `alert_minutes` enregistré (IT `ALERTS`), **mais aucune tâche ne l'envoie** (aucun envoyeur trouvé dans app/ ni dans les migrations) | P2 (à faire, ou à cacher : un réglage sans effet trompe) | M |
| A2 | Deux alertes (iPhone), plusieurs (Mac) | [A-set] | **Non** | P3 | S |
| A3 | Alertes par défaut | [A-set] | **Non** | P3 | S |
| A4 | Heure de départ (trafic) | [A-set] | **Non** | P3 | — |
| A5 | Un interrupteur par type de notification | [A-set] | **Oui** : `notification_prefs.booking_requests` | — | — |

### 2.6 Calendriers, comptes, abonnements, partage (iCal)

| # | Fonction | iCal | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| K1 | Plusieurs calendriers, nom et couleur | [A-cal] | **Oui** : `agenda_calendars` (8 couleurs) | — | — |
| K2 | Afficher / masquer | [A-cal] | **Oui** : `visible` ; iPhone « Voir ici » | — | — |
| K3 | Comptes iCloud / Google / Exchange réunis | [A-cal] | **Partiel** : iPhone par EventKit (tous les comptes de l'appareil) ; web par .ics privé | P2 (Google « free/busy » par OAuth, §3) | L |
| K4 | S'abonner à un .ics | [A-cal] | **Oui** : agendas .ics lus par le serveur pour leur seul propriétaire (`/api/account/agenda/ics`) | — | — |
| K5 | Se désabonner et signaler | [A-cal] | **Partiel** : retirer un calendrier ; pas de signalement (inutile : c'est sa propre adresse) | P3 | — |
| K6 | Partager un calendrier avec des personnes | iCloud [A-share] | **Partiel** : partage **libre / occupé** groupe par groupe (`agenda_set_sharing`), jamais le détail | P3 (le détail, §3) | — |
| K7 | Calendrier public | iCloud [A-share] | **Partiel** : liens de dispo publics ; flux « Vendredi Party » des soirées | — | — |
| K8 | Fréquence d'actualisation | [A-set] | **Partiel** : l'iPhone envoie ses plages à l'ouverture de l'app (`appBecameActive`). Le web les envoie à l'ouverture de l'Agenda | P2 (« à jour il y a… » sur chaque lien ; tâche de fond iOS si possible) | M |
| K9 | Calendrier des jours fériés | [A-hol] | **Non** | P2 (fériés suisses et cantonaux, pour « Dates à part ») | S |
| K10 | Anniversaires | [A-set] | **Non** | P3 (nouvelle donnée personnelle) | — |
| K11 | Importer / exporter un .ics | [A-cal] | **Partiel** : .ics par rendez-vous de lien ; pas d'export global | P3 | S |
| K12 | Rappels (to-do) dans le calendrier | iOS 18 et plus [A-rem] | **Non** | P3 | M |

### 2.7 Disponibilités (iCal Mac, Exchange, Google)

| # | Fonction | Référence | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| D1 | Fenêtre « Disponibilités » d'un groupe | Mac, CalDAV / Exchange [A-mac] | **Oui** : « Qui est libre ? » (`agenda_group_free`, free.tsx) | — | — |
| D2 | « Prochain horaire disponible » | Mac | **Oui** : « Le mieux » dès 3 qui partagent (`rankDays`) | — | — |
| D3 | Heures de travail / « jamais libre » | Google, Outlook | **Partiel** : les plages du lien jouent ce rôle pour un lien ; rien pour « Qui est libre ? » | P2 | M |
| D4 | Niveaux de partage (dispo seule, + titre, tout) | Exchange, Google | **Oui** (dispo seule), **voulu** | — | — |

### 2.8 Recherche, widgets, Siri, montre, accessibilité, réglages

| # | Fonction | iCal | Notre Agenda | Prio | Effort |
|---|---|---|---|---|---|
| S1 | Rechercher dans l'agenda | [A-search] | **Non** | P2 | S/M |
| S2 | Spotlight | iPhone | **Non** | P3 | M |
| W1 | Widgets (à suivre, liste, mois) | [A-27] | **Non** | P3 (règle CLAUDE.md : aucun texte libre non modéré dans un widget) | M |
| SI1 | Siri / Raccourcis | iPhone | **Non** | P3 | M |
| AW1 | Apple Watch | watchOS | **Non** (les actions de notification suffisent) | P3 | — |
| AC1 | VoiceOver, texte dynamique, pas seulement la couleur | iOS | **Oui** : « Disponible / Occupé » en mots + rayures ; libellés (V, free.tsx). Page publique : liste texte | — | — |
| AC2 | Raccourcis clavier (Mac) | macOS | **Non** | P3 | S |
| RG1 | Imprimer | Mac | **Non** | P3 | — |
| RG2 | iCloud.com (web) | [A-web] | **Oui** : Agenda web + iPhone | — | — |
| RG3 | Forcer un fuseau d'affichage | [A-tz] | **Non** (heure de Suisse partout) | P3 | M |

**Compte** : 118 lignes. 43 pour les liens et rendez-vous, 75 pour iCal. Elles résument les 122 fonctions de
`fonctions-calendrier.md` et les fonctions des trois outils de rendez-vous.

| | Oui | Partiel | Non |
|---|---|---|---|
| Liens / rendez-vous (43) | 14 | 15 | 14 |
| iCal (75) | 25 | 17 | 33 |

P1 manquants ou partiels : **7**, ceux du §1 (B1, B4, B5, B11, B30, B23 avec B21, B22).

---

## 3. Impossible ou déconseillé chez nous, et pourquoi

- **Écrire dans les calendriers de l'iPhone sans accord.** Ce n'est jamais automatique : on passe toujours par
  `EKEventEditViewController`, et la personne touche « Ajouter ». Un rendez-vous accepté va dans « Juste pour moi » (Party), pas
  dans l'iPhone d'office. Raisons : App Store 5.1.1 et 5.1.2 (usage décrit à l'accès), et la phrase d'accès aux calendriers doit
  dire exactement ce qu'on fait.
- **Envoyer le détail des rendez-vous de l'iPhone** (titre, lieu, notes, invités, nom du calendrier). C'est interdit par notre
  modèle : seules des plages « pris » arrondies à 30 minutes, sur 60 jours, quittent l'iPhone (iOS `AgendaBusy`). Une marge, un
  maximum par jour ou un pas de 15 minutes se calculent **sur le serveur**, à partir de ces plages. Ils ne demandent rien de plus
  à l'iPhone. Un pas de 15 minutes ne doit **pas** affiner l'arrondi des plages de l'iPhone.
- **Synchronisation en arrière-plan garantie.** iOS ne garantit pas de tâche de fond régulière. Les plages de l'iPhone datent de
  la dernière ouverture de Party. On ne peut pas promettre « toujours à jour » : il faut afficher la fraîcheur.
- **Partager le détail d'un agenda avec un groupe** (iCloud « Partager le calendrier »). C'est déconseillé : l'accord est donné
  pour « Disponible / Occupé » seulement (Planet49, données sensibles par leurs habitudes : santé, religion).
- **Rendez-vous le jour même, horizon au-delà de 60 jours.** Ce sont des décisions de conformité (spec.md). On peut rendre le
  délai réglable **vers le haut** seulement.
- **Paiement à la réservation** (Google Stripe, Calendly). C'est déconseillé : CLAUDE.md « Paiement » (les organisateurs n'ont
  jamais de « payé » sur parole), App Store 3.1 et 3.2 (achat dans l'app), statut DSA. Ce serait une nouvelle revue complète.
- **Pièces jointes et URL libres sur la page publique.** Contenu d'inconnus à modérer. La page n'a ni ressource externe ni lien
  (CSP nonce). La redirection après réservation fait sortir vers un site inconnu.
- **SMS ou appel à l'inconnu.** C'est exclu par décision (CLAUDE.md : « jamais de SMS, d'appel ni de rapprochement avec un compte
  Party »).
- **Google « free/busy » par OAuth.** C'est possible mais lourd : Google vérifie l'app pour un droit sensible (des semaines).
  À garder pour plus tard.
- **Widgets, Siri, montre avec des titres de rendez-vous.** Ce n'est possible que par l'app iPhone native, pas par le web. Les
  titres de « Juste pour moi » sont du texte libre du membre : visibles par lui seul, ils passent dans un widget sans risque.
  Les noms d'inconnus (« Rendez-vous · Prénom N. »), eux, ne doivent pas aller dans un widget sans filtre.
- **Co-hôtes / rendez-vous à plusieurs hôtes.** Il faudrait croiser les plages « pris » de plusieurs membres pour un inconnu.
  C'est une nouvelle exposition, à faire seulement avec l'accord de chacun : P3.

---

## 4. Conformité touchée par chaque P1

| P1 | RGPD / vie privée | App Store / Play | Autres règles du projet |
|---|---|---|---|
| Marges (B1) | Rien de nouveau : calcul sur le serveur à partir des plages arrondies. Attention : une marge **révèle un peu plus** l'agenda (un trou plus large autour de chaque rendez-vous), sans titre | Rien | Migration additive (M3) ; test réel `test_agenda_live.py` (déjà modifié, non commité) |
| Maximum par jour (B4) | Rien de nouveau. Un jour « complet » ne doit pas dire **pourquoi** à l'inconnu : on retire les créneaux, sans « complet » | Rien | Contrôle refait sous verrou dans `agenda_booking_request` |
| Pas des créneaux (B5) | Ne pas affiner l'arrondi des plages de l'iPhone : 30 minutes en partage | Rien | La grille de 15 minutes est propre au lien |
| Dates à part (B11) | Une date « fermée » se voit comme une absence de créneaux, sans motif. Pas de texte « vacances » affiché | Rien | Fériés : source publique (K9), sans donnée personnelle |
| Lieu (B30) | L'adresse exacte du membre est une donnée personnelle. Elle n'apparaît **qu'après acceptation**, sur le lien secret. Mettre à jour la notice sous le formulaire et privacy.tsx | Contenu publié par le membre : filtre (`moderate_text`), « Signaler cette page » couvre le lieu, CGU | Lien de visio : https seulement, aucun aperçu chargé (CSP) |
| E-mails à l'inconnu (B23 + B21) | Nouveau traitement : base légale (exécution de la demande), double opt-in, prestataire d'envoi (sous-traitant, accord de traitement, pays), durée de conservation (effacé avec la demande), lien « Effacer mes données » dans chaque e-mail. Aucun e-mail marketing. UE : information DSA / RGPD dans la politique | App Privacy et Data safety : « adresse e-mail », collectée pour le fonctionnement de l'app, pas de suivi. Notes de revue | Adresse d'envoi depuis `PARTY_PUBLIC_URL` (domaine vendrediparty.ch), jamais en dur ; aucun texte libre de l'inconnu dans les e-mails (anti-hameçonnage) |
| Accepter tout seul (B22) | Le nom de l'inconnu entre seul dans l'agenda du membre : notice à l'inconnu (« votre prénom et l'initiale de votre nom figureront dans son agenda »). Effacement à 30 jours inchangé | Contenu d'inconnus qui entre sans contrôle : le filtre, Signaler et Bloquer doivent rester sur le rendez-vous accepté. Garder la limite par jour obligatoire | Éteint par défaut ; interrupteur de notification « Nouveau rendez-vous » |

Avant toute mise en prod de ces P1 : passer l'agent « Exigence Apple » sur la page publique, les e-mails et l'acceptation
automatique, puis faire la recette réelle (règle de l'admin du 06.11).

---

## Sources

- [G-cr] Google, créer un agenda de rendez-vous : https://support.google.com/calendar/answer/10729749
- [G-av] Google, modifier ses disponibilités (fenêtre, dates à part, marge, maximum par jour) : https://support.google.com/calendar/answer/11423292
- [G-cxl] Google, annuler un rendez-vous : https://support.google.com/calendar/answer/10737245
- [C-buf] Calendly, marges : https://calendly.com/help/how-to-use-buffers
- [C-av] Calendly, réglages de disponibilité (plage de dates, délai minimal, pas, fuseaux, lien secret) : https://calendly.com/help/how-to-fine-tune-your-availability-settings
- [C-lim] Calendly, limites de réunions : https://calendly.com/help/how-to-set-meeting-limits
- [C-dur] Calendly, plusieurs durées : https://calendly.com/help/how-to-set-up-multiple-durations-for-an-event-type
- [C-cxl] Calendly, liens d'annulation et de report : https://calendly.com/help/how-to-include-cancel-and-reschedule-links-for-invitees
- [C-pol] Calendly, politique d'annulation (affichée, non imposée) : https://calendly.com/help/how-to-add-a-cancellation-policy
- [C-q] Calendly, questions personnalisées : https://calendly.com/blog/guide-calendly-custom-questions
- [MS-pol] Microsoft Bookings, règles de planification (pas, délai minimal, jours à l'avance, notifications) : https://learn.microsoft.com/en-us/microsoft-365/bookings/set-scheduling-policies
- [MS-graph] Microsoft Bookings, règles (pré / post-marge) : https://learn.microsoft.com/en-us/graph/bookingsbusiness-business-rules
- [MS-me] Bookings with me (types publics / privés, lien à usage unique, Teams) : https://support.microsoft.com/office/bookings-with-me-setup-and-sharing-ad2e28c4-4abd-45c7-9439-27a789d254a2 ; guide universitaire : https://saultcollege.teamdynamix.com/TDClient/53/Portal/KB/ArticleDet?ID=9603
- [A-ev] Apple, créer et modifier des événements (iPhone) : https://support.apple.com/guide/iphone/create-and-edit-events-in-calendar-iph3d110f84/ios
- [A-view], [A-set], [A-cal], [A-inv], [A-tz], [A-hol], [A-share], [A-search], [A-rem] : guide Calendrier de l'iPhone, https://support.apple.com/guide/iphone/use-multiple-calendars-iph3d1110d4/ios et ses pages voisines (vues, réglages, fuseaux, jours fériés, partage, recherche, rappels)
- [A-mac] Guide Calendrier pour Mac (Disponibilités, vue Année) : https://support.apple.com/guide/calendar/welcome/mac
- [A-26] iOS 26, ajouter depuis une capture : https://9to5mac.com/2025/10/21/ios-26-gives-apples-calendar-app-a-convenient-new-advantage/
- [A-27] iOS 27, nouveautés de Calendrier (Occupé / Libre iCloud, widgets, fiches) : https://9to5mac.com/2026/09/23/heres-everything-new-for-apple-calendar-in-ios-27/
- Pas de page de rendez-vous chez Apple : https://cal.com/blog/apple-calendar-a-complete-guide (non daté) ; aucune annonce d'Apple pour iOS 27 trouvée.
- [A-web] iCloud.com Calendrier : rappelé dans fonctions-calendrier.md.

Non vérifié sur une page officielle :
- les valeurs par défaut du délai minimal de Microsoft (1 h ou 1 jour selon les guides) ;
- le report d'un rendez-vous par l'invité chez Google ;
- la marge unique de Google, qui n'a pas de réglage avant / après séparé.
