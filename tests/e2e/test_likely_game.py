"""« Qui est le plus… ? » de bout en bout (vrais boutons) : chacun vote en même temps sur son téléphone, le téléphone
de l'animateur passe à ceux qui n'en ont pas, vote secret et définitif, révélation."""
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
    """Le téléphone de l'animateur passe à `voter` (sans téléphone) : « C'est moi », puis il désigne `target` en secret."""
    page = phone.page
    expect(page.locator('.lk-pass .lk-name')).to_have_text(voter)
    page.locator('[data-lk-ready]').click()
    expect(page.locator('.lk-who')).to_contain_text(voter)
    page.locator('.lk-pick', has_text=target).first.click()


def vote_on_own_phone(phone, target, last=False):
    page = phone.page
    expect(page.locator('.lk-who')).to_contain_text('Qui désignes-tu')
    page.locator('.lk-pick', has_text=target).first.click()
    if not last:  # le dernier vote révèle aussitôt le résultat
        expect(page.locator('.lk-done')).to_contain_text('Vote enregistré')
    expect(page.locator('.lk-grid')).to_have_count(0)  # le choix n'est plus visible


def test_host_votes_then_passes_the_phone_to_people_without_phone(phones):
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

    vote_on_own_phone(alice, 'Papa')
    # Le vote d'Alice est caché aussitôt : son téléphone passe à Papa (sans téléphone).
    expect(alice.page.locator('.lk-pass .lk-name')).to_have_text('Papa')
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
    vote_on_own_phone(alice, 'Maman')
    expect(alice.page.locator('[data-gact="lkswap"]')).to_have_count(0)
    alice.tap('.lk-pass [data-gact="lkskip"]')
    vote_on_shared_phone(alice, 'Maman', 'Maman')
    expect(alice.page.locator('.lk-win-t')).to_have_text('🫵 Maman')
    s = alice.state()
    assert {p['name']: p['drink'] for p in s['players']} == {'Alice': 0, 'Papa': 1, 'Maman': 1}


def test_everyone_with_a_phone_votes_at_the_same_time(phones):
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('likely')
    bob.join(code)  # le lien du QR code l'inscrit d'office
    wait_state(alice, lambda g: len(g['players']) == 2)
    expect(bob.page.locator('.lk-card')).to_contain_text('Tu es inscrit')
    alice.tap('[data-gact="start"]')

    # Pas de tour : Bob vote le premier, sur son téléphone, sans attendre Alice.
    vote_on_own_phone(bob, 'Alice')
    expect(bob.page.locator('.lk-win-t')).to_have_count(0)
    # L'animatrice voit qui réfléchit encore… puis vote elle aussi.
    vote_on_own_phone(alice, 'Alice', last=True)
    for p in (alice, bob):
        expect(p.page.locator('.lk-win-t')).to_have_text('🫵 Alice')
        expect(p.page.locator('.lk-win-s')).to_have_text('prend 1 point')
    expect(bob.page.locator('[data-gact="next"]')).to_have_count(0)  # seul l'animateur avance


def test_host_passes_a_guest_whose_phone_is_away(phones):
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('likely')
    bob.join(code)
    wait_state(alice, lambda g: len(g['players']) == 2)
    alice.tap('[data-gact="start"]')
    vote_on_own_phone(alice, 'Bob')
    expect(alice.page.locator('.lk-waiting')).to_contain_text('Réfléchissent encore')
    alice.tap('[data-gact="lkskip"][data-target]')
    expect(alice.page.locator('.lk-win-t')).to_have_text('🫵 Bob')


def test_home_card_offers_friends_pack_and_rules(phones):
    alice = phones('Alice', 'desktop')
    alice.create('likely', lkfriends=True)
    assert alice.state()['likely']['packs'] == ['family', 'friends']
    alice.page.locator('#gTop [data-rules="likely"]').click()
    expect(alice.page.locator('#rulesTitle')).to_have_text('Qui est le plus… ?')
    expect(alice.page.locator('#rulesBody')).to_contain_text('jamais qui a voté pour qui')
