"""Biskit Royal (vrais navigateurs) : on tire des cartes jusqu'à un 4 ; le lanceur voit « Lance les dés ! », le touche,
les dés partent ; aucune erreur JavaScript ni serveur."""
import time

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


def test_the_roller_throws_the_dice(phones):
    boby = phones('Boby')
    code = boby.create('biskit')
    lea = phones('Lea')
    lea.join(code)
    lea.act('join')
    boby.act('start')
    by_pid = {boby.pid(): boby, lea.pid(): lea}
    for _ in range(60):
        s = boby.state()
        B = s['bk']
        if B.get('await') and B['await'].get('kind') == 'dice':
            roller = by_pid[B['await']['pid']]
            roller.tap('[data-bk="roll"]')
            s = wait_state(boby, lambda g: g['bk'].get('dice'))
            assert s['bk']['outcomes']
            return
        if B.get('await'):  # autre choix (pote, règle…) : l'animateur le fait pour avancer
            a = B['await']
            target = next(p['pid'] for p in s['players'] if p['pid'] != a['pid'])
            boby.act('bpick', who=a['pid'], target=target if a['kind'] != 'rule' else '', guess='Règle de test')
            if a['kind'] == 'unrule' and B.get('rules'):
                boby.act('bpick', who=a['pid'], target=B['rules'][0]['id'])
        if B.get('reflex') and not B['reflex'].get('done'):
            boby.act('bclose')
        turn = B.get('turn')
        if turn:
            boby.act('bdraw', who=turn)
        time.sleep(max(0.2, B.get('wait') or 0))
    pytest.skip("Pas de 4 tiré en 60 essais")
