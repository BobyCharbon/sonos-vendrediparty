"""Prénoms ajoutés à la main dans Qui de nous ?, Blackjack et Casino (vrais boutons) : l'animateur ajoute « Mamie »
(sans téléphone), puis vote, mise et joue pour elle depuis son propre téléphone."""
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


def add_mamie(host):
    field = host.page.locator('#gameHost [data-gform="addguest"] input')
    field.fill('Mamie')
    field.press('Enter')
    s = wait_state(host, lambda g: any(p['name'] == 'Mamie' for p in g['players']))
    return next(p for p in s['players'] if p['name'] == 'Mamie')


def ensure_seated(host):
    if not host.state().get('me'):
        host.tap('[data-gact="join"]')
        wait_state(host, lambda g: g.get('me'))


def test_whoof_host_picks_who_mamie_designates(phones):
    boby = phones('Boby')
    code = boby.create('whoof')
    lea = phones('Lea')
    lea.join(code)
    lea.act('join')
    mamie = add_mamie(boby)
    boby.tap('[data-gact="start"]')
    wait_state(boby, lambda g: g['phase'] == 'question')
    s = boby.state()
    lea_pid = next(p['pid'] for p in s['players'] if p['name'] == 'Lea')
    boby.tap(f'#gameHost [data-gact="mvote"][data-target="{mamie["pid"]}"][data-guess="{lea_pid}"]')
    wait_state(boby, lambda g: next(p for p in g['players'] if p['pid'] == mamie['pid']).get('voted'))


def test_blackjack_host_bets_and_plays_for_mamie(phones):
    boby = phones('Boby')
    boby.create('blackjack')
    ensure_seated(boby)
    mamie = add_mamie(boby)
    boby.tap('[data-gact="start"]')
    wait_state(boby, lambda g: g['phase'] == 'bet')
    boby.tap(f'#gameHost [data-gact="bet"][data-who="{mamie["pid"]}"][data-amount="10"]')
    wait_state(boby, lambda g: next(x for x in g['bj']['seats'] if x['pid'] == mamie['pid'])['hand'])
    boby.tap('#gameBody [data-gact="bet"][data-amount="5"], #gamePlay [data-gact="bet"]:not([data-who])')
    for _ in range(6):
        s = wait_state(boby, lambda g: g['phase'] != 'play' or g['bj']['turn'])
        if s['phase'] != 'play':
            break
        if s['bj']['turn'] == mamie['pid']:
            boby.tap(f'#gameHost [data-gact="stand"][data-who="{mamie["pid"]}"]')
        else:
            boby.tap('[data-gact="stand"]:not([data-who])')
        wait_state(boby, lambda g, t=s['bj']['turn']: g['phase'] != 'play' or g['bj']['turn'] != t)
    s = wait_state(boby, lambda g: g['phase'] == 'results')
    assert next(x for x in s['bj']['seats'] if x['pid'] == mamie['pid'])['hand']['result']


def test_casino_host_bets_for_mamie(phones):
    boby = phones('Boby')
    boby.create('casino')
    ensure_seated(boby)
    mamie = add_mamie(boby)
    boby.tap('[data-gact="start"]')
    wait_state(boby, lambda g: g['phase'] == 'bet')
    boby.tap(f'[data-cfor="{mamie["pid"]}"]')
    expect(boby.page.locator(f'[data-cfor="{mamie["pid"]}"]')).to_have_class('py-mini ok')
    boby.tap('[data-cbet="color:red"]')
    s = wait_state(boby, lambda g: next(t for t in g['casino']['table'] if t['pid'] == mamie['pid'])['staked'])
    assert not s['casino']['me']['staked']  # la mise est à Mamie, pas à Boby
    boby.tap(f'[data-gact="cready"][data-who="{mamie["pid"]}"]')
    wait_state(boby, lambda g: next(t for t in g['casino']['table'] if t['pid'] == mamie['pid'])['ready'])
