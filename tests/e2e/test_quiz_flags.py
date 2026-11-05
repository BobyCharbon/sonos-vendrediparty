"""Quiz, catégorie Drapeaux (avis 544a8fd8b5bd), de bout en bout (vrais boutons) : l'animateur choisit « Drapeaux »
seul, lance en solo, la question montre le drapeau en grand (ou des drapeaux en réponses), on répond, la révélation
arrive."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state

BIG_FLAG_PX = 80  # drapeau de la question : au moins 80 px de haut sur un iPhone


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Alice')
    yield p
    errors = p.errors
    p.close()
    server_errors = server.errors()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def test_host_picks_flags_and_the_flag_is_shown_big(phone):
    page = phone.page
    phone.create('quiz')
    theme = page.locator('[data-qz-theme="drapeaux"]')
    expect(theme).to_contain_text('Drapeaux')
    theme.click()
    wait_state(phone, lambda g: g['quiz']['settings']['themes'] == ['drapeaux'])
    phone.tap('[data-qz-set="diff"][data-val="1"]')
    wait_state(phone, lambda g: g['quiz']['settings']['diff'] == '1')
    phone.tap('.qz-go')
    expect(page.locator('.qz-qcard')).to_be_visible()
    expect(page.locator('.qz-qmeta')).to_contain_text('Drapeaux')
    question_flag = page.locator('.qz-qtext .qz-flag')
    answer_flags = page.locator('.qz-ans .qz-flag')
    expect(question_flag.or_(answer_flags.first)).to_be_visible()
    if question_flag.count():
        assert question_flag.bounding_box()['height'] >= BIG_FLAG_PX
    else:
        assert answer_flags.count() == 4
    phone.shot('quiz-drapeaux')
    page.locator('.qz-ans').first.click()
    wait_state(phone, lambda g: g['phase'] == 'rev')
    expect(page.locator('.qz-ans.right')).to_have_count(1)
