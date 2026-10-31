"""« Tu me connais ? » de bout en bout (vrais boutons) : la personne interrogée écrit sa réponse en secret, puis c'est
ELLE qui la révèle quand le devin a parlé à voix haute (avis 4e5e56ee8168) ; le devin n'a pas ce bouton."""
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


def test_the_subject_reveals_her_own_answer_when_the_guesser_has_spoken(phones):
    host, ana, bob = phones('Lou'), phones('Ana'), phones('Bob', 'android')
    code = host.create('tmc')
    ana.join(code)
    bob.join(code)
    wait_state(host, lambda g: len(g['players']) >= 3)
    host.tap('[data-gact="start"]')
    duo = wait_state(host, lambda g: g['phase'] == 'answer')['tmc']['duo']
    by_name = {p.name: p for p in (host, ana, bob)}
    subject, guesser = by_name[duo['subject']['name']], by_name[duo['guesser']['name']]
    subject.page.locator('#guessInput').fill('Une 2CV')
    subject.page.locator('form[data-gform="tanswer"] button').click()
    wait_state(host, lambda g: g['phase'] == 'guess')
    expect(guesser.page.locator('[data-gact="treveal"].tm-reveal')).to_have_count(0)  # le devin ne révèle pas
    subject.tap('.tm-reveal')
    for p in (host, ana, bob):
        expect(p.page.locator('.tm-answer b')).to_have_text('Une 2CV')
