"""« Le Masque » et « Le Reflet » de bout en bout (vrais boutons, trois téléphones) : écrire en secret, deviner qui a
écrit quoi (sans jamais voir la sienne), masques levés ou gardés pour toute la table, révélation avec les votes en vert
ou rouge ; choisir une affirmation et parier, voter en secret, compteur."""
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


GREEN, RED = 'rgb(123, 216, 143)', 'rgb(255, 138, 122)'


def border(locator):
    return locator.evaluate('el => getComputedStyle(el).borderTopColor')


def write_all(alice, bob, chloe):
    write(alice, "La mer <b>en hiver</b>")
    expect(alice.page.locator('.ms-mine-t')).to_contain_text('<b>en hiver</b>')  # texte échappé, jamais du HTML
    expect(bob.page.locator('body')).not_to_contain_text('La mer')  # secret tant que tout le monde n'a pas écrit
    write(bob, "Le bruit du train de nuit")
    write(chloe, "Ma grand-mère qui chante")


def test_masque_masks_up_votes_in_green_and_red_and_ones_own_answer_never_shown(phones):
    alice, bob, chloe = table(phones, 'masque')
    expect(alice.page.locator('.ms-hero')).to_be_visible()
    expect(alice.page.locator('[data-ms-mask="open"]')).to_have_attribute('aria-pressed', 'true')  # masques levés d'office
    alice.tap('[data-gact="start"]')
    question = alice.page.locator('.ms-q-t').inner_text()
    expect(bob.page.locator('.ms-q-t')).to_have_text(question)
    write_all(alice, bob, chloe)

    # Avis du 04.11 : chacun voit les deux autres réponses, jamais la sienne (rien de jaune à repérer pour un voisin).
    for p, own in ((alice, 'La mer'), (bob, 'train de nuit'), (chloe, 'grand-mère')):
        expect(p.page.locator('.ms-slot')).to_have_count(2)
        expect(p.page.locator('#game')).not_to_contain_text(own)
        expect(p.page.locator('.ms-slot.mine, [data-ms-unmask]')).to_have_count(0)  # plus de choix du masque
    # Bob trouve Alice ; Chloé pense que « La mer… » est de Bob ; Alice ne devine rien.
    bob.page.locator('.ms-slot', has_text='La mer').locator('.ms-name', has_text='Alice').click()
    expect(bob.page.locator('.ms-slot', has_text='La mer').locator('.ms-name.on')).to_have_text('Alice')
    bob.tap('[data-ms-send]')
    expect(bob.page.locator('.lk-done')).to_contain_text('Choix envoyés')
    expect(bob.page.locator('#game')).not_to_contain_text('train de nuit')  # même après l'envoi
    chloe.page.locator('.ms-slot', has_text='La mer').locator('.ms-name', has_text='Bob').click()
    chloe.tap('[data-ms-send]')
    alice.tap('[data-ms-send]')

    for p in (alice, bob, chloe):
        sea = p.page.locator('.ms-slot', has_text='La mer')
        expect(sea.locator('.ms-author')).to_have_text("C'était Alice")  # à qui était la réponse, en clair
        expect(sea.locator('.ms-vote.right')).to_have_text('✓ Bob')  # qui a voté quoi
        expect(sea.locator('.ms-vote.wrong')).to_contain_text('Chloe pensait Bob')
        expect(p.page.locator('.ms-slot', has_text='train de nuit').locator('.ms-author')).to_have_text("C'était Bob")
        expect(p.page.locator('.ms-slot', has_text='train de nuit')).to_contain_text("Personne n'a voté")
    # Le vert ne dit que « juste » et le rouge « faux », pour qui regarde ; la coche en haut à droite.
    bob_sea = bob.page.locator('.ms-slot', has_text='La mer')
    expect(bob_sea.locator('.ms-mark.right')).to_have_text('✓')
    assert border(bob_sea) == GREEN
    chloe_sea = chloe.page.locator('.ms-slot', has_text='La mer')
    expect(chloe_sea.locator('.ms-mark.wrong')).to_have_text('✗')
    assert border(chloe_sea) == RED
    for p in (alice, bob, chloe):  # sans devinette : ni vert ni rouge
        assert border(p.page.locator('.ms-slot', has_text='grand-mère')) not in (GREEN, RED)
    assert border(alice.page.locator('.ms-slot', has_text='La mer')) not in (GREEN, RED)
    expect(bob.page.locator('body')).not_to_contain_text("Tu l'avais trouvé")
    expect(bob.page.locator('.lk-card', has_text='Points')).to_contain_text('Bob · 1')
    alice.tap('[data-gact="next"]')
    expect(chloe.page.locator('.ms-q-n')).to_contain_text('Question 2/8')


def test_masque_masks_kept_by_the_organizer_never_tell_who_wrote_what(phones):
    alice, bob, chloe = table(phones, 'masque')
    alice.tap('[data-ms-mask="closed"]')
    expect(alice.page.locator('[data-ms-mask="closed"]')).to_have_attribute('aria-pressed', 'true')
    expect(bob.page.locator('.ms-mode')).to_contain_text('Masques gardés')  # chacun sait à quoi s'attendre
    alice.tap('[data-gact="start"]')
    write_all(alice, bob, chloe)
    for p in (alice, bob, chloe):
        expect(p.page.locator('.ms-slot')).to_have_count(2)
    bob.page.locator('.ms-slot', has_text='La mer').locator('.ms-name', has_text='Alice').click()
    bob.tap('[data-ms-send]')
    chloe.page.locator('.ms-slot', has_text='La mer').locator('.ms-name', has_text='Alice').click()
    chloe.tap('[data-ms-send]')
    alice.tap('[data-ms-send]')
    for p in (alice, bob, chloe):
        expect(p.page.locator('.ms-author.masked')).to_have_count(3)
        sea = p.page.locator('.ms-slot', has_text='La mer')
        expect(sea.locator('.ms-votes')).to_contain_text('On a pensé à')
        expect(sea.locator('.ms-vote')).to_have_text('Alice ×2')  # à qui, en nombre, jamais le prénom des votants
        expect(p.page.locator('.ms-mark, .ms-vote.right, .ms-vote.wrong')).to_have_count(0)  # rien ne se confirme
        expect(p.page.locator('#game')).not_to_contain_text("C'était")
        expect(p.page.locator('.lk-card', has_text='Points')).to_have_count(0)


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
