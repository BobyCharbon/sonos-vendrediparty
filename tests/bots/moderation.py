"""Campagne 2, agent 08 — droits, confidentialité, modération (base de TEST, CGU exigées).

Sondes directes de la base avec le jeton de chaque bot (l'écran n'est jamais le seul garde-fou), puis vrais écrans :
· CGU : première action de chaque type de contenu sans les avoir acceptées (forum, petit mot, à apporter, option de
  sondage, événement) ;
· filtre : titre, description, forum, petit mot, à apporter, option de sondage (insulte masquée / propos haineux refusés) ;
· signaler : événement, message du forum, profil ; « réponse » (petit mot) ;
· bloquer : invitations refusées, messages et notifications ;
· groupes : un bot hors d'un groupe ne voit ni ne choisit ce groupe (formulaire, Inviter, API).
Événements préfixés « [C2-08] », créés en SQL (aucune notification) puis supprimés à la fin.
Usage : BOTS_OUT=… .venv/bin/python -m tests.bots.run moderation_api moderation_ui"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import httpx

from tests.bots.bench import OUT, anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, TEST_URL, Session, q, sql

PREFIX = "[C2-08]"
INSULT = "t'es un connard"          # insulte d'un mot : masquée dans un message, refusée ailleurs
HATE = "sale arabe"                 # propos haineux : refusé partout
DISGUISED = "s@l0pe"                # contournement simple


def iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def rest(s: Session, method: str, path: str, **kw) -> httpx.Response:
    headers = {**s.headers, "Prefer": "return=representation", **kw.pop("headers", {})}
    return httpx.request(method, f"{TEST_URL}/rest/v1/{path}", headers=headers, timeout=30, **kw)


def make_event(title: str, by: str, invited: list[str], **fields) -> str:
    """Événement créé en SQL (sans session : ni filtre ni notification), invités ajoutés en SQL."""
    cols = {"title": f"{PREFIX} {title}", "description": "Recette campagne 2 (droits, modération). Ignorer.",
            "created_by": uid(by), "status": "published", "date_mode": "fixed", "starts_at": iso(18),
            "visibility": "invited", "notify_on_publish": False, "forum_enabled": True, **fields}
    names = ", ".join(cols)
    values = ", ".join("null" if v is None else (str(v).lower() if isinstance(v, bool) else q(v)) for v in cols.values())
    eid = sql(f"insert into public.events ({names}) values ({values}) returning id")[0]["id"]
    for key in invited:
        sql(f"insert into public.event_invites (event_id, user_id) values ({q(eid)}, {q(uid(key))}) on conflict do nothing")
    events = load_state().get("c2_events", [])
    save_state(c2_events=events + [eid])
    return eid


class Probe:
    def __init__(self):
        self.rows: list[dict] = []

    def rec(self, area: str, case: str, expected: str, observed: str, ok: bool, sev: str = "🟠", detail: str = "") -> None:
        row = {"area": area, "case": case, "expected": expected, "observed": observed, "ok": ok, "detail": detail[:300]}
        self.rows.append(row)
        print(f"{'✅' if ok else sev} [{area}] {case} — attendu {expected} — observé {observed} {detail[:160]}", flush=True)
        if not ok:
            anomaly("api", sev, f"[{area}] {case}", f"attendu : {expected} ; observé : {observed} ; {detail[:400]}")

    def save(self, name: str) -> None:
        (OUT / name).write_text(json.dumps(self.rows, indent=1, ensure_ascii=False))


def refused(r: httpx.Response, word: str) -> bool:
    return r.status_code >= 400 and word in r.text


# ── CGU : première action de chaque type de contenu (compte sans acceptation) ──
def cgu(pr: Probe, eid: str) -> None:
    for key in ("membre3", "guest2"):
        rows = sql(f"select count(*) n from public.terms_acceptances where user_id = {q(uid(key))}")
        if rows[0]["n"]:
            print(f"{key} a déjà accepté les CGU : sondes CGU sautées pour lui")
            continue
        s = Session(BY_KEY[key].phone)
        who = BY_KEY[key].nickname
        r = rest(s, "POST", "messages", json={"event_id": eid, "user_id": s.uid, "body": "Premier message sans CGU"})
        pr.rec("CGU", f"{who} : premier message du forum", "refus terms_required", f"{r.status_code}", refused(r, "terms_required"), "🔴", r.text[:200])
        r = rest(s, "POST", "rsvps", json={"event_id": eid, "user_id": s.uid, "status": "yes", "note": "Petit mot sans CGU"})
        pr.rec("CGU", f"{who} : premier petit mot (réponse avec mot)", "refus terms_required", f"{r.status_code} note={r.json()[0].get('note') if r.status_code < 300 and r.json() else None}",
               refused(r, "terms_required"), "🟠", r.text[:200])
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(s.uid)}")
        r = rest(s, "POST", "rsvps", json={"event_id": eid, "user_id": s.uid, "status": "yes"})
        pr.rec("CGU", f"{who} : répondre Présent sans mot (pas un contenu)", "permis", f"{r.status_code}", r.status_code < 300, "🔴", r.text[:200])
        r = rest(s, "POST", "bring_items", json={"event_id": eid, "label": "Chips sans CGU", "added_by": s.uid})
        pr.rec("CGU", f"{who} : premier « à apporter » ajouté", "refus terms_required", f"{r.status_code}", refused(r, "terms_required"), "🟡", r.text[:200])
        poll = load_state()["c2_poll"]
        r = rest(s, "POST", "poll_options", json={"poll_id": poll, "label": "Option sans CGU", "created_by": s.uid})
        pr.rec("CGU", f"{who} : première option de sondage proposée", "refus terms_required", f"{r.status_code}", refused(r, "terms_required"), "🟡", r.text[:200])
        r = rest(s, "POST", "events", json={"title": f"{PREFIX} sans CGU", "created_by": s.uid, "status": "draft", "date_mode": "fixed",
                                            "starts_at": iso(19), "visibility": "invited", "notify_on_publish": False})
        if r.status_code < 300 and r.json():
            sql(f"delete from public.events where id = {q(r.json()[0]['id'])}")
        pr.rec("CGU", f"{who} : premier événement (brouillon)", "refus terms_required ou droit", f"{r.status_code}",
               r.status_code >= 400, "🔴", r.text[:200])
        r = s.rpc("report_content", p_kind="event", p_target=eid, p_reason="spam", p_comment="Banc C2-08 sans CGU")
        pr.rec("CGU", f"{who} : signaler sans CGU (doit rester possible)", "permis", f"{r.status_code}", r.status_code < 300, "🟠", r.text[:200])
        sql(f"delete from public.content_reports where reporter_id = {q(s.uid)} and target_id = {q(eid)}")
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(s.uid)}")
        sql(f"delete from public.bring_items where event_id = {q(eid)} and added_by = {q(s.uid)}")
        sql(f"delete from public.poll_options where poll_id = {q(poll)} and created_by = {q(s.uid)}")
        sql(f"delete from public.messages where event_id = {q(eid)} and user_id = {q(s.uid)}")


def accept(s: Session) -> None:
    version = sql("select terms_version from private.moderation_settings where id = 1")[0]["terms_version"]
    s.rpc("accept_terms", p_version=version)


# ── Filtre de contenu ──
def content_filter(pr: Probe, eid: str) -> None:
    marc = Session(BY_KEY["membre1"].phone)
    olga = Session(BY_KEY["orga1"].phone)
    accept(marc)
    accept(olga)
    poll = load_state()["c2_poll"]
    for text, kind in ((INSULT, "insulte"), (HATE, "haine"), (DISGUISED, "insulte déguisée")):
        r = rest(marc, "POST", "messages", json={"event_id": eid, "user_id": marc.uid, "body": text})
        body = r.json()[0]["body"] if r.status_code < 300 and r.json() else None
        if kind == "haine":
            pr.rec("filtre", f"forum : « {text} » ({kind})", "refus content_refused", f"{r.status_code} {body}", refused(r, "content_refused"), "🔴", r.text[:200])
        else:
            pr.rec("filtre", f"forum : « {text} » ({kind})", "masqué (••••)", f"{r.status_code} {body}", bool(body) and "•" in body, "🔴", r.text[:200])
        # petit mot
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(marc.uid)}")
        r = rest(marc, "POST", "rsvps", json={"event_id": eid, "user_id": marc.uid, "status": "yes", "note": text})
        note = r.json()[0].get("note") if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"petit mot : « {text} » ({kind})", "refusé ou masqué", f"{r.status_code} note={note!r}",
               r.status_code >= 400 or (note is not None and "•" in note), "🟠", r.text[:200])
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(marc.uid)}")
        # à apporter
        r = rest(marc, "POST", "bring_items", json={"event_id": eid, "label": f"Chips {text}", "added_by": marc.uid})
        label = r.json()[0].get("label") if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"à apporter : « Chips {text} » ({kind})", "refusé ou masqué", f"{r.status_code} label={label!r}",
               r.status_code >= 400 or (label is not None and "•" in label), "🟡", r.text[:200])
        # option de sondage
        r = rest(marc, "POST", "poll_options", json={"poll_id": poll, "label": f"Option {text}", "created_by": marc.uid})
        label = r.json()[0].get("label") if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"option de sondage : « Option {text} » ({kind})", "refusé ou masqué", f"{r.status_code} label={label!r}",
               r.status_code >= 400 or (label is not None and "•" in label), "🟡", r.text[:200])
        # titre / description d'un événement (organisatrice)
        r = rest(olga, "POST", "events", json={"title": f"{PREFIX} Soirée {text}", "created_by": olga.uid, "status": "draft",
                                               "date_mode": "fixed", "starts_at": iso(19), "visibility": "invited", "notify_on_publish": False})
        if r.status_code < 300 and r.json():
            sql(f"delete from public.events where id = {q(r.json()[0]['id'])}")
        pr.rec("filtre", f"titre d'événement : « Soirée {text} » ({kind})", "refus content_refused", f"{r.status_code}",
               refused(r, "content_refused"), "🔴", r.text[:200])
        r = rest(olga, "PATCH", f"events?id=eq.{eid}", json={"description": f"Venez nombreux, {text}"})
        desc = sql(f"select description from public.events where id = {q(eid)}")[0]["description"]
        sql(f"update public.events set description = 'Recette campagne 2 (droits, modération). Ignorer.' where id = {q(eid)}")
        pr.rec("filtre", f"description modifiée : « …{text} » ({kind})", "refus content_refused", f"{r.status_code} base={desc[:50]!r}",
               refused(r, "content_refused") and text not in desc, "🔴", r.text[:200])
        r = rest(olga, "POST", "polls", json={"event_id": eid, "question": f"Question {text} ?", "created_by": olga.uid})
        qtext = r.json()[0].get("question") if r.status_code < 300 and r.json() else None
        if r.status_code < 300 and r.json():
            sql(f"delete from public.polls where id = {q(r.json()[0]['id'])}")
        pr.rec("filtre", f"question de sondage : « Question {text} ? » ({kind})", "refusé ou masqué", f"{r.status_code} {qtext!r}",
               r.status_code >= 400 or (qtext is not None and "•" in qtext), "🟡", r.text[:200])
    # mise à jour d'un message (contournement par modification)
    r = rest(marc, "POST", "messages", json={"event_id": eid, "user_id": marc.uid, "body": "Message propre"})
    if r.status_code < 300:
        mid = r.json()[0]["id"]
        r2 = rest(marc, "PATCH", f"messages?id=eq.{mid}", json={"body": HATE})
        body = sql(f"select body from public.messages where id = {q(mid)}")[0]["body"]
        pr.rec("filtre", "forum : message propre puis modifié en propos haineux", "refus", f"{r2.status_code} base={body!r}", body == "Message propre", "🔴", r2.text[:200])
        save_state(c2_clean_message=mid)
    sql(f"delete from public.bring_items where event_id = {q(eid)} and added_by = {q(marc.uid)}")
    sql(f"delete from public.poll_options where poll_id = {q(poll)} and created_by = {q(marc.uid)}")


# ── Signaler ──
def reports(pr: Probe, eid: str) -> None:
    gina = Session(BY_KEY["guest2"].phone)
    olga = Session(BY_KEY["orga1"].phone)
    marc_uid = uid("membre1")
    mid = load_state().get("c2_clean_message")
    cases = [("event", eid, "l'événement"), ("event_message", mid, "un message du forum"), ("profile", marc_uid, "le profil de Bot Marc")]
    for kind, target, what in cases:
        r = gina.rpc("report_content", p_kind=kind, p_target=target, p_reason="harassment", p_comment="Banc C2-08, à ignorer")
        rows = sql(f"select status, target_user from public.content_reports where target_kind = {q(kind)} and target_id = {q(target)} and reporter_id = {q(gina.uid)}")
        pr.rec("signaler", f"Bot Gina signale {what} (API)", "enregistré", f"{r.status_code} {rows}", r.status_code < 300 and bool(rows), "🔴", r.text[:200])
        r = gina.rpc("report_content", p_kind=kind, p_target=target, p_reason="spam")
        n = sql(f"select count(*) n from public.content_reports where target_kind = {q(kind)} and target_id = {q(target)} and reporter_id = {q(gina.uid)}")[0]["n"]
        pr.rec("signaler", f"Bot Gina signale deux fois {what}", "un seul signalement (raison mise à jour)", f"{r.status_code} n={n}", n == 1, "🟡")
    r = olga.rpc("report_content", p_kind="event", p_target=eid, p_reason="spam")
    pr.rec("signaler", "l'organisatrice signale son propre événement", "refus self", f"{r.status_code}", refused(r, "self"), "🟡", r.text[:200])
    # Événement invisible pour le bot : pas de signalement (pas d'oracle sur l'existence).
    hidden = make_event("Invisible pour Gina", "orga1", [])
    r = gina.rpc("report_content", p_kind="event", p_target=hidden, p_reason="spam")
    pr.rec("signaler", "signaler un événement qu'on ne voit pas", "refus not_found", f"{r.status_code}", refused(r, "not_found"), "🟠", r.text[:200])
    r = gina.rpc("report_content", p_kind="rsvp", p_target=marc_uid, p_reason="spam")
    pr.rec("signaler", "signaler une réponse / un petit mot (target rsvp)", "possible (contenu de membre visible)", f"{r.status_code}",
           r.status_code < 300, "🟡", r.text[:200])
    # Lire les signalements des autres
    r = rest(gina, "GET", "content_reports?select=id,reporter_id")
    others = [x for x in (r.json() if r.status_code < 300 else []) if x["reporter_id"] != gina.uid]
    pr.rec("signaler", "Bot Gina lit les signalements des autres (REST)", "aucun", f"{len(others)}", not others, "🔴")
    r = gina.rpc("moderation_queue")
    pr.rec("signaler", "Bot Gina (Guest) lit la file de modération", "refus forbidden", f"{r.status_code}", refused(r, "forbidden"), "🔴", r.text[:120])
    rid = sql(f"select id from public.content_reports where reporter_id = {q(gina.uid)} and target_kind = 'event' and target_id = {q(eid)}")
    if rid:
        r = gina.rpc("moderation_act", p_report=rid[0]["id"], p_action="dismiss")
        pr.rec("signaler", "Bot Gina classe son propre signalement (moderation_act)", "refus forbidden", f"{r.status_code}", refused(r, "forbidden"), "🔴", r.text[:120])
        coadmin = Session(BY_KEY["coadmin"].phone)
        r = coadmin.rpc("moderation_queue")
        pr.rec("signaler", "Bot Côme (Co-admin) lit la file de modération", "selon le rôle (moderation.reports)", f"{r.status_code}",
               True, "🟡", r.text[:120])


# ── Bloquer ──
def blocking(pr: Probe, eid: str) -> None:
    olga = Session(BY_KEY["orga1"].phone)
    gus = Session(BY_KEY["guest1"].phone)
    accept(gus)
    r = olga.rpc("set_block", target=gus.uid, blocked=True)
    pr.rec("bloquer", "Bot Olga bloque Bot Gus", "ok", f"{r.status_code}", r.status_code < 300, "🔴", r.text[:200])
    sql(f"delete from public.event_invites where event_id = {q(eid)} and user_id = {q(gus.uid)}")
    r = rest(olga, "POST", "event_invites", json={"event_id": eid, "user_id": gus.uid})
    pr.rec("bloquer", "Bot Olga invite Bot Gus (bloqué) à son événement", "refus blocked", f"{r.status_code}", refused(r, "blocked"), "🔴", r.text[:200])
    # Gus invité malgré tout (en SQL) : son message dans le forum, Olga mentionnée → pas de notification, mention retirée
    sql(f"insert into public.event_invites (event_id, user_id) values ({q(eid)}, {q(gus.uid)}) on conflict do nothing")
    r = rest(gus, "POST", "messages", json={"event_id": eid, "user_id": gus.uid, "body": "Coucou @Olga du bloqué", "mentions": [olga.uid]})
    m = r.json()[0] if r.status_code < 300 and r.json() else {}
    pr.rec("bloquer", "mention d'Olga par Bot Gus (bloqué)", "mention retirée", f"{r.status_code} mentions={m.get('mentions')}",
           r.status_code < 300 and not m.get("mentions"), "🟠", r.text[:200])
    if m:
        save_state(c2_blocked_message=m["id"])
        n = sql(f"select count(*) n from public.notifications where user_id = {q(olga.uid)} and event_id = {q(eid)} and created_at > now() - interval '2 minutes'")[0]["n"]
        pr.rec("bloquer", "notification à Olga pour le message de Gus (bloqué)", "aucune", f"{n}", n == 0, "🟠")
    r = olga.rpc("member_card", target=gus.uid)
    pr.rec("bloquer", "Olga ouvre la fiche de Gus (qu'elle a bloqué)", "blocked=true", r.text[:120], '"blocked": true' in r.text or '"blocked":true' in r.text, "🟡")
    r = gus.rpc("member_card", target=olga.uid)
    pr.rec("bloquer", "Gus (bloqué) ouvre la fiche d'Olga", "fiche réduite (restricted)", r.text[:160],
           '"restricted": true' in r.text or '"restricted":true' in r.text, "🟠")
    # Les messages de Gus restent-ils lisibles par Olga (forum) ?
    r = rest(olga, "GET", f"messages?event_id=eq.{eid}&user_id=eq.{gus.uid}&select=id,body")
    pr.rec("bloquer", "Olga lit encore les messages du forum de Gus (base)", "information (l'écran doit les masquer)",
           f"{len(r.json()) if r.status_code < 300 else r.status_code}", True)


# ── Groupes : Bot Violette (dans « Bots 2 », pas dans « Bots ») ──
def groups(pr: Probe) -> None:
    v = Session(BY_KEY["vip4"].phone)
    accept(v)
    gid = {g["name"]: g["id"] for g in sql("select id, name from public.member_groups where name in ('Bots', 'Bots 2')")}
    r = rest(v, "GET", f"member_groups?id=eq.{gid['Bots']}&select=id,name")
    seen = r.status_code < 300 and bool(r.json())
    pr.rec("groupes", "Violette (hors « Bots ») lit le groupe « Bots » (REST)", "invisible", f"{r.status_code} {r.text[:80]}", not seen, "🟠")
    r = rest(v, "GET", f"group_members?group_id=eq.{gid['Bots']}&select=user_id")
    seen = r.status_code < 300 and bool(r.json())
    pr.rec("groupes", "Violette lit les membres de « Bots »", "invisible", f"{r.status_code} n={len(r.json()) if r.status_code < 300 else '-'}", not seen, "🟠")
    own = make_event("Événement de Violette", "vip4", [])
    for name in ("Bots", "Bots 2"):
        r = rest(v, "POST", "event_groups", json={"event_id": own, "group_id": gid[name]})
        expected = name == "Bots 2"
        pr.rec("groupes", f"Violette met « {name} » sur son événement (API)", "permis" if expected else "refus",
               f"{r.status_code}", (r.status_code < 300) == expected, "🔴", r.text[:200])
        sql(f"delete from public.event_groups where event_id = {q(own)}")
    # Événement réservé au groupe « Bots » : invisible pour Violette
    only_bots = make_event("Réservé au groupe Bots", "orga1", [])
    sql(f"insert into public.event_groups (event_id, group_id, status) values ({q(only_bots)}, {q(gid['Bots'])}, 'approved') on conflict do nothing")
    r = rest(v, "GET", f"events?id=eq.{only_bots}&select=id,title")
    pr.rec("groupes", "Violette lit un événement réservé à « Bots » (REST)", "invisible", f"{r.status_code} {r.text[:80]}",
           r.status_code < 300 and r.json() == [], "🔴")
    r = rest(v, "GET", f"event_groups?event_id=eq.{only_bots}&select=group_id")
    pr.rec("groupes", "Violette lit les groupes de cet événement", "invisible", r.text[:80], r.status_code >= 300 or r.json() == [], "🟡")
    save_state(c2_only_bots=only_bots, c2_violette_event=own)


def phase_moderation_api(browser, origin, only):
    pr = Probe()
    eid = make_event("Modération (forum, petit mot, à apporter)", "orga1",
                     ["membre1", "membre3", "guest2", "guest1", "vip1", "vip4"], allow_plus_ones=True, max_plus_ones=2)
    save_state(c2_mod_event=eid)
    poll = sql(f"insert into public.polls (event_id, question, created_by, members_can_add_options) values ({q(eid)}, 'Quel jour ?', {q(uid('orga1'))}, true) returning id")[0]["id"]
    save_state(c2_poll=poll)
    for step in (cgu, content_filter, reports, blocking):
        try:
            step(pr, eid)
        except Exception as e:  # une sonde cassée devient une anomalie
            anomaly("api", "🟠", f"sonde {step.__name__} interrompue", f"{type(e).__name__}: {str(e)[:400]}")
            print(f"sonde {step.__name__} interrompue : {e}")
        pr.save("moderation-api.json")
    try:
        groups(pr)
    except Exception as e:
        anomaly("api", "🟠", "sonde groupes interrompue", f"{type(e).__name__}: {str(e)[:400]}")
    pr.save("moderation-api.json")


def phase_moderation_cleanup(browser, origin, only):
    st = load_state()
    olga, gus = uid("orga1"), uid("guest1")
    sql(f"delete from public.direct_blocks where user_id = {q(olga)} and blocked_id = {q(gus)}")
    sql(f"delete from public.direct_blocks where user_id = {q(uid('membre3'))} and blocked_id = {q(gus)}")
    for eid in st.get("c2_events", []):
        sql(f"delete from public.content_reports where target_kind = 'event' and target_id = {q(eid)}")
        sql(f"delete from public.content_reports where target_kind = 'event_message' and target_id in (select id::text from public.messages where event_id = {q(eid)})")
        sql(f"delete from public.events where id = {q(eid)}")
    sql(f"delete from public.events where title like {q(PREFIX + '%')}")
    sql("delete from public.content_reports where comment like 'Banc C2-08%'")
    sql("delete from public.moderation_sanctions where note like 'Avertissement du banc C2-08%'")
    sql("delete from public.notifications where kind = 'moderation_notice' and body like 'Avertissement du banc C2-08%'")
    print("événements [C2-08] et leurs signalements supprimés ; blocages retirés")


# ── Vrais écrans ──────────────────────────────────────────────────────────────────────────────────────────────

def _buttons(p) -> list[str]:
    """Noms des boutons visibles sur l'écran (arbre d'accessibilité)."""
    names = p.page.get_by_role("button").evaluate_all(
        "els => els.filter(e => e.offsetParent !== null).map(e => (e.getAttribute('aria-label') || e.innerText || '').trim().slice(0, 50))")
    return sorted({n for n in names if n})


def _open_event(p, eid: str) -> None:
    p.goto(f"/events/event/{eid}")
    try:
        p.page.get_by_role("button", name="Retour : Événements").first.wait_for(state="visible", timeout=45000)
    except Exception:
        p.log("repère de la fiche absent")
    p.page.wait_for_timeout(2500)


def _chat(p, eid: str) -> None:
    p.goto(f"/events/event/{eid}/chat")
    p.page.get_by_label("Message", exact=True).wait_for(state="visible", timeout=45000)
    p.page.wait_for_timeout(2000)


def _send_chat(p, text: str) -> None:
    page = p.page
    p.type(page.get_by_label("Message", exact=True), text, "le message")
    p.tap(page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer")
    page.wait_for_timeout(1000)
    for _ in range(40):  # attente de la base (bouton en chargement)
        if not page.locator('[role="progressbar"]').count():
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(1000)


def ui_cgu(browser, origin, eid: str, key: str = "guest2") -> None:
    """Bot Gina (Guest, CGU jamais acceptées) : forum (feuille « Avant de publier » → Plus tard → J'accepte) ; petit mot."""
    p = phone(browser, key, origin, "c2-cgu")
    page = p.page
    try:
        gina = uid(key)
        if sql(f"select count(*) n from public.terms_acceptances where user_id = {q(gina)}")[0]["n"]:
            p.log("Gina a déjà accepté les CGU (autre agent) : feuille CGU non testable avec elle")
        with p.step("petit mot sans CGU"):
            sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(eid)}, {q(gina)}, 'yes') on conflict (event_id, user_id) do update set status = 'yes', note = null")
            _open_event(p, eid)
            note = page.get_by_label("Un petit mot perso pour l’organisateur")
            p.type(note, "Petit mot de Gina sans CGU", "le petit mot")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            page.wait_for_timeout(2000)
            sheet = page.get_by_role("button", name=re.compile("J.accepte")).count() > 0
            p.shot("petit-mot-sans-cgu")
            saved = sql(f"select note from public.rsvps where event_id = {q(eid)} and user_id = {q(gina)}")
            p.log(f"petit mot : feuille CGU {sheet} ; base {saved}")
            if not sheet and saved and saved[0]["note"]:
                p.flag("🟠", "petit mot publié sans CGU (ni feuille « Avant de publier », ni refus de la base)", str(saved))
            if sheet:
                p.tap(page.get_by_role("button", name="Plus tard"), "Plus tard")
        with p.step("forum : feuille CGU, Plus tard"):
            _chat(p, eid)
            _send_chat(p, "Bonjour de Gina")
            if not p.see(page.get_by_text("Avant de publier"), "la feuille « Avant de publier »", 6000):
                p.flag("🔴", "forum : pas de feuille CGU au premier message d'un compte sans CGU")
            else:
                p.shot("feuille-cgu")
                p.tap(page.get_by_role("button", name="Plus tard"), "Plus tard")
                page.wait_for_timeout(1500)
                n = sql(f"select count(*) n from public.messages where event_id = {q(eid)} and user_id = {q(gina)}")[0]["n"]
                p.log(f"après « Plus tard » : {n} message(s) en base, champ : {page.get_by_label('Message', exact=True).input_value()!r}")
                if n:
                    p.flag("🔴", "message parti malgré « Plus tard » sur la feuille CGU")
                p.tap(page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer (2e fois)")
                page.wait_for_timeout(1500)
                p.tap(page.get_by_role("button", name=re.compile("J.accepte")).first, "J'accepte")
                page.wait_for_timeout(3000)
                p.shot("apres-acceptation")
                n = sql(f"select count(*) n from public.messages where event_id = {q(eid)} and user_id = {q(gina)}")[0]["n"]
                acc = sql(f"select version from public.terms_acceptances where user_id = {q(gina)}")
                p.log(f"après « J'accepte » : messages {n}, acceptation {acc}")
                if not n:
                    p.flag("🟠", "après « J'accepte », le message n'est pas parti (il faut renvoyer)")
                if not acc:
                    p.flag("🔴", "« J'accepte » n'enregistre pas l'acceptation des CGU")
    finally:
        p.close()


def ui_filter(browser, origin, eid: str) -> None:
    """Bot Marc (CGU acceptées) : forum (haine refusée avec message, insulte masquée) ; petit mot ; Olga : description."""
    p = phone(browser, "membre1", origin, "c2-filtre")
    page = p.page
    try:
        with p.step("forum : propos haineux"):
            _chat(p, eid)
            _send_chat(p, f"Bande de {HATE}")
            p.shot("forum-haine")
            if not p.see(page.get_by_text(re.compile("propos haineux")), "le refus « propos haineux »", 5000):
                p.flag("🟠", "forum : propos haineux refusé sans message clair à l'écran")
            left = page.get_by_label("Message", exact=True).input_value()
            p.log(f"champ après refus : {left!r}")
            if not left:
                p.flag("🟡", "forum : le texte refusé est effacé du champ (impossible de le corriger)")
        with p.step("forum : insulte masquée"):
            _send_chat(p, "Salut le connard de service")
            p.shot("forum-insulte")
            p.see(page.get_by_text(re.compile("Salut le •+ de service")), "le message masqué")
        with p.step("petit mot : insulte et haine"):
            marc = uid("membre1")
            sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(eid)}, {q(marc)}, 'yes') on conflict (event_id, user_id) do update set status = 'yes', note = null")
            _open_event(p, eid)
            p.type(page.get_by_label("Un petit mot perso pour l’organisateur"), f"Coucou {HATE}", "le petit mot")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            page.wait_for_timeout(2500)
            p.shot("petit-mot-haine")
            note = sql(f"select note from public.rsvps where event_id = {q(eid)} and user_id = {q(marc)}")[0]["note"]
            p.log(f"petit mot en base : {note!r}")
            if note and HATE in note:
                p.flag("🟠", "petit mot : propos haineux enregistré tel quel et affiché aux autres participants (aucun filtre)", note)
    finally:
        p.close()
    p = phone(browser, "vip1", origin, "c2-filtre")
    page = p.page
    try:
        with p.step("Victor voit le petit mot de Marc"):
            _open_event(p, eid)
            if p.see(page.get_by_text(re.compile(HATE)), "le petit mot haineux de Marc", 5000):
                p.shot("petit-mot-vu-par-victor")
                p.flag("🟠", "le petit mot haineux de Marc est visible par Bot Victor ; aucun « Signaler » sur un petit mot")
        sql(f"update public.rsvps set note = null where event_id = {q(eid)} and user_id = {q(uid('membre1'))}")
    finally:
        p.close()
    p = phone(browser, "orga1", origin, "c2-filtre")
    page = p.page
    try:
        with p.step("modifier : description haineuse puis titre insultant"):
            p.goto(f"/events/event/{eid}/edit")
            title = page.get_by_label("Titre", exact=True)
            title.wait_for(state="visible", timeout=45000)
            p.type(page.get_by_label("Description", exact=True), f"Venez nombreux, {HATE}", "la description")
            p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
            page.wait_for_timeout(3000)
            p.shot("description-haine")
            if not p.see(page.get_by_text(re.compile("propos haineux")), "le refus de la description", 5000):
                p.flag("🟠", "modifier : description haineuse refusée sans message clair")
            p.type(page.get_by_label("Description", exact=True), "Recette campagne 2 (droits, modération). Ignorer.", "la description")
            p.type(title, f"{PREFIX} Modération connard", "le titre")
            p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
            page.wait_for_timeout(3500)
            p.shot("titre-insulte")
            t = sql(f"select title from public.events where id = {q(eid)}")[0]["title"]
            p.log(f"titre en base : {t!r} ; écran : {page.url}")
            if "•" in t and not page.get_by_text(re.compile("masqu|remplac|•")).count():
                p.flag("🟡", "titre insultant enregistré masqué (••••) sans que l'organisatrice en soit avertie", t)
            sql(f"update public.events set title = {q(PREFIX + ' Modération (forum, petit mot, à apporter)')} where id = {q(eid)}")
    finally:
        p.close()


def _report(p, button, reason: str, what: str) -> None:
    page = p.page
    p.tap(button, f"Signaler {what}")
    page.wait_for_timeout(1200)
    p.shot(f"feuille-signaler")
    p.tap(page.get_by_label(reason, exact=True).first, f"raison {reason}")
    p.type(page.get_by_label("Commentaire", exact=True), "Banc C2-08, à ignorer", "le commentaire")
    p.tap(page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer le signalement")
    # Base de TEST chargée (10 agents) : on attend la réponse (feuille fermée ou message de confirmation).
    try:
        page.get_by_role("button", name="Envoyer", exact=True).last.wait_for(state="hidden", timeout=45000)
    except Exception:
        p.log("la feuille Signaler reste ouverte après 45 s")
    page.wait_for_timeout(1500)
    p.shot(f"signale")


def ui_report(browser, origin, eid: str) -> None:
    """Bot Gina signale l'événement, un message du forum (Marc) et le profil de Marc, par les vrais boutons."""
    p = phone(browser, "guest2", origin, "c2-signaler")
    page = p.page
    gina, marc = uid("guest2"), uid("membre1")
    sql(f"delete from public.content_reports where reporter_id = {q(gina)}")
    try:
        with p.step("signaler l'événement"):
            _open_event(p, eid)
            _report(p, page.get_by_role("button", name="Signaler cet événement"), "Spam", "l'événement")
        with p.step("signaler un message du forum"):
            _chat(p, eid)
            _report(p, page.get_by_role("button", name="Signaler le message de Bot Marc").first, "Harcèlement", "le message de Marc")
        with p.step("signaler le profil"):
            p.goto(f"/events/member/{marc}")
            page.get_by_role("button", name="Signaler le profil").wait_for(state="visible", timeout=45000)
            _report(p, page.get_by_role("button", name="Signaler le profil"), "Contenu choquant", "le profil de Marc")
        rows = sql(f"select target_kind, reason, status from public.content_reports where reporter_id = {q(gina)} order by created_at")
        p.log(f"base : {rows}")
        kinds = {r["target_kind"] for r in rows}
        for k in ("event", "event_message", "profile"):
            if k not in kinds:
                p.flag("🔴", f"signalement « {k} » par l'écran non enregistré", str(rows))
        with p.step("Mes signalements (Réglages)"):
            p.goto("/events/settings")
            page.wait_for_timeout(3000)
            p.shot("reglages")
            p.dump("reglages")
    finally:
        p.close()


def ui_block(browser, origin, eid: str) -> None:
    """Bot Olga a bloqué Bot Gus (sondes API) : le forum montre-t-il encore ses messages ? la feuille Inviter le propose-t-elle ?
    Puis Bot Max bloque Bot Gus par la fiche (vrai bouton) et Gus essaie d'ouvrir la fiche de Max."""
    p = phone(browser, "orga1", origin, "c2-bloquer")
    page = p.page
    gus = uid("guest1")
    try:
        with p.step("forum : messages de la personne bloquée"):
            _chat(p, eid)
            p.shot("forum-bloque")
            if page.get_by_text("Coucou @Olga du bloqué").count() or page.get_by_text(re.compile("Coucou .*du bloqué")).count():
                p.flag("🟠", "Olga voit toujours les messages de Bot Gus (qu'elle a bloqué) dans le forum de l'événement")
        with p.step("feuille Inviter : la personne bloquée"):
            sql(f"delete from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")
            _open_event(p, eid)
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
            page.wait_for_timeout(2000)
            sheet = page.get_by_label(re.compile("^Inviter à "))
            search = sheet.get_by_placeholder(re.compile("Rechercher|Chercher", re.I))
            if search.count():
                p.type(search.first, "Gus", "la recherche")
                page.wait_for_timeout(1500)
            p.shot("inviter-bloque")
            tree = p.dump("inviter-bloque")
            if "Bot Gus" in tree:
                p.log("Bot Gus (bloqué) proposé dans la feuille Inviter : essai")
                p.tap(sheet.get_by_text("Bot Gus").first, "Bot Gus")
                page.wait_for_timeout(2500)
                p.shot("inviter-bloque-apres")
                n = sql(f"select count(*) n from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")[0]["n"]
                msg = page.get_by_text(re.compile("ne peux pas inviter|bloqu", re.I)).count()
                p.log(f"invité en base : {n} ; message de refus visible : {bool(msg)}")
                if n:
                    p.flag("🔴", "Bot Gus (bloqué) invité depuis la feuille Inviter")
                elif not msg:
                    p.flag("🟠", "feuille Inviter : Bot Gus (bloqué) est proposé, le refus de la base n'est pas expliqué")
    finally:
        p.close()
    p = phone(browser, "membre3", origin, "c2-bloquer")
    page = p.page
    try:
        with p.step("Max bloque Gus par la fiche"):
            p.goto(f"/events/member/{gus}")
            p.tap(page.get_by_role("button", name=re.compile("^Bloquer")).first, "Bloquer Bot Gus")
            page.wait_for_timeout(800)
            p.tap(page.get_by_role("button", name="Confirmer le blocage"), "Confirmer le blocage")
            page.wait_for_timeout(2500)
            p.shot("bloque")
            p.expect_or_flag(page.get_by_role("button", name=re.compile("^Débloquer")), "« Débloquer » après blocage")
            n = sql(f"select count(*) n from public.direct_blocks where user_id = {q(uid('membre3'))} and blocked_id = {q(gus)}")[0]["n"]
            if not n:
                p.flag("🔴", "blocage par la fiche non enregistré")
        with p.step("Personnes bloquées (Réglages › Confidentialité)"):
            p.goto("/events/settings/privacy")
            page.wait_for_timeout(3000)
            p.shot("confidentialite")
            if not page.get_by_text("Bot Gus").count():
                p.flag("🟡", "Bot Gus n'apparaît pas dans « Personnes bloquées »")
    finally:
        p.close()
    p = phone(browser, "guest1", origin, "c2-bloquer")
    page = p.page
    try:
        with p.step("Gus ouvre la fiche de Max (qui l'a bloqué)"):
            p.goto(f"/events/member/{uid('membre3')}")
            page.wait_for_timeout(3500)
            p.shot("fiche-max-vue-par-gus")
            tree = p.dump("fiche-max")
            p.log(f"fiche : {tree[:400]}")
    finally:
        p.close()


def ui_admin_reports(browser, origin, eid: str) -> None:
    """Bot Ada (Admin) : écran Signalements ; masque l'événement signalé, avertit l'auteur du message signalé."""
    p = phone(browser, "admin", origin, "c2-signalements")
    page = p.page
    marc = uid("membre1")
    if not sql(f"select 1 from public.content_reports where target_kind = 'event' and target_id = {q(eid)} and status = 'open'"):
        r = Session(BY_KEY["guest2"].phone).rpc("report_content", p_kind="event", p_target=eid, p_reason="spam",
                                                p_comment="Banc C2-08 (événement à masquer), à ignorer")
        p.log(f"signalement de l'événement préparé par l'API : {r.status_code}")
    try:
        p.goto("/events/admin/reports")
        page.wait_for_timeout(4000)
        p.shot("file")
        p.dump("file")
        with p.step("masquer l'événement signalé"):
            card = page.get_by_text(re.compile(r"\[C2-08\] Modération")).first
            card.scroll_into_view_if_needed(timeout=45000)
            p.shot("carte-evenement")
            # Le bouton « Masquer le contenu » de la carte qui contient le titre
            container = page.locator("div").filter(has=page.get_by_text(re.compile(r"\[C2-08\] Modération"))).filter(
                has=page.get_by_role("button", name="Masquer le contenu")).last
            p.tap(container.get_by_role("button", name="Masquer le contenu").first, "Masquer le contenu (événement)")
            page.wait_for_timeout(3500)
            p.shot("apres-masquer")
            t = sql(f"select title, description from public.events where id = {q(eid)}")[0]
            st = sql(f"select status, resolution from public.content_reports where target_kind = 'event' and target_id = {q(eid)}")
            p.log(f"base : {t} ; signalements {st}")
            if "masqué" not in t["title"]:
                p.flag("🔴", "« Masquer le contenu » ne masque pas l'événement", str(t))
        with p.step("avertir l'auteur du message"):
            container = page.locator("div").filter(has=page.get_by_text("Bot Marc")).filter(
                has=page.get_by_role("button", name="Avertir")).last
            note = container.get_by_label("Note (envoyée avec l’avertissement)")
            if note.count():
                p.type(note.first, "Avertissement du banc C2-08, à ignorer", "la note")
            p.tap(container.get_by_role("button", name="Avertir").first, "Avertir")
            page.wait_for_timeout(3500)
            p.shot("apres-avertir")
            s = sql(f"select kind, note from public.moderation_sanctions where user_id = {q(marc)} order by created_at desc limit 1")
            n = sql(f"select title, body from public.notifications where user_id = {q(marc)} and kind = 'moderation_notice' order by created_at desc limit 1")
            p.log(f"sanction {s} ; notification {n}")
            if not s or s[0]["kind"] != "warn":
                p.flag("🔴", "« Avertir » n'enregistre pas d'avertissement", str(s))
            if not n:
                p.flag("🟠", "« Avertir » : pas de notification « Message de la modération » à Bot Marc")
        with p.step("Journal des actions"):
            p.goto("/events/admin/journal")
            page.wait_for_timeout(3500)
            p.shot("journal")
    finally:
        p.close()
    p = phone(browser, "guest2", origin, "c2-signalements")
    try:
        _open_event(p, eid)
        p.shot("evenement-masque-vu-par-gina")
    finally:
        p.close()


def ui_buttons_by_role(browser, origin, eid: str) -> None:
    """Boutons de la fiche de l'événement complet pour chaque rôle (Guest, Membre, VIP, co-organisateur, organisatrice,
    Co-admin, Admin) : relevé dans buttons-by-role.json, contrôlé contre les attentes."""
    seen = {}
    import os
    who = os.environ.get("C2_WHO", "guest1,membre2,vip1,orga2,orga1,coadmin,admin").split(",")
    for key in who:
        p = phone(browser, key, origin, "c2-boutons")
        try:
            _open_event(p, eid)
            p.page.wait_for_timeout(6000)
            p.scroll_to_bottom("fiche", tries=6)
            seen[key] = _buttons(p)
            p.shot("fiche-bas")
            p.log(f"boutons : {seen[key]}")
        finally:
            p.close()
    (OUT / "buttons-by-role.json").write_text(json.dumps(seen, indent=1, ensure_ascii=False))
    manage = ("Modifier", "Annuler l’événement", "📷 Scanner les billets")
    for key in ("guest1", "membre2", "vip1"):
        for b in manage:
            if any(x == b or x.startswith(b) for x in seen.get(key, [])):
                anomaly(key, "🔴", f"{BY_KEY[key].role} voit « {b} » sur l'événement d'un autre", ", ".join(seen[key]))
    for key in ("orga2", "orga1", "admin"):
        if not any(x == "Modifier" for x in seen.get(key, [])):
            anomaly(key, "🟠", f"{key} ne voit pas « Modifier » sur la fiche", ", ".join(seen.get(key, [])))
    for key in ("orga1",):
        if any(x.startswith("Signaler") for x in seen.get(key, [])):
            anomaly(key, "🟡", "l'organisatrice voit « Signaler cet événement » sur son propre événement")


def ui_groups(browser, origin) -> None:
    """Bot Violette (dans « Bots 2 », pas dans « Bots ») : formulaire, feuille Inviter de son événement, liste."""
    p = phone(browser, "vip4", origin, "c2-groupes")
    page = p.page
    st = load_state()
    try:
        with p.step("formulaire : puces de groupes"):
            p.goto("/events/event/new")
            page.get_by_label("Titre", exact=True).wait_for(state="visible", timeout=45000)
            page.wait_for_timeout(1500)
            p.tap(page.get_by_role("radiogroup", name="Qui est invité").get_by_role("button", name=re.compile("Sur invitation")), "Sur invitation")
            page.wait_for_timeout(1500)
            tree = p.dump("formulaire")
            p.log("groupes proposés : " + ", ".join(l.strip() for l in tree.splitlines() if " · " in l and "button" in l))
            p.shot("formulaire")
            if re.search(r'button "(✓ )?Bots · ', tree) or re.search(r'"Bots"', tree):
                p.flag("🔴", "Violette (hors « Bots ») voit le groupe « Bots » dans le formulaire")
        with p.step("feuille Inviter de son événement"):
            _open_event(p, st["c2_violette_event"])
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
            page.wait_for_timeout(2500)
            tree = p.dump("inviter")
            p.shot("inviter")
            if re.search(r"\bBots\b(?! 2)", tree):
                p.flag("🔴", "Violette (hors « Bots ») voit le groupe « Bots » dans la feuille Inviter")
        with p.step("événement réservé à « Bots » : invisible"):
            _open_event(p, st["c2_only_bots"])
            p.shot("reserve-bots")
            if page.get_by_text("Réservé au groupe Bots").count():
                p.flag("🔴", "Violette ouvre un événement réservé au groupe « Bots »")
            p.goto("/events/")
            page.wait_for_timeout(3500)
            if page.get_by_text("Réservé au groupe Bots").count():
                p.flag("🔴", "l'événement réservé à « Bots » apparaît dans la liste de Violette")
    finally:
        p.close()


def phase_moderation_ui(browser, origin, only):
    eid = load_state()["c2_mod_event"]
    steps = {"cgu": lambda: ui_cgu(browser, origin, eid),
             "cgu_max": lambda: ui_cgu(browser, origin, eid, "membre3"), "filtre": lambda: ui_filter(browser, origin, eid),
             "signaler": lambda: ui_report(browser, origin, eid), "bloquer": lambda: ui_block(browser, origin, eid),
             "admin": lambda: ui_admin_reports(browser, origin, eid),
             "boutons": lambda: ui_buttons_by_role(browser, origin, load_state()["e_full"]),
             "groupes": lambda: ui_groups(browser, origin)}
    for name, run in steps.items():
        if only and name not in only:
            continue
        print(f"── {name} ──", flush=True)
        try:
            run()
        except Exception as e:
            anomaly("banc", "🟠", f"étape UI {name} interrompue", f"{type(e).__name__}: {str(e)[:400]}")
