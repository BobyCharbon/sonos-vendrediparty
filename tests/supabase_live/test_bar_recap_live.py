"""Récapitulatif du bar pour l'organisateur (demande de l'admin du 16.11.2026, migration 20261116100000), sur la VRAIE base
de TEST avec les comptes des BOTS, dans des transactions ANNULÉES : qui a pris quoi (articles, quantités), combien,
remboursé, reste dû ; totaux par article et par barman ; réservé aux organisateurs.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_bar_recap_live.py -q"""
import json

from tests.supabase_live.test_bar_options_live import BAR, as_bot, as_postgres, keep, lines, note, pledge_of, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

# Comptoir : Ada prend 2 Vodka Red Bull (4.50) et 1 Coca (2.00), Côme 1 Coca ; Ada rembourse 5, confirmé par Olga.
SOIREE = BAR + as_bot("olga") + """
      perform public.bar_save_settings(e, '{"counter_serve": true}'::jsonb);""" + pledge_of("ada") + """
      perform public.bar_pledge(e, pt, pv);""" + pledge_of("come") + """
      perform public.bar_pledge(e, pt, pv);""" + as_bot("valentin") + f"""
      perform public.bar_serve(e, ada, {lines('vrb', 0, 2)}, gen_random_uuid()::text);
      perform public.bar_serve(e, ada, {lines('coca', 0, 1)}, gen_random_uuid()::text);
      perform public.bar_serve(e, come, {lines('coca', 0, 1)}, gen_random_uuid()::text);""" + as_bot("ada") + """
      perform public.bar_declare_refund(e, 5);""" + as_postgres() + """
      srv := (select id from public.event_bar_refunds where event_id = e and user_id = ada);""" + as_bot("olga") + """
      perform public.bar_confirm_refund(e, srv, true);"""


def recap(out: str) -> dict:
    return json.JSONDecoder().raw_decode(out.split("recap=", 1)[1])[0]


def test_the_organizer_gets_who_had_what_how_much_and_what_is_still_due():
    out = run(SOIREE + as_bot("olga") + keep("recap", "public.bar_recap(e)"))
    r = recap(out)
    assert r["title"] == "[Recette] Options du bar" and r["currency"] == "CHF", r
    assert r["totals"] == {"served": 4, "amount": 13.0, "pending": 0, "refunded": 5, "due": 8.0, "people": 2}, r["totals"]
    assert [(i["name"], i["qty"], i["amount"]) for i in r["items"]] == [("Coca", 2, 4.0), ("Vodka Red Bull", 2, 9.0)], r["items"]
    ada = next(p for p in r["people"] if p["name"] == "Bot Ada")
    assert [(i["name"], i["qty"], i["amount"]) for i in ada["items"]] == [("Vodka Red Bull", 2, 9.0), ("Coca", 1, 2.0)], ada
    assert (ada["served"], ada["amount"], ada["refunded"], ada["balance"]) == (3, 11.0, 5, 6.0), ada
    come = next(p for p in r["people"] if p["name"] == "Bot Côme")
    assert (come["served"], come["amount"], come["balance"]) == (1, 2.0, 2.0), come
    assert r["staff"] == [{"name": "Bot Valentin", "served": 4}], r["staff"]


def test_only_the_organizers_read_the_recap():
    out = run(SOIREE + as_bot("valentin") + note("barman", "perform public.bar_recap(e)")
              + as_bot("victor") + note("invite", "perform public.bar_recap(e)"))
    assert "barman=forbidden" in out and "invite=forbidden" in out, out  # Bot Ada et Bot Côme sont admins sur TEST


def test_a_served_glass_signals_the_guest_the_organizer_and_the_barman_right_away():
    # Temps réel (migration 20261116110000, avis du 16.11) : le verre servi recharge aussitôt la page de l'invité, de
    # l'organisatrice et du barman ; chacun ne lit que SES signaux (RLS), sans aucun contenu.
    out = run(SOIREE + as_postgres()
              + keep("pings", "(select string_agg(p.display_name, ',' order by p.display_name) from public.live_pings l "
                              "join public.profiles p on p.id = l.user_id where l.event_id = e)")
              + as_bot("ada") + keep("vus_par_ada", "(select count(distinct user_id) from public.live_pings where event_id = e)")
              + note("ecrire", "insert into public.live_pings (user_id, event_id) values (ada, e)"))
    assert "pings=Bot Ada,Bot Côme,Bot Olga,Bot Valentin" in out, out
    assert "vus_par_ada=1" in out, out
    assert "ecrire=permission denied" in out, out


def test_the_served_notification_reads_at_a_glance():
    # Avis du 16.11 : « 🍹 Barman : −2 Vodka Red Bull » en titre ; dessous qui a servi, combien, le total à rembourser.
    out = run(SOIREE + as_postgres()
              + keep("notes", "(select string_agg(title || ' // ' || body, ' ## ' order by created_at, title) from public.notifications "
                              "where user_id = ada and kind = 'bar_served' and event_id = e)"))
    assert "🍹 Barman : −2 Vodka Red Bull // Servi par Bot Valentin · 9 CHF · à rembourser : 9 CHF · [Recette] Options du bar" in out, out
    assert "🍹 Barman : −1 Coca // Servi par Bot Valentin · 2 CHF · à rembourser : 11 CHF · [Recette] Options du bar" in out, out
