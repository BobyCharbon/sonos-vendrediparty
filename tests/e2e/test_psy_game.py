"""« Qui es-tu vraiment ? » de bout en bout (vrais boutons) : chacun répond aux 12 questions sur son téléphone, valide,
l'animateur révèle ; chacun voit son profil, son score de logique, le groupe et les âmes sœurs."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


@pytest.fixture
def phones(browser):
    server = Server()
    made = []

    def make(name, device='iphone'):
        p = Phone(browser, server, name, device)
        made.append(p)
        return p
    yield make
    errors = [e for p in made for e in p.errors]
    for p in made:
        p.close()
    server_errors = server.errors()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def answer_everything(phone, pick=0):
    for i in range(12):
        expect(phone.page.locator('.ps-top')).to_contain_text(f'Question {i + 1}/12')
        phone.page.locator('.ps-opt').nth(pick).click()
    phone.tap('[data-gact="psysub"]')
    expect(phone.page.locator('.ps-hero')).to_contain_text('Chut')


def test_everyone_answers_in_secret_then_the_host_reveals_the_profiles(phones):
    lou, ana = phones('Lou'), phones('Ana', 'android')
    code = lou.create('psy')
    ana.join(code)
    wait_state(lou, lambda g: len(g['players']) == 2)
    lou.tap('[data-gact="start"]')
    expect(ana.page.locator('.ps-q-t')).to_be_visible()
    answer_everything(ana, 0)
    answer_everything(lou, 0)
    lou.tap('[data-gact="psyreveal"]')
    for p in (lou, ana):
        expect(p.page.locator('.ps-me-n')).to_be_visible()
        expect(p.page.locator('.ps-logic')).to_contain_text('/3')
        expect(p.page.locator('.ps-group')).to_contain_text('Âmes sœurs')
    expect(ana.page.locator('[data-gact="next"]')).to_have_count(0)  # nouveau test : l'animateur
    lou.tap('[data-gact="next"]')
    expect(ana.page.locator('.ps-top')).to_contain_text('Question 1/12')
