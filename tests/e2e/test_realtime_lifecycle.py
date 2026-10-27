"""Exercise visible exits and resource cleanup, not just game rules."""
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect
from tests.e2e.helpers import wait_state
from tests.e2e.test_heist_game import phones


@pytest.mark.parametrize("kind", ["island", "neon", "heist"])
@pytest.mark.parametrize("playing", [False, True])
def test_visible_exit_for_player_and_host_stops_frame_requests(phones,kind,playing):
    host=phones("ExitHost");friend=phones("ExitFriend")
    host.page.set_viewport_size({"width":320,"height":740})
    code=host.create(kind);friend.join(code)
    wait_state(host,lambda g:len(g["players"])==2)
    if playing:
        host.page.locator('#game [data-gact="start"]').click()
        wait_state(host,lambda g:g["phase"]=="play")
    # The exit is visible at phone width and does not require finding the drawer footer.
    friend.page.locator('#gTop .g-quit').click()
    leave=friend.page.locator('[data-exit="away"]')  # « Quitter » : libère sa place et part
    expect(leave).to_be_in_viewport()
    expect(leave).to_contain_text("Quitter")
    friend.page.on("dialog",lambda d:d.accept())
    leave.click()
    expect(friend.page.locator("#gHome")).to_be_visible()
    wait_state(host,lambda g:len(g["players"])==1)
    requests=[]
    friend.page.on("request",lambda r:requests.append(r.url) if r.url.endswith("/"+kind) else None)
    friend.page.wait_for_timeout(800)
    assert not requests
    assert friend.page.evaluate("localStorage.getItem('vp_game')")==""
    host.page.locator('#gTop .g-quit').click()
    close=host.page.locator('[data-exit="end"]')
    expect(close).to_be_in_viewport()
    host.page.on("dialog",lambda d:d.accept())
    close.click()
    expect(host.page.locator("#gHome")).to_be_visible()
    host.page.reload()
    expect(host.page.locator("#gamePlay")).not_to_be_visible()


def test_failed_handover_keeps_host_and_menu_blocks_keyboard(phones):
    host=phones("Leader");friend=phones("Partner")
    code=host.create("heist");friend.join(code)
    wait_state(host,lambda g:len(g["players"])==2)
    host.page.locator('#game [data-gact="start"]').click()
    wait_state(host,lambda g:g["phase"]=="play")
    host.page.locator('#gTop .g-quit').click()
    before=host.state()["heist"]["fighters"]
    host.page.keyboard.down("ArrowRight")
    host.page.wait_for_timeout(600)
    host.page.keyboard.up("ArrowRight")
    after=host.state()["heist"]["fighters"]
    assert [(p["x"],p["y"]) for p in before]==[(p["x"],p["y"]) for p in after]
    host.page.locator('[data-exit="pick"]').click()
    host.page.on("dialog",lambda d:d.accept())
    host.page.route("**/api/games/"+code,lambda route:route.fulfill(status=409,content_type="application/json",body='{"detail":"Transfert impossible"}') if route.request.method=="POST" else route.continue_())
    host.page.locator('[data-exit="to"]').click()
    expect(host.page.locator(".toast")).to_contain_text("Transfert impossible")
    expect(host.page.locator("#gamePlay")).to_be_visible()
    assert host.page.evaluate("localStorage.getItem('vp_game')")==code


@pytest.mark.parametrize("kind", ["island","neon","heist"])
def test_host_can_transfer_and_leave_without_closing_friends_game(phones,kind):
    host=phones("FormerHost");friend=phones("NewHost")
    code=host.create(kind);friend.join(code)
    wait_state(host,lambda g:len(g["players"])==2)
    host.page.locator("#gTop .g-quit").click()
    host.page.locator('[data-exit="pick"]').click()
    host.page.on("dialog",lambda d:d.accept())
    host.page.locator('[data-exit="to"]').click()
    # Passer la main ne fait plus quitter (retour 26.10) : l'ancien animateur reste joueur…
    wait_state(friend,lambda g:g["is_host"] and len(g["players"])==2)
    expect(host.page.locator("#gamePlay")).to_be_visible()
    # … et part ensuite avec « Quitter », sans fermer la partie de son ami.
    host.page.locator("#gTop .g-quit").click()
    host.page.locator('[data-exit="away"]').click()
    wait_state(friend,lambda g:g["is_host"] and len(g["players"])==1)
    assert friend.current()==code


def test_delayed_old_refresh_cannot_reopen_room_after_exit(phones):
    host=phones("LateReply");code=host.create("heist")
    pending=[]
    host.page.route("**/api/games/"+code+"?*",lambda route:pending.append(route))
    host.page.evaluate("() => { void refreshGame(); }")
    host.page.wait_for_timeout(100)
    assert pending
    host.page.locator("#gTop .g-quit").click()
    host.page.on("dialog",lambda d:d.accept())
    host.page.locator('[data-exit="end"]').click()
    expect(host.page.locator("#gHome")).to_be_visible()
    for route in pending:
        route.fulfill(status=404,content_type="application/json",body='{"detail":{"ended":{"room":"9999"}}}')
    host.page.unroute("**/api/games/"+code+"?*")
    host.page.wait_for_timeout(500)
    expect(host.page.locator("#gHome")).to_be_visible()
    assert host.page.evaluate("localStorage.getItem('vp_game')")==""



def test_stop_playing_keeps_you_watching_then_quit_leaves(phones):
    """« Arrêter de jouer » libère la place mais on reste pour regarder ; « Quitter » fait vraiment partir."""
    host=phones("Animatrice");friend=phones("Ami")
    code=host.create("heist");friend.join(code)
    wait_state(host,lambda g:len(g["players"])==2)
    friend.page.on("dialog",lambda d:d.accept())
    friend.page.locator('#gTop .g-quit').click()
    stop=friend.page.locator('[data-exit="leave"]')
    expect(stop).to_contain_text("Arrêter de jouer")
    stop.click()
    wait_state(host,lambda g:len(g["players"])==1)
    expect(friend.page.locator("#gamePlay")).to_be_visible()  # il regarde toujours
    assert friend.page.evaluate("localStorage.getItem('vp_game')")==code
    friend.page.locator('#gTop .g-quit').click()
    expect(friend.page.locator('[data-exit="leave"]')).to_have_count(0)
    friend.page.locator('[data-exit="away"]').click()
    expect(friend.page.locator("#gHome")).to_be_visible()
    assert friend.page.evaluate("localStorage.getItem('vp_game')")==""
