"""Conformité App Store du 16.11.2026 (migration 20261116150000), sur la VRAIE base de TEST, bots seulement, transactions
ANNULÉES :
- bloquer quelqu'un le signale aussi aux modérateurs (Apple 1.2), une seule fois ;
- le bar refuse tabac et drogues parmi ses articles (Apple 1.4.3) ;
- bar payant réservé aux soirées privées : créé sur un événement public, il est offert ; il ne repasse pas payant ; un
  événement avec un bar payant ne devient pas public ;
- conditions d'utilisation en version 2026-11-16.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_conformite_app_store_live.py -q"""
from tests.supabase_live.test_bar_options_live import BAR, as_bot, as_postgres, keep, note, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401


def test_blocking_someone_also_reports_them_to_moderators_once():
    out = run(as_bot("ada") + """
      perform public.set_direct_block(come, true);
      perform public.set_direct_block(come, false);
      perform public.set_direct_block(come, true);""" + as_postgres() + keep(
        "reports", "(select count(*) from public.content_reports where reporter_id = ada and target_kind = 'profile' "
                   "and target_id = come::text and comment like 'Bloqué par un membre%')"))
    assert "reports=1" in out, out


def test_the_bar_refuses_tobacco_and_drugs():
    out = run(BAR + note("cigarettes", "perform public.bar_save_item(e, '{\"name\": \"Cigarettes\", \"price_chf\": 2}'::jsonb)")
              + note("puff", "perform public.bar_save_item(e, '{\"name\": \"Puff menthe\", \"price_chf\": 8}'::jsonb)")
              + note("detail", "perform public.bar_save_item(e, '{\"name\": \"Spécial\", \"detail\": \"CBD\", \"price_chf\": 8}'::jsonb)")
              + note("biere", "perform public.bar_save_item(e, '{\"name\": \"Bière blonde\", \"price_chf\": 3}'::jsonb)"))
    assert "cigarettes=Le bar ne sert ni tabac ni drogue" in out, out
    assert "puff=Le bar ne sert ni tabac ni drogue" in out and "detail=Le bar ne sert ni tabac ni drogue" in out, out
    assert "biere=ok" in out, out


def test_a_paid_bar_belongs_to_private_parties_only():
    out = run(as_postgres() + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by)
        values ('[Recette] Bar public', 'published', 'all', true, false, now() + interval '2 days', olga) returning id into e;"""
              + as_bot("olga") + "perform public.bar_create(e);" + as_postgres()
              + keep("free_public", "(select free_bar from public.event_bars where event_id = e)") + as_bot("olga")
              + note("paid_public", "perform public.bar_save_settings(e, '{\"free_bar\": false}'::jsonb)")
              # Un événement sur invitation garde son bar payant, mais ne devient pas public avec lui.
              + as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by)
        values ('[Recette] Bar privé', 'published', 'invited', false, now() + interval '2 days', olga) returning id into srv;"""
              + as_bot("olga") + "perform public.bar_create(srv);" + as_postgres()
              + keep("paid_private", "(select not free_bar from public.event_bars where event_id = srv)")
              + note("go_public", "update public.events set visibility = 'all', public_link = true where id = srv"))
    assert "free_public=true" in out, out
    assert "paid_public=Un bar payant est réservé aux soirées privées" in out, out
    assert "paid_private=true" in out, out
    assert "go_public=Cet événement a un bar payant" in out, out


def test_terms_are_the_version_of_the_16th():
    out = run(as_postgres() + keep("v", "(select terms_version from private.moderation_settings where id = 1)"))
    assert "v=2026-11-18" in out, out
