# Questions pour l'admin (27.11) — réponds par numéro quand tu es libre

1. **Texte libre dans les jeux de l'app App Store — DÉCISION QUI BLOQUE L'ENVOI.** Quatre tours de contrôle de suite (6 à 9), un contrôleur qui cherche exprès a toujours trouvé une nouvelle famille qui passe le filtre (une autre langue, une conjugaison, un groupe de personnes, une périphrase). Un filtre de mots ne sera jamais complet, et plus on l'élargit plus il refuse des phrases normales (« Va te tuer à la tâche » était refusé dans les messages). Deux choix :
   - **(a)** on garde le texte libre (prénoms, réponses de Tu me connais ?, du Masque) avec le filtre actuel + « 🚩 Signaler » partout (prénom et réponse, retiré aussitôt pour la table, modération sous 24 h) + exclusion par l'animateur + contact. C'est ce que la règle 1.2 d'Apple demande (filtre, signaler, bloquer, contact). Risque : un examinateur qui tape exprès une phrase haineuse rare la verra passer.
   - **(b)** plus aucun texte libre montré aux autres dans les jeux de l'app : prénom choisi dans une liste ou « Joueur N », réponses choisies parmi des propositions. Seul choix qui résiste à un contrôleur qui cherche exprès ; certains jeux (Tu me connais ?, Le Masque) perdent leur réponse écrite dans l'app (le web garde tout).
   Même limite ailleurs : dans les Discussions, les surnoms et les noms de groupe, le filtre refuse la haine évidente (« Sale juif », « Mort aux arabes », « Hitler »…) mais laisse passer des tournures rares (« Les juifs sont des rats ») ; là, le choix (b) n'existe pas, c'est « Signaler » + blocage + modération sous 24 h.
   Je n'ai pas tranché à ta place.
2. **Phrase de la politique** : « Anthropic (Claude) : outil d'aide à la maintenance utilisé par l'éditeur, avec un accès technique limité. » D'accord pour l'ajouter ?
3. **Compte créé en prod par erreur** par un agent de test (+41 79 000 09 01) : je le supprime ?
4. **« Hard Boat Shotgun »** (lien avec `uhandle` / `utm`) : on le laisse tel quel ou on nettoie le lien ?
5. **« Anniversaire de P-A, Maxou et Boby »** : on le passe en « Sur invitation » ?
6. **Clé `storage_secret_key`** à mettre dans le coffre Supabase de prod (sans elle, photos et vocaux ne sont jamais effacés). Tu la poses toi-même ? (je ne tape jamais de clé)
7. **Dépôt GitHub** : on le passe en privé ?
8. **support@vendrediparty.ch** : tu peux t'envoyer un message test et me dire s'il arrive ? (adresse affichée partout dans l'app)
9. **App Store Connect** (à faire par toi) : cocher les 17 types de données (Search History compris), pas de tvOS, joindre le nouveau PDF, retirer les anciennes captures et la vidéo, mettre les nouvelles captures.
10. **Méninges** : tu relis les 26 débuts de mots retirés (liste dans le rapport du lot 10) ?
11. **« Ok prod »** pour : les **15** fichiers de `supabase/prod/`, dans l'ordre de `checklist-envoi.md` (13 blocage dans le Pot commun, 14 notifications d'un organisateur bloqué + signaler un pot, 15 phrases de haine), le déploiement de develop sur main, send-push et send-web-push. À savoir : l'accord IA passe en version 4, donc **chaque personne qui utilise l'IA devra le réaccepter une fois**. Rien avant ton accord, et rien pendant une revue d'Apple.
12. **Envoi à Apple** : je te montre la réponse en anglais avant tout envoi — tu valides le texte ?
13. **Nouveau compte qui refuse les CGU (« Plus tard »)** : aujourd'hui il garde les Jeux, mais Événements et Discussions restent sur « Faisons connaissance » (le surnom exige les CGU) et ce qu'il avait tapé est perdu en rouvrant l'app. On garde ainsi (simple, accepté par Apple), ou on le laisse REGARDER les événements publics sans CGU (les CGU seulement au premier contenu : répondre, écrire) ? Je garderais le texte tapé dans les deux cas.
14. **Présences, personne avec un compte** : réessaie le ✕ dans l'app (la question « Retirer X des présences ? » doit s'afficher) et dis-moi si ça marche.
15. **Musique pendant la revue** : les notes disent maintenant à Apple « we run one on request » (on lance une soirée Sonos à l'heure qu'Apple choisit et on envoie le code dans la réponse). Tu peux le faire pendant la revue ? Sinon je retire la phrase.
16. **Politique, présences sans compte** : « Elle peut demander à Party de retirer son nom (contact ci-dessous). » D'accord avec cet engagement ?
17. **TestFlight** : j'envoie la nouvelle BETA (copie exacte de la version Apple, onglet Musique par le code) ? Elle part directement sur le lien public « Invités ».
18. **Musique, deux choix** : (a) soirée arrêtée = les invités doivent retaper le code s'ils reviennent ; (b) une pause temporaire d'un invité lui laisse l'onglet (seul un retrait sans limite l'enlève). OK ?
19. **Apple TV BETA** : elle est encore compilée « BETA » (jeux à boire visibles). Elle n'est pas dans la version 1.0.0. On la laisse telle quelle pour l'instant ?
