"""Campagne 2, agent 10 : accès public, partage et robustesse du module Événements (base de TEST uniquement).

Événements « [C2-10] … » créés par Bot Olga directement dans la base de TEST (sans annonce : notify_on_publish = false),
puis parcourus dans de vrais navigateurs (Playwright tactile, iPhone et Android) par des bots :
- « Bot Noé » / « Bot Nora » (41790000116 / 117) : numéros neufs, aucun compte au départ (première connexion) ;
- Bot Victor (deux appareils), Bot Vera, Bot Olga.
Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.run ap_setup ap_anonyme ap_premiere ap_deux_appareils \
        ap_reseau ap_double ap_session ap_perf ap_menage"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from tests.bots import flows as f
from tests.bots.bench import OUT, Phone, anomaly, load_state, save_state
from tests.bots.common import BY_KEY, Bot, OTP, q, sql

# Relance : AP_PREFIX="[R-10]" et AP_PHONES=<Noé>,<Nora> (numéros neufs, ajoutés à sms_test_otp par ap_numeros).
PREFIX = os.environ.get("AP_PREFIX", "[C2-10]")
_PHONES = (os.environ.get("AP_PHONES") or "41790000116,41790000117").split(",")
NEW_BOTS = {
    "noe": Bot("noe", _PHONES[0], "Noé", "Nouveau", "none", "iphone"),
    "nora": Bot("nora", _PHONES[1], "Nora", "Nouvelle", "none", "android"),
}
PERF_COUNT = 32


def _uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def _at(days: int, hour: int = 19) -> str:
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d.isoformat()


def _insert_event(title: str, days: int, *, public: bool, status: str = "published", group: str | None = "Bots",
                  extra: str = "") -> str:
    olga = _uid("orga1")
    row = sql(f"""insert into public.events (title, description, created_by, status, starts_at, location_name,
                   visibility, public_link, notify_on_publish, max_participants, forum_enabled)
                  values ({q(title)}, 'Événement de test des bots (campagne 2, agent 10). Ignorer.', {q(olga)}, {q(status)},
                   {q(_at(days))}, 'Salle des bots, Vevey', {q('all' if public else 'invited')}, {str(public).lower()},
                   false, 20, true)
                  returning id""")[0]["id"]
    if group:
        sql(f"""insert into public.event_groups (event_id, group_id)
                select {q(row)}, id from public.member_groups where name = {q(group)} on conflict do nothing""")
    return row


def P(browser, key: str, origin: str, phase: str, fresh: bool = False) -> Phone:
    bot = NEW_BOTS.get(key) or BY_KEY[key]
    if fresh:
        (OUT / bot.key / "storage.json").unlink(missing_ok=True)
    return Phone(browser, bot, origin, phase)


def api_session(phone: str) -> dict:
    """Session complète (comme supabase-js la garde) obtenue par l'API : un vrai second appareil, sans l'écran."""
    from tests.bots.common import TEST_URL, publishable_key
    base = {"apikey": publishable_key(), "Content-Type": "application/json"}
    for _ in range(8):
        sent = httpx.post(f"{TEST_URL}/auth/v1/otp", headers=base, json={"phone": phone}, timeout=60)
        if sent.status_code == 200:
            r = httpx.post(f"{TEST_URL}/auth/v1/verify", headers=base, json={"type": "sms", "phone": phone, "token": OTP}, timeout=60)
            if r.status_code == 200:
                return r.json()
        time.sleep(35)
    raise RuntimeError(f"pas de session pour {phone} : {sent.status_code} {sent.text[:200]}")


def inject(p: Phone, phone: str) -> None:
    """Connecte le navigateur avec une session neuve (clé de stockage de supabase-js)."""
    from tests.bots.common import TEST_REF
    s = api_session(phone)
    p.log("session injectée (connexion par l'API)")
    p.ctx.add_init_script(f"try {{ if (!sessionStorage.getItem('bots-injected')) {{ sessionStorage.setItem('bots-injected', '1'); "
                          f"localStorage.setItem('sb-{TEST_REF}-auth-token', {json.dumps(json.dumps(s))}); }} }} catch (e) {{}}")


def P2(browser, key: str, origin: str, phase: str, device: str) -> Phone:
    """Second appareil du même bot (dossier <bot>-<appareil>)."""
    b = BY_KEY[key]
    return Phone(browser, Bot(f"{b.key}-{device}", b.phone, b.first, b.last, b.role, device, b.groups), origin, phase)


def _rsvp_rows(event: str, phone: str) -> list:
    return sql(f"""select r.status, r.waitlisted, r.plus_ones, r.updated_at from public.rsvps r
                   join public.profiles p on p.id = r.user_id where r.event_id = {q(event)} and p.phone = {q(phone)}""") or []


def _url_trail(p: Phone, seconds: int) -> list[str]:
    """Adresses successives pendant quelques secondes (redirections après connexion)."""
    trail: list[str] = []
    end = time.time() + seconds
    while time.time() < end:
        if not trail or trail[-1] != p.page.url:
            trail.append(p.page.url.replace(p.origin, ""))
        p.page.wait_for_timeout(400)
    return trail


def _radio(p: Phone, choice: str):
    return p.page.get_by_role("radiogroup").get_by_role("button", name=re.compile(rf"^{choice}")).first


# ── Préparation ─────────────────────────────────────────────────────────────────────────────────────────────────

def phase_ap_setup(browser, origin, only):
    """Tout en une requête (l'API de gestion limite le débit quand 10 agents tournent)."""
    olga = _uid("orga1")
    specs = [("Apéro public", 6, True, "published", False), ("Public annulé", 8, True, "cancelled", False),
             ("Soirée Bots (robustesse)", 4, False, "published", True)]
    specs += [(f"Perf {i:02d}", 10 + i, False, "published", True) for i in range(PERF_COUNT)]
    values = ",".join(f"({q(PREFIX + ' ' + t)}, {q(_at(d))}, {q('all' if pub else 'invited')}, {str(pub).lower()}, "
                      f"{q(stt)}, {str(g).lower()})" for t, d, pub, stt, g in specs)
    rows = sql(f"""delete from public.events where title like {q(PREFIX + '%')};
        with spec(title, starts, vis, pub, st, grp) as (values {values}),
        ins as (insert into public.events (title, description, created_by, status, starts_at, location_name, visibility,
                public_link, notify_on_publish, max_participants, forum_enabled)
                select title, 'Événement de test des bots (campagne 2, agent 10). Ignorer.', {q(olga)}, st::event_status,
                       starts::timestamptz, 'Salle des bots, Vevey', vis::event_visibility, pub, false, 20, true from spec
                returning id, title),
        g as (insert into public.event_groups (event_id, group_id)
              select ins.id, mg.id from ins join spec using (title), public.member_groups mg
              where spec.grp and mg.name = 'Bots' returning 1)
        select ins.id, ins.title, (select count(*) from g) groups from ins order by title""")
    by = {r["title"][len(PREFIX) + 1:]: r["id"] for r in rows}
    save_state(ap_public=by["Apéro public"], ap_public_cancel=by["Public annulé"], ap_invited=by["Soirée Bots (robustesse)"],
               ap_perf=[v for k, v in by.items() if k.startswith("Perf")])
    print(len(rows), "événements ;", rows[0]["groups"], "liens de groupe")


# ── 1. Lien public sans compte, aperçus ────────────────────────────────────────────────────────────────────────

OG = re.compile(r'<meta[^>]+property="(og:[a-z:_]+)"[^>]+content="([^"]*)"')


def og_tags(origin: str, path: str) -> dict:
    html = httpx.get(origin + path, headers={"User-Agent": "WhatsApp/2.23 facebookexternalhit/1.1"}, timeout=20).text
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    return {"title": title.group(1).strip() if title else None, **dict(OG.findall(html))}


def phase_ap_apercus(browser, origin, only):
    st = load_state()
    out = {}
    for name, path in (("événement public", f"/events/event/{st['ap_public']}"), ("partage", f"/events/share/{st['ap_public']}"),
                       ("événement sur invitation", f"/events/event/{st['ap_invited']}"), ("module", "/events/")):
        out[name] = og_tags(origin, path)
    cover = "https://ewromqfsmcqsthftyhzm.supabase.co/storage/v1/object/public/bots/affiche-r10.jpg"
    sql(f"update public.events set cover_url = {q(cover)} where id = {q(st['ap_public'])}")
    out["public avec affiche"] = og_tags(origin, f"/events/event/{st['ap_public']}")
    out["partage Party avec affiche"] = og_tags(origin, f"/?tab=events&event={st['ap_public']}")
    out["public annulé"] = og_tags(origin, f"/events/share/{st['ap_public_cancel']}")
    sql(f"update public.events set cover_url = null where id = {q(st['ap_public'])}")
    for k in ("public avec affiche", "partage Party avec affiche"):
        if out[k].get("og:image") != cover:
            anomaly("banc", "🟠", f"Aperçu ({k}) : l'affiche de l'événement n'est pas l'image de l'aperçu",
                    json.dumps(out[k], ensure_ascii=False))
    (OUT / "apercus.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    pub = out["événement public"]
    if PREFIX not in (pub.get("og:title") or ""):
        anomaly("banc", "🟠", "Aperçu du lien public d'un événement : ni titre ni date de l'événement (balises Open Graph génériques)",
                json.dumps(pub, ensure_ascii=False))
    if out["événement sur invitation"].get("og:title", "").find(PREFIX) >= 0:
        anomaly("banc", "🔴", "Aperçu d'un événement SUR INVITATION : le titre fuite dans les balises", json.dumps(out["événement sur invitation"]))


def phase_ap_anonyme(browser, origin, only):
    """Visiteur sans compte : lit le lien public, voit le signalement par e-mail, l'annulé, un lien faux."""
    st = load_state()
    p = P(browser, "nora", origin, "anonyme", fresh=True)
    page = p.page
    try:
        p.goto(f"/events/event/{st['ap_public']}")
        page.wait_for_timeout(4000)
        p.log(f"adresse après ouverture : {page.url}")
        if "/share/" not in page.url:
            p.flag("🔴", "lien public ouvert sans compte : pas de page publique", page.url)
        p.expect_or_flag(page.get_by_text(f"{PREFIX} Apéro public"), "titre de l'événement public", "🔴")
        p.expect_or_flag(page.get_by_text("Lien public"), "pastille « Lien public »", "🟡")
        p.shot("public-sans-compte")
        p.dump("public-sans-compte")
        p.scroll_to_bottom("page publique")
        cut = p.check_texts_cut("page publique")
        if cut:
            p.flag("🟡", "page publique : textes coupés", "; ".join(cut))
        with p.step("Signaler par e-mail (sans compte)"):
            link = page.get_by_role("link", name="Signaler cet événement par e-mail")
            p.see(link, "lien Signaler par e-mail")
            mail = []
            page.route("mailto:*", lambda r: (mail.append(r.request.url), r.abort()))
            page.context.on("page", lambda pg: mail.append(pg.url))
            with page.expect_request(lambda r: r.url.startswith("mailto:"), timeout=4000) as req:
                p.tap(link, "Signaler cet événement par e-mail")
            p.log(f"mailto ouvert : {req.value.url}")
            if st["ap_public"] not in req.value.url:
                p.flag("🟡", "Signaler par e-mail : l'identifiant de l'événement manque dans l'objet", req.value.url)
        with p.step("événement public annulé"):
            p.goto(f"/events/event/{st['ap_public_cancel']}")
            page.wait_for_timeout(3500)
            p.expect_or_flag(page.get_by_text("Annulé", exact=True), "pastille « Annulé » (lien public sans compte)")
            p.shot("public-annule")
            if page.get_by_role("button", name="Se connecter pour répondre").count():
                p.flag("🟡", "événement annulé : « Se connecter pour répondre » proposé quand même au visiteur")
        with p.step("événement sur invitation ouvert sans compte"):
            p.goto(f"/events/event/{st['ap_invited']}")
            page.wait_for_timeout(3500)
            p.shot("invitation-sans-compte")
            if page.get_by_text(f"{PREFIX} Soirée Bots").count():
                p.flag("🔴", "événement sur invitation lisible sans compte")
            p.expect_or_flag(page.get_by_text("Lien indisponible"), "« Lien indisponible » pour un événement non public", "🟡")
        with p.step("lien faux / inexistant"):
            for bad in ("/events/event/00000000-0000-0000-0000-000000000000", "/events/share/pas-un-uuid",
                        "/events/event/abc", "/events/n-importe-quoi"):
                p.goto(bad)
                page.wait_for_timeout(3000)
                p.shot("lien-faux")
                body = page.locator("body").inner_text()[:200].replace("\n", " | ")
                p.log(f"{bad} → {page.url} : {body}")
                if not body.strip():
                    p.flag("🟠", f"lien faux {bad} : page blanche")
        with p.step("Conditions et Confidentialité sans compte"):
            for path, word in (("/events/terms", "Conditions"), ("/events/privacy", "onfidentialit")):
                p.goto(path)
                page.wait_for_timeout(2500)
                if not p.see(page.get_by_text(re.compile(word)).first, path, 6000):
                    p.flag("🟠", f"{path} illisible sans compte")
    finally:
        p.close()


def phase_ap_intent(browser, origin, only):
    """Visiteur : ouvre le lien public A, puis un lien /events/share/B (ou un autre lien) dans le même onglet."""
    st = load_state()
    p = P(browser, "nora", origin, "intention", fresh=True)
    page = p.page
    page.add_init_script("window.__opened = []; window.open = (u) => { window.__opened.push(String(u)); return null; };")
    try:
        p.goto(f"/events/event/{st['ap_public']}")
        page.wait_for_timeout(4000)
        p.log(f"A ouvert : {page.url}")
        with p.step("Signaler par e-mail : adresse ouverte"):
            p.tap(page.get_by_role("link", name="Signaler cet événement par e-mail"), "Signaler cet événement par e-mail")
            page.wait_for_timeout(1500)
            opened = page.evaluate("window.__opened")
            p.log(f"ouvert : {opened} ; adresse : {page.url}")
            if not any(u.startswith("mailto:") for u in opened) and not page.url.startswith("mailto:"):
                p.flag("🟠", "Signaler par e-mail : aucun e-mail ne s'ouvre", str(opened))
        for target in (f"/events/share/{st['ap_public_cancel']}", f"/events/invite/00000000-0000-0000-0000-000000000000",
                       "/events/terms"):
            p.goto(target)
            page.wait_for_timeout(4500)
            p.log(f"{target} → {page.url}")
            p.shot("intention")
            if st["ap_public"] in page.url and st["ap_public"] not in target:
                p.flag("🔴", f"lien {target} : le visiteur est renvoyé sur l'événement ouvert AVANT ({st['ap_public']})", page.url)
    finally:
        p.close()


# ── 2. Première connexion par le lien public jusqu'à la réponse ────────────────────────────────────────────────

def _sign_in_here(p: Phone, bot: Bot) -> None:
    page = p.page
    field = page.get_by_label("Ton numéro de téléphone", exact=True)
    field.wait_for(state="visible", timeout=15000)
    p.type(field, "0" + bot.phone[2:], "le numéro")
    p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
    code = page.get_by_placeholder("123456", exact=True)
    try:
        code.wait_for(state="visible", timeout=60000)
    except Exception:
        p.shot("code-pas-arrive")
        msg = page.locator("body").inner_text()[:500].replace("\n", " | ")
        p.flag("🟡", "envoi du code SMS en échec : message montré", msg)
        page.wait_for_timeout(31000)
        p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS (2e essai)")
        code.wait_for(state="visible", timeout=60000)
    p.type(code, OTP, "le code")
    p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter")
    page.wait_for_timeout(4000)


def phase_ap_premiere(browser, origin, only):
    """Bot Noé (numéro neuf) : lien public → Se connecter pour répondre → SMS → retour sur l'événement → prénom → CGU →
    Présent ; puis retour arrière, rechargement, déconnexion / reconnexion."""
    st = load_state()
    ev = st["ap_public"]
    sql(f"delete from auth.users where phone = {q(NEW_BOTS['noe'].phone)}")  # vraiment neuf
    p = P(browser, "noe", origin, "premiere", fresh=True)
    page = p.page
    try:
        p.goto(f"/events/event/{ev}")
        page.wait_for_timeout(4000)
        p.shot("lien-public")
        with p.step("Se connecter pour répondre"):
            p.tap(page.get_by_role("button", name="Se connecter pour répondre"), "Se connecter pour répondre")
            page.wait_for_timeout(1500)
            p.shot("connexion")
            _sign_in_here(p, NEW_BOTS["noe"])
            trail = _url_trail(p, 20)
            p.log(f"adresses après connexion : {trail}")
            p.shot("apres-connexion")
            p.dump("apres-connexion")
            if f"/share/{ev}" not in page.url and f"/event/{ev}" not in page.url:
                p.flag("🔴", "après la connexion SMS depuis le lien public, retour ailleurs que sur l'événement", page.url)
        prof = sql(f"select id, display_name, status, role from public.profiles where phone = {q(NEW_BOTS['noe'].phone)}")
        p.log(f"profil créé : {prof}")
        with p.step("prénom demandé sur la page publique"):
            name = page.get_by_label("Ton prénom, pour que l’organisateur sache qui vient")
            if p.see(name, "le champ prénom", 20000):
                p.type(name, "Bot Noé", "le prénom")
                patches: list[int] = []
                page.on("response", lambda r: patches.append(r.status)
                        if "/rest/v1/profiles" in r.url and r.request.method == "PATCH" else None)
                p.tap(page.get_by_role("button", name="Continuer"), "Continuer")
                page.wait_for_timeout(2500)
                sheet = f.accept_terms_if_asked(p)
                p.log(f"feuille CGU au prénom : {sheet}")
                if not sheet:
                    p.flag("🔴", "Lien public, nouveau compte : « Continuer » (prénom) sans feuille CGU (CGU exigées)")
                for _ in range(40):
                    if patches:
                        break
                    page.wait_for_timeout(500)
                page.wait_for_timeout(2500)
                p.log(f"enregistrement du prénom : HTTP {patches}")
                if any(st >= 400 for st in patches):
                    p.flag("🟠", "enregistrement du prénom : réponse en erreur", str(patches))
                p.shot("prenom-enregistre")
                if page.get_by_text("Ton prénom n’a pas été enregistré").count():
                    p.flag("🔴", "Lien public, nouveau compte : « Continuer » (prénom) refusé par la base (terms_required, 403) "
                           "et aucune feuille CGU proposée — impasse, impossible de répondre")
                    # Suite du parcours : CGU acceptées en base (ce que la feuille CGU aurait fait).
                    sql(f"""insert into public.terms_acceptances (user_id, version)
                            select p.id, s.terms_version from public.profiles p, private.moderation_settings s
                            where p.phone = {q(NEW_BOTS['noe'].phone)} on conflict do nothing""")
                    p.tap(page.get_by_role("button", name="Continuer"), "Continuer (CGU acceptées en base)")
                    page.wait_for_timeout(2500)
                    p.shot("prenom-apres-cgu")
        with p.step("répondre Présent (CGU si demandées)"):
            btn = page.get_by_role("button", name=re.compile(r"^Présent"))
            p.tap(btn.first, "Présent")
            page.wait_for_timeout(2500)
            terms = f.accept_terms_if_asked(p)
            p.log(f"CGU demandées : {terms}")
            rows = _rsvp_rows(ev, NEW_BOTS["noe"].phone)
            p.log(f"base après le 1er toucher : {rows}")
            if terms and not rows:
                p.log("CGU acceptées : la réponse n'est pas partie toute seule, nouveau toucher")
                p.flag("🟠", "Lien public : après « J'accepte » (CGU), la réponse Présent n'est pas enregistrée — il faut toucher à nouveau")
                p.tap(btn.first, "Présent (2e fois)")
                page.wait_for_timeout(2500)
            p.shot("apres-present")
            rows = _rsvp_rows(ev, NEW_BOTS["noe"].phone)
            p.log(f"base : {rows}")
            if not rows or rows[0]["status"] != "yes":
                body = page.locator("body").inner_text()[:600]
                p.flag("🔴", "Lien public : la réponse Présent du nouveau compte n'est pas enregistrée", body)
            else:
                p.expect_or_flag(page.get_by_text("Ta réponse : Présent"), "« Ta réponse : Présent »")
                p.expect_or_flag(page.get_by_text(re.compile(r"1 participant")), "compteur « 1 participant »", "🟡", 5000)
        with p.step("changer pour Absent puis Peut-être"):
            for choice, status in (("Absent", "no"), ("Peut-être", "maybe")):
                p.tap(page.get_by_role("button", name=re.compile(rf"^{choice}")).first, choice)
                page.wait_for_timeout(2500)
                rows = _rsvp_rows(ev, NEW_BOTS["noe"].phone)
                if not rows or rows[0]["status"] != status:
                    p.flag("🟠", f"page publique : changement de réponse en {choice} non enregistré", str(rows))
            p.shot("peut-etre")
        with p.step("Signaler (connecté) depuis la page publique"):
            if p.see(page.get_by_role("button", name="Signaler cet événement"), "bouton Signaler (connecté)", 4000):
                p.log("bouton présent (signalement réel non envoyé ici : fait dans ap_double)")
            else:
                p.flag("🟡", "page publique connectée : pas de bouton « Signaler cet événement »")
        with p.step("retour arrière du navigateur puis avant"):
            before = page.url
            page.go_back()
            page.wait_for_timeout(2500)
            p.log(f"retour arrière : {page.url}")
            p.shot("retour-arriere")
            if not page.locator("body").inner_text().strip():
                p.flag("🟠", "retour arrière : page blanche", page.url)
            page.go_forward()
            page.wait_for_timeout(2500)
            p.log(f"avant : {page.url} (avant : {before})")
        with p.step("rechargement : la réponse est toujours là"):
            p.goto(f"/events/event/{ev}")
            page.wait_for_timeout(4000)
            p.log(f"rechargé : {page.url}")
            p.expect_or_flag(page.get_by_text("Ta réponse : Peut-être"), "réponse gardée après rechargement")
            p.shot("recharge")
        with p.step("onglet Événements du nouveau compte (sans photo)"):
            p.goto("/events/")
            page.wait_for_timeout(4000)
            p.shot("accueil-nouveau-compte")
            tree = p.dump("accueil-nouveau-compte")
            p.log(tree[:800])
        p.save_session()
    finally:
        p.close()


def phase_ap_profil(browser, origin, only):
    """Nora : première connexion directe par l'accueil (pas de lien) → « Faisons connaissance » → profil complet → liste."""
    sql(f"delete from auth.users where phone = {q(NEW_BOTS['nora'].phone)}")
    p = P(browser, "nora", origin, "profil", fresh=True)
    page = p.page
    try:
        p.goto("/events/")
        page.wait_for_timeout(3000)
        p.shot("accueil-sans-compte")
        _sign_in_here(p, NEW_BOTS["nora"])
        p.shot("apres-connexion")
        tree = p.dump("apres-connexion")
        p.log(tree[:1500])
        with p.step("profil complet (prénom, nom, surnom, photo) → CGU → Continuer"):
            from tests.bots.setup_accounts import _png
            photo = OUT / "nora-photo.png"
            photo.write_bytes(_png((200, 80, 140), 256))
            p.type(page.get_by_label("Prénom", exact=True), "Nora", "le prénom")
            p.type(page.get_by_label("Nom", exact=True), "Nouvelle", "le nom")
            p.type(page.get_by_label("Surnom", exact=True), "Bot Nora", "le surnom")
            with page.expect_file_chooser() as fc:
                p.tap(page.get_by_role("button", name="Choisir une photo"), "Choisir une photo")
            fc.value.set_files(str(photo))
            page.wait_for_timeout(1500)
            p.shot("recadrage")
            p.tap(page.get_by_role("button", name="Valider la photo"), "Valider la photo")
            page.wait_for_timeout(1000)
            _double_tap(p, page.get_by_role("button", name="Continuer").first, "Continuer (double)")
            page.wait_for_timeout(2500)
            terms = f.accept_terms_if_asked(p)
            p.log(f"CGU demandées : {terms}")
            if terms:
                page.wait_for_timeout(1500)
                if page.get_by_role("button", name="Continuer").count():
                    p.tap(page.get_by_role("button", name="Continuer").first, "Continuer (après CGU)")
            trail = _url_trail(p, 10)
            p.log(f"adresses : {trail}")
            p.shot("apres-profil")
            prof = sql(f"""select display_name, first_name, last_name, avatar_url is not null av, status, role,
                           (select count(*) from public.terms_acceptances t where t.user_id = p.id) cgu
                           from public.profiles p where phone = {q(NEW_BOTS['nora'].phone)}""")
            p.log(f"base : {prof}")
            if not prof or not prof[0]["av"] or prof[0]["display_name"] != "Bot Nora":
                p.flag("🔴", "première connexion : profil non enregistré", str(prof))
        with p.step("liste des événements du nouveau Guest, réponse à l'événement public"):
            p.goto("/events/")
            page.wait_for_timeout(5000)
            p.shot("liste-nouveau-guest")
            p.log(p.dump("liste-nouveau-guest")[:1500])
            card = page.get_by_text(f"{PREFIX} Apéro public").first
            if not p.see(card, "l'événement public dans la liste", 10000):
                p.flag("🟠", "nouveau Guest : l'événement public n'est pas dans sa liste")
            else:
                p.tap(card, "carte Apéro public")
                page.wait_for_timeout(3500)
                p.shot("fiche-guest")
                p.tap(_radio(p, "Présent"), "Présent")
                page.wait_for_timeout(3000)
                f.accept_terms_if_asked(p)
                rows = _rsvp_rows(load_state()["ap_public"], NEW_BOTS["nora"].phone)
                p.log(f"base : {rows}")
                if not rows or rows[0]["status"] != "yes":
                    p.flag("🔴", "nouveau Guest : Présent depuis la fiche non enregistré", str(rows))
    finally:
        p.close()


def phase_ap_connexion_erreurs(browser, origin, only):
    """Écran de connexion : code demandé hors ligne, mauvais code, bon code hors ligne, double toucher."""
    p = P(browser, "noe", origin, "connexion-erreurs", fresh=True)
    page = p.page
    noe = NEW_BOTS["noe"]

    def message() -> str:
        return " | ".join(l for l in page.locator("body").inner_text().splitlines()
                          if l.strip() and not l.startswith(("Ton compte", "Connecte-toi", "Pays", "Suisse", "France", "Autre",
                                                              "Un numéro", "Confidentialité", "Recevoir", "Se connecter", "Changer")))

    try:
        p.goto("/events/")
        field = page.get_by_label("Ton numéro de téléphone", exact=True)
        field.wait_for(timeout=60000)
        p.type(field, "0" + noe.phone[2:], "le numéro")
        with p.step("Recevoir un code hors ligne"):
            p.ctx.set_offline(True)
            p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code (hors ligne)")
            page.wait_for_timeout(3000)
            p.shot("code-hors-ligne")
            msg = message()
            p.log(f"message : {msg}")
            if not re.search(r"(?i)réseau|connexion a échoué|internet", msg):
                p.flag("🟡", "connexion : « Recevoir un code » hors ligne — message technique ou absent", msg)
            p.ctx.set_offline(False)
        with p.step("double toucher Recevoir un code"):
            with page.expect_response(lambda r: "/auth/v1/otp" in r.url, timeout=90000):
                if os.environ.get("AP_SIMPLE_CODE"):  # relance : le 2e toucher ouvrait la Confidentialité (constat R-10)
                    p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
                else:
                    _double_tap(p, page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
            page.wait_for_timeout(2500)
            p.shot("code-demande")
        code = page.get_by_placeholder("123456", exact=True)
        if not p.see(code, "le champ du code", 60000):
            msg = message()
            p.flag("🟠", "connexion : le code n'arrive pas — message montré", msg)
            if re.search(r"(?i)security purposes|HTTP \d|seconds", msg):
                p.flag("🟠", "connexion : message de Supabase en anglais ou technique montré tel quel", msg)
            return
        with p.step("mauvais code"):
            p.type(code, "000000", "un mauvais code")
            p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter (mauvais code)")
            page.wait_for_timeout(4000)
            p.shot("mauvais-code")
            p.log(f"message : {message()}")
        with p.step("bon code hors ligne"):
            p.type(code, OTP, "le bon code")
            p.ctx.set_offline(True)
            p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter (hors ligne)")
            page.wait_for_timeout(4000)
            p.shot("bon-code-hors-ligne")
            msg = message()
            p.log(f"message : {msg}")
            if "Code incorrect" in msg:
                p.flag("🟡", "connexion hors ligne : « Code incorrect ou expiré » affiché alors que le code est bon (c'est le réseau)", msg)
            p.ctx.set_offline(False)
        with p.step("bon code en ligne"):
            p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter")
            trail = _url_trail(p, 12)
            p.log(f"adresses : {trail}")
            p.shot("connecte")
    finally:
        p.ctx.set_offline(False)
        p.close()


def phase_ap_partage(browser, origin, only):
    """« Partager le lien » (organisatrice) → le lien copié, ouvert par un visiteur sans compte ; aperçu de ce lien."""
    st = load_state()
    o = P(browser, "orga1", origin, "partage")
    page = o.page
    url = ""
    try:
        inject(o, o.bot.phone)
        o.goto(f"/events/event/{st['ap_public']}")
        btn = page.get_by_role("button", name="Partager le lien")
        if not o.see(btn, "« Partager le lien »", 90000):
            o.flag("🟠", "fiche d'un événement public : pas de bouton « Partager le lien »")
            return
        page.evaluate("try { delete navigator.share } catch (e) {}; Object.defineProperty(navigator, 'share', {value: undefined})")
        o.tap(btn, "Partager le lien")
        page.wait_for_timeout(1500)
        url = page.evaluate("navigator.clipboard.readText()")
        o.log(f"lien copié : {url}")
        o.shot("lien-copie")
    finally:
        o.close()
    if not url:
        return
    meta = og_tags(origin, re.sub(r"^https?://[^/]+", "", url))
    anomaly_detail = json.dumps(meta, ensure_ascii=False)
    print("aperçu du lien partagé :", anomaly_detail)
    if PREFIX not in json.dumps(meta, ensure_ascii=False):
        anomaly("orga1", "🟠", "« Partager le lien » : l'aperçu (WhatsApp, iMessage) ne montre ni le titre ni la date de l'événement",
                f"{url} → {anomaly_detail}")
    v = P(browser, "nora", origin, "partage-visiteur", fresh=True)
    page = v.page
    try:
        v.page.goto(url, wait_until="domcontentloaded")
        v.log(f"ouvre le lien partagé {url}")
        page.wait_for_timeout(8000)
        v.shot("lien-partage-ouvert")
        frame_txt = " | ".join(fr.locator("body").inner_text()[:300] for fr in page.frames if "/events/" in fr.url)
        v.log(f"cadre Événements : {[fr.url for fr in page.frames]} → {frame_txt!r}")
        if PREFIX not in frame_txt and PREFIX not in page.locator("body").inner_text():
            v.flag("🔴", "lien partagé ouvert sans compte : l'événement public ne s'affiche pas", frame_txt[:300])
    finally:
        v.close()


# ── 3. Deux appareils, temps réel ──────────────────────────────────────────────────────────────────────────────

CONFIRM = {"yes": "C’est noté, tu viens !", "maybe": "Noté en peut-être. Pense à confirmer.", "no": "Dommage ! Tu es noté absent."}


def phase_ap_deux_appareils(browser, origin, only):
    st = load_state()
    ev = st["ap_invited"]
    a = P(browser, "vip1", origin, "deux-appareils")
    b = P2(browser, "vip1", origin, "deux-appareils", "android")
    try:
        for ph in (a, b):
            inject(ph, ph.bot.phone)
            frames = []
            ph.page.on("websocket", lambda ws, frames=frames: ws.on("framereceived", lambda d, frames=frames: frames.append(str(d)[:200])))
            ph.frames = frames
            ph.goto(f"/events/event/{ev}")
            _radio(ph, "Présent").wait_for(timeout=90000)
            ph.page.wait_for_timeout(3000)
        a.shot("iphone-avant")
        b.shot("android-avant")
        for who, other, choice, status in ((a, b, "Présent", "yes"), (b, a, "Absent", "no"), (a, b, "Peut-être", "maybe")):
            with who.step(f"{choice} sur un appareil, visible sur l'autre sans recharger"):
                n_frames = len(other.frames)
                with who.page.expect_response(lambda r: "/rest/v1/rsvps" in r.url and r.request.method in ("POST", "PATCH")
                                              and r.status < 300, timeout=90000):
                    who.tap(_radio(who, choice), choice)
                t_saved = time.time()
                who.page.wait_for_timeout(800)
                rows = _rsvp_rows(ev, BY_KEY["vip1"].phone)
                who.log(f"base : {rows}")
                if not rows or rows[0]["status"] != status:
                    who.flag("🔴", f"{choice} non enregistré", str(rows))
                t0 = t_saved
                seen = False
                while time.time() - t0 < 25:
                    if other.page.get_by_text(CONFIRM[status], exact=True).count():
                        seen = True
                        break
                    other.page.wait_for_timeout(500)
                rt = [x for x in other.frames[n_frames:] if "postgres_changes" in x]
                other.log(f"{choice} vu sur l'autre appareil : {seen} en {time.time() - t0:.1f} s ; trames temps réel reçues : {len(rt)} {rt[:2]}")
                other.shot(f"autre-{status}")
                if not seen:
                    other.flag("🟠", f"deux appareils : « {choice} » donné sur l'un n'apparaît pas sur l'autre (25 s après l'enregistrement, sans recharger)")
    finally:
        a.close()
        b.close()


# ── 4. Perte de réseau, double toucher ──────────────────────────────────────────────────────────────────────────

def phase_ap_reseau(browser, origin, only):
    st = load_state()
    ev = st["ap_invited"]
    p = P(browser, "vip2", origin, "reseau")
    page = p.page
    try:
        inject(p, p.bot.phone)
        p.goto(f"/events/event/{ev}")
        page.wait_for_timeout(3500)
        with p.step("Présent hors ligne"):
            p.ctx.set_offline(True)
            p.tap(_radio(p, "Présent"), "Présent (hors ligne)")
            page.wait_for_timeout(4000)
            p.shot("present-hors-ligne")
            body = page.locator("body").inner_text()
            msg = [l for l in body.splitlines() if re.search(r"(?i)réseau|connexion|hors ligne|internet|réessaie|failed|fetch", l)]
            p.log(f"message affiché hors ligne : {msg}")
            if not msg:
                p.flag("🟠", "Réponse hors ligne : aucun message clair (le bouton a l'air de marcher ou rien ne se passe)")
            elif any(re.search(r"(?i)failed to fetch|typeerror|networkerror", m) for m in msg):
                p.flag("🟠", "Réponse hors ligne : message technique en anglais", "; ".join(msg))
            p.ctx.set_offline(False)
            page.wait_for_timeout(2000)
            rows = _rsvp_rows(ev, BY_KEY["vip2"].phone)
            p.log(f"base après retour du réseau : {rows}")
        with p.step("Présent après retour du réseau"):
            p.tap(_radio(p, "Présent"), "Présent (en ligne)")
            page.wait_for_timeout(2500)
            f.accept_terms_if_asked(p)
            rows = _rsvp_rows(ev, BY_KEY["vip2"].phone)
            if len(rows) != 1 or rows[0]["status"] != "yes":
                p.flag("🔴", "après retour du réseau : réponse absente ou en double", str(rows))
            p.shot("present-en-ligne")
        with p.step("forum : message envoyé hors ligne"):
            p.goto(f"/events/event/{ev}/chat")
            page.wait_for_timeout(3500)
            p.shot("forum")
            box = page.get_by_role("textbox").last
            if not box.count():
                p.log("pas de zone de message (forum)")
            else:
                p.ctx.set_offline(True)
                p.type(box, f"{PREFIX} message hors ligne", "le message")
                send = page.get_by_role("button", name=re.compile("^Envoyer")).last
                p.tap(send, "Envoyer (hors ligne)")
                page.wait_for_timeout(3500)
                p.shot("forum-hors-ligne")
                body = page.locator("body").inner_text()
                p.log("forum hors ligne : " + " | ".join(l for l in body.splitlines()[-12:]))
                p.ctx.set_offline(False)
                page.wait_for_timeout(5000)
                n = sql(f"select count(*) n from public.messages where event_id = {q(ev)} and body like '%message hors ligne%'")[0]["n"]
                p.log(f"messages hors ligne en base : {n}")
                p.shot("forum-retour-reseau")
                remain = box.input_value() if box.count() else ""
                p.log(f"texte resté dans la zone : {remain!r}")
                if n == 0 and not remain:
                    p.flag("🟠", "forum : message écrit hors ligne perdu (ni envoyé ni gardé dans la zone)")
                if n > 1:
                    p.flag("🔴", f"forum : message hors ligne envoyé {n} fois")
        with p.step("liste des événements hors ligne puis rechargement"):
            p.goto("/events/")
            page.wait_for_timeout(3000)
            p.ctx.set_offline(True)
            try:
                page.reload(wait_until="domcontentloaded", timeout=8000)
            except Exception as e:  # le navigateur montre sa page d'erreur : attendu
                p.log(f"rechargement hors ligne : {type(e).__name__}")
            page.wait_for_timeout(2000)
            p.shot("liste-hors-ligne")
            p.ctx.set_offline(False)
            p.goto("/events/")
            page.wait_for_timeout(4000)
            p.expect_or_flag(page.get_by_label("Rechercher un événement"), "liste revenue après le réseau")
    finally:
        p.ctx.set_offline(False)
        p.close()


def _double_tap(p: Phone, locator, what: str) -> None:
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    p.log(f"double toucher « {what} »")
    p.page.touchscreen.tap(x, y)
    p.page.wait_for_timeout(60)
    p.page.touchscreen.tap(x, y)


def phase_ap_double(browser, origin, only):
    st = load_state()
    ev = st["ap_invited"]
    p = P(browser, "membre1", origin, "double")
    page = p.page
    try:
        inject(p, p.bot.phone)
        p.goto(f"/events/event/{ev}")
        page.wait_for_timeout(3500)
        with p.step("double toucher Présent"):
            _double_tap(p, _radio(p, "Présent"), "Présent")
            page.wait_for_timeout(3000)
            f.accept_terms_if_asked(p)
            rows = _rsvp_rows(ev, BY_KEY["membre1"].phone)
            p.log(f"base : {rows}")
            if len(rows) != 1:
                p.flag("🔴", "double toucher Présent : réponses en double", str(rows))
            p.shot("double-present")
        with p.step("double toucher Envoyer (signalement)"):
            p.tap(page.get_by_role("button", name="Signaler cet événement"), "Signaler cet événement")
            page.wait_for_timeout(1200)
            p.tap(page.get_by_role("radio", name=re.compile("Spam")).first, "raison Spam")
            p.type(page.get_by_label("Commentaire"), f"{PREFIX} test double envoi, à ignorer", "le commentaire")
            _double_tap(p, page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer le signalement")
            page.wait_for_timeout(3000)
            p.shot("double-signalement")
            n = sql(f"select count(*) n from public.content_reports where target_kind = 'event' and target_id = {q(ev)}")[0]["n"]
            p.log(f"signalements en base : {n}")
            if n > 1:
                p.flag("🟠", f"double toucher « Envoyer » le signalement : {n} signalements enregistrés")
            close = page.get_by_role("button", name="Fermer")
            if close.count():
                p.tap(close.last, "Fermer")
        with p.step("double toucher Envoyer (forum)"):
            p.goto(f"/events/event/{ev}/chat")
            page.wait_for_timeout(3500)
            box = page.get_by_role("textbox").last
            p.type(box, f"{PREFIX} double envoi", "le message")
            _double_tap(p, page.get_by_role("button", name=re.compile("^Envoyer")).last, "Envoyer (forum)")
            page.wait_for_timeout(3500)
            n = sql(f"select count(*) n from public.messages where event_id = {q(ev)} and body like '%double envoi%'")[0]["n"]
            p.log(f"messages « double envoi » : {n}")
            p.shot("double-forum")
            if n > 1:
                p.flag("🟠", f"double toucher « Envoyer » dans le forum : message envoyé {n} fois")
    finally:
        p.close()
    o = P(browser, "orga1", origin, "double-publier")
    page = o.page
    try:
        inject(o, o.bot.phone)
        with o.step("double toucher Publier (formulaire)"):
            o.goto("/events/event/new")
            o.see(page.get_by_label("Titre", exact=True), "le formulaire")
            f.fill(o, "Titre", f"{PREFIX} Double publier")
            f.fill(o, "Description", "Test du double toucher. Ignorer.")
            f.set_date(o, "Début", f.day(9), "19:30")
            f.audience_invite_groups(o, ["Bots"])
            _double_tap(o, page.get_by_role("button", name="Publier", exact=True).last, "Publier")
            page.wait_for_timeout(6000)
            f.accept_terms_if_asked(o)
            o.shot("double-publier")
            n = sql(f"select count(*) n from public.events where title = {q(PREFIX + ' Double publier')}")[0]["n"]
            o.log(f"événements créés : {n}")
            if n != 1:
                o.flag("🔴", f"double toucher « Publier » : {n} événements créés")
    finally:
        o.close()


# ── 5. Session expirée, inactivité, déconnexion ─────────────────────────────────────────────────────────────────

AUTH_KEY_JS = "Object.keys(localStorage).find(k => /^sb-.*-auth-token$/.test(k))"


def _ready(p: Phone, timeout: int = 90) -> str:
    """Attend la fin du chargement (plus de roue seule à l'écran) ; renvoie le texte affiché."""
    end = time.time() + timeout
    text = ""
    while time.time() < end:
        text = p.page.locator("body").inner_text().strip()
        if text and not p.page.get_by_role("progressbar").count():
            return text
        p.page.wait_for_timeout(500)
    p.log(f"toujours en chargement après {timeout} s")
    return text


def _set_session(p: Phone, js: str) -> None:
    p.page.evaluate(f"""() => {{ const k = {AUTH_KEY_JS}; const s = JSON.parse(localStorage.getItem(k)); {js};
        localStorage.setItem(k, JSON.stringify(s)); }}""")


def phase_ap_session(browser, origin, only):
    st = load_state()
    ev = st["ap_invited"]
    p = P(browser, "vip3", origin, "session")
    page = p.page
    login = page.get_by_label("Ton numéro de téléphone", exact=True)
    try:
        inject(p, p.bot.phone)
        p.goto("/events/")
        _ready(p)
        with p.step("jeton expiré, rafraîchissement valide"):
            _set_session(p, "s.expires_at = Math.floor(Date.now()/1000) - 60")
            p.goto(f"/events/event/{ev}")
            _ready(p)
            p.shot("jeton-expire")
            if not p.see(_radio(p, "Présent"), "fiche ouverte après un jeton expiré", 30000):
                p.flag("🟠", "jeton expiré (rafraîchissement possible) : la fiche ne s'ouvre pas", page.url)
        with p.step("session morte (jeton et rafraîchissement invalides) puis lien d'un événement sur invitation"):
            _set_session(p, "s.expires_at = Math.floor(Date.now()/1000) - 60; s.access_token = 'x.y.z'; s.refresh_token = 'mort'")
            p.goto(f"/events/event/{ev}")
            body = _ready(p)
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text()
            p.shot("session-morte")
            p.log(f"session morte : {page.url} | {body[:300]!r}")
            offer = page.get_by_role("button", name="Se connecter", exact=True)
            if not login.count() and not offer.count():
                p.flag("🟠", "session expirée : le lien d'un événement sur invitation affiche la page publique "
                       "(« Lien indisponible ») au lieu de proposer la connexion", f"{page.url} : {body[:200]}")
        with p.step("reconnexion depuis là"):
            if not login.count() and offer.count():
                p.tap(offer, "Se connecter (page « Connecte-toi pour voir cet événement »)")
                page.wait_for_timeout(1500)
            if not login.count():
                p.goto("/events/")
                _ready(p)
            _sign_in_here(p, BY_KEY["vip3"])
            trail = _url_trail(p, 15)
            p.log(f"après reconnexion : {trail}")
            p.shot("apres-reconnexion")
            if f"/event/{ev}" not in page.url:
                p.flag("🟡", "session expirée → Se connecter : retour ailleurs que sur l'événement demandé", page.url)
        with p.step("déconnexion (Réglages) puis lien de l'événement"):
            p.goto("/events/account")
            _ready(p)
            out = page.get_by_role("button", name="Se déconnecter")
            out.first.wait_for(timeout=60000)
            p.tap(out.first, "Se déconnecter")
            page.wait_for_timeout(1500)
            if not login.count():
                confirm = page.get_by_role("button", name=re.compile("^(Se déconnecter|Confirmer|Oui)"))
                if confirm.count():
                    p.tap(confirm.last, "confirmer la déconnexion")
            page.wait_for_timeout(3000)
            p.shot("deconnecte")
            stored = page.evaluate(f"() => {{ const k = {AUTH_KEY_JS}; return k ? localStorage.getItem(k) : null }}")
            p.log(f"session restante dans le navigateur : {bool(stored)} ; écran : {page.url}")
            p.goto(f"/events/event/{ev}")
            body = _ready(p)
            p.shot("deconnecte-fiche")
            p.log(f"lien après déconnexion : {page.url} | {body[:200]!r}")
            if f"{PREFIX} Soirée Bots" in body:
                p.flag("🔴", "après déconnexion, l'événement sur invitation reste lisible")
            offer = page.get_by_role("button", name="Se connecter", exact=True)
            if not login.count() and offer.count():
                p.tap(offer, "Se connecter (après déconnexion)")
                page.wait_for_timeout(1500)
            if not login.count():
                p.flag("🟡", "membre déconnecté qui ouvre le lien d'un événement sur invitation : « Lien indisponible », "
                       "aucun bouton pour se connecter", body[:200])
                p.goto("/events/")
                _ready(p)
            _sign_in_here(p, BY_KEY["vip3"])
            trail = _url_trail(p, 15)
            p.log(f"après reconnexion : {trail}")
            p.shot("reconnecte")
            if f"/event/{ev}" not in page.url:
                p.flag("🟡", "reconnexion après un lien d'événement : retour à la liste, pas à l'événement demandé", page.url)
        with p.step("onglet ouvert longtemps (horloge avancée de 3 h)"):
            p.goto("/events/")
            _ready(p)
            page.clock.install()
            page.clock.fast_forward("03:00:00")
            page.wait_for_timeout(3000)
            p.tap(page.get_by_text(f"{PREFIX} Soirée Bots (robustesse)").first, "carte Soirée Bots", timeout=60000)
            _ready(p)
            p.shot("apres-3h")
            if not p.see(_radio(p, "Présent"), "fiche après 3 h", 60000):
                p.flag("🟠", "après 3 h d'inactivité, la fiche ne s'ouvre pas", page.locator("body").inner_text()[:300])
            else:
                with page.expect_response(lambda r: "/rest/v1/rsvps" in r.url and r.request.method in ("POST", "PATCH"),
                                          timeout=90000) as resp:
                    p.tap(_radio(p, "Absent"), "Absent après 3 h")
                p.log(f"réponse HTTP {resp.value.status}")
                rows = _rsvp_rows(ev, BY_KEY["vip3"].phone)
                p.log(f"base : {rows}")
                if not rows or rows[0]["status"] != "no":
                    p.flag("🟠", "après 3 h d'inactivité, la réponse n'est pas enregistrée", page.locator("body").inner_text()[:300])
    finally:
        p.close()


def phase_ap_rechargement(browser, origin, only):
    """Relance (correction C2 n° 2) : l'intention n'est plus gardée dans sessionStorage une fois servie. Un membre sans
    session ouvre le lien d'un événement sur invitation → « Se connecter » → la page de connexion est RECHARGÉE (onglet
    rechargé par iOS pendant qu'on lit le SMS, ou geste « tirer pour recharger ») → connexion : où arrive-t-il ?
    Témoin : même parcours sans rechargement."""
    st = load_state()
    ev = st["ap_invited"]
    for reload_sign_in in (False, True):
        tag = "avec-rechargement" if reload_sign_in else "sans-rechargement"
        p = P(browser, "vip3", origin, f"rechargement-{tag}", fresh=True)
        page = p.page
        try:
            p.goto(f"/events/event/{ev}")
            _ready(p)
            page.wait_for_timeout(1500)
            p.log(f"ouvert : {page.url}")
            p.shot("lien-sans-session")
            offer = page.get_by_role("button", name="Se connecter", exact=True)
            if not p.see(offer, "« Se connecter » (événement sur invitation, sans session)", 20000):
                p.flag("🟠", "lien d'un événement sur invitation sans session : pas de « Se connecter »",
                       page.locator("body").inner_text()[:200])
                continue
            p.tap(offer, "Se connecter")
            page.wait_for_timeout(1500)
            if reload_sign_in:
                page.reload(wait_until="domcontentloaded")
                _ready(p)
                p.log(f"page de connexion rechargée : {page.url}")
                p.shot("connexion-rechargee")
            _sign_in_here(p, BY_KEY["vip3"])
            trail = _url_trail(p, 15)
            p.log(f"après connexion : {trail}")
            p.shot("apres-connexion")
            if f"/event/{ev}" not in page.url and f"/share/{ev}" not in page.url:
                p.flag("🟠" if reload_sign_in else "🔴",
                       f"lien d'un événement → Se connecter{' → page rechargée' if reload_sign_in else ''} → connexion : "
                       "arrivée sur la liste, pas sur l'événement demandé", page.url)
        finally:
            p.close()


# ── 6. Performances : liste avec 30+ événements ─────────────────────────────────────────────────────────────────

def phase_ap_perf(browser, origin, only):
    results = []
    for key in ("vip1", "orga1"):
        p = P(browser, key, origin, "perf")
        page = p.page
        try:
            inject(p, p.bot.phone)
            for run in range(3):
                t0 = time.time()
                p.goto("/events/")
                page.get_by_label("Rechercher un événement").wait_for(timeout=60000)
                page.get_by_text(re.compile(re.escape(PREFIX) + r" (Perf|Soirée)")).first.wait_for(timeout=60000)
                t_first = time.time() - t0
                nav = page.evaluate("""() => { const n = performance.getEntriesByType('navigation')[0];
                    const r = performance.getEntriesByType('resource');
                    return {dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd),
                            bytes: r.reduce((a, x) => a + (x.transferSize || 0), 0) + (n.transferSize || 0),
                            requests: r.length,
                            supabase: r.filter(x => x.name.includes('supabase.co')).map(x => [x.name.split('?')[0].split('/').slice(-1)[0], Math.round(x.duration)])}; }""")
                cards = page.get_by_text(re.compile(re.escape(PREFIX) + r" Perf")).count()
                results.append({"bot": key, "run": run, "first_card_s": round(t_first, 2), "cards_in_dom": cards, **nav})
                p.log(f"mesure {run} : première carte en {t_first:.2f} s ; {nav} ; cartes Perf dans la page : {cards}")
            p.shot("liste-30")
            t0 = time.time()
            res = p.scroll_to_bottom("liste de 30+ événements", tries=25)
            p.log(f"défilement jusqu'en bas : {res} en {time.time() - t0:.1f} s")
            p.shot("liste-bas")
        finally:
            p.close()
    (OUT / "perf.json").write_text(json.dumps(results, indent=2))
    slow = [r for r in results if r["first_card_s"] > 4]
    if slow:
        anomaly("banc", "🟠", "liste des événements (30+) lente : première carte > 4 s", json.dumps(slow))


# ── Ménage ──────────────────────────────────────────────────────────────────────────────────────────────────────

def phase_ap_menage(browser, origin, only):
    n = sql(f"""with d as (delete from public.events where title like {q(PREFIX + '%')} returning 1) select count(*) n from d""")
    sql(f"delete from auth.users where phone in ({q(NEW_BOTS['noe'].phone)}, {q(NEW_BOTS['nora'].phone)})")
    print("événements supprimés :", n)
    phase_ap_numeros_retirer(browser, origin, only)


def _otp_entries() -> list[str]:
    from tests.bots.common import auth_config
    return [x for x in (auth_config().get("sms_test_otp") or "").split(",") if x]


def _patch_otp(entries: list[str]) -> None:
    from tests.bots.common import auth_config, patch_auth_config
    until = auth_config().get("sms_test_otp_valid_until") or "2027-10-25T00:00:00+00:00"
    patch_auth_config({"sms_test_otp": ",".join(entries), "sms_test_otp_valid_until": until})


def phase_ap_numeros(browser, origin, only):
    """Numéros neufs de Noé et Nora ajoutés à sms_test_otp (base TEST) ; aucun compte ne doit exister pour eux."""
    phones = [b.phone for b in NEW_BOTS.values()]
    for n in phones:
        if sql(f"select 1 from auth.users where phone = {q(n)}"):
            raise RuntimeError(f"le numéro {n} a déjà un compte : pas neuf")
    entries = _otp_entries()
    known = {e.split("=")[0] for e in entries}
    missing = [f"{n}={OTP}" for n in phones if n not in known]
    if missing:
        _patch_otp(entries + missing)
    print("sms_test_otp + ", missing, flush=True)


def phase_ap_numeros_retirer(browser, origin, only):
    phones = {b.phone for b in NEW_BOTS.values()}
    _patch_otp([e for e in _otp_entries() if e.split("=")[0] not in phones])
    print("numéros retirés de sms_test_otp :", sorted(phones), flush=True)


if __name__ == "__main__":
    import sys
    import traceback

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in sys.argv[1:]:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, load_state()["origin"], None)
            except Exception as e:  # une phase cassée n'arrête pas les suivantes
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()
