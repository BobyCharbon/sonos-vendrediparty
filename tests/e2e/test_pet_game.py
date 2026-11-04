"""Compagnon (vrai navigateur, iPhone) : carte en tête de l'onglet Jeux, invitation à se connecter, œuf (nom), soins
(nourrir, dodo, câlin), mini-jeu de 20 s, tenues, visite d'un ami et cadeau (nom échappé), écran souvenir et nouvel
œuf, animations coupées si l'utilisateur les réduit. Le serveur Party est le vrai ; Supabase est simulé (fonctions pet_*
tenues en mémoire, mêmes règles que la migration — FakeBase de tests/test_pet_api.py)."""
import copy
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from app import pet
from tests.e2e.helpers import Phone, Server, sign_in
from tests.test_pet_api import BOB, TOK_A, FakeBase


class PetSupabase:
    """Faux Supabase HTTP : comptes de FakeBase, routes lues par Party pour relier un compte, fonctions pet_*."""

    def __init__(self):
        self.base = base = FakeBase()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self, status, body: bytes):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route(self):
                content = self.rfile.read(int(self.headers["Content-Length"])) if self.headers.get("Content-Length") else b""
                auth = self.headers.get("Authorization", "")
                uid = base.users.get(auth.removeprefix("Bearer "))
                path = self.path.split("?")[0]
                simple = {"/rest/v1/rpc/my_permissions": [], "/rest/v1/rpc/is_beta_tester": False,
                          "/rest/v1/rpc/get_member_directory": [{"id": uid, "display_name": "Alice", "status": "active"}]}
                if uid and path in simple:
                    return self._answer(200, json.dumps(simple[path]).encode())
                if not path.startswith(("/auth/v1/user", "/rest/v1/rpc/pet_")):
                    return self._answer(404, b"{}")
                r = base.handler(httpx.Request("POST", "http://x" + path, headers={"Authorization": auth}, content=content))
                return self._answer(r.status_code, r.content)

            do_GET = do_POST = _route

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def seed(self, uid: str, life: dict, owner: dict):
        self.base.pets[uid] = {"life": copy.deepcopy(life), "owner": copy.deepcopy(owner), "version": 1}

    def stop(self):
        self.http.shutdown()


def grown(minutes_ago=30, **gauges):
    now = datetime.now(timezone.utc)
    life, owner = pet.new_pet(now - timedelta(minutes=minutes_ago))
    pet.advance(life, now, owner)
    life["g"].update(gauges)
    return life, owner


@pytest.fixture
def world(browser):
    supa = PetSupabase()
    server = Server(supa)
    phone = Phone(browser, server, "Alice")
    yield phone, supa
    errors, server_errors = phone.errors, server.errors()
    phone.close()
    server.stop()
    supa.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, "\n".join(errors)


def open_pet(phone):
    phone.open_games()
    card = phone.page.locator('#gHome section.g-cat').first.locator('.gcard').first
    expect(card).to_have_class("gcard g-pt")
    expect(card.locator('[data-pet-name]')).to_have_text('Compagnon')
    expect(card.locator('.g-pt-ico svg')).to_be_visible()
    card.locator('[data-pet-open]').click()
    root = phone.page.locator('#petRoot')
    expect(root).to_be_visible()
    return root


def test_without_account_the_card_invites_to_sign_in(world):
    phone, _ = world
    page = phone.page
    root = open_pet(phone)
    expect(root.locator('.pt-login h2')).to_contain_text('Adopte ton')
    assert root.evaluate('el => getComputedStyle(el).position') == 'fixed'
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
    assert page.evaluate("document.documentElement.classList.contains('pt-open')")
    expect(page.locator('#tabs')).to_be_hidden()
    phone.shot('pet-0-connexion')
    root.locator('[data-pt="login"]').click()
    expect(root).to_be_hidden()
    assert not page.evaluate("document.documentElement.classList.contains('pt-open')")


def test_egg_name_then_care_for_a_baby(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    root = open_pet(phone)
    expect(root.locator('.pt-count')).to_contain_text('Éclosion dans')
    expect(root.locator('.pt-art svg[role="img"]')).to_have_attribute('aria-label', 'Paillou, Œuf dans son œuf')
    phone.shot('pet-1-oeuf')
    root.locator('#ptName').fill('<b>Bijou</b>')
    root.locator('.pt-name button[type="submit"]').click()
    expect(root.locator('.pt-title')).to_have_text('<b>Bijou</b>')   # affiché tel quel, jamais interprété
    assert supa.base.pets[supa.base.users[TOK_A]]["life"]["name"] == '<b>Bijou</b>'

    # Bébé éclos depuis 30 min, ventre à moitié vide : on le nourrit.
    life, owner = grown(food=40)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root.locator('[data-pt="close"]').click()
    root = open_pet(phone)
    expect(root.locator('.pt-gauges .pt-bar').first).to_have_attribute('aria-valuenow', '40')
    phone.shot('pet-2-accueil')
    root.locator('[data-pt="act"][data-a="feed"]').click()
    expect(root.locator('.pt-gauges .pt-bar').first).to_have_attribute('aria-valuenow', '70')
    expect(root.locator('[data-a="feed"] small')).to_have_text(f'5/{pet.DAILY_LIMITS["feed"]}')

    # Dodo : la nuit tombe, les soins attendent ; on rallume.
    life = supa.base.pets[supa.base.users[TOK_A]]["life"]
    life["g"]["energy"] = 40
    root.locator('[data-pt="close"]').click()
    root = open_pet(phone)
    root.locator('[data-pt="act"][data-a="sleep"]').click()
    expect(root.locator('.pt-hero.pt-night')).to_be_visible()
    expect(root.locator('[data-a="feed"]')).to_have_attribute('aria-disabled', 'true')
    root.locator('[data-a="feed"]').click(force=True)   # aria-disabled : le toucher explique pourquoi
    expect(root.locator('.pt-live')).to_contain_text('il dort')
    phone.shot('pet-3-dodo')
    root.locator('[data-pt="act"][data-a="wake"]').click()
    expect(root.locator('.pt-hero.pt-night')).to_have_count(0)

    # Câlin en touchant le personnage, tenue débloquée (nœud).
    root.locator('[data-pt="pet"]').click()
    expect(root.locator('[data-a="cuddle"] small')).to_have_text(f'{pet.DAILY_LIMITS["cuddle"] - 1}/{pet.DAILY_LIMITS["cuddle"]}')
    root.locator('[data-pt="outfits"]').click()
    expect(root.locator('.pt-tile[data-o="couronne"]')).to_have_attribute('aria-disabled', 'true')
    root.locator('.pt-tile[data-o="noeud"]').click()
    expect(root.locator('.pt-tile[data-o="noeud"]')).to_have_attribute('aria-pressed', 'true')
    phone.shot('pet-4-tenues')
    assert supa.base.pets[supa.base.users[TOK_A]]["life"]["outfit"] == "noeud"


def test_the_twenty_second_micro_game(world):
    phone, supa = world
    page = phone.page
    page.clock.install()
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(joy=20)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    root.locator('[data-pt="act"][data-a="play"]').click()
    expect(root.locator('[data-pt-field]')).to_be_visible()
    for _ in range(6):
        page.clock.run_for(700)
        note = root.locator('.pt-note:not([disabled])').first
        if note.count():
            note.dispatch_event("click")   # la note flotte (animation) : jamais « stable »
    expect(root.locator('[data-pt-hits]')).not_to_have_text('0')
    phone.shot('pet-5-mini-jeu')
    page.clock.run_for(20_000)
    expect(root.locator('.pt-gauges')).to_be_visible()
    played = [s for s in supa.base.saves if any(j["kind"] == "play" for j in s["p_journal"])]
    assert len(played) == 1 and played[0]["p_owner"]["stats"]["plays"] == 1
    assert next(j for j in played[0]["p_journal"] if j["kind"] == "play")["detail"]["score"] > 0
    joy = int(root.locator('.pt-gauges .pt-bar').nth(1).get_attribute('aria-valuenow'))
    assert joy > 20 + pet.PLAY_JOY_MIN - 1


def test_visit_a_friend_and_give_a_hug(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    mine, owner = grown()
    supa.seed(supa.base.users[TOK_A], mine, owner)
    bob, bob_owner = grown(minutes_ago=60 * 30)
    bob["name"] = '<img src=x onerror=alert(1)>'
    supa.seed(BOB, bob, bob_owner)
    root = open_pet(phone)
    root.locator('[data-pt="friends"]').click()
    friend = root.locator('.pt-friend').first
    expect(friend).to_contain_text('<img src=x onerror=alert(1)>')
    expect(friend).to_contain_text('chez <b>Bob</b>')
    assert root.locator('img').count() == 0
    phone.shot('pet-6-amis')
    friend.click()
    root.locator('[data-pt="gift"][data-k="hug"]').click()
    expect(root.locator('.pt-line').last).to_contain_text('déjà fait plaisir')
    assert supa.base.gifts[0]["to"] == BOB and supa.base.gifts[0]["kind"] == "hug"
    phone.shot('pet-7-visite')
    page.go_back()
    expect(root.locator('.pt-friends')).to_be_visible()


def test_memorial_then_a_new_egg(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(minutes_ago=60 * 24 * 9)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    expect(root.locator('.pt-memo h2')).to_contain_text("s'est envolé")
    expect(root.locator('.pt-memo-list li')).to_have_count(1)
    phone.shot('pet-8-souvenir')
    root.locator('[data-a="new_egg"]').click()
    expect(root.locator('.pt-count')).to_contain_text('Éclosion dans')
    assert supa.base.pets[supa.base.users[TOK_A]]["life"]["gen"] == 2


def test_reduced_motion_stops_the_animations_and_deep_link_opens(world):
    phone, supa = world
    page = phone.page
    page.emulate_media(reduced_motion='reduce')
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    supa.seed(supa.base.users[TOK_A], life, owner)
    page.goto('/?tab=games&pet=1')
    root = page.locator('#petRoot')
    expect(root.locator('.pt-gauges')).to_be_visible()
    assert root.locator('.pt-body').first.evaluate('el => getComputedStyle(el).animationName') == 'none'
