"""Assistant IA de Party (Claude, par l'API d'Anthropic) : d'abord la lecture d'un ticket pour le pot commun.

Réservé aux comptes qui ont le droit « Utiliser l'assistant IA » (ai.use, réglable dans Rôles et droits). Chaque
appel est noté (qui, quoi, jetons, coût) dans un journal que l'admin consulte ; un plafond mensuel par personne et
un débit maximal évitent toute surprise sur la facture. La clé API ne vit que dans l'environnement du serveur."""
import base64
import json
import logging
import threading
import time
from pathlib import Path

from . import tricount_logic as tc
from .accounts import AccountError

MODEL = "claude-sonnet-5-5"
# Dollars par million de jetons (entrée, sortie). La réflexion du modèle compte comme sortie.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
MAX_PHOTO = 6 * 1024 * 1024
MAX_TOKENS = 4000
BURST = (15, 10 * 60)  # au plus 15 appels par personne en 10 minutes (une conversation compte plusieurs appels)
MAX_LOG = 5000
IMAGE_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}
# Accord exprès avant le 1er envoi à Anthropic (Apple 5.1.2(i)) : UN SEUL accord « IA » par compte, le même que l'IA
# des avis (app/ai_feedback.ConsentBox, clé « acct:<uid> », /api/feedback/ai/consent) : l'app iPhone ne montre qu'une
# feuille, qui couvre l'avis, l'assistant des événements (texte, captures, photos, liens) et le scan des tickets.
CONSENT_ACCEPTED = "accepted"
CONSENT_REQUIRED = "Accord requis : donne d'abord ton accord pour que Party envoie ta demande à Anthropic (Claude)."
GLOBAL_OVER_BUDGET = "L'assistant IA a atteint sa limite pour ce mois-ci, pour toute l'app. Il repart le 1er."
UNREADABLE = "Ce ticket n'a pas pu être lu. Reprends la photo bien à plat, ou saisis la dépense à la main."

RECEIPT_SYSTEM = """Tu lis des photos de tickets de caisse, de factures et d'additions pour une app suisse de partage
de dépenses entre amis. Tu réponds uniquement avec les champs demandés, en français.
- merchant : le nom du commerce tel qu'on le dit (« Migros », « Pizzeria Da Mario »), sans forme juridique.
- title : un titre court pour la dépense (« Courses Migros », « Resto Da Mario »).
- date : la date d'achat au format AAAA-MM-JJ, ou une chaîne vide si elle n'est pas lisible.
- currency : le code à trois lettres (CHF par défaut en Suisse, EUR, USD, GBP…).
- total : le montant total réellement payé (après rabais, avec TVA et pourboire inscrits), en unités (ex. 84.5).
- category : la catégorie la plus juste parmi la liste proposée.
- items : chaque article ou ligne du ticket, avec sa quantité et son prix total pour la ligne ; pas les lignes de TVA,
  de sous-total, de rendu de monnaie ni de moyen de paiement. Les rabais sont des lignes à montant négatif.
- summary : une phrase courte qui résume l'achat (« Raclette, vin et pain pour 84.50 CHF »).
- readable : false si l'image n'est pas un ticket ou si le total est illisible ; tous les autres champs peuvent alors
  être vides ou à zéro."""

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean"},
        "merchant": {"type": "string"},
        "title": {"type": "string"},
        "date": {"type": "string"},
        "currency": {"type": "string"},
        "total": {"type": "number"},
        "category": {"type": "string", "enum": list(tc.CATEGORIES)},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "quantity": {"type": "number"}, "amount": {"type": "number"}},
            "required": ["label", "quantity", "amount"], "additionalProperties": False}},
        "summary": {"type": "string"},
    },
    "required": ["readable", "merchant", "title", "date", "currency", "total", "category", "items", "summary"],
    "additionalProperties": False,
}


def cost_usd(tokens_in: int, tokens_out: int, model: str = MODEL) -> float:
    price_in, price_out = PRICES[model]
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def image_type(data: bytes) -> str | None:
    return next((t for magic, t in IMAGE_TYPES.items() if data.startswith(magic)), None)


def cents(value) -> int:
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return 0


def clean_receipt(raw: dict, currencies: tuple[str, ...]) -> dict:
    """Réponse de Claude → ce que l'éditeur de dépense remplit : montants en centimes, champs bornés et vérifiés."""
    total = cents(raw.get("total"))
    if not raw.get("readable") or total <= 0 or total > 100_000_000:
        raise AccountError(UNREADABLE)
    currency = str(raw.get("currency") or "CHF").upper()
    date = str(raw.get("date") or "")
    items = [{"label": str(i.get("label") or "").strip()[:80], "quantity": float(i.get("quantity") or 1),
              "amount_cents": cents(i.get("amount"))}
             for i in (raw.get("items") or [])[:60] if str(i.get("label") or "").strip()]
    merchant = str(raw.get("merchant") or "").strip()[:60]
    return {"merchant": merchant,
            "title": (str(raw.get("title") or "").strip() or merchant or "Ticket")[:80],
            "date": date if len(date) == 10 and date[4] == "-" and date[7] == "-" else "",
            "currency": currency if currency in currencies else "CHF",
            "amount_cents": total,
            "category": raw.get("category") if raw.get("category") in tc.CATEGORIES else "other",
            "items": items,
            "summary": str(raw.get("summary") or "").strip()[:200]}


class UsageLog:
    """Journal des appels à l'IA (fichier JSON), pour le plafond mensuel et la page de l'admin."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        try:
            self.items: list[dict] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = []

    def add(self, entry: dict):
        with self.lock:
            self.items = (self.items + [entry])[-MAX_LOG:]
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    @staticmethod
    def month_start(now: float) -> float:
        t = time.localtime(now)
        return time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1))

    def spent_this_month(self, uid: str, now: float) -> float:
        start = self.month_start(now)
        return sum(i["cost_usd"] for i in self.items if i["uid"] == uid and i["at"] >= start)

    def spent_total_this_month(self, now: float) -> float:
        """Dépense de toute l'app ce mois-ci (assistant, avis, toutes personnes) : plafond global."""
        start = self.month_start(now)
        return sum(i["cost_usd"] for i in self.items if i["at"] >= start)

    def forget(self, subjects: set[str]) -> int:
        """Compte supprimé : ses appels partent du journal (le texte dicté compris). Renvoie le nombre retiré."""
        with self.lock:
            kept = [i for i in self.items if i.get("uid") not in subjects]
            removed = len(self.items) - len(kept)
            if removed:
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self.path)
                self.items = kept
        return removed

    def recent(self, uid: str, now: float, seconds: float) -> int:
        return sum(1 for i in self.items if i["uid"] == uid and now - i["at"] < seconds)

    def report(self, now: float) -> dict:
        """Pour l'admin : total du mois, par personne, et les derniers appels."""
        start = self.month_start(now)
        people: dict[str, dict] = {}
        for i in self.items:
            if i["at"] < start:
                continue
            p = people.setdefault(i["uid"], {"uid": i["uid"], "name": "?", "calls": 0, "cost_usd": 0.0})
            p["calls"] += 1
            p["cost_usd"] += i["cost_usd"]
            p["name"] = i.get("name") or p["name"]
        month = sorted(people.values(), key=lambda p: -p["cost_usd"])
        return {"month_cost_usd": sum(p["cost_usd"] for p in month), "people": month,
                "recent": list(reversed(self.items[-50:]))}


class ConsentRequired(AccountError):
    """Pas encore d'accord pour envoyer à Anthropic : 403, l'app montre la feuille d'accord."""


def assistant_consent_key(uid: str) -> str:
    return f"acct:{uid}"  # même clé que l'IA des avis pour un compte (main.feedback_ai_subject)


class Assistant:
    def __init__(self, accounts, usage: UsageLog, client_factory, monthly_budget_usd: float, currencies: tuple[str, ...],
                 consents=None, global_budget_usd: float = float("inf")):
        self.accounts = accounts
        self.usage = usage
        self.client_factory = client_factory  # None tant que la clé API n'est pas configurée
        self.budget = monthly_budget_usd
        self.global_budget = global_budget_usd  # toute l'app, toutes personnes et tous usages (AI_GLOBAL_MONTHLY_BUDGET_USD)
        self.currencies = currencies
        self.consents = consents  # app/ai_feedback.ConsentBox ; None (tests anciens) : aucun accord demandé
        self._client = None

    def over_global_budget(self, now: float) -> bool:
        return self.usage.spent_total_this_month(now) >= self.global_budget

    def consent(self, uid: str) -> str:
        """« accepted », « declined » ou « » (jamais demandé, ou texte d'accord changé)."""
        return self.consents.state(assistant_consent_key(uid)) if self.consents is not None else CONSENT_ACCEPTED

    def set_consent(self, token: str, accept: bool) -> dict:
        uid = self.accounts._uid(token)
        if self.consents is None:
            raise AccountError("L'assistant IA n'est pas encore configuré sur ce serveur.")
        self.consents.set(assistant_consent_key(uid), accept)
        return self.status(token)

    def _client_or_error(self):
        if self.client_factory is None:
            raise AccountError("L'assistant IA n'est pas encore configuré sur ce serveur.")
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def status(self, token: str) -> dict:
        uid = self.accounts._uid(token)
        now = time.time()
        return {"allowed": "ai.use" in self.accounts._perms(token), "configured": self.client_factory is not None,
                "consent": self.consent(uid), "global_full": self.over_global_budget(now),
                "spent_usd": round(self.usage.spent_this_month(uid, now), 4), "budget_usd": self.budget}

    def allowed(self, token: str) -> str:
        """Le compte a le droit « Utiliser l'assistant IA » et a donné son accord ; renvoie son identifiant."""
        uid = self.accounts._uid(token)
        if "ai.use" not in self.accounts._perms(token):
            raise AccountError("L'assistant IA n'est pas activé pour ton compte. Demande à l'admin.")
        if self.consent(uid) != CONSENT_ACCEPTED:
            raise ConsentRequired(CONSENT_REQUIRED)
        return uid

    @staticmethod
    def warn(what: str, error: Exception):
        logging.getLogger(__name__).warning("%s : %s: %s", what, type(error).__name__, error)

    def _check(self, token: str) -> str:
        """Avant un appel à l'IA : droit, plafond du mois et débit."""
        uid = self.allowed(token)
        now = time.time()
        if self.over_global_budget(now):
            raise AccountError(GLOBAL_OVER_BUDGET)
        if self.usage.spent_this_month(uid, now) >= self.budget:
            raise AccountError("Tu as atteint ta limite d'assistant IA pour ce mois-ci. Elle repart le 1er.")
        if self.usage.recent(uid, now, BURST[1]) >= BURST[0]:
            raise AccountError("Doucement : réessaie dans quelques minutes.")
        return uid

    def _log(self, uid: str, token: str, feature: str, usage, model: str = MODEL, said: str = "") -> float:
        """Appel noté pour le plafond et l'admin ; `said` : ce que la personne a demandé (pour comprendre les ratés)."""
        tokens_in = getattr(usage, "input_tokens", 0) or 0
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        cost = cost_usd(tokens_in, tokens_out, model)
        try:
            name = self.accounts.link(token).get("name") or ""
        except AccountError:
            name = ""
        entry = {"at": time.time(), "uid": uid, "name": name, "feature": feature, "model": model,
                 "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost}
        self.usage.add({**entry, "said": said[:1500]} if said else entry)
        return cost

    def read_receipt(self, token: str, photo: bytes) -> dict:
        """Photo d'un ticket → commerce, titre, date, total, catégorie, articles et résumé, pour remplir la dépense."""
        uid = self._check(token)
        media = image_type(photo)
        if not media or len(photo) > MAX_PHOTO:
            raise AccountError("Photo illisible ou trop lourde.")
        client = self._client_or_error()
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=RECEIPT_SYSTEM,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": RECEIPT_SCHEMA}},
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media,
                                                 "data": base64.standard_b64encode(photo).decode("ascii")}},
                    {"type": "text", "text": "Lis ce ticket."}]}])
        except Exception as e:  # réseau ou API : message clair pour la personne, détail dans le journal du serveur
            self.warn("Lecture du ticket impossible", e)
            raise AccountError("La lecture du ticket n'a pas marché. Réessaie dans un instant, ou saisis à la main.") from None
        cost = self._log(uid, token, "receipt", getattr(response, "usage", None))
        if response.stop_reason in ("refusal", "max_tokens"):
            raise AccountError(UNREADABLE)
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        try:
            raw = json.loads(text)
        except ValueError:
            raise AccountError(UNREADABLE) from None
        return {**clean_receipt(raw, self.currencies), "cost_usd": round(cost, 4)}

    def report(self, token: str) -> dict:
        if not self.accounts.is_party_admin(token):
            raise AccountError("Réservé aux admins.")
        return {**self.usage.report(time.time()), "budget_usd": self.budget, "global_budget_usd": self.global_budget, "model": MODEL,
                "configured": self.client_factory is not None}
