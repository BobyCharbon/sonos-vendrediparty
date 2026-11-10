"""Bar de la soirée dans l'app Cartes Apple (maquette v6, écran 9) : le même pass que le billet (un seul QR pour la
soirée) montre « À REMBOURSER » en grand et « À SERVIR », et l'iPhone affiche « Nouveau solde : … » à chaque service
(changeMessage). Sans bar, le pass reste exactement celui d'avant."""
from app import wallet as wl
from tests.test_wallet import EVENT_ROW, ME, PASS_AUTH, TICKET

BAR = {"balance": 10.56, "pending": 5, "payee": "Boby", "method": "Revolut", "repay_by": "2026-11-23"}


def build(**more):
    return wl.ticket_pass(origin="https://party.example", event=EVENT_ROW, user_id=ME, holder="Léa", ticket=TICKET,
                          auth_token=PASS_AUTH, **more)


def test_without_a_bar_the_pass_is_exactly_the_same_as_before():
    assert build() == build(bar=None)


def test_the_bar_puts_the_balance_first_with_a_change_message_and_keeps_the_single_qr():
    data = build(bar=BAR)
    fields = data["eventTicket"]
    assert fields["primaryFields"] == [{"key": "bar_balance", "label": "À REMBOURSER", "value": "10.56 CHF",
                                        "changeMessage": "Nouveau solde : %@"}]
    assert fields["headerFields"][0]["label"] == "À SERVIR" and fields["headerFields"][0]["value"] == "5 articles"
    assert fields["secondaryFields"][0]["value"] == build()["eventTicket"]["primaryFields"][0]["value"]  # le titre reste
    assert any("Boby" in f["value"] and "Revolut" in f["value"] and "23" in f["value"] for f in fields["backFields"])
    assert data["barcodes"] == build()["barcodes"]  # même QR : entrée et bar


def test_round_amounts_and_one_article_read_naturally():
    fields = build(bar={**BAR, "balance": 4, "pending": 1, "repay_by": None})["eventTicket"]
    assert fields["primaryFields"][0]["value"] == "4 CHF" and fields["headerFields"][0]["value"] == "1 article"
