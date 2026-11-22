"""Discussions : son et photos (avis c54e83dc5130 et 48a0eefd44ce, 22.11.2026).

1. Ouvrir l'onglet Discussions ou une conversation ne touche jamais à la session audio d'iOS : l'activer
   (ancien « warmUp » du micro) coupait la musique en cours (Spotify…). Elle ne s'ouvre qu'au toucher du micro ou
   de la lecture d'un vocal, et se rend ensuite avec .notifyOthersOnDeactivation (la musique reprend).
2. Toucher une photo d'une bulle (groupe, événement, à deux ; web et iPhone) l'ouvre en plein écran avec « Enregistrer ».
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHATS = ROOT / "ios/Party/Chats"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def function_body(code: str, signature: str) -> str:
    start = code.index(signature)
    depth, i = 0, code.index("{", start)
    for j in range(i, len(code)):
        depth += {"{": 1, "}": -1}.get(code[j], 0)
        if depth == 0:
            return code[i:j + 1]
    raise AssertionError(signature)


def test_no_audio_session_is_activated_when_a_chat_opens():
    voice = read("ios/Party/Chats/VoiceMessages.swift")
    assert "func warmUp" not in voice
    # Seuls le micro (start → useBuiltInMicrophone) et la lecture d'un vocal (toggle) activent la session.
    active = [m.start() for m in re.finditer(r"setActive\(true", voice)]
    allowed = [function_body(voice, "static func useBuiltInMicrophone"), function_body(voice, "func toggle(id: String")]
    assert active and all(any(voice[a:a + 20] in body for body in allowed) for a in active)
    assert "useBuiltInMicrophone" in function_body(voice, "func start() async")
    # Aucun écran des Discussions ne touche lui-même à la session audio ni ne prépare le micro.
    for swift in CHATS.rglob("*.swift"):
        if swift.name == "VoiceMessages.swift":
            continue
        code = swift.read_text(encoding="utf-8")
        assert "AVAudioSession" not in code and "warmUp" not in code and "useBuiltInMicrophone" not in code, swift.name


def test_the_music_resumes_after_a_voice_message():
    voice = read("ios/Party/Chats/VoiceMessages.swift")
    stop = function_body(voice, "func stop(release: Bool = true)")
    assert "setActive(false, options: .notifyOthersOnDeactivation)" in stop
    assert "setActive(false, options: .notifyOthersOnDeactivation)" in function_body(voice, "func stop(send: Bool)")


def test_the_web_chat_never_autoplays_media():
    for path in ["web/events/src/components/ChatBubble.tsx", "web/events/src/components/GroupChat.tsx"]:
        code = read(path)
        assert "autoPlay" not in code and "autoplay" not in code
        assert "preload=\"auto\"" not in code


def test_touching_a_chat_photo_opens_it_full_screen_with_save_on_iphone():
    conv = read("ios/Party/Chats/ConversationView.swift")
    assert ".fullScreenCover(item: $viewingPhoto) { EventChatPhotoViewer(item: $0) }" in conv
    # Bulle et annonce : le toucher de la photo ouvre la visionneuse.
    assert conv.count(".onTapGesture { onPhoto?() }") == 2
    assert conv.count("onPhoto: { showPhoto(m) }") == 2
    viewer = read("ios/Party/Chats/EventChatMediaView.swift")
    assert "PHAssetChangeRequest.creationRequestForAsset" in viewer and 'requestAuthorization(for: .addOnly)' in viewer
    assert '"Enregistrer"' in viewer and "ShareLink(item: Image(uiImage: image)" in viewer
    assert "NSPhotoLibraryAddUsageDescription" in read("ios/project.yml")


def test_touching_a_chat_photo_opens_it_full_screen_with_save_on_the_web():
    bubble = read("web/events/src/components/ChatBubble.tsx")
    assert bubble.count("photoTap(<Image") == 2  # bulle et annonce
    assert "<PhotoViewer" in bubble and " save " in bubble
    viewer = read("web/events/src/components/ProfilePhotoViewer.tsx")
    assert 'testID="chat-photo-save"' in viewer and "nav.share({ files: [file] })" in viewer
