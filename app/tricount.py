"""Tricount pour l'app iOS (Réglages › Pot commun) : relais vers la base avec la session du membre. La base (règles RLS,
fonctions tc_*) décide qui lit et écrit ; ce module met en forme et ajoute le calcul (tricount_logic) : soldes,
remboursements les moins nombreux, parts de chacun, catégorie devinée, lien pour rejoindre, photos des tickets."""
import re
import time
import uuid

from . import tricount_logic as tc
from .accounts import SUPABASE_URL, AccountError
from .group_admin import GroupAdmin

RECEIPT_MAX = 8 * 1024 * 1024
RECEIPT_TTL = 3600
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CURRENCIES = ("CHF", "EUR", "USD", "GBP")
MAX_TITLE, MAX_NAME = 80, 40


class Tricount:
    def __init__(self, admin: GroupAdmin, link_base):
        self.admin = admin
        self.link_base = link_base  # () -> adresse publique du site (lien à partager)

    # ── Lecture ──
    def _receipts(self, token: str, paths: list[str]) -> dict[str, str]:
        paths = sorted({p for p in paths if p})
        if not paths:
            return {}
        r = self.admin._call("POST", "/storage/v1/object/sign/tc-receipts", token, json={"expiresIn": RECEIPT_TTL, "paths": paths})
        rows = r.json() if r.status_code == 200 else []
        return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
                for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}

    def link(self, join_token: str) -> str:
        return f"{self.link_base().rstrip('/')}/pot/{join_token}"

    def shape(self, g: dict, token: str = "", receipts: bool = False) -> dict:
        """Le pot commun tel que l'écran l'affiche : soldes, remboursements nommés, parts de chacun, catégories."""
        s = tc.summarize(g)
        names = {m["id"]: m["name"] for m in g.get("members", [])}
        signed = self._receipts(token, [e.get("receipt_path") for e in g.get("expenses", [])]) if receipts else {}
        members = []
        for m in g.get("members", []):
            pay = m.get("payment") or {}
            members.append({"id": m["id"], "name": m["name"], "linked": m.get("linked"), "left": m.get("left"), "me": m["id"] == g.get("me"),
                            "balance_cents": s["balances"].get(m["id"], 0),
                            "payment": {"iban": tc.format_iban(pay["iban"]) if pay.get("iban") else None, "holder": pay.get("holder"),
                                        "links": pay.get("links") or {}, "note": pay.get("note")} if pay else None})
        expenses = []
        for e in g.get("expenses", []):
            parts = tc.split(e)
            expenses.append({**{k: e.get(k) for k in ("id", "kind", "title", "amount_cents", "currency", "rate", "paid_by", "spent_on",
                                                      "category", "note", "split_mode", "receipt_path", "created_at")},
                             "group_amount_cents": tc.group_amount(e), "paid_by_name": names.get(e["paid_by"], "?"),
                             "shares": e.get("shares") or [], "parts": [{"member_id": k, "name": names.get(k, "?"), "amount_cents": v}
                                                                        for k, v in parts.items()],
                             "my_part_cents": parts.get(g.get("me"), 0), "receipt_url": signed.get(e.get("receipt_path") or "")})
        return {"id": g["id"], "name": g["name"], "emoji": g.get("emoji") or "💸", "currency": g.get("currency") or "CHF",
                "archived": g.get("archived", False), "me": g.get("me"), "link": self.link(g["join_token"]) if g.get("join_token") else None,
                "members": members, "expenses": expenses, "total_cents": s["total_cents"], "my_balance_cents": s["my_balance_cents"],
                "my_spent_cents": s["my_spent_cents"],
                "by_category": [{**c, "label": tc.CATEGORIES.get(c["category"], tc.CATEGORIES["other"])[0],
                                 "emoji": tc.CATEGORIES.get(c["category"], tc.CATEGORIES["other"])[1]} for c in s["by_category"]],
                "settle": [{**t, "from_name": names.get(t["from"], "?"), "to_name": names.get(t["to"], "?")} for t in s["settle"]]}

    def overview(self, token: str) -> dict:
        rows = self.admin._rpc(token, "tc_list", {}, "Les pots communs n'ont pas pu être chargés.") or []
        out = []
        for g in rows:
            s = tc.summarize(g)
            out.append({"id": g["id"], "name": g["name"], "emoji": g.get("emoji") or "💸", "currency": g.get("currency") or "CHF",
                        "archived": g.get("archived", False), "members": len([m for m in g.get("members", []) if not m.get("left")]),
                        "total_cents": s["total_cents"], "my_balance_cents": s["my_balance_cents"]})
        return {"tricounts": out, "categories": [{"id": k, "label": v[0], "emoji": v[1]} for k, v in tc.CATEGORIES.items()],
                "currencies": list(CURRENCIES)}

    def state(self, token: str, grp: str) -> dict:
        g = self.admin._rpc(token, "tc_state", {"grp": grp}, "Ce pot commun n'a pas pu être chargé.")
        return self.shape(g, token, receipts=True)

    # ── Écriture ──
    @staticmethod
    def _name(value: str, limit: int, what: str) -> str:
        v = " ".join((value or "").split())
        if not v:
            raise AccountError(f"Écris {what}")
        return v[:limit]

    def create(self, token: str, name: str, emoji: str, currency: str, my_name: str) -> dict:
        if currency not in CURRENCIES:
            raise AccountError("Monnaie inconnue")
        grp = self.admin._rpc(token, "tc_create", {"group_name": self._name(name, 60, "un nom"), "group_emoji": (emoji or "💸")[:8],
                                                  "group_currency": currency, "my_name": self._name(my_name, MAX_NAME, "ton prénom")},
                              "Le pot commun n'a pas pu être créé.")
        return self.state(token, grp)

    def update(self, token: str, grp: str, name: str | None, emoji: str | None, currency: str | None, archived: bool | None) -> dict:
        if currency and currency not in CURRENCIES:
            raise AccountError("Monnaie inconnue")
        self.admin._rpc(token, "tc_update_group", {"grp": grp, "group_name": name, "group_emoji": emoji, "group_currency": currency,
                                                  "is_archived": archived})
        return self.state(token, grp)

    def renew_link(self, token: str, grp: str) -> dict:
        self.admin._rpc(token, "tc_renew_link", {"grp": grp})
        return self.state(token, grp)

    def join_info(self, token: str, join_token: str) -> dict:
        info = self.admin._rpc(token, "tc_join_info", {"token": join_token}, "Lien invalide.")
        if not info:
            raise AccountError("Ce lien n'est plus valable : demande un nouveau lien.")
        return info

    def join(self, token: str, join_token: str, my_name: str, claim: str | None) -> dict:
        grp = self.admin._rpc(token, "tc_join", {"token": join_token, "my_name": self._name(my_name, MAX_NAME, "ton prénom"),
                                                "claim": claim if claim and UUID_RE.match(claim) else None}, "Impossible de rejoindre ce pot commun.")
        return self.state(token, grp)

    def add_member(self, token: str, grp: str, name: str) -> dict:
        self.admin._rpc(token, "tc_add_member", {"grp": grp, "member_name": self._name(name, MAX_NAME, "un prénom")})
        return self.state(token, grp)

    def rename_member(self, token: str, grp: str, member: str, name: str) -> dict:
        self.admin._rpc(token, "tc_rename_member", {"member": member, "member_name": self._name(name, MAX_NAME, "un prénom")})
        return self.state(token, grp)

    def remove_member(self, token: str, grp: str, member: str) -> dict:
        self.admin._rpc(token, "tc_remove_member", {"member": member})
        return self.state(token, grp)

    def leave(self, token: str, grp: str) -> dict:
        self.admin._rpc(token, "tc_leave", {"grp": grp})
        return self.overview(token)

    def save_expense(self, token: str, grp: str, exp: dict) -> dict:
        """Dépense ou remboursement : titre, montant, payeur, parts ; la catégorie est devinée si elle manque."""
        title = self._name(exp.get("title", ""), MAX_TITLE, "un titre")
        amount = int(exp.get("amount_cents") or 0)
        if amount <= 0 or amount > 100_000_000:
            raise AccountError("Montant invalide")
        mode = exp.get("split_mode") or "equal"
        if mode not in ("equal", "shares", "amounts"):
            raise AccountError("Partage inconnu")
        shares = [s for s in exp.get("shares") or [] if UUID_RE.match(str(s.get("member_id", "")))]
        if mode == "shares":
            shares = [s for s in shares if float(s.get("weight") or 0) > 0]
        if mode == "amounts":
            shares = [s for s in shares if int(s.get("amount_cents") or 0) > 0]
            if sum(int(s["amount_cents"]) for s in shares) != amount:
                raise AccountError("Les montants de chacun ne font pas le total")
        if not shares:
            raise AccountError("Choisis au moins une personne")
        currency = exp.get("currency") or "CHF"
        if currency not in CURRENCIES:
            raise AccountError("Monnaie inconnue")
        rate = float(exp.get("rate") or 1)
        if not 0 < rate < 100_000:
            raise AccountError("Taux de change invalide")
        kind = "transfer" if exp.get("kind") == "transfer" else "expense"
        payload = {"id": exp.get("id") or None, "kind": kind, "title": title, "amount_cents": amount, "currency": currency, "rate": rate,
                   "paid_by": exp.get("paid_by"), "spent_on": exp.get("spent_on") or None,
                   "category": exp.get("category") if exp.get("category") in tc.CATEGORIES else tc.guess_category(title),
                   "note": (exp.get("note") or "")[:500], "receipt_path": exp.get("receipt_path") or None, "split_mode": mode,
                   "shares": [{"member_id": s["member_id"], "weight": float(s.get("weight") or 1),
                               "amount_cents": int(s["amount_cents"]) if mode == "amounts" else None} for s in shares]}
        self.admin._rpc(token, "tc_save_expense", {"grp": grp, "exp": payload}, "La dépense n'a pas été enregistrée. Réessaie.")
        return self.state(token, grp)

    def settle_up(self, token: str, grp: str, payer: str, to: str, amount: int) -> dict:
        """« J'ai remboursé » : un remboursement de `payer` à `to`, d'un toucher depuis la liste des remboursements."""
        return self.save_expense(token, grp, {"kind": "transfer", "title": "Remboursement", "amount_cents": amount, "paid_by": payer,
                                              "shares": [{"member_id": to}], "split_mode": "equal", "category": "other"})

    def delete_expense(self, token: str, grp: str, expense: str) -> dict:
        self.admin._rpc(token, "tc_delete_expense", {"expense": expense})
        return self.state(token, grp)

    def upload_receipt(self, token: str, grp: str, data: bytes) -> dict:
        if not data or len(data) > RECEIPT_MAX:
            raise AccountError("Photo trop volumineuse (8 Mo au plus).")
        if not data.startswith(IMAGE_MAGIC):
            raise AccountError("Choisis une photo (JPEG ou PNG).")
        png = data.startswith(b"\x89PNG")
        path = f"{grp}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}.{'png' if png else 'jpg'}"
        r = self.admin._call("POST", f"/storage/v1/object/tc-receipts/{path}", token, content=data,
                             headers={"Content-Type": "image/png" if png else "image/jpeg"})
        if r.status_code not in (200, 201):
            raise AccountError("La photo du ticket n'a pas pu être envoyée. Réessaie.")
        return {"path": path}

    # ── Profil de paiement ──
    def payment(self, token: str) -> dict:
        p = self.admin._rpc(token, "tc_my_payment", {}, "Ton profil de paiement n'a pas pu être lu.") or {}
        return {"iban": tc.format_iban(p["iban"]) if p.get("iban") else "", "holder": p.get("holder") or "",
                "links": p.get("links") or {}, "note": p.get("note") or ""}

    def set_payment(self, token: str, iban: str, holder: str, links: dict, note: str) -> dict:
        try:
            clean = tc.clean_iban(iban) if (iban or "").strip() else ""
            links = tc.clean_links(links)
        except ValueError as e:
            raise AccountError(str(e)) from None
        self.admin._rpc(token, "tc_set_payment", {"pay_iban": clean, "pay_holder": (holder or "").strip()[:80], "pay_links": links,
                                                 "pay_note": (note or "").strip()[:200]}, "Ton profil de paiement n'a pas été enregistré.")
        return self.payment(token)
