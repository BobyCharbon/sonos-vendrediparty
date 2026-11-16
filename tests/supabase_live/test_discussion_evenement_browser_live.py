"""Discussion d'un événement façon WhatsApp (demande de l'admin du 16.11.2026), recette RÉELLE : base de TEST, vrai
navigateur, connexion normale de deux comptes de test, aucun faux.

  * le co-organisateur (compte VIP de test, l'Admin de test crée l'événement) écrit @toutlemonde puis publie une annonce avec 📣 ; la base garde les deux
    (mention_all, annonce épinglée) ;
  * l'invitée (Guest A, « Présente ») voit les deux messages arriver sans recharger, l'annonce en carte et dans le bandeau ;
    elle n'a ni 📣 ni @toutlemonde et est prévenue si elle l'écrit.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_discussion_evenement_browser_live.py -q
"""
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, create_event
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw, shot, signed_in_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live
FAST = 8000


@pytest.fixture(scope='module')
def admin():
    return Session(ADMIN)


def test_the_organiser_tags_everyone_and_announces_and_the_guest_sees_it_live(browser, party, admin):  # noqa: F811
    sql("insert into public.terms_acceptances (user_id, version) select p.id, (select terms_version from private.moderation_settings "
        f"where id = 1) from public.profiles p where p.phone in ('{ADMIN}', '{GUEST_A}', '{VIP}') on conflict do nothing")
    event = create_event(admin, 'Discussion recette', visibility='all', public_link=True, forum_enabled=True)
    guest = sql(f"select id::text id from public.profiles where phone = '{GUEST_A}'")[0]['id']
    # Co-organisateur : se connecte dans le navigateur (l'Admin de test vient de recevoir un code par l'API : un par minute).
    sql(f"insert into public.event_organizers (event_id, user_id) select '{event}', id from public.profiles where phone = '{VIP}'")
    # Un co-organisateur est membre (un Guest n'organise pas : is_organizer) ; rôle remis à la fin.
    vip_role = sql(f"select role from public.profiles where phone = '{VIP}'")[0]['role']
    sql(f"update public.profiles set role = 'member' where phone = '{VIP}'")
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{guest}', 'yes') on conflict do nothing")
    errors: list = []
    contexts = []
    try:
        octx, orga = signed_in_page(browser, VIP, party, event, errors)
        contexts.append(octx)
        gctx, g = signed_in_page(browser, GUEST_A, party, event, errors)
        contexts.append(gctx)
        g.goto(f'{party}/events/event/{event}/chat')
        gfield = g.get_by_label('Message', exact=True)
        pw.expect(gfield).to_be_visible(timeout=30000)
        pw.expect(g.get_by_role('button', name='Faire une annonce')).to_have_count(0)
        gfield.fill('@toutlemonde ça marche ?')
        pw.expect(g.get_by_text('réservés à l’organisation de l’événement', exact=False)).to_be_visible()
        gfield.fill('')
        shot(g, 'de-01-invitee-vide')

        orga.goto(f'{party}/events/event/{event}/chat')
        field = orga.get_by_label('Message', exact=True)
        pw.expect(field).to_be_visible(timeout=30000)
        field.fill('@tou')
        orga.get_by_role('menuitem', name='@toutlemonde : Tout le monde : invités et participants').click()
        field.press_sequentially('on commence à 20 h')
        orga.get_by_role('button', name='Envoyer', exact=True).click()
        orga.get_by_role('button', name='Faire une annonce').click()
        field.fill('Parking derrière la salle')
        shot(orga, 'de-02-orga-annonce-en-cours')
        orga.get_by_role('button', name='Publier l’annonce').click()

        # Chez l'invitée, sans recharger : le message, puis l'annonce en carte et en bandeau.
        pw.expect(g.get_by_text('on commence à 20 h', exact=False).first).to_be_visible(timeout=FAST)
        pw.expect(g.get_by_text('📣 ANNONCE', exact=True)).to_be_visible(timeout=FAST)
        pw.expect(g.get_by_role('button', name='Annonce : ', exact=False).first).to_be_visible(timeout=FAST)
        shot(g, 'de-03-invitee-annonce')
        shot(orga, 'de-04-orga-apres')

        rows = sql(f"select body, mention_all, announcement, pinned from public.messages where event_id = '{event}' order by created_at")
        assert [(r['mention_all'], r['announcement'], r['pinned']) for r in rows] == [(True, False, False), (False, True, True)], rows
        # Notifications : un compte Guest n'en reçoit pas pour une discussion d'événement (private.is_member, règle d'avant) ;
        # celles des membres (citée, « 📣 Annonce · … ») sont vérifiées sur la base : test_discussion_evenement_live.py.
        assert not errors, errors
    finally:
        for context in contexts:
            context.close()
        sql(f"update public.profiles set role = '{vip_role}' where phone = '{VIP}'")
        sql(f"delete from public.notifications where event_id = '{event}'")
        sql(f"delete from public.events where id = '{event}'")
