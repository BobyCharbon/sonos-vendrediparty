"""Animations de l'onglet Musique (list-motion.js, now-progress.js, toast.js) dans un vrai navigateur (iPhone).
La page se rafraîchit souvent : un état identique ne doit rien redessiner (rien ne « se rejoue »), la file garde ses
lignes d'un rendu à l'autre (les titres glissent au lieu d'être recréés), la barre de progression avance seule et
un message flottant repart en s'effaçant. Le titre piégé reste du texte."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import DEVICES, Server  # noqa: E402

TRAP = '<img src=x onerror="window.hacked=1">'


def track(i, mine=False):
    return {"title": f"Titre {i}", "artist": f"Artiste {i}", "art": "", "by": "Léa" if mine else None,
            "rid": f"r{i}" if mine else None, "eta": 60 * i, "track_id": f"t{i}"}


def state(upcoming, now=1, playing=True):
    return {"active": True, "room": "Salon", "state": "PLAYING" if playing else "PAUSED_PLAYBACK", "name": "Boby",
            "now": {**track(now), "title": TRAP, "position": "0:01:00", "duration": "0:04:00"},
            "upcoming": [track(i, mine=i == 3) for i in upcoming], "upcoming_total": len(upcoming),
            "played": [], "messages": [], "source": "sonos", "queue_editable": True}


@pytest.fixture
def phone(browser):
    server = Server()
    ctx = browser.new_context(base_url=server.url, **DEVICES["iphone"])
    ctx.add_init_script("localStorage.setItem('vp_name','Boby'); localStorage.setItem('vp_install_dismissed','1');")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    current = {"state": state((2, 3, 4))}
    page.route("**/api/state*", lambda r: r.fulfill(json=current["state"]))
    page.route("**/api/hello", lambda r: r.fulfill(json={}))
    page.goto("/")
    page.locator('#tabs [data-tab="music"]').click()  # l'app s'ouvre sur Événements (avis fb95d317cb64)
    expect(page.locator("#party")).to_be_visible()
    expect(page.locator("#upcoming .track")).to_have_count(3)
    yield page, current
    ctx.close()
    server.stop()
    assert not errors, "\n".join(errors)


def rows(page):
    return page.locator("#upcoming .track:not([data-lm-leaving]) .title").all_inner_texts()


def test_an_identical_refresh_redraws_nothing(phone):
    page, _ = phone
    same = page.evaluate("""async () => {
        const row = document.querySelector('#upcoming .track'), art = document.querySelector('#now img');
        await refresh(); await refresh();
        return row === document.querySelector('#upcoming .track') && art === document.querySelector('#now img'); }""")
    assert same
    assert page.evaluate("window.hacked") is None
    expect(page.locator("#now .title")).to_have_text(TRAP)


def test_the_queue_keeps_its_rows_when_a_track_is_added_moved_or_removed(phone):
    page, current = phone
    current["state"] = state((4, 5, 2, 3))   # 4 remonte en tête, 5 arrive
    page.evaluate("refresh()")
    expect(page.locator("#upcoming .track:not([data-lm-leaving])")).to_have_count(4)
    assert rows(page) == ["Titre 4", "Titre 5", "Titre 2", "Titre 3"]
    current["state"] = state((4, 5, 3))       # 2 retiré
    page.evaluate("refresh()")
    expect(page.locator("#upcoming [data-lm-leaving]")).to_have_count(0, timeout=3000)
    assert rows(page) == ["Titre 4", "Titre 5", "Titre 3"]
    current["state"] = state(())              # file vide : le message remplace les lignes après leur départ
    page.evaluate("refresh()")
    expect(page.locator("#upcoming .empty")).to_be_visible()
    expect(page.locator("#upcoming .track")).to_have_count(0, timeout=3000)


def test_the_progress_bar_advances_on_its_own_and_freezes_on_pause(phone):
    page, current = phone
    bar = page.locator("#now .now-progress")
    expect(bar).to_be_visible()
    scale = "() => new DOMMatrix(getComputedStyle(document.querySelector('#now .now-progress i')).transform).a"
    first = page.evaluate(scale)
    assert 0.24 < first < 0.3   # 1 min sur 4
    page.wait_for_timeout(1200)
    assert page.evaluate(scale) > first
    current["state"] = state((2, 3, 4), playing=False)
    page.evaluate("refresh()")
    page.wait_for_timeout(300)
    paused = page.evaluate(scale)
    page.wait_for_timeout(800)
    assert page.evaluate(scale) == pytest.approx(paused)


def test_a_toast_leaves_by_fading_out_then_hides(phone):
    page, _ = phone
    page.evaluate("toast('Titre ajouté', 'ok')")
    expect(page.locator("#toast")).to_be_visible()
    page.evaluate("toast('Autre message')")   # remplacé sur place
    expect(page.locator("#toast")).to_have_text("Autre message")
    page.evaluate("hideToast()")
    expect(page.locator("#toast")).to_have_class("toast hidden", timeout=2000)
