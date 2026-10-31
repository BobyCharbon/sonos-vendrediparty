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
PRICE_IN, PRICE_OUT = 2.0, 10.0  # dollars par million de jetons (entrée, sortie) pour MODEL
MAX_PHOTO = 6 * 1024 * 1024
MAX_TOKENS = 4000
BURST = (6, 10 * 60)  # au plus 6 lectures par personne en 10 minutes
MAX_LOG = 5000
IMAGE_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}
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


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1_000_000


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


class Assistant:
    def __init__(self, accounts, usage: UsageLog, client_factory, monthly_budget_usd: float, currencies: tuple[str, ...]):
        self.accounts = accounts
        self.usage = usage
        self.client_factory = client_factory  # None tant que la clé API n'est pas configurée
        self.budget = monthly_budget_usd
        self.currencies = currencies
        self._client = None

    def _client_or_error(self):
        if self.client_factory is None:
            raise AccountError("L'assistant IA n'est pas encore configuré sur ce serveur.")
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def status(self, token: str) -> dict:
        uid = self.accounts._uid(token)
        return {"allowed": "ai.use" in self.accounts._perms(token), "configured": self.client_factory is not None,
                "spent_usd": round(self.usage.spent_this_month(uid, time.time()), 4), "budget_usd": self.budget}

    def _check(self, token: str) -> str:
        uid = self.accounts._uid(token)
        if "ai.use" not in self.accounts._perms(token):
            raise AccountError("L'assistant IA n'est pas activé pour ton compte. Demande à l'admin.")
        now = time.time()
        if self.usage.spent_this_month(uid, now) >= self.budget:
            raise AccountError("Tu as atteint ta limite d'assistant IA pour ce mois-ci. Elle repart le 1er.")
        if self.usage.recent(uid, now, BURST[1]) >= BURST[0]:
            raise AccountError("Doucement : réessaie dans quelques minutes.")
        return uid

    def _log(self, uid: str, token: str, feature: str, usage) -> float:
        tokens_in = getattr(usage, "input_tokens", 0) or 0
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        cost = cost_usd(tokens_in, tokens_out)
        try:
            name = self.accounts.link(token).get("name") or ""
        except AccountError:
            name = ""
        self.usage.add({"at": time.time(), "uid": uid, "name": name, "feature": feature, "model": MODEL,
                        "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost})
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
            logging.getLogger(__name__).warning("Lecture du ticket impossible : %s: %s", type(e).__name__, e)
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
        return {**self.usage.report(time.time()), "budget_usd": self.budget, "model": MODEL,
                "configured": self.client_factory is not None}
