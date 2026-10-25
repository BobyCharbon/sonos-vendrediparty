# Backend événements de Party

Ce dossier reprend les migrations et la fonction `send-push` du projet Vendredi Party,
puis ajoute le canal Web Push de Party.

## Deux bases (depuis le 25 octobre 2026)

| Base | Projet | Utilisée par |
|---|---|---|
| PRODUCTION | `gsuetixzobooggeaubvb` (VendrediParty, eu-central-2) | party.bobycharbon.ch (image `latest`, branche main) |
| TEST | `ewromqfsmcqsthftyhzm` (Vendrediparty-test, eu-west-1) | partytest.bobycharbon.ch (image `develop`) |

- `migrations/` = l'historique exact de la prod (`supabase_migrations.schema_migrations`, recopié le
  25.10.2026) + les migrations écrites ensuite. Le rejouer sur une base vide recrée la prod à l'identique :
  vérifié avec `tools/fingerprint.sql` (740 éléments : colonnes, fonctions, règles RLS, déclencheurs,
  droits, tâches planifiées, stockage), aucune différence.
- Exception connue : `20261022090000_bring_items_by_members` a été appliquée en prod à la main (hors historique).
- Base de test : après les migrations, `tools/test_db_after_migrations.sql` (adresse des fonctions Edge,
  compte Root de test). Auth → Phone par Twilio Verify (mêmes identifiants que la prod) : Root se connecte
  avec son vrai numéro et un vrai SMS. Numéros de test à code fixe `123456`, sans SMS : 41768163120 (Guest)
  et 41790000001-4 (41790000004 = Admin de test, utilisé par les tests automatiques). Jamais le numéro de
  Root dans les numéros de test : un code fixe sur le compte Root ouvrirait l'admin à quiconque le connaît.
- Fonctions Edge `send-push` et `send-web-push` déployées aussi sur la base de test (25.10.2026) :
  `SUPABASE_ACCESS_TOKEN=… npx supabase functions deploy <nom> --project-ref ewromqfsmcqsthftyhzm --use-api --no-verify-jwt`.
- Nouvelle migration : base de TEST d'abord (`python3 tools/sbq.py test rw < fichier.sql`), tests
  (`supabase/tests` hors ligne, puis `SUPABASE_LIVE_TESTS=1 pytest tests/supabase_live`), puis PROD seulement
  avec l'accord explicite de l'admin. `tools/sbq.py prod` est en lecture seule (refuse `rw`).
- Jeton d'accès : `~/.config/supabase-claude/token` sur le Mac (hors dépôt, expire le 24.11.2026).

## Envoi Web Push

`send-web-push` est une fonction Edge distincte de l'ancien envoi Expo. Le cron
`send-web-push` appelle `private.dispatch_web_push_job()` chaque minute. L'appel est
authentifié par le secret `push_job_secret` déjà conservé dans Supabase Vault ; il
n'est jamais transmis au navigateur.

Les clés VAPID sont générées une seule fois par la fonction Edge. Une insertion atomique
les conserve dans `private.web_push_config`, sans permission de lecture pour les
membres. Seule la clé publique est accessible aux comptes actifs par RPC. Aucun secret
Twilio, VAPID ou `service_role` ne doit apparaître dans le client ou dans Git.

Les trois tables privées ont RLS activé sans politique cliente : c'est un refus par
défaut intentionnel. Seuls les RPC contrôlés y accèdent. Le diagnostic Supabase peut
l'indiquer comme [information RLS sans politique](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

L'inscription d'un appareil vérifie le compte actif, sa session et l'endpoint du service
push autorisé. Les origines admises sont `https://party.bobycharbon.ch` et
`https://partytest.bobycharbon.ch`. Les appareils ne rejouent pas l'historique antérieur
à leur inscription. Un compte désactivé, une session expirée, une préférence modifiée
ou une mise en sourdine annulent les envois devenus inéligibles.

Une livraison est enregistrée pour chaque couple notification/appareil. Les reprises
ont un délai croissant, un maximum de huit tentatives et une réservation contre les
traitements concurrents. Les réponses 404/410 retirent un abonnement expiré. `sent`
signifie **accepté par le service push**, sans garantir l'affichage sur le téléphone.
Un tag stable évite de refaire sonner une notification en cas de reprise ambiguë.

Les annonces sont stockées séparément dans `public.admin_announcements` : lecture pour
les membres actifs, publication uniquement par le RPC contrôlant le rôle admin, aucune
suppression ou désactivation par le destinataire. La purge à 90 jours ne les efface pas.
Une publication identique par le même admin dans les cinq minutes renvoie la première
annonce, pour éviter les doublons après une erreur réseau.

## Déploiement

1. Examiner les migrations par rapport à l'historique distant, sans réappliquer les
   anciens scripts ni les utiliser pour écraser une base existante.
2. Appliquer les nouvelles migrations avec Supabase après revue des droits et RLS.
3. Déployer `send-web-push` avec son `deno.json` et son fichier de verrouillage. Son
   `verify_jwt=false` correspond à l'authentification interne par `x-job-secret` ; une
   requête non authentifiée reçoit 401. Ne pas retirer cette vérification interne.
4. Activer le cron après le déploiement :

```sql
select cron.schedule('send-web-push', '* * * * *', 'select private.dispatch_web_push_job();');
```

Le build Docker met à jour les pages web ; les migrations et fonctions Supabase sont
déployées séparément. L'image `develop` (site de test) pointe sur la base de TEST, l'image
`latest` sur la PRODUCTION : jamais d'annonce ni de donnée de démonstration en production.

Le bouton **Envoyer une notification d'essai** vise uniquement l'appareil courant,
limite les essais à un par minute et ignore les heures silencieuses pour cet essai
explicitement demandé. Le contrôle réel de réception doit être effectué sur l'appareil.
