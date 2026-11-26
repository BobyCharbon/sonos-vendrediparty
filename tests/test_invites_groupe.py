"""« Réunir les invités dans un groupe » (décision de l'admin du 17.11.2026, avis de conformité du 17.11) : ce que les
tests en vraie base (tests/supabase_live/test_invites_groupe_live.py) ne voient pas — l'IA n'y touche jamais, la migration
reste additive, la case est décochée par défaut, la notification a son interrupteur partout, le toucher ouvre le groupe."""
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from app import ai_events as ev, group_chats as gc, main
from tests.test_ai_event_edit import current, editor
from tests.test_ai_events import READY, make

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261117110000_invites_groupe.sql").read_text()
WEB = ROOT / "web/events/src"


def test_the_ai_never_sets_the_guest_group(tmp_path):
    """Hors du schéma de l'IA (création et modification) : ni le brouillon, ni l'événement écrit n'en parlent."""
    schema = ev.schema({"categories": [], "tags": [], "audiences": ["Vendredi Party"], "people": []})
    assert "guest_group" not in json.dumps(schema)
    d = ev.clean_draft({**READY, "guest_group": "g1"}, datetime.now(ev.ZURICH),
                       {"categories": ["Soirée"], "tags": [], "audiences": ["Ski"], "people": ["Tom"]})
    assert "guest_group" not in d
    a, accounts, _ = make(tmp_path)
    a.save_draft("ok", {**READY, "guest_group": "g1"}, None)
    a.create("ok", {**READY, "guest_group": "g1"}, None)
    writes = [j for m, p, j in accounts.calls if p.startswith("/rest/v1/events") and isinstance(j, dict)]
    assert writes and all("guest_group" not in j for j in writes)
    asked = {**current(tmp_path), "title": "Raclette géante", "guest_group": "g1"}
    e, accounts, _ = editor(tmp_path, asked)
    e.save("ok", "e1", asked, None, announce=False)
    patch = next(body for m, p, body in accounts.calls if m == "PATCH" and p.startswith("/rest/v1/events"))
    assert "guest_group" not in patch
    assert "guest_group" not in (ROOT / "app/ai_events.py").read_text() + (ROOT / "app/ai_event_edit.py").read_text()


def test_the_migration_is_additive_and_replayable():
    for line in re.findall(r"^\s*(create (?:table|function|trigger|or replace function)[^\n]*)", MIGRATION, flags=re.M | re.I):
        assert re.match(r"create (table if not exists|or replace function|trigger)", line, flags=re.I), line
    for trigger in re.findall(r"create trigger (\w+)", MIGRATION):
        assert f"drop trigger if exists {trigger}" in MIGRATION
    assert "add column if not exists guest_group" in MIGRATION and "add column if not exists group_added" in MIGRATION
    assert not re.search(r"\b(drop table|drop column|delete from public\.|truncate)\b", MIGRATION, flags=re.I)
    # Tables privées : aucune lecture directe (RLS fermée, droits retirés).
    for table in ("group_departures", "guest_group_choices", "band_offers"):
        assert f"alter table private.{table} enable row level security" in MIGRATION
        assert f"revoke all on private.{table} from public, anon, authenticated" in MIGRATION


def test_the_database_never_decides_alone_and_never_announces_to_the_group():
    # Le choix vient de l'écran (true / false) ; sans paramètre (accept_invite), rien.
    assert "if join_group is null then raise exception 'Choix manquant'" in MIGRATION
    assert "coalesce((r->>'organizer')::boolean, false) or join_group is null" in MIGRATION
    # Seul le créateur est prévenu (join_group existant), jamais une annonce ni une invitation d'événement au groupe.
    code = "\n".join(line for line in MIGRATION.splitlines() if not line.lstrip().startswith("--"))
    assert "send_announcement" not in code and "private_invite" not in code and "event_announcements" not in code
    # Départ noté seulement quand on part soi-même, jamais par une cascade (groupe ou compte supprimé).
    assert "if auth.uid() = old.user_id and exists (select 1 from public.member_groups g where g.id = old.group_id)" in MIGRATION
    # Le trou du 17.11 : invite_to_group refuse aussi une personne en blocage avec le créateur du groupe.
    assert "if private.blocked_either(target, auth.uid()) or private.blocked_either(target, g.created_by) then" in MIGRATION


def test_the_box_is_unticked_by_default_and_clear():
    screen = (WEB / "components/InviteCardScreen.tsx").read_text()
    assert "peekInviteJoin(token!) ?? false : false" in screen
    rsvp = (WEB / "components/EventSections.tsx").read_text()
    assert "const [joinGroup, setJoinGroup] = useState(false);" in rsvp
    lib = (WEB / "lib/guestGroup.ts").read_text()
    assert "Rejoindre aussi le groupe « ${groupLabel(g)} »${g.owner ? ` de ${g.owner}` : ''}" in lib
    for words in ("ton surnom et ta photo (ton nom seulement si tu as choisi de l’afficher)", "Ton numéro reste caché", "Tu quittes le groupe quand tu veux",
                  "invité à ses prochains événements"):
        assert words in lib
    box = (WEB / "components/GuestGroup.tsx").read_text()
    assert 'accessibilityRole="checkbox"' in box and "membersLine(card.members)" in box
    privacy = (WEB / "app/privacy.tsx").read_text()
    assert "Groupe d’un événement : si tu coches « Rejoindre aussi le groupe »" in privacy and "Base : ta demande." in privacy


def test_the_notification_has_its_switch_everywhere():
    assert "when 'group_added' then coalesce(prefs.group_added, true)" in MIGRATION
    assert main.NotificationPatch(group_added=False).group_added is False
    web = (WEB / "app/settings/notifications.tsx").read_text()
    assert "update({ group_added: v })" in web
    ios = (ROOT / "ios/Party/Settings/NotificationSettingsView.swift").read_text()
    assert 'eventToggle("group_added"' in ios
    assert 'case ("group_added", let v as Bool): p.groupAdded = v' in (ROOT / "ios/Party/Settings/SettingsStore.swift").read_text()


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_touching_the_notification_opens_the_group():
    script = ("import(process.argv[1]).then(({ notificationTarget }) => console.log(JSON.stringify(notificationTarget("
              "JSON.parse(process.argv[2])))))")
    row = {"origin": "https://party.bobycharbon.ch", "kind": "group_added", "event_id": None,
           "group_id": "0a0b0c0d-0000-4000-8000-000000000002"}
    out = subprocess.run(["node", "-e", script, (ROOT / "supabase/functions/send-web-push/target.ts").as_uri(), json.dumps(row)],
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == "https://party.bobycharbon.ch/?tab=chats&chat=0a0b0c0d-0000-4000-8000-000000000002"
    assert "data.kind === 'group_added'" in (ROOT / "supabase/functions/send-push/apns.ts").read_text()
    activity = (WEB / "app/(tabs)/activity.tsx").read_text()
    assert "n.kind === 'group_added'" in activity


def test_the_native_conversation_carries_the_join_note_once():
    class Admin:
        def __init__(self, answer):
            self.answer, self.calls = answer, []

        def _rpc(self, token, name, args, fallback=""):
            self.calls.append((name, args))
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    note = {"event_id": "e1", "event_title": "Raclette", "group_name": "Les raclettes", "owner": "Ludo", "creator": False}
    chats = gc.GroupChats.__new__(gc.GroupChats)
    chats.admin = Admin(note)
    assert chats._join_note("t", "g1") == note and chats.admin.calls == [("take_group_join_note", {"grp": "g1"})]
    chats.admin = Admin(gc.AccountError("base sans la migration"))
    assert chats._join_note("t", "g1") is None  # la discussion s'ouvre quand même
    assert '"join_note": got["join_note"]' in (ROOT / "app/group_chats.py").read_text()


def test_prod_files_are_ready_and_not_applied():
    apply = (ROOT / "supabase/prod/2026-11-17-invites-groupe-apply.sql").read_text()
    rollback = (ROOT / "supabase/prod/2026-11-17-invites-groupe-rollback.sql").read_text()
    assert MIGRATION.strip() in apply and apply.strip().startswith("--") and apply.rstrip().endswith("commit;")
    assert "values ('20261117110000', 'invites_groupe')" in apply
    assert "delete from supabase_migrations.schema_migrations where version = '20261117110000'" in rollback
    assert "alter table public.events drop column if exists guest_group" in rollback
