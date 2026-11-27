"""Contrôle Apple, tour 8 (migration 20261127160000, version du lot 15b) sur la VRAIE base de test (jamais la prod) :
phrases de haine sans double sens refusées par la base comme par app/moderation.py (surnom, message de groupe), sans
faux refus (l'incitation au suicide et les tournures à double sens ne valent que pour les joueurs de l'app).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_haine_suicide_live.py -q"""
import json

import httpx

from app import moderation
from tests.supabase_live.test_member_admin_live import TEST_URL, pytestmark  # noqa: F401
from tests.supabase_live.test_moderation_live import people, say, terms_were  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql
from tests.test_store_jeux_tour5 import ACCEPTED_ANSWERS, ACCEPTED_NAMES
from tests.test_moderation_faux_refus import ACCEPTED, NAMES, REFUSED
from tests.test_store_jeux_tour8 import FINE, HATE, SUICIDE

KINDS = ("name", "message")  # la base ne connaît pas « answer » (réponses de jeu : serveur Party seulement)


def test_the_base_gives_exactly_the_python_verdicts():
    """Même motifs lus par PostgreSQL et par Python (lookahead, lookbehind, « ^ » au milieu) : verdict ligne à ligne."""
    corpus = HATE + SUICIDE + FINE + ACCEPTED_NAMES + ACCEPTED_ANSWERS + ACCEPTED + NAMES + REFUSED
    texts = "array[" + ",".join("'" + t.replace("'", "''") + "'" for t in corpus) + "]::text[]"
    rows = sql(f"select t, k, private.moderation_verdict(t, k) v from unnest({texts}) t, "
               f"unnest(array['name', 'message']) k")
    assert len(rows) == len(corpus) * len(KINDS)
    for row in rows:
        v = row["v"] if isinstance(row["v"], dict) else json.loads(row["v"])
        py = moderation.check(row["t"], row["k"])
        assert (v["ok"], v.get("category"), v.get("text", row["t"]) if v["ok"] else None) == \
            (py.ok, py.category, py.text if py.ok else None), (row["t"], row["k"], v, py)


def test_a_hateful_nickname_and_message_are_refused_by_the_base(people):
    admin, a, b, c, group = people
    for bad in ("Sale juive", "Sales arabes", "Négresse", "Hitler", "KKK"):  # surnom : 12 signes au plus
        r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{a.uid}', headers=a.headers, json={'display_name': bad}, timeout=30)
        assert r.status_code == 400 and 'content_refused' in r.json()['message'], (bad, r.text)
    a.set_nickname('Testeur 1')
    for bad in ("Mort aux arabes", "Gazer les juifs", "Vive Daech", "Les juifs à la chambre à gaz"):
        r = say(a, group, bad)
        assert r.status_code == 400 and 'propos haineux' in r.json()['message'], (bad, r.text)
    for ok in ("Je meurs de faim", "J'adore la cuisine arabe", "Va te jeter à l'eau", "Va te tuer à la tâche",
               "Les gays dehors ce soir pour la pride"):  # lot 15b : plus jamais refusées par la base
        r = say(a, group, ok)
        assert r.status_code == 201 and r.json()[0]['body'] == ok, (ok, r.text)
