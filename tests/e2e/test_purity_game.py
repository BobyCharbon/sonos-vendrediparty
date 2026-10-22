"""Purify Test de bout en bout : vrais boutons, comptes Party simulés (faux Supabase local)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state

USERS = {'tok-alice-' + 'a' * 30: ('u-alice', 'Alice'), 'tok-bob-' + 'b' * 30: ('u-bob', 'Bob')}


class FakeSupabase(BaseHTTPRequestHandler):
    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self):
        user = USERS.get(self.headers.get('Authorization', '').removeprefix('Bearer '))
        path = self.path.split('?')[0]
        if not user:
            return self._reply(401, {})
        if path == '/auth/v1/user':
            return self._reply(200, {'id': user[0]})
        if path == '/rest/v1/rpc/get_member_directory':
            return self._reply(200, [{'display_name': user[1], 'avatar_url': None, 'status': 'active'}])
        if path == '/rest/v1/rpc/my_permissions':
            return self._reply(200, [])
        if path == '/rest/v1/rpc/is_beta_tester':
            return self._reply(200, False)
        return self._reply(404, {})

    def do_GET(self):
        self._route()

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        self._route()

    def log_message(self, *args):
        pass


@pytest.fixture
def phones(browser, monkeypatch):
    fake = ThreadingHTTPServer(('127.0.0.1', 0), FakeSupabase)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    monkeypatch.setenv('SUPABASE_URL', f'http://127.0.0.1:{fake.server_port}')
    server = Server()
    made = []

    def make(name, token=None):
        p = Phone(browser, server, name)
        if token:  # session Supabase gardée par le module Comptes, comme après une vraie connexion
            p.ctx.add_init_script(f"localStorage.setItem('sb-fake-auth-token', JSON.stringify({{access_token: '{token}'}}))")
            p.page.goto('/')
            p.page.wait_for_function("(localStorage.getItem('vp_guest') || '').startsWith('acct-')")
            p.gid = p.page.evaluate("localStorage.getItem('vp_guest')")
        made.append(p)
        return p
    yield make
    errors = [e for p in made for e in p.errors]
    for p in made:
        p.close()
    server_errors = server.errors()
    server.stop()
    fake.shutdown()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def test_purity_private_answers_reveal_and_accounts_only(phones):
    tokens = list(USERS)
    alice, bob, carol = phones('Alice', tokens[0]), phones('Bob', tokens[1]), phones('Carol')

    code = alice.create('purity', pualcohol=True)
    expect(alice.page.locator('.pu-hero')).to_be_visible()

    # Sans compte : écran de connexion, pas de place dans le test.
    carol.join(code)
    expect(carol.page.get_by_text('Réservé aux comptes connectés')).to_be_visible()
    assert not carol.state().get('me')
    carol.tap('[data-pu-login]')
    expect(carol.page.locator('body')).to_have_attribute('data-tab', 'account')

    bob.join(code)
    wait_state(alice, lambda g: len(g['players']) == 2)

    alice.tap('[data-gact="start"]')
    expect(bob.page.locator('.pu-q').first).to_be_visible()
    for i in range(5):
        bob.tap(f'[data-pu-i="{i}"]')
    expect(bob.page.locator('#puCount')).to_have_text('5')
    bob.tap('[data-pu-i="4"]')  # on décoche
    wait_state(bob, lambda g: g['purity']['answered'] == 4)
    bob.tap('[data-pu-act="pusub"]')
    expect(bob.page.get_by_text('Réponses envoyées')).to_be_visible()

    alice.tap('[data-pu-act="pusub"]')
    expect(alice.page.locator('.pu-progress')).to_contain_text('2/2')
    alice.tap('[data-pu-act="pureveal"]')

    expect(alice.page.locator('.pu-score-v')).to_have_text('100 %')
    expect(bob.page.locator('.pu-row').first).to_contain_text('Alice')
    expect(bob.page.locator('.pu-row').last).to_contain_text('Bob')
    expect(bob.page.locator('.pu-drink')).to_contain_text('Bob boit 2 gorgées')
    expect(bob.page.locator('.pu-lb')).to_contain_text('Classement général')
    # Les cases cochées ne sont jamais renvoyées après la révélation.
    assert 'mine' not in bob.state()['purity']
    expect(alice.page.locator('[data-gact="restart"]')).to_be_visible()
