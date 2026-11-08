"""Onglet « Ton avis » de bout en bout : l'invité envoie, l'admin voit et traite."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, FakeSupabase, Phone, Server, sign_in  # noqa: E402


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


def open_feedback(guest):
    """« Ton avis » : une page des Réglages depuis le 4.11 (l'onglet Zicou a pris sa place dans la barre). La ligne
    des Réglages du module la demande à la page (party-events:open-tab, testé dans test_zicou_home)."""
    guest.page.evaluate("showTab('feedback')")
    expect(guest.page.locator('[data-view="feedback"]')).to_be_visible()


def test_guest_feedback_reaches_admin(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Admin", "desktop")
    try:
        guest.page.set_viewport_size({"width": 360, "height": 740})
        guest.page.goto("/")
        sign_in(guest, "jeton-de-test-guest-plus-0001")  # « Ton avis » : Guest+ et au-dessus
        open_feedback(guest)
        assert guest.page.evaluate("document.documentElement.scrollWidth <= innerWidth")  # 4 onglets tiennent
        guest.page.locator('[data-fb-kind="bug"]').tap()
        guest.page.locator("#fbText").fill("Le joystick est trop petit sur mon iPhone")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Le joystick est trop petit")
        guest.shot("feedback_guest")
        boss.page.goto("/admin")
        boss.page.locator("#pin").fill(ADMIN_PIN)
        boss.page.locator("#pin").press("Enter")
        expect(boss.page.locator("#fbBadge")).to_have_text("1")
        boss.page.locator('button[data-tab="feedback"]').click()
        expect(boss.page.locator("#fbList")).to_contain_text("Le joystick est trop petit")
        expect(boss.page.locator("#fbList")).to_contain_text("Bug")
        boss.shot("feedback_admin")
        boss.page.locator("#fbList [data-fb-status]").first.select_option("done")
        expect(boss.page.locator("#fbList")).to_contain_text("Rien à faire de ton côté")
        guest.page.locator('button[data-tab="music"]').tap()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("✅ Terminé")
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()


def act_as_account_admin(phone):
    """Compte Party admin connecté dans l'app : session admin (même cookie que /api/account/admin) + compte admin.
    La vérification du compte auprès de Supabase est testée dans test_accounts.py."""
    phone.page.request.post(f"{phone.server.url}/api/admin/login", data={"pin": ADMIN_PIN})
    phone.page.evaluate("account = { name: 'Boss', admin: true }; adminSession = true; fbSyncRole();")


def test_account_admin_manages_feedback_from_the_app_tab_and_guest_is_told(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Boss")
    try:
        guest.page.goto("/")
        sign_in(guest, "jeton-de-test-guest-plus-0001")
        open_feedback(guest)
        guest.page.locator("#fbText").fill("Un mode équipe au Quiz, avec deux camps")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Envoyé")

        boss.page.goto("/")
        act_as_account_admin(boss)
        # Réglages › Retours (plus besoin de /admin) : la pastille des avis à traiter est sur l'onglet Réglages.
        expect(boss.page.locator("#hostBadge")).to_have_text("1")
        boss.page.wait_for_function("fbInfo().label === 'Retours' && fbInfo().badge === '1'")
        open_feedback(boss)
        expect(boss.page.locator("#fbScreenTitle")).to_have_text("Retours")
        expect(boss.page.locator("#fbAdmin #fbList")).to_contain_text("Un mode équipe au Quiz")
        assert boss.page.locator("#fbGuest").is_hidden()

        # 🔧 En cours : l'invité voit « en cours de correction ».
        boss.page.locator("#fbAdmin [data-fb-status]").select_option("progress")
        expect(boss.page.locator("#hostBadge")).to_be_hidden()
        guest.page.reload()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("En cours de correction")

        # ✅ Terminé avec un mot : l'invité a une pastille, voit le statut et le mot, puis la pastille s'éteint.
        boss.page.locator('#fbAdmin [data-fb-filter="claude"]').tap()  # « Pour Claude » : prêt, en cours, chez Claude
        boss.page.locator("#fbAdmin [data-fb-edit]").tap()
        boss.page.locator("#fbAdmin [data-fb-reply]").fill("Ajouté au Quiz, merci !")
        boss.page.locator('#fbAdmin .fb-edit [data-fb="done"]').tap()
        expect(boss.page.locator("#fbAdmin")).to_contain_text("Aucun retour")  # vue « Pour Claude » vide
        guest.page.locator('#tabs button[data-tab="music"]').tap()
        guest.page.reload()
        expect(guest.page.locator("#hostBadge")).to_have_text("1")  # pastille de Réglages (ligne « Ton avis »)
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("✅ Terminé")
        expect(guest.page.locator("#fbMine")).to_contain_text("Ajouté au Quiz, merci !")
        expect(guest.page.locator("#hostBadge")).to_be_hidden()

        # L'admin peut toujours envoyer son propre avis.
        boss.page.locator('[data-fb-view="mine"]').tap()
        expect(boss.page.locator("#fbForm")).to_be_visible()
        assert boss.page.locator("#fbAdmin").is_hidden()
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()


def test_feedback_tab_is_only_for_guest_plus_and_above(browser, server):
    """Non connecté ou Guest : pas de ligne « Ton avis », et le serveur refuse l'envoi ; Guest+ : la ligne revient."""
    phone = Phone(browser, server, "Tom")
    allowed = lambda: phone.page.evaluate("fbInfo().allowed")  # noqa: E731  (ligne des Réglages)
    try:
        phone.page.goto("/")
        assert phone.page.locator('#tabs button[data-tab="feedback"]').count() == 0   # plus dans la barre (4.11)
        assert not allowed()  # non connecté
        refused = phone.page.request.post(f"{server.url}/api/feedback", data={
            "guest_id": phone.gid, "name": "Tom", "kind": "idea", "text": "Un mode équipe au Quiz, avec deux camps"})
        assert refused.status == 403
        sign_in(phone, "jeton-de-test-guest-0001")
        phone.page.wait_for_function("account && account.name === 'Tom'")
        assert not allowed()  # Guest connecté : toujours pas
        phone.page.evaluate("showTab('feedback')")
        assert phone.page.evaluate("document.body.dataset.tab") != "feedback"   # lien profond refusé
        sign_in(phone, "jeton-de-test-guest-plus-0001")
        phone.page.wait_for_function("fbInfo().allowed")  # Guest+ : la ligne apparaît
        phone.page.evaluate("showTab('feedback')")
        phone.page.locator("#fbText").fill("Trop court")
        phone.page.locator("#fbSend").tap()
        expect(phone.page.locator("#fbMine")).to_be_hidden()  # moins de 30 caractères : rien d'envoyé
        assert not phone.errors and not server.errors(), phone.errors
    finally:
        phone.close()


def test_admin_creates_classifies_filters_and_discusses(browser, server):
    """Avis 834064fae819 / eaf018fd3967 : l'admin crée un avis déjà classé (statut, priorité, zone…), le retrouve
    par les vues, filtres et la recherche, et échange avec Claude dans le fil ; l'invité ne voit jamais ces statuts."""
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Boss")
    try:
        guest.page.goto("/")
        sign_in(guest, "jeton-de-test-guest-plus-0001")
        open_feedback(guest)
        guest.page.locator("#fbText").fill("Un mode équipe au Quiz, avec deux camps")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Envoyé")

        boss.page.goto("/")
        act_as_account_admin(boss)
        open_feedback(boss)
        admin = boss.page.locator("#fbAdmin")
        expect(admin.locator("#fbList")).to_contain_text("Un mode équipe au Quiz")
        expect(admin.locator('[data-fb-filter="mine"]')).to_contain_text("À moi")

        # ＋ Nouvel avis, classé dès la création.
        admin.locator("[data-fb-newopen]").tap()
        form = admin.locator("[data-fb-new]")
        form.locator("[data-fb-newtext]").fill("Retravailler l'écran de fin du Quiz")
        form.locator('[data-fbc="status"]').select_option("think")
        form.locator('[data-fbc="priority"]').select_option("high")
        form.locator('[data-fbc="area"]').select_option("games")
        form.locator('[data-fbc-platform="iphone"]').check()
        form.locator('[data-fbc="effort"]').select_option("m")
        form.locator('[data-fbc="tags"]').fill("quiz, fin de partie")
        form.locator('button[type="submit"]').tap()
        expect(admin.locator("[data-fb-new]")).to_have_count(0)
        admin.locator('[data-fb-filter="thinking"]').tap()
        row = admin.locator(".fb-item", has_text="Retravailler l'écran de fin")
        expect(row).to_contain_text("Idée à mûrir")
        expect(row).to_contain_text("Haute")
        expect(row).to_contain_text("#quiz")
        expect(row).to_contain_text("iPhone")

        # Filtres fins, recherche, tri, regroupement.
        admin.locator('[data-fb-filter="all"]').tap()
        admin.locator(".fb-filters summary").tap()
        admin.locator('[data-fb-fine="area"]').select_option("games")
        expect(admin.locator(".fb-item")).to_have_count(1)
        admin.locator('[data-fb-fine="area"]').select_option("")
        admin.locator("[data-fb-search]").fill("deux camps")
        expect(admin.locator(".fb-item")).to_have_count(1)
        expect(admin.locator(".fb-item")).to_contain_text("Un mode équipe")
        admin.locator("[data-fb-search]").fill("")
        admin.locator("[data-fb-group]").check()
        expect(admin.locator(".fb-group")).to_have_count(2)  # Jeux, et la zone de l'avis de l'invité
        admin.locator("[data-fb-group]").uncheck()
        admin.locator('[data-fb-sortsel]').select_option("priority")
        expect(admin.locator(".fb-item").first).to_contain_text("Retravailler")

        # Fil admin ↔ Claude et statut « questions à poser » sur l'avis de l'invité.
        guest_row = admin.locator(".fb-item", has_text="Un mode équipe")
        guest_row.locator("[data-fb-status]").select_option("questions")
        guest_row = admin.locator(".fb-item", has_text="Un mode équipe")
        guest_row.locator("[data-fb-edit]").tap()
        guest_row.locator("[data-fb-comment]").fill("Combien d'équipes au maximum ?")
        guest_row.locator("[data-fb-send-comment]").tap()
        expect(admin.locator(".fb-thread")).to_contain_text("Combien d'équipes")
        expect(boss.page.locator("#hostBadge")).to_have_text("1")  # questions à poser : à moi d'agir
        guest.page.reload()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("Envoyé")  # jamais « Questions à poser »
        expect(guest.page.locator("#fbMine")).not_to_contain_text("Questions")

        # « Mon avis » de l'admin : mêmes champs de classement.
        boss.page.locator('[data-fb-view="mine"]').tap()
        expect(boss.page.locator('#fbClassify [data-fbc="status"]')).to_be_visible()
        boss.page.locator("#fbText").fill("Bloqué : attendre iOS 27")
        boss.page.locator('#fbClassify [data-fbc="status"]').select_option("blocked")
        boss.page.locator("#fbSend").tap()
        expect(boss.page.locator("#fbMine")).to_contain_text("Bloqué : attendre iOS 27")
        boss.page.locator('[data-fb-view="admin"]').tap()
        admin.locator('[data-fb-filter="thinking"]').tap()
        expect(admin.locator(".fb-item", has_text="attendre iOS 27")).to_contain_text("Bloqué / en attente")
        admin.locator(".fb-item").first.scroll_into_view_if_needed()
        assert boss.page.evaluate("document.documentElement.scrollWidth <= innerWidth")  # rien ne déborde sur iPhone
        boss.shot("feedback_triage")
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()


def test_the_author_rewrites_his_feedback_and_the_admin_sees_the_new_text(browser, server):
    """Retour de l'admin (08.11) : l'auteur modifie son avis à tout moment ; « modifié le … » s'affiche, l'admin voit le
    nouveau texte ; un avis terminé n'a plus de bouton « Modifier »."""
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Admin", "desktop")
    try:
        guest.page.goto("/")
        sign_in(guest, "jeton-de-test-guest-plus-0001")
        open_feedback(guest)
        guest.page.locator("#fbText").fill("Le joystick est trop petit sur mon iPhone")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Le joystick est trop petit")
        guest.page.locator("#fbMine [data-fb-edit]").tap()
        box = guest.page.locator("#fbMine textarea")
        expect(box).to_have_value("Le joystick est trop petit sur mon iPhone")
        box.fill("Le joystick est trop petit sur mon iPhone, surtout en mode paysage")
        guest.page.locator("#fbMine [data-fb-save]").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("surtout en mode paysage")
        expect(guest.page.locator("#fbMine .fb-edited")).to_contain_text("modifié le")
        guest.shot("feedback_modifie")
        boss.page.goto("/admin")
        boss.page.locator("#pin").fill(ADMIN_PIN)
        boss.page.locator("#pin").press("Enter")
        boss.page.locator('button[data-tab="feedback"]').click()
        expect(boss.page.locator("#fbList")).to_contain_text("surtout en mode paysage")
        boss.page.locator("#fbList [data-fb-status]").first.select_option("done")
        expect(boss.page.locator("#fbList")).to_contain_text("Rien à faire de ton côté")
        guest.page.locator('button[data-tab="music"]').tap()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("✅ Terminé")
        expect(guest.page.locator("#fbMine [data-fb-edit]")).to_have_count(0)
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()
