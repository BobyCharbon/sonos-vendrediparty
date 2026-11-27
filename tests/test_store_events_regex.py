"""Contrôle Apple tour 6 : la copie écran de DRINK_RE (web/events/src/lib/storeEvents.ts) répond comme celle du serveur
(app/store_app.py) sur les mots accentués. Le `\\b` de JS ne connaît que l'ASCII : « saké », « bourré » passaient, et
« buée », « barème » étaient pris à tort. La regex TS est exécutée pour de vrai (node) sur le même corpus que Python."""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from app import store_app

pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')
TS = pathlib.Path(__file__).resolve().parents[1] / 'web/events/src/lib/storeEvents.ts'
CORPUS = [
    # Accents au bord d'un mot de la liste : attrapés des deux côtés.
    'Soirée saké', 'Saké !', 'Complètement bourré', 'Bourrée', 'Tournée générale', 'Ivre mort', 'Soirée apéro',
    'Une bière', 'Bières artisanales', 'Rosé de Provence', 'Narguilé', 'Héroïne', 'Gorgée', 'Cuvée 2026', 'Jäger',
    # Mots ordinaires où un accent touche une borne : jamais pris (ni en Python ni à l'écran).
    'La buée sur la vitre', 'Le barème des points', 'Un bois boisé', 'Évapoter', 'Débuté', 'Ébar', 'Verreé',
    'Soirée jeux de société', 'Pique-nique au bord du lac', 'Rendez-vous au parc', 'Publication', 'Gâteau d’anniversaire',
    # Mots simples, pour le reste de la liste.
    'Un shot', 'Soirée vin', 'Au bar', 'Happy hour', 'On vapote', 'Soirée IPA', 'Un joint', 'Bu ensemble', 'Boire un verre',
]


def ts_results(texts):
    src = TS.read_text(encoding='utf-8')
    start = src.index('export const DRINK_RE = ')
    end = src.index('\n);\n', start) + 3
    script = src[start:end].replace('export const', 'const') + f'\nconsole.log(JSON.stringify({json.dumps(texts)}.map((t) => DRINK_RE.test(t))));'
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script], capture_output=True, text=True,
                         timeout=30, check=True)
    return json.loads(out.stdout)


def test_the_screen_filter_answers_like_the_server_on_accented_words():
    py = [bool(store_app.DRINK_RE.search(t)) for t in CORPUS]
    assert dict(zip(CORPUS, ts_results(CORPUS))) == dict(zip(CORPUS, py))
    assert py[CORPUS.index('Soirée saké')] and py[CORPUS.index('Complètement bourré')]
    assert not py[CORPUS.index('La buée sur la vitre')] and not py[CORPUS.index('Le barème des points')]


def test_the_screen_filter_never_uses_a_lookbehind():
    # iOS 16.0–16.3 (cible minimale de l'app) refuse (?<! : le module entier ne se chargerait pas.
    assert not re.search(r'\(\?<[!=]', TS.read_text(encoding='utf-8'))


def test_the_push_filter_answers_like_the_server_on_accented_words():
    """Même défaut dans la copie de send-push (Deno) : exécutée pour de vrai sur le même corpus."""
    src = (TS.parents[4] / 'supabase/functions/send-push/apns.ts').read_text(encoding='utf-8')
    start = src.index('const DRINK_PY = ')
    end = src.index("'iu');", src.index('export const DRINK_RE = ', start)) + 6
    script = src[start:end].replace('export const', 'const') + f'\nconsole.log(JSON.stringify({json.dumps(CORPUS)}.map((t) => DRINK_RE.test(t))));'
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script], capture_output=True, text=True,
                         timeout=30, check=True)
    py = [bool(store_app.DRINK_RE.search(t)) for t in CORPUS]
    assert dict(zip(CORPUS, json.loads(out.stdout))) == dict(zip(CORPUS, py))
