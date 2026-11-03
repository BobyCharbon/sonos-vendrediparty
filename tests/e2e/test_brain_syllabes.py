"""Méninges, « Débuts de mots » sans fin (vrai navigateur, iPhone, horloge simulée). Dictionnaire de test servi par
interception (mots/index.json + un fichier par début) pour maîtriser les lettres : saisie avec accents, majuscule
initiale (iPhone), œ, apostrophe typographique, point final de la double espace, suite seule, déjà donné, inconnu,
trop court ; objectif atteint → manche suivante (autres lettres) ; temps écoulé → une vie ; fichier lent ou en erreur
→ message, « Réessayer », jamais de chrono ni de mot refusé tant que le fichier n'est pas là. Enfin le vrai
dictionnaire est bien servi par le serveur (types, cache, gzip)."""
import json
import re
import time
from pathlib import Path

import httpx
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

MOTS = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'brain' / 'mots'
FILES = {
    'cha': ['chaine', 'chaines', 'chaise', 'chaleur', 'champs', 'chance', 'chantaient', 'chanter', 'chapeau',
            'chapeaux', 'chateau', 'chateaux', 'chou-fleur'],
    'coe': ['coequipier', 'coercition', 'coeur', 'coeurs', 'coexister', 'coexistons'],
    'auj': ["aujourd'hui", 'aujourdhuiste', 'aujourdhuistes', 'aujourdhuite'],
    'por': ['porte', 'porte-monnaie', 'portes', 'portions', 'portrait'],
}
# Saisies de la manche, par début : (texte tapé, accepté ?, extrait attendu dans le message si refusé)
SCRIPT = {
    'cha': [('Château', True, ''), ('CHATEAU', False, 'déjà trouvé'), ('cha', False, 'Trop court'),
            ('chazzz', False, 'inconnu'), ('chapeau. ', True, ''), ('îne', True, ''), ('Champs', True, '')],
    'coe': [('Cœur', True, ''), ('cœurs', True, ''), ('COEUR', False, 'déjà trouvé'), ('xistons', True, ''), ('coéquipier', True, '')],
    'auj': [('Aujourd’hui', True, ''), ('aujourd\'hui', False, 'déjà trouvé'), ('ourdhuite', True, ''),
            ('aujourdhuite', False, 'déjà trouvé'), ('Aujourdhuiste', True, ''), ('aujourdhuistes', True, '')],
    'por': [('Porte monnaie', True, ''), ('Portes', True, ''), ('portrait', True, ''), ('portions', True, '')],
}


def index_for(prefixes):
    return {'version': 'test', 'total': 99, 'prefixes': {
        **{p: {'n': 60, 'common': 30, 'rank': 1} for p in prefixes},
        'con': {'n': 900, 'common': 400, 'rank': 1},  # début grossier : jamais proposé
    }}


@pytest.fixture
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def phone(browser, server):
    p = Phone(browser, server, 'Boby')
    p.page.clock.install()
    yield p
    errors = p.errors
    p.close()
    assert not [e for e in errors if 'Failed to load resource' not in e], '\n'.join(errors)


def serve_dictionary(page, prefixes=tuple(FILES), fail=None, delay=0.0):
    """Interception de mots/ : `fail` = ensemble de débuts dont le fichier répond 503 (modifiable en cours de test)."""
    page.route(re.compile(r'/static/brain/mots/index\.json'),
               lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(index_for(prefixes))))

    def txt(route):
        abc = re.search(r'/mots/([a-z]{3})\.txt', route.request.url).group(1)
        if fail is not None and abc in fail:
            return route.fulfill(status=503, body='indisponible')
        if delay:
            time.sleep(delay)
        return route.fulfill(status=200, content_type='text/plain', body='\n'.join(FILES.get(abc, [])) + '\n')
    page.route(re.compile(r'/static/brain/mots/[a-z]{3}\.txt'), txt)


def start_game(phone):
    page = phone.page
    phone.open_games()
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    root.locator('[data-br="play"][data-id="syllabes"]').click()
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)  # 3-2-1
    expect(root.locator('.br-syllabes-wrap')).to_be_visible()
    return root


def submit(page, root, text):
    field = root.locator('.br-syllabes-input')
    field.fill(text)
    field.press('Enter')
    return root.locator('.br-syllabes-note').inner_text()


def wait_playable(page, root, pause=2000):
    if pause:
        page.clock.run_for(pause)  # pause entre les manches
    expect(root.locator('.br-syllabes-input')).to_be_enabled()
    return root.locator('.br-syllabes-pre').inner_text()


def test_accents_capitals_oe_apostrophe_duplicates_and_next_round(phone):
    page = phone.page
    serve_dictionary(page)
    root = start_game(phone)
    seen = []
    for manche in range(1, 5):
        prefix = wait_playable(page, root, pause=2000 if manche > 1 else 0)
        assert prefix in SCRIPT and prefix not in seen, (prefix, seen)  # jamais « con », jamais deux fois le même
        seen.append(prefix)
        expect(root.locator('.br-syllabes-rn')).to_have_text(f'Manche {manche}')
        expect(root.locator('.br-syllabes-goal')).to_have_text(re.compile(r'^0 / \d+ mots$'))
        for typed, ok, why in SCRIPT[prefix]:
            if not root.locator('.br-syllabes-input').is_enabled():
                break  # objectif atteint
            note = submit(page, root, typed)
            if ok:
                assert 'inconnu' not in note and 'déjà' not in note, (typed, note)
            else:
                assert why in note, (typed, note)
        expect(root.locator('.br-syllabes-note')).to_contain_text('Manche réussie')
        goal = page.evaluate(f'BrainSyllabes.goalFor({manche})')  # départ au niveau 1, +1 par manche réussie
        assert root.locator('.br-syllabes-word').count() == goal
    # Les mots sont affichés tels que tapés, échappés, en entier.
    assert float(root.locator('.br-syllabes-input').evaluate('e => parseFloat(getComputedStyle(e).fontSize)')) >= 16
    assert float(root.locator('.br-syllabes-word').first.evaluate('e => parseFloat(getComputedStyle(e).fontSize)')) >= 16


def lost_lives(root):
    return root.locator('.br-lives .br-heart.lost').count()


def test_round_missed_costs_a_life_and_three_misses_end_the_game(phone):
    page = phone.page
    serve_dictionary(page)
    root = start_game(phone)
    wait_playable(page, root, pause=0)
    page.clock.run_for(29_000)
    expect(root.locator('.br-syllabes-note')).not_to_contain_text('Temps écoulé')
    assert lost_lives(root) == 0
    page.clock.run_for(1_500)
    expect(root.locator('.br-syllabes-note')).to_contain_text('Temps écoulé')
    assert lost_lives(root) == 1
    wait_playable(page, root)
    expect(root.locator('.br-syllabes-rn')).to_have_text('Manche 2')
    page.clock.run_for(32_000)
    assert lost_lives(root) == 2
    page.clock.run_for(35_000)
    expect(root.locator('.br-end')).to_be_visible()  # 3 manches ratées = 3 vies : fin de partie
    expect(root.locator('.br-end .br-stat').first).to_contain_text('Précision')


def test_dictionary_error_shows_retry_and_never_runs_the_clock(phone):
    page = phone.page
    failing = set(FILES)
    serve_dictionary(page, prefixes=('cha',), fail=failing)
    root = start_game(phone)
    note = root.locator('.br-syllabes-note')
    expect(note).to_contain_text('Dictionnaire indisponible')
    expect(root.locator('.br-syllabes-input')).to_be_disabled()
    page.clock.run_for(65_000)  # rien ne tourne sans dictionnaire : aucune vie perdue
    expect(root.locator('.br-end')).to_have_count(0)
    expect(note).not_to_contain_text('Temps écoulé')
    failing.clear()  # la connexion revient
    note.locator('.br-syllabes-retry').click()
    expect(root.locator('.br-syllabes-input')).to_be_enabled()
    assert re.search('Bien vu|Bravo', submit(page, root, 'Château'))


def test_slow_dictionary_file_only_starts_once_loaded(phone):
    page = phone.page
    serve_dictionary(page, prefixes=('coe',), delay=1.5)
    root = start_game(phone)
    expect(root.locator('.br-syllabes-input')).to_be_enabled(timeout=10000)
    assert 'Bien vu' in submit(page, root, 'cœur')


def test_real_dictionary_is_served_with_cache_and_gzip(server):
    if not (MOTS / 'index.json').exists():
        pytest.skip('dictionnaire pas encore construit (tools/build_mots_fr.py)')
    html = httpx.get(server.url + '/').text
    build = re.search(r'/static/brain/core\.js\?v=([\w.-]+)', html).group(1)
    index = httpx.get(f'{server.url}/static/brain/mots/index.json?v={build}', headers={'Accept-Encoding': 'gzip'})
    assert index.status_code == 200 and 'json' in index.headers['content-type']
    assert 'immutable' in index.headers['cache-control']
    prefixes = index.json()['prefixes']
    abc = 'cha' if 'cha' in prefixes else next(iter(prefixes))
    txt = httpx.get(f'{server.url}/static/brain/mots/{abc}.txt?v={build}', headers={'Accept-Encoding': 'gzip'})
    assert txt.status_code == 200 and txt.headers['content-type'].startswith('text/plain')
    assert txt.headers.get('content-encoding') == 'gzip' and 'immutable' in txt.headers['cache-control']
    lines = txt.text.splitlines()
    assert lines == sorted(set(lines)) and all(w.startswith(abc) for w in lines)
    assert httpx.get(f'{server.url}/static/brain/mots/{abc}.txt').headers['cache-control'] == 'no-cache'
