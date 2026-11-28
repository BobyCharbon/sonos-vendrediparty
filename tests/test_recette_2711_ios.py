"""Recette du 27.11 (lot 17C), côté iPhone : textes et gestes vérifiés dans le code natif."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ai_consent_sheet_scrolls_and_can_grow():
    sheet = read("ios/Party/Feedback/AIConsentSheet.swift")
    assert "ScrollView {" in sheet and ".presentationDetents([.medium, .large])" in sheet


def test_direct_chat_info_no_longer_says_the_history_stays():
    info = read("ios/Party/Chats/DirectChatInfoView.swift")
    assert "L'historique reste." not in info and "Ses messages sont masqués" in info


def test_pot_report_hidden_for_its_creator_and_settle_reserved_to_the_two_people():
    pot = read("ios/Party/Tricount/TricountGroupView.swift")
    assert "if !Self.createdByMe(g) {" in pot and "if Self.maySettle(t, in: g) {" in pot
    assert "t.from == me || t.to == me" in pot
    assert "creditcard" not in pot and "creditcard" not in read("ios/Party/Tricount/TricountListView.swift")


def test_share_extension_is_dark_whatever_the_iphone_appearance():
    share = read("ios/PartyShare/ShareViewController.swift")
    assert share.count("overrideUserInterfaceStyle = .dark") == 2


def test_audio_session_calls_stay_off_the_main_thread():
    voice = read("ios/Party/Chats/VoiceMessages.swift")
    # Chaque setActive / setCategory passe par la file série AudioSessionQueue (sauf dans useBuiltInMicrophone,
    # elle-même appelée dans cette file).
    body = voice.split("nonisolated static func useBuiltInMicrophone", 1)
    rest = body[0] + body[1].split("\n    }\n", 1)[1]
    for m in re.finditer(r"AVAudioSession\.sharedInstance\(\)\.(setActive|setCategory|recordPermission)", rest):
        # L'appel doit être DANS une fermeture encore ouverte d'un `AudioSessionQueue.run / perform(...)` (accolades
        # comptées depuis le dernier appel à la file ; lot 19 : `perform(within: délai, { … }, late: { … })`).
        start = rest.rfind("AudioSessionQueue.", 0, m.start())
        assert start >= 0, rest[rest.rfind("\n", 0, m.start()):m.start()]
        between = rest[start:m.start()]
        assert between.count("{") > between.count("}"), between[-300:]
