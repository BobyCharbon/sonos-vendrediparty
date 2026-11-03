"""Méninges (vrai navigateur, iPhone) : la carte de l'onglet Jeux ouvre le panneau, l'accueil montre la Température,
l'Échauffement et les jeux ; on lance un vrai jeu, on répond puis on ne joue plus : faute de réponse, les 3 vies
partent et l'écran de fin s'affiche avec score, précision et bonus. Sans compte : la partie est gardée sur le téléphone.
Moteur sans fin (contrat v2) avec un jeu factice : vies, +1 vie après 15 bonnes, ctx.slip, paliers (annonce, mémoire,
palier de départ), fin de partie à 0 vie."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

# Jeux qui se jouent au clavier (flèches) : un joueur qui ne répond plus y perd ses 3 vies.
KEYBOARD_GAMES = ('pareil', 'encre', 'bascule', 'courant', 'deux_avant', 'motif', 'intrus', 'nuee', 'balance', 'autoroute')


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Boby')
    p.page.clock.install()
    yield p
    errors, server_errors = p.errors, server.errors()
    p.close()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def test_open_play_a_game_and_see_the_end_screen(phone):
    page = phone.page
    phone.open_games()
    card = page.locator('#gHome section[data-cat="brain"] .gcard.g-br')
    expect(card).to_be_visible()
    expect(card.locator('[data-brain-name]')).to_have_text('Méninges')
    card.locator('[data-brain-open]').click()

    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    expect(root.locator('.br-title')).to_contain_text('Méninges')
    expect(root.locator('.br-temp b')).to_have_text('0')
    expect(root.locator('.br-login')).to_contain_text('Connecte-toi')
    assert root.evaluate('el => getComputedStyle(el).position') == 'fixed'
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
    ids = page.evaluate('Brain.list().map(g => g.id)')
    game = next((g for g in KEYBOARD_GAMES if g in ids), None)
    assert game, f'aucun jeu au clavier chargé : {ids}'
    assert 1 <= root.locator('.br-warm-row li').count() <= 5

    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    expect(root.locator('.br-howto .br-rules li').first).to_be_visible()
    root.locator('[data-br="go"]').click()
    expect(root.locator('.br-count-n')).to_be_visible()
    page.clock.run_for(3000)  # 3-2-1
    expect(root.locator('.br-hud')).to_be_visible()
    expect(root.locator('#brStage')).not_to_be_empty()
    page.keyboard.press('ArrowRight')  # une réponse au clavier (Oui), juste ou fausse selon la partie
    page.clock.run_for(2000)
    page.keyboard.press('ArrowLeft')
    page.clock.run_for(70_000)  # plus de réponse : les 3 vies partent

    end = root.locator('.br-end')
    expect(end).to_be_visible()
    expect(end.locator('.br-bonus')).to_contain_text('bonus ×')
    expect(end.locator('.br-stat').first).to_contain_text('Précision')
    expect(end.locator('.br-save')).to_contain_text('Connecte-toi', timeout=10000)
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 1
    assert page.evaluate(f"JSON.parse(localStorage.getItem('brain_levels'))['{game}']") >= 1

    end.locator('[data-br="home"]').click()
    expect(root.locator(f'[data-br="play"][data-id="{game}"] .br-tile-s')).to_contain_text('Record')
    root.locator('.br-top [data-br="close"]').click()
    expect(root).to_be_hidden()
    expect(page.locator('#gHome')).to_be_visible()


# ── Moteur sans fin, avec un jeu factice à la place de « Pareil ? » (indépendant des vrais jeux) ──
# → : bonne réponse (et niveau suivant) ; ← : petite erreur (ctx.slip) ; ↓ : erreur ; 2 s sans réponse : erreur.
STUB = """Brain.register({ id: "pareil", name: "Pareil ?", domain: "vitesse", icon: "🟰", seconds: null, howto: ["Jeu factice."],
  start(ctx) {
    let level = ctx.level, timer = null;
    const arm = () => { clearTimeout(timer); timer = setTimeout(() => { ctx.miss(); arm(); }, 2000); };
    const key = (ev) => {
      if (ev.key === "ArrowRight") { ctx.hit({ rt: 500 }); level += 1; ctx.setLevel(level); arm(); }
      else if (ev.key === "ArrowLeft") ctx.slip({ rt: 500 });
      else if (ev.key === "ArrowDown") { ctx.miss(); arm(); }
    };
    document.addEventListener("keydown", key);
    ctx.root.innerHTML = '<p class="stub">Jeu factice</p>';
    window.__stub = { starts: (window.__stub?.starts || 0) + 1, level: ctx.level, stops: window.__stub?.stops || 0 };
    arm();
    return { stop() { clearTimeout(timer); document.removeEventListener("keydown", key); window.__stub.stops += 1; } };
  } });"""


@pytest.fixture
def stub(phone):
    phone.page.route('**/static/brain/games/pareil.js*', lambda r: r.fulfill(status=200, body=STUB,
                                                                            content_type='application/javascript'))
    return phone


def start_stub(page):
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    root.locator('[data-br="play"][data-id="pareil"]').click()
    return root


def go(page, root):
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)
    expect(root.locator('.br-hud')).to_be_visible()
    expect(root.locator('.stub')).to_be_visible()


def lost(root):
    return root.locator('.br-lives .br-heart.lost').count()


def press(page, key, n=1):
    for _ in range(n):
        page.keyboard.press(key)


def test_endless_game_lives_tiers_and_the_end_at_zero_life(stub):
    page = stub.page
    stub.open_games()
    root = start_stub(page)
    howto = root.locator('.br-howto')
    expect(howto.locator('.br-common')).to_contain_text('Tu as 3 vies')
    expect(howto.locator('.br-tier-one')).to_contain_text('Départ : palier 1')
    expect(howto.locator('.br-chip-dom')).to_contain_text('3 vies')
    go(page, root)
    hud = root.locator('.br-hud')
    expect(hud.locator('.br-heart')).to_have_count(3)
    expect(hud.locator('.br-lvl')).to_have_text('Niv. 1 · Palier 1')
    assert hud.locator('.br-time').count() == 0  # plus de chrono global
    assert page.evaluate('window.__stub.level') == 1

    press(page, 'ArrowRight', 5)  # niveau 6 : palier 2 débloqué
    expect(root.locator('.br-tierup')).to_contain_text('Palier 2 débloqué')
    expect(hud.locator('.br-lvl')).to_have_text('Niv. 6 · Palier 2')
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_tiers')).pareil") == 2
    press(page, 'ArrowLeft')       # petite erreur : pas de vie perdue, la jauge repart de zéro
    assert lost(root) == 0 and root.locator('.br-gauge4 i.on').count() == 0
    press(page, 'ArrowDown')       # erreur : une vie de moins
    assert lost(root) == 1
    page.clock.run_for(60_000)     # plus de réponse : les 2 dernières vies partent, la partie s'arrête
    end = root.locator('.br-end')
    expect(end).to_be_visible()
    assert page.evaluate('window.__stub.stops') == 1  # le jeu est arrêté une seule fois, rien ne tourne après
    expect(end.locator('.br-reason')).to_contain_text('Plus de vie')
    expect(end.locator('.br-tier-new')).to_contain_text('Palier 2 débloqué')
    stats = end.locator('.br-stat')
    expect(stats.filter(has_text='Niveau max')).to_contain_text('6 · palier 2')
    expect(stats.filter(has_text='Palier max')).to_contain_text('2')
    expect(stats.filter(has_text='Bonnes / erreurs')).to_contain_text('5 / 4')
    expect(stats.filter(has_text='Précision')).to_contain_text('56 %')  # 5 bonnes sur 9 gestes (slip compris)
    saved = page.evaluate("JSON.parse(localStorage.getItem('brain_local'))")
    assert len(saved) == 1 and saved[0]['level'] == 6 and saved[0]['game'] == 'pareil'

    # Rejouer : départ au plus haut palier débloqué (niveau 6), ou plus bas au choix.
    end.locator('[data-br="again"]').click()
    picker = root.locator('.br-howto .br-tier')
    expect(picker).to_contain_text('Départ : palier 2')
    expect(picker).to_contain_text('niveau 6')
    root.locator('[data-br="tier-down"]').click()
    expect(root.locator('.br-tier')).to_contain_text('Départ : palier 1')
    root.locator('[data-br="tier-up"]').click()
    expect(root.locator('.br-tier')).to_contain_text('Départ : palier 2')
    go(page, root)
    assert page.evaluate('window.__stub.level') == 6
    expect(root.locator('.br-lvl')).to_have_text('Niv. 6 · Palier 2')
    press(page, 'ArrowRight', 4)   # niveau 10 : encore le palier 2, déjà connu → pas de nouvelle annonce
    expect(root.locator('.br-tierup')).to_have_count(0)
    root.locator('[data-br="quit"]').click()
    root.locator('[data-br="leave"]').click()
    expect(root.locator('.br-home')).to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 1  # partie quittée : pas comptée
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'


def test_15_good_answers_in_a_row_give_back_a_life_up_to_3(stub):
    page = stub.page
    stub.open_games()
    root = start_stub(page)
    go(page, root)
    press(page, 'ArrowDown', 2)
    assert lost(root) == 2
    press(page, 'ArrowRight', 14)
    assert lost(root) == 2
    press(page, 'ArrowRight')      # 15e d'affilée : +❤️
    assert lost(root) == 1
    expect(root.locator('.br-fly.life')).to_have_text('+❤️')
    press(page, 'ArrowRight', 10)
    press(page, 'ArrowLeft')       # une petite erreur casse la série
    press(page, 'ArrowRight', 14)
    assert lost(root) == 1
    press(page, 'ArrowRight')
    assert lost(root) == 0
    press(page, 'ArrowRight', 15)  # déjà 3 vies : jamais plus de 3
    expect(root.locator('.br-heart')).to_have_count(3)
    assert lost(root) == 0
    expect(root.locator('.br-mult b')).to_have_text('×10')


def test_tier_reached_in_an_earlier_game_comes_from_the_stats(stub):
    """Palier connu par les parties (profil : max_tier), pas seulement par ce téléphone : niveau 12 → palier 3."""
    page = stub.page
    stub.open_games()
    page.evaluate("""() => localStorage.setItem('brain_local', JSON.stringify([{ game: 'pareil', score: 900, accuracy: 0.8,
      avg_rt_ms: 700, level: 12, duration_ms: 60000, played_at: new Date().toISOString() }]))""")
    root = start_stub(page)
    expect(root.locator('.bd-sheet')).to_be_visible()     # déjà joué : la fiche d'abord
    expect(root.locator('.bd-sheet .br-stat').filter(has_text='Palier max')).to_contain_text('3')
    root.locator('.bd-sheet [data-br="again"]').click()
    expect(root.locator('.br-tier')).to_contain_text('Départ : palier 3')
    expect(root.locator('.br-tier')).to_contain_text('niveau 11')
    go(page, root)
    assert page.evaluate('window.__stub.level') == 11
