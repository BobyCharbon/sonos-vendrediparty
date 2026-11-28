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
    # Décision du 28.11 : le prénom se touche dans la liste du serveur (aucun champ de texte) ; « 🎲 Joueur » d'abord.
    page.wait_for_selector('#gName [data-pick-name="Léa"]')
    assert page.locator("#gName input[type=text], #gName textarea").count() == 0
    assert page.locator("[data-name-pick] [data-pick-name]").first.get_attribute("data-pick-name") == "Joueur"
    # Sans la case : on reste sur l'écran du prénom, qui dit pourquoi.
    page.click('#gName [data-pick-name="Léa"]')
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
    page.check("#gTermsCheck")
    page.click('#gName [data-pick-name="Léa"]')
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
    assert page.evaluate("gameAction('addguest', { guess: 'Max' })") is True  # hors de la liste : « Joueur N »
    page.wait_for_function("game.players.some((p) => p.name.startsWith('Joueur ')) && !game.players.some((p) => p.name === 'Max')")
    page.evaluate("gameAction('end')")
    page.wait_for_function("!myGame")
    # Les jeux gardés s'ouvrent avec les scripts de l'app (aucune erreur de script).
    show_game_cards(page)
    for kind in ("likely", "undercover", "debate"):  # tmc, masque : cachés dans l'app (28.11)
        page.click(f'#gHome [data-create="{kind}"]')
        page.wait_for_function("(k) => game && game.type === k", arg=kind)
        page.wait_for_selector("#gamePlay:not(.hidden)")
        if kind == "likely":  # participant sans téléphone : choisi dans la liste, aucun champ de texte (28.11)
            page.wait_for_selector('[data-gform=addguest] select[name=manualName]', state="attached")
            assert page.locator('[data-gform=addguest] input').count() == 0
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
    # Contrôle Apple, tour 4 : « Plus tard » = Méninges seul (rien d'écrit n'est lu par d'autres), sans salle ni code.
    page.wait_for_selector("#gHome.g-solo:not(.hidden)")
    assert page.locator('#gHome [data-brain-open="brain"]').is_visible()
    assert page.locator('#gHome [data-create="room"]').is_hidden() and page.locator("#gCode").is_hidden()
    # « Jouer avec les autres » : la case revient ; cochée, la salle de jeux.
    page.click("[data-gsolo-back]")
    page.wait_for_selector("#gName:not(.hidden) #gTermsCheck")
    page.check("#gTermsCheck")
    page.wait_for_selector("#gHome:not(.hidden):not(.g-solo)")
    page.click('#gHome [data-create="room"]')
    page.wait_for_selector('[data-room-pick="quiz"]', state="visible")
    assert page.errors == []
    ctx.close()


def test_later_is_shown_from_the_start_and_opens_meninges_without_a_name(browser, server):
    """Contrôle Apple, tour 4 : le texte parle de « revenir plus tard » : le bouton est là d'office, sans prénom."""
    ctx, page = phone(browser, server)
    page.wait_for_selector("#gName:not(.hidden) #gTermsLater:not(.hidden)")
    page.click("#gTermsLater")
    page.wait_for_selector("#gHome.g-solo:not(.hidden)")
    page.click('#gHome [data-brain-open="brain"]')
    page.wait_for_function("!!window.Brain")
    assert page.evaluate("localStorage.getItem('vp_name')") is None
    assert page.errors == [], page.errors
    ctx.close()


def test_joueur_gets_a_number_from_the_game(browser, server):
    """Décision du 28.11 : « 🎲 Joueur » (aucun prénom) ; la partie donne « Joueur N », jamais un texte tapé."""
    ctx, page = phone(browser, server)
    page.wait_for_selector("#gName:not(.hidden) #gTermsCheck")
    page.check("#gTermsCheck")
    page.click('#gName [data-pick-name="Joueur"]')
    page.wait_for_selector("#gHome:not(.hidden)")
    assert page.evaluate("guestName") == "Joueur"
    show_game_cards(page)
    page.click('#gHome [data-create="likely"]')
    page.wait_for_function("game && game.type === 'likely' && game.players.length === 1")
    assert page.evaluate("game.players[0].name") == "Joueur 1"
    assert page.errors == [], page.errors
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


def test_the_name_chip_reopens_the_list_never_a_text_field(browser, server):
    """Décision du 28.11 : le prénom en haut à droite se rechoisit dans la liste (aucune fenêtre de saisie)."""
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Tom"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    page.evaluate("window.prompt = () => { throw new Error('prompt'); }; changeName()")
    page.wait_for_selector('#gName:not(.hidden) [data-pick-name="Tom"][aria-pressed="true"]')
    page.click('#gName [data-pick-name="Lucas"]')
    page.wait_for_function("guestName === 'Lucas'")
    page.wait_for_selector("#gHome:not(.hidden)")
    assert "Lucas" in page.text_content("#nameChip")
    assert page.errors == [], page.errors
    ctx.close()
