"""Beer pong de bout en bout (vrais boutons) : équipes, gobelet touché, joueur, sentence ; tout le monde voit la
dernière sentence ; l'équipe sans gobelets perd."""
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


def test_host_marks_cups_and_picks_sentences(phones):
    boby = phones('Boby')
    code = boby.create('beerpong')
    lea, tom = phones('Lea'), phones('Tom')
    for p in (lea, tom):
        p.join(code)
        p.act('join')
    boby.tap('#gamePlay [data-bp-cups="6"]')
    wait_state(boby, lambda g: g['bp']['cups'] == 6)
    boby.tap('#gamePlay [data-gact="start"]')
    s = wait_state(boby, lambda g: g['phase'] == 'play')
    expect(boby.page.locator('#gamePlay .bp-rack.red .bp-cup')).to_have_count(6)
    red = [p for p in s['bp']['players'] if p['team'] == 'red']
    boby.tap('#gamePlay [data-bp-cup="red:0"]')
    if len(red) > 1:
        boby.tap(f'#gamePlay [data-bp-who="{red[0]["pid"]}"]')
    expect(boby.page.locator('#gamePlay .bp-opt[data-bp-sent]')).to_have_count(3)
    expect(lea.page.locator('#gamePlay .bp-pending')).to_be_visible()  # les joueurs voient l'attente
    boby.tap('#gamePlay [data-bp-sent="0"]')
    s = wait_state(boby, lambda g: g['bp']['last'] is not None)
    expect(lea.page.locator('#gamePlay .bp-last')).to_contain_text(s['bp']['last']['text'][:20])
    expect(lea.page.locator('#gamePlay .bp-rack.red .bp-cup.down')).to_have_count(6 - s['bp']['alive']['red'])
    # Un joueur sans droit de marquer ne peut pas toucher les gobelets.
    expect(lea.page.locator('#gamePlay [data-bp-cup]')).to_have_count(0)
