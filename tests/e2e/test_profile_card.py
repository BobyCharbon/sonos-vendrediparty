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
