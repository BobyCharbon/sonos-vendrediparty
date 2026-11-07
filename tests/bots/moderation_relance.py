"""Campagne 2, RELANCE de l'agent 08 — droits, confidentialité des groupes, modération (base de TEST, CGU exigées).

Rejoue les scénarios de tests/bots/moderation.py après les corrections (lots A, B, C2, G, E), adaptés au nouveau modèle :
· petit mot rangé dans public.rsvp_notes (rsvps.note vidé par la base), lu par l'organisation seulement ;
· signalables : rsvp_note, poll, poll_option, bring_item ; forum : messages des bloqués masqués à l'écran ;
· CGU : un compte sans acceptation (Bot Sara, acceptation remise à la fin) ;
· écran Signalements : masquer mot / choix / objet / question, Suspendre, Bannir, Réintégrer (sur Bot Sara, remis).
Événements préfixés « [R-08] », créés en SQL (aucune notification) puis supprimés à la fin.
Usage : BOTS_OUT=… .venv/bin/python -m tests.bots.moderation_relance api|ui[:étape,…]|cleanup"""
from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

from tests.bots import moderation as m
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, Session, q, sql

PREFIX = "[R-08]"
m.PREFIX = PREFIX  # make_event / cleanup du premier passage écrivent avec ce préfixe
NO_TERMS = "sansapp2"  # Bot Sara : CGU retirées le temps des sondes, remises à la fin
UI_NO_TERMS = "guest2"  # Bot Gina : CGU retirées pour l'écran (Sara n'ouvre que la page publique), remises à la fin
HATE, INSULT, DISGUISED = m.HATE, m.INSULT, m.DISGUISED
_SESSIONS: dict[str, Session] = {}


def sess(key: str) -> Session:
    """Une session par bot (un code SMS par minute et par numéro)."""
    if key not in _SESSIONS:
        _SESSIONS[key] = Session(BY_KEY[key].phone)
    return _SESSIONS[key]


def notes_of(eid: str, user: str) -> list[str]:
    return [r["note"] for r in sql(f"select note from public.rsvp_notes where event_id = {q(eid)} and user_id = {q(user)}")]


def column_note(eid: str, user: str):
    rows = sql(f"select note from public.rsvps where event_id = {q(eid)} and user_id = {q(user)}")
    return rows[0]["note"] if rows else None


def drop_terms(key: str) -> None:
    """Retire l'acceptation des CGU d'un bot (gardée dans state.json pour être remise exactement)."""
    u = m.uid(key)
    rows = sql(f"select * from public.terms_acceptances where user_id = {q(u)}")
    st = load_state()
    if rows and f"r08_terms_{key}" not in st:
        save_state(**{f"r08_terms_{key}": json.loads(json.dumps(rows, default=str))})
    sql(f"delete from public.terms_acceptances where user_id = {q(u)}")


def restore_terms(key: str) -> None:
    u = m.uid(key)
    rows = load_state().get(f"r08_terms_{key}") or (load_state().get("r08_terms_rows") if key == NO_TERMS else None) or []
    if sql(f"select 1 from public.terms_acceptances where user_id = {q(u)}"):
        return
    for r in rows:
        cols = ", ".join(r)
        vals = ", ".join("null" if v is None else q(v) for v in r.values())
        sql(f"insert into public.terms_acceptances ({cols}) values ({vals}) on conflict do nothing")
    print(f"CGU de {key} remises : {sql(f'select count(*) n from public.terms_acceptances where user_id = {q(u)}')}")


# ── Sondes API ────────────────────────────────────────────────────────────────────────────────────────────
def cgu(pr: m.Probe, eid: str, poll: str) -> None:
    drop_terms(NO_TERMS)
    s = sess(NO_TERMS)
    who = BY_KEY[NO_TERMS].nickname
    r = m.rest(s, "POST", "messages", json={"event_id": eid, "user_id": s.uid, "body": "Premier message sans CGU"})
    pr.rec("CGU", f"{who} : premier message du forum", "refus terms_required", f"{r.status_code}", m.refused(r, "terms_required"), "🔴", r.text[:200])
    r = m.rest(s, "POST", "rsvps", json={"event_id": eid, "user_id": s.uid, "status": "yes", "note": "Petit mot sans CGU"})
    pr.rec("CGU", f"{who} : premier petit mot (réponse avec mot)", "refus terms_required",
           f"{r.status_code} rsvp_notes={notes_of(eid, s.uid)}", m.refused(r, "terms_required") and not notes_of(eid, s.uid), "🟠", r.text[:200])
    sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(s.uid)}")
    r = m.rest(s, "POST", "rsvps", json={"event_id": eid, "user_id": s.uid, "status": "yes"})
    pr.rec("CGU", f"{who} : répondre Présent sans mot", "permis", f"{r.status_code}", r.status_code < 300, "🔴", r.text[:200])
    r = m.rest(s, "PATCH", f"rsvps?event_id=eq.{eid}&user_id=eq.{s.uid}", json={"note": "Mot ajouté après coup"})
    pr.rec("CGU", f"{who} : ajouter un mot à sa réponse (PATCH)", "refus terms_required",
           f"{r.status_code} rsvp_notes={notes_of(eid, s.uid)}", m.refused(r, "terms_required") and not notes_of(eid, s.uid), "🟠", r.text[:200])
    r = m.rest(s, "POST", "bring_items", json={"event_id": eid, "label": "Chips sans CGU", "added_by": s.uid, "claimed_by": s.uid})
    pr.rec("CGU", f"{who} : premier « à apporter »", "refus terms_required", f"{r.status_code}", m.refused(r, "terms_required"), "🟡", r.text[:200])
    r = m.rest(s, "POST", "poll_options", json={"poll_id": poll, "label": "Option sans CGU", "created_by": s.uid})
    pr.rec("CGU", f"{who} : première option de sondage", "refus terms_required", f"{r.status_code}", m.refused(r, "terms_required"), "🟡", r.text[:200])
    r = m.rest(s, "POST", "events", json={"title": f"{PREFIX} sans CGU", "created_by": s.uid, "status": "draft", "date_mode": "fixed",
                                          "starts_at": m.iso(19), "visibility": "invited", "notify_on_publish": False})
    if r.status_code < 300 and r.json():
        sql(f"delete from public.events where id = {q(r.json()[0]['id'])}")
    pr.rec("CGU", f"{who} : premier événement", "refus", f"{r.status_code}", r.status_code >= 400, "🔴", r.text[:200])
    r = s.rpc("report_content", p_kind="event", p_target=eid, p_reason="spam", p_comment="Banc R-08 sans CGU")
    pr.rec("CGU", f"{who} : signaler sans CGU (doit rester possible)", "permis", f"{r.status_code}", r.status_code < 300, "🟠", r.text[:200])
    sql(f"delete from public.content_reports where reporter_id = {q(s.uid)}")
    for t in ("bring_items", "messages"):
        col = "added_by" if t == "bring_items" else "user_id"
        sql(f"delete from public.{t} where event_id = {q(eid)} and {col} = {q(s.uid)}")
    sql(f"delete from public.poll_options where poll_id = {q(poll)} and created_by = {q(s.uid)}")


def content_filter(pr: m.Probe, eid: str, poll: str) -> None:
    marc, olga = sess("membre1"), sess("orga1")
    m.accept(marc)
    m.accept(olga)
    for text, kind in ((INSULT, "insulte"), (HATE, "haine"), (DISGUISED, "insulte déguisée")):
        hate = kind == "haine"
        r = m.rest(marc, "POST", "messages", json={"event_id": eid, "user_id": marc.uid, "body": text})
        body = r.json()[0]["body"] if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"forum : « {text} » ({kind})", "refus" if hate else "masqué", f"{r.status_code} {body}",
               m.refused(r, "content_refused") if hate else bool(body) and "•" in body, "🔴", r.text[:200])
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(marc.uid)}")
        r = m.rest(marc, "POST", "rsvps", json={"event_id": eid, "user_id": marc.uid, "status": "yes", "note": text})
        notes = notes_of(eid, marc.uid)
        okk = m.refused(r, "content_refused") if hate else (r.status_code < 300 and notes and "•" in notes[0])
        pr.rec("filtre", f"petit mot : « {text} » ({kind})", "refus" if hate else "masqué (rsvp_notes)",
               f"{r.status_code} rsvp_notes={notes} rsvps.note={column_note(eid, marc.uid)!r}", bool(okk), "🟠", r.text[:200])
        sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(marc.uid)}")
        sql(f"delete from public.rsvp_notes where event_id = {q(eid)} and user_id = {q(marc.uid)}")
        # « à apporter » / option : il faut pouvoir participer (réponse Présent)
        sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(eid)}, {q(marc.uid)}, 'yes') on conflict do nothing")
        r = m.rest(marc, "POST", "bring_items", json={"event_id": eid, "label": f"Chips {text}", "added_by": marc.uid, "claimed_by": marc.uid})
        label = r.json()[0].get("label") if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"à apporter : « Chips {text} » ({kind})", "refus" if hate else "masqué", f"{r.status_code} {label!r}",
               m.refused(r, "content_refused") if hate else bool(label) and "•" in label, "🟡", r.text[:200])
        r = m.rest(marc, "POST", "poll_options", json={"poll_id": poll, "label": f"Option {text}", "created_by": marc.uid})
        label = r.json()[0].get("label") if r.status_code < 300 and r.json() else None
        pr.rec("filtre", f"option de sondage : « Option {text} » ({kind})", "refus" if hate else "masqué", f"{r.status_code} {label!r}",
               m.refused(r, "content_refused") if hate else bool(label) and "•" in label, "🟡", r.text[:200])
        r = m.rest(olga, "POST", "events", json={"title": f"{PREFIX} Soirée {text}", "created_by": olga.uid, "status": "draft",
                                                 "date_mode": "fixed", "starts_at": m.iso(19), "visibility": "invited", "notify_on_publish": False})
        title = r.json()[0]["title"] if r.status_code < 300 and r.json() else None
        if title:
            sql(f"delete from public.events where id = {q(r.json()[0]['id'])}")
        pr.rec("filtre", f"titre d'événement : « Soirée {text} » ({kind})", "refus content_refused", f"{r.status_code} {title!r}",
               m.refused(r, "content_refused"), "🔴" if hate else "🟡", r.text[:200])
        r = m.rest(olga, "PATCH", f"events?id=eq.{eid}", json={"description": f"Venez nombreux, {text}"})
        desc = sql(f"select description from public.events where id = {q(eid)}")[0]["description"]
        sql(f"update public.events set description = 'Recette campagne 2 (droits, modération). Ignorer.' where id = {q(eid)}")
        pr.rec("filtre", f"description : « …{text} » ({kind})", "refus content_refused", f"{r.status_code} base={desc[:50]!r}",
               m.refused(r, "content_refused") and text not in desc, "🔴" if hate else "🟡", r.text[:200])
        r = m.rest(olga, "POST", "polls", json={"event_id": eid, "question": f"Question {text} ?", "created_by": olga.uid})
        qtext = r.json()[0].get("question") if r.status_code < 300 and r.json() else None
        if qtext:
            sql(f"delete from public.polls where id = {q(r.json()[0]['id'])}")
        pr.rec("filtre", f"question de sondage : « Question {text} ? » ({kind})", "refus" if hate else "masqué", f"{r.status_code} {qtext!r}",
               m.refused(r, "content_refused") if hate else bool(qtext) and "•" in qtext, "🟡", r.text[:200])
        # Modifier un objet / une option propre en contenu interdit (contournement par PATCH)
    r = m.rest(marc, "POST", "bring_items", json={"event_id": eid, "label": "Chips propres", "added_by": marc.uid, "claimed_by": marc.uid})
    if r.status_code < 300:
        bid = r.json()[0]["id"]
        r2 = m.rest(marc, "PATCH", f"bring_items?id=eq.{bid}", json={"label": f"Chips {HATE}"})
        lab = sql(f"select label from public.bring_items where id = {q(bid)}")[0]["label"]
        pr.rec("filtre", "à apporter : objet propre puis modifié en propos haineux (PATCH)", "refus", f"{r2.status_code} base={lab!r}",
               HATE not in lab, "🟠", r2.text[:200])
    r = m.rest(marc, "POST", "messages", json={"event_id": eid, "user_id": marc.uid, "body": "Message propre"})
    if r.status_code < 300:
        mid = r.json()[0]["id"]
        r2 = m.rest(marc, "PATCH", f"messages?id=eq.{mid}", json={"body": HATE})
        body = sql(f"select body from public.messages where id = {q(mid)}")[0]["body"]
        pr.rec("filtre", "forum : message propre puis modifié en propos haineux", "refus", f"{r2.status_code} base={body!r}",
               body == "Message propre", "🔴", r2.text[:200])
        save_state(c2_clean_message=mid)
    sql(f"delete from public.bring_items where event_id = {q(eid)} and added_by = {q(marc.uid)}")
    sql(f"delete from public.poll_options where poll_id = {q(poll)} and created_by = {q(marc.uid)}")


def notes_visibility(pr: m.Probe, eid: str) -> None:
    """Petit mot propre de Marc : qui le lit (organisation oui, autres invités non) ; rsvps.note toujours vide."""
    marc = sess("membre1")
    sql(f"delete from public.rsvps where event_id = {q(eid)} and user_id = {q(marc.uid)}")
    r = m.rest(marc, "POST", "rsvps", json={"event_id": eid, "user_id": marc.uid, "status": "yes", "note": "Je viens avec le dessert"})
    pr.rec("petit mot", "Marc répond avec un mot propre", "enregistré dans rsvp_notes, rsvps.note vide",
           f"{r.status_code} notes={notes_of(eid, marc.uid)} col={column_note(eid, marc.uid)!r}",
           r.status_code < 300 and notes_of(eid, marc.uid) == ["Je viens avec le dessert"] and not column_note(eid, marc.uid), "🟠", r.text[:200])
    for key, expected in (("orga1", True), ("vip1", False), ("guest2", False), ("membre1", True)):
        s = sess(key)
        r = m.rest(s, "GET", f"rsvp_notes?event_id=eq.{eid}&user_id=eq.{marc.uid}&select=note")
        seen = r.status_code < 300 and bool(r.json())
        pr.rec("petit mot", f"{BY_KEY[key].nickname} lit le mot de Marc (REST)", "oui" if expected else "non", f"{r.status_code} {r.text[:60]}",
               seen == expected, "🟠")
    r = m.rest(sess("vip1"), "GET", f"rsvps?event_id=eq.{eid}&select=user_id,note")
    leaks = [x for x in (r.json() if r.status_code < 300 else []) if x.get("note")]
    pr.rec("petit mot", "Victor lit rsvps.note des autres", "aucun mot", f"{leaks}", not leaks, "🟠")
    nid = sql(f"select id from public.rsvp_notes where event_id = {q(eid)} and user_id = {q(marc.uid)}")
    save_state(r08_note=nid[0]["id"] if nid else None)
    # Un invité modifie directement rsvp_notes d'un autre / le sien en propos haineux
    if nid:
        r = m.rest(sess("vip1"), "PATCH", f"rsvp_notes?id=eq.{nid[0]['id']}", json={"note": "piraté"})
        pr.rec("petit mot", "Victor modifie le mot de Marc (REST)", "refus / 0 ligne", f"{r.status_code} base={notes_of(eid, marc.uid)}",
               notes_of(eid, marc.uid) == ["Je viens avec le dessert"], "🔴", r.text[:120])
        r = m.rest(marc, "PATCH", f"rsvp_notes?id=eq.{nid[0]['id']}", json={"note": f"Coucou {HATE}"})
        pr.rec("petit mot", "Marc écrit directement dans rsvp_notes (contournement du filtre)", "refus",
               f"{r.status_code} base={notes_of(eid, marc.uid)}", HATE not in " ".join(notes_of(eid, marc.uid)), "🔴", r.text[:120])
        r = m.rest(marc, "POST", "rsvp_notes", json={"event_id": eid, "user_id": marc.uid, "note": f"Bis {HATE}"})
        pr.rec("petit mot", "Marc insère directement dans rsvp_notes", "refus", f"{r.status_code}",
               HATE not in " ".join(notes_of(eid, marc.uid)), "🔴", r.text[:120])


def reports(pr: m.Probe, eid: str, poll: str) -> None:
    gina, olga = sess("guest2"), sess("orga1")
    m.accept(gina)
    marc_uid = m.uid("membre1")
    mid = load_state().get("c2_clean_message")
    # Contenus des invités : objet et option de Marc (propres), mot de Marc (notes_visibility)
    marc = sess("membre1")
    bi = m.rest(marc, "POST", "bring_items", json={"event_id": eid, "label": "Gâteau de Marc", "added_by": marc.uid, "claimed_by": marc.uid}).json()[0]["id"]
    po = m.rest(marc, "POST", "poll_options", json={"poll_id": poll, "label": "Samedi (Marc)", "created_by": marc.uid}).json()[0]["id"]
    save_state(r08_bring=bi, r08_option=po)
    cases = [("event", eid, "l'événement"), ("event_message", mid, "un message du forum"), ("profile", marc_uid, "le profil de Marc"),
             ("bring_item", bi, "l'objet de Marc"), ("poll_option", po, "l'option de Marc"), ("poll", poll, "le sondage")]
    for kind, target, what in cases:
        r = gina.rpc("report_content", p_kind=kind, p_target=target, p_reason="harassment", p_comment="Banc R-08, à ignorer")
        rows = sql(f"select status, target_user, snapshot from public.content_reports where target_kind = {q(kind)} and target_id = {q(target)} and reporter_id = {q(gina.uid)}")
        pr.rec("signaler", f"Gina signale {what}", "enregistré", f"{r.status_code} n={len(rows)} {str(rows)[:120]}",
               r.status_code < 300 and bool(rows), "🔴", r.text[:200])
        r = gina.rpc("report_content", p_kind=kind, p_target=target, p_reason="spam")
        n = sql(f"select count(*) n from public.content_reports where target_kind = {q(kind)} and target_id = {q(target)} and reporter_id = {q(gina.uid)}")[0]["n"]
        pr.rec("signaler", f"Gina signale deux fois {what}", "un seul signalement", f"{r.status_code} n={n}", n == 1, "🟡")
    note = load_state().get("r08_note")
    r = gina.rpc("report_content", p_kind="rsvp_note", p_target=note, p_reason="spam")
    pr.rec("signaler", "Gina (simple invitée, ne lit pas les mots) signale le mot de Marc", "refus not_found (pas d'oracle)",
           f"{r.status_code}", m.refused(r, "not_found"), "🟡", r.text[:200])
    r = olga.rpc("report_content", p_kind="rsvp_note", p_target=note, p_reason="harassment", p_comment="Banc R-08, à ignorer")
    pr.rec("signaler", "Olga (organisatrice) signale le mot de Marc", "enregistré", f"{r.status_code}", r.status_code < 300, "🔴", r.text[:200])
    r = marc.rpc("report_content", p_kind="bring_item", p_target=bi, p_reason="spam")
    pr.rec("signaler", "Marc signale son propre objet", "refus self", f"{r.status_code}", m.refused(r, "self"), "🟡", r.text[:200])
    r = olga.rpc("report_content", p_kind="event", p_target=eid, p_reason="spam")
    pr.rec("signaler", "l'organisatrice signale son propre événement", "refus self", f"{r.status_code}", m.refused(r, "self"), "🟡", r.text[:200])
    hidden = m.make_event("Invisible pour Gina", "orga1", [])
    hp = sql(f"insert into public.polls (event_id, question, created_by) values ({q(hidden)}, 'Caché ?', {q(m.uid('orga1'))}) returning id")[0]["id"]
    for kind, target in (("event", hidden), ("poll", hp)):
        r = gina.rpc("report_content", p_kind=kind, p_target=target, p_reason="spam")
        pr.rec("signaler", f"signaler un {kind} qu'on ne voit pas", "refus not_found", f"{r.status_code}", m.refused(r, "not_found"), "🟠", r.text[:200])
    r = m.rest(gina, "GET", "content_reports?select=id,reporter_id")
    others = [x for x in (r.json() if r.status_code < 300 else []) if x["reporter_id"] != gina.uid]
    pr.rec("signaler", "Gina lit les signalements des autres", "aucun", f"{len(others)}", not others, "🔴")
    r = gina.rpc("moderation_queue")
    pr.rec("signaler", "Gina (Guest) lit la file", "refus forbidden", f"{r.status_code}", m.refused(r, "forbidden"), "🔴", r.text[:120])
    r = sess("coadmin").rpc("moderation_queue")
    pr.rec("signaler", "Côme (Co-admin) lit la file", "information (droit moderation.reports)", f"{r.status_code}", True, "🟡", r.text[:80])


def phase_api() -> None:
    pr = m.Probe()
    eid = m.make_event("Modération (forum, petit mot, à apporter)", "orga1",
                       ["membre1", "membre3", "guest2", "guest1", "vip1", "vip4", NO_TERMS], allow_plus_ones=True, max_plus_ones=2)
    poll = sql(f"insert into public.polls (event_id, question, created_by, members_can_add_options) values "
               f"({q(eid)}, 'Quel jour ?', {q(m.uid('orga1'))}, true) returning id")[0]["id"]
    save_state(c2_mod_event=eid, c2_poll=poll)
    for step in (cgu, content_filter, notes_visibility, reports, blocking_step, groups_step):
        try:
            if step is notes_visibility or step in (blocking_step, groups_step):
                step(pr, eid)
            else:
                step(pr, eid, poll)
        except Exception as e:
            anomaly("api", "🟠", f"sonde {step.__name__} interrompue", f"{type(e).__name__}: {str(e)[:400]}")
            print(f"sonde {step.__name__} interrompue : {e}")
        pr.save("moderation-api.json")


def blocking_step(pr: m.Probe, eid: str) -> None:
    m.Session = lambda phone: sess(next(k for k, b in BY_KEY.items() if b.phone == phone))  # sessions partagées
    olga = sess("orga1")
    # Ancien bug 6 : l'organisatrice prévenue de sa propre modification (aucune écriture SQL entre les deux)
    sql(f"delete from public.notifications where user_id = {q(olga.uid)} and event_id = {q(eid)}")
    r = m.rest(olga, "PATCH", f"events?id=eq.{eid}", json={"description": "Recette R-08 : modification par l'organisatrice."})
    import time
    time.sleep(4)
    n = sql(f"select kind, title from public.notifications where user_id = {q(olga.uid)} and event_id = {q(eid)}")
    pr.rec("notifications", "Olga modifie son événement : est-elle prévenue ?", "aucune notification", f"{r.status_code} {n}",
           not any(x["kind"] == "event_changed" for x in n), "🟡")
    n2 = sql(f"select count(*) n from public.notifications where user_id = {q(m.uid('membre1'))} and event_id = {q(eid)} and kind = 'event_changed' and created_at > now() - interval '10 seconds'")[0]["n"]
    pr.rec("notifications", "Marc (Présent) prévenu de la modification d'Olga", "information", f"{n2}", True, "🟡")
    sql(f"delete from public.notifications where user_id = {q(olga.uid)} and event_id = {q(eid)}")
    m.blocking(pr, eid)
    n = sql(f"select kind, title, body from public.notifications where user_id = {q(olga.uid)} and event_id = {q(eid)}")
    pr.rec("bloquer", "notifications d'Olga après le message de Gus (bloqué) — détail", "aucune liée au message", f"{n}",
           not any(x["kind"] in ("chat_message", "mention", "event_message", "chat_mention") for x in n), "🟠")


def groups_step(pr: m.Probe, eid: str) -> None:
    m.groups(pr)


def make_full() -> str:
    """Événement complet (billets, accompagnants, co-organisateur Oscar) pour les boutons par rôle et la matrice."""
    eid = m.make_event("Soirée complète (droits)", "orga1", ["guest1", "membre2", "vip1", "orga2", "membre1"],
                       tickets_enabled=True, price_chf=10, allow_plus_ones=True, max_plus_ones=2)
    sql(f"insert into public.event_organizers (event_id, user_id) values ({q(eid)}, {q(m.uid('orga2'))}) on conflict do nothing")
    save_state(e_full=eid)
    return eid


# ── Écrans ───────────────────────────────────────────────────────────────────────────────────────────────
def ui_cgu(browser, origin, eid: str) -> None:
    """Bot Gina (CGU retirées le temps de l'étape, puis remises ; Sara, sans identité complète, n'a que la page publique) : petit mot → feuille CGU → Plus tard (rien n'est envoyé) ; forum → Plus tard → J'accepte."""
    drop_terms(UI_NO_TERMS)
    p = phone(browser, UI_NO_TERMS, origin, "r08-cgu")
    page = p.page
    u = m.uid(UI_NO_TERMS)
    try:
        with p.step("petit mot sans CGU"):
            sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(eid)}, {q(u)}, 'yes') on conflict (event_id, user_id) do update set status = 'yes'")
            m._open_event(p, eid)
            p.type(page.get_by_label("Un petit mot perso pour l’organisateur"), "Petit mot de Gina sans CGU", "le petit mot")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            sheet = p.see(page.get_by_text("Avant de publier"), "la feuille « Avant de publier »", 8000)
            p.shot("petit-mot-feuille-cgu")
            if not sheet:
                p.flag("🟠", "petit mot : pas de feuille CGU pour un compte sans CGU", str(notes_of(eid, u)))
            else:
                p.tap(page.get_by_role("button", name="Plus tard"), "Plus tard")
                page.wait_for_timeout(2000)
                left = page.get_by_label("Un petit mot perso pour l’organisateur").input_value()
                p.log(f"après Plus tard : base {notes_of(eid, u)} ; champ {left!r}")
                if notes_of(eid, u):
                    p.flag("🔴", "petit mot enregistré malgré « Plus tard »")
                if not left:
                    p.flag("🟡", "petit mot : le texte est effacé après « Plus tard »")
        with p.step("forum : feuille CGU, Plus tard puis J'accepte"):
            m._chat(p, eid)
            m._send_chat(p, "Bonjour de Gina")
            if not p.see(page.get_by_text("Avant de publier"), "la feuille « Avant de publier »", 8000):
                p.flag("🔴", "forum : pas de feuille CGU au premier message d'un compte sans CGU")
                return
            p.shot("feuille-cgu")
            p.tap(page.get_by_role("button", name="Plus tard"), "Plus tard")
            page.wait_for_timeout(1500)
            n = sql(f"select count(*) n from public.messages where event_id = {q(eid)} and user_id = {q(u)}")[0]["n"]
            if n:
                p.flag("🔴", "message parti malgré « Plus tard »")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer (2e fois)")
            page.wait_for_timeout(1500)
            p.tap(page.get_by_role("button", name=re.compile("J.accepte")).first, "J'accepte")
            page.wait_for_timeout(4000)
            p.shot("apres-acceptation")
            n = sql(f"select count(*) n from public.messages where event_id = {q(eid)} and user_id = {q(u)}")[0]["n"]
            acc = sql(f"select version from public.terms_acceptances where user_id = {q(u)}")
            p.log(f"après J'accepte : messages {n}, acceptation {acc}")
            if n != 1:
                p.flag("🟠" if not n else "🔴", f"après « J'accepte » : {n} message(s) envoyés (attendu 1)")
            if not acc:
                p.flag("🔴", "« J'accepte » n'enregistre pas l'acceptation")
        with p.step("petit mot après acceptation"):
            m._open_event(p, eid)
            field = page.get_by_label("Un petit mot perso pour l’organisateur")
            p.type(field, "Petit mot de Gina", "le petit mot")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            page.wait_for_timeout(4000)
            p.shot("petit-mot-envoye")
            p.log(f"base : rsvp_notes {notes_of(eid, u)} ; rsvps.note {column_note(eid, u)!r}")
            if notes_of(eid, u) != ["Petit mot de Gina"]:
                p.flag("🟠", "petit mot non enregistré après acceptation des CGU", str(notes_of(eid, u)))
            page.reload()
            page.wait_for_timeout(5000)
            if field.input_value() != "Petit mot de Gina":
                p.flag("🟡", f"après rechargement, le champ petit mot ne montre pas mon mot : {field.input_value()!r}")
            p.type(field, "", "le petit mot (effacé)")
            p.tap(page.get_by_role("button", name="Effacer", exact=True).first, "Effacer (le bouton devient « Effacer »)")
            page.wait_for_timeout(4000)
            p.log(f"après effacement : {notes_of(eid, u)}")
            if notes_of(eid, u):
                p.flag("🟡", "effacer son petit mot ne le retire pas de la base", str(notes_of(eid, u)))
    finally:
        p.close()


def ui_filter(browser, origin, eid: str) -> None:
    """Marc : forum (haine refusée, insulte masquée) ; petit mot haineux refusé à l'écran ; objet et option interdits.
    Victor ne voit pas les mots ; Olga : description haineuse, titre insultant, puis notifications d'auto-modification."""
    p = phone(browser, "membre1", origin, "r08-filtre")
    page = p.page
    marc = m.uid("membre1")
    try:
        with p.step("forum : propos haineux puis insulte"):
            m._chat(p, eid)
            m._send_chat(p, f"Bande de {HATE}")
            p.shot("forum-haine")
            if not p.see(page.get_by_text(re.compile("propos haineux")), "le refus « propos haineux »", 8000):
                p.flag("🟠", "forum : propos haineux refusé sans message clair")
            if not page.get_by_label("Message", exact=True).input_value():
                p.flag("🟡", "forum : texte refusé effacé du champ")
            m._send_chat(p, "Salut le connard de service")
            p.shot("forum-insulte")
            p.see(page.get_by_text(re.compile("Salut le •+ de service")), "le message masqué")
        with p.step("petit mot : propos haineux"):
            sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(eid)}, {q(marc)}, 'yes') on conflict (event_id, user_id) do update set status = 'yes'")
            sql(f"delete from public.rsvp_notes where event_id = {q(eid)} and user_id = {q(marc)}")
            m._open_event(p, eid)
            field = page.get_by_label("Un petit mot perso pour l’organisateur")
            p.type(field, f"Coucou {HATE}", "le petit mot")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            page.wait_for_timeout(4000)
            p.shot("petit-mot-haine")
            msg = page.get_by_text(re.compile("propos haineux|non enregistré", re.IGNORECASE))
            p.log(f"base : {notes_of(eid, marc)} ; message : {msg.first.inner_text() if msg.count() else None} ; champ {field.input_value()!r}")
            if any(HATE in n for n in notes_of(eid, marc)):
                p.flag("🟠", "petit mot haineux enregistré", str(notes_of(eid, marc)))
            if not msg.count():
                p.flag("🟠", "petit mot haineux refusé sans message à l'écran")
            elif re.search(r"content_refused|terms_required", msg.first.inner_text()):
                p.flag("🟡", "le refus affiche la clé technique", msg.first.inner_text())
            p.type(field, "Je viens avec le dessert", "le petit mot propre")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).first, "Envoyer (petit mot)")
            page.wait_for_timeout(4000)
            p.log(f"mot propre : {notes_of(eid, marc)}")
        with p.step("à apporter et sondage : contenu interdit à l'écran"):
            p.scroll_to_bottom("fiche", tries=6)
            tree = p.dump("fiche-marc")
            add = page.get_by_placeholder(re.compile("apporte|Ajouter|objet", re.IGNORECASE))
            p.log(f"champs d'ajout trouvés : {add.count()}")
            if add.count():
                p.type(add.first, f"Chips {HATE}", "l'objet")
                page.keyboard.press("Enter")
                page.wait_for_timeout(3500)
                p.shot("objet-haine")
                err = page.get_by_text(re.compile("propos haineux|non enregistr|refus", re.IGNORECASE))
                txt = err.first.inner_text() if err.count() else None
                p.log(f"objet haineux : message {txt!r} ; base {sql(f'select label from public.bring_items where event_id = {q(eid)} and added_by = {q(marc)}')}")
                if not txt:
                    p.flag("🟠", "« Qui amène quoi » : objet haineux refusé sans message à l'écran")
                elif "content_refused" in txt:
                    p.flag("🟡", "« Qui amène quoi » : le refus affiche la clé technique content_refused", txt)
            else:
                p.log("aucun champ « à apporter » trouvé" + tree[:200])
    finally:
        p.close()
    p = phone(browser, "vip1", origin, "r08-filtre")
    page = p.page
    try:
        with p.step("Victor (invité) ne voit pas les petits mots"):
            m._open_event(p, eid)
            p.scroll_to_bottom("fiche", tries=6)
            p.shot("fiche-victor")
            if page.get_by_text("Je viens avec le dessert").count() or page.get_by_text("Petits mots").count():
                p.flag("🟠", "Victor (simple invité) voit les petits mots des autres")
    finally:
        p.close()
    p = phone(browser, "orga1", origin, "r08-filtre")
    page = p.page
    olga = m.uid("orga1")
    try:
        with p.step("Olga voit le mot de Marc et son bouton Signaler"):
            m._open_event(p, eid)
            p.scroll_to_bottom("fiche", tries=6)
            p.shot("fiche-olga-mots")
            if not page.get_by_text("Je viens avec le dessert").count():
                p.flag("🟠", "l'organisatrice ne voit pas le petit mot de Marc")
            if not page.get_by_role("button", name="Signaler le mot de Bot Marc").count():
                p.flag("🟠", "pas de « Signaler » sur le petit mot de Marc (organisatrice)")
        with p.step("modifier : description haineuse puis titre insultant"):
            before = sql("select now() t")[0]["t"]
            p.goto(f"/events/event/{eid}/edit")
            title = page.get_by_label("Titre", exact=True)
            title.wait_for(state="visible", timeout=45000)
            p.type(page.get_by_label("Description", exact=True), f"Venez nombreux, {HATE}", "la description")
            p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
            page.wait_for_timeout(4000)
            p.shot("description-haine")
            if not p.see(page.get_by_text(re.compile("propos haineux")), "le refus de la description", 6000):
                p.flag("🟠", "description haineuse refusée sans message clair")
            p.type(page.get_by_label("Description", exact=True), "Recette campagne 2 (droits, modération). Ignorer.", "la description")
            p.type(title, f"{PREFIX} Modération connard", "le titre")
            p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
            page.wait_for_timeout(5000)
            p.shot("titre-insulte")
            t = sql(f"select title from public.events where id = {q(eid)}")[0]["title"]
            p.log(f"titre en base : {t!r}")
            if "•" in t and not page.get_by_text(re.compile("masqu|remplac|•")).count():
                p.flag("🟡", "titre insultant enregistré masqué (••••) sans avertir l'organisatrice", t)
            page.wait_for_timeout(3000)
            n = sql(f"select kind, title from public.notifications where user_id = {q(olga)} and event_id = {q(eid)} and created_at >= {q(before)}")
            p.log(f"notifications d'Olga après sa propre modification : {n}")
            if any(x["kind"] == "event_changed" for x in n):
                p.flag("🟡", "l'organisatrice reçoit « Événement modifié » pour sa propre modification", str(n))
            sql(f"update public.events set title = {q(PREFIX + ' Modération (forum, petit mot, à apporter)')} where id = {q(eid)}")
    finally:
        p.close()


def ui_report(browser, origin, eid: str) -> None:
    """Gina signale par les vrais boutons : événement, message, profil, objet, choix de sondage, sondage. Olga signale un mot."""
    p = phone(browser, "guest2", origin, "r08-signaler")
    page = p.page
    gina = m.uid("guest2")
    sql(f"delete from public.content_reports where reporter_id = {q(gina)}")
    try:
        with p.step("signaler l'événement"):
            m._open_event(p, eid)
            m._report(p, page.get_by_role("button", name="Signaler cet événement"), "Spam", "l'événement")
        with p.step("signaler un objet, un choix, le sondage"):
            for name in ("Signaler l’objet « Gâteau de Marc »", "Signaler le choix « Samedi (Marc) »", "Signaler ce sondage"):
                m._open_event(p, eid)
                p.scroll_to_bottom("fiche", tries=6)
                b = page.get_by_role("button", name=name)
                if not b.count():
                    p.dump("fiche-gina")
                    p.flag("🟠", f"bouton « {name} » absent pour Gina")
                    continue
                b.first.scroll_into_view_if_needed()
                m._report(p, b.first, "Harcèlement", name)
        with p.step("signaler un message du forum"):
            m._chat(p, eid)
            m._report(p, page.get_by_role("button", name="Signaler le message de Bot Marc").first, "Harcèlement", "le message de Marc")
        with p.step("signaler le profil"):
            p.goto(f"/events/member/{m.uid('membre1')}")
            page.get_by_role("button", name="Signaler le profil").wait_for(state="visible", timeout=45000)
            m._report(p, page.get_by_role("button", name="Signaler le profil"), "Contenu choquant", "le profil de Marc")
        with p.step("ses propres contenus : pas de Signaler"):
            sid = m.rest(sess("guest2"), "POST", "bring_items", json={"event_id": eid, "label": "Bière de Gina", "added_by": gina, "claimed_by": gina})
            m._open_event(p, eid)
            p.scroll_to_bottom("fiche", tries=6)
            if page.get_by_role("button", name="Signaler l’objet « Bière de Gina »").count():
                p.flag("🟡", "Gina voit « Signaler » sur son propre objet")
            p.log(f"objet de Gina : {sid.status_code}")
        rows = sql(f"select target_kind, reason from public.content_reports where reporter_id = {q(gina)} order by created_at")
        p.log(f"base : {rows}")
        kinds = {r["target_kind"] for r in rows}
        for k in ("event", "event_message", "profile", "bring_item", "poll_option", "poll"):
            if k not in kinds:
                p.flag("🔴", f"signalement « {k} » par l'écran non enregistré", str(rows))
    finally:
        p.close()
    p = phone(browser, "orga1", origin, "r08-signaler")
    page = p.page
    try:
        with p.step("Olga signale le mot de Marc"):
            sql(f"delete from public.content_reports where target_kind = 'rsvp_note' and reporter_id = {q(m.uid('orga1'))}")
            m._open_event(p, eid)
            p.scroll_to_bottom("fiche", tries=6)
            b = page.get_by_role("button", name="Signaler le mot de Bot Marc")
            if b.count():
                b.first.scroll_into_view_if_needed()
                m._report(p, b.first, "Harcèlement", "le mot de Marc")
            n = sql(f"select count(*) n from public.content_reports where target_kind = 'rsvp_note' and reporter_id = {q(m.uid('orga1'))}")[0]["n"]
            if not n:
                p.flag("🔴", "signalement du petit mot par l'écran non enregistré")
    finally:
        p.close()


def ui_block(browser, origin, eid: str) -> None:
    """Olga a bloqué Gus (sondes API) : forum masqué ? feuille Inviter ? Max bloque Gus par la fiche."""
    p = phone(browser, "orga1", origin, "r08-bloquer")
    page = p.page
    gus = m.uid("guest1")
    try:
        with p.step("forum : messages de la personne bloquée"):
            m._chat(p, eid)
            page.wait_for_timeout(3000)
            p.shot("forum-bloque")
            shown = page.get_by_text(re.compile("Coucou .*du bloqué")).count()
            masked = page.get_by_text(re.compile("Message masqué")).count()
            p.log(f"texte de Gus visible : {shown} ; « Message masqué » : {masked}")
            if shown:
                p.flag("🟠", "Olga voit toujours les messages de Gus (bloqué) dans le forum")
            if page.get_by_role("button", name="Signaler le message de Bot Gus").count():
                p.flag("🟡", "« Signaler » reste proposé sur un message masqué de Gus")
        with p.step("« @ » : Gus (bloqué) proposé ?"):
            p.type(page.get_by_label("Message", exact=True), "@Bot", "@")
            page.wait_for_timeout(2500)
            p.shot("mentions")
            tree = p.dump("mentions")
            if "Bot Gus" in tree:
                p.flag("🟡", "Gus (bloqué) proposé dans les mentions « @ »")
            p.type(page.get_by_label("Message", exact=True), "", "vider")
        with p.step("feuille Inviter : la personne bloquée"):
            sql(f"delete from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")
            m._open_event(p, eid)
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
            page.wait_for_timeout(2500)
            sheet = page.get_by_label(re.compile("^Inviter à "))
            search = sheet.get_by_placeholder(re.compile("Rechercher|Chercher", re.IGNORECASE))
            if search.count():
                p.type(search.first, "Gus", "la recherche")
                page.wait_for_timeout(2000)
            p.shot("inviter-bloque")
            tree = p.dump("inviter-bloque")
            if "Bot Gus" in tree:
                p.tap(sheet.get_by_text("Bot Gus").first, "Bot Gus")
                page.wait_for_timeout(3000)
                p.shot("inviter-bloque-apres")
                n = sql(f"select count(*) n from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")[0]["n"]
                msg = page.get_by_text(re.compile("ne peux pas inviter|bloqu", re.IGNORECASE))
                txt = msg.first.inner_text() if msg.count() else None
                p.log(f"invité en base : {n} ; message : {txt!r}")
                if n:
                    p.flag("🔴", "Gus (bloqué) invité depuis la feuille Inviter")
                elif not txt:
                    p.flag("🟠", "feuille Inviter : Gus (bloqué) proposé, refus non expliqué")
                elif "blocked:" in txt:
                    p.flag("🟡", "le refus affiche la clé technique « blocked: »", txt)
            else:
                p.log("Gus n'est pas proposé dans la feuille Inviter")
    finally:
        p.close()
    p = phone(browser, "membre3", origin, "r08-bloquer")
    page = p.page
    try:
        with p.step("Max bloque Gus par la fiche"):
            p.goto(f"/events/member/{gus}")
            p.tap(page.get_by_role("button", name=re.compile("^Bloquer")).first, "Bloquer Bot Gus")
            page.wait_for_timeout(800)
            p.tap(page.get_by_role("button", name="Confirmer le blocage"), "Confirmer le blocage")
            page.wait_for_timeout(3000)
            p.shot("bloque")
            p.expect_or_flag(page.get_by_role("button", name=re.compile("^Débloquer")), "« Débloquer » après blocage")
            if not sql(f"select 1 from public.direct_blocks where user_id = {q(m.uid('membre3'))} and blocked_id = {q(gus)}"):
                p.flag("🔴", "blocage par la fiche non enregistré")
        with p.step("Personnes bloquées (Réglages › Confidentialité) puis Débloquer"):
            p.goto("/events/settings/privacy")
            page.wait_for_timeout(4000)
            p.shot("confidentialite")
            if not page.get_by_text("Bot Gus").count():
                p.flag("🟡", "Gus n'apparaît pas dans « Personnes bloquées »")
            b = page.get_by_role("button", name=re.compile("Débloquer"))
            if b.count():
                p.tap(b.first, "Débloquer")
                page.wait_for_timeout(3000)
                p.shot("debloque")
                if sql(f"select 1 from public.direct_blocks where user_id = {q(m.uid('membre3'))} and blocked_id = {q(gus)}"):
                    p.flag("🟠", "« Débloquer » (Réglages) ne retire pas le blocage")
    finally:
        p.close()
    p = phone(browser, "guest1", origin, "r08-bloquer")
    page = p.page
    try:
        with p.step("Gus ouvre la fiche d'Olga (qui l'a bloqué)"):
            p.goto(f"/events/member/{m.uid('orga1')}")
            page.wait_for_timeout(4000)
            p.shot("fiche-olga-vue-par-gus")
            p.log(p.dump("fiche-olga")[:400])
    finally:
        p.close()


def ui_admin(browser, origin, eid: str) -> None:
    """Bot Ada : écran Signalements — nouveaux types affichés, masquer mot / choix / objet / sondage / événement, avertir ;
    puis Suspendre, Réintégrer, Bannir, Réintégrer sur Bot Sara (remis), et ce que Sara peut encore faire."""
    st = load_state()
    p = phone(browser, "admin", origin, "r08-signalements")
    page = p.page

    def card(text_re: str):
        return page.locator("div").filter(has=page.get_by_text(re.compile(text_re))).filter(
            has=page.get_by_role("button", name="Masquer le contenu")).last

    try:
        p.goto("/events/admin/reports")
        page.wait_for_timeout(6000)
        p.shot("file")
        tree = p.dump("file")
        for label in ("Petit mot", "Choix de sondage", "Objet à amener", "Sondage"):
            if label not in tree:
                p.flag("🟠", f"écran Signalements : type « {label} » absent de la file")
        for what, rx, check in (
                ("le mot de Marc", r"Je viens avec le dessert", lambda: not sql(f"select 1 from public.rsvp_notes where event_id = {q(eid)} and note = 'Je viens avec le dessert'")),
                ("l'objet de Marc", r"Gâteau de Marc", lambda: not sql(f"select 1 from public.bring_items where id = {q(st.get('r08_bring'))}")),
                ("le choix de Marc", r"Samedi \(Marc\)", lambda: not sql(f"select 1 from public.poll_options where id = {q(st.get('r08_option'))}")),
                ("le sondage", r"^Quel jour \?$", lambda: sql(f"select question from public.polls where id = {q(st['c2_poll'])}")[0]["question"].startswith("Question masquée")),
                ("l'événement", r"\[R-08\] Modération", lambda: "masqué" in sql(f"select title from public.events where id = {q(eid)}")[0]["title"])):
            with p.step(f"masquer {what}"):
                c = card(rx)
                if not c.count():
                    p.flag("🟠", f"carte du signalement « {what} » introuvable")
                    continue
                c.scroll_into_view_if_needed(timeout=30000)
                p.tap(c.get_by_role("button", name="Masquer le contenu").first, f"Masquer {what}")
                page.wait_for_timeout(5000)
                p.shot("apres-masquer")
                if not check():
                    p.flag("🔴", f"« Masquer le contenu » ne retire pas {what}")
        with p.step("avertir l'auteur du message"):
            c = page.locator("div").filter(has=page.get_by_text("Bot Marc")).filter(has=page.get_by_role("button", name="Avertir")).last
            if c.count():
                note = c.get_by_label("Note (envoyée avec l’avertissement)")
                if note.count():
                    p.type(note.first, "Avertissement du banc R-08, à ignorer", "la note")
                p.tap(c.get_by_role("button", name="Avertir").first, "Avertir")
                page.wait_for_timeout(4000)
                s = sql(f"select kind from public.moderation_sanctions where user_id = {q(m.uid('membre1'))} and note like 'Avertissement du banc R-08%'")
                if not s:
                    p.flag("🔴", "« Avertir » n'enregistre pas d'avertissement")
    finally:
        p.close()
    ui_sanctions(browser, origin, eid)


def ui_sanctions(browser, origin, eid: str) -> None:
    """Suspendre / Réintégrer / Bannir / Réintégrer Bot Sara depuis l'écran ; ce que Sara peut faire entre-temps."""
    sara = m.uid(NO_TERMS)
    s = sess(NO_TERMS)
    m.accept(s)
    msg = m.rest(s, "POST", "messages", json={"event_id": eid, "user_id": sara, "body": "Message de Sara à signaler"})
    gina = sess("guest2")
    gina.rpc("report_content", p_kind="event_message", p_target=msg.json()[0]["id"], p_reason="spam", p_comment="Banc R-08 sanctions, à ignorer")
    gina.rpc("report_content", p_kind="profile", p_target=sara, p_reason="spam", p_comment="Banc R-08 sanctions bis, à ignorer")
    p = phone(browser, "admin", origin, "r08-sanctions")
    page = p.page
    try:
        for action, label in (("suspend", re.compile(r"^Suspendre \d+ jour")), ("ban", re.compile("^Bannir le compte"))):
            with p.step(f"{action} Sara"):
                p.goto("/events/admin/reports")
                page.wait_for_timeout(6000)
                c = page.locator("div").filter(has=page.get_by_text(re.compile("Message de Sara à signaler|Bot Sara"))).filter(
                    has=page.get_by_role("button", name=label)).last
                if not c.count():
                    p.dump(f"file-{action}")
                    p.flag("🟠", f"bouton {action} introuvable sur un signalement de Sara")
                    continue
                c.scroll_into_view_if_needed(timeout=30000)
                p.tap(c.get_by_role("button", name=label).first, action)
                page.wait_for_timeout(5000)
                p.shot(f"apres-{action}")
                status = sql(f"select status from public.profiles where id = {q(sara)}")[0]["status"]
                sanc = sql(f"select kind, ends_at, lifted_at from public.moderation_sanctions where user_id = {q(sara)} order by created_at desc limit 1")
                p.log(f"Sara : statut {status} ; sanction {sanc}")
                if status != "banned":
                    p.flag("🔴", f"« {action} » ne retire pas l'accès de Sara", str(sanc))
                # Ce que Sara peut encore faire (session déjà ouverte)
                r = m.rest(s, "POST", "messages", json={"event_id": eid, "user_id": sara, "body": "Sara suspendue écrit"})
                rr = m.rest(s, "PATCH", f"rsvps?event_id=eq.{eid}&user_id=eq.{sara}", json={"status": "no"})
                rp = s.rpc("report_content", p_kind="event", p_target=eid, p_reason="spam", p_comment="Banc R-08 sanctions, à ignorer")
                rs = m.rest(s, "GET", f"events?id=eq.{eid}&select=id")
                p.log(f"Sara bannie : message {r.status_code} ; réponse {rr.status_code} {rr.text[:60]} ; signaler {rp.status_code} ; lire {rs.status_code} {rs.text[:60]}")
                if r.status_code < 300:
                    p.flag("🔴", f"Sara ({action}) écrit encore dans le forum")
                lift = page.get_by_role("button", name=re.compile("^Réintégrer Bot Sara"))
                p.goto("/events/admin/reports")
                page.wait_for_timeout(1000)
                page.get_by_role("radio", name="Traités").or_(page.get_by_role("button", name="Traités")).first.click()
                page.wait_for_timeout(5000)
                p.shot(f"traites-{action}")
                if not lift.count():
                    p.dump(f"traites-{action}")
                    p.flag("🟠", f"« Réintégrer Bot Sara » introuvable après {action}")
                    sql(f"update public.profiles set status = 'active' where id = {q(sara)}")
                    sql(f"update public.moderation_sanctions set lifted_at = now() where user_id = {q(sara)} and lifted_at is null")
                    continue
                p.tap(lift.first, "Réintégrer Bot Sara")
                page.wait_for_timeout(4000)
                p.shot(f"reintegre-{action}")
                status = sql(f"select status from public.profiles where id = {q(sara)}")[0]["status"]
                p.log(f"après Réintégrer : {status}")
                if status != "active":
                    p.flag("🔴", "« Réintégrer » ne rend pas l'accès à Sara")
                    sql(f"update public.profiles set status = 'active' where id = {q(sara)}")
                r = m.rest(s, "POST", "messages", json={"event_id": eid, "user_id": sara, "body": "Sara réintégrée écrit"})
                p.log(f"Sara réintégrée écrit : {r.status_code} {r.text[:80]}")
                if r.status_code >= 300:
                    p.flag("🟠", "Sara réintégrée ne peut plus écrire (session ou statut)", r.text[:200])
    finally:
        p.close()
        sql(f"update public.profiles set status = 'active' where id = {q(sara)} and status = 'banned'")


def ui_contents(browser, origin, eid: str) -> None:
    """Marc, au doigt : « Ce que j'amène » et « Proposer une option » avec propos haineux (refus clair ?) puis insulte."""
    p = phone(browser, "membre1", origin, "r08-contenus")
    page = p.page
    marc = m.uid("membre1")
    try:
        for label, kind, table, col in (("Ce que j’amène", "objet", "bring_items", "added_by"),
                                        ("Proposer une option", "option", "poll_options", "created_by")):
            with p.step(f"{kind} : propos haineux puis insulte"):
                m._open_event(p, eid)
                field = page.get_by_label(label, exact=True)
                if not field.count():
                    p.scroll_to_bottom("fiche", tries=6)
                if not field.count():
                    p.dump(f"sans-{kind}")
                    p.flag("🟠", f"champ « {label} » absent pour Marc (Présent)")
                    continue
                field.first.scroll_into_view_if_needed()
                for text in (f"Chips {HATE}", "Chips connard"):
                    p.type(field.first, text, kind)
                    field.first.press("Enter") if kind == "objet" else p.tap(page.get_by_role("button", name="Ajouter", exact=True).first, "Ajouter")
                    page.wait_for_timeout(4000)
                    p.shot(f"{kind}-{'haine' if HATE in text else 'insulte'}")
                    rows = sql(f"select label from public.{table} where {col} = {q(marc)} and label like 'Chips%'")
                    err = page.get_by_text(re.compile("non enregistr|propos haineux|content_refused", re.I))
                    txt = err.first.inner_text() if err.count() else None
                    p.log(f"{kind} « {text} » : base {rows} ; message {txt!r} ; champ {field.first.input_value()!r}")
                    if HATE in text:
                        if any(HATE in r["label"] for r in rows):
                            p.flag("🔴", f"{kind} haineux enregistré", str(rows))
                        if not txt:
                            p.flag("🟠", f"{kind} haineux refusé sans message à l'écran")
                        elif "content_refused" in txt:
                            p.flag("🟡", f"{kind} : le refus affiche la clé technique content_refused", txt)
                    sql(f"delete from public.{table} where {col} = {q(marc)} and label like 'Chips%'")
    finally:
        p.close()


def ui_preview(browser, origin, eid: str) -> None:
    """Olga (qui a bloqué Gus) : l'aperçu « Discussion » de la fiche montre-t-il le texte de Gus ?
    Puis la feuille Inviter : Gus est-il proposé, et que se passe-t-il au toucher ?"""
    p = phone(browser, "orga1", origin, "r08-apercu")
    page = p.page
    gus = m.uid("guest1")
    try:
        with p.step("aperçu Discussion de la fiche"):
            if not sql(f"select 1 from public.direct_blocks where user_id = {q(m.uid('orga1'))} and blocked_id = {q(gus)}"):
                sess("orga1").rpc("set_block", target=gus, blocked=True)
            sql(f"insert into public.messages (event_id, user_id, body) values ({q(eid)}, {q(gus)}, 'Dernier mot de Gus (bloqué)')")
            m._open_event(p, eid)
            sec = page.get_by_role("link", name=re.compile("^Discussion"))
            sec.first.scroll_into_view_if_needed(timeout=30000)
            page.wait_for_timeout(1500)
            p.shot("apercu-discussion")
            if page.get_by_text(re.compile("Dernier mot de Gus")).count():
                p.flag("🟠", "fiche : l'aperçu « Discussion » montre le texte d'une personne bloquée (le forum, lui, le masque)")
        with p.step("feuille Inviter : chercher Gus"):
            sql(f"delete from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")
            page.reload()
            page.wait_for_timeout(5000)
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
            page.wait_for_timeout(2500)
            sheet = page.get_by_role("dialog", name=re.compile("^Inviter à "))
            search = sheet.get_by_placeholder(re.compile("prénom", re.I))
            p.type(search.first, "Gus", "la recherche")
            page.wait_for_timeout(3000)
            p.shot("inviter-gus")
            tree = p.dump("inviter-gus")
            rows = [l for l in tree.splitlines() if "Gus" in l]
            p.log(f"lignes Gus dans la feuille : {rows}")
            if not rows:
                p.log("Gus (bloqué) n'est pas proposé dans la feuille Inviter")
                return
            btn = sheet.get_by_role("button", name=re.compile("Gus"))
            p.tap(btn.last, "Gus")
            page.wait_for_timeout(4000)
            p.shot("inviter-gus-apres")
            n = sql(f"select count(*) n from public.event_invites where event_id = {q(eid)} and user_id = {q(gus)}")[0]["n"]
            msg = page.get_by_text(re.compile("ne peux pas inviter|bloqu", re.I))
            txt = msg.first.inner_text() if msg.count() else None
            p.log(f"invité en base : {n} ; message : {txt!r}")
            if n:
                p.flag("🔴", "Gus (bloqué) invité depuis la feuille Inviter")
            elif not txt:
                p.flag("🟠", "feuille Inviter : Gus (bloqué) proposé, refus non expliqué")
            elif "blocked:" in txt:
                p.flag("🟡", "le refus affiche la clé technique « blocked: »", txt)
    finally:
        p.close()


def ui_groups_and_buttons(browser, origin) -> None:
    m.ui_buttons_by_role(browser, origin, load_state()["e_full"])
    m.ui_groups(browser, origin)


def phase_cleanup() -> None:
    st = load_state()
    restore_terms(NO_TERMS)
    restore_terms(UI_NO_TERMS)
    sara = m.uid(NO_TERMS)
    sql(f"update public.profiles set status = 'active' where id = {q(sara)} and status = 'banned'")
    m.phase_moderation_cleanup(None, None, None)
    sql("delete from public.content_reports where comment like 'Banc R-08%'")
    sql(f"delete from public.moderation_sanctions where user_id = {q(sara)} and report_id in (select id from public.content_reports where false)")
    sql("delete from public.moderation_sanctions where note like 'Avertissement du banc R-08%'")
    sql("delete from public.notifications where kind = 'moderation_notice' and body like 'Avertissement du banc R-08%'")
    sql(f"delete from public.direct_blocks where user_id = {q(m.uid('membre3'))} and blocked_id = {q(m.uid('guest1'))}")
    print("restant [R-08] :", sql(f"select count(*) n from public.events where title like {q(PREFIX + '%')}"), st.get("c2_events"))


def main(argv: list[str]) -> None:
    what = argv[0]
    if what == "api":
        phase_api()
        make_full()
        return
    if what == "cleanup":
        phase_cleanup()
        return
    only = set(argv[0].split(":")[1].split(",")) if ":" in argv[0] else None
    eid = load_state()["c2_mod_event"]
    steps = {"cgu": ui_cgu, "filtre": ui_filter, "signaler": ui_report, "bloquer": ui_block, "admin": ui_admin,
             "sanctions": ui_sanctions, "contenus": ui_contents, "apercu": ui_preview}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        origin = load_state()["origin"]
        for name, run in steps.items():
            if only and name not in only:
                continue
            print(f"── {name} ──", flush=True)
            try:
                run(browser, origin, eid)
            except Exception as e:
                anomaly("banc", "🟠", f"étape UI {name} interrompue", f"{type(e).__name__}: {str(e)[:400]}")
                print(f"étape {name} interrompue : {e}", flush=True)
        if only and "groupes" in only:
            try:
                ui_groups_and_buttons(browser, origin)
            except Exception as e:
                anomaly("banc", "🟠", "étape UI groupes interrompue", f"{type(e).__name__}: {str(e)[:400]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
