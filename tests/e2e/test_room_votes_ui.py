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
