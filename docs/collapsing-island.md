# L’île qui s’effondre

Jeu WebGL intégré au catalogue de Vendredi Party et aux salles de jeux. La première version propose la survie solo et le chacun-pour-soi à 2–8 joueurs, chacun dans son navigateur. Les équipes ne font pas partie de cette version.

## Jouer

Dans **Jeux**, choisir **Explorer l’île**. Partager le code à quatre chiffres ou le lien d’invitation. L’animateur lance la manche et les suivantes.

- Seul : survivre 90 secondes ; le meilleur temps est conservé dans cette partie.
- À plusieurs : le dernier survivant marque une victoire. Une chute simultanée ou plusieurs survivants après 90 secondes donnent une égalité.
- Mobile : joystick à gauche, saut à droite. Les deux commandes fonctionnent simultanément. Le paysage donne une vue plus large ; le portrait reste utilisable.
- Clavier : flèches, ZQSD ou WASD pour bouger, espace pour sauter. Relâcher entre deux sauts.
- Les plateformes se fissurent et changent de couleur 2,8 secondes avant de tomber. L’ordre varie entre les manches ; les plateformes restantes conservent un chemin connecté jusqu’à la dernière.
- Arriver pendant une manche donne une place pour la suivante. Changer d’application arrête les déplacements mais ne met pas la partie en pause.
- Le menu commun conserve le QR, les joueurs, la modération, la réduction du jeu et les sons.

## Implémentation

`app/island.py` calcule le terrain, les mouvements, les sauts, les chutes et les résultats avec un pas de 1/60 s. Le serveur reçoit des directions normalisées, jamais des positions choisies par le client. Un verrou couvre les actions de partie et les snapshots. Chaque manche fige son effectif et son mode solo/multijoueur.

`POST /api/games/{code}/island` échange les entrées et les snapshots à environ 15 Hz par navigateur. Les identifiants privés des invités ne figurent pas dans les vues publiques. Des commandes vieilles de plus de 400 ms s’arrêtent ; une absence de simulation de plus de 5 s termine la manche sans attribuer de score. Cette simulation à la demande reprend le modèle d’hébergement existant : **un seul processus applicatif**.

`app/static/island.js` gère l’interface, le réseau, les entrées tactiles/clavier, les résultats et la durée de vie de la scène. `island-scene.js` crée les géométries et interpole les positions avec Three.js. Le moteur 0.180.0 est livré localement dans `static/vendor/three/` avec sa licence MIT ; il n’est chargé que lorsqu’on ouvre le jeu. Aucun service de génération ou CDN n’est utilisé pendant une partie.

Les couleurs et fissures d’avertissement restent visibles lorsque la réduction des animations est activée. La limite de densité de pixels et l’herbe instanciée réduisent le coût de rendu. Le panneau du salon est presque opaque pour éviter un défaut de composition WebGL/Chromium en portrait ; ne pas le rendre entièrement opaque sans vérifier le rendu réel.

## Vérification

```sh
# Dépendances navigateur facultatives (à installer une fois)
.venv/bin/python -m pip install -r requirements-island-test.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests/test_island.py -q
.venv/bin/python -m pytest tests/e2e/test_island_game.py -q
.venv/bin/python -m pytest -q -m 'not e2e'
node --test tests/game_audio.test.cjs
```

Les tests ciblés couvrent les sauts, l’atterrissage dans le vide, l’impossibilité du double saut, les entrées périmées, l’objectif solo, les égalités, les points de salle, les arrivées tardives, les permissions et la connectivité du terrain restant. Les tests navigateur passent par les vrais boutons et vérifient le jeu solo, le multijoueur, le multitouch, la reconnexion, le rechargement et la réduction/reprise. Un contrôle des pixels du salon mobile vérifie que le terrain est effectivement affiché.

La maquette approuvée est une référence d’ambiance. Cette version utilise une 3D stylisée plus simple. Les captures de navigateur et les tests sur tailles mobiles ne constituent pas une validation sur un vrai iPhone ou sur un réseau mobile. Aucun déploiement distant n’est effectué par cette modification.
