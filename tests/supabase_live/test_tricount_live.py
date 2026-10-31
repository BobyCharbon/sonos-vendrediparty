"""Tricount sur la VRAIE base de test (jamais la prod) : création, lien pour rejoindre (et reprendre un prénom),
dépenses égales / par parts / montants, remboursement, soldes, photo du ticket, profil de paiement, et surtout les
droits : un compte qui n'est pas du tricount ne voit ni n'écrit rien."""
import httpx
import pytest

from app import accounts as accounts_mod, group_admin as ga, tricount as tcmod
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


@pytest.fixture(scope='module')
def tc():
    mp = pytest.MonkeyPatch()
    key = KEY_FILE.read_text().strip()
    for mod in (accounts_mod, ga, tcmod):
        mp.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    mp.setattr(accounts_mod, 'SUPABASE_ANON_KEY', key)
    relay = tcmod.Tricount(ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))), lambda: "https://partytest.example")
    tokens = [Session(g).headers['Authorization'].removeprefix('Bearer ') for g in (GUEST_A, GUEST_B, VIP)]
    created = []
    yield relay, tokens, created
    for grp, tok in created:  # ménage : on quitte (les données de test restent invisibles pour tous)
        try:
            relay.leave(tok, grp)
        except accounts_mod.AccountError:
            pass
    mp.undo()


def test_tricount_end_to_end_with_link_claim_and_settlement(tc):
    relay, (ta, tb, tcx), created = tc
    g = relay.create(ta, "Week-end Verbier", "⛷️", "CHF", "Léa")
    created.append((g["id"], ta))
    assert g["link"].startswith("https://partytest.example/pot/") and g["members"][0]["me"]
    g = relay.add_member(ta, g["id"], "Tom")  # Tom n'a pas encore de compte : prénom ajouté à la main
    tom = next(m for m in g["members"] if m["name"] == "Tom")
    lea = next(m for m in g["members"] if m["me"])
    link = g["link"].rsplit("/", 1)[1]
    # Un autre compte ne voit rien sans le lien
    with pytest.raises(accounts_mod.AccountError):
        relay.state(tb, g["id"])
    info = relay.join_info(tb, link)
    assert info["name"] == "Week-end Verbier" and any(m["name"] == "Tom" and not m["linked"] for m in info["members"])
    g = relay.join(tb, link, "Tom", tom["id"])  # Testeur 2 reprend « Tom » : ses dépenses deviennent les siennes
    assert next(m for m in g["members"] if m["me"])["id"] == tom["id"]
    # Dépenses : égale, par parts, montants exacts ; photo du ticket
    path = relay.upload_receipt(ta, g["id"], JPEG)["path"]
    relay.save_expense(ta, g["id"], {"title": "Courses Migros", "amount_cents": 9000, "paid_by": lea["id"],
                                      "shares": [{"member_id": lea["id"]}, {"member_id": tom["id"]}], "receipt_path": path})
    relay.save_expense(tb, g["id"], {"title": "Forfait ski", "amount_cents": 12000, "paid_by": tom["id"], "split_mode": "shares",
                                      "shares": [{"member_id": lea["id"], "weight": 1}, {"member_id": tom["id"], "weight": 2}]})
    g = relay.save_expense(ta, g["id"], {"title": "Essence", "amount_cents": 3000, "paid_by": lea["id"], "split_mode": "amounts",
                                          "shares": [{"member_id": lea["id"], "amount_cents": 1000}, {"member_id": tom["id"], "amount_cents": 2000}]})
    courses = next(e for e in g["expenses"] if e["title"] == "Courses Migros")
    assert courses["category"] == "food" and courses["receipt_url"].startswith(TEST_URL)
    assert httpx.get(courses["receipt_url"], timeout=30).status_code == 200
    # Léa : +9000 - 4500 - 4000 + 3000 - 1000 = 2500 ; Tom : -2500 → Tom rembourse 25 CHF à Léa
    assert g["my_balance_cents"] == 2500 and g["settle"] == [{"from": tom["id"], "to": lea["id"], "amount_cents": 2500,
                                                              "from_name": "Tom", "to_name": "Léa"}]
    assert g["total_cents"] == 24000
    g = relay.settle_up(tb, g["id"], tom["id"], lea["id"], 2500)
    assert g["settle"] == [] and g["total_cents"] == 24000  # le remboursement n'est pas une dépense


def test_wrong_amounts_and_strangers_are_refused(tc):
    relay, (ta, tb, tcx), created = tc
    g = relay.create(ta, "Coloc", "🏠", "EUR", "Léa")
    created.append((g["id"], ta))
    me = g["members"][0]["id"]
    with pytest.raises(accounts_mod.AccountError):
        relay.save_expense(ta, g["id"], {"title": "Loyer", "amount_cents": 1000, "paid_by": me, "split_mode": "amounts",
                                          "shares": [{"member_id": me, "amount_cents": 900}]})
    with pytest.raises(accounts_mod.AccountError):
        relay.save_expense(tcx, g["id"], {"title": "Pirate", "amount_cents": 100, "paid_by": me, "shares": [{"member_id": me}]})
    # Lecture directe par l'API de la base : rien pour un non-membre (RLS)
    r = httpx.get(f'{TEST_URL}/rest/v1/tc_expenses?group_id=eq.{g["id"]}', timeout=30,
                  headers={'apikey': KEY_FILE.read_text().strip(), 'Authorization': f'Bearer {tcx}'})
    assert r.status_code == 200 and r.json() == []
    old = g["link"]
    g = relay.renew_link(ta, g["id"])
    assert g["link"] != old
    with pytest.raises(accounts_mod.AccountError):
        relay.join(tcx, old.rsplit("/", 1)[1], "Zoé", None)  # l'ancien lien ne marche plus


def test_payment_profile_is_checked_and_shared_with_co_members_only(tc):
    relay, (ta, tb, tcx), created = tc
    with pytest.raises(accounts_mod.AccountError):
        relay.set_payment(ta, "CH93 0076 2011 6238 5295 8", "Léa", {}, "")  # clé de contrôle fausse
    p = relay.set_payment(ta, "ch93 0076 2011 6238 5295 7", "Léa Test", {"revolut": "leatest", "twint": "+41 79 000 00 01"}, "Merci !")
    assert p["iban"] == "CH93 0076 2011 6238 5295 7" and p["links"]["revolut"] == "https://revolut.me/leatest"
    g = relay.create(ta, "Resto", "🍽️", "CHF", "Léa")
    created.append((g["id"], ta))
    link = g["link"].rsplit("/", 1)[1]
    g = relay.join(tb, link, "Tom", None)
    lea = next(m for m in g["members"] if not m["me"])
    assert lea["payment"]["iban"] == "CH93 0076 2011 6238 5295 7"  # Tom, co-membre, voit l'IBAN de Léa pour la rembourser
    r = httpx.get(f'{TEST_URL}/rest/v1/tc_payment', timeout=30,
                  headers={'apikey': KEY_FILE.read_text().strip(), 'Authorization': f'Bearer {tcx}'})
    assert all(row.get("iban") != "CH9300762011623852957" for row in r.json())  # un inconnu ne le voit pas
