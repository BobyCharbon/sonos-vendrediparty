"""Contrôle du 26.11 (Apple 1.2) : dans l'app App Store, la case « J'ai 18 ans ou plus et j'accepte les conditions
d'utilisation » sous « Comment tu t'appelles ? » (games.js), cochée une fois par appareil. Sans elle, on ne joue pas avec
les autres (le serveur refuse tout texte lu par la table) ; on peut refuser, partir et revenir. Les conditions s'ouvrent
sur place. La page de l'app (scripts /static-store/) tourne sans erreur. Le navigateur : aucune case."""
import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import IGNORED_CONSOLE, Server, show_game_cards

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    s.stop()


def phone(browser, server, store=True, init=""):
    ctx = browser.new_context(base_url=server.url, user_agent=UA + (" PartyStore" if store else ""), **IPHONE)
    ctx.add_init_script('localStorage.setItem("vp_install_dismissed", "1");' + init)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not any(x in m.text for x in IGNORED_CONSOLE) and page.errors.append(m.text))
    page.on("dialog", lambda d: d.accept())
    page.goto("/")
    page.evaluate("showTab('games')")
    return ctx, page


def test_refuse_the_terms_then_come_back_and_accept(browser, server):
    ctx, page = phone(browser, server)
    page.wait_for_selector("#gName:not(.hidden) #gTermsCheck")
    box = page.locator("#gTermsBox")
    assert "18 ans ou plus" in box.inner_text() and "tolérance zéro" in box.inner_text()
    # Sans la case : on reste sur l'écran du prénom, qui dit pourquoi.
    page.fill("#gNameInput", "Léa")
    page.click("#gNameForm button")
    assert page.locator("#gHome").is_hidden() and "warn" in box.get_attribute("class")
    assert "coche d'abord la case" in page.inner_text("#gTermsNote")
    # Les conditions s'ouvrent sur place (la page ne change pas), puis se ferment.
    page.click("[data-gterms=open]")
    page.wait_for_selector("#gTermsSheet:not(.hidden)")
    assert page.get_attribute("#gTermsFrame", "src") == "/events/terms?app=ios" and page.url.endswith("/")
    page.click("#gTermsSheet .g-help[data-gterms=close]")
    assert page.locator("#gTermsSheet").is_hidden()
    # Elle part et revient plus tard : toujours la case, rien n'a été enregistré.
    page.reload()
    page.evaluate("showTab('games')")
    page.wait_for_selector("#gName:not(.hidden) #gTermsCheck")
    assert page.evaluate("localStorage.getItem('vp_games_terms')") is None and page.evaluate("localStorage.getItem('vp_name')") is None
    # Cette fois, elle accepte : l'accueil des jeux, et la case n'est plus jamais redemandée sur ce téléphone.
    page.fill("#gNameInput", "Léa")
    page.check("#gTermsCheck")
    page.click("#gNameForm button")
    page.wait_for_selector("#gHome:not(.hidden)")
    page.reload()
    page.evaluate("showTab('games')")
    page.wait_for_selector("#gHome:not(.hidden)")
    assert page.locator("#gName").is_hidden()
    assert page.errors == []
    ctx.close()


def test_after_accepting_she_writes_and_plays_without_error(browser, server):
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Tom"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    # Salle de jeux puis un prénom ajouté (texte lu par la table) : accepté par le serveur.
    page.click('#gHome [data-create="room"]')
    page.wait_for_selector('[data-room-pick="quiz"]', state="visible")
    assert page.evaluate("gameAction('addguest', { guess: 'Max' })") is True
    page.wait_for_function("game.players.some((p) => p.name === 'Max')")
    page.evaluate("gameAction('end')")
    page.wait_for_function("!myGame")
    # Les jeux gardés s'ouvrent avec les scripts de l'app (aucune erreur de script).
    show_game_cards(page)
    for kind in ("likely", "undercover", "masque", "tmc", "debate"):
        page.click(f'#gHome [data-create="{kind}"]')
        page.wait_for_function("(k) => game && game.type === k", arg=kind)
        page.wait_for_selector("#gamePlay:not(.hidden)")
        page.evaluate("gameAction('end')")
        page.wait_for_function("!myGame")
        show_game_cards(page)
    assert page.errors == [], page.errors
    assert not server.errors()
    ctx.close()


def test_later_then_the_server_refusal_reopens_the_box(browser, server):
    # Prénom donné avant la mise à jour, case jamais cochée : l'écran du prénom revient, déjà rempli, avec « Plus tard ».
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Zoé");')
    page.wait_for_selector("#gName:not(.hidden) #gTermsLater:not(.hidden)")
    assert page.input_value("#gNameInput") == "Zoé"
    page.click("#gTermsLater")
    page.wait_for_selector("#gHome:not(.hidden)")
    # Elle crée une salle (son prénom serait lu par la table) : le serveur refuse, la case revient avec la raison.
    page.click('#gHome [data-create="room"]')
    page.wait_for_selector("#gName:not(.hidden) #gTermsCheck")
    assert "conditions" in page.inner_text("#gTermsNote")
    page.check("#gTermsCheck")
    page.wait_for_selector("#gHome:not(.hidden)")
    page.click('#gHome [data-create="room"]')
    page.wait_for_selector('[data-room-pick="quiz"]', state="visible")
    assert page.errors == []
    ctx.close()


def test_the_browser_has_no_box(browser, server):
    ctx, page = phone(browser, server, store=False)
    page.wait_for_selector("#gName:not(.hidden)")
    assert page.locator("#gTermsCheck").count() == 0
    page.fill("#gNameInput", "Léa")
    page.click("#gNameForm button")
    page.wait_for_selector("#gHome:not(.hidden)")
    ctx.close()


def test_reopening_the_app_never_reopens_full_screen_a_game_she_stopped_playing(browser, server):
    """D4 (recette iPhone du 26.11) : seule dans le salon d'un jeu 3D, ou après « Arrêter de jouer », la réouverture de
    l'app montre les onglets (partie réduite), jamais le salon en plein écran."""
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Tom"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    show_game_cards(page)
    page.click('#gHome [data-create="neon"]')
    page.wait_for_function("game && game.type === 'neon'")
    assert page.evaluate("pyrFull") is True  # toute neuve : plein écran
    page.reload()
    page.evaluate("showTab('games')")
    page.wait_for_function("game && game.type === 'neon'")
    page.wait_for_selector('[data-pyr="enter"]')
    assert page.evaluate("pyrFull") is False
    assert page.errors == [], page.errors
    ctx.close()


def test_a_refused_new_name_keeps_the_old_one_and_says_why(browser, server):
    """Contrôle du 26.11 (tour 1) : le prénom changé en haut à droite attend la réponse du serveur ; refusé (insulte,
    boisson dans l'app), l'ancien reste et la raison s'affiche."""
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Tom"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    for bad in ("Vodka", "connard"):
        page.evaluate(f"window.prompt = () => {bad!r}; changeName()")
        page.wait_for_function("document.getElementById('toast').textContent.includes(\"n'a pas changé\")")
        assert page.evaluate("guestName") == "Tom" and "Tom" in page.text_content("#nameChip")
        assert page.evaluate("localStorage.getItem('vp_name')") == "Tom"
    page.evaluate("window.prompt = () => 'Lucas'; changeName()")
    page.wait_for_function("guestName === 'Lucas'")
    assert "Lucas" in page.text_content("#nameChip")
    assert page.errors == []
    ctx.close()
