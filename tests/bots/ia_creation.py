"""Campagne 2, agent 02 : « Créer avec l'IA », étapes 2 et 3 dans le navigateur (et l'API de l'étape 1), base de TEST.

Sans clé Anthropic : les brouillons sont injectés par POST /api/account/ai/event/draft/save (comme l'app iPhone après
« Oui, continuer »), tout le reste passe par le vrai serveur et la vraie base. Titres préfixés « [C2-02] ».
Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.ia_creation <phase…>   (phases : voir PHASES)"""
from __future__ import annotations

import os
import re
import sys
import threading
import traceback

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state, phone, save_state
import functools
import time

from tests.bots.common import BY_KEY, GROUP_BOTS, GROUP_BOTS_2, Session, q
from tests.bots.common import sql as _sql


def sql(query: str):
    """Base de TEST ; l'API de gestion est partagée par 10 agents : on attend et on réessaie (429)."""
    for attempt in range(12):
        try:
            return _sql(query)
        except RuntimeError as e:
            if "429" not in str(e) or attempt == 11:
                raise
            time.sleep(8 + attempt * 4)

PREFIX = os.environ.get("BOTS_PREFIX", "[C2-02]")  # relance : « [R-02] »
DRAFT = {"status": "ready", "questions": [], "description": "Assistant IA, recette de la campagne 2. Ignorer.",
         "end": "", "place_query": "Rue du Lac 12, Vevey", "place_name": "Chez les bots", "place_broad": "",
         "address_complete": True, "price_chf": 0, "max_participants": 0, "category": "Soirée", "audience": "",
         "invitees": [], "not_understood": [], "pot": False, "bring": ["Salade"], "summary": "Recette IA"}
PLACE = {"name": "Chez les bots", "address": "Rue du Lac 12, 1800 Vevey", "url": ""}
INVITE_BTN = re.compile("^✉️ Sur invitation seulement : ")
_sessions: dict[str, Session] = {}
_consented: set[str] = set()


def session(key: str) -> Session:
    if key not in _sessions:
        _sessions[key] = Session(BY_KEY[key].phone)
    return _sessions[key]


def origin() -> str:
    return load_state()["origin"]


def post(path: str, body: dict) -> dict:
    r = httpx.post(f"{origin()}{path}", json=body, timeout=60)
    try:
        data = r.json()
    except ValueError:
        data = r.text
    return {"status": r.status_code, "body": data}


def save_draft(key: str, title: str, offset: int, **extra) -> dict:
    s = session(key)
    while key not in _consented:  # comme l'app : l'accord « IA » est donné avant le premier envoi
        if post("/api/account/ai/consent", {"token": s.token, "accept": True})["status"] == 200:
            _consented.add(key)
        else:
            time.sleep(10)
    draft = {**DRAFT, "title": f"{PREFIX} {title}", "start": f"{f.day(offset)}T19:00", **extra}
    for attempt in range(10):  # base de TEST chargée par 10 agents : « ne répond pas » passager → on réessaie
        out = post("/api/account/ai/event/draft/save", {"token": s.token, "draft": draft, "place": PLACE})
        if out["status"] == 200 or "ne répond pas" not in str(out["body"]):
            break
        print(f"brouillon : service des comptes lent ({attempt + 1}), nouvel essai", flush=True)
        time.sleep(10)
    print("brouillon", key, title, out, flush=True)
    return out


def ev(eid: str) -> dict:
    rows = sql(f"""select status, visibility, public_link, announce_group, ai_suggested,
        (select coalesce(array_agg(g.name order by g.name), '{{}}') from public.event_groups eg join public.member_groups g on g.id = eg.group_id where eg.event_id = e.id) groups,
        (select count(*) from public.event_invites i where i.event_id = e.id) invites,
        (select count(*) from public.event_announcements a where a.event_id = e.id) announcements,
        (select coalesce(array_agg(a.status), '{{}}') from public.event_announcements a where a.event_id = e.id) ann_status
        from public.events e where id = {q(eid)}""")
    return rows[0] if rows else {}


@functools.cache
def uid_of(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


@functools.cache
def gid(name: str) -> str:
    return sql(f"select id from public.member_groups where name = {q(name)}")[0]["id"]


def check(p, cond: bool, sev: str, title: str, detail: str = "") -> None:
    if cond:
        p.log(f"✅ {title}")
    else:
        p.flag(sev, title, detail)


def note_api(sev: str, title: str, detail: str) -> None:
    print(f"{sev} API : {title} {detail}", flush=True)
    anomaly("api", sev, title, detail)


def signed(browser, key: str, phase: str):
    """Connexion par le vrai écran ; code SMS limité à un par minute et par numéro (partagé avec les autres agents) :
    on attend et on redemande, jusqu'à voir la liste des événements."""
    p = phone(browser, key, origin(), phase)
    page = p.page
    for attempt in range(5):
        p.goto("/events/")
        field = page.get_by_label("Ton numéro de téléphone", exact=True)
        listed = page.get_by_role("button", name="Rechercher", exact=True)
        try:
            field.or_(listed).first.wait_for(state="visible", timeout=40000)
        except Exception:
            p.log("ni liste ni connexion : nouvel essai")
            continue
        if listed.count() and listed.first.is_visible():
            p.log("connecté")
            p.save_session()
            return p
        p.type(field, "0" + p.bot.phone[2:], "le numéro")
        p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
        code = page.get_by_placeholder("123456", exact=True)
        try:
            code.wait_for(state="visible", timeout=20000)
        except Exception:
            p.log(f"pas de code (limite d'envoi ?), nouvel essai dans 45 s ({attempt + 1})")
            page.wait_for_timeout(45000)
            continue
        p.type(code, "123456", "le code")
        p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter")
        try:
            listed.wait_for(state="visible", timeout=40000)
            p.log("connecté")
            p.save_session()
            return p
        except Exception:
            p.shot("connexion-ratee")
            p.log("connexion non aboutie : nouvel essai dans 45 s")
            page.wait_for_timeout(45000)
    raise RuntimeError(f"connexion impossible pour {key}")


def step2(p, eid: str, query: str = "") -> bool:
    bar = p.page.get_by_role("progressbar", name=re.compile("Étape 2 sur 3"))
    for attempt in range(3):  # base de TEST surchargée (25P02, 544) : on recharge avant de conclure
        p.goto(f"/events/event/{eid}/invite{query}")
        if p.see(bar, "l'étape 2 « Qui est invité »", 40000):
            return True
        p.shot("etape2-pas-chargee")
        p.log(f"étape 2 pas chargée (essai {attempt + 1}) : la base de TEST répond mal, nouvel essai dans 30 s")
        p.page.wait_for_timeout(30000)
    return p.expect_or_flag(p.page.get_by_role("progressbar", name=re.compile("Étape 2 sur 3")), "l'étape 2 « Qui est invité »", "🔴", 40000)


# ── API (étape 1) ───────────────────────────────────────────────────────────────────────────────────────────────

def phase_api(browser):
    """Accord IA (refus / accord), IA sans clé, plafond, droits, brouillon incomplet, double « Oui, continuer »."""
    s = session("orga2")
    st = post("/api/account/ai/status", {"token": s.token})
    print("statut", st, flush=True)
    out = post("/api/account/ai/consent", {"token": s.token, "accept": False})
    print("accord refusé", out, flush=True)
    # Appel direct : save_draft() donne d'abord l'accord (comme l'app), ce qui fausserait ce cas.
    refused = post("/api/account/ai/event/draft/save", {"token": s.token, "place": PLACE,
                    "draft": {**DRAFT, "title": f"{PREFIX} accord refusé", "start": f"{f.day(30)}T19:00"}})
    print("brouillon (accord refusé)", refused, flush=True)
    if refused["status"] != 403:
        note_api("🔴", "brouillon enregistré alors que l'accord IA est refusé", str(refused)[:300])
    post("/api/account/ai/consent", {"token": s.token, "accept": True})
    talk = post("/api/account/ai/event/draft", {"token": s.token, "turns": ["Raclette samedi chez moi"]})
    print("IA sans clé", talk, flush=True)
    if talk["status"] < 400 or "configuré" not in str(talk["body"]):
        note_api("🟠", "IA sans clé : pas le message « pas encore configuré »", str(talk)[:300])
    incomplete = post("/api/account/ai/event/draft/save", {"token": s.token, "place": PLACE,
                                                            "draft": {**DRAFT, "title": f"{PREFIX} incomplet", "start": ""}})
    print("brouillon incomplet", incomplete, flush=True)
    if incomplete["status"] < 400:
        note_api("🔴", "brouillon sans date accepté", str(incomplete)[:300])
    for key in ("membre1", "guest1"):  # Membre / Guest : ai.use mais pas events.create
        post("/api/account/ai/consent", {"token": session(key).token, "accept": True})
        out = save_draft(key, f"sans droit ({key})", 31)
        if out["status"] < 400:
            note_api("🔴", f"{key} (sans events.create) a pu enregistrer un brouillon IA", str(out)[:300])
            save_state(**{f"api_{key}": out["body"].get("id")})
    # Double toucher sur « Oui, continuer » (deux requêtes à la fois) : combien de brouillons ?
    results: list[dict] = []
    threads = [threading.Thread(target=lambda: results.append(save_draft("orga2", "double toucher", 32))) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    ids = [r["body"].get("id") for r in results if r["status"] == 200]
    save_state(api_double=ids)
    print("double toucher (API) :", ids, flush=True)
    # Invités cités : soi-même, une personne inconnue, une vraie (Bot Max)
    out = save_draft("orga2", "citées", 33, invitees=["Bot Oscar", "Bot Max", "Personne Inconnue"])
    print("invités cités", out, flush=True)
    if out["status"] == 200:
        save_state(api_cited=out["body"]["id"])
        names = [x["name"] for x in out["body"].get("suggested", [])]
        if names != ["Bot Max"]:
            note_api("🟡", "personnes citées : liste inattendue", str(names))


# ── Étape 2 dans le navigateur ──────────────────────────────────────────────────────────────────────────────────

def phase_invite(browser):
    """Bot Oscar (Android) : Sur invitation → feuille Inviter, lien prêt, Bot Max coché ; Inviter Bot Max."""
    out = save_draft("orga2", "Sur invitation", 20, invitees=["Bot Max"])
    eid = out["body"]["id"]
    save_state(e_invite=eid)
    max_id = uid_of("membre3")
    p = signed(browser, "orga2", "ia-invite")
    try:
        if not step2(p, eid, f"?suggested={max_id}"):
            return
        page = p.page
        p.shot("etape2")
        p.dump("etape2")
        # Bot Oscar est dans Vendredi Party (base de TEST) : le choix « Membres » existe, mais un bot ne le touche JAMAIS
        # (vrais membres VIP dans la base de TEST).
        p.log(f"choix « Membres Vendredi Party » : {page.get_by_role('button', name=re.compile('Membres Vendredi Party')).count()}")
        p.scroll_to_bottom("étape 2")
        cut = p.check_texts_cut("étape 2")
        if cut:
            p.flag("🟡", "étape 2 : textes coupés", "; ".join(cut))
        p.tap(page.get_by_role("button", name=INVITE_BTN), "Sur invitation seulement")
        page.wait_for_timeout(3000)
        if f.accept_terms_if_asked(p):
            page.wait_for_timeout(3000)
        sheet = page.get_by_label(re.compile("^Inviter à "))
        if p.expect_or_flag(sheet, "la feuille « Inviter » (lien prêt)", "🔴", 15000):
            p.shot("feuille-inviter")
            p.dump("feuille-inviter")
            check(p, "invite=link" in page.url and "step=online" in page.url, "🟡", "adresse de l'étape 3", page.url)
            for how in ("Partager le lien…", "WhatsApp", "Messages", "QR code", "Copier"):
                check(p, sheet.get_by_role("button", name=how).count() > 0, "🟠", f"bouton « {how} » dans la feuille")
            check(p, sheet.get_by_role("button", name="Retirer Bot Max").count() > 0, "🟠", "Bot Max (cité à l'IA) coché d'avance")
            p.tap(sheet.get_by_role("button", name="Copier"), "Copier")
            page.wait_for_timeout(1500)
            clip = page.evaluate("navigator.clipboard.readText()")
            check(p, "/events/invite/" in (clip or ""), "🔴", "lien d'invitation copié", repr(clip))
            p.tap(sheet.get_by_role("button", name=re.compile("^Inviter Bot Max")), "Inviter Bot Max")
            page.wait_for_timeout(2500)
            p.shot("max-invite")
        row = ev(eid)
        p.log(f"base : {row}")
        check(p, row["status"] == "published" and row["visibility"] == "invited" and not row["public_link"], "🔴",
              "base : publié, sur invitation, sans lien public", str(row))
        check(p, row["invites"] >= 1, "🟠", "base : Bot Max invité après « Inviter Bot Max »", str(row))
        check(p, not row["ai_suggested"], "🟡", "base : personnes citées effacées après publication", str(row["ai_suggested"]))
        inv = sql(f"select count(*) n from public.event_invite_links where event_id = {q(eid)}") if _has("event_invite_links") else []
        p.log(f"liens d'invitation en base : {inv}")
        # Étape 3 rechargée : la feuille ne doit pas se rouvrir en boucle ni recréer de lien
        page.reload()
        page.wait_for_timeout(3500)
        p.shot("etape3-rechargee")
        # Étape 2 rouverte après publication
        step_again = f"/events/event/{eid}/invite"
        p.goto(step_again)
        page.wait_for_timeout(3000)
        check(p, page.get_by_text("Cet événement est déjà publié.").count() > 0, "🟠", "étape 2 rouverte : « déjà publié »")
        p.tap(page.get_by_role("button", name="Ouvrir l’événement"), "Ouvrir l'événement")
        page.wait_for_timeout(2500)
        check(p, re.search(rf"/events/event/{eid}$", page.url.split("?")[0]) is not None, "🟠", "« Ouvrir l'événement » ouvre la fiche", page.url)
        p.shot("fiche")
    finally:
        p.close()


def _has(table: str) -> bool:
    return bool(sql(f"select 1 from information_schema.tables where table_schema='public' and table_name={q(table)}"))


def phase_groupe_oscar(browser):
    """Même parcours « Un groupe » par Bot Oscar (aucun blocage avec les membres de « Bots ») : étape 3 d'un groupe."""
    out = save_draft("orga2", "Un groupe (Oscar)", 28)
    eid = out["body"]["id"]
    p = signed(browser, "orga2", "ia-groupe-oscar")
    try:
        if not step2(p, eid, f"?audience=group&groups={gid(GROUP_BOTS)}"):
            return
        page = p.page
        p.shot("etape2-preset-bots")
        c = f.chip(p, f"{GROUP_BOTS} · ").first
        check(p, c.count() > 0 and f.selected(c), "🟠", "pré-réglage « Bots » coché")
        p.tap(page.get_by_role("button", name=f"Publier pour « {GROUP_BOTS} »"), "Publier pour « Bots » (sans prévenir)")
        page.wait_for_timeout(3000)
        p.expect_or_flag(page.get_by_text("C’est en ligne !").first, "« C'est en ligne ! » (groupe)", "🟠", 40000)
        p.shot("etape3-groupe")
        p.dump("etape3-groupe")
        box = page.get_by_label("Invités", exact=True)
        p.log(f"carte « Invités » : {box.count()} ; y = {box.first.bounding_box() if box.count() else None}")
        _check_screen(p, "fiche étape 3 (groupe, Oscar)")
        row = ev(eid)
        p.log(f"base : {row}")
        check(p, row["status"] == "published" and row["groups"] == [GROUP_BOTS] and not row["announce_group"], "🔴",
              "base : publié pour « Bots », sans annonce", str(row))
    finally:
        p.close()


def phase_groupe(browser):
    """Bot Olga (iPhone, Bots + Bots 2) : pré-réglage « Bots 2 » suggéré ; aucun groupe → bouton inactif ;
    « Bots » + « Prévenir le groupe » → publié, annonce en base."""
    out = save_draft("orga1", "Un groupe", 21)
    eid = out["body"]["id"]
    save_state(e_group=eid)
    p = signed(browser, "orga1", "ia-groupe")
    try:
        if not step2(p, eid, f"?audience=group&groups={gid(GROUP_BOTS_2)}"):
            return
        page = p.page
        p.shot("etape2-preset")
        p.dump("etape2-preset")
        b2 = f.chip(p, f"{GROUP_BOTS_2} · ").first
        check(p, b2.count() > 0 and f.selected(b2), "🟠", "pré-réglage « Bots 2 » coché (groupe dit à l'IA)")
        check(p, page.get_by_text("Suggéré").count() == 1, "🟡", "une seule étiquette « Suggéré »")
        for c in page.get_by_role("button", name=re.compile(r" · \d+$")).all():
            if f.selected(c):
                p.tap(c, "décocher " + (c.get_attribute("aria-label") or c.inner_text()))
        none = page.get_by_role("button", name="Choisis un groupe")
        check(p, none.count() > 0 and none.first.is_disabled(), "🔴", "sans groupe coché : bouton « Choisis un groupe » inactif")
        # Un interrupteur dans la carte « Membres Vendredi Party » ; celui de la carte « Un groupe » disparaît sans groupe
        check(p, page.get_by_role("switch", name=re.compile("^Prévenir (le groupe|«)")).count() == 0, "🟡", "sans groupe : pas d'interrupteur « Prévenir … » dans « Un groupe »")
        p.shot("aucun-groupe")
        p.tap(f.chip(p, f"{GROUP_BOTS} · ").first, "groupe Bots")
        sw = page.get_by_label(f"Prévenir « {GROUP_BOTS} »", exact=True)  # celui de la carte « Un groupe » (fix C1 : nom propre)
        if not sw.is_checked():
            p.tap(sw, f"Prévenir « {GROUP_BOTS} » → oui")
        page.wait_for_timeout(800)
        vip_sw = page.get_by_label("Prévenir les Membres Vendredi Party", exact=True)
        vip_on = vip_sw.count() > 0 and vip_sw.first.is_checked()
        p.log(f"interrupteur de la carte Membres après celui du groupe : {vip_on} (bug 4 de la campagne : réglage partagé)")
        check(p, not vip_on, "🟡", "« Prévenir les Membres » reste éteint quand on allume « Prévenir « Bots » » (bug 4)")
        p.shot("bots-prevenir")
        p.dump("bots-prevenir")
        btn = page.get_by_role("button", name=f"Publier pour « {GROUP_BOTS} »")
        p.tap(btn, "Publier pour « Bots »")
        page.wait_for_timeout(3500)
        if f.accept_terms_if_asked(p):
            page.wait_for_timeout(3000)
        p.expect_or_flag(page.get_by_text("C’est en ligne !").first, "« C'est en ligne ! » (étape 3)", "🟠")
        check(p, "invite=more" in page.url, "🟡", "adresse « invite=more » après un groupe", page.url)
        p.shot("etape3")
        p.dump("etape3")
        _check_screen(p, "fiche étape 3 (groupe)")
        row = ev(eid)
        p.log(f"base : {row}")
        check(p, row["status"] == "published" and row["groups"] == [GROUP_BOTS] and row["visibility"] == "invited", "🔴",
              "base : publié pour « Bots » seulement", str(row))
        check(p, row["announce_group"] and row["announcements"] >= 1, "🟠", "base : « Prévenir le groupe » enregistré (annonce)", str(row))
    finally:
        p.close()


def _check_screen(p, what: str) -> None:
    p.scroll_to_bottom(what)
    cut = p.check_texts_cut(what)
    if cut:
        p.flag("🟡", f"{what} : textes coupés", "; ".join(cut))


def phase_public(browser):
    """Bot Oscar : Public (suggéré par défaut) → « C'est en ligne ! », base public + lien public, sans annonce."""
    out = save_draft("orga2", "Public", 22)
    eid = out["body"]["id"]
    save_state(e_public=eid)
    p = signed(browser, "orga2", "ia-public")
    try:
        if not step2(p, eid):
            return
        page = p.page
        pub = page.get_by_role("button", name="🌍 Public + lien public : Publier")
        p.tap(pub, "Public : Publier")
        page.wait_for_timeout(3500)
        f.accept_terms_if_asked(p)
        p.expect_or_flag(page.get_by_text("C’est en ligne !").first, "« C'est en ligne ! » (étape 3, public)", "🟠")
        p.shot("etape3-public")
        row = ev(eid)
        p.log(f"base : {row}")
        check(p, row["status"] == "published" and row["visibility"] == "all" and row["public_link"] and not row["announce_group"], "🔴",
              "base : public + lien, sans annonce", str(row))
    finally:
        p.close()


def phase_reprise(browser):
    """« Ouvrir l'événement (finir à la main) » → fiche du brouillon → « Inviter et publier » → étape 2 sans paramètre :
    Bot Max (cité, gardé avec le brouillon) coché d'avance dans la feuille Inviter."""
    out = save_draft("orga2", "Reprise brouillon", 23, invitees=["Bot Max"])
    eid = out["body"]["id"]
    save_state(e_reprise=eid)
    p = signed(browser, "orga2", "ia-reprise")
    try:
        row = ev(eid)
        check(p, row.get("ai_suggested") == [uid_of("membre3")], "🟠", "base : Bot Max gardé avec le brouillon (ai_suggested)", str(row))
        if not step2(p, eid, f"?suggested={uid_of('membre3')}"):
            return
        page = p.page
        p.tap(page.get_by_role("button", name="Ouvrir l’événement (finir à la main)"), "Ouvrir l'événement (finir à la main)")
        page.wait_for_timeout(3000)
        p.shot("fiche-brouillon")
        p.dump("fiche-brouillon")
        check(p, page.get_by_text("Ce brouillon n’est visible que par toi.").count() > 0, "🟠", "fiche : « brouillon visible que par toi »")
        # Liste des événements : le brouillon y est-il retrouvable ?
        p.goto("/events/")
        page.wait_for_timeout(3000)
        drafts = page.get_by_role("tab", name=re.compile("Brouillons")).or_(page.get_by_role("button", name=re.compile("^Brouillons")))
        if drafts.count():
            p.tap(drafts.first, "onglet Brouillons")
            page.wait_for_timeout(2500)
        else:
            p.log("onglet « Brouillons » introuvable")
        found = page.get_by_text(f"{PREFIX} Reprise brouillon").count()
        p.shot("liste-avec-brouillon")
        check(p, found > 0, "🟠", "brouillon retrouvable dans « Brouillons » (après avoir quitté)")
        p.goto(f"/events/event/{eid}")
        page.wait_for_timeout(3000)
        p.tap(page.get_by_role("button", name="Inviter et publier"), "Inviter et publier")
        page.wait_for_timeout(3000)
        p.expect_or_flag(page.get_by_role("progressbar", name=re.compile("Étape 2 sur 3")), "étape 2 rouverte depuis la fiche", "🔴")
        p.shot("etape2-rouverte")
        p.tap(page.get_by_role("button", name=INVITE_BTN), "Sur invitation seulement")
        page.wait_for_timeout(3500)
        f.accept_terms_if_asked(p)
        sheet = page.get_by_label(re.compile("^Inviter à "))
        if p.expect_or_flag(sheet, "feuille Inviter après reprise", "🔴"):
            p.shot("feuille-reprise")
            check(p, sheet.get_by_role("button", name="Retirer Bot Max").count() > 0, "🟠",
                  "reprise par « Inviter et publier » : Bot Max coché d'avance")
        row = ev(eid)
        p.log(f"base : {row}")
        check(p, row["status"] == "published" and row["invites"] == 0, "🔴", "base : publié, personne invité d'office", str(row))
        check(p, not row["ai_suggested"], "🟡", "base : ai_suggested vidé après publication", str(row))
    finally:
        p.close()


def phase_validation(browser):
    """Bot Victor (Membre VIP, sans « publier sans validation ») : « Envoyer pour validation » partout ;
    Sur invitation → « Envoyé pour validation » ; Un groupe + Prévenir → pending ; étape rouverte : « attend déjà »."""
    for kind, offset in (("invite", 24), ("group", 25)):
        post("/api/account/ai/consent", {"token": session("vip1").token, "accept": True})
        out = save_draft("vip1", f"Validation ({kind})", offset)
        if out["status"] != 200:
            note_api("🔴", f"Membre VIP : brouillon IA refusé ({kind})", str(out)[:300])
            continue
        eid = out["body"]["id"]
        save_state(**{f"e_valid_{kind}": eid})
        p = signed(browser, "vip1", f"ia-validation-{kind}")
        try:
            if not step2(p, eid):
                continue
            page = p.page
            p.shot("etape2")
            p.dump("etape2")
            check(p, page.get_by_text("Un toucher l’envoie pour validation").count() > 0, "🟠", "phrase « envoie pour validation »")
            check(p, page.get_by_role("button", name=re.compile(": Publier")).count() == 0, "🔴", "aucun bouton « Publier » sans le droit")
            if kind == "invite":
                check(p, page.get_by_text("Le lien à partager arrive dès qu’un admin a validé.").count() > 0, "🟡", "phrase du lien après validation")
                p.tap(page.get_by_role("button", name="✉️ Sur invitation seulement : Envoyer pour validation"), "Sur invitation : Envoyer pour validation")
            else:
                p.tap(page.get_by_role("button", name="👥 Des groupes", exact=True), "Un groupe")
                page.wait_for_timeout(800)
                for c in page.get_by_role("button", name=re.compile(r" · \d+$")).all():
                    if f.selected(c) and not (c.get_attribute("aria-label") or c.inner_text()).lstrip("✓ ").startswith(f"{GROUP_BOTS} · "):
                        p.tap(c, "décocher")
                c = f.chip(p, f"{GROUP_BOTS} · ").first
                if not f.selected(c):
                    p.tap(c, "Bots")
                sw = page.get_by_label(f"Prévenir « {GROUP_BOTS} »", exact=True)
                if not sw.is_checked():
                    p.tap(sw, f"Prévenir « {GROUP_BOTS} » → oui")
                p.shot("groupe-prevenir")
                buttons = page.get_by_role("button", name="Envoyer pour validation", exact=True)
                p.tap(buttons.last, "Envoyer pour validation (groupe)")
            page.wait_for_timeout(3500)
            f.accept_terms_if_asked(p)
            p.expect_or_flag(page.get_by_text("Envoyé pour validation").first, "« Envoyé pour validation » (étape 3)", "🔴")
            p.shot("etape3")
            p.dump("etape3")
            check(p, page.get_by_role("button", name="Partager le lien…").count() == 0, "🟠", "pas de lien avant la validation")
            if kind == "invite":
                check(p, page.get_by_text(re.compile("sera disponible dès la validation")).count() > 0, "🟡",
                      "étape 3 : « lien disponible dès la validation »")
            row = ev(eid)
            p.log(f"base : {row}")
            check(p, row["status"] == "pending", "🔴", "base : en attente de validation", str(row))
            if kind == "group":
                check(p, row["announce_group"] and row["groups"] == [GROUP_BOTS], "🟠", "base : groupe Bots + annonce demandée", str(row))
            p.goto(f"/events/event/{eid}/invite")
            page.wait_for_timeout(3000)
            check(p, page.get_by_text("Cet événement attend déjà sa validation.").count() > 0, "🟠", "étape 2 rouverte : « attend déjà »")
            p.shot("etape2-rouverte")
        finally:
            p.close()


def phase_quitter(browser):
    """Quitter au milieu (Événements, retour arrière, rechargement), perte réseau, double toucher, autre compte."""
    out = save_draft("orga2", "Quitter et revenir", 26)
    eid = out["body"]["id"]
    save_state(e_quit=eid)
    p = signed(browser, "orga2", "ia-quitter")
    try:
        if not step2(p, eid):
            return
        page = p.page
        p.tap(page.get_by_role("button", name=re.compile("Événements")).first, "‹ Événements (quitter)")
        page.wait_for_timeout(2500)
        p.shot("apres-quitter")
        check(p, ev(eid)["status"] == "draft", "🔴", "base : toujours brouillon après avoir quitté")
        page.go_back()
        page.wait_for_timeout(3000)
        p.shot("retour-arriere")
        p.log(f"après retour arrière : {page.url}")
        # Revenir : la même adresse rouvre l'étape 2 (brouillon intact), et un rechargement la garde
        step2(p, eid)
        page.reload()
        page.wait_for_timeout(3500)
        p.expect_or_flag(page.get_by_role("progressbar", name=re.compile("Étape 2 sur 3")), "étape 2 après rechargement", "🟠", 40000)
        # Perte réseau au toucher
        p.ctx.set_offline(True)
        p.tap(page.get_by_role("button", name=INVITE_BTN), "Sur invitation (hors ligne)")
        page.wait_for_timeout(4000)
        p.shot("hors-ligne")
        p.dump("hors-ligne")
        err = page.get_by_text(re.compile("réseau|connexion|Failed to fetch|fetch|hors ligne", re.I))
        check(p, err.count() > 0, "🟠", "hors ligne : message d'erreur affiché")
        btn = page.get_by_role("button", name=INVITE_BTN)
        check(p, btn.count() > 0 and btn.first.is_enabled(), "🟠", "hors ligne : bouton à nouveau actif (pas bloqué)")
        p.ctx.set_offline(False)
        page.wait_for_timeout(1500)
        row = ev(eid)
        p.log(f"base après échec réseau : {row}")
        check(p, row["status"] == "draft", "🔴", "base : rien publié hors ligne", str(row))
        # Double toucher
        p.log("double toucher sur « Sur invitation seulement »")
        btn.first.tap()
        try:
            btn.first.tap(timeout=1500, no_wait_after=True)
        except Exception as e:
            p.log(f"2e toucher non reçu (bouton déjà occupé) : {str(e).splitlines()[0][:120]}")
        page.wait_for_timeout(4000)
        p.shot("double-toucher")
        check(p, page.get_by_label(re.compile("^Inviter à ")).count() > 0, "🟠", "double toucher : la feuille Inviter s'ouvre une fois")
        row = ev(eid)
        p.log(f"base après double toucher : {row}")
        check(p, row["status"] == "published", "🔴", "base : publié après double toucher", str(row))
        errs = (p.dir / "errors.log")
        if errs.exists():
            p.log("erreurs (fin) : " + errs.read_text()[-800:])
    finally:
        p.close()
    # Un autre compte ouvre l'étape 2 d'un brouillon d'Oscar
    out = save_draft("orga2", "Brouillon d'Oscar", 27)
    other = out["body"]["id"]
    save_state(e_other=other)
    p = signed(browser, "orga1", "ia-autre-compte")
    try:
        p.goto(f"/events/event/{other}/invite")
        try:
            p.page.get_by_role("alert").or_(p.page.get_by_role("button", name="Réessayer")).first.wait_for(timeout=40000)
        except Exception:
            p.log("ni message ni « Réessayer » après 40 s")
        p.shot("brouillon-d-un-autre")
        p.dump("brouillon-d-un-autre")
        check(p, p.page.get_by_role("button", name=INVITE_BTN).count() == 0, "🔴", "autre compte : aucun bouton pour publier le brouillon d'Oscar")
        check(p, ev(other)["status"] == "draft", "🔴", "base : brouillon d'Oscar intact")
    finally:
        p.close()


def phase_autre(browser):
    """Seulement le cas « autre compte » de phase_quitter (Bot Olga ouvre l'étape 2 d'un brouillon de Bot Oscar)."""
    out = save_draft("orga2", "Brouillon d'Oscar", 27)
    other = out["body"]["id"]
    p = signed(browser, "orga1", "ia-autre-compte")
    try:
        p.goto(f"/events/event/{other}/invite")
        try:
            p.page.get_by_role("alert").or_(p.page.get_by_role("button", name="Réessayer")).first.wait_for(timeout=40000)
        except Exception:
            p.log("ni message ni « Réessayer » après 40 s")
        p.shot("brouillon-d-un-autre")
        p.log("écran : " + p.dump("brouillon-d-un-autre").replace("\n", " | ")[:600])
        check(p, p.page.get_by_role("button", name=INVITE_BTN).count() == 0, "🔴", "autre compte : aucun bouton pour publier le brouillon d'Oscar")
    finally:
        p.close()


def phase_groupe_bloque(browser):
    """Relance du bug 1 : Bot Olga bloque Bot Gus (membre de « Bots »), puis publie pour « Bots » depuis l'étape 2.
    Attendu (fix A) : publié, Gus sauté sans rien dire, les autres membres invités ; le blocage est retiré à la fin."""
    olga, gus = session("orga1"), session("guest1")
    r = olga.rpc("set_block", target=gus.uid, blocked=True)
    print("blocage Olga → Gus", r.status_code, r.text[:200], flush=True)
    try:
        out = save_draft("orga1", "Groupe avec un bloqué", 29)
        eid = out["body"]["id"]
        save_state(e_group_block=eid)
        p = signed(browser, "orga1", "ia-groupe-bloque")
        try:
            if not step2(p, eid, f"?audience=group&groups={gid(GROUP_BOTS)}"):
                return
            page = p.page
            c = f.chip(p, f"{GROUP_BOTS} · ").first
            if not f.selected(c):
                p.tap(c, "groupe Bots")
            p.shot("etape2-bots")
            p.tap(page.get_by_role("button", name=f"Publier pour « {GROUP_BOTS} »"), "Publier pour « Bots » (Gus bloqué)")
            page.wait_for_timeout(3500)
            if f.accept_terms_if_asked(p):
                page.wait_for_timeout(3000)
            ok = p.expect_or_flag(page.get_by_text("C’est en ligne !").first, "« C'est en ligne ! » malgré un membre bloqué (bug 1)", "🔴", 40000)
            p.shot("etape3-ou-erreur")
            p.dump("etape3-ou-erreur")
            if not ok:
                p.log("écran : " + p.dump("erreur").replace("\n", " | ")[:600])
            row = ev(eid)
            p.log(f"base : {row}")
            check(p, row["status"] == "published" and row["groups"] == [GROUP_BOTS], "🔴", "base : publié pour « Bots » (bug 1)", str(row))
            inv = sql(f"""select p.display_name n from public.event_invites i join public.profiles p on p.id = i.user_id
                where i.event_id = {q(eid)} order by 1""")
            names = [x["n"] for x in inv]
            p.log(f"invités en base : {names}")
            check(p, not any("Gus" in n for n in names), "🔴", "Bot Gus (bloqué) n'est pas invité", str(names))
            check(p, any("Victor" in n for n in names), "🟠", "les autres membres de « Bots » sont invités", str(names))
        finally:
            p.close()
    finally:
        r = olga.rpc("set_block", target=gus.uid, blocked=False)
        print("blocage retiré", r.status_code, r.text[:200], flush=True)


def phase_echec_etape2(browser):
    """Nouveau (fix C1 n° 2) : l'écriture du statut échoue (réseau coupé sur ce seul PATCH) après « qui voit » →
    message « Rien n'est publié », brouillon remis comme avant (visibilité, groupes, sans annonce) ; nouvel essai OK."""
    out = save_draft("orga1", "Echec etape 2", 35)
    eid = out["body"]["id"]
    before = ev(eid)
    p = signed(browser, "orga1", "ia-echec-etape2")
    try:
        if not step2(p, eid, f"?audience=group&groups={gid(GROUP_BOTS_2)}"):
            return
        page = p.page
        failed: list[str] = []

        def fail_status(route):
            req = route.request
            body = req.post_data or ""
            if req.method == "PATCH" and '"status"' in body:
                failed.append(body[:200])
                return route.abort("internetdisconnected")
            return route.continue_()

        page.route("**/rest/v1/events*", fail_status)
        c = f.chip(p, f"{GROUP_BOTS_2} · ").first
        if not f.selected(c):
            p.tap(c, "groupe Bots 2")
        sw = page.get_by_label(f"Prévenir « {GROUP_BOTS_2} »", exact=True)
        if sw.count() and not sw.is_checked():
            p.tap(sw, f"Prévenir « {GROUP_BOTS_2} » → oui")
        p.tap(page.get_by_role("button", name=f"Publier pour « {GROUP_BOTS_2} »"), "Publier (statut coupé)")
        page.wait_for_timeout(5000)
        f.accept_terms_if_asked(p)
        page.wait_for_timeout(2000)
        p.shot("echec-statut")
        txt = p.dump("echec-statut")
        p.log(f"PATCH du statut coupés : {failed}")
        check(p, "Rien n’est publié" in txt or "Rien n'est publié" in txt, "🟠", "message « Rien n'est publié, le brouillon est resté tel quel »", txt[:400].replace("\n", " | "))
        row = ev(eid)
        p.log(f"base avant : {before} ; après l'échec : {row}")
        check(p, row["status"] == "draft" and not row["announce_group"], "🔴", "base : toujours brouillon, sans annonce", str(row))
        check(p, row["visibility"] == before["visibility"] and row["groups"] == before["groups"], "🟡",
              "base : « qui voit » et groupes remis comme avant", f"avant {before} / après {row}")
        page.unroute("**/rest/v1/events*")
        p.tap(page.get_by_role("button", name=f"Publier pour « {GROUP_BOTS_2} »"), "Publier (nouvel essai)")
        page.wait_for_timeout(4000)
        f.accept_terms_if_asked(p)
        p.expect_or_flag(page.get_by_text("C’est en ligne !").first, "nouvel essai : « C'est en ligne ! »", "🔴", 40000)
        p.shot("nouvel-essai")
        row = ev(eid)
        p.log(f"base après le nouvel essai : {row}")
        check(p, row["status"] == "published" and row["groups"] == [GROUP_BOTS_2] and row["announce_group"], "🔴",
              "base : publié pour « Bots 2 » avec l'annonce", str(row))
    finally:
        p.close()


def phase_valider_ia(browser):
    """« Non testé » de la campagne : Bot Côme (co-admin) approuve les deux propositions IA de Bot Victor ; Victor
    retrouve alors son événement en ligne et le lien d'invitation (feuille Inviter)."""
    st = load_state()
    for kind in ("invite", "group"):
        eid = st.get(f"e_valid_{kind}")
        if not eid:
            continue
        p = signed(browser, "coadmin", f"ia-valider-{kind}")
        try:
            p.goto(f"/events/event/{eid}")
            p.page.wait_for_timeout(3500)
            p.shot("proposition")
            p.tap(p.page.get_by_role("button", name="Approuver"), "Approuver")
            p.page.wait_for_timeout(3500)
            p.shot("approuvee")
            row = ev(eid)
            p.log(f"base : {row}")
            check(p, row["status"] == "published", "🔴", f"Approuver publie la proposition IA ({kind})", str(row))
            if kind == "group":
                check(p, row["announcements"] >= 1, "🟠", "annonce demandée par Victor créée à la validation", str(row))
        finally:
            p.close()
        if kind != "invite":
            continue
        p = signed(browser, "vip1", "ia-valide-victor")
        try:
            p.goto(f"/events/event/{eid}")
            p.page.wait_for_timeout(3500)
            p.shot("fiche-validee")
            txt = p.dump("fiche-validee")
            invite = p.page.get_by_role("button", name=re.compile("^(Inviter|Partager)"))
            check(p, invite.count() > 0, "🟠", "Victor : bouton Inviter / Partager sur son événement validé", txt[:300].replace("\n", " | "))
            if invite.count():
                p.tap(invite.first, invite.first.inner_text()[:40])
                p.page.wait_for_timeout(3000)
                f.accept_terms_if_asked(p)
                sheet = p.page.get_by_label(re.compile("^Inviter à "))
                if p.expect_or_flag(sheet, "feuille Inviter après validation", "🟠", 15000):
                    p.shot("feuille-apres-validation")
                    p.tap(sheet.get_by_role("button", name="Copier"), "Copier")
                    p.page.wait_for_timeout(1500)
                    clip = p.page.evaluate("navigator.clipboard.readText()")
                    check(p, "/events/invite/" in (clip or ""), "🟠", "lien d'invitation copié après validation", repr(clip))
        finally:
            p.close()


PHASES = {"valider_ia": phase_valider_ia, "groupe_bloque": phase_groupe_bloque, "echec_etape2": phase_echec_etape2, "autre": phase_autre, "groupe_oscar": phase_groupe_oscar, "api": phase_api, "invite": phase_invite, "groupe": phase_groupe, "public": phase_public,
          "reprise": phase_reprise, "validation": phase_validation, "quitter": phase_quitter}


def cleanup() -> None:
    n = sql(f"delete from public.events where title like {q(PREFIX + '%')} returning id")
    print(f"événements {PREFIX} supprimés : {len(n or [])}", flush=True)


def main(argv: list[str]) -> None:
    if argv == ["cleanup"]:
        return cleanup()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                PHASES[name](browser)
            except Exception as e:  # une phase cassée devient une anomalie, la suite continue
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
