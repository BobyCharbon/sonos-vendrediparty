"""Covoiturage (avis 34d5c07f2e56 de l'admin, 11.11.2026), sur la base de TEST, bots seulement, tout annulé :
option de l'événement ; seuls les participants (Présent / Peut-être) et les organisateurs y prennent part ; places comptées
(jamais plus de passagers que de places) ; un conducteur prend quelqu'un qui cherche ; « Pas présent » fait quitter le
covoiturage. Événement public de Bot Olga ; Ada, Côme, Victor répondent Présent ; Violette ne répond pas."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

EVENT = olga_event(announce=False, public=True) + as_postgres() + """
  update public.events set carpool_enabled = true where id = e;""" + "".join(
    as_bot(b) + "insert into public.rsvps (event_id, user_id, status) values (e, %s, 'yes');" % b for b in ("ada", "come", "victor"))


def test_a_driver_offers_seats_and_passengers_take_them_until_full():
    out = run(EVENT + as_bot("ada") + """
      perform public.carpool_drive(e, 1, '  Sion ');""" + as_bot("come") + """
      perform public.carpool_take(e, ada);""" + as_bot("victor") + """
      begin perform public.carpool_take(e, ada); m := 1; exception when others then m := 0; end;
      r := public.carpool(e);
      raise exception 'résultat: ville=% places=% passager=% victor_monte=% victor_moi=%', r->'drivers'->0->>'from_city',
        r->'drivers'->0->>'seats', r->'drivers'->0->'passengers'->0->>'name', m, coalesce(r->>'me', 'aucun');""")
    assert "résultat: ville=Sion places=1 passager=Bot Côme victor_monte=0 victor_moi=aucun" in out, out


def test_someone_looking_is_seen_and_a_driver_takes_her():
    out = run(EVENT + as_bot("victor") + """
      perform public.carpool_seek(e, 'Martigny');""" + as_bot("ada") + """
      r := public.carpool(e);
      m := jsonb_array_length(r->'seekers');
      a := (r->'seekers'->0->>'id')::uuid;
      perform public.carpool_drive(e, 3);
      n := case when r->'seekers'->0->>'from_city' = 'Martigny' then 1 else 0 end;
      r := public.carpool_pick(e, victor);""" + as_bot("victor") + """
      raise exception 'résultat: cherchent=% ville=% victor=% apres=% sa_voiture=%', m, n, a = victor,
        jsonb_array_length(public.carpool(e)->'seekers'), (public.carpool(e)->'me'->>'driver_id')::uuid = ada;""")
    assert "résultat: cherchent=1 ville=1 victor=t apres=0 sa_voiture=t" in out, out


def test_only_participants_take_part():
    out = run(EVENT + as_bot("violette") + """
      r := public.carpool(e);
      begin perform public.carpool_seek(e, null); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: option=% membre=% cherche=%', r->>'enabled', r->>'member', m;""")
    assert "résultat: option=true membre=false cherche=0" in out, out


def test_switched_off_the_carpool_is_absent():
    out = run(EVENT + as_postgres() + """
      update public.events set carpool_enabled = false where id = e;""" + as_bot("ada") + """
      begin perform public.carpool_drive(e, 2); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: option=% conduit=%', public.carpool(e)->>'enabled', m;""")
    assert "résultat: option=false conduit=0" in out, out


def test_answering_no_leaves_the_carpool_and_frees_the_passengers():
    out = run(EVENT + as_bot("ada") + """
      perform public.carpool_drive(e, 2);""" + as_bot("come") + """
      perform public.carpool_take(e, ada);""" + as_bot("ada") + """
      update public.rsvps set status = 'no' where event_id = e and user_id = ada;""" + as_bot("come") + """
      r := public.carpool(e);
      raise exception 'résultat: conducteurs=% cherchent=% come_cherche=%', jsonb_array_length(r->'drivers'),
        jsonb_array_length(r->'seekers'), r->'seekers'->0->>'name';""")
    assert "résultat: conducteurs=0 cherchent=1 come_cherche=Bot Côme" in out, out


def test_a_driver_cannot_cut_seats_below_his_passengers_and_can_drop_one():
    out = run(EVENT + as_bot("ada") + """
      perform public.carpool_drive(e, 2);""" + as_bot("come") + """
      perform public.carpool_take(e, ada);""" + as_bot("victor") + """
      perform public.carpool_take(e, ada);""" + as_bot("ada") + """
      begin perform public.carpool_drive(e, 1); m := 1; exception when others then m := 0; end;
      r := public.carpool_drop(e, come);
      raise exception 'résultat: reduit=% passagers=% cherchent=%', m, jsonb_array_length(r->'drivers'->0->'passengers'),
        jsonb_array_length(r->'seekers');""")
    assert "résultat: reduit=0 passagers=1 cherchent=1" in out, out


def test_an_insult_as_city_is_refused():
    out = run(EVENT + as_bot("ada") + """
      begin perform public.carpool_drive(e, 2, 'connard'); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: accepte=%', m;""")
    assert "résultat: accepte=0" in out, out


def test_the_table_is_never_read_directly():
    out = run(EVENT + as_bot("ada") + """
      perform public.carpool_drive(e, 2);
      begin select count(*) into n from public.event_carpool; m := 1; exception when others then m := 0; end;
      raise exception 'résultat: lecture_directe=%', m;""")
    assert "résultat: lecture_directe=0" in out, out
