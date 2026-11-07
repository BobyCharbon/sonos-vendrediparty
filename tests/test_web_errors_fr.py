"""Erreurs techniques de la base en français (campagne 2, rapports 01, 04, 05, 06, 07, 09, 10) :
web/events/src/lib/errors.ts testé tel quel par Node. Jamais l'anglais brut de PostgreSQL / PostgREST à l'écran."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ERRORS = ROOT / 'web/events/src/lib/errors.ts'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')


def run(fn: str, messages: list) -> list:
    script = (f"import {{ {fn} }} from {json.dumps(ERRORS.as_uri())};\n"
              f"console.log(JSON.stringify({json.dumps(messages)}.map((m) => {fn}(m))));")
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script],
                         capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


GONE = 'Cet événement n’existe plus ou ne t’est pas ouvert.'


@pytest.mark.parametrize('raw, expected_part', [
    ('canceling statement due to statement timeout', 'trop de temps'),
    ('current transaction is aborted, commands ignored until end of transaction block', 'souci'),
    ('numeric field overflow', 'trop grand'),
    ('invalid input syntax for type integer: "2.7"', 'nombre entier'),
    ('invalid input syntax for type uuid: "abc"', 'pas valable'),
    ('Cannot coerce the result to a single JSON object', GONE),
    ('JSON object requested, multiple (or no) rows returned', GONE),
    ('new row violates row-level security policy for table "events"', 'pas le droit'),
    ('Failed to fetch', 'connexion'),
    ('TypeError: Load failed', 'connexion'),
    ('HTTP 504', 'trop de temps'),
    ('upstream request timeout', 'trop de temps'),
    ('duplicate key value violates unique constraint "x_pkey"', 'existe déjà'),
    ('value too long for type character varying(120)', 'trop long'),
    ('For security purposes, you can only request this after 0 seconds.', 'Attends'),
])
def test_technical_errors_are_translated(raw, expected_part):
    [text] = run('friendlyError', [raw])
    assert expected_part in text
    assert 'statement' not in text and 'JSON' not in text and 'transaction' not in text


def test_unknown_english_technical_message_gets_a_generic_french_sentence():
    [text] = run('friendlyError', ['some unexpected relation "foo" does not exist'])
    assert text == 'Un souci technique est survenu. Réessaie dans un instant.'


def test_french_messages_from_the_base_are_kept_as_is():
    msgs = ['Réponse « Peut-être » désactivée', 'La date limite de réponse est passée', 'Il n’en reste que 2']
    assert run('friendlyError', msgs) == msgs


def test_missing_or_closed_event_is_detected_to_hide_the_useless_retry():
    r = run('isGoneError', ['Cannot coerce the result to a single JSON object', 'canceling statement due to statement timeout',
                            'Failed to fetch', GONE, 'Introuvable'])
    # Déjà traduit : `must()` passe l'erreur par friendlyError avant que la fiche ne la reçoive (vu en recette réelle).
    assert r == [True, False, False, True, True]


def test_offline_errors_are_detected():
    assert run('isNetworkError', ['Failed to fetch', 'NetworkError when attempting to fetch resource.', 'numeric field overflow',
                                  'La connexion a échoué. Vérifie ton réseau puis réessaie.']) == [True, True, False, True]
