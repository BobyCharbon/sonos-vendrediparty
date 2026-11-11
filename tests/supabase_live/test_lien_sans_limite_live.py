"""Lien d'invitation « Plusieurs » sans limite (retour de l'admin du 11.11.2026), sur la base de TEST, bots seulement,
tout annulé : sans limite de places par défaut, valable jusqu'au lendemain de l'événement même lointain (plus de plafond
de 60 jours), un nombre de places reste possible (1 à 50), et l'organisatrice peut toujours l'arrêter."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

FAR = olga_event(announce=False) + "\n  update public.events set starts_at = now() + interval '120 days', ends_at = null where id = e;"


def test_unlimited_by_default_until_the_day_after_even_a_far_event():
    out = run(FAR + as_bot("olga") + """
      r := public.create_event_invite(e, 0);
      raise exception 'résultat: places=% jours=%', r->>'max_uses',
        round(extract(epoch from ((r->>'expires_at')::timestamptz - now())) / 86400);""")
    assert "résultat: places=10000 jours=121" in out, out


def test_a_number_of_places_still_works_and_51_is_refused():
    out = run(FAR + as_bot("olga") + """
      r := public.create_event_invite(e, 12);
      begin
        perform public.create_event_invite(e, 51);
        m := 1;
      exception when others then m := 0;
      end;
      raise exception 'résultat: places=% refus_51=%', r->>'max_uses', 1 - m;""")
    assert "résultat: places=12 refus_51=1" in out, out


def test_the_link_follows_the_date_and_can_be_stopped():
    out = run(FAR + as_bot("olga") + """
      r := public.create_event_invite(e, 0);
      update public.events set starts_at = now() + interval '200 days' where id = e;
      perform public.revoke_invite_link((r->>'token')::uuid);""" + as_postgres() + """
      n := round(extract(epoch from ((select expires_at from private.invite_links where token = (r->>'token')::uuid) - now())) / 86400);
      raise exception 'résultat: jours=% arrete=%', n,
        (select revoked_at is not null from private.invite_links where token = (r->>'token')::uuid);""")
    assert "résultat: jours=201 arrete=t" in out, out
