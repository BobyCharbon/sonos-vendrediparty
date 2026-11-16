"""Web Push (supabase/functions/send-web-push) : le toucher ouvre la page portée par la notification (data.url), par
exemple « Nouveau compte » → /?tab=account, et jamais un autre site. target.ts est exécuté tel quel par Node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "supabase/functions/send-web-push"
ORIGIN = "https://party.bobycharbon.ch"
EVENT = "0a0b0c0d-0000-4000-8000-000000000001"
GROUP = "0a0b0c0d-0000-4000-8000-000000000002"


def targets(rows: list[dict]) -> list[str]:
    script = ("import(process.argv[1]).then(({ notificationTarget }) => "
              "console.log(JSON.stringify(JSON.parse(process.argv[2]).map(notificationTarget))))")
    out = subprocess.run(["node", "-e", script, (FUNCTION / "target.ts").as_uri(), json.dumps(rows)],
                         capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_the_notification_url_is_followed_on_the_same_site_only():
    row = {"origin": ORIGIN, "kind": "member_signup", "event_id": None, "group_id": None}
    assert targets([
        {**row, "url": "/?tab=account"},
        {**row, "url": "//evil.example/x"},
        {**row, "url": "/\\evil.example"},
        {**row, "url": "https://evil.example/?tab=account"},
        {**row, "url": "javascript:alert(1)"},
        {**row, "url": None},
        {**row, "kind": "event_changed", "event_id": EVENT, "url": "/?tab=account"},
        {**row, "kind": "group_message", "group_id": GROUP},
        {**row, "kind": "pet_daily", "url": "/?tab=games&pet=1"},
        {**row, "kind": "message", "event_id": EVENT},
    ]) == [
        f"{ORIGIN}/?tab=account",
        f"{ORIGIN}/?tab=events&activity=1",
        f"{ORIGIN}/?tab=events&activity=1",
        f"{ORIGIN}/?tab=events&activity=1",
        f"{ORIGIN}/?tab=events&activity=1",
        f"{ORIGIN}/?tab=events&activity=1",
        f"{ORIGIN}/?tab=events&event={EVENT}",
        f"{ORIGIN}/?tab=chats&chat={GROUP}",
        f"{ORIGIN}/?tab=games&pet=1&src=notif",
        f"{ORIGIN}/?tab=events&event={EVENT}&chat=1",
    ]


def test_the_function_sends_the_notification_url():
    source = (FUNCTION / "index.ts").read_text()
    assert "import { notificationTarget } from './target.ts';" in source
    assert "db.from('notifications').select('id, data')" in source
    assert "url: notificationTarget({ ...row, url: urls.get(row.notification_id) })" in source


def test_party_opens_the_account_tab_from_a_notification():
    page = (ROOT / "app/static/index.html").read_text()
    assert 'params.get("tab") === "account"' in page and 'showTab("account");' in page
