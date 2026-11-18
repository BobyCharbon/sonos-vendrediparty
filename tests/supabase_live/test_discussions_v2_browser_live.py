"""Discussions v2 « Néon club » (demande de l'admin du 18.11.2026), recette RÉELLE : base de TEST, vrai navigateur,
connexion normale de deux comptes de test, aucun faux.

  * l'Admin de test et le VIP de test ont vécu une soirée passée ensemble ;
  * l'Admin ouvre Discussions › « Nouveau message », trouve le VIP, lui écrit (conversation directe ou demande de message,
    selon la règle de la base `chat_link`) ;
  * le VIP voit la conversation (ou la demande) arriver, l'accepte au besoin, répond ; l'Admin voit la réponse sans recharger ;
  * le mini-profil dit « Déjà vu 1 fois » et nomme la soirée.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_discussions_v2_browser_live.py -q   (captures dans $BAR_SHOTS si défini)
"""
import re
from datetime import datetime, timedelta, timezone

from tests.supabase_live.test_audiences_live import ADMIN, VIP
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw, shot, signed_in_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live
FAST = 10000
TITLE = 'Soirée recette discussions'


def ids():
    rows = sql(f"select phone, id::text id from public.profiles where phone in ('{ADMIN}', '{VIP}')")
    return {r['phone']: r['id'] for r in rows}


def clean(a, v):
    sql(f"delete from public.direct_chats where (user_a = '{a}' and user_b = '{v}') or (user_a = '{v}' and user_b = '{a}')")


def test_admin_writes_to_someone_met_at_a_party_and_they_answer_live(browser, party):  # noqa: F811
    sql("insert into public.terms_acceptances (user_id, version) select p.id, (select terms_version from private.moderation_settings "
        f"where id = 1) from public.profiles p where p.phone in ('{ADMIN}', '{VIP}') on conflict do nothing")
    who = ids()
    a, v = who[ADMIN], who[VIP]
    clean(a, v)
    vip_role = sql(f"select role from public.profiles where phone = '{VIP}'")[0]['role']
    sql(f"update public.profiles set role = 'member' where phone = '{VIP}'")
    # Soirée passée créée directement en base (aucune notification ; la connexion par l'API enverrait un code SMS de trop).
    past = datetime.now(timezone.utc) - timedelta(days=3)
    event = sql("insert into public.events (title, created_by, status, starts_at, ends_at, notify_on_publish) values "
                f"('{TITLE}', '{a}', 'published', '{past.isoformat()}', '{(past + timedelta(hours=5)).isoformat()}', false) "
                "returning id::text id")[0]['id']
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{v}', 'yes'), ('{event}', '{a}', 'yes') "
        "on conflict (event_id, user_id) do update set status = 'yes'")
    errors: list = []
    contexts = []
    try:
        actx, ap = signed_in_page(browser, ADMIN, party, event, errors)
        contexts.append(actx)
        vctx, vp = signed_in_page(browser, VIP, party, event, errors)
        contexts.append(vctx)

        # 1. Liste, puis « Nouveau message ».
        ap.goto(f'{party}/events/chats')
        pw.expect(ap.get_by_role('heading', name='Discussions')).to_be_visible(timeout=30000)
        shot(ap, 'dv2-01-liste-admin')
        ap.get_by_role('button', name='Nouveau message').first.click()
        field = ap.get_by_label('Ajouter quelqu’un', exact=True)
        pw.expect(field).to_be_visible(timeout=FAST)
        field.fill('VIP')
        person = ap.get_by_role('checkbox', name=re.compile('^VIP Test')).first
        pw.expect(person).to_be_visible(timeout=FAST)
        shot(ap, 'dv2-02-nouveau-message-recherche')
        person.click()
        shot(ap, 'dv2-03-nouveau-message-choisi')
        ap.get_by_test_id('new-message-go').click()

        # 2. La conversation : premier message.
        msg = ap.get_by_label('Message', exact=True)
        pw.expect(msg).to_be_visible(timeout=FAST)
        msg.fill('Salut ! Super soirée samedi 🎉')
        ap.get_by_role('button', name='Envoyer', exact=True).click()
        pw.expect(ap.get_by_text('Salut ! Super soirée samedi 🎉', exact=True).first).to_be_visible(timeout=FAST)
        shot(ap, 'dv2-04-conversation-admin')
        chat = sql(f"select id::text id, status from public.direct_chats where (user_a = '{a}' and user_b = '{v}') "
                   f"or (user_a = '{v}' and user_b = '{a}')")
        assert len(chat) == 1, chat
        status = chat[0]['status']

        # 3. Chez le VIP : la conversation ou la demande, sans recharger.
        vp.goto(f'{party}/events/chats')
        pw.expect(vp.get_by_role('heading', name='Discussions')).to_be_visible(timeout=30000)
        shot(vp, f'dv2-05-liste-vip-{status}')
        if status == 'request':
            vp.goto(f'{party}/events/chats/requests')
            accept = vp.get_by_role('button', name=re.compile('^Accepter la demande de '))
            pw.expect(accept.first).to_be_visible(timeout=FAST)
            shot(vp, 'dv2-06-demande-recue')
            accept.first.click()
            vp.wait_for_timeout(1500)
        vp.goto(f"{party}/events/chats/{chat[0]['id']}")
        pw.expect(vp.get_by_text('Salut ! Super soirée samedi 🎉', exact=True).first).to_be_visible(timeout=FAST)
        vmsg = vp.get_by_label('Message', exact=True)
        pw.expect(vmsg).to_be_visible(timeout=FAST)
        vmsg.fill('Grave ! On remet ça vendredi ?')
        vp.get_by_role('button', name='Envoyer', exact=True).click()
        shot(vp, 'dv2-07-conversation-vip')

        # 4. Chez l'Admin, sans recharger : la réponse.
        pw.expect(ap.get_by_text('Grave ! On remet ça vendredi ?', exact=True).first).to_be_visible(timeout=FAST)
        shot(ap, 'dv2-08-reponse-en-direct')

        # 5. Mini-profil : déjà vu 1 fois, la soirée nommée.
        ap.get_by_role('button', name=re.compile('^Infos de la conversation|^Profil de ')).first.click()
        sheet = ap.get_by_test_id('mini-profile')
        if sheet.count() == 0:
            ap.get_by_role('button', name=re.compile('Profil de ')).first.click()
        pw.expect(sheet).to_be_visible(timeout=FAST)
        pw.expect(sheet.get_by_test_id('mini-met')).to_have_text('Déjà vu 1 fois', timeout=FAST)
        pw.expect(sheet.get_by_role('link', name=re.compile(f'^{TITLE}'))).to_be_visible()
        shot(ap, 'dv2-09-mini-profil')

        rows = sql(f"select body from public.direct_messages where chat_id = '{chat[0]['id']}' order by created_at")
        assert [r['body'] for r in rows] == ['Salut ! Super soirée samedi 🎉', 'Grave ! On remet ça vendredi ?'], rows
        assert not errors, errors
    finally:
        for context in contexts:
            context.close()
        sql(f"update public.profiles set role = '{vip_role}' where phone = '{VIP}'")
        clean(a, v)
        sql(f"delete from public.events where id = '{event}'")
