# Backend événements de Party

Ce dossier reprend les migrations et la fonction `send-push` du projet Vendredi Party,
puis ajoute le canal Web Push de Party. Le projet hébergé est conservé :
`gsuetixzobooggeaubvb`. Ne pas créer une nouvelle base ni réinitialiser celle-ci.

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
déployées séparément. Le site de test utilise les mêmes comptes et données que Party.
Ne jamais publier une annonce de démonstration dans ce projet partagé.

Le bouton **Envoyer une notification d'essai** vise uniquement l'appareil courant,
limite les essais à un par minute et ignore les heures silencieuses pour cet essai
explicitement demandé. Le contrôle réel de réception doit être effectué sur l'appareil.
