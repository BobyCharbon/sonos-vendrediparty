"""« Pour ou contre » de bout en bout (vrais boutons) : vote secret sur 5 crans, révélation anonyme ou avec les prénoms,
revote décidé par l'animateur, dilemme proposé par un joueur puis validé, téléphone qui passe aux invités sans téléphone."""
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


def vote(phone, label, last=False):
    page = phone.page
    expect(page.locator('.lk-who')).to_contain_text('Où te places-tu')
    page.locator('.db-pick', has_text=label).click()
    if not last:  # le dernier vote révèle aussitôt la répartition
        expect(page.locator('.db-mine')).to_contain_text(label)
    expect(page.locator('.db-scale')).to_have_count(0)  # vote définitif : l'échelle disparaît


def two_players(phones, **options):
    alice, bob = phones('Alice'), phones('Bob', 'android')
    code = alice.create('debate', **options)
    bob.join(code)
    wait_state(alice, lambda g: len(g['players']) == 2)
    return alice, bob


def test_public_votes_then_host_revotes_and_sees_who_changed_their_mind(phones):
    alice, bob = two_players(phones, dbpublic=True)
    expect(alice.page.locator('.db-hero')).to_be_visible()
    expect(bob.page.locator('.lk-card')).to_contain_text('Tu es inscrit')
    alice.tap('[data-gact="start"]')
    expect(alice.page.locator('.db-q-n')).to_have_text('Dilemme 1/10')
    question = alice.page.locator('.db-q-t').inner_text()
    expect(bob.page.locator('.db-q-t')).to_have_text(question)

    vote(bob, 'Totalement contre')
    expect(bob.page.locator('.lk-win')).to_have_count(0)  # secret tant que tout le monde n'a pas voté
    vote(alice, 'Totalement pour', last=True)
    for p in (alice, bob):
        expect(p.page.locator('.lk-win-t')).to_have_text('Le groupe est partagé')
        expect(p.page.locator('.db-bar.db-c0 .db-names')).to_have_text('Bob')
        expect(p.page.locator('.db-bar.db-c4 .db-names')).to_have_text('Alice')
    expect(bob.page.locator('[data-gact="dbrevote"]')).to_have_count(0)  # l'animateur décide

    alice.tap('[data-gact="dbrevote"]')
    expect(bob.page.locator('.db-again')).to_contain_text('as-tu changé d')
    expect(bob.page.locator('.db-q-t')).to_have_text(question)
    vote(bob, 'Plutôt pour')
    vote(alice, 'Totalement pour', last=True)
    for p in (alice, bob):
        expect(p.page.locator('.db-moved')).to_have_text('🔄 1 personne a changé d\'avis')
        expect(p.page.locator('.lk-win-t')).to_have_text('Plutôt pour')
    expect(alice.page.locator('[data-gact="dbrevote"]')).to_have_count(0)  # un seul revote
    alice.tap('[data-gact="next"]')
    expect(alice.page.locator('.db-q-n')).to_have_text('Dilemme 2/10')


def test_anonymous_by_default_never_shows_names(phones):
    alice, bob = two_players(phones)
    alice.tap('[data-gact="start"]')
    vote(bob, 'Plutôt contre')
    vote(alice, 'Plutôt contre', last=True)
    expect(alice.page.locator('.lk-win-t')).to_have_text('Plutôt contre')
    expect(alice.page.locator('.db-names')).to_have_count(0)
    expect(bob.page.locator('.db-bars')).not_to_contain_text('Alice')


def test_player_proposes_a_dilemma_the_host_validates_it_and_it_comes_next(phones):
    alice, bob = two_players(phones)
    text = 'Faut-il <b>vraiment</b> manger la raclette en été ?'
    bob.tap('[data-db-compose]')
    area = bob.page.locator('.db-sheet textarea')
    area.fill(text)
    bob.page.wait_for_timeout(1500)  # rafraîchissements en arrière-plan : le texte tapé ne doit pas s'effacer
    expect(area).to_have_value(text)
    bob.page.locator('.db-sheet [type="submit"]').click()
    expect(bob.page.locator('.db-sheet')).to_have_count(0)
    expect(bob.page.locator('.db-pending')).to_have_text('1 en attente de validation')

    expect(alice.page.locator('.db-prop-t')).to_contain_text(text)  # affiché tel quel, jamais interprété en HTML
    expect(alice.page.locator('.db-prop-t b')).to_have_count(0)
    alice.tap('[data-db-accept]')
    expect(alice.page.locator('.db-inbox')).to_have_count(0)
    alice.tap('[data-gact="start"]')
    for p in (alice, bob):
        expect(p.page.locator('.db-q-t')).to_have_text(text)
        expect(p.page.locator('.db-q-tag')).to_have_text('✍️ Proposé par Bob')


def test_host_passes_the_phone_to_a_guest_without_phone_and_reaches_the_summary(phones):
    alice = phones('Alice')
    alice.create('debate')
    field = alice.page.locator('#gameHost [data-gform="addguest"] input')
    field.fill('Papa')
    field.press('Enter')
    expect(alice.page.locator('#gameHost')).to_contain_text('Papa')
    alice.tap('[data-gact="start"]')
    for _ in range(10):
        vote(alice, 'Partagé')
        expect(alice.page.locator('.lk-pass .lk-name')).to_have_text('Papa')
        alice.tap('[data-db-ready]')
        expect(alice.page.locator('.lk-who')).to_contain_text('Papa')
        alice.page.locator('.db-pick', has_text='Totalement pour').click()
        expect(alice.page.locator('.lk-win')).to_be_visible()
        alice.tap('[data-gact="next"]')
    expect(alice.page.locator('.lk-end-k')).to_have_text('Bilan de la partie')
    expect(alice.page.locator('.db-award')).to_have_count(2)  # divisant + unanime ; personne n'a changé d'avis
    expect(alice.page.locator('[data-gact="restart"]')).to_be_visible()


def test_home_card_rules(phones):
    alice = phones('Alice', 'desktop')
    alice.create('debate')
    alice.page.locator('#gTop [data-rules="debate"]').click()
    expect(alice.page.locator('#rulesTitle')).to_have_text('Pour ou contre')
    expect(alice.page.locator('#rulesBody')).to_contain_text('faire revoter')


def test_wtf_theme_is_unchecked_by_default_and_the_host_can_add_it(phones):
    alice = phones('Alice')
    alice.open_games()
    card = alice.page.locator('#gHome .gcard:has([data-create="debate"])')
    wtf = card.locator('[data-opt-group="cats"] [data-val="wtf"]')
    expect(wtf).not_to_have_class('on')
    wtf.click()
    expect(wtf).to_have_class('on')
    card.locator('[data-create="debate"]').click()
    expect(alice.page.locator('#gamePlay')).to_be_visible()
    wait_state(alice, lambda g: 'wtf' in g['debate']['themes'])
    expect(alice.page.locator('[data-db-theme="wtf"]')).to_contain_text('🔞')
    alice.tap('[data-db-theme="wtf"]')  # l'animateur peut encore le retirer avant de lancer
    wait_state(alice, lambda g: 'wtf' not in g['debate']['themes'])


def test_new_badge_marks_only_this_game_on_the_home_cards(phones):
    alice = phones('Alice')
    alice.open_games()
    badge = alice.page.locator('#gHome .gcard:has([data-create="debate"]) .g-new')
    expect(badge).to_be_visible()
    expect(badge).to_have_text('NEW')
    expect(alice.page.locator('#gHome .g-new')).to_have_count(1)
    # En haut à droite de la carte, sans masquer le bouton « ? » des règles.
    card = alice.page.locator('#gHome .gcard:has([data-create="debate"])').bounding_box()
    b = badge.bounding_box()
    help_btn = alice.page.locator('#gHome .gcard:has([data-create="debate"]) .g-help').bounding_box()
    assert b['x'] + b['width'] > card['x'] + card['width'] * 0.7 and b['y'] < card['y'] + 20
    assert b['y'] + b['height'] <= help_btn['y'] + 2


def test_home_and_game_room_list_games_by_category(phones):
    alice = phones('Alice')
    alice.open_games()
    page = alice.page
    heads = page.locator('#gHome .g-cat-h')
    expect(heads).to_have_text(['🍻 Alcool', '🎮 Jeux 3D', '💞 Parler vrai', '🃏 Jeux de cartes', '🎉 Ambiance'])
    expect(page.locator('#gHome .g-cat[data-cat="talk"] [data-create]')).to_have_count(3)
    expect(page.locator('#gHome .g-cat[data-cat="talk"] [data-create="divan"]')).to_have_count(1)
    expect(page.locator('#gHome .g-cat[data-cat="cards"] [data-create="pyramid"]')).to_have_count(1)
    # Chaque jeu une seule fois ; ceux qui se jouent aussi avec alcool portent l'étiquette 🍻.
    expect(page.locator('#gHome .gcard:not(.g-room-card)')).to_have_count(18)
    expect(page.locator('#gHome .g-cat[data-cat="cards"] .gcard:has([data-create="pyramid"]) .g-drink')).to_be_visible()
    expect(page.locator('#gHome .g-cat[data-cat="drinks"] .g-drink')).to_have_count(0)
    # Le bouton d'une carte rangée crée toujours la partie.
    page.locator('#gHome [data-create="room"]').click()
    expect(page.locator('#gamePlay')).to_be_visible()
    expect(page.locator('.g-room-cat-h')).to_have_text(['🍻 Alcool', '🎮 Jeux 3D', '💞 Parler vrai', '🃏 Jeux de cartes', '🎉 Ambiance'])
    expect(page.locator('.g-room-cat[data-cat="talk"] [data-room-pick]')).to_have_count(3)
    page.locator('.g-room-cat[data-cat="talk"] [data-room-pick="debate"]').click()
    expect(page.locator('.g-room-sheet [data-create="debate"]')).to_be_visible()
