"""Matrice des droits « Événements » sur la base de TEST : pour chaque droit, le bot de test (Bot Violette, passé au rôle
personnalisé « Bot rôle test ») l'A puis ne l'a PLUS ; on regarde l'écran (bouton visible ?) ET la base (appel direct à
l'API REST Supabase avec le jeton du bot : l'écran ne doit pas être le seul garde-fou).

Rôles et droits sont photographiés avant et remis exactement à la fin (ranks compris). Résultat : rights.json + tableau
dans le rapport. Usage : .venv/bin/python -m tests.bots.run droits_matrice"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from tests.bots.bench import OUT, load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, GROUP_BOTS_2, TEST_URL, Session, q, sql

ROLE_LABEL = "Bot rôle test"
TESTER = "vip4"  # Bot Violette (Membre VIP au départ, groupe « Bots 2 » seulement)
PERMS = ["events.view", "events.rsvp", "events.create", "events.publish_direct", "events.approve",
         "events.edit_own_published", "events.manage_all", "events.plus_ones", "events.see_participants", "polls.create",
         "tickets.scan", "tickets.pay", "ai.use", "moderation.reports", "members.invite", "members.view_identity",
         "taxonomy.manage", "announcements.publish", "zicou.event_coins"]
BASE = ["chat.write"]  # écrire dans un forum : hors matrice, toujours donné


def rest(s: Session, method: str, path: str, **kw) -> httpx.Response:
    headers = {**s.headers, "Prefer": "return=representation", **kw.pop("headers", {})}
    return httpx.request(method, f"{TEST_URL}/rest/v1/{path}", headers=headers, timeout=30, **kw)


def ok(r: httpx.Response) -> bool:
    return r.status_code < 300 and r.text not in ("[]", "")


def iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class Matrix:
    def __init__(self, browser, origin):
        self.origin = origin
        self.admin = Session(BY_KEY["admin"].phone)
        self.orga = Session(BY_KEY["orga1"].phone)
        self.vip = Session(BY_KEY["vip1"].phone)
        self.marc = Session(BY_KEY["membre1"].phone)
        self.me = Session(BY_KEY[TESTER].phone)
        self.p = phone(browser, TESTER, origin, "droits-matrice")
        self.rows: list[dict] = []

    # ── mise en place ──
    def snapshot(self) -> None:
        roles = sql("select key, rank from public.roles order by rank")
        perms = sql("select role, perm from public.role_permissions order by 1, 2")
        role = sql(f"select role from public.profiles where id = {q(self.me.uid)}")[0]["role"]
        (OUT / "roles-avant.json").write_text(json.dumps({"roles": roles, "perms": perms, "tester_role": role}, indent=1))
        save_state(rights_snapshot=str(OUT / "roles-avant.json"))

    def setup(self) -> None:
        self.snapshot()
        existing = sql(f"select key from public.roles where label = {q(ROLE_LABEL)}")
        key = existing[0]["key"] if existing else self.admin.rpc("create_role", role_label=ROLE_LABEL, role_color="#123456").json()
        self.role = key
        save_state(rights_role=key)
        self.set_perms(PERMS + BASE)
        sql(f"update public.profiles set role = {q(key)} where id = {q(self.me.uid)}")
        # Bot Violette garde les groupes « Bots 2 » (pas « Bots ») ; quitter Membre VIP la sort de Vendredi Party.
        start = iso(20)
        self.m = self._event(self.orga, "Bot matrice des droits", visibility="invited", tickets_enabled=True, price_chf=10,
                             show_participants=False, allow_plus_ones=True, max_plus_ones=2, starts_at=start)
        rest(self.orga, "POST", "event_invites", json={"event_id": self.m, "user_id": self.me.uid})
        rest(self.orga, "POST", "event_invites", json={"event_id": self.m, "user_id": self.marc.uid})
        rest(self.marc, "POST", "rsvps", json={"event_id": self.m, "user_id": self.marc.uid, "status": "yes"})
        # Public SANS lien public : seuls les comptes qui ont « Voir les événements » le voient (can_see_event).
        self.v = self._event(self.orga, "Bot matrice public", visibility="all", public_link=False, starts_at=start)
        # Hors matrice : CGU acceptées et accord IA donné (sinon tout refus viendrait des CGU / de l'accord, pas du droit).
        version = sql("select terms_version from private.moderation_settings where id = 1")[0]["terms_version"]
        self.me.rpc("accept_terms", p_version=version)
        httpx.post(f"{self.origin}/api/account/ai/consent", json={"token": self.me.token, "accept": True}, timeout=30)
        self.pending = self._event(self.vip, "Bot matrice proposition", visibility="invited", status="pending", starts_at=start)
        self.own = self._event(self.me, "Bot matrice : l'événement de Violette", visibility="invited", starts_at=start)
        save_state(rights_events=[self.m, self.v, self.pending, self.own])

    def _event(self, s: Session, title: str, status: str = "published", **fields) -> str:
        body = {"title": title, "created_by": s.uid, "status": status, "date_mode": "fixed", "notify_on_publish": False,
                "description": "Matrice des droits du banc des bots. Ignorer.", **fields}
        r = rest(s, "POST", "events", json=body)
        if r.status_code >= 300:
            raise RuntimeError(f"création {title} : {r.status_code} {r.text}")
        return r.json()[0]["id"]

    def set_perms(self, perms: list[str]) -> None:
        sql(f"delete from public.role_permissions where role = {q(self.role)}; "
            f"insert into public.role_permissions (role, perm) select {q(self.role)}, unnest(array[{','.join(q(x) for x in perms)}])")

    def grant(self, perm: str, granted: bool) -> None:
        """Comme l'écran Rôles de l'admin : set_role_permission avec la session de Bot Ada."""
        r = self.admin.rpc("set_role_permission", target=self.role, perm=perm, granted=granted)
        if r.status_code >= 300:
            raise RuntimeError(f"set_role_permission {perm} {granted} : {r.status_code} {r.text}")

    def restore(self) -> None:
        snap = json.loads((OUT / "roles-avant.json").read_text())
        sql(f"update public.profiles set role = {q(snap['tester_role'])} where id = {q(self.me.uid)}")
        r = self.admin.rpc("delete_role", role_key=self.role, move_to=snap["tester_role"])
        self.p.log(f"delete_role : {r.status_code} {r.text[:200]}")
        sql(f"delete from public.role_permissions where role = {q(self.role)}; delete from public.roles where key = {q(self.role)}")
        for row in snap["roles"]:
            sql(f"update public.roles set rank = {row['rank']} where key = {q(row['key'])}")
        now = {(x["role"], x["perm"]) for x in sql("select role, perm from public.role_permissions")}
        before = {(x["role"], x["perm"]) for x in snap["perms"]}
        for role, perm in before - now:
            sql(f"insert into public.role_permissions (role, perm) values ({q(role)}, {q(perm)})")
        for role, perm in now - before:
            sql(f"delete from public.role_permissions where role = {q(role)} and perm = {q(perm)}")
        after_roles = sql("select key, rank from public.roles order by rank")
        after_perms = sql("select role, perm from public.role_permissions order by 1, 2")
        same = after_roles == snap["roles"] and after_perms == snap["perms"]
        self.p.log(f"rôles et droits remis comme avant : {same}")
        save_state(rights_restored=same)

    # ── écran ──
    def ui(self, path: str, anchor, target, wait: int = 2500) -> bool:
        page = self.p.page
        self.p.goto(path)
        try:
            anchor(page).first.wait_for(state="visible", timeout=20000)
        except Exception:
            self.p.log(f"repère de chargement absent sur {path}")
        page.wait_for_timeout(wait)
        visible = target(page).count() > 0 and target(page).first.is_visible()
        return visible

    def page_event(self, eid: str, target) -> bool:
        return self.ui(f"/events/event/{eid}", lambda pg: pg.get_by_role("button", name="Retour : Événements"), target)

    # ── sondes : (écran, base) → vrai = permis / visible ──
    def probe(self, perm: str) -> tuple[bool | None, bool | None, str]:
        s, page = self.me, self.p.page
        if perm == "events.view":
            api = ok(rest(s, "GET", f"events?id=eq.{self.v}&select=id"))
            ui = self.page_event(self.v, lambda pg: pg.get_by_text("Bot matrice public"))
            return ui, api, "événement public d'un autre"
        if perm == "events.rsvp":
            sql(f"delete from public.rsvps where event_id = {q(self.m)} and user_id = {q(s.uid)}")
            r = rest(s, "POST", "rsvps", json={"event_id": self.m, "user_id": s.uid, "status": "maybe"})  # comme lib/rsvp.ts
            api = ok(r)
            sql(f"delete from public.rsvps where event_id = {q(self.m)} and user_id = {q(s.uid)}")
            ui = self.page_event(self.m, lambda pg: pg.get_by_role("radiogroup").get_by_role("button", name="Présent"))
            return ui, api, f"POST rsvps → {r.status_code}"
        if perm == "events.create":
            r = rest(s, "POST", "events", json={"title": "Bot matrice brouillon", "created_by": s.uid, "status": "draft",
                                                 "date_mode": "fixed", "starts_at": iso(21), "visibility": "invited", "notify_on_publish": False})
            if ok(r):
                rest(s, "DELETE", f"events?id=eq.{r.json()[0]['id']}")
            ui = self.ui("/events/", lambda pg: pg.get_by_text(re.compile("^Salut ")),
                         lambda pg: pg.get_by_role("button", name="Proposer un événement"))
            return ui, ok(r), f"POST events (brouillon) → {r.status_code}"
        if perm == "events.publish_direct":
            r = rest(s, "POST", "events", json={"title": "Bot matrice publié", "created_by": s.uid, "status": "published",
                                                 "date_mode": "fixed", "starts_at": iso(21), "visibility": "invited", "notify_on_publish": False})
            status = r.json()[0]["status"] if ok(r) else None
            if ok(r):
                rest(s, "DELETE", f"events?id=eq.{r.json()[0]['id']}")
                sql(f"delete from public.events where id = {q(r.json()[0]['id'])}")
            ui = self.ui("/events/event/new", lambda pg: pg.get_by_label("Titre", exact=True),
                         lambda pg: pg.get_by_role("button", name="Publier", exact=True))
            return ui, status == "published", f"POST events status=published → {r.status_code} {status}"
        if perm == "events.approve":
            r = s.rpc("approve_event", e=self.pending)
            st = sql(f"select status from public.events where id = {q(self.pending)}")[0]["status"]
            sql(f"update public.events set status = 'pending', approved_by = null where id = {q(self.pending)}")
            ui = self.page_event(self.pending, lambda pg: pg.get_by_role("button", name="Approuver"))
            return ui, st == "published", f"rpc approve_event → {r.status_code} {st}"
        if perm == "events.edit_own_published":
            r = rest(s, "PATCH", f"events?id=eq.{self.own}", json={"description": "modifiée par la matrice"})
            changed = sql(f"select description from public.events where id = {q(self.own)}")[0]["description"] == "modifiée par la matrice"
            sql(f"update public.events set description = 'Matrice des droits du banc des bots. Ignorer.' where id = {q(self.own)}")
            ui = self.page_event(self.own, lambda pg: pg.get_by_role("button", name="Modifier", exact=True))
            return ui, changed, f"PATCH son événement publié → {r.status_code}"
        if perm == "events.manage_all":
            r = rest(s, "PATCH", f"events?id=eq.{self.m}", json={"description": "modifiée par un autre"})
            changed = sql(f"select description from public.events where id = {q(self.m)}")[0]["description"] == "modifiée par un autre"
            sql(f"update public.events set description = 'Matrice des droits du banc des bots. Ignorer.' where id = {q(self.m)}")
            ui = self.page_event(self.m, lambda pg: pg.get_by_role("button", name="Modifier", exact=True))
            return ui, changed, f"PATCH l'événement d'un autre → {r.status_code}"
        if perm == "events.plus_ones":
            sql(f"insert into public.rsvps (event_id, user_id, status) values ({q(self.m)}, {q(s.uid)}, 'yes') on conflict (event_id, user_id) do update set status = 'yes', plus_ones = 0")
            r = rest(s, "PATCH", f"rsvps?event_id=eq.{self.m}&user_id=eq.{s.uid}", json={"plus_ones": 1})
            n = sql(f"select plus_ones from public.rsvps where event_id = {q(self.m)} and user_id = {q(s.uid)}")[0]["plus_ones"]
            ui = self.page_event(self.m, lambda pg: pg.get_by_label("Ajouter un accompagnant"))
            sql(f"delete from public.rsvps where event_id = {q(self.m)} and user_id = {q(s.uid)}")
            return ui, n == 1, f"PATCH rsvps plus_ones=1 → {r.status_code}, base {n}"
        if perm == "events.see_participants":
            r = rest(s, "GET", f"rsvps?event_id=eq.{self.m}&select=user_id")
            api = self.marc.uid in r.text
            ui = self.page_event(self.m, lambda pg: pg.get_by_text("Bot Marc"))
            return ui, api, "liste masquée (show_participants=false) : lire les réponses des autres"
        if perm == "polls.create":
            r = rest(s, "POST", "polls", json={"event_id": self.own, "question": "Matrice ?", "created_by": s.uid})
            if ok(r):
                sql(f"delete from public.polls where id = {q(r.json()[0]['id'])}")
            ui = self.ui(f"/events/event/{self.own}/edit", lambda pg: pg.get_by_label("Titre", exact=True),
                         lambda pg: pg.get_by_role("button", name="+ Ajouter un sondage"))
            if not ui:  # mode simple : le bouton est dans « Avancé »
                tab = page.get_by_role("tab", name="Avancé")
                if tab.count():
                    tab.tap()
                    page.wait_for_timeout(1000)
                    ui = page.get_by_role("button", name="+ Ajouter un sondage").count() > 0
            return ui, ok(r), f"POST polls → {r.status_code}"
        if perm == "tickets.scan":
            r = s.rpc("set_ticket_arrival", e=self.m, member=self.marc.uid, arrived=True)
            arrived = bool(sql(f"select checked_in_at from public.event_tickets where event_id = {q(self.m)} and user_id = {q(self.marc.uid)}") and
                           sql(f"select checked_in_at from public.event_tickets where event_id = {q(self.m)} and user_id = {q(self.marc.uid)}")[0]["checked_in_at"])
            sql(f"update public.event_tickets set checked_in_at = null, checked_in_by = null where event_id = {q(self.m)}")
            ui = self.page_event(self.m, lambda pg: pg.get_by_role("button", name="📷 Scanner les billets"))
            return ui, arrived, f"rpc set_ticket_arrival → {r.status_code} {r.text[:120]}"
        if perm == "tickets.pay":
            r = s.rpc("set_ticket_paid", e=self.m, member=self.marc.uid, is_paid=True)
            rows = sql(f"select paid from public.event_tickets where event_id = {q(self.m)} and user_id = {q(self.marc.uid)}")
            paid = bool(rows and rows[0]["paid"])
            sql(f"update public.event_tickets set paid = false, paid_at = null, paid_by = null where event_id = {q(self.m)}")
            ui = self.ui(f"/events/event/{self.m}/scan", lambda pg: pg.get_by_text("Bot Marc"),
                         lambda pg: pg.get_by_role("button", name="Payé ?"))
            return ui, paid, f"rpc set_ticket_paid → {r.status_code} {r.text[:120]}"
        if perm == "ai.use":
            r = httpx.post(f"{self.origin}/api/account/ai/status", json={"token": s.token}, timeout=30)
            d = httpx.post(f"{self.origin}/api/account/ai/event/draft/save", timeout=30,
                           json={"token": s.token, "draft": {"title": "Bot IA matrice", "start": iso(22)[:16]}, "place": None})
            if d.status_code == 200:
                sql(f"delete from public.events where id = {q(d.json()['id'])}")
            return None, d.status_code == 200, f"ai/status allowed={r.json().get('allowed')} ; draft/save → {d.status_code} (bouton IA : app iPhone seulement)"
        if perm == "moderation.reports":
            r = s.rpc("moderation_queue")
            ui = self.ui("/events/admin/reports", lambda pg: pg.get_by_role("heading").first,
                         lambda pg: pg.get_by_text(re.compile("Spam|signalement", re.I)))
            return ui, r.status_code < 300, f"rpc moderation_queue → {r.status_code}"
        if perm == "members.invite":
            r = s.rpc("my_app_invite")
            ui = self.ui("/events/profile", lambda pg: pg.get_by_text(re.compile("Bot Violette")),
                         lambda pg: pg.get_by_text(re.compile("Inviter dans Party|Invite (un|des) ami", re.I)))
            return ui, r.status_code < 300, f"rpc my_app_invite → {r.status_code} {r.text[:80]}"
        if perm == "members.view_identity":
            r = s.rpc("member_card", target=self.marc.uid)
            api = "790000109" in r.text
            ui = self.ui(f"/events/member/{self.marc.uid}", lambda pg: pg.get_by_text("Bot Marc"),
                         lambda pg: pg.get_by_text(re.compile("79 000 01 09|790000109")))
            return ui, api, f"rpc member_card → numéro visible {api}"
        if perm == "taxonomy.manage":
            name = f"bot-{uuid.uuid4().hex[:6]}"
            r = rest(s, "POST", "tags", json={"name": name, "created_by": s.uid})
            sql(f"delete from public.tags where name = {q(name)}")
            ui = self.ui("/events/event/new", lambda pg: pg.get_by_label("Titre", exact=True),
                         lambda pg: pg.get_by_placeholder("Nouveau tag"))
            return ui, ok(r), f"POST tags → {r.status_code}"
        if perm == "announcements.publish":
            # Jamais une vraie annonce (vrais membres) : titre vide → refus de validation si permis, refus de droit sinon.
            r = s.rpc("publish_admin_announcement", announcement_title="", announcement_body="")
            forbidden = r.status_code in (401, 403) or "forbidden" in r.text.lower()
            ui = self.ui("/events/admin/announcements", lambda pg: pg.get_by_role("heading").first,
                         lambda pg: pg.get_by_role("button", name=re.compile("Publier|Envoyer")))
            return ui, not forbidden, f"rpc publish_admin_announcement (vide) → {r.status_code} {r.text[:120]}"
        if perm == "zicou.event_coins":
            api = httpx.get(f"{self.origin}/api/pet/state", timeout=30).status_code
            ui = self.page_event(self.m, lambda pg: pg.get_by_text(re.compile("Zicou|pièces", re.I)))
            return ui, None, f"Zicou éteint : /api/pet → {api} ; lien « cadeaux Zicou » sur la fiche : {ui}"
        raise KeyError(perm)

    def record(self, perm: str, has: bool, ui, api, detail: str) -> None:
        row = {"perm": perm, "has": has, "ui": ui, "api": api, "detail": detail}
        self.rows.append(row)
        self.p.log(f"{'A' if has else 'SANS'} {perm} → écran {ui} · base {api} · {detail}")

    def run(self) -> None:
        for perm in PERMS:
            with self.p.step(f"{perm} : avec"):
                self.record(perm, True, *self.probe(perm))
            with self.p.step(f"{perm} : sans"):
                # events.manage_all = is_admin() dans la base : il ouvrirait tout ; « sans » le retire aussi.
                off = [perm] + ([] if perm == "events.manage_all" else ["events.manage_all"])
                for x in off:
                    self.grant(x, False)
                try:
                    self.record(perm, False, *self.probe(perm))
                finally:
                    for x in off:
                        self.grant(x, True)
        with self.p.step("tickets.scan ET tickets.pay : sans les deux"):
            self.grant("tickets.scan", False)
            self.grant("tickets.pay", False)
            self.grant("events.manage_all", False)
            try:
                ui, api, detail = self.probe("tickets.scan")
                self.record("tickets.scan + tickets.pay (aucun des deux)", False, ui, api, detail)
                ui, api, detail = self.probe("tickets.pay")
                self.record("tickets.pay + tickets.scan (aucun des deux)", False, ui, api, detail)
            finally:
                self.grant("tickets.scan", True)
                self.grant("tickets.pay", True)
                self.grant("events.manage_all", True)
        (OUT / "rights.json").write_text(json.dumps(self.rows, indent=1, ensure_ascii=False))

    def groups_and_roles(self) -> None:
        """Groupes : Bot Violette (dans « Bots 2 », pas dans « Bots ») ; organisateur / co-organisateur / invité."""
        s = self.me
        self.grant("events.manage_all", False)  # un admin (manage_all) garde tous les groupes : on le retire ici
        gid = {g["name"]: g["id"] for g in sql("select id, name from public.member_groups where name in ('Bots', 'Bots 2')")}
        own = self.own
        for name in (GROUP_BOTS, GROUP_BOTS_2):
            r = rest(s, "POST", "event_groups", json={"event_id": own, "group_id": gid[name]})
            self.record(f"groupe « {name} » sur son événement", name == GROUP_BOTS_2, None, r.status_code < 300, f"POST event_groups → {r.status_code} {r.text[:100]}")
            sql(f"delete from public.event_groups where event_id = {q(own)}")
        ui_chips = self.ui("/events/event/new", lambda pg: pg.get_by_label("Titre", exact=True),
                           lambda pg: pg.get_by_role("button", name=re.compile(rf"^(✓ )?{GROUP_BOTS} · ")))
        self.record("choisir le groupe « Bots » (hors du groupe)", False, ui_chips, None, "puce visible dans le formulaire")
        self.grant("events.manage_all", True)
        full = load_state()["e_full"]
        oscar, marc = Session(BY_KEY["orga2"].phone), self.marc
        for who, sess, expected in (("co-organisateur (Bot Oscar)", oscar, True), ("simple invité (Bot Marc)", marc, False)):
            before = sql(f"select description from public.events where id = {q(full)}")[0]["description"]
            r = rest(sess, "PATCH", f"events?id=eq.{full}", json={"description": before + " ·"})
            changed = sql(f"select description from public.events where id = {q(full)}")[0]["description"] != before
            sql(f"update public.events set description = {q(before)} where id = {q(full)}")
            self.record(f"{who} modifie l'événement", expected, None, changed, f"PATCH events → {r.status_code}")
            t = sess.rpc("issue_event_ticket", e=full, member=marc.uid, issued=True)
            self.record(f"{who} remet un billet", expected, None, t.status_code < 300, f"rpc issue_event_ticket → {t.status_code} {t.text[:80]}")
        (OUT / "rights.json").write_text(json.dumps(self.rows, indent=1, ensure_ascii=False))

    def cleanup(self) -> None:
        for eid in load_state().get("rights_events", []):
            sql(f"delete from public.events where id = {q(eid)}")


def phase_droits_matrice(browser, origin, only):
    m = Matrix(browser, origin)
    try:
        m.setup()
        m.run()
        m.groups_and_roles()
    finally:
        try:
            m.restore()
        finally:
            m.cleanup()
            m.p.close()
