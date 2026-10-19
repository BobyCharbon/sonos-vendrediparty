# Néon Knockout

Jeu d’arène intégré au catalogue Vendredi Party, sans dépendance supplémentaire.

## Règles

- Chacun joue sur son téléphone : 2 à 8 joueurs en solo, ou 2 à 4 duos complets. Aucun joueur manuel.
- Joystick gauche pour se déplacer et viser ; maintenir DASH à droite puis relâcher pour frapper. Charge complète en 1,1 s, recharge de 1,15 s. Les deux commandes acceptent des contacts indépendants.
- Les coéquipiers partagent leur couleur et ne se repoussent pas. Un duo reste en jeu tant qu’un membre survit.
- Après un compte à rebours de 3 s, la manche dure au plus 45 s. La plateforme rétrécit à partir de 12 s. Dernier joueur ou duo debout : un point. Une élimination simultanée sans survivant ne donne aucun point.
- Premier à 5 victoires. L’animateur lance chaque manche. Depuis les résultats, il peut préparer un nouveau match et remettre les scores à zéro pour reformer les équipes après un départ.
- Un arrivant en solo attend la manche suivante. Les inscriptions en duo sont fermées pendant le match. Les équipes restent fixées pour le match.
- Au clavier : flèches, ZQSD ou WASD ; espace pour charger. Changer d’application annule la commande ; le personnage reste vulnérable dans l’arène.

## Direction visuelle et accessibilité

L’arène suspendue et ses personnages sont dessinés procéduralement en Canvas 2D : dalle métallique, bordure lumineuse, grille au sol, silhouettes colorées et traînées de dash. Aucun moteur 3D ni asset distant spécifique au jeu.

Cette surface prolonge le site existant : les titres gardent Bricolage Grotesque, le texte hérite de la typographie du site. Le style est limité à `.g-nk` et `.nk-*`. Préserver les propriétés personnalisées des couleurs et des états (`--gc`, `--g-rgb`, `--nk-muted`, `--fighter`, `--charge`) ; conserver la concordance entre les palettes serveur et Canvas lorsque les couleurs changent. Les styles et le rendu contiennent également des couleurs littérales : ils ne constituent pas encore une palette centralisée unique.

Préserver les commandes tactiles larges, le focus visible, les libellés accessibles, les scores textuels et le repère « toi ». La préférence de mouvement réduit désactive particules, traînées et halos ; elle conserve les mouvements indispensables au jeu. Le Canvas ne fournit pas une représentation non visuelle complète des positions.

Les adaptations portrait compact et paysage maintiennent les commandes à portée de pouce. Vérifier les petits écrans après toute modification du HUD ou des règles. Ce jeu ne justifie pas de redéfinir l’identité globale dans PRODUCT.md ou DESIGN.md.

## Simulation et transport

`app/neon.py` porte les règles et la physique autoritaire : le client transmet une direction et un état de charge, jamais une position. Le serveur avance à pas fixes de 1/60 s à la demande des requêtes, sous un verrou partagé avec les actions du lobby. Ce fonctionnement n’est pas une boucle serveur autonome à 60 Hz.

`POST /api/games/{code}/neon` échange commandes et instantanés compacts. `app/static/neon.js` vise environ 15 requêtes/s au premier plan, sans requêtes concurrentes dans sa boucle ; le débit baisse avec la latence. Le Canvas lisse les positions et extrapole au plus 90 ms. Une sauvegarde accompagne les transitions de phase, pas chaque commande ou image.

Les commandes périmées sont annulées après 0,4 s. Un écart d’horloge supérieur à 5 s, ou un recul supérieur à 1 s, termine la manche sans point et demande de la relancer. Une requête expirant après 1,8 s affiche la reconnexion et réinitialise les commandes.

Conserver **un seul processus Uvicorn**, comme dans le Dockerfile : l’état en mémoire et le verrou ne coordonnent pas plusieurs workers. Un déploiement multi-processus demanderait une autre architecture de simulation et de partage d’état.

## Vérification et limites

`tests/test_neon.py` couvre notamment les effectifs, les duos, les commandes normalisées et périmées, la charge, les collisions, les égalités, les cinq victoires, les permissions, les arrivées/départs, l’annulation tactile et l’absence d’accélération quand plusieurs clients interrogent le même instant. À exécuter avec la suite existante lors d’une modification du moteur ou de son intégration.

La validation navigateur de cette livraison comprend quatre contextes Chromium distincts. Elle ne remplace pas un essai sur plusieurs téléphones physiques : multitouch réel, Safari mobile, interruptions système et latence Internet restent à valider en situation de jeu.
