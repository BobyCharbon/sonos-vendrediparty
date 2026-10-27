"""Président à la table (vrai navigateur) : le dernier coup est en surbrillance et les coups précédents du pli en
cours restent visibles en dessous ; un nouveau pli repart de zéro."""
import httpx
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


@pytest.fixture
def table(browser):
    server = Server()
    phones = [Phone(browser, server, name) for name in ('Alice', 'Bob', 'Chloe')]
    yield server, phones
    errors = [e for p in phones for e in p.errors]
    for p in phones:
        p.close()
    server_errors = server.errors()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def move(server, phone, action, cards=()):
    pres = phone.state()['president']
    r = httpx.post(f'{server.url}/api/games/{phone.code}', json={
        'guest_id': phone.gid, 'name': phone.name, 'action': action, 'values': list(cards), 'guess': pres['token']}, timeout=10)
    assert r.status_code == 200, r.text


def lowest_single(phone, above):
    """Plus petite carte seule (sans joker ni 2, qui fermerait le pli) au-dessus de la valeur, ou None."""
    hand = phone.state()['president']['hand']
    return next((c['id'] for c in hand if not c['joker'] and above < c['value'] < 12), None)


def test_last_play_is_highlighted_and_previous_plays_of_the_trick_stay_visible(table):
    server, (alice, bob, chloe) = table
    code = alice.create('president')
    for p in (bob, chloe):
        p.join(code)
    wait_state(alice, lambda g: len(g['players']) == 3)
    alice.tap('[data-gact="start"]')
    wait_state(alice, lambda g: g['phase'] == 'play')
    phones = {p.pid(): p for p in (alice, bob, chloe)}

    played = []  # coups du pli en cours : (prénom, carte)
    for _ in range(15):
        if len(played) == 3:
            break
        pres = alice.state()['president']
        who = phones[pres['turn']]
        pile = pres['pile']
        card = lowest_single(who, pile['value'] if pile else -1)
        if card and (not pile or len(pile['cards']) == 1):
            move(server, who, 'prplay', [card])
            played.append((who.name, card))
        else:
            move(server, who, 'prpass')
        if alice.state()['president']['pile'] is None:
            played = []  # pli ramassé : on repart de zéro, comme la table
    assert len(played) == 3

    page = alice.page
    expect(page.locator('.pr-pile.pr-latest')).to_be_visible()
    expect(page.locator('.pr-last-tag')).to_have_text('Dernier coup')
    expect(page.locator('.pr-table-caption')).to_contain_text(played[-1][0])
    items = page.locator('.pr-trail-item')
    expect(items).to_have_count(2)
    expect(items.nth(0)).to_contain_text(played[1][0])  # du plus récent au plus ancien
    expect(items.nth(1)).to_contain_text(played[0][0])
    alice.shot('president-trail')
