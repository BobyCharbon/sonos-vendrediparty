"""Verrou unique de toutes les parties.

Les requêtes FastAPI tournent en parallèle (pool de fils) et tous les téléphones d'une soirée interrogent le serveur
chaque seconde. Toute lecture-modification d'une partie (action, avancée automatique du quiz, image des jeux en
temps réel) et l'enregistrement sur disque passent par ce verrou ré-entrant : une étape de jeu ne s'applique
qu'une fois (révélation d'une question, donne du Blackjack…). Un seul verrou pour tous les jeux : aucun ordre de
prise à respecter, donc pas d'interblocage possible. Les opérations sont courtes (quelques microsecondes)."""
import threading

LOCK = threading.RLock()
