"""Règle permanente : chaque type de notification a son interrupteur, et il coupe tous les canaux.

Base (Événements) : `private.web_push_allowed` décide pour le Web Push, l'iPhone et Expo ; un type absent de son
`case` tombe dans `else true` (envoyé sans aucun interrupteur). On relit les migrations : chaque type créé par la base
doit y avoir sa branche `prefs.<colonne>`, et chaque colonne un interrupteur dans Réglages › Notifications (web).
Serveur Party (musique, avis, jeux) : chaque `notify_guest` / `notify_admin` utilise un type réglable, présent à l'écran.
Le vrai comportement (base de test) : tests/supabase_live/test_notification_pause_live.py, test_nouveau_compte_live.py."""
import re
from pathlib import Path

from app.party import ADMIN_NOTIFY_DEFAULTS, GUEST_NOTIFY_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
SQL = "\n".join(p.read_text() for p in sorted((ROOT / "supabase/migrations").glob("*.sql")))
SETTINGS = (ROOT / "web/events/src/app/settings/notifications.tsx").read_text()
# Toujours envoyés : l'essai demandé par la personne elle-même (aucun interrupteur à avoir).
TESTS = {"web_push_test", "push_test"}


def created_kinds() -> set[str]:
    kinds = set(re.findall(r"queue_notification\(\s*[^,()]+,\s*'([a-z_]+)'", SQL))
    kinds |= set(re.findall(r"insert into public\.notifications\s*\([^)]*\)\s*(?:values\s*\(|select)\s*[^,]+,\s*'([a-z_]+)'", SQL,
                            flags=re.I))
    kinds |= set(re.findall(r"v_kind\s*:=\s*'([a-z_]+)'", SQL))
    for call in re.findall(r"private\.tell_(?:requester|validators)\(([^;]*)", SQL):
        kinds |= set(re.findall(r"'([a-z_]+)'", call))
    return kinds


def switched_kinds() -> dict[str, set[str]]:
    """Branches de web_push_allowed : type → colonnes de notification_prefs lues."""
    out: dict[str, set[str]] = {}
    for kind, rule in re.findall(r"when '([a-z_]+)' then ([^\n]*prefs\.[^\n]*)", SQL):
        out.setdefault(kind, set()).update(re.findall(r"prefs\.([a-z_]+)", rule))
    out["admin_announcement"] = {"announcements"}  # branche à part, en tête de la fonction
    return out


def test_the_scan_finds_the_kinds_of_every_feature():
    kinds = created_kinds()
    for kind in ("new_event", "event_changed", "group_message", "direct_message", "admin_announcement", "member_signup",
                 "join_request", "announce_request", "group_event_refused", "pet_daily", "bar_served", "web_push_test"):
        assert kind in kinds, kind


def test_every_notification_kind_has_a_switch_on_every_channel():
    missing = sorted(created_kinds() - TESTS - set(switched_kinds()))
    assert not missing, f"types envoyés sans interrupteur (else true de web_push_allowed) : {missing}"


def test_every_switch_is_on_the_settings_screen():
    columns = set().union(*switched_kinds().values())
    absent = sorted(c for c in columns if not re.search(rf"\b{c}\b", SETTINGS))
    assert not absent, f"interrupteurs absents de Réglages › Notifications : {absent}"


def test_party_server_notifications_use_switchable_kinds():
    main = (ROOT / "app/main.py").read_text()
    calls = re.findall(r"\n\s+(notify_guest|notify_admin)\((.*?)\)\n", main, flags=re.S)
    kinds = lambda name: {(re.findall(r'kind="([a-z_]+)"', args) or ["messages"])[0] for n, args in calls if n == name}
    guest, admin = kinds("notify_guest"), kinds("notify_admin")
    assert guest == set(GUEST_NOTIFY_DEFAULTS), guest
    # notify_admin sans kind = « messages » (valeur par défaut).
    assert admin == set(ADMIN_NOTIFY_DEFAULTS), admin
    screens = (ROOT / "web/events/src/components/PartyNotifications.tsx").read_text()
    assert all(f"kind: '{k}'" in screens for k in GUEST_NOTIFY_DEFAULTS)
    host = (ROOT / "app/static/people-admin.js").read_text() + (ROOT / "app/static/admin.html").read_text()
    assert all(f'data-pa-notif="{k}"' in host for k in ADMIN_NOTIFY_DEFAULTS)


def test_track_notification_opens_the_music_tab():
    """Party s'ouvre sur Événements (avis du 13.11) : « Ton titre passe » doit demander Musique."""
    main = (ROOT / "app/main.py").read_text()
    assert '"url": "/?tab=music", "tag": "now-playing"' in main
    assert 'params.get("tab") === "music"' in (ROOT / "app/static/index.html").read_text()
