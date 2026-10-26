"""Retours du 26.10 sur les jeux, de bout en bout (vrais boutons, vrais téléphones) :
- Qui de nous ? : une fois voté, la grille se cache (le choix n'est plus lisible) et le vote est définitif ;
- passer la main ne fait plus quitter la partie : l'ancien animateur reste joueur ;
- l'admin qui rejoint une partie par son code y est vraiment joueur (et garde ses droits d'animateur) ;
- le compteur de gorgées en haut à droite est translucide et laisse passer les touchers."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import ADMIN_PIN, Phone, Server, wait_state


@pytest.fixture
def phones(browser):
    server = Server()
    made = []

    def make(name, device='iphone'):
        p = Phone(browser, server, name, device)
        made.append(p)
        return p
    yield make
    errors = [e for p in made for e in p.errors]
    for p in made:
        p.close()
    server_errors = server.errors()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def start_whoof(phones):
    """Partie « Qui de nous ? » à deux (2 gorgées pour le désigné, réglage par défaut)."""
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('whoof')
    bob.join(code)
    wait_state(alice, lambda g: len(g['players']) == 2)
    alice.tap('[data-gact="start"]')
    expect(alice.page.locator('.qs-q')).to_contain_text('Qui de nous')
    return alice, bob


def test_whoof_vote_hides_the_grid_and_cannot_be_changed(phones):
    alice, bob = start_whoof(phones)
    expect(alice.page.locator('.qs-pick')).to_have_count(2)
    alice.page.locator('.qs-pick', has_text='Bob').click()
    expect(alice.page.locator('.qs-help')).to_contain_text('Vote enregistré')
    expect(alice.page.locator('.qs-pick')).to_have_count(0)  # personne ne lit le choix par-dessus l'épaule
    assert 'Bob' not in alice.page.locator('.qs-help').inner_text()
    # Même en contournant l'écran, le serveur refuse un second vote.
    bob_pid = next(p['pid'] for p in alice.state()['players'] if p['name'] == 'Bob')
    alice_pid = alice.pid()
    r = alice.act('vote', target=alice_pid)
    assert r and 'déjà' in str(r).lower(), r
    bob.page.locator('.qs-pick', has_text='Moi').click()
    expect(alice.page.locator('.qs-win-n')).to_contain_text('2 votes')
    assert bob_pid


def test_handing_over_keeps_the_former_host_in_the_game(phones):
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('never')
    bob.join(code)
    wait_state(alice, lambda g: len(g['players']) == 2)
    alice.tap('[data-gdrawer="open"]')
    alice.tap('[data-exit="pick"]')
    expect(alice.page.locator('.g-handover')).to_contain_text('Tu restes dans la partie')
    alice.page.once('dialog', lambda d: d.accept())
    alice.tap('[data-exit="to"]')
    expect(bob.page.locator('[data-gact="start"]')).to_be_visible()  # Bob anime
    s = wait_state(alice, lambda g: not g['is_host'])
    assert s['me'] and [p['name'] for p in s['players']] == ['Alice', 'Bob']
    expect(alice.page.locator('#gamePlay')).to_be_visible()  # toujours dans la partie
    bob.tap('[data-gact="start"]')
    expect(alice.page.locator('.qs-opt')).to_have_count(2)  # elle répond comme les autres


def test_admin_joining_by_code_is_a_real_player(phones):
    alice, boss = phones('Alice'), phones('Boss', 'android')
    code = alice.create('whoof')
    boss.page.request.post(f"{boss.server.url}/api/admin/login", data={"pin": ADMIN_PIN})
    boss.open_games()
    boss.page.locator('#gCode').fill(code)
    s = wait_state(boss, lambda g: g.get('me'))
    assert s['is_host'] and not s['is_owner']  # droits d'animateur gardés
    assert [p['name'] for p in s['players']] == ['Alice', 'Boss']
    alice.tap('[data-gact="start"]')
    expect(boss.page.locator('.qs-pick')).to_have_count(2)  # il vote comme tout le monde


def test_sips_counter_is_translucent_and_lets_taps_through(phones):
    alice, bob = start_whoof(phones)
    alice.page.locator('.qs-pick', has_text='Moi').click()
    bob.page.locator('.qs-pick', has_text='Alice').click()
    hud = alice.page.locator('#gameHud')
    expect(hud).to_be_visible()
    style = hud.evaluate("e => { const s = getComputedStyle(e); return [s.pointerEvents, s.backgroundColor]; }")
    assert style[0] == 'none'
    alpha = float(style[1].split(',')[-1].rstrip(')')) if style[1].startswith('rgba') else 1.0
    assert alpha < 0.5, style
