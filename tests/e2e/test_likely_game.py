"""« Qui est le plus… ? » de bout en bout : un seul téléphone qui tourne (vrais boutons), vote secret, révélation."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


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


def add_guest(phone, name):
    field = phone.page.locator('#gameHost [data-gform="addguest"] input')
    field.fill(name)
    field.press('Enter')
    expect(phone.page.locator('#gameHost')).to_contain_text(name)


def vote_on_shared_phone(phone, voter, target):
    """Le téléphone passe à `voter` : il touche « C'est moi », puis désigne `target` en secret."""
    page = phone.page
    expect(page.locator('.lk-name')).to_have_text(voter)
    page.locator('[data-lk-ready]').click()
    expect(page.locator('.lk-who')).to_contain_text(voter)
    page.locator('.lk-pick', has_text=target).first.click()


def test_one_phone_goes_round_the_table_and_reveals_the_most_designated(phones):
    alice = phones('Alice')
    alice.create('likely', lkalcohol=True)
    expect(alice.page.locator('.lk-hero')).to_be_visible()
    add_guest(alice, 'Papa')
    add_guest(alice, 'Maman')
    alice.tap('[data-lk-count="10"]')
    wait_state(alice, lambda g: g['likely']['count'] == 10 and len(g['players']) == 3)

    alice.tap('[data-gact="start"]')
    expect(alice.page.locator('.lk-q-n')).to_have_text('Question 1/10')
    question = alice.page.locator('.lk-q-t').inner_text()
    assert question.startswith('Qui ')

    vote_on_shared_phone(alice, 'Alice', 'Papa')
    # Le vote d'Alice est caché aussitôt : l'écran attend le joueur suivant.
    expect(alice.page.locator('.lk-name')).to_have_text('Papa')
    expect(alice.page.locator('.lk-pick')).to_have_count(0)
    expect(alice.page.locator('.lk-dots i.on')).to_have_count(1)
    vote_on_shared_phone(alice, 'Papa', 'Papa')
    vote_on_shared_phone(alice, 'Maman', 'Alice')

    expect(alice.page.locator('.lk-win-t')).to_have_text('🫵 Papa')
    expect(alice.page.locator('.lk-win-s')).to_have_text('boit 1 gorgée')
    expect(alice.page.locator('.lk-bar')).to_have_count(2)
    expect(alice.page.locator('.lk-bar').first).to_contain_text('Papa')
    expect(alice.page.locator('.lk-bar').first).to_contain_text('2')
    alice.tap('[data-gact="next"]')
    expect(alice.page.locator('.lk-q-n')).to_have_text('Question 2/10')
    assert alice.page.locator('.lk-q-t').inner_text() != question

    # Quelqu'un est parti : on le passe ; changer de question n'est possible qu'avant le premier vote.
    expect(alice.page.locator('[data-gact="lkswap"]')).to_be_visible()
    vote_on_shared_phone(alice, 'Alice', 'Maman')
    expect(alice.page.locator('[data-gact="lkswap"]')).to_have_count(0)
    alice.tap('[data-gact="lkskip"]')
    vote_on_shared_phone(alice, 'Maman', 'Maman')
    expect(alice.page.locator('.lk-win-t')).to_have_text('🫵 Maman')
    s = alice.state()
    assert {p['name']: p['drink'] for p in s['players']} == {'Alice': 0, 'Papa': 1, 'Maman': 1}


def test_a_guest_with_a_phone_votes_on_it_and_sees_only_the_turn_of_others(phones):
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('likely')
    bob.join(code)  # le lien du QR code l'inscrit d'office
    wait_state(alice, lambda g: len(g['players']) == 2)
    expect(bob.page.locator('.lk-card')).to_contain_text('Tu es inscrit')
    alice.tap('[data-gact="start"]')

    # Au tour d'Alice : Bob voit seulement que le téléphone tourne.
    expect(bob.page.locator('.lk-card')).to_contain_text('au tour de')
    expect(bob.page.locator('.lk-pick')).to_have_count(0)
    vote_on_shared_phone(alice, 'Alice', 'Bob')

    # Au tour de Bob : il vote directement sur son téléphone ; celui d'Alice attend.
    expect(bob.page.locator('.lk-who')).to_contain_text('Bob')
    bob.page.locator('.lk-pick', has_text='Bob').first.click()
    for p in (alice, bob):
        expect(p.page.locator('.lk-win-t')).to_have_text('🫵 Bob')
        expect(p.page.locator('.lk-win-s')).to_have_text('prend 1 point')
    expect(bob.page.locator('[data-gact="next"]')).to_have_count(0)  # seul l'animateur avance


def test_home_card_offers_friends_pack_and_rules(phones):
    alice = phones('Alice', 'desktop')
    alice.create('likely', lkfriends=True)
    assert alice.state()['likely']['packs'] == ['family', 'friends']
    alice.page.locator('#gTop [data-rules="likely"]').click()
    expect(alice.page.locator('#rulesTitle')).to_have_text('Qui est le plus… ?')
    expect(alice.page.locator('#rulesBody')).to_contain_text('jamais qui a voté pour qui')
