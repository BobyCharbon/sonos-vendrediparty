import os
import tempfile

# Avant l'import de app.main : données isolées et code admin connu.
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_PIN"] = "9999"
# La section Événements est testée telle qu'elle tourne sur le site de test (en production : « Bientôt »).
os.environ.setdefault("EVENTS_ENABLED", "1")
