"""Pause de l'animateur (vrais boutons) : ⏸ dans la barre du haut, voile « Pause » chez tout le monde, reprise."""
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


def test_host_pauses_everyone_sees_it_then_resumes(phones):
    boby = phones('Boby')
    code = boby.create('never')
    lea = phones('Lea')
    lea.join(code)
    lea.act('join')
    boby.act('start')
    wait_state(boby, lambda g: g['phase'] == 'question')
    expect(lea.page.locator('#gTop [data-gact="pause"]')).to_have_count(0)  # pas pour les joueurs
    boby.tap('#gTop [data-gact="pause"]')
    expect(lea.page.locator('#gPause')).to_contain_text('Boby a mis la partie en pause')
    expect(lea.page.locator('#gPause [data-gact="resume"]')).to_have_count(0)
    assert lea.act('vote', target='yes')['detail'].startswith('⏸')
    boby.tap('#gPause [data-gact="resume"]')
    expect(lea.page.locator('#gPause')).to_have_count(0)
    expect(boby.page.locator('#gTop [data-gact="pause"]')).to_be_visible()
