"""Conformité des Discussions v2 (revue du 18.11.2026 : 🔴 4 et 5, 🟠 7, 8, 10, 11, règles C1-C9) : ce qui se lit dans
les fichiers. Textes obligatoires sur le web ET l'iPhone (CGU et politique de confidentialité, mot pour mot), réglages
« Demandes de message » et « Confirmations de lecture », interrupteur de notification, phrase Contacts, notes de revue.
La base (dm_link, demandes, plafonds) : tests/supabase_live/test_discussions_v2_live.py."""
import re
from pathlib import Path

from tests.test_compliance_1411 import swift_paragraphs, usage_texts, targets, web_paragraphs
from tests.test_compliance_pronos import terms_sections

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def plain(text: str) -> str:
    return text.replace("’", "'")


# Politique de confidentialité (🟠 10, 🔴 4, 🔴 5, C5, C6, C9) : chaque point, web et iPhone.
PRIVACY = [
    # qui peut t'écrire, demandes et leur réglage
    "Qui peut t'écrire", "demande de message : un seul message texte, sans photo, vocal, lien ni numéro",
    "elle n'est jamais prévenue d'un refus", "« Demandes de message »", "de tout membre (par défaut) ou de personne",
    "« … veut t'écrire », sans son contenu",
    # filtre automatique aussi pour les messages directs (DSA art. 14)
    "Le filtre automatique des mots", "messages directs et demandes compris",
    # Root et les groupes (🔴 4)
    "ne sont jamais lus par l'administration ni par l'administrateur principal (Root)",
    "y compris ceux qui existaient déjà, peuvent être lus par l'administrateur principal (Root)",
    # suggestions et recherche (C3)
    "jamais par numéro", "Jamais de personnes prises au hasard sur tout le site",
    # Déjà vu
    "« Déjà vu N fois »", "calculé à chaque affichage à partir des réponses ; rien n'est gardé à part",
    # confirmations de lecture et « écrit… » (C6)
    "« Confirmations de lecture »", "si tu le coupes, tu ne vois plus celles des autres",
    "« écrit… » passe en direct, seulement pendant que tu écris, et n'est jamais enregistré",
    # contacts (🔴 5)
    "Ces personnes te sont aussi proposées quand tu écris un nouveau message.",
    "Les personnes qui ont ton numéro dans leurs contacts peuvent voir que tu es sur Party et t'envoyer une demande de message.",
    # conservation (C9)
    "Messages directs : jusqu'à la suppression du compte de l'un des deux.",
    "Photos et messages vocaux des discussions : 90 jours.",
    "Demandes de message refusées ou supprimées : effacées aussitôt ; ignorées : effacées au bout de 30 jours.",
    # signalement : fichiers copiés, 10 messages, masquage notifié (🔴 2, 🟠 7, 🟠 8)
    "avec sa photo ou son vocal copiés dans un espace réservé aux modérateurs",
    "les 10 messages précédents (texte, auteur, heure) seulement si tu coches « Joindre les 10 messages précédents »",
    "Si un modérateur masque ton contenu, une notification te dit pourquoi et où le contester.",
]

TERMS = [
    "Messages directs et demandes",
    "tu envoies une demande de message : un seul message texte, sans photo, vocal, lien ni numéro de téléphone",
    "Au plus 10 nouvelles demandes par jour et 30 en attente.",
    "Le filtre automatique et ces conditions valent pour tous les messages, messages directs et demandes compris.",
    "ne sont jamais lus par l'administration de Party",
    "Les autres groupes peuvent être lus par l'administrateur principal de Party (Root)",
    "« Joindre les 10 messages précédents »", "avec sa photo ou son vocal",
    "t'envoyer de demande de message",
    "Quand un modérateur masque ton contenu, tu en es prévenu avec le motif et l'adresse pour le contester.",
    "Les signalements sont traités sous 24 heures.",
]


def test_privacy_policy_tells_the_discussions_v2_rules_word_for_word_on_web_and_iphone():
    web, ios = web_paragraphs(), swift_paragraphs()
    assert web == ios
    for text in (" ".join(web), " ".join(ios)):
        for words in PRIVACY:
            assert words in text, words
    assert "title: 'Discussions et messages directs'" in read("web/events/src/app/privacy.tsx")
    assert '("Discussions et messages directs", [' in read("ios/Party/Settings/Account/SignInView.swift")


def test_terms_of_2026_11_18_have_the_direct_messages_section_without_a_new_version():
    web, ios = terms_sections(web=True), ios_terms_after_refus_143()
    assert web == ios
    text = " ".join(t + " " + " ".join(ps) for t, ps in web)
    for words in TERMS:
        assert words in text, words
    assert "TERMS_UPDATED = '25 novembre 2026'" in read("web/events/src/lib/terms.ts")  # pas en prod : complétée


def test_web_privacy_settings_have_message_requests_and_read_receipts():
    src = plain(read("web/events/src/app/settings/privacy.tsx"))
    for words in ("rpc('chat_prefs_get')", "rpc('chat_prefs_set'", "Demandes de message", "label: 'Tout membre'",
                  "label: 'Personne'", "Confirmations de lecture", "tu ne vois plus celles des autres", "discussionsOn"):
        assert words in src, words


def test_web_notification_settings_have_the_message_requests_switch():
    src = plain(read("web/events/src/app/settings/notifications.tsx"))
    assert 'label="Demandes de message"' in src and "update({ message_requests: v })" in src
    assert "message_requests?: boolean" in read("web/events/src/lib/types.ts")
    # Reçue aussi par les Guests (may_receive_push) : jamais cachée aux non-membres.
    assert "message_requests" not in read("web/events/src/lib/notificationPrefs.ts")


def test_iphone_settings_have_the_same_switches():
    privacy = read("ios/Party/Settings/ChatPrefsSettings.swift")
    for words in ('"/api/account/chats/rpc"', '"chat_prefs_get"', '"chat_prefs_set"', '"Demandes de message"',
                  'Text("Tout membre").tag("all")', 'Text("Personne").tag("none")', '"Confirmations de lecture"'):
        assert words in privacy, words
    assert "ChatPrefsSection(store: chatPrefs)" in read("ios/Party/Settings/Account/SignInView.swift")
    assert 'eventToggle("message_requests"' in read("ios/Party/Settings/NotificationSettingsView.swift")
    assert 'case messageRequests = "message_requests"' in read("ios/Party/Settings/NotificationModels.swift")
    assert 'case ("message_requests", let v as Bool): p.messageRequests = v' in read("ios/Party/Settings/SettingsStore.swift")


def test_contacts_permission_says_they_are_also_suggested_for_new_messages():
    text = usage_texts(targets()["Party"])["NSContactsUsageDescription"]
    assert "quand tu écris un nouveau message" in text and "empreinte des numéros" in text and "chiffrée" not in text
    assert text.startswith("Pour")


def test_review_notes_describe_discussions_v2_within_4000_characters():
    notes = read("ios/appstore/review-notes.txt").strip()
    assert len(notes) <= 4000
    section = notes.split("DISCUSSIONS (1.2)", 1)[1].split("\n\n", 1)[0]
    for words in ("message request", "Demandes de message", "Nouveau message", "private group", "not read by admins",
                  "Signaler", "Bloquer", "Apple-test 2", "support@vendrediparty.ch"):
        assert words in section, words
    # Contrôle Apple, tour 5 : faute de place, le mini-profil et les 10 messages joints ne sont plus que dans la partie B.
    part_b = read("docs/app-store/notes-for-review.md").split("## PART B", 1)[1]
    assert "mini-profile" in part_b and "Joindre les 10 messages précédents" in part_b
    assert not re.search(r"\b\d{6}\b", notes)  # jamais un code de compte de démo


def test_app_store_checklist_keeps_the_admin_decisions_in_view():
    checklist = read("docs/app-store/checklist-envoi.md")
    for words in ("Discussions v2 (18.11)", "Deux comptes de démo", "Apple-test 2", "rien de neuf à cocher",
                  "Représentant légal dans l'UE** (décision de l'admin du 19.11)"):
        assert words in checklist, words
    guide = read("docs/app-store/notes-for-review.md")
    assert read("ios/appstore/review-notes.txt").strip() in guide  # partie A = fichier envoyé


def ios_terms_after_refus_143():
    """Refus Apple 1.4.3 (25.11) : web et iPhone (prochain build) disent la même chose, sans « un verre d'eau compte
    toujours » ni « les jeux se jouent en points » (simple précision, même version des CGU)."""
    return terms_sections(web=False)
