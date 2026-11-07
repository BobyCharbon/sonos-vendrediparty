"""Invitations v2 (05.11.2026, bêta), sur la VRAIE base de test (jamais la prod) : liens pour une personne ou pour
plusieurs, carte lisible sans compte, réponse en une fois avec le prénom seul, carte « Invités » de l'organisateur,
gens de Party ajoutés hors du groupe, relances (une par jour), retrait, comptes invités minimaux effacés après.
CGU exigées comme en prod (terms_enforced) : le compte neuf les accepte au geste « Confirmer » de la carte, avant sa
réponse (InviteCardScreen → acceptTermsIfNeeded) ; sans elles, son prénom est refusé (terms_required).
Seuls des comptes de test sont invités ou prévenus ; aucun SMS (codes fixes).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_invitations_v2_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, create_event
from tests.supabase_live.test_invite_links_live import NEW, anon_rpc
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def terms_version() -> str:
    return sql('select terms_version v from private.moderation_settings where id = 1')[0]['v']


def terms_enforced() -> bool:
    return sql('select terms_enforced from private.moderation_settings where id = 1')[0]['terms_enforced']


@pytest.fixture(scope='module')
def people():
    sessions = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP), Session(NEW)
    newcomer = sessions[-1]
    # Comptes déjà là : CGU acceptées (comme un vrai compte avant son premier contenu).
    for s in sessions[:-1]:
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    # Compte neuf : aucun prénom ni CGU (comme une personne qui reçoit le lien sur WhatsApp) ; remis tel quel après.
    accepted = sql(f"select version from public.terms_acceptances where user_id = '{newcomer.uid}'")
    reset = (f"update public.profiles set display_name = '' where id = '{newcomer.uid}'; "
             f"delete from private.light_invitees where user_id = '{newcomer.uid}'; "
             f"delete from public.terms_acceptances where user_id = '{newcomer.uid}'")
    sql(reset)
    yield sessions
    sql(reset)
    for row in accepted:
        sql(f"insert into public.terms_acceptances (user_id, version) values ('{newcomer.uid}', '{row['version']}') "
            "on conflict do nothing")


def error_of(r: httpx.Response) -> str:
    assert r.status_code >= 400, r.text
    return r.text


def test_links_for_one_or_several_people_and_answer_without_a_full_profile(people):
    admin, ga, gb, vip, new = people
    event = create_event(admin, 'Test invitations v2', visibility='invited', location_name='Chez Admin',
                         location_address='Rue Secrète 1, Sion')
    try:
        # Seuls les organisateurs créent un lien ; il marche quel que soit le public de l'événement.
        assert ga.rpc('create_event_invite', e=event).status_code >= 400
        single = admin.rpc('create_event_invite', e=event, places=1, label='Léa').json()
        several = admin.rpc('create_event_invite', e=event, places=2).json()
        assert single['max_uses'] == 1 and single['label'] == 'Léa' and several['max_uses'] == 2

        # Sans compte : la carte, sans l'adresse exacte ; l'ouverture est notée (« A ouvert »).
        preview = anon_rpc('invite_preview', token=single['token'], opened=True).json()
        assert preview['title'] == 'Test invitations v2' and preview['inviter'] == 'Admin test'  # surnom complet (20261106200000)
        assert preview['location_name'] == 'Chez Admin' and preview['location_address'] is None
        assert preview['state'] == 'pending' and preview['label'] == 'Léa' and preview['event_id'] is None
        assert anon_rpc('invite_preview', token='00000000-0000-4000-8000-000000000000').json() is None
        assert anon_rpc('accept_invite', token=single['token'], answer='yes').status_code >= 400  # compte requis

        # Compte neuf : le prénom suffit ; il voit l'événement, n'entre dans aucun groupe.
        assert 'first_name_required' in error_of(new.rpc('accept_invite', token=single['token'], answer='yes'))
        if terms_enforced():  # CGU exigées (prod) : pas de prénom enregistré tant qu'elles ne sont pas acceptées
            assert 'terms_required' in error_of(new.rpc('accept_invite', token=single['token'], answer='yes', first_name='Léa'))
            assert sql(f"select display_name from public.profiles where id = '{new.uid}'") == [{'display_name': ''}]
            assert anon_rpc('invite_preview', token=single['token']).json()['state'] == 'opened'  # lien intact (ouvert, pas servi)
        # Le geste « Confirmer » de la carte accepte les CGU, puis répond.
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        done = new.rpc('accept_invite', token=single['token'], answer='yes', first_name='Léa').json()
        assert done['event_id'] == event and done['location_address'] == 'Rue Secrète 1, Sion'
        assert sql(f"select display_name, first_name from public.profiles where id = '{new.uid}'") == [{'display_name': 'Léa', 'first_name': ''}]
        assert new.get(f'events?select=id&id=eq.{event}').json() == [{'id': event}]
        assert new.get(f'member_group_members?select=group_id&user_id=eq.{new.uid}').json() == []
        row = admin.get(f'event_invites?select=via_link,via_group,invited_by,link_token&event_id=eq.{event}&user_id=eq.{new.uid}').json()
        assert row == [{'via_link': True, 'via_group': False, 'invited_by': admin.uid, 'link_token': single['token']}]
        mine = new.rpc('invite_preview', token=single['token']).json()
        assert mine['state'] == 'mine' and mine['mine'] == 'yes' and mine['location_address'] == 'Rue Secrète 1, Sion'
        # Rouvrir le même lien pour changer sa réponse : pas de seconde arrivée ni de seconde notification.
        assert new.rpc('accept_invite', token=single['token'], answer='maybe').json()['status'] == 'maybe'
        notes = admin.get(f"notifications?select=body&kind=eq.link_join&event_id=eq.{event}").json()
        assert notes == [{'body': "Léa a répondu par ton lien d'invitation"}]

        # Pour une personne : déjà servi. Pour plusieurs : 2 places, puis plein.
        assert 'une seule personne' in error_of(gb.rpc('accept_invite', token=single['token'], answer='yes'))
        assert ga.rpc('accept_invite', token=several['token'], answer='maybe').status_code == 200
        assert anon_rpc('invite_preview', token=several['token']).json()['places_left'] == 1
        assert gb.rpc('accept_invite', token=several['token'], answer='no').status_code == 200
        assert 'places de ce lien sont prises' in error_of(vip.rpc('accept_invite', token=several['token'], answer='yes'))

        # Carte « Invités » : qui vient, d'où (lien noté « Léa »), invité par qui, liens et arrivées.
        assert ga.rpc('event_guest_list', e=event).status_code >= 400
        card = admin.rpc('event_guest_list', e=event).json()
        by_id = {p['id']: p for p in card['people']}
        assert by_id[new.uid]['source'] == 'link' and by_id[new.uid]['link_label'] == 'Léa' and by_id[new.uid]['light']
        assert by_id[new.uid]['invited_by'] == 'Admin test' and by_id[new.uid]['status'] == 'maybe' and by_id[new.uid]['removable']
        assert (by_id[ga.uid]['status'], by_id[gb.uid]['status']) == ('maybe', 'no')
        links = {l['token']: l for l in card['links']}
        assert links[single['token']]['state'] == 'full' and links[single['token']]['opened_at']
        assert [a['name'] for a in links[single['token']]['arrivals']] == ['Léa']
        assert links[several['token']]['uses'] == 2 and links[several['token']]['state'] == 'full'

        # Retiré : il ne voit plus l'événement, sa réponse part, le lien ne le réinscrit pas.
        assert admin.rpc('remove_invitee', e=event, member=new.uid).status_code in (200, 204)
        assert new.get(f'events?select=id&id=eq.{event}').json() == []
        assert admin.get(f'rsvps?select=status&event_id=eq.{event}&user_id=eq.{new.uid}').json() == []
        assert 'removed' in error_of(new.rpc('accept_invite', token=single['token'], answer='yes'))

        # Compte invité minimal, plus d'événement à venir, 7 jours passés : prêt à être effacé (on ne l'efface pas ici).
        sql(f"update private.light_invitees set created_at = now() - interval '8 days' where user_id = '{new.uid}'")
        assert {'u': new.uid} in sql('select private.light_invitees_to_purge() u')
        assert {'u': ga.uid} not in sql('select private.light_invitees_to_purge() u')  # profil complet : jamais

        # Lien arrêté, puis événement annulé : refusés avec la raison.
        third = admin.rpc('create_event_invite', e=event, places=3).json()['token']
        assert admin.rpc('revoke_invite_link', tok=third).status_code in (200, 204)
        assert 'arrêté' in error_of(vip.rpc('accept_invite', token=third, answer='yes'))
        fourth = admin.rpc('create_event_invite', e=event, places=3).json()['token']
        httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, json={'status': 'cancelled'}, timeout=30)
        assert anon_rpc('invite_preview', token=fourth).json()['status'] == 'cancelled'
        assert 'annulé' in error_of(vip.rpc('accept_invite', token=fourth, answer='yes'))
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_party_people_are_added_out_of_the_group_and_nudged_once_a_day(people):
    admin, ga, gb, vip, _new = people
    event = create_event(admin, 'Test invités v2 relances', visibility='invited')
    session_of_gb = sql(f"select id from auth.sessions where user_id = '{gb.uid}' order by created_at desc limit 1")[0]['id']
    try:
        # Ajoutés d'ici : invités (pas dans un groupe), prévenus par une invitation Party.
        added = admin.rpc('invite_people', e=event, people=[ga.uid, gb.uid]).json()
        assert added == {'people': 2, 'groups': 0}
        assert admin.rpc('invite_people', e=event, people=[ga.uid]).json() == {'people': 0, 'groups': 0}  # déjà invité
        assert ga.rpc('invite_people', e=event, people=[vip.uid]).status_code >= 400  # organisateurs seulement
        rows = admin.get(f'event_invites?select=user_id,via_group,invited_by&event_id=eq.{event}&order=user_id').json()
        assert {(r['user_id'], r['via_group'], r['invited_by']) for r in rows} == {(ga.uid, False, admin.uid), (gb.uid, False, admin.uid)}
        assert len(ga.get(f"notifications?select=id&kind=eq.private_invite&event_id=eq.{event}").json()) == 1
        card = admin.rpc('event_guest_list', e=event).json()
        assert {p['id']: p['invited_by'] for p in card['people']} == {ga.uid: 'Admin test', gb.uid: 'Admin test'}

        # Relance : Guest B a l'app (un appareil de test, jeton factice) → notification ; Guest A non → la feuille de partage.
        sql(f"insert into public.push_tokens (token, user_id, platform, session_id) values ('test-invites-v2-{gb.uid}', '{gb.uid}', 'ios', '{session_of_gb}')"
            " on conflict do nothing")
        nudge = admin.rpc('nudge_invitees', e=event, people=[ga.uid, gb.uid]).json()
        assert nudge['notified'] == 1 and nudge['share'] == [ga.uid] and nudge['skipped'] == 0
        notes = gb.get(f"notifications?select=title,body,dedupe_key&kind=eq.private_invite&event_id=eq.{event}&dedupe_key=like.invite_nudge*").json()
        assert len(notes) == 1 and notes[0]['body'] == 'Admin test attend ta réponse : tu viens ?'
        # Une seule relance par jour et par personne ; qui a répondu n'est jamais relancé.
        again = admin.rpc('nudge_invitees', e=event, people=[ga.uid, gb.uid]).json()
        assert again == {'notified': 0, 'skipped': 2, 'share': []}
        assert all(p['nudged_today'] for p in admin.rpc('event_guest_list', e=event).json()['people'])

        # Un lien sans réponse se relance aussi une fois par jour (par le partage).
        link = admin.rpc('create_event_invite', e=event, places=1, label='Tom').json()['token']
        assert admin.rpc('nudge_invite_link', tok=link).status_code in (200, 204)
        assert 'Déjà relancé' in error_of(admin.rpc('nudge_invite_link', tok=link))
        assert ga.rpc('nudge_invite_link', tok=link).status_code >= 400

        # Une personne venue par un groupe ne se retire pas d'ici.
        sql(f"update public.event_invites set via_group = true where event_id = '{event}' and user_id = '{ga.uid}'")
        assert 'groupe' in error_of(admin.rpc('remove_invitee', e=event, member=ga.uid))
    finally:
        sql(f"delete from public.push_tokens where token = 'test-invites-v2-{gb.uid}'; "
            f"delete from public.notifications where event_id = '{event}'")
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)
