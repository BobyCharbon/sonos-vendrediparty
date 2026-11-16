"""Salle de jeux (vrais boutons) : les participants voient les mêmes jeux que l'animateur et votent (un seul choix,
modifiable) ; le compteur apparaît sur le jeu ; l'animateur voit le ou les plus votés et lance directement."""
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


def test_players_vote_and_the_host_launches_the_favourite(phones):
    boby = phones('Boby')
    code = boby.create('room')
    lea, tom = phones('Lea'), phones('Tom')
    for p in (lea, tom):
        p.join(code)
        p.act('join')
    # Les participants voient les mêmes catégories et jeux que l'animateur.
    expect(lea.page.locator('#gamePlay [data-room-vote="quiz"]')).to_be_visible()
    assert lea.page.locator('#gamePlay .g-room-grid [data-room-vote]').count() == boby.page.locator('#gamePlay .g-room-grid [data-room-pick]').count()
    lea.tap('#gamePlay [data-room-vote="quiz"]')
    expect(lea.page.locator('#gamePlay [data-room-vote="quiz"] .g-room-votes')).to_have_text('1')
    expect(lea.page.locator('#gamePlay [data-room-vote="quiz"]')).to_have_attribute('aria-pressed', 'true')
    tom.tap('#gamePlay [data-room-vote="never"]')
    # Égalité : l'animateur voit les deux, chacun avec son bouton.
    expect(boby.page.locator('.g-room-best [data-room-pick]')).to_have_count(2)
    # Tom change d'avis : un seul choix, son vote se déplace.
    tom.tap('#gamePlay [data-room-vote="quiz"]')
    expect(boby.page.locator('#gamePlay .g-room-grid [data-room-pick="quiz"] .g-room-votes')).to_have_text('2')
    expect(boby.page.locator('#gamePlay .g-room-grid [data-room-pick="never"] .g-room-votes')).to_have_count(0)
    expect(boby.page.locator('.g-room-best [data-room-pick]')).to_have_count(1)
    expect(boby.page.locator('.g-room-best')).to_contain_text('Quiz')
    # L'animateur lance le plus voté directement depuis la case.
    boby.tap('.g-room-best [data-room-pick="quiz"]')
    boby.tap('.g-room-sheet [data-create="quiz"]')
    wait_state(boby, lambda g: g.get('type') == 'quiz' or (g.get('room_info') or {}).get('current'), timeout=10)


def test_a_participant_reads_the_rules_of_a_game_before_voting(phones):
    """Avis de l'admin (10.11) : « ? » en haut à droite de chaque jeu de la salle (règles, sans voter), « NEW » à gauche."""
    boby = phones('Boby')
    code = boby.create('room')
    lea = phones('Lea')
    lea.join(code)
    lea.act('join')
    help_btn = lea.page.locator('#gamePlay .g-room-cell:has([data-room-vote="undercover"]) .g-room-help')
    expect(help_btn).to_be_visible()
    tile = lea.page.locator('#gamePlay [data-room-vote="undercover"]').bounding_box()
    box = help_btn.bounding_box()
    assert box['x'] + box['width'] / 2 > tile['x'] + tile['width'] / 2 and box['y'] < tile['y'] + 10  # en haut à droite
    help_btn.click()
    expect(lea.page.locator('#rulesModal')).to_be_visible()
    expect(lea.page.locator('#rulesTitle')).to_have_text('Undercover')
    expect(lea.page.locator('#gamePlay [data-room-vote="undercover"]')).to_have_attribute('aria-pressed', 'false')  # rien voté
    lea.page.locator('#rulesModal [data-rules-close]').last.click()
    expect(lea.page.locator('#rulesModal')).to_be_hidden()
    # Le nouveau jeu garde « NEW », à gauche ; le « ? » reste à droite.
    new = lea.page.locator('#gamePlay .g-room-tile .g-new').first
    if new.count():
        cell = new.locator('xpath=ancestor::div[contains(@class,"g-room-cell")]').bounding_box()
        assert new.bounding_box()['x'] < cell['x'] + cell['width'] / 2


def test_home_creates_or_joins_a_room_and_the_host_changes_game(phones):
    """Maquette approuvée le 15.11.2026 : l'accueil des Jeux propose « Créer une salle » ou son code, puis les jeux
    solo ; dans un jeu de la salle, « 🎮 Changer de jeu » (animateur seulement) ramène tout le monde à la salle."""
    boby = phones('Boby')
    boby.open_games()
    expect(boby.page.locator('#gHome .g-cat-h:visible')).to_have_text(['🧠 Jeux solo'])
    boby.page.locator('#gHome .g-room-card [data-create="room"]').click()
    expect(boby.page.locator('#gamePlay')).to_be_visible()
    room = boby.page.locator('#gameCode').inner_text().strip()
    # Léa rejoint avec le code tapé dans la carte de la salle.
    lea = phones('Lea')
    lea.open_games()
    lea.page.locator('#gHome .g-room-card #gCode').fill(room)
    lea.page.locator('#gHome .g-room-card #gCode').press('Enter')
    expect(lea.page.locator('#gamePlay')).to_be_visible()
    lea.act('join')
    boby.tap('#gamePlay [data-room-pick="likely"]')
    boby.tap('.g-room-sheet [data-create="likely"]')
    wait_state(lea, lambda g: g.get('type') == 'likely', timeout=10)
    wait_state(boby, lambda g: g.get('type') == 'likely', timeout=10)
    expect(boby.page.locator('#gRoomSwitch button')).to_have_text('🎮 Changer de jeu')
    expect(lea.page.locator('#gRoomSwitch button')).to_have_count(0)
    boby.page.on('dialog', lambda d: d.accept())
    boby.tap('#gRoomSwitch button')
    for p in (boby, lea):
        wait_state(p, lambda g: g.get('type') == 'room', timeout=10)
    expect(boby.page.locator('#gamePlay [data-room-pick="likely"]')).to_be_visible()
    expect(boby.page.locator('#gRoomSwitch button')).to_have_count(0)


SCROLL = "document.getElementById('gamePlay').scrollTop"


def test_a_game_launched_from_the_room_opens_at_the_top_and_so_does_the_room_after(phones):
    """Recette du 15.11.2026 : le plein écran (#gamePlay) gardait le défilement d'un écran à l'autre. L'animateur qui
    lançait le Quiz depuis le bas du catalogue de la salle arrivait au milieu des réglages (QR et code cachés), les
    joueurs aussi ; après « Changer de jeu » (tout en bas du jeu), la salle s'ouvrait au milieu du catalogue."""
    boby, lea = phones('Boby'), phones('Lea')
    boby.open_games()
    boby.page.locator('#gHome [data-create="room"]').click()
    expect(boby.page.locator('#gamePlay [data-room-pick="quiz"]')).to_be_visible()
    lea.join(boby.page.locator('#gameCode').inner_text().strip())
    expect(lea.page.locator('#gamePlay [data-room-vote="quiz"]')).to_be_visible()
    lea.page.locator('#gamePlay [data-room-vote="quiz"]').scroll_into_view_if_needed()
    boby.page.locator('#gamePlay [data-room-pick="quiz"]').scroll_into_view_if_needed()
    assert boby.page.evaluate(SCROLL) > 200 and lea.page.evaluate(SCROLL) > 200
    boby.tap('#gamePlay [data-room-pick="quiz"]')
    boby.tap('.g-room-sheet [data-create="quiz"]')
    for p in (boby, lea):
        wait_state(p, lambda g: g.get('type') == 'quiz', timeout=10)
        expect(p.page.locator('#gTop')).to_contain_text('Quiz')
        assert p.page.evaluate(SCROLL) == 0, p.name
    boby.page.locator('#gRoomSwitch button').scroll_into_view_if_needed()
    assert boby.page.evaluate(SCROLL) > 200
    boby.page.on('dialog', lambda d: d.accept())
    boby.tap('#gRoomSwitch button')
    expect(boby.page.locator('#gamePlay [data-room-pick="quiz"]')).to_be_attached(timeout=10000)
    assert boby.page.evaluate(SCROLL) == 0


def test_an_incomplete_room_code_says_so_on_enter(phones):
    """Recette du 15.11.2026 : « Entrée » avec un code de moins de 4 chiffres (ou vide) ne faisait rien, sans un mot."""
    lea = phones('Lea')
    lea.open_games()
    field = lea.page.locator('#gHome .g-room-card #gCode')
    field.press_sequentially('12')
    field.press('Enter')
    expect(lea.page.get_by_text('Le code de la salle a 4 chiffres.')).to_be_visible()
    expect(lea.page.locator('#gHome')).to_be_visible()
