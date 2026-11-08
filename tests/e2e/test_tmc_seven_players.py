"""Retour de l'admin (07.11) : « Tu me connais ? » ne marchait plus au bout de sept personnes, et un joueur ne pouvait
pas quitter la partie. Vraie partie à 7 téléphones : plusieurs duos joués jusqu'au bout, puis un joueur quitte."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state

# Prénoms sans accent : l'identifiant des téléphones de test en est tiré (un vrai téléphone a un identifiant aléatoire).
NAMES = ['Lou', 'Ana', 'Bob', 'Cleo', 'Dan', 'Eva', 'Fio']


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


def test_seven_players_play_several_duos_then_one_leaves(phones):
    every = [phones(n, 'android' if i % 2 else 'iphone') for i, n in enumerate(NAMES)]
    host = every[0]
    code = host.create('tmc')
    for p in every[1:]:
        p.join(code)
    wait_state(host, lambda g: len(g['players']) >= 7)
    host.tap('[data-gact="start"]')
    by_name = {p.name: p for p in every}
    for _ in range(8):
        duo = wait_state(host, lambda g: g['phase'] == 'answer')['tmc']['duo']
        subject = by_name[duo['subject']['name']]
        subject.page.locator('#guessInput').fill('Une réponse')
        subject.page.locator('form[data-gform="tanswer"] button').click()
        wait_state(host, lambda g: g['phase'] == 'guess')
        subject.tap('.tm-reveal')
        wait_state(host, lambda g: g['phase'] == 'judge')
        host.tap('[data-gact="tjudge"][data-amount="2"]')
        wait_state(host, lambda g: g['phase'] == 'scored')
        host.tap('[data-gact="next"]')
    leaver = every[3]
    leaver.tap('[data-gdrawer="open"]')
    leaver.page.once('dialog', lambda d: d.accept())
    leaver.tap('[data-exit="away"]')
    wait_state(host, lambda g: len(g['players']) == 6)
    for p in every:
        p.shot(f'tmc7-{p.name}')
    expect(host.page.locator('[data-gact="tq"]').first).to_be_visible()
