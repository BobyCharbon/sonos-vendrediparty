

def test_a_malformed_expense_is_refused_cleanly_never_a_server_error():
    import pytest
    from app.accounts import AccountError
    from app.tricount import Tricount
    t = Tricount.__new__(Tricount)
    for bad in ({"title": "x", "amount_cents": "douze", "shares": []}, {"title": "x", "amount_cents": 100, "shares": ["a"]},
                {"title": "x", "amount_cents": 100, "shares": [{"member_id": "1" * 36, "weight": "lourd"}], "split_mode": "shares"},
                {"title": "x", "amount_cents": 100, "rate": "inf?", "shares": "pas une liste"}, "pas un dict"):
        with pytest.raises(AccountError):
            t.save_expense("tok", "grp", bad)


def test_show_payment_route_calls_the_base_and_hides_the_payment_of_who_does_not_show_it(monkeypatch):
    """Contrôle du 26.11, tour 2 : POST /api/account/tricount/show-payment {token, group_id, on} → tc_set_show_payment
    (p_group, p_on), puis le pot comme /open ; shape() ne montre les moyens d'un autre que s'il les montre."""
    from fastapi.testclient import TestClient
    from app import main
    from app.tricount import Tricount
    grp = "11111111-2222-4333-8444-555555555555"
    pot = {"id": grp, "name": "Ski", "me": "m1", "members": [
        {"id": "m1", "name": "Léa", "linked": True, "show_payment": False, "payment": {"iban": None, "holder": "Léa"}},
        {"id": "m2", "name": "Tom", "linked": True, "show_payment": False, "payment": {"iban": None, "holder": "Tom"}},
        {"id": "m3", "name": "Zoé", "linked": True, "show_payment": True, "payment": {"iban": None, "holder": "Zoé"}}],
        "expenses": []}
    calls = []

    class Admin:
        def _rpc(self, token, name, args, err=""):
            calls.append((name, args))
            return pot if name == "tc_state" else True
    t = Tricount(Admin(), lambda: "https://x")
    monkeypatch.setattr(main, "tricount", t)
    r = TestClient(main.app).post("/api/account/tricount/show-payment", json={"token": "t" * 20, "group_id": grp, "on": True})
    assert r.status_code == 200, r.text
    assert calls[0] == ("tc_set_show_payment", {"p_group": grp, "p_on": True})
    members = {m["name"]: m for m in r.json()["members"]}
    assert members["Léa"]["payment"]["holder"] == "Léa"          # les miens, toujours
    assert members["Tom"]["payment"] is None and members["Tom"]["show_payment"] is False
    assert members["Zoé"]["payment"]["holder"] == "Zoé" and members["Zoé"]["show_payment"] is True
