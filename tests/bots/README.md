# Banc des bots — module Événements (base de TEST uniquement)

15 bots (1 admin, 1 co-admin, 2 organisateurs, 4 Membres VIP, 3 Membres, 2 Guests, 2 « sans l'app ») jouent un
événement complet dans de vrais navigateurs (Playwright, 390×844 tactile, iPhone et Android), contre un serveur Party
local branché sur la base de TEST et réglé comme la prod (`/api/features` de la prod, CGU exigées pendant la campagne).
Chaque bot : vidéo, journal horodaté, captures, erreurs JS et réponses HTTP ≥ 400 dans `$BOTS_OUT/<bot>/`.

**Jamais de vrai membre prévenu** : les bots n'utilisent que les groupes « Bots » / « Bots 2 » (jamais Vendredi Party)
et `quarantine.py` retient, le temps de la campagne, toute notification qu'un bot causerait à un compte qui n'est pas
un bot (signalement → admins, forum → admins, publication publique…).

```sh
W=<dossier de travail> ; export BOTS_OUT=$W/bots BOTS_PORT=8796
.venv/bin/python -m tests.bots.setup_accounts            # numéros à code fixe (sms_test_otp gardé), comptes, groupes
sh tests/bots/build_events.sh $W                          # module de HEAD construit avec l'URL TEST (pas web/events/dist)
.venv/bin/python -m tests.bots.serve $W/src $W/events-dist &   # serveur du banc (sources de HEAD)
.venv/bin/python -c "from tests.bots import quarantine; quarantine.install()"
# CGU exigées pendant la campagne (valeur d'origine notée dans state.json) :
.venv/bin/python -c "from tests.bots.common import sql; from tests.bots.bench import save_state; \
  save_state(terms_enforced_was=sql('select terms_enforced from private.moderation_settings')[0]['terms_enforced'], \
  campaign_started=sql('select now() t')[0]['t']); sql('update private.moderation_settings set terms_enforced = true')"
.venv/bin/python -m tests.bots.run connexion creation_simple creation ia invitations retirer droits_creation \
  reponses sondage_dates forum paiements billets sans_app signaler valider modifier annuler droits page_party droits_matrice
sh tests/bots/ios_run.sh $W http://127.0.0.1:$BOTS_PORT "<session de Bot Olga, littéral JS>"   # app iPhone (Release)
.venv/bin/python -m tests.bots.cleanup                    # événements supprimés, quarantaine retirée, CGU remises
```

- `run.py <phase…> [--only bot,bot]` : chaque phase est relançable seule (identifiants dans `state.json`) ; une étape
  qui échoue devient une anomalie (`anomalies.jsonl`, capture) et la suite continue.
- `rights.py` (phase `droits_matrice`) : rôle personnalisé « Bot rôle test » donné à Bot Violette ; pour chaque droit
  Événements, avec / sans, l'écran ET l'API REST Supabase avec le jeton du bot ; rôles et droits photographiés puis
  remis exactement (`roles-avant.json`, `rights.json`).
- `snapshot.py <bot> <chemin>` : arbre d'accessibilité d'une page vue par un bot (mise au point).
- Défilement : `Phone.finger_scroll` envoie un vrai geste tactile (CDP `synthesizeScrollGesture`) au point donné et
  regarde les conteneurs sous le doigt ; « bloqué » (il restait de quoi défiler) = anomalie 🔴.
