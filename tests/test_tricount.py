

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
