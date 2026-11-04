"""Compagnon (vrai navigateur, iPhone) : carte en tête de l'onglet Jeux, invitation à se connecter, œuf (nom), soins
(nourrir, dodo, câlin), mini-jeu de 20 s, tenues, visite d'un ami et cadeau (nom échappé), écran souvenir et nouvel
œuf, animations coupées si l'utilisateur les réduit ; boucle du jour (coffre tiré par le serveur et révélé, chances sous
« i », série et paliers, missions, trésors, ouverture comptée avec sa source). Le serveur Party est le vrai ; Supabase est simulé (fonctions pet_*
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
                if not path.startswith(("/auth/v1/user", "/rest/v1/rpc/pet_", "/rest/v1/rpc/report_content",
                                        "/rest/v1/rpc/set_block", "/rest/v1/rpc/my_blocks")):
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
    expect(root.locator('.pt-login h2')).to_have_text('Adopte ton Zicou')   # (le playtest a vu « Paillou »)
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
    expect(root.locator('.pt-art svg[role="img"]')).to_have_attribute('aria-label', 'Zicou, Œuf dans son œuf')
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
    expect(root.locator('[data-a="feed"] small')).to_have_text(f'reste {pet.DAILY_LIMITS["feed"] - 1}')

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

    # Câlin en touchant le personnage, puis la garde-robe (collection) : le nœud offert dès le premier jour.
    root.locator('[data-pt="pet"]').click()
    expect(root.locator('[data-a="cuddle"] small')).to_have_text(f'reste {pet.DAILY_LIMITS["cuddle"] - 1}')
    root.locator('[data-pt="coll"][data-s="wear"]').click()
    root.locator('[data-pt="pc-slot"][data-s="neck"]').click()
    root.locator('[data-pt="pc-wear"][data-i="noeud"]').click()
    expect(root.locator('[data-pt="pc-wear"][data-i="noeud"]')).to_have_attribute('aria-pressed', 'true')
    phone.shot('pet-4-tenues')
    assert supa.base.pets[supa.base.users[TOK_A]]["life"]["acc"] == {"neck": "noeud"}


def test_the_twenty_second_micro_game(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(joy=20)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    root.locator('[data-pt="act"][data-a="play"]').click()
    expect(root.locator('[data-pt-field]')).to_be_visible()
    expect(root.locator('.pt-game-pet .pt-art svg')).to_be_visible()   # le compagnon joue avec toi
    for _ in range(6):   # en temps réel : le serveur compte la partie à sa propre horloge (20 s)
        page.wait_for_timeout(700)
        note = root.locator('.pt-note:not([disabled])').first
        if note.count():
            bg = note.evaluate("el => getComputedStyle(el).backgroundImage")
            assert "255, 255, 255" in bg   # pastille claire : la note se voit sur le fond violet
            note.dispatch_event("click")   # la note flotte (animation) : jamais « stable »
    expect(root.locator('[data-pt-hits]')).not_to_have_text('0')
    phone.shot('pet-5-mini-jeu')
    # Fin de partie : le score calculé par le serveur, avec le compagnon (playtest « Léa » : retour direct à l'accueil).
    result = root.locator('.pt-result')
    expect(result).to_be_visible(timeout=30_000)
    expect(result.locator('h2')).to_contain_text('sur 30')
    expect(result.locator('.pt-art svg')).to_be_visible()
    expect(root.locator('.pt-burst')).to_have_count(0)   # rien par-dessus le score
    phone.shot('pet-5b-score')
    result.locator('[data-pt="home"]').click()
    expect(root.locator('.pt-gauges')).to_be_visible()
    played = [s for s in supa.base.saves if any(j["kind"] == "play" for j in s["p_journal"])]
    assert len(played) == 1 and played[0]["p_owner"]["stats"]["plays"] == 1
    detail = next(j for j in played[0]["p_journal"] if j["kind"] == "play")["detail"]
    assert 0 < detail["hits"] <= 6 and detail["score"] == round(100 * detail["hits"] / 30)   # calculé par le serveur
    joy = int(root.locator('.pt-gauges .pt-bar').nth(1).get_attribute('aria-valuenow'))
    assert joy > 20 + pet.PLAY_JOY_MIN - 1


def test_a_phone_that_skips_the_game_time_scores_nothing(world):
    """Playtest « Marc » : avancer l'heure du téléphone (ou forger la fin) ne fait pas gagner la partie."""
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
    page.clock.run_for(21_000)   # 21 s pour le téléphone, 1 s pour le serveur
    expect(root.locator('.pt-toast.pt-err')).to_contain_text('Rejoue')
    assert not [s for s in supa.base.saves if any(j["kind"] == "play" for j in s["p_journal"])]


def test_burst_never_covers_the_chips(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(food=40)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    root.locator('[data-pt="act"][data-a="feed"]').click()
    burst = root.locator('.pt-burst').first
    expect(burst).to_be_visible()
    b, chips = burst.bounding_box(), root.locator('.pt-chips').bounding_box()
    assert b["y"] >= chips["y"] + chips["height"], (b, chips)
    phone.shot('pet-burst-sous-les-pastilles')


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


def test_daily_chest_odds_streak_missions_and_treasures(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    assert supa.base.opens[-1] == (supa.base.users[TOK_A], "tab")
    chest = root.locator('[data-pt="chest"]')
    expect(chest).to_contain_text('Zicou a trouvé un truc')
    expect(root.locator('.pt-missions li')).to_have_count(3)
    expect(root.locator('.pt-week')).to_contain_text('Mission de la semaine')
    phone.shot('pet-9-boucle-du-jour')
    # Les chances, sous « i ».
    root.locator('[data-pt="odds"]').click()
    expect(root.locator('.pt-odds li')).to_have_count(7)
    expect(root.locator('.pt-odds')).to_contain_text('50 %')
    expect(root.locator('.pt-odds')).to_contain_text('Objet mystère')
    expect(root.locator('.pt-pity')).to_contain_text('Épique garanti')
    page.go_back()
    # Le coffre : animation, puis révélation de ce que le serveur a tiré.
    root.locator('[data-pt="chest"]').click()
    expect(root.locator('.pt-reveal h2')).not_to_be_empty()
    saved = supa.base.pets[supa.base.users[TOK_A]]["owner"]["loop"]["chest"]
    shown = (saved["found"].get("item_info") or {}).get("label") if saved["found"]["kind"] == "item" and not saved["found"].get("dup") else saved["found"]["label"]
    assert saved["opened"] and shown in root.locator('.pt-reveal h2').inner_text()
    phone.shot('pet-10-coffre')
    root.locator('.pt-reveal [data-pt="home"]').click()
    expect(root.locator('.pt-chest-done')).to_contain_text('un nouveau demain')
    expect(root.locator('[data-pt="chest"]')).to_have_count(0)
    # La série : le coffre seul ne compte pas (playtest), un câlin oui : 1 jour, prochain palier annoncé, gels.
    expect(root.locator('.pt-chips [data-pt="streak"]')).to_contain_text('0')
    root.locator('[data-pt="act"][data-a="cuddle"]').click()
    expect(root.locator('.pt-chips [data-pt="streak"]')).to_contain_text('1')
    root.locator('.pt-chips [data-pt="streak"]').click()
    expect(root.locator('.pt-streak .pt-big')).to_contain_text('1')
    expect(root.locator('.pt-next')).to_contain_text('3 j')
    expect(root.locator('.pt-miles li')).to_have_count(7)
    phone.shot('pet-11-serie')
    page.go_back()
    root.locator('.pt-more [data-pt="treasures"]').click()
    expect(root.locator('.pt-treasures [data-pt="coll"][data-s="shop"]')).to_be_visible()   # les pièces ont un usage
    expect(root.locator('.pt-album span')).to_have_count(25)
    expect(root.locator('.pt-treasures h3', has_text='Morceaux de tenues')).to_have_count(0)


def test_no_empty_pieces_title_once_every_outfit_is_won(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    owner["unlocked"] = [o[0] for o in pet.OUTFITS]
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    root.locator('.pt-more [data-pt="treasures"]').click()
    expect(root.locator('.pt-treasures')).to_contain_text('Album de stickers')
    expect(root.locator('.pt-treasures h3', has_text='Morceaux de tenues')).to_have_count(0)
    expect(root.locator('.pt-pieces')).to_have_count(0)


def test_a_notification_link_counts_as_an_open_from_a_notification(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    supa.seed(supa.base.users[TOK_A], life, owner)
    page.goto('/?tab=games&pet=1&src=notif')
    root = page.locator('#petRoot')
    expect(root.locator('.pt-gauges')).to_be_visible()
    me = supa.base.users[TOK_A]
    assert [src for uid, src in supa.base.opens if uid == me][-1] == "notification"
    nudge = supa.base.pets[me]["nudge"]
    assert nudge["title"] == "Zicou" and 8 * 60 <= nudge["minute"] <= 22 * 60 + 45


def test_zicou_shows_his_mood_on_rings_and_antenna_leds_in_the_panel_and_on_the_card(world):
    """Skin « Zicou Nuit » branché dans l'app : carte de l'onglet Jeux dessinée par le skin, et dans le panneau
    l'humeur (faim → ambre) sur les deux anneaux d'oreillette et les deux LED d'antenne, halo de la même couleur."""
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(food=10)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    assert phone.page.locator('.g-pt-ico svg .pt-led').count() == 4
    art = root.locator('.pt-hero .pt-art').first
    expect(art.locator('svg.pt-e-hungry')).to_be_visible()
    assert art.get_attribute('style') == '--pt-mood:#ffb547'
    expect(art.locator('.pt-led[fill="#ffb547"]')).to_have_count(2)
    expect(art.locator('.pt-led[stroke="#ffb547"]')).to_have_count(2)
    expect(art.locator('.pt-tear')).to_have_count(1)
    phone.shot('pet-9-zicou-faim')


# ── Retours de la testeuse « Léa » (4.11) ──

def test_lea_the_egg_hatches_on_return_without_reopening(world):
    """Les minuteurs dorment en arrière-plan sur iPhone : au retour, le compte repart de l'heure d'éclosion et l'œuf
    éclot sans rouvrir le panneau."""
    phone, supa = world
    page = phone.page
    page.clock.install(time=datetime.now(timezone.utc))
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = pet.new_pet(datetime.now(timezone.utc) - timedelta(seconds=pet.EGG_SECONDS - 4))
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    expect(root.locator('.pt-count')).to_contain_text('Éclosion dans')
    page.clock.pause_at(datetime.now(timezone.utc) + timedelta(milliseconds=500))   # l'app « dort » : plus aucun tic
    page.wait_for_timeout(5000)                                                     # 5 vraies secondes passent
    page.clock.set_system_time(datetime.now(timezone.utc))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")          # retour dans l'app
    page.clock.resume()
    # Avant : le compte reprenait où il s'était arrêté (encore ~4 s à attendre). Désormais : tout de suite.
    expect(root.locator('.pt-gauges')).to_be_visible(timeout=3_000)


def test_lea_messages_never_cover_the_chips_and_never_pile_up(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = pet.new_pet(datetime.now(timezone.utc) - timedelta(days=9))   # oublié 9 jours : grandit, s'envole
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    expect(root.locator('.pt-memo h2')).to_contain_text("s'est envolé")
    page.wait_for_timeout(2500)   # toutes les nouvelles annoncées
    toasts = root.locator('.pt-toast')
    assert toasts.count() <= 1
    assert "devenu" not in " ".join(toasts.all_inner_texts())   # jamais « devenu adulte rebelle » en même temps
    stage = root.locator('.pt-stage').bounding_box()
    for box in (t.bounding_box() for t in toasts.all()):
        assert box["y"] >= stage["y"] + stage["height"], (box, stage)
    phone.shot('pet-lea-souvenir-sans-pile')


def test_lea_two_quick_feeds_both_count(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(food=20)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    root.locator('.pt-acts [data-a="feed"]').click()
    root.locator('.pt-acts [data-a="feed"]').click()   # tout de suite après
    expect(root.locator('.pt-acts [data-a="feed"] small')).to_have_text(f'reste {pet.DAILY_LIMITS["feed"] - 2}')
    assert supa.base.pets[supa.base.users[TOK_A]]["owner"]["stats"]["feeds"] == 2
    # Les jauges ont leur valeur écrite (et lue par VoiceOver).
    expect(root.locator('.pt-gauge .pt-g-v').first).to_have_text(root.locator('.pt-bar').first.get_attribute('aria-valuenow'))
    assert "sur 100" in root.locator('.pt-bar').first.get_attribute('aria-valuetext')
    expect(root.locator('.pt-danger')).to_have_count(0)


def test_lea_morning_care_buttons_stay_on_screen_and_hunger_is_announced(world):
    phone, supa = world
    page = phone.page
    def morning(route):   # le matin (avant 11 h) : carte « Bonjour ! » avec le rêve, quelle que soit l'heure du test
        r = route.fetch()
        data = r.json()
        data["pet"]["daily"]["morning"] = "J'ai rêvé que je faisais du skate sur un arc-en-ciel, le violet glisse plus que le jaune 🌈"
        route.fulfill(response=r, json=data)
    page.route("**/api/pet/me", morning)
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(food=15)
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    expect(root.locator('.pt-morning')).to_be_visible()
    feed = root.locator('.pt-acts [data-a="feed"]')
    box = feed.bounding_box()
    assert box["y"] + box["height"] <= 844, box   # visible sans défiler (390 × 844)
    expect(root.locator('.pt-line.pt-warn')).to_contain_text('petit creux')   # avertissement visible, avant le ventre vide
    expect(root.locator('.pt-rule')).to_contain_text('un soin à')
    phone.shot('pet-lea-matin')


def test_lea_gift_message_is_not_on_the_friends_face(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    mine, owner = grown()
    supa.seed(supa.base.users[TOK_A], mine, owner)
    bob, bob_owner = grown(minutes_ago=60 * 30)
    supa.seed(BOB, bob, bob_owner)
    root = open_pet(phone)
    root.locator('.pt-more [data-pt="friends"]').click()
    root.locator('.pt-friend').first.click()
    root.locator('[data-pt="gift"][data-k="snack"]').click()
    toast = root.locator('.pt-toast', has_text='Goûter offert')
    expect(toast).to_be_visible()
    t, face = toast.bounding_box(), root.locator('.pt-stage').bounding_box()
    assert t["y"] >= face["y"] + face["height"] or t["y"] + t["height"] <= face["y"], (t, face)


def test_lea_a_clear_warning_with_the_fix_before_he_flies_away(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(food=0)
    life["starving_h"] = 40.0   # ventre vide depuis 40 h : il reste ~32 h
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    card = root.locator('.pt-danger')
    expect(card).to_contain_text("s'envolera dans environ")
    card.locator('[data-pt="alert-feed"]').click()
    expect(root.locator('.pt-danger')).to_have_count(0)
    phone.shot('pet-lea-alerte')
