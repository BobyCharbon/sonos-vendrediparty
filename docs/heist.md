# Braquage en miniature

Dans Jeux, choisir **Préparer le braquage**. L'animateur choisit la Galerie royale, le Cabinet des curiosités ou l'Aile des antiquités, partage le code et lance la manche. Le jeu fonctionne seul ou en coopération à 2–8, avec une limite de quatre minutes.

Joystick ou flèches / ZQSD / WASD pour avancer. Le bouton d'action (espace ou E au clavier) indique ce qui est possible : prendre un trésor, déposer à la sortie verte, couper les lasers quinze secondes ou libérer les amis près de la prison rose. Un seul trésor par personne. Objectif commun : quatre trésors seul, puis un de plus par joueur, jusqu'à huit.

Les gardiens suivent des parcours visibles et détectent dans un cône, bloqué par les murs. Les lasers alternent quatre secondes actives et trois secondes inactives. L'exposition monte dans les zones dangereuses et redescend à couvert. Une capture laisse le trésor sur place : prison en coopération, retour à la sortie et douze secondes perdues en solo. Une équipe entièrement emprisonnée perd. Les victoires sont attribuées à tous les participants encore présents, également dans le classement d'une salle.

## Architecture

`app/heist.py` est l'autorité pour les positions, interactions, patrouilles et résultats, à 30 pas/s. `/api/games/{code}/heist` reçoit uniquement direction et bouton, puis retourne la vue publique. Les identifiants privés ne figurent pas dans ces snapshots. Les entrées périmées s'arrêtent après 400 ms. Une interruption de simulation supérieure à cinq secondes termine la manche sans victoire. Déploiement à un seul processus, comme les jeux temps réel existants.

`heist.js` gère les entrées, connexions, états et le cycle de vie WebGL. `heist-scene.js` utilise le moteur Three.js local déjà livré. Les décors et positions dérivent du même plan que les collisions. Le zoom mobile suit le joueur ; la carte miniature conserve le plan complet. La fermeture ou la réduction libère les ressources graphiques.

## Vérification

```sh
.venv/bin/python -m pytest tests/test_heist.py -q
.venv/bin/python -m pytest tests/e2e/test_heist_game.py -q
```

Les tests navigateur réutilisent `tests/e2e/helpers.py`. Installer au besoin `requirements-island-test.txt` puis `python -m playwright install chromium`. Les tests couvrent déplacement, collecte et dépôt par le vrai clavier, les trois sélections de carte, deux joueurs, commande tactile, arrivées tardives, reconnexion, rechargement et réduction/reprise. Les tests serveur couvrent les trois plans, les patrouilles, le sauvetage, les captures, les scores et permissions. Des tailles mobiles simulées ne constituent pas une mesure de performance sur un vrai téléphone.
