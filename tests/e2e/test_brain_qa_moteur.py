"""Méninges, QA du moteur (core.js, detail.js) : vrai navigateur iPhone, horloge simulée, jeu factice à la place de
« Pareil ? ». Stockage local corrompu, plein ou bloqué ; jeu qui ne démarre pas ; réseau coupé au chargement des jeux
et à l'envoi ; serveur 500 / 401 ; envoi en double ; navigation pendant une réponse lente du serveur ; retour
(Android / navigateur) ; focus pour VoiceOver ; limite de 30 minutes ; Échauffement de 5 jeux et lendemain."""
import json
import time

import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

# Jeu factice : → bonne réponse (niveau suivant), ← slip, ↓ erreur ; sans réponse pendant 2 s : erreur
# (sauf window.__calm : aucun délai, pour la partie de 30 minutes). window.__boom : start() lève une exception.
STUB = """Brain.register({ id: "pareil", name: "Pareil ?", domain: "vitesse", icon: "🟰", seconds: null, howto: ["Jeu factice."],
  start(ctx) {
    if (window.__boom) throw new Error("boom");
    let level = ctx.level, timer = null;
    const arm = () => { clearTimeout(timer); if (!window.__calm) timer = setTimeout(() => { ctx.miss(); arm(); }, 2000); };
    const key = (ev) => {
      if (ev.key === "ArrowRight") { ctx.hit({ rt: 500 }); level += 1; ctx.setLevel(level); arm(); }
      else if (ev.key === "ArrowLeft") ctx.slip({ rt: 500 });
      else if (ev.key === "ArrowDown") { ctx.miss(); arm(); }
    };
    document.addEventListener("keydown", key);
    ctx.root.innerHTML = '<p class="stub">Jeu factice</p>';
    window.__stub = { starts: (window.__stub?.starts || 0) + 1, level: ctx.level, stops: window.__stub?.stops || 0, live: true };
    arm();
    return { stop() { clearTimeout(timer); document.removeEventListener("keydown", key); window.__stub.stops += 1; window.__stub.live = false; } };
  } });"""

TOKEN = 'jeton-de-test-qa-moteur-0001'
SESSION = {'game': 'pareil', 'score': 900, 'accuracy': 0.8, 'avg_rt_ms': 700, 'level': 7, 'duration_ms': 60000}


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Boby')
    p.page.clock.install()
    p.page.route('**/static/brain/games/pareil.js*', lambda r: r.fulfill(status=200, body=STUB,
                                                                       content_type='application/javascript'))
    yield p
    errors, server_errors = p.errors, server.errors()
    p.close()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def brain(page):
    return page.locator('#brainRoot')


def open_brain(page):
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    expect(brain(page).locator('.br-home')).to_be_visible(timeout=15000)
    return brain(page)


def start(page, root):
    """Explication → 3-2-1 → partie."""
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)
    expect(root.locator('.br-hud')).to_be_visible()
    expect(root.locator('.stub')).to_be_visible()


def play_stub(page, root):
    tile = root.locator('[data-br="play"][data-id="pareil"]')
    tile.click()
    expect(root.locator('.br-howto, .bd-sheet')).to_be_visible()
    if root.locator('.bd-sheet').count():
        root.locator('.bd-sheet [data-br="again"]').click()
    start(page, root)


def die(page, root):
    page.clock.run_for(10_000)
    expect(root.locator('.br-end')).to_be_visible()


def connect(page):
    session = {'access_token': TOKEN, 'refresh_token': 'r', 'expires_at': int(time.time()) + 3600 * 24}
    page.evaluate(f"localStorage.setItem('sb-e2e-auth-token', {json.dumps(json.dumps(session))})")


PROFILE = {'temperature': 0, 'domains': {}, 'games': {}, 'streak': {'current': 0, 'best': 0}, 'history': [],
           'warmup': None}


def mock_account(page, results: list, result_status=200, me_status=200):
    """Compte simulé : /me, /game et /result répondent comme la base (result_status : 200, 500, 401, 'abort')."""
    def reply(route, status, data):
        if status == 'abort':
            return route.abort()
        route.fulfill(status=status, content_type='application/json',
                      body=json.dumps(data if status == 200 else {'detail': 'Erreur de test'}))

    def result(route):
        body = json.loads(route.request.post_data or '{}')
        results.append(body)
        reply(route, result_status() if callable(result_status) else result_status,
              {'saved': True, 'index': 1000, 'best': body.get('score'), 'record': True, 'plays': len(results)})
    page.route('**/api/brain/result', result)
    page.route('**/api/brain/me', lambda r: reply(r, me_status, PROFILE))
    page.route('**/api/brain/game', lambda r: reply(r, 200, {'game': 'pareil', 'plays': 0, 'best': 0, 'avg': 0,
                                                              'level': 0, 'history': []}))


# ── Stockage local ──
CORRUPT = """() => {
  localStorage.setItem('brain_local', JSON.stringify({ not: 'a list' }));
  localStorage.setItem('brain_warmup', JSON.stringify({ day: new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Zurich' }), ids: null }));
  localStorage.setItem('brain_tiers', '"x"');
  localStorage.setItem('brain_levels', '[3]');
  localStorage.setItem('brain_best', '42');
}"""


def test_corrupted_storage_does_not_break_the_panel_or_the_end_screen(phone):
    page = phone.page
    phone.open_games()
    page.evaluate(CORRUPT)
    root = open_brain(page)
    expect(root.locator('.br-warm .br-cta')).to_be_visible()
    play_stub(page, root)
    die(page, root)
    expect(root.locator('.br-save')).to_contain_text('Connecte-toi', timeout=10000)
    saved = page.evaluate("JSON.parse(localStorage.getItem('brain_local'))")
    assert isinstance(saved, list) and len(saved) == 1 and saved[0]['game'] == 'pareil'


def test_a_bad_entry_in_the_local_sessions_does_not_hide_the_other_games(phone):
    """Une partie gardée illisible (vieille version, édition à la main) : le profil se calcule avec les autres."""
    page = phone.page
    phone.open_games()
    page.evaluate("""() => localStorage.setItem('brain_local', JSON.stringify([
      { game: 'pareil', score: 900, accuracy: 0.8, avg_rt_ms: 700, level: 7, duration_ms: 60000, played_at: new Date().toISOString() },
      { game: 'PAS UN JEU', score: -5 }, null, 'texte']))""")
    root = open_brain(page)
    expect(root.locator('.br-temp b')).not_to_have_text('0')


@pytest.mark.parametrize('mode', ['blocked', 'full'])
def test_blocked_or_full_storage_still_plays_and_ends(phone, mode):
    page = phone.page
    phone.open_games()
    # Seules les clés de Méninges sont touchées (le reste de l'app garde son identité).
    page.add_init_script("""(mode => {
      const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
      Storage.prototype.getItem = function (k) { if (mode === 'blocked' && String(k).startsWith('brain_')) throw new DOMException('bloqué', 'SecurityError'); return get.call(this, k); };
      Storage.prototype.setItem = function (k, v) { if (String(k).startsWith('brain_')) throw new DOMException('plein', 'QuotaExceededError'); return set.call(this, k, v); };
    })""" + f"('{mode}')")
    page.reload()
    page.locator('button[data-tab="games"]').first.click()
    root = open_brain(page)
    play_stub(page, root)
    die(page, root)
    expect(root.locator('.br-big')).to_be_visible()
    root.locator('[data-br="home"]').click()
    expect(root.locator('.br-home')).to_be_visible()


# ── Jeu qui ne démarre pas ──
def test_a_game_that_fails_to_start_is_not_recorded(phone):
    page = phone.page
    phone.open_games()
    page.evaluate('window.__boom = true')
    root = open_brain(page)
    root.locator('.br-warm .br-cta').click()
    warm_first = page.evaluate("JSON.parse(localStorage.getItem('brain_warmup')).ids[0]")
    root.locator('.br-howto .br-top [data-br="close"]').click()
    root.locator('[data-br="play"][data-id="pareil"]').click()
    start_btn = root.locator('[data-br="go"]')
    start_btn.click()
    page.clock.run_for(3000)
    expect(root.locator('.br-end')).to_be_visible()
    expect(root.locator('.br-detail')).to_contain_text("n'a pas pu démarrer")
    page.clock.run_for(2000)
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local') || '[]').length") == 0
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_best') || '{}').pareil || 0") == 0
    assert warm_first


# ── Réseau ──
def test_games_come_back_after_a_first_opening_without_network(phone):
    page = phone.page
    phone.open_games()
    page.route('**/static/brain/games/*.js*', lambda r: r.abort())
    page.route('**/api/brain/**', lambda r: r.abort())
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = brain(page)
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    expect(root.locator('[data-br="play"]')).to_have_count(0)
    root.locator('.br-top [data-br="close"]').click()
    page.unroute('**/static/brain/games/*.js*')
    page.unroute('**/api/brain/**')
    page.route('**/static/brain/games/pareil.js*', lambda r: r.fulfill(status=200, body=STUB,
                                                                       content_type='application/javascript'))
    root = open_brain(page)
    expect(root.locator('[data-br="play"][data-id="pareil"]')).to_be_visible()


@pytest.mark.parametrize('failure', ['abort', 500, 401])
def test_save_failure_keeps_the_game_and_says_so_in_french(phone, failure):
    page = phone.page
    phone.open_games()
    connect(page)
    results = []
    mock_account(page, results, result_status=failure)
    root = open_brain(page)
    expect(root.locator('.br-login')).to_have_count(0)
    play_stub(page, root)
    page.keyboard.press('ArrowRight')
    die(page, root)
    note = root.locator('.br-save')
    expect(note).to_contain_text('Gardé sur ce téléphone', timeout=10000)
    assert 'fetch' not in note.inner_text().lower()
    assert 'Failed' not in note.inner_text()
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 1


def test_offline_games_are_sent_once_even_when_the_panel_refreshes_twice(phone):
    """Double envoi : deux rafraîchissements du profil en même temps (double toucher, retour rapide à l'accueil)
    n'envoient chaque partie gardée qu'une fois."""
    page = phone.page
    phone.open_games()
    page.evaluate(f"""() => localStorage.setItem('brain_local', JSON.stringify([
      {{ ...{json.dumps(SESSION)}, played_at: new Date().toISOString() }},
      {{ ...{json.dumps(SESSION)}, score: 1200, played_at: new Date().toISOString() }}]))""")
    connect(page)
    results = []
    mock_account(page, results)
    page.evaluate('Promise.all([Brain.open(), Brain.open()])')
    expect(brain(page).locator('.br-home')).to_be_visible(timeout=15000)
    page.clock.run_for(3000)
    assert sorted(r['score'] for r in results) == [900, 1200]
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 0


def test_more_than_30_offline_games_are_all_sent_over_time(phone):
    """Les parties au-delà des 30 envoyées d'un coup restent sur le téléphone pour la prochaine fois."""
    page = phone.page
    phone.open_games()
    page.evaluate(f"""() => localStorage.setItem('brain_local', JSON.stringify(Array.from({{ length: 40 }}, (_, i) =>
      ({{ ...{json.dumps(SESSION)}, score: 100 + i, played_at: new Date().toISOString() }}))))""")
    connect(page)
    results = []
    mock_account(page, results)
    root = open_brain(page)
    assert len(results) == 30
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 10
    root.locator('.br-top [data-br="close"]').click()
    open_brain(page)
    assert len(results) == 40
    assert sorted(r['score'] for r in results) == list(range(100, 140))
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 0


def test_connecting_after_playing_sends_the_games_to_the_account(phone):
    page = phone.page
    phone.open_games()
    root = open_brain(page)
    play_stub(page, root)
    for _ in range(3):
        page.keyboard.press('ArrowRight')
    die(page, root)
    expect(root.locator('.br-save')).to_contain_text('Connecte-toi', timeout=10000)
    root.locator('.br-top [data-br="close"]').click()
    connect(page)
    results = []
    mock_account(page, results)
    root = open_brain(page)
    expect(root.locator('.br-login')).to_have_count(0)
    assert len(results) == 1 and results[0]['game'] == 'pareil' and results[0]['level'] == 4
    assert results[0]['token'] == TOKEN and 'played_at' not in results[0]
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 0


# ── Navigation pendant une réponse lente ──
SLOW = """() => {
  const real = window.fetch;
  window.__slow = 0;
  window.fetch = function (url, opts) {
    if (String(url).includes('/api/brain/local') && window.__slowNext) {
      window.__slowNext = false;
      return new Promise((done) => setTimeout(done, 4000)).then(() => real.call(this, url, opts));
    }
    return real.call(this, url, opts);
  };
}"""


def test_a_slow_refresh_never_replaces_a_newer_screen(phone):
    page = phone.page
    phone.open_games()
    page.evaluate(SLOW)
    root = open_brain(page)
    play_stub(page, root)
    die(page, root)
    page.evaluate('window.__slowNext = true')
    root.locator('[data-br="home"]').click()            # serveur lent : l'accueil se fait attendre
    expect(root.locator('.br-end')).to_have_count(0)    # le toucher a un effet visible tout de suite
    page.keyboard.press('Escape')                       # l'invité ferme puis rouvre et relance une partie
    expect(root).to_be_hidden()
    root = open_brain(page)
    play_stub(page, root)
    page.clock.run_for(1500)                            # l'ancienne réponse arrive enfin
    page.wait_for_timeout(300)
    expect(root.locator('.br-hud')).to_be_visible()
    assert root.get_attribute('data-screen') == 'play'


# ── Retour (bouton Android, geste, navigateur) ──
def test_back_closes_the_panel_and_asks_before_leaving_a_game(phone):
    page = phone.page
    phone.open_games()
    page.evaluate('window.__still = 1')
    root = open_brain(page)
    page.go_back()
    expect(root).to_be_hidden()
    assert page.evaluate('window.__still') == 1           # même page : pas de rechargement, pas de sortie de l'app
    expect(page.locator('#gHome')).to_be_visible()

    root = open_brain(page)
    play_stub(page, root)
    page.go_back()                                       # en pleine partie : on demande d'abord
    expect(root.locator('.br-confirm')).to_be_visible()
    assert page.evaluate('window.__still') == 1
    root.locator('[data-br="stay"]').click()
    expect(root.locator('.br-hud')).to_be_visible()
    page.go_back()
    root.locator('[data-br="leave"]').click()
    expect(root.locator('.br-home')).to_be_visible()
    root.locator('.br-top [data-br="close"]').click()
    expect(root).to_be_hidden()
    assert not page.evaluate('history.state?.navDepth')  # le panneau fermé n'a pas laissé d'entrée orpheline


# ── VoiceOver / clavier ──
def test_focus_moves_into_the_panel_and_follows_the_screens(phone):
    page = phone.page
    phone.open_games()
    page.evaluate("""() => localStorage.setItem('brain_tiers', JSON.stringify({ pareil: 3 }))""")
    root = open_brain(page)
    inside = "document.getElementById('brainRoot').contains(document.activeElement)"
    assert page.evaluate(inside), 'focus resté derrière le panneau'
    root.locator('[data-br="play"][data-id="pareil"]').click()
    root.locator('[data-br="tier-down"]').click()
    expect(root.locator('.br-tier')).to_contain_text('Départ : palier 2')
    assert page.evaluate("document.activeElement?.dataset.br") == 'tier-down'   # le focus ne tombe pas à la page
    root.locator('[data-br="tier-down"]').click()
    expect(root.locator('.br-tier')).to_contain_text('Départ : palier 1')
    assert page.evaluate("document.activeElement?.dataset.br") == 'tier-up'     # « − » désactivé : vers « + »
    start(page, root)
    page.keyboard.press('Escape')
    expect(root.locator('.br-confirm')).to_be_visible()
    assert page.evaluate("document.activeElement?.dataset.br") == 'stay'
    page.keyboard.press('Escape')                                                # Échap referme la question
    expect(root.locator('.br-confirm')).to_have_count(0)
    expect(root.locator('.br-hud')).to_be_visible()


def test_escape_on_a_game_sheet_goes_back_home(phone):
    page = phone.page
    phone.open_games()
    page.evaluate(f"""() => localStorage.setItem('brain_local', JSON.stringify([{{ ...{json.dumps(SESSION)}, played_at: new Date().toISOString() }}]))""")
    root = open_brain(page)
    root.locator('[data-br="play"][data-id="pareil"]').click()
    expect(root.locator('.bd-sheet')).to_be_visible()
    page.keyboard.press('Escape')
    expect(root.locator('.br-home')).to_be_visible()


# ── Limite de 30 minutes ──
def test_a_perfect_player_is_stopped_after_30_minutes_and_the_game_counts(phone):
    page = phone.page
    phone.open_games()
    page.evaluate('window.__calm = true')
    root = open_brain(page)
    play_stub(page, root)
    for _ in range(20):
        page.keyboard.press('ArrowRight')
    page.clock.run_for(30 * 60 * 1000 + 500)
    end = root.locator('.br-end')
    expect(end).to_be_visible()
    expect(end.locator('.br-reason')).to_contain_text('30 minutes')
    assert page.evaluate('window.__stub.live') is False
    saved = page.evaluate("JSON.parse(localStorage.getItem('brain_local'))")
    assert len(saved) == 1 and saved[0]['level'] == 21 and saved[0]['duration_ms'] <= 30 * 60 * 1000 + 1000


# ── Fermeture : rien ne tourne ──
@pytest.mark.parametrize('when', ['count', 'play', 'dying'])
def test_closing_stops_everything(phone, when):
    page = phone.page
    phone.open_games()
    root = open_brain(page)
    root.locator('[data-br="play"][data-id="pareil"]').click()
    root.locator('[data-br="go"]').click()
    if when != 'count':
        page.clock.run_for(3000)
        expect(root.locator('.stub')).to_be_visible()
    if when == 'dying':
        for _ in range(3):
            page.keyboard.press('ArrowDown')
    page.evaluate('Brain.close()')
    expect(root).to_be_hidden()
    page.clock.run_for(60_000)
    expect(root).to_be_hidden()
    assert root.inner_html() == ''
    assert page.evaluate('window.__stub?.live || false') is False
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local') || '[]').length") == 0  # fermée : pas comptée


# ── Échauffement : 5 jeux d'affilée, puis le lendemain ──
def stub_all_games(phone):
    """Chaque jeu remplacé par le jeu factice (même id, même domaine) : on teste le moteur, pas les jeux."""
    import httpx
    catalog = httpx.get(f'{phone.server.url}/api/brain/catalog', timeout=10).json()
    domains = {g['id']: g['domain'] for g in catalog['games']}

    def fulfill(route):
        gid = route.request.url.split('/games/')[1].split('.js')[0]
        body = STUB.replace('id: "pareil"', f'id: "{gid}"').replace('domain: "vitesse"', f'domain: "{domains.get(gid, "vitesse")}"')
        route.fulfill(status=200, body=body, content_type='application/javascript')
    phone.page.route('**/static/brain/games/*.js*', fulfill)


def test_warmup_five_games_in_a_row_then_a_new_one_the_next_day(phone):
    page = phone.page
    stub_all_games(phone)
    phone.open_games()
    page.clock.set_system_time('2026-11-03T22:58:00Z')   # 23:58 à Zurich
    root = open_brain(page)
    ids = page.evaluate("JSON.parse(localStorage.getItem('brain_warmup')).ids")
    assert len(ids) == 5 and len(set(ids)) == 5
    root.locator('.br-warm .br-cta').click()
    for i in range(5):
        howto = root.locator('.br-howto')
        expect(howto.locator('.br-chip').first).to_contain_text(f'Échauffement · {i + 1}/5')
        root.locator('[data-br="go"]').click()
        page.clock.run_for(3000)
        expect(root.locator('.br-hud')).to_be_visible()
        for _ in range(40):                             # le joueur ne répond plus : 3 vies perdues
            page.clock.run_for(3000)
            if root.locator('.br-end').count():
                break
        expect(root.locator('.br-end')).to_be_visible(timeout=10000)
        if i < 4:
            root.locator('[data-br="next"]').click()
    done = page.evaluate("JSON.parse(localStorage.getItem('brain_warmup'))")
    root.locator('[data-br="warmdone"]').click()
    expect(root.locator('.br-done')).to_be_visible()
    root.locator('.br-done [data-br="home"]').click()
    expect(root.locator('.br-warm')).to_contain_text("Fait aujourd'hui")
    root.locator('.br-top [data-br="close"]').click()
    page.clock.fast_forward(24 * 3600 * 1000)           # lendemain (sans jouer chaque minuterie d'une journée)
    root = open_brain(page)
    expect(root.locator('.br-warm .br-cta')).to_have_text('Commencer')
    nxt = page.evaluate("JSON.parse(localStorage.getItem('brain_warmup'))")
    assert nxt['day'] != done['day'] and nxt['done'] == []


# ── Textes : Méninges est sans fin (plus « une minute par jeu ») ──
def test_the_games_card_no_longer_promises_one_minute_per_game(phone):
    phone.open_games()
    card = phone.page.locator('#gHome section[data-cat="brain"] .gcard.g-br')
    expect(card).to_be_visible()
    assert 'minute' not in card.inner_text()
    expect(card).to_contain_text('3 vies')


def open_brain_stats(page):
    page.evaluate("postMessage({type: 'party-events:open-tab', tab: 'stats'}, location.origin)")
    expect(page.locator('#appTitle')).to_have_text('Mes stats de jeu')
    page.locator('[data-stats-tab="brain"]').click()
    return page.locator('#brainStats')


def test_stats_tab_offline_says_it_in_french_and_ignores_a_bad_local_entry(phone):
    page = phone.page
    phone.page.goto('/')
    page.evaluate(f"""() => localStorage.setItem('brain_local', JSON.stringify([
      {{ ...{json.dumps(SESSION)}, played_at: new Date().toISOString() }}, {{ game: 'X!', score: 'a' }}, 7]))""")
    page.route('**/api/brain/local', lambda r: r.abort())
    stats = open_brain_stats(page)
    expect(stats.locator('.brs-error')).to_contain_text('pas de réseau')
    assert 'Failed' not in stats.inner_text()
    page.unroute('**/api/brain/local')
    stats.locator('[data-brs="retry"]').click()
    expect(stats.locator('.brs-temp b')).not_to_have_text('0')
    expect(stats.locator('.brs-empty')).to_have_count(0)


# ── App installée sur iPhone (bug iOS 26 du CLAUDE.md), thèmes, mouvements réduits, tailles d'écran ──
IOS_SCREEN = {'width': 390, 'height': 844}
IOS_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 '
          '(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1')


@pytest.fixture
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


def device(browser, server, viewport, **extra):
    ctx = browser.new_context(base_url=server.url, viewport=viewport, user_agent=IOS_UA, is_mobile=True, has_touch=True,
                              device_scale_factor=2, locale='fr-CH', **extra)
    ctx.add_init_script("localStorage.setItem('vp_install_dismissed', '1'); localStorage.setItem('vp_name', 'Test');")
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: m.type == 'error' and 'Failed to load resource' not in m.text and errors.append(m.text))
    page.clock.install()
    page.route('**/static/brain/games/pareil.js*', lambda r: r.fulfill(status=200, body=STUB,
                                                                     content_type='application/javascript'))
    page.goto('/')
    page.locator('button[data-tab="games"]').first.click()
    expect(page.locator('#gHome')).to_be_visible()
    return ctx, page, errors


def no_sideways_scroll(page):
    over = page.evaluate("""() => { const r = document.getElementById('brainRoot');
      return { panel: r.scrollWidth - r.clientWidth, page: document.documentElement.scrollWidth - innerWidth }; }""")
    assert over['panel'] <= 1 and over['page'] <= 1, over


def test_installed_iphone_app_keeps_its_tab_bar_with_meninges_open(browser, server):
    ctx, page, errors = device(browser, server, {'width': 390, 'height': 765}, screen=IOS_SCREEN)
    ctx.add_init_script("Object.defineProperty(Navigator.prototype, 'standalone', { get: () => true });")
    page.reload()
    page.locator('button[data-tab="games"]').first.click()
    assert page.evaluate("document.documentElement.classList.contains('ios-app')")
    tabs = "document.getElementById('tabs').getBoundingClientRect().bottom"
    before = page.evaluate(tabs)
    root = open_brain(page)
    for step in ('home', 'play', 'end'):
        if step == 'play':
            play_stub(page, root)
        if step == 'end':
            die(page, root)
        h = page.evaluate("({ scroll: document.documentElement.scrollHeight, screen: screen.height })")
        assert h['scroll'] > h['screen'], (step, h)
        assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
        assert page.evaluate("getComputedStyle(document.documentElement).overflowY") != 'hidden'
        no_sideways_scroll(page)
    root.locator('.br-top [data-br="close"]').click()
    expect(root).to_be_hidden()
    assert abs(page.evaluate(tabs) - before) <= 1
    ctx.close()
    assert not errors, errors


@pytest.mark.parametrize('scheme,motion,viewport', [('light', 'reduce', {'width': 390, 'height': 844}),
                                                     ('dark', 'no-preference', {'width': 820, 'height': 1180})])
def test_themes_reduced_motion_and_sizes(browser, server, scheme, motion, viewport):
    ctx, page, errors = device(browser, server, viewport, color_scheme=scheme, reduced_motion=motion)
    root = open_brain(page)
    contrast = """() => { const r = document.querySelector('#brainRoot .br-title');
      return [getComputedStyle(r).color, getComputedStyle(document.getElementById('brainRoot')).backgroundColor]; }"""
    color, bg = page.evaluate(contrast)
    assert color in ('rgb(238, 242, 255)',), color          # texte clair sur fond sombre, quel que soit le thème
    assert bg == 'rgb(10, 14, 29)', bg
    no_sideways_scroll(page)
    play_stub(page, root)
    no_sideways_scroll(page)
    for _ in range(3):
        page.keyboard.press('ArrowDown')
    page.clock.run_for(1000)
    end = root.locator('.br-end')
    expect(end).to_be_visible()
    if motion == 'reduce':                                    # score affiché d'emblée, sans compteur qui défile
        assert end.locator('.br-big').inner_text() == end.locator('.br-big').get_attribute('data-count') or \
            end.locator('.br-big').inner_text().replace(' ', '').replace("'", '') == end.locator('.br-big').get_attribute('data-count')
    no_sideways_scroll(page)
    ctx.close()
    assert not errors, errors


def test_login_link_closes_meninges_and_opens_the_settings_tab(phone):
    page = phone.page
    phone.open_games()
    root = open_brain(page)
    root.locator('.br-login [data-br="login"]').click()
    expect(root).to_be_hidden()
    page.clock.run_for(1500)
    expect(page.locator('body')).to_have_attribute('data-tab', 'account')
    assert page.evaluate('Nav.has("brain")') is False    # pas d'entrée d'historique laissée par Méninges


def test_opened_from_the_stats_tab_back_returns_to_the_stats(phone):
    page = phone.page
    page.goto('/')
    page.evaluate(f"""() => localStorage.setItem('brain_local', JSON.stringify([{{ ...{json.dumps(SESSION)}, played_at: new Date().toISOString() }}]))""")
    stats = open_brain_stats(page)
    stats.locator('[data-brs="open"]').click()
    root = brain(page)
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    page.go_back()
    expect(root).to_be_hidden()
    expect(page.locator('#appTitle')).to_have_text('Mes stats de jeu')
    expect(stats).to_be_visible()


def test_native_ios_tab_bar_hides_while_meninges_is_open(browser, server):
    """App iOS native : la UITabBar est sous la vue web. Méninges ouvert (plein écran) → elle se masque, comme pour
    un jeu en plein écran ; sinon un toucher d'onglet changeait d'onglet SOUS le panneau resté ouvert."""
    from tests.e2e.test_native_tabs import IPHONE, NATIVE_BRIDGE
    ctx = browser.new_context(base_url=server.url, **IPHONE)
    ctx.add_init_script(NATIVE_BRIDGE)
    page = ctx.new_page()
    page.route('**/static/brain/games/pareil.js*', lambda r: r.fulfill(status=200, body=STUB,
                                                                     content_type='application/javascript'))
    page.goto('/')
    page.wait_for_function('window.__tabStates.length > 0')
    page.evaluate("PartyTabs.select('games')")
    expect(page.locator('#gHome')).to_be_visible()
    last = "() => window.__tabStates[window.__tabStates.length - 1].hidden"
    page.wait_for_timeout(200)
    assert page.evaluate(last) is False
    root = open_brain(page)
    page.wait_for_timeout(200)
    assert page.evaluate(last) is True
    root.locator('.br-top [data-br="close"]').click()
    page.wait_for_timeout(200)
    assert page.evaluate(last) is False
    ctx.close()


def test_game_sheet_tier_matches_the_start_tier_picker(phone):
    """Palier débloqué puis partie quittée (non comptée) : la fiche annonçait « Palier max 1 » alors que l'explication
    proposait de repartir au palier 3."""
    page = phone.page
    phone.open_games()
    page.evaluate(f"""() => {{ localStorage.setItem('brain_local', JSON.stringify([{{ ...{json.dumps(SESSION)}, level: 2,
      played_at: new Date().toISOString() }}])); localStorage.setItem('brain_tiers', JSON.stringify({{ pareil: 3 }})); }}""")
    root = open_brain(page)
    root.locator('[data-br="play"][data-id="pareil"]').click()
    sheet = root.locator('.bd-sheet')
    expect(sheet).to_be_visible()
    expect(sheet.locator('.br-stat').filter(has_text='Palier max')).to_contain_text('3')
    sheet.locator('[data-br="again"]').click()
    expect(root.locator('.br-tier')).to_contain_text('palier max 3')


@pytest.mark.parametrize('status,text', [(401, 'reconnecte-toi'), (500, 'Erreur de test'), ('abort', 'pas de réseau')])
def test_home_says_when_the_account_stats_cannot_be_read(phone, status, text):
    """Compte connecté, /api/brain/me en échec : l'accueil le dit (au lieu d'une Température à 0 sans explication)."""
    page = phone.page
    phone.open_games()
    connect(page)
    mock_account(page, [], me_status=status)
    root = open_brain(page)
    expect(root.locator('.br-offline')).to_contain_text(text)
    page.unroute('**/api/brain/me')
    mock_account(page, [])
    root.locator('.br-top [data-br="close"]').click()
    root = open_brain(page)
    expect(root.locator('.br-offline')).to_have_count(0)


def test_connected_player_whose_session_cannot_be_renewed_is_not_told_to_log_in(phone):
    """Compte connecté, jeton expiré pendant la partie et renouvellement impossible (réseau coupé) : la partie est
    gardée et partira plus tard ; on ne lui dit pas « Connecte-toi » alors qu'il l'est."""
    page = phone.page
    phone.open_games()
    connect(page)
    mock_account(page, [])
    root = open_brain(page)
    expect(root.locator('.br-login')).to_have_count(0)
    page.route('**/api/account/refresh', lambda r: r.abort())
    page.evaluate("""() => { const k = 'sb-e2e-auth-token', s = JSON.parse(localStorage.getItem(k));
      localStorage.setItem(k, JSON.stringify({ ...s, expires_at: Math.floor(Date.now() / 1000) - 10 })); }""")
    play_stub(page, root)
    page.keyboard.press('ArrowRight')
    die(page, root)
    note = root.locator('.br-save')
    expect(note).to_contain_text('gardée sur ce téléphone', timeout=10000)
    assert 'Connecte-toi' not in note.inner_text()
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 1


def test_warmup_progress_survives_a_game_file_that_failed_to_load(phone):
    """Échauffement commencé (2/5), puis un des jeux du jour ne se charge pas (réseau) : la progression du jour reste,
    le jeu manquant est sauté, et tout revient quand le réseau revient."""
    page = phone.page
    stub_all_games(phone)
    phone.open_games()
    root = open_brain(page)
    w = page.evaluate("JSON.parse(localStorage.getItem('brain_warmup'))")
    ids = w['ids']
    page.evaluate(f"""() => localStorage.setItem('brain_warmup', JSON.stringify({{ ...{json.dumps(w)}, done: {json.dumps(ids[:2])} }}))""")
    root.locator('.br-top [data-br="close"]').click()
    missing = ids[2]
    page.route(f'**/static/brain/games/{missing}.js*', lambda r: r.abort())
    page.reload()
    page.locator('button[data-tab="games"]').first.click()
    root = open_brain(page)
    expect(root.locator('.br-warm .br-cta')).to_have_text('Continuer · 2/5')
    root.locator('.br-warm .br-cta').click()
    expect(root.locator('.br-howto .br-howto-n')).to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_warmup')).done.length") == 2
    root.locator('.br-howto .br-top [data-br="close"]').click()
    root.locator('.br-top [data-br="close"]').click()
    page.unroute(f'**/static/brain/games/{missing}.js*')
    root = open_brain(page)
    expect(root.locator('.br-warm .br-cta')).to_have_text('Continuer · 2/5')
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_warmup')).ids") == ids


def test_hud_fits_a_small_iphone_at_extreme_levels(phone):
    """iPhone SE (320 px) au niveau max (999, palier 200), ×10, gros score : rien ne déborde ni ne se chevauche dans le HUD."""
    page = phone.page
    page.set_viewport_size({'width': 320, 'height': 568})
    phone.open_games()
    root = open_brain(page)
    play_stub(page, root)
    page.evaluate("() => { for (let i = 0; i < 1100; i++) document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' })); }")
    expect(root.locator('.br-lvl')).to_have_text('Niv. 999 · Palier 200')
    expect(root.locator('.br-mult b')).to_have_text('×10')
    boxes = page.evaluate("""() => [...document.querySelectorAll('#brainRoot .br-hud > *')].filter((el) => !el.classList.contains('br-fly'))
      .map((el) => { const r = el.getBoundingClientRect(); return { c: el.className, l: r.left, r: r.right, sw: el.scrollWidth, cw: el.clientWidth }; })""")
    width = page.evaluate('innerWidth')
    for b in boxes:
        assert b['l'] >= -0.5 and b['r'] <= width + 0.5, boxes
    ordered = sorted(boxes, key=lambda b: b['l'])
    for a, b in zip(ordered, ordered[1:]):
        assert a['r'] <= b['l'] + 1, ordered
    no_sideways_scroll(page)


def test_meninges_card_works_in_the_admin_page_too(browser, server):
    """/admin (gardé en secours) charge games.js, donc la carte Méninges, mais pas le moteur : « Faire chauffer » ne
    faisait rien. Le moteur se charge à la demande."""
    from tests.e2e.helpers import ADMIN_PIN
    ctx = browser.new_context(base_url=server.url, viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                              locale='fr-CH')
    ctx.add_init_script("localStorage.setItem('vp_install_dismissed', '1'); localStorage.setItem('vp_name', 'Hôte');")
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('/admin')
    page.locator('input[type=password], #pin').first.fill(ADMIN_PIN)
    page.keyboard.press('Enter')
    expect(page.locator('#tabs')).to_be_visible()
    page.locator('#tabs button[data-tab="games"]').first.click()
    btn = page.locator('#gHome section[data-cat="brain"] [data-brain-open]')
    expect(btn).to_be_visible()
    btn.click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    assert root.evaluate('el => getComputedStyle(el).position') == 'fixed'   # brain.css chargé aussi
    root.locator('.br-top [data-br="close"]').click()
    expect(root).to_be_hidden()
    ctx.close()
    assert not errors, errors
