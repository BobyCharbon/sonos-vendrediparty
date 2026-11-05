"""Assistant IA ouvert à tous (migration 20261105110000), sur la VRAIE base de test : chaque rôle a le droit ai.use, un
Guest le voit dans ses droits, et la distribution ne repasse pas (un rôle à qui l'admin l'a retiré ne le retrouve pas).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_ai_pour_tous_live.py -q"""
from pathlib import Path

from tests.supabase_live.test_audiences_live import GUEST_A
from tests.supabase_live.test_event_tickets_live import sql_test
from tests.supabase_live.test_member_admin_live import Session, pytestmark  # noqa: F401

MIGRATION = Path(__file__).resolve().parents[2] / 'supabase/migrations/20261105110000_ai_pour_tous.sql'


def test_every_role_can_use_the_assistant():
    missing = sql_test("select r.key from public.roles r where not exists "
                       "(select 1 from public.role_permissions p where p.role = r.key and p.perm = 'ai.use')")
    assert missing == []
    assert 'ai.use' in Session(GUEST_A).rpc('my_permissions').json()


def test_replaying_the_migration_does_not_give_the_right_back():
    sql_test("delete from public.role_permissions where role = 'guestplus' and perm = 'ai.use'; select 1")
    try:
        sql_test(MIGRATION.read_text(encoding='utf-8') + '\nselect 1')
        assert sql_test("select count(*) as n from public.role_permissions where role = 'guestplus' and perm = 'ai.use'")[0]['n'] == 0
    finally:
        sql_test("insert into public.role_permissions (role, perm) values ('guestplus', 'ai.use') on conflict do nothing; select 1")
