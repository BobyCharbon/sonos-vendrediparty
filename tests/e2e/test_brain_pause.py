"""Méninges : pause commune du moteur (core.js, ctx.onPause / ctx.onResume) et niveaux au-delà de 99.

- application en arrière-plan : aucun des 15 jeux ne fait perdre de vie loin de l'écran, la partie reprend au retour ;
  pour Débuts de mots, le chrono de la manche s'arrête ; le temps caché ne compte pas dans l'arrêt des 30 minutes ;
- question « Quitter la partie ? » : le jeu est en pause derrière (aucune vie perdue), il reprend sur « Continuer » ;
- niveaux : un palier de départ haut (palier 60 = niveau 296) est proposé, affiché et compté (plus de plafond à 99).
Joueur passif (aucune réponse) : s'il perd une vie après le retour, c'est que le jeu a bien repris.
Banc d'essai : tests/e2e/test_brain_qa_jeux_b.py (vrai moteur, fichiers servis depuis app/static, horloge simulée)."""
import pytest
pytest.importorskip('playwright.sync_api')

from tests.e2e.test_brain_qa_jeux_b import Bench

ALL_GAMES = ('pareil', 'motif', 'autoroute', 'grille', 'deux_avant', 'tresor', 'nuee', 'aiguillage',
             'intrus', 'encre', 'bascule', 'courant', 'balance', 'gouttes', 'syllabes')
JEUX_B = ('aiguillage', 'encre', 'bascule', 'courant', 'balance', 'gouttes', 'syllabes')
HIDE_JS = """(h) => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => h ? 'hidden' : 'visible' });
  document.dispatchEvent(new Event('visibilitychange'));
}"""
AWAY_MS = 90_000               # plus long que toute manche (30 s), toute carte, toute chute
BACK_MS = 120_000              # un joueur passif perd une vie bien avant (Débuts de mots : manche de 30 s)
STEP_MS = 2000


@pytest.fixture
def bench(browser):
    made = []

    def make(device='iphone'):
        b = Bench(browser, device)
        made.append(b)
        return b
    yield make
    errors = [e for b in made for e in b.errors]
    for b in made:
        b.close()
    assert not errors, '\n'.join(errors[:20])


def lives(b):
    label = b.page.get_attribute('#brainRoot .br-lives', 'aria-label')
    return int(label.split()[0])


def warm_up(b, game):
    """Partie en cours (dictionnaire chargé pour Débuts de mots), sans vie perdue."""
    b.start(game, mode='passif')
    b.page.evaluate('() => clearInterval(window.__qa.timer)')   # joueur passif : le robot n'a rien à faire
    b.page.clock.run_for(1500)
    if game == 'syllabes':
        b.page.wait_for_selector('#brainRoot .br-syllabes-input:not([disabled])')
    assert b.screen() == 'play' and lives(b) == 3


def goes_on(b, game):
    """Après la reprise, le joueur passif finit par perdre une vie : le jeu tourne de nouveau."""
    for _ in range(BACK_MS // STEP_MS):
        b.page.clock.run_for(STEP_MS)
        if b.screen() != 'play' or lives(b) < 3:
            return
    pytest.fail(f'{game} : le jeu ne reprend pas après la pause')


@pytest.mark.parametrize('game', JEUX_B)
def test_background_costs_no_life_and_the_game_goes_on(bench, game):
    b = bench()
    warm_up(b, game)
    b.page.evaluate(HIDE_JS, True)
    b.page.clock.run_for(AWAY_MS)
    assert b.screen() == 'play', f'{game} : partie finie pendant l’arrière-plan'
    assert lives(b) == 3, f'{game} : vie perdue loin de l’écran'
    b.page.evaluate(HIDE_JS, False)
    b.page.clock.run_for(1000)
    assert lives(b) == 3, f'{game} : vie perdue juste au retour (le temps caché a compté)'
    goes_on(b, game)


@pytest.mark.parametrize('game', ALL_GAMES)
def test_quit_question_pauses_the_game_and_continue_resumes_it(bench, game):
    b = bench()
    warm_up(b, game)
    b.page.click('#brainRoot [data-br="quit"]')
    b.page.clock.run_for(AWAY_MS)
    assert b.page.is_visible('#brainRoot .br-confirm'), f'{game} : la question a disparu'
    assert b.screen() == 'play' and lives(b) == 3, f'{game} : vie perdue derrière « Quitter la partie ? »'
    b.page.click('#brainRoot [data-br="stay"]')
    b.page.clock.run_for(1000)
    assert lives(b) == 3
    goes_on(b, game)


def test_syllabes_round_clock_keeps_its_time_left_while_hidden(bench):
    b = bench()
    warm_up(b, 'syllabes')
    b.page.clock.run_for(20_000)                       # 20 s de la manche de 30 s
    b.page.evaluate(HIDE_JS, True)
    b.page.clock.run_for(AWAY_MS)
    b.page.evaluate(HIDE_JS, False)
    b.page.clock.run_for(6000)                         # il restait ~8 s : la manche continue
    assert lives(b) == 3 and b.page.inner_text('#brainRoot .br-syllabes-rn') == 'Manche 1'
    b.page.clock.run_for(6000)                         # puis le temps s'écoule normalement
    assert lives(b) == 2


def test_hidden_time_does_not_count_in_the_30_minute_stop(bench):
    b = bench()
    warm_up(b, 'encre')
    b.page.evaluate(HIDE_JS, True)
    b.page.clock.fast_forward(31 * 60_000)           # page cachée : les minuteurs ne tournent presque plus
    b.page.clock.run_for(500)
    b.page.evaluate(HIDE_JS, False)
    b.page.clock.run_for(500)
    assert b.screen() == 'play', 'partie coupée à 30 min alors que la page était cachée'


def test_a_tier_60_start_plays_and_counts_level_296(bench):
    """Les jeux montent à 250+ : palier 60 (niveau 296) proposé, affiché dans le HUD et sur l'écran de fin."""
    b = bench()
    b.start('encre', mode='passif', tier=60)
    assert b.page.inner_text('#brainRoot .br-lvl') == 'Niv. 296 · Palier 60'
    for _ in range(30):
        b.page.clock.run_for(STEP_MS)
        if b.screen() == 'end':
            break
    end = b.page.inner_text('#brainRoot .br-end')
    assert '296 · palier 60' in end, end
