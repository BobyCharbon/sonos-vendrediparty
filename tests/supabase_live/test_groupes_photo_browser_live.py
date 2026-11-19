"""Recette RÉELLE de la photo de groupe (17.11.2026) : vrai navigateur, vrai serveur Party, base de TEST, Guest A.
Guest A crée « Recette photo » avec une photo (choisie, recadrée) : la base la garde dans le dossier du groupe ; la page
du groupe, la liste et les bulles l'affichent ; Réglages du groupe › « Retirer la photo » la retire. Groupe supprimé à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $GROUPS_SHOTS si la variable est définie."""
import io

import httpx
import pytest
from PIL import Image

from tests.supabase_live.test_groupes_graphisme_browser_live import DIST, pw, shot  # noqa: F401
from tests.supabase_live.test_audiences_live import GUEST_A
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
NAME = 'Recette photo'


def cleanup(s: Session):
    for r in sql(f"select id::text from public.member_groups where name = '{NAME}' and created_by = '{s.uid}'"):
        files = [f['name'] for f in sql(f"select name from storage.objects where bucket_id = 'group-photos' and name like '{r['id']}/%'")]
        if files:
            httpx.request('DELETE', f'{TEST_URL}/storage/v1/object/group-photos', headers=s.headers, json={'prefixes': files}, timeout=30)
    sql(f"delete from public.member_groups where name = '{NAME}' and created_by = '{s.uid}'")


@pytest.fixture
def guest():
    s = Session(GUEST_A)
    assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    cleanup(s)
    yield s
    cleanup(s)


def photo_file() -> dict:
    out = io.BytesIO()
    img = Image.new('RGB', (600, 400), (255, 179, 71))
    for x in range(0, 600, 60):
        for y in range(0, 400, 40):
            img.putpixel((x, y), (40, 20, 80))
    img.save(out, 'JPEG')
    return {'name': 'bande.jpg', 'mimeType': 'image/jpeg', 'buffer': out.getvalue()}


def test_a_group_gets_a_photo_shown_everywhere_then_removed(browser, party, guest):  # noqa: F811
    context, page, errors = phone_page(browser, alone=True)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 01')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/group/new', wait_until='domcontentloaded')
        page.get_by_label('Nom du groupe').fill(NAME, timeout=30000)
        page.get_by_test_id('group-photo-input').set_input_files(photo_file())
        pw.expect(page.get_by_role('dialog', name='Recadrer la photo du groupe')).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Valider la photo').click()
        pw.expect(page.get_by_test_id('group-preview').get_by_test_id('group-photo')).to_be_visible(timeout=15000)
        shot(page, 'photo-01-creer')
        page.get_by_role('button', name='Continuer').click()
        pw.expect(page.get_by_test_id('group-invite-panel')).to_be_visible(timeout=20000)
        rows = sql(f"select id::text, photo_path, photo_by::text from public.member_groups where name = '{NAME}' and created_by = '{guest.uid}'")
        assert len(rows) == 1 and rows[0]['photo_path'].startswith(rows[0]['id'] + '/') and rows[0]['photo_by'] == guest.uid, rows
        gid = rows[0]['id']
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_role('heading', name=NAME)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_label(f'Photo du groupe {NAME}')).to_be_visible(timeout=15000)  # couverture
        pw.expect(page.get_by_test_id('group-page').get_by_test_id('group-photo')).to_be_visible()  # tuile
        shot(page, 'photo-02-page')
        page.goto(f'{party}/events/groups', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id(f'group-row-{gid}').get_by_test_id('group-photo')).to_be_visible(timeout=30000)
        shot(page, 'photo-03-liste')
        page.goto(f'{party}/events/group/{gid}/settings', wait_until='domcontentloaded')
        page.get_by_role('button', name='Retirer la photo').click(timeout=30000)
        page.get_by_role('button', name='Confirmer').click()
        pw.expect(page.get_by_text('Photo retirée', exact=True)).to_be_visible(timeout=15000)
        assert sql(f"select photo_path from public.member_groups where id = '{gid}'") == [{'photo_path': None}]
        shot(page, 'photo-04-retiree')
        assert not errors, errors
    finally:
        context.close()
