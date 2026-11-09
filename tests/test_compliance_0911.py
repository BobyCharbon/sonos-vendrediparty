"""Exigence Apple du 09.11.2026 (avant l'envoi de 1.0.0) :
- 🟠 8 : l'accord IA se voit, se retire et se redonne dans Réglages › Confidentialité, pour TOUS les comptes ;
- 🟠 9 : politique de confidentialité (IA de développement, historique des avis, identifiant de l'appareil) ;
- 🟠 12 : CGU « aucune tolérance » et « signalements traités sous 24 heures » (web et iPhone) ;
- 🟠 7 : manifeste PrivacyInfo.xcprivacy (identifiant de l'appareil, plus d'audio)."""
import plistlib
import re

from fastapi.testclient import TestClient

from app import ai_feedback, assistant as ai, feedback, main
from tests.test_assistant import FakeAccounts, FakeClient


def read(path: str) -> str:
    return open(path, encoding="utf-8").read()


def assistant_for(tmp_path, perms=("ai.use",)):
    consents = ai_feedback.ConsentBox(tmp_path / "consent.json")
    return ai.Assistant(FakeAccounts(perms=perms), ai.UsageLog(tmp_path / "ai.json"), FakeClient, 3.0, ("CHF",),
                        consents=consents)


# ── 🟠 8 : accord IA dans Réglages › Confidentialité ──
def test_consent_date_is_known_only_while_the_consent_holds(tmp_path):
    consents = ai_feedback.ConsentBox(tmp_path / "consent.json")
    assert consents.accepted_at("acct:u1") is None
    consents.set("acct:u1", True)
    assert isinstance(consents.accepted_at("acct:u1"), float)
    consents.set("acct:u1", False)
    assert consents.accepted_at("acct:u1") is None


def test_an_account_without_the_ai_right_can_still_see_and_withdraw_its_consent(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "assistant", assistant_for(tmp_path, perms=()))
    c = TestClient(main.app)
    given = c.post("/api/account/ai/consent", json={"token": "ok", "accept": True}).json()
    assert given["consent"] == "accepted" and given["consent_at"] > 0
    status = c.post("/api/account/ai/status", json={"token": "ok"}).json()
    assert status["consent"] == "accepted" and status["consent_at"] == given["consent_at"]
    withdrawn = c.post("/api/account/ai/consent", json={"token": "ok", "accept": False}).json()
    assert withdrawn == {**withdrawn, "consent": "declined", "consent_at": None}


def test_privacy_settings_show_the_ai_consent_on_the_web_and_the_iphone():
    web = read("web/events/src/app/settings/privacy.tsx")
    assert "IA de Party" in web and "Retirer mon accord" in web and "setAiConsent" in web
    lib = read("web/events/src/lib/aiConsent.ts")
    assert "/api/account/ai/status" in lib and "/api/account/ai/consent" in lib
    ios_view = read("ios/Party/Settings/Account/SignInView.swift")
    assert "AIConsentSection(store: moderation)" in ios_view
    ios = read("ios/Party/Settings/Moderation/AIConsentSettings.swift")
    assert "Retirer mon accord" in ios and "Donner mon accord" in ios and "AIConsentSheet(copy: .settings)" in ios


def test_the_web_consent_text_is_the_sheet_text():
    swift = read("ios/Party/Feedback/FeedbackAI.swift")
    sheet = re.search(r'static let consentText = "(.*?)"\n', swift).group(1)
    web = re.search(r"AI_CONSENT_TEXT = '(.*?)';", read("web/events/src/lib/aiConsent.ts")).group(1)
    assert web.replace("’", "'").startswith(sheet)


def test_withdrawing_points_to_confidentialite_everywhere():
    for path in ("web/events/src/app/privacy.tsx", "ios/Party/Feedback/FeedbackAI.swift", "app/static/index.html",
                 "ios/Party/Settings/Account/SignInView.swift"):
        text = read(path)
        assert "Réglages › Ton avis ;" not in text and "dans Réglages › Ton avis." not in text, path
        assert "Réglages › Confidentialité" in text, path


# ── 🟠 9 : politique de confidentialité ──
def test_privacy_policy_tells_the_dev_ai_the_edit_history_and_the_device_id():
    page = read("web/events/src/app/privacy.tsx")
    assert "9 novembre 2026" in page
    assert "GitHub" in page and "que si tu as donné ton accord pour l’IA" in page and "sans ton prénom" in page
    assert feedback.MAX_EDITS == 20 and "au plus les 20 dernières" in page
    assert "Identifiant de l’appareil" in page and "jeton de notifications" in page and "Wallet" in page


def test_iphone_privacy_text_is_the_web_text():
    swift = read("ios/Party/Settings/Account/SignInView.swift")
    web = read("web/events/src/app/privacy.tsx")
    assert 'static let updated = "9 novembre 2026"' in swift and "const UPDATED = '9 novembre 2026'" in web
    for title in re.findall(r"title: '([^']*)',", web):
        assert f'("{title.replace("’", chr(39))}", [' in swift, title
    assert "GitHub" in swift and "au plus les 20 dernières" in swift and "19 octobre" not in swift


# ── 🟠 12 : CGU ──
def test_terms_say_zero_tolerance_and_24_hours_without_a_new_version():
    web = read("web/events/src/lib/terms.ts").replace("’", "'")
    ios = read("ios/Party/Settings/Moderation/TermsView.swift")
    for text in (web, ios):
        assert "Aucune tolérance pour les contenus choquants ou les utilisateurs abusifs" in text
        assert "Les signalements sont traités sous 24 heures." in text
    assert "TERMS_UPDATED = '4 novembre 2026'" in web and 'static let updated = "4 novembre 2026"' in ios


# ── 🟠 7 : manifeste de confidentialité ──
def test_privacy_manifest_matches_the_app_store_app():
    with open("ios/Party/PrivacyInfo.xcprivacy", "rb") as f:
        manifest = plistlib.load(f)
    assert manifest["NSPrivacyTracking"] is False
    entries = manifest["NSPrivacyCollectedDataTypes"]
    types = {e["NSPrivacyCollectedDataType"] for e in entries}
    assert "NSPrivacyCollectedDataTypeDeviceID" in types
    assert "NSPrivacyCollectedDataTypeGameplayContent" in types  # stats de jeux gardées avec le compte
    assert "NSPrivacyCollectedDataTypePurchaseHistory" not in types  # aucun achat dans l'app
    assert "NSPrivacyCollectedDataTypeAudioData" not in types  # dictée par Apple ; vocaux : Discussions masquées
    assert {"NSPrivacyCollectedDataTypeOtherFinancialInfo", "NSPrivacyCollectedDataTypePhoneNumber",
            "NSPrivacyCollectedDataTypeOtherUserContent"} <= types
    assert all(e["NSPrivacyCollectedDataTypeLinked"] and not e["NSPrivacyCollectedDataTypeTracking"] for e in entries)
