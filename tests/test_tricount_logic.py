"""Tricount : le calcul (parts au centime, soldes, remboursements les moins nombreux, catégories, IBAN, liens de paiement).
Pur Python, sans base : c'est ce que l'app affiche."""
import pytest

from app import tricount_logic as tc

A, B, C, D = "a", "b", "c", "d"


def expense(amount, paid_by, shares, mode="equal", kind="expense", rate=1, currency="CHF"):
    return {"id": f"e{amount}{paid_by}", "kind": kind, "amount_cents": amount, "paid_by": paid_by, "split_mode": mode,
            "rate": rate, "currency": currency, "shares": shares}


def eq(*ids):
    return [{"member_id": i, "weight": 1, "amount_cents": None} for i in ids]


def test_equal_split_gives_cents_to_the_first_without_losing_any():
    parts = tc.split(expense(1000, A, eq(A, B, C)))
    assert parts == {A: 334, B: 333, C: 333} and sum(parts.values()) == 1000


def test_split_by_shares_and_by_exact_amounts():
    by_shares = expense(900, A, [{"member_id": A, "weight": 2}, {"member_id": B, "weight": 1}], mode="shares")
    assert tc.split(by_shares) == {A: 600, B: 300}
    exact = expense(1000, A, [{"member_id": A, "amount_cents": 250}, {"member_id": B, "amount_cents": 750}], mode="amounts")
    assert tc.split(exact) == {A: 250, B: 750}


def test_foreign_currency_is_converted_into_the_group_currency():
    parts = tc.split(expense(1000, A, eq(A, B), currency="EUR", rate=0.95))
    assert sum(parts.values()) == 950  # 10 € à 0,95 = 9,50 CHF


def test_balances_sum_to_zero_and_a_transfer_settles_a_debt():
    members = [A, B, C]
    exps = [expense(3000, A, eq(A, B, C)), expense(600, B, eq(A, B, C))]
    bal = tc.balances(members, exps)
    assert bal == {A: 1800, B: -600, C: -1200} and sum(bal.values()) == 0
    exps.append(expense(1200, C, eq(A), kind="transfer"))  # C rembourse A
    assert tc.balances(members, exps)[C] == 0


def test_settlement_uses_as_few_transfers_as_possible():
    bal = {A: 3000, B: -1000, C: -1000, D: -1000}
    plan = tc.settle(bal)
    assert len(plan) == 3 and all(t["to"] == A for t in plan) and sum(t["amount_cents"] for t in plan) == 3000
    bal = {A: 1000, B: 500, C: -1500}
    assert tc.settle(bal) == [{"from": C, "to": A, "amount_cents": 1000}, {"from": C, "to": B, "amount_cents": 500}]
    assert tc.settle({A: 0, B: 0}) == []


def test_settlement_never_leaves_a_debt_behind_on_random_groups():
    import random
    rng = random.Random(3)
    for _ in range(300):
        n = rng.randint(2, 9)
        vals = [rng.randint(-50000, 50000) for _ in range(n - 1)]
        bal = {f"m{i}": v for i, v in enumerate(vals)} | {f"m{n - 1}": -sum(vals)}
        plan = tc.settle(bal)
        after = dict(bal)
        for t in plan:
            after[t["from"]] += t["amount_cents"]
            after[t["to"]] -= t["amount_cents"]
        assert all(v == 0 for v in after.values()) and len(plan) <= n - 1


@pytest.mark.parametrize("title, category", [("Migros", "food"), ("Courses Coop", "food"), ("Essence Shell", "transport"),
                                             ("Billets de train CFF", "transport"), ("Airbnb Lisbonne", "lodging"),
                                             ("Resto italien", "restaurant"), ("Bières au bar", "drinks"), ("Cinéma", "leisure"),
                                             ("Truc divers", "other")])
def test_category_is_guessed_from_the_title(title, category):
    assert tc.guess_category(title) == category


def test_iban_is_checked_and_formatted():
    assert tc.clean_iban("ch93 0076 2011 6238 5295 7") == "CH9300762011623852957"
    assert tc.format_iban("CH9300762011623852957") == "CH93 0076 2011 6238 5295 7"
    with pytest.raises(ValueError):
        tc.clean_iban("CH93 0076 2011 6238 5295 8")  # clé de contrôle fausse


def test_payment_links_are_normalised_and_unsafe_ones_refused():
    assert tc.clean_links({"revolut": "boby", "paypal": "https://paypal.me/boby", "twint": "+41 79 000 00 00"}) == {
        "revolut": "https://revolut.me/boby", "paypal": "https://paypal.me/boby", "twint": "+41790000000"}
    with pytest.raises(ValueError):
        tc.clean_links({"revolut": "javascript:alert(1)"})


def test_summary_gives_totals_my_balance_and_categories():
    members = [{"id": A, "name": "Léa"}, {"id": B, "name": "Tom"}]
    exps = [dict(expense(2000, A, eq(A, B)), category="food"), dict(expense(1000, B, eq(A, B)), category="drinks"),
            dict(expense(500, B, eq(A), kind="transfer"), category="other")]
    s = tc.summarize({"members": members, "expenses": exps, "me": A, "currency": "CHF"})
    assert s["total_cents"] == 3000  # les remboursements ne sont pas des dépenses
    assert s["my_balance_cents"] == 0 and s["my_spent_cents"] == 1500
    assert s["by_category"][0] == {"category": "food", "amount_cents": 2000}
    assert s["settle"] == []
