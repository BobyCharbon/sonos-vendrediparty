"""Fiche profil dans les jeux, de bout en bout : le nom d'un joueur qui a un compte Party ouvre sa fiche ;
un joueur sans compte n'est pas touchable. Le serveur ne reçoit que la partie et le numéro du joueur."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in  # noqa: E402


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


def test_tapping_a_player_with_an_account_opens_the_profile_card(browser, server):
    lea, tom = Phone(browser, server, "Lea"), Phone(browser, server, "Tom")
    try:
        lea.page.goto("/")
        sign_in(lea, "jeton-de-test-guest-plus-0001")  # « Léa » sur la fausse base
        lea.page.wait_for_function("account && account.name === 'Léa'")
        code = lea.create("undercover")
        tom.page.goto("/")
        sign_in(tom, "jeton-de-test-guest-0001")  # « Tom », connecté lui aussi pour voir les profils
        tom.page.wait_for_function("account && account.name === 'Tom'")
        tom.join(code)

        pill = tom.page.locator('.g-lobby-players [data-profile-pid]').filter(has_text="Léa")
        expect(pill).to_be_visible()
        pill.click()
        card = tom.page.locator(".pc-card")
        expect(card).to_contain_text("Léa")
        expect(card).to_contain_text("Guest+")
        tom.shot("profile_card_game")
        card.locator(".pc-close").click()
        expect(card).to_be_hidden()
        assert not lea.errors and not tom.errors and not server.errors(), lea.errors + tom.errors
    finally:
        lea.close(); tom.close()


def test_a_player_without_an_account_is_not_tappable(browser, server):
    lea, max_ = Phone(browser, server, "Lea"), Phone(browser, server, "Max")
    try:
        lea.page.goto("/")
        sign_in(lea, "jeton-de-test-guest-plus-0001")
        lea.page.wait_for_function("account && account.name === 'Léa'")
        code = lea.create("undercover")
        max_.page.goto("/")
        max_.join(code)  # Max : invité sans compte
        expect(lea.page.locator(".g-lobby-players").filter(has_text="Max")).to_be_visible()
        assert lea.page.locator('.g-lobby-players [data-profile-pid]').filter(has_text="Max").count() == 0
    finally:
        lea.close(); max_.close()


def test_names_in_the_vote_results_open_the_profile_too(browser, server):
    """Avis 36c47b3d1f82 : dans les résultats d'un vote (« Qui de nous ? »), le nom d'un joueur avec un compte se touche
    et ouvre sa fiche ; les avatars de ceux qui ont voté aussi."""
    lea, tom = Phone(browser, server, "Lea"), Phone(browser, server, "Tom")
    try:
        lea.page.goto("/")
        sign_in(lea, "jeton-de-test-guest-plus-0001")
        lea.page.wait_for_function("account && account.name === 'Léa'")
        code = lea.create("whoof")
        tom.page.goto("/")
        sign_in(tom, "jeton-de-test-guest-0001")  # connecté : on ne voit les profils qu'avec un compte
        tom.page.wait_for_function("account && account.name === 'Tom'")
        tom.join(code)
        expect(lea.page.locator(".g-lobby-players").filter(has_text="Tom")).to_be_visible()
        lea.tap('[data-gact="start"]')
        expect(lea.page.locator(".qs-q")).to_contain_text("Qui de nous")
        lea.page.locator(".qs-pick", has_text="Moi").click()
        expect(lea.page.locator(".qs-who[data-profile-pid]")).to_have_count(2)  # les avatars des votants se touchent
        tom.page.locator(".qs-pick", has_text="Léa").click()
        winner = tom.page.locator(".qs-win-names [data-profile-pid]")
        expect(winner).to_have_text("Léa", timeout=10000)
        tom.shot("profile_from_results")
        winner.click()
        expect(tom.page.locator(".pc-card")).to_contain_text("Léa")
        assert not lea.errors and not tom.errors and not server.errors(), lea.errors + tom.errors
    finally:
        lea.close(); tom.close()


def test_two_players_with_the_same_name_each_open_their_own_profile(browser, server):
    """Deux « Léa » à la table : le nom dans les résultats ouvre la fiche de celle qui a reçu les votes (son pid), jamais
    celle de l'autre ; sans pid (Pour ou contre ne donne que des prénoms), un prénom en double n'ouvre aucune fiche."""
    lea = Phone(browser, server, "Lea")
    try:
        lea.open_games()
        links = lea.page.evaluate("""() => {
          const g = { code: '1234', type: 'whoof', options: {}, players: [
            { pid: 'p1', name: 'Léa', account: true }, { pid: 'p2', name: 'Léa', account: true }],
            results: [{ pid: 'p2', name: 'Léa', count: 2 }, { pid: 'p1', name: 'Léa', count: 1 }] };
          const box = document.createElement('div');
          box.innerHTML = resultsHtml(g);
          const won = [...box.querySelectorAll('.qs-win-names [data-profile-pid]')].map((e) => e.dataset.profilePid);
          const rest = [...box.querySelectorAll('.qs-bars [data-profile-pid]')].map((e) => e.dataset.profilePid);
          return { won, rest, debate: whoName(g, 'Léa') };
        }""")
        assert links["won"] == ["p2"] and links["rest"] == ["p1"]
        assert "data-profile-pid" not in links["debate"]
        assert lea.errors == []
    finally:
        lea.close()
