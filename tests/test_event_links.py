"""Liens cliquables dans les textes des événements (avis 2c221fd8effc) : web/events/src/lib/links.ts testé tel quel
par Node (qui lit le TypeScript directement). Adresses web, www., e-mails et numéros deviennent des liens ; jamais
javascript:, data: ni un IBAN, une date ou un prix ; le texte n'est jamais transformé en HTML."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / 'web/events/src/lib/links.ts'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')


def run(expr_by_name: dict) -> dict:
    """Évalue chaque expression JS (avec linkify, safeHref, hasLink) et renvoie les résultats en JSON."""
    body = ',\n'.join(f'{json.dumps(k)}: {v}' for k, v in expr_by_name.items())
    script = f"import {{ linkify, safeHref, hasLink }} from {json.dumps(LINKS.as_uri())};\nconsole.log(JSON.stringify({{{body}}}));"
    out = subprocess.run(['node', '--no-warnings', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def links(segments):
    return [(s['text'], s['href']) for s in segments if s.get('href')]


def L(text: str) -> str:
    return f'linkify({json.dumps(text)})'


def test_web_addresses_become_links_without_trailing_punctuation():
    r = run({'a': L('Infos : https://exemple.ch/a?b=1. Merci !'), 'b': L('Voir (www.lac.ch) ou https://fr.wikipedia.org/wiki/Gen%C3%A8ve_(ville), ok'),
             'c': L('HTTPS://EXEMPLE.CH/X')})
    assert links(r['a']) == [('https://exemple.ch/a?b=1', 'https://exemple.ch/a?b=1')]
    assert ''.join(s['text'] for s in r['a']) == 'Infos : https://exemple.ch/a?b=1. Merci !'  # rien de perdu ni d'ajouté
    assert links(r['b']) == [('www.lac.ch', 'https://www.lac.ch/'),
                             ('https://fr.wikipedia.org/wiki/Gen%C3%A8ve_(ville)', 'https://fr.wikipedia.org/wiki/Gen%C3%A8ve_(ville)')]
    assert links(r['c'])[0][1].startswith('https://exemple.ch/')


def test_emails_and_phone_numbers_become_links():
    r = run({'a': L('Écris à ana@exemple.ch ou appelle le 079 123 45 67 ou le +41 79 123 45 67 (TWINT).')})
    assert links(r['a']) == [('ana@exemple.ch', 'mailto:ana@exemple.ch'), ('079 123 45 67', 'tel:0791234567'),
                             ('+41 79 123 45 67', 'tel:+41791234567')]


def test_iban_dates_prices_and_plain_numbers_stay_text():
    r = run({'a': L('IBAN CH93 0076 2011 6238 5295 7, prix 20.50 CHF le 14.11.2030 à 18:00, 12 places, code 123456')})
    assert links(r['a']) == []


def test_dangerous_schemes_are_never_links():
    r = run({'text': L('javascript:alert(1) data:text/html,<script>alert(1)</script> file:///etc/passwd vbscript:x'),
             'js': 'safeHref("javascript:alert(1)")', 'JS': 'safeHref(" JAVASCRIPT:alert(1)")', 'tab': 'safeHref("java\\tscript:alert(1)")',
             'data': 'safeHref("data:text/html,x")', 'creds': 'safeHref("https://banque.ch@piege.example")',
             'www': 'safeHref("www.exemple.ch")', 'maps': 'safeHref("https://maps.app.goo.gl/abc")', 'empty': 'safeHref(null)',
             'trap': L('https://banque.ch@piege.example')})
    assert links(r['text']) == []
    assert r['js'] is r['JS'] is r['tab'] is r['data'] is r['creds'] is r['empty'] is None
    assert r['www'] == 'https://www.exemple.ch/' and r['maps'] == 'https://maps.app.goo.gl/abc'
    assert links(r['trap']) == []  # adresse trompeuse : affichée, jamais cliquable


def test_markup_is_kept_as_plain_text_segments():
    text = '<img src=x onerror=alert(1)> <a href="javascript:alert(1)">clic</a> https://ok.ch'
    r = run({'a': L(text), 'has': f'hasLink({json.dumps(text)})', 'none': 'hasLink("bonjour")', 'empty': 'linkify("")'})
    assert ''.join(s['text'] for s in r['a']) == text
    assert links(r['a']) == [('https://ok.ch', 'https://ok.ch/')]
    assert r['has'] is True and r['none'] is False and r['empty'] == []
