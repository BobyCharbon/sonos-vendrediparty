"""Agenda dans l'app iPhone (17.11) : pont PartyNative.agenda, ligne « Agenda » de Réglages › Autres apps avec sa pastille,
interrupteur « Demandes de rendez-vous », toucher de la notification booking_request, phrase d'accès aux calendriers.
Les calculs (plages « pris ») sont testés en Swift : ios/PartyTests/AgendaTests.swift."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import main

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "ios"
BOOKING = "0a0b0c0d-0000-4000-8000-000000000003"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_bridge_offers_the_agreed_contract():
    bridge = read("ios/Party/Agenda/AgendaBridge.swift")
    for method in ("status", "requestAccess", "calendars", "setCalendar", "events", "syncBusy", "addToPhone"):
        assert f"{method}: function" in bridge
    native = read("ios/Party/NativeBridge.swift")
    # BETA : le contrat ; app App Store (storeLocked) : pont à null et aucun gestionnaire (contrôle du 26.11).
    assert 'private static let agendaScript = AppConfig.storeLocked ? "null" : AgendaBridge.script' in native
    assert "agenda: \\(agendaScript)" in native
    assert ("if !AppConfig.storeLocked {\n            controller.addScriptMessageHandler(AgendaBridge(model: model), "
            "contentWorld: .page, name: AgendaBridge.handler)") in native
    # Feuille d'iOS sans autorisation ; seule la page interne parle au pont.
    assert "EKEventEditViewController" in bridge and "AppConfig.mayUseBridge(message.frameInfo.securityOrigin.url)" in bridge


def test_only_rounded_busy_ranges_leave_the_iphone():
    busy = read("ios/Party/Agenda/AgendaBusy.swift")
    store = read("ios/Party/Agenda/AgendaStore.swift")
    # Jamais titre, lieu ni nom du calendrier : début, fin, clé « ios:<id> », compte pour les groupes.
    assert 'blocks.map { ["s": iso($0.start), "e": iso($0.end), "c": key($0.calendar), "g": $0.groups] }' in busy
    assert "static let horizonDays = 60" in busy and "static let step: TimeInterval = 1800" in busy
    assert '"agenda_set_busy", ["source": "device", "blocks": AgendaBusy.payload(blocks)]' in store
    # Rien ne part tant que le partage n'est pas actif (un groupe coché ou un lien de dispo actif).
    assert store.index('rpc(token, "agenda_sharing")') < store.index('"agenda_set_busy"')
    # Le calendrier abonné « Vendredi Party » et les dates de sondage mises par l'app ne comptent jamais.
    assert '"@vendredi-party"' in busy and '"/events/event/"' in busy and 'partyFeedName = "Vendredi Party"' in busy


def test_the_settings_row_and_its_badge():
    settings = read("ios/Party/Settings/SettingsView.swift")
    assert "AgendaRow(agenda: store.agenda) { open(.agenda) }" in settings
    assert 'title: "Agenda"' in settings and '"settings-agenda"' in settings
    assert 'signal: "user:\\(account)"' in read("ios/Party/Agenda/AgendaStore.swift")
    assert "agenda.appBecameActive()" in read("ios/Party/PartyApp.swift")


def test_the_booking_requests_switch():
    assert main.NotificationPatch(booking_requests=False).booking_requests is False
    assert 'eventToggle("booking_requests"' in read("ios/Party/Settings/NotificationSettingsView.swift")
    assert 'case ("booking_requests", let v as Bool): p.bookingRequests = v' in read("ios/Party/Settings/SettingsStore.swift")


def test_the_calendar_sentence_says_what_leaves_the_iphone():
    from tests.test_compliance_1411 import targets, usage_texts
    party = targets()["Party"]
    beta, store = usage_texts(party, "STORE_beta"), usage_texts(party)
    keys = ("NSCalendarsFullAccessUsageDescription", "NSCalendarsUsageDescription")
    # 24.11 : l'Agenda ouvre (BETA) ; la phrase dit l'usage réel (Apple 5.1.1) : lecture des rendez-vous de l'iPhone,
    # dates d'un sondage, et, seulement si on partage ses dispos, les heures prises arrondies, jamais titre, lieu ni notes.
    for line in (beta[k] for k in keys):
        assert "sondage" in line and "Agenda" in line and "dispos" in line
        assert "arrondies" in line and "jamais le titre, le lieu ni les notes" in line
        assert "ne quitte ton iPhone" not in line
    # App App Store (contrôle du 26.11) : pas d'Agenda ; seulement les dates d'un sondage, rien ne quitte l'iPhone.
    for line in (store[k] for k in keys):
        assert "sondage" in line and "Agenda" not in line and "rien ne quitte ton iPhone" in line


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_a_booking_notification_opens_the_request_in_the_agenda():
    shell = ROOT / "app/static/events-shell.js"
    script = ("globalThis.window = { addEventListener() {} }; globalThis.document = { readyState: 'loading', addEventListener() {} }; "
              "import(process.argv[1]).then(() => console.log(JSON.stringify("
              "JSON.parse(process.argv[2]).map((q) => window.PartyEvents.target(new URLSearchParams(q))))))")
    out = subprocess.run(["node", "-e", script, shell.as_uri(), json.dumps([f"tab=events&booking={BOOKING}",
                                                                         "tab=events&booking=../admin"])],
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == [f"/events/agenda?booking={BOOKING}", "/events/"]
    apns = read("supabase/functions/send-push/apns.ts")
    assert "data.kind === 'booking_request' || data.kind === 'booking_cancelled'" in apns
    assert "return `/?tab=events&booking=${data.booking_id}`" in apns
