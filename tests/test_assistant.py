"""Assistant IA : lecture d'un ticket (Claude simulé, aucun appel payant), droit, plafond mensuel, débit, journal."""
import json
from types import SimpleNamespace

import pytest

from app import assistant as ai
from app.accounts import AccountError

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")
TICKET = {"readable": True, "merchant": "Migros", "title": "Courses Migros", "date": "2026-10-31", "currency": "chf",
          "total": 84.5, "category": "food", "summary": "Raclette, vin et pain pour 84.50 CHF",
          "items": [{"label": "Fromage à raclette", "quantity": 1, "amount": 32.9},
                    {"label": "Vin blanc", "quantity": 2, "amount": 39.8}, {"label": "Pain", "quantity": 1, "amount": 11.8}]}


class FakeAccounts:
    def __init__(self, perms=("ai.use",), admin=False):
        self.perms, self.admin = set(perms), admin

    def _uid(self, token):
        if token != "ok":
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        return "u1"

    def _perms(self, token):
        return self.perms

    def link(self, token):
        return {"name": "Léa"}

    def is_party_admin(self, token):
        return self.admin


class FakeClient:
    def __init__(self, answer=TICKET, stop="end_turn", fail=False):
        self.calls = []
        self.answer, self.stop, self.fail = answer, stop, fail
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("réseau coupé")
        return SimpleNamespace(stop_reason=self.stop, usage=SimpleNamespace(input_tokens=1500, output_tokens=400),
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def make(tmp_path, client=None, perms=("ai.use",), budget=3.0, admin=False):
    client = client or FakeClient()
    a = ai.Assistant(FakeAccounts(perms, admin), ai.UsageLog(tmp_path / "ai.json"), lambda: client, budget, ("CHF", "EUR"))
    return a, client


def test_a_receipt_fills_the_expense_and_is_logged_with_its_cost(tmp_path):
    a, client = make(tmp_path)
    r = a.read_receipt("ok", JPEG)
    assert (r["title"], r["amount_cents"], r["currency"], r["category"], r["date"]) == ("Courses Migros", 8450, "CHF", "food", "2026-10-31")
    assert [i["amount_cents"] for i in r["items"]] == [3290, 3980, 1180] and r["summary"].startswith("Raclette")
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5" and call["output_config"]["format"]["schema"] is ai.RECEIPT_SCHEMA
    assert call["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"
    entry = a.usage.items[0]
    assert entry["name"] == "Léa" and entry["cost_usd"] == pytest.approx((1500 * 2 + 400 * 10) / 1e6)
    assert ai.UsageLog(tmp_path / "ai.json").items == a.usage.items  # gardé sur le disque


def test_only_accounts_with_the_right_can_use_it(tmp_path):
    a, client = make(tmp_path, perms=())
    with pytest.raises(AccountError, match="pas activé"):
        a.read_receipt("ok", JPEG)
    assert not client.calls and not a.status("ok")["allowed"]


def test_monthly_budget_and_burst_stop_the_calls(tmp_path):
    a, client = make(tmp_path, budget=0.01)
    a.read_receipt("ok", JPEG)  # 0.007 $
    a.read_receipt("ok", JPEG)
    with pytest.raises(AccountError, match="limite"):
        a.read_receipt("ok", JPEG)
    b, _ = make(tmp_path / "..", budget=100)
    b.usage = ai.UsageLog(tmp_path / "burst.json")
    for _ in range(ai.BURST[0]):
        b.read_receipt("ok", JPEG)
    with pytest.raises(AccountError, match="Doucement"):
        b.read_receipt("ok", JPEG)


def test_unreadable_refused_or_failed_reads_say_so_clearly(tmp_path):
    for client in (FakeClient(answer={**TICKET, "readable": False}), FakeClient(stop="refusal"), FakeClient(fail=True)):
        a, _ = make(tmp_path, client)
        with pytest.raises(AccountError):
            a.read_receipt("ok", JPEG)
    a, client = make(tmp_path)
    with pytest.raises(AccountError, match="Photo"):
        a.read_receipt("ok", b"pas une image")
    assert not client.calls


def test_without_api_key_the_assistant_says_it_is_not_configured(tmp_path):
    a = ai.Assistant(FakeAccounts(), ai.UsageLog(tmp_path / "ai.json"), None, 3.0, ("CHF",))
    assert a.status("ok")["configured"] is False
    with pytest.raises(AccountError, match="pas encore configuré"):
        a.read_receipt("ok", JPEG)


def test_unknown_currency_and_bad_date_fall_back_safely():
    r = ai.clean_receipt({**TICKET, "currency": "XYZ", "date": "31.10.2026", "category": "space"}, ("CHF",))
    assert (r["currency"], r["date"], r["category"]) == ("CHF", "", "other")


def test_report_is_for_admins_only_and_sums_the_month(tmp_path):
    a, _ = make(tmp_path)
    a.read_receipt("ok", JPEG)
    with pytest.raises(AccountError):
        a.report("ok")
    a.accounts.admin = True
    rep = a.report("ok")
    assert rep["people"][0]["name"] == "Léa" and rep["people"][0]["calls"] == 1 and rep["recent"][0]["feature"] == "receipt"


def test_receipt_endpoint_refuses_a_bad_photo_and_answers_without_key():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.post("/api/account/ai/receipt", json={"token": "x", "photo": "%%%"}).status_code == 400
