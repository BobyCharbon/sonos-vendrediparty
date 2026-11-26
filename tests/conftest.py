import os
import tempfile

# Avant l'import de app.main : données isolées et code admin connu.
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_PIN"] = "9999"
# Discussions testées allumées, comme sur le site de test (en production elles sont absentes : test_discussions_flag.py).
os.environ.setdefault("DISCUSSIONS_ENABLED", "1")
# Compagnon (Zicou) testé allumé, comme sur le site de test (en production il est éteint : tests/test_compagnon_flag.py).
os.environ.setdefault("COMPAGNON_ENABLED", "1")
# Agenda et Pronos testés allumés, comme sur le site de test (gardés en test le 19.11 : tests/test_apps_flag.py).
os.environ.setdefault("AGENDA_ENABLED", "1")
os.environ.setdefault("PRONOS_ENABLED", "1")
# Souvenirs et couverture testés allumés, comme sur le site de test (26.11 : tests/test_apps_flag.py).
os.environ.setdefault("SOUVENIRS_ENABLED", "1")
os.environ.setdefault("COVERS_ENABLED", "1")
# Compte progressivement obligatoire (app/guest_gate.py) : sans limite dans les tests qui ne le testent pas (les
# tests du palier posent leurs réglages eux-mêmes ; en production : 3 parties et 3 titres par défaut).
os.environ.setdefault("GUEST_GAMES_BEFORE_ACCOUNT", "1000")
os.environ.setdefault("GUEST_TRACKS_PER_PARTY", "1000")


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def no_real_sonos_watch():
    """Chaque `with TestClient(main.app)` démarre la boucle watch_sonos, qui cherche les VRAIES enceintes du réseau
    (soco.discover, minuté par time.time()). Un test qui fige time.time (session admin de 30 jours…) la faisait tourner
    sans fin en gardant le verrou de l'état Sonos : la suite restait bloquée (14.11). Les tests ne parlent jamais au
    vrai Sonos : la boucle ne fait rien ici (les tests du Sonos appellent snapshot() eux-mêmes, avec un faux)."""
    from app import main
    main.watch_sonos = lambda: None
    yield
