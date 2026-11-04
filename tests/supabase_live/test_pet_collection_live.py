"""Collection du Compagnon (lot A) sur la VRAIE base de TEST (jamais la prod), migration 20261104210000 :

  · catalogue en base = app/pet_catalog.json ; tables fermées ;
  · frappe : numéros uniques, idempotente, tirage d'un Mythique plafonné (« tous partis »), jamais un souvenir de
    soirée ni un Mythique à l'atelier ; certificat (payload recalculé par la base, signature Ed25519 vérifiable) ;
  · cadeaux d'événement : bornes de l'organisateur, Mythique réservé à l'admin, publication avant le début puis chances
    FIGÉES, graine cachée puis révélée ; tirage pour les PRÉSENTS seulement (billet scanné, ou noté par l'organisateur),
    jamais selon un paiement ; exemplaires limités ; jets refaits en Python ; cadeaux rangés une fois ;
  · modération : nom refusé par la base, Signaler le nom d'un ami (copie), masquer, blocage = plus « ami ».
Comptes : Admin de test et Testeurs 1, 2, 3 (leurs compagnons, exemplaires, événement et groupe de test : effacés)."""
import copy
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import pet, pet_catalog, pet_cert, pet_events
from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, GUESTS, KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_audiences_live import make_vip, unmake_vip
from tests.supabase_live.test_pet_live import KEY, sql_test

EVENT = "6e7a0000-0000-4000-8000-0000000c0117"
GROUP = "6e7a0000-0000-4000-8000-00000000c011"


def clean(ids):
    users = ",".join(f"'{u}'" for u in ids)
    sql_test(f"""delete from public.pet_event_drops where event_id = '{EVENT}';
      delete from public.pet_event_awards where event_id = '{EVENT}';
      delete from public.pet_items where minted_for in ({users}) or event_id = '{EVENT}';
      delete from public.event_tickets where event_id = '{EVENT}';
      delete from public.rsvps where event_id = '{EVENT}';
      delete from public.events where id = '{EVENT}';
      delete from public.pets where user_id in ({users});
      delete from public.content_reports where reporter_id in ({users});
      delete from public.direct_blocks where user_id in ({users}) or blocked_id in ({users});
      delete from public.member_groups where id = '{GROUP}';""")


@pytest.fixture(scope="module")
def people():
    admin, a, b, c = Session(ADMIN_PHONE), Session(GUESTS[0]), Session(GUESTS[1]), Session(GUESTS[2])
    ids = [admin.uid, a.uid, b.uid, c.uid]
    clean(ids)
    make_vip(admin, c)   # l'organisateur doit être membre (comme en vrai)
    sql_test(f"""insert into public.member_groups (id, name) values ('{GROUP}', 'Test collection');
      insert into public.member_group_members (group_id, user_id) values ('{GROUP}', '{a.uid}'), ('{GROUP}', '{b.uid}');
      insert into public.events (id, title, created_by, status, starts_at, ends_at, public_link, notify_on_publish, reminders)
      values ('{EVENT}', 'Soirée test collection', '{c.uid}', 'published', now() + interval '2 hours', now() + interval '6 hours', true, false, '{{}}');""")
    yield admin, a, b, c
    clean(ids)
    unmake_vip(admin, c)


def anon_rpc(name, **args):
    key = KEY_FILE.read_text().strip()
    return httpx.post(f"{TEST_URL}/rest/v1/rpc/{name}", headers={"apikey": key, "Authorization": f"Bearer {key}"}, json=args, timeout=30)


def test_the_catalog_in_the_database_is_the_json_file(people):
    rows = sql_test("select id, slot, series, rarity, edition, source, label from public.pet_catalog order by id;")
    want = sorted(({"id": it["id"], "slot": it["slot"], "series": it["series"], "rarity": it["rarity"], "edition": it.get("edition"),
                    "source": pet_catalog.series()[it["series"]]["source"], "label": it["label"]} for it in pet_catalog.items().values()),
                  key=lambda r: r["id"])
    assert rows == want
    _, a, *_ = people
    for table in ("pet_catalog", "pet_items", "pet_item_owners", "pet_event_drops", "pet_event_awards"):
        r = a.get(f"{table}?select=*")
        assert r.status_code in (401, 403) or r.json() == [], (table, r.text)


def test_minting_is_numbered_idempotent_capped_and_certified(people):
    _, a, b, _ = people
    first = a.rpc("pet_mint", p_item="piolet-or", p_source="atelier", p_ref="atelier:piolet-or", p_key=KEY())
    assert first.status_code == 200, first.text
    again = a.rpc("pet_mint", p_item="piolet-or", p_source="atelier", p_ref="atelier:piolet-or", p_key=KEY()).json()
    assert again["id"] == first.json()["id"] and again["serial"] == first.json()["serial"]
    assert a.rpc("pet_mint", p_item="piolet-or", p_source="atelier", p_ref="atelier:piolet-or").status_code == 400   # sans clé
    for item, source, why in (("m-soirees", "chest", "événements"), ("m-disco", "atelier", "fabrique"), ("bonnet", "chest", "inconnu")):
        r = a.rpc("pet_mint", p_item=item, p_source=source, p_ref=f"{source}:x", p_key=KEY())
        assert r.status_code == 400 and why in r.json()["message"], r.text
    # Certificat : la base recalcule le texte signé ; la signature se vérifie avec la clé publique.
    inst = first.json()
    cert = pet_cert.sign(KEY(), inst)
    bad = a.rpc("pet_cert_set", p_id=inst["id"], p_sig=cert["sig"], p_code=cert["code"], p_payload=cert["payload"].replace("|atelier", "|chest"), p_key=KEY())
    assert bad.status_code == 400
    ok = a.rpc("pet_cert_set", p_id=inst["id"], p_sig=cert["sig"], p_code=cert["code"], p_payload=cert["payload"], p_key=KEY())
    assert ok.status_code == 200 and ok.json()["code"] == cert["code"]
    shown = anon_rpc("pet_verify", p_code=cert["code"].lower()).json()
    assert shown["serial"] == inst["serial"] and shown["owners"][0]["how"] == "minted" and "user_id" not in str(shown["owners"])
    assert pet_cert.verify(pet_cert.public_key_b64(KEY()), shown["payload"], shown["sig"])
    # Tirage d'un Mythique : plafonné, jamais réédité.
    left = sql_test("select 25 - count(*)::int as n from public.pet_items where item = 'm-escalade';")[0]["n"]
    for n in range(left):
        sql_test(f"select private.pet_mint_for('{b.uid}', 'm-escalade', 'chest', 'chest:cap{n}', null);")
    r = b.rpc("pet_mint", p_item="m-escalade", p_source="chest", p_ref="chest:over", p_key=KEY())
    assert r.status_code == 400 and "partis" in r.json()["message"]
    assert sql_test("select max(serial) as m from public.pet_items where item = 'm-escalade';")[0]["m"] == 25


def test_event_gifts_bounds_freeze_and_a_draw_for_present_people_only(people):
    admin, a, b, c = people
    # Organisateur (c, membre VIP) : dans les bornes de l'admin seulement.
    for prizes, why in (([{"item": "projecteurs", "pct": 50, "copies": 1}], "au plus"),
                        ([{"item": "m-soirees", "pct": 5, "copies": 1}], "au plus"),
                        ([{"item": "projecteurs", "pct": 5}], "exemplaires")):
        r = c.rpc("pet_event_drop_save", p_event=EVENT, p_prizes=prizes)
        assert r.status_code == 400 and why in r.json()["message"], r.text
    assert b.rpc("pet_event_drop_save", p_event=EVENT, p_prizes=[{"item": "noeud-or", "pct": 100}]).status_code in (400, 403)   # ni admin ni organisateur
    prizes = [{"item": "noeud-or", "pct": 100}, {"item": "lumi", "pct": 20}, {"item": "projecteurs", "pct": 10, "copies": 1}]
    assert c.rpc("pet_event_drop_save", p_event=EVENT, p_prizes=prizes).status_code == 200
    # L'admin peut ajouter un Mythique (exemplaires restants).
    full = prizes + [{"item": "m-soirees", "pct": 100, "copies": 1}]
    r = admin.rpc("pet_event_drop_save", p_event=EVENT, p_prizes=full)
    assert r.status_code == 200, r.text
    assert b.rpc("pet_event_drop_get", p_event=EVENT).json()["drop"] is None   # brouillon : invisible des participants
    pub = admin.rpc("pet_event_drop_publish", p_event=EVENT).json()
    assert pub["drop"]["status"] == "published" and len(pub["drop"]["seed_hash"]) == 64 and pub["drop"]["seed"] is None
    seen = b.rpc("pet_event_drop_get", p_event=EVENT).json()["drop"]
    assert [p["pct"] for p in seen["prizes"]] == [100, 20, 10, 100]
    assert seen["prizes"][3]["label"] == "Objet mystère (Mythique numéroté)" and seen["prizes"][3]["item"] is None
    frozen = admin.rpc("pet_event_drop_save", p_event=EVENT, p_prizes=prizes)
    assert frozen.status_code == 400 and "figés" in frozen.json()["message"] or "ne changent plus" in frozen.json()["message"]
    # Présents : b (billet scanné, n'a PAS payé), a (noté « Présent » par l'organisateur c, sans billet).
    # admin : inscrit lui-même et a PAYÉ, mais pas arrivé → pas de cadeau (jamais selon un paiement).
    sql_test(f"""insert into public.rsvps (event_id, user_id, status) values ('{EVENT}', '{b.uid}', 'yes'), ('{EVENT}', '{admin.uid}', 'yes');
      update public.rsvps set waitlisted = false where event_id = '{EVENT}';
      insert into public.event_tickets (event_id, user_id, token, code, checked_in_at, paid)
      values ('{EVENT}', '{b.uid}', encode(extensions.gen_random_bytes(32), 'hex'), 'BBBBBB', now(), false),
             ('{EVENT}', '{admin.uid}', encode(extensions.gen_random_bytes(32), 'hex'), 'CCCCCC', null, true);""")
    assert c.rpc("set_rsvp_for", event=EVENT, member=a.uid, answer="yes").status_code == 204   # l'organisateur le note présent
    assert sql_test(f"select set_by::text as s from public.rsvps where event_id = '{EVENT}' and user_id = '{a.uid}';")[0]["s"] == c.uid
    assert sql_test(f"select private.pet_event_draw('{EVENT}') as n;")[0]["n"] == 0   # pas encore fini : rien
    sql_test(f"update public.events set starts_at = now() - interval '5 hours', ends_at = now() - interval '1 hour' where id = '{EVENT}';")
    sql_test(f"select private.pet_event_draw('{EVENT}');")
    awards = sql_test(f"select user_id::text as u, prize, item, roll::float as roll, instance_id is not null as inst from public.pet_event_awards where event_id = '{EVENT}' order by u, prize;")
    winners = {r["u"] for r in awards}
    assert winners == {a.uid, b.uid}   # jamais l'admin (payé, pas arrivé)
    assert sum(1 for r in awards if r["prize"] == 0) == 2 and sum(1 for r in awards if r["prize"] == 3) == 1   # 100 % ; Mythique : 1 exemplaire
    assert sum(1 for r in awards if r["prize"] == 2) <= 1
    assert all(r["inst"] == (pet_catalog.item(r["item"])["rarity"] in ("legendary", "mythic")) for r in awards)
    drawn = b.rpc("pet_event_drop_get", p_event=EVENT).json()
    seed = drawn["drop"]["seed"]
    assert drawn["drop"]["status"] == "drawn" and drawn["drop"]["eligible_count"] == 2
    assert pet_events.seed_matches(seed, drawn["drop"]["seed_hash"])
    for r in awards:
        assert abs(pet_events.roll(seed, EVENT, r["u"], r["prize"]) - r["roll"]) < 1e-5
        assert r["roll"] < full[r["prize"]]["pct"]
    assert {m["prize"] for m in drawn["mine"]} == {r["prize"] for r in awards if r["u"] == b.uid}
    # Le chargement (serveur Party) les donne une fois, puis les marque rangés.
    loaded = b.rpc("pet_load", p_key=KEY()).json()
    mine = [x for x in loaded["awards"] if x["event_id"] == EVENT]
    assert {x["item"] for x in mine} >= {"noeud-or"}
    assert b.rpc("pet_awards_claim", p_ids=[x["id"] for x in mine], p_key=KEY()).json() == len(mine)
    assert not [x for x in b.rpc("pet_load", p_key=KEY()).json()["awards"] if x["event_id"] == EVENT]


def test_names_are_filtered_reported_hidden_and_blocking_ends_the_friendship(people):
    _, a, b, _ = people
    life, owner = pet.new_pet(datetime.now(timezone.utc) - timedelta(minutes=10))
    pet.advance(life, datetime.now(timezone.utc), owner)
    r = a.rpc("pet_save", p_key=KEY(), p_life=life, p_owner=owner, p_version=0, p_hungry_at=None, p_dies_at=None)
    assert r.status_code == 200, r.text
    bad = copy.deepcopy(life)
    bad["name"] = "connard"
    r = a.rpc("pet_save", p_key=KEY(), p_life=bad, p_owner=owner, p_version=1, p_hungry_at=None, p_dies_at=None)
    assert r.status_code == 400 and r.json()["message"].startswith("content_refused"), r.text
    named = copy.deepcopy(life)
    named["name"] = "Pikou"
    named["showcase"] = {"title": "Mes trésors", "items": [{"id": "noeud"}]}
    assert a.rpc("pet_save", p_key=KEY(), p_life=named, p_owner=owner, p_version=1, p_hungry_at=None, p_dies_at=None).status_code == 200
    rid = b.rpc("report_content", p_kind="pet_name", p_target=a.uid, p_reason="harassment").json()
    snap = sql_test(f"select snapshot ->> 'text' as t, snapshot ->> 'place' as p, target_user::text as u from public.content_reports where id = '{rid}';")[0]
    assert snap == {"t": "Pikou", "p": "Compagnon · nom", "u": a.uid}
    assert b.rpc("report_content", p_kind="pet_showcase", p_target=a.uid, p_reason="spam").status_code == 200
    sql_test("select private.moderation_hide_pet('pet_name', '" + a.uid + "'), private.moderation_hide_pet('pet_showcase', '" + a.uid + "');")
    row = sql_test(f"select name, life ->> 'name' as n, life -> 'showcase' ->> 'title' as t, version from public.pets where user_id = '{a.uid}';")[0]
    assert row["name"] == "Zicou" and row["n"] == "Zicou" and row["t"] == "" and row["version"] == 4
    assert any(f["id"] == a.uid for f in b.rpc("pet_friends").json())
    assert b.rpc("set_block", target=a.uid, blocked=True).status_code in (200, 204)
    assert not any(f["id"] == a.uid for f in b.rpc("pet_friends").json())
    r = b.rpc("report_content", p_kind="pet_name", p_target=a.uid, p_reason="other")
    assert r.status_code >= 400   # plus « ami » : plus rien à voir ni à signaler
