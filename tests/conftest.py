import os
import tempfile

# Avant l'import de app.main : données isolées et code admin connu.
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_PIN"] = "9999"
# Discussions testées allumées, comme sur le site de test (en production elles sont absentes : test_discussions_flag.py).
os.environ.setdefault("DISCUSSIONS_ENABLED", "1")
# Compagnon (Zicou) testé allumé, comme sur le site de test (en production il est éteint : tests/test_compagnon_flag.py).
os.environ.setdefault("COMPAGNON_ENABLED", "1")
# Compte progressivement obligatoire (app/guest_gate.py) : sans limite dans les tests qui ne le testent pas (les
# tests du palier posent leurs réglages eux-mêmes ; en production : 3 parties et 3 titres par défaut).
os.environ.setdefault("GUEST_GAMES_BEFORE_ACCOUNT", "1000")
os.environ.setdefault("GUEST_TRACKS_PER_PARTY", "1000")
