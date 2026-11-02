"""« Le Masque » et « Le Reflet » de bout en bout (vrais boutons, trois téléphones) : écrire en secret, deviner qui a
écrit quoi, lever ou garder son masque, révélation ; choisir une affirmation et parier, voter en secret, compteur."""
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


def table(phones, kind, extra=0):
    alice, bob, chloe = phones('Alice'), phones('Bob', 'android'), phones('Chloe')
    others = [phones(f'Dan{i}') for i in range(extra)]
    code = alice.create(kind)
    for p in (bob, chloe, *others):
        p.join(code)
    wait_state(alice, lambda g: len(g['players']) == 3 + extra)
    return (alice, bob, chloe, *others)


def write(phone, text):
    phone.tap('[data-ms-compose]')
    phone.page.locator('.ms-sheet textarea').fill(text)
    phone.page.locator('.ms-sheet button[type="submit"]').click()
    expect(phone.page.locator('.ms-sheet')).to_have_count(0)


def test_masque_secret_answers_guesses_and_a_lifted_mask(phones):
    alice, bob, chloe = table(phones, 'masque')
    expect(alice.page.locator('.ms-hero')).to_be_visible()
    alice.tap('[data-gact="start"]')
    question = alice.page.locator('.ms-q-t').inner_text()
    expect(bob.page.locator('.ms-q-t')).to_have_text(question)

    write(alice, "La mer <b>en hiver</b>")
    expect(alice.page.locator('.ms-mine-t')).to_contain_text('<b>en hiver</b>')  # texte échappé, jamais du HTML
    expect(bob.page.locator('body')).not_to_contain_text('La mer')  # secret tant que tout le monde n'a pas écrit
    write(bob, "Le bruit du train de nuit")
    write(chloe, "Ma grand-mère qui chante")

    for p in (alice, bob, chloe):
        expect(p.page.locator('.ms-slot')).to_have_count(3)
    # Bob devine Alice pour « La mer… » et lève son masque ; les autres envoient sans deviner.
    sea = bob.page.locator('.ms-slot', has_text='La mer')
    sea.locator('.ms-name', has_text='Alice').click()
    expect(sea.locator('.ms-name.on')).to_have_text('Alice')
    bob.tap('[data-ms-unmask="1"]')
    bob.tap('[data-ms-send]')
    expect(bob.page.locator('.lk-done')).to_contain_text('Choix envoyés')
    alice.tap('[data-ms-unmask="1"]')
    alice.tap('[data-ms-send]')
    chloe.tap('[data-ms-unmask="0"]')
    chloe.tap('[data-ms-send]')

    for p in (alice, bob, chloe):
        expect(p.page.locator('.ms-slot.open')).to_have_count(2)
        expect(p.page.locator('.ms-slot.masked')).to_contain_text('Reste masqué')
        expect(p.page.locator('.ms-slot.masked')).not_to_contain_text('Chloe')  # le masque gardé ne trahit personne
    expect(bob.page.locator('.ms-slot', has_text='La mer')).to_contain_text("Tu l'avais trouvé")
    expect(alice.page.locator('.ms-slot', has_text='La mer')).to_contain_text('Trouvé par Bob')
    alice.tap('[data-gact="next"]')
    expect(chloe.page.locator('.ms-q-n')).to_contain_text('Question 2/8')


def test_reflet_pick_bet_secret_votes_and_the_counter(phones):
    alice, bob, chloe, dan = table(phones, 'reflet', extra=1)
    alice.tap('[data-gact="start"]')
    expect(alice.page.locator('[data-rf-pick]')).to_have_count(3)
    expect(bob.page.locator('.rf-mirror')).to_contain_text('Alice')
    expect(bob.page.locator('[data-rf-pick]')).to_have_count(0)  # seul le joueur devant le miroir choisit
    alice.tap('[data-rf-pick]', 1)
    alice.tap('[data-rf-bet="1"]')
    alice.tap('[data-rf-go]')
    card = alice.page.locator('.rf-card-t').inner_text()
    expect(chloe.page.locator('.rf-card-t')).to_have_text(card)
    expect(alice.page.locator('.lk-done')).to_contain_text('1 « oui »')

    bob.tap('[data-rf-vote="1"]')
    expect(bob.page.locator('.lk-done')).to_contain_text('Vote enregistré')
    chloe.tap('[data-rf-vote="0"]')
    dan.tap('[data-rf-vote="0"]')
    for p in (alice, bob, chloe):
        expect(p.page.locator('.rf-count-n')).to_contain_text('1/3')
        expect(p.page.locator('.lk-win-t')).to_have_text('🎯 Pile dans le mille !')
    alice.tap('[data-gact="next"]')
    expect(bob.page.locator('[data-rf-pick]')).to_have_count(3)  # au tour de Bob devant le miroir
