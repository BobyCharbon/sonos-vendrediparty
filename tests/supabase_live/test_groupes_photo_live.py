"""Photo de groupe (17.11.2026, migration 20261117130000), sur la VRAIE base de test (jamais la prod) :
- qui gère le groupe envoie la photo dans le dossier du groupe et la pose ; my_groups_overview et my_chats la donnent ;
- un membre la voit mais ne peut pas en envoyer ; quelqu'un hors du groupe ne la voit pas ;
- chemin d'un autre dossier ou fichier absent : refusé ; Membres Vendredi Party : jamais de photo (logo officiel) ;
- « Signaler la photo » puis « Masquer » : la photo quitte le groupe, le modérateur reçoit le fichier à retirer."""
import io
import uuid

import httpx
import pytest
from PIL import Image

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, make_vip, unmake_vip
from tests.supabase_live.test_groupes_graphisme_live import patch_group
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

BUCKET = f'{TEST_URL}/storage/v1/object/group-photos'


def jpeg() -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (32, 32), (255, 79, 154)).save(out, 'JPEG')
    return out.getvalue()


def upload(s: Session, path: str) -> httpx.Response:
    return httpx.post(f'{BUCKET}/{path}', headers={**s.headers, 'Content-Type': 'image/jpeg'}, content=jpeg(), timeout=30)


def download(s: Session, path: str) -> httpx.Response:
    return httpx.get(f'{TEST_URL}/storage/v1/object/authenticated/group-photos/{path}', headers=s.headers, timeout=30)


@pytest.fixture(scope='module')
def world():
    admin, vip, ga, gb = Session(ADMIN), Session(VIP), Session(GUEST_A), Session(GUEST_B)
    make_vip(admin, vip)
    complete_profile(ga, 'Guest A')
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**vip.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test photo', 'emoji': '🎸', 'color': 'sky', 'created_by': vip.uid})
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    sql_test(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{ga.uid}') on conflict do nothing")
    yield admin, vip, ga, gb, gid
    paths = [p['name'] for p in sql_test(f"select name from storage.objects where bucket_id = 'group-photos' and name like '{gid}/%'")]
    if paths:
        httpx.request('DELETE', BUCKET, headers=vip.headers, json={'prefixes': paths}, timeout=30)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=vip.headers, timeout=30)
    unmake_vip(admin, vip)


def test_the_creator_sets_a_photo_that_members_see_and_outsiders_do_not(world):
    _, vip, ga, gb, gid = world
    path = f'{gid}/{uuid.uuid4().hex}.jpg'
    assert upload(vip, path).status_code == 200
    ok = patch_group(vip, gid, photo_path=path)
    assert ok.status_code == 200 and ok.json()[0]['photo_path'] == path and ok.json()[0]['photo_by'] == vip.uid, ok.text
    assert next(g for g in vip.rpc('my_groups_overview').json() if g['id'] == gid)['photo'] == path
    assert next(c for c in ga.rpc('my_chats').json() if c['id'] == gid)['photo_path'] == path  # app iPhone
    assert download(ga, path).status_code == 200  # membre : la voit
    assert download(gb, path).status_code in (400, 403, 404)  # hors du groupe : rien
    assert upload(ga, f'{gid}/{uuid.uuid4().hex}.jpg').status_code in (400, 403)  # membre : n'en envoie pas
    assert patch_group(ga, gid, photo_path=None).json() == []  # ni ne la retire (ligne non modifiable)


def test_a_path_outside_the_group_or_a_missing_file_is_refused(world):
    _, vip, _, _, gid = world
    other = f'{uuid.uuid4()}/{uuid.uuid4().hex}.jpg'
    assert upload(vip, other).status_code in (400, 403)  # dossier d'un groupe qu'il ne gère pas
    assert patch_group(vip, gid, photo_path=other).status_code == 400
    assert patch_group(vip, gid, photo_path=f'{gid}/absente.jpg').status_code == 400


def test_vendredi_party_never_gets_a_photo():
    rows = sql_test("""
    with u as (update public.member_groups set photo_path = id::text || '/x.jpg' where system_key = 'vip' returning photo_path)
    select photo_path from u""")
    assert rows == [{'photo_path': None}], rows


def test_a_reported_photo_is_removed_by_the_moderation(world):
    admin, vip, ga, gb, gid = world
    path = f'{gid}/{uuid.uuid4().hex}.jpg'
    assert upload(vip, path).status_code == 200 and patch_group(vip, gid, photo_path=path).status_code == 200
    assert gb.rpc('report_content', p_kind='group_photo', p_target=gid, p_reason='shocking').status_code == 404  # hors du groupe : pas visible
    rid = ga.rpc('report_content', p_kind='group_photo', p_target=gid, p_reason='shocking')
    assert rid.status_code == 200, rid.text
    done = admin.rpc('moderation_act', p_report=rid.json(), p_action='hide')
    assert done.status_code == 200 and done.json()['remove_group_photo'] == path, done.text
    assert sql_test(f"select photo_path from public.member_groups where id = '{gid}'") == [{'photo_path': None}]
    gone = httpx.request('DELETE', BUCKET, headers=admin.headers, json={'prefixes': [path]}, timeout=30)
    assert gone.status_code == 200 and gone.json(), gone.text  # le modérateur retire le fichier
