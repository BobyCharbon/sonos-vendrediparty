"""Un prénom tapé par un joueur ne doit jamais devenir du code dans la page (audit des jeux).

Régression : dans « Tu me connais ? », le prénom d'un participant sans téléphone était inséré tel quel dans
les attributs du champ de réponse ; « "autofocus onfocus=alert(1) » y exécutait du code."""
import pytest
pytest.importorskip('playwright.sync_api')
from tests.e2e.helpers import Phone, Server

EVIL = '"autofocus onfocus=alert(1) x="'


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Alice')
    yield p
    errors = p.errors
    p.close()
    server.stop()
    assert not errors, '\n'.join(errors)


def test_tmc_answer_field_keeps_a_trapped_name_as_plain_text(phone):
    phone.open_games()
    html = phone.page.evaluate("""(evil) => tmcHtml({
        id: 't1', round: 1, phase: 'answer', is_host: true, players: [],
        tmc: { duo: { guesser: { name: 'Alice', pid: 'a' }, subject: { name: evil, pid: 'b' }, role: null,
                      proxy: true, mine: null, question: 'Son plat préféré ?' }, scores: [] } })""", EVIL)
    field = phone.page.evaluate("""(html) => {
        const box = document.createElement('div');
        box.innerHTML = html;
        const input = box.querySelector('#guessInput');
        return { attrs: [...input.attributes].map((a) => a.name), placeholder: input.placeholder };
    }""", html)
    assert 'onfocus' not in field['attrs'] and 'autofocus' not in field['attrs']
    assert field['placeholder'] == f'Réponse de {EVIL}'
