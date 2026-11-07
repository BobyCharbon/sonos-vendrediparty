"""Réglages › Notifications (campagne 2, rapport 07 n° 5) : un Membre (basic) ou un Guest ne voit plus les interrupteurs
que private.may_receive_push lui refuse toujours (sondage, billet, réponses…). Le serveur dit lesquels cacher
(« hidden ») : l'app iPhone et le web suivent la même liste."""
import httpx
import pytest

from app import accounts as accounts_mod

# Clés de notification_prefs dont les types sont refusés aux non-Membres VIP (matrice-push.txt de la campagne 2).
EXPECTED_HIDDEN = {"new_event", "poll_new", "poll_nudge", "rsvp_set", "ticket_pay_confirmed", "ticket_issued",
                   "rsvp_mine", "ticket_pay_declared", "proposal_result", "proposals", "chat"}


def accounts(perms):
    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-9"})
        if request.url.path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=perms)
        if request.url.path == "/rest/v1/notification_prefs":
            return httpx.Response(200, json=[{"user_id": "u-9", "chat": "all"}])
        return httpx.Response(404)
    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("perms", [[], ["feedback.write"]])
def test_member_and_guest_get_the_list_of_switches_that_never_fire(perms):
    state = accounts(perms).notification_prefs("tok")
    assert state["member"] is False
    assert set(state["hidden"]) == EXPECTED_HIDDEN
    assert state["hidden"] == sorted(state["hidden"])


def test_vip_member_sees_every_switch():
    state = accounts(["events.view", "events.approve"]).notification_prefs("tok")
    assert state["member"] is True and state["hidden"] == [] and state["approver"] is True


def test_keys_that_still_fire_for_everyone_are_never_hidden():
    # Types que may_receive_push laisse passer pour tout compte actif : event_changed, date_fixed, waitlist, invites…
    for key in ("event_changed", "date_fixed", "waitlist", "invites", "link_join", "reminders", "moderation_notices"):
        assert key not in accounts_mod.NON_MEMBER_HIDDEN_PREFS
