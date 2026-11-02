"""Tricount : le calcul, sans base (testé à part) — parts au centime près, soldes, remboursements les moins nombreux,
catégorie devinée d'après le titre, IBAN vérifié, liens de paiement (Revolut, PayPal, Twint…) nettoyés.

Conventions : montants en centimes (entiers) ; solde > 0 = on lui doit de l'argent, < 0 = il doit.
Une dépense « transfer » est un remboursement : celui qui paie donne à la personne de la part (pas une dépense du groupe).
"""
import re
from decimal import ROUND_HALF_UP, Decimal

CATEGORIES = {  # id → (libellé, emoji) ; ordre d'affichage
    "food": ("Courses", "🛒"), "restaurant": ("Restaurant", "🍽️"), "drinks": ("Boissons", "🍻"), "transport": ("Transport", "🚗"),
    "lodging": ("Logement", "🏠"), "leisure": ("Loisirs", "🎉"), "shopping": ("Achats", "🛍️"), "health": ("Santé", "💊"),
    "bills": ("Factures", "🧾"), "other": ("Autre", "💸"),
}
KEYWORDS = {
    "food": ("migros", "coop", "denner", "aldi", "lidl", "manor food", "courses", "épicerie", "epicerie", "supermarché", "marché",
             "boulangerie", "carrefour", "leclerc", "volg", "spar"),
    "restaurant": ("resto", "restaurant", "pizza", "burger", "kebab", "sushi", "mcdo", "mcdonald", "brunch", "déjeuner", "dîner",
                   "diner", "repas", "café ", "takeaway", "uber eats", "smood"),
    "drinks": ("bière", "biere", "bar", "apéro", "apero", "vin", "alcool", "cocktail", "shots", "pub", "boissons"),
    "transport": ("essence", "carburant", "shell", "esso", "bp ", "train", "cff", "sbb", "bus", "taxi", "uber", "parking", "péage",
                  "peage", "avion", "vol ", "easyjet", "swiss", "location voiture", "mobility", "vignette", "tram"),
    "lodging": ("airbnb", "hôtel", "hotel", "logement", "booking", "chalet", "camping", "auberge", "loyer"),
    "leisure": ("cinéma", "cinema", "concert", "musée", "musee", "billet", "ski", "forfait", "bowling", "karting", "escape",
                "festival", "boîte", "boite", "club", "piscine", "spa"),
    "shopping": ("cadeau", "vêtement", "vetement", "zara", "ikea", "amazon", "galaxus", "digitec", "décoration", "deco"),
    "health": ("pharmacie", "médecin", "medecin", "amavita", "sun store"),
    "bills": ("facture", "internet", "électricité", "electricite", "abonnement", "netflix", "spotify", "swisscom", "salt", "sunrise"),
}
LINK_HOSTS = {"revolut": "https://revolut.me/", "paypal": "https://paypal.me/", "lydia": "https://lydia-app.com/"}


def _cents(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _spread(total: int, weights: list[tuple[str, Decimal]]) -> dict[str, int]:
    """Répartit `total` centimes selon les poids ; les centimes restants vont aux plus grands restes (rien ne se perd)."""
    weights = [(m, w) for m, w in weights if w > 0]
    if not weights:
        return {}
    whole = sum(w for _, w in weights)
    exact = [(m, Decimal(total) * w / whole) for m, w in weights]
    out = {m: int(x) for m, x in exact}
    left = total - sum(out.values())
    for m, _ in sorted(exact, key=lambda mx: -(mx[1] - int(mx[1])))[:left]:
        out[m] += 1
    return out


def group_amount(e: dict) -> int:
    """Montant de la dépense dans la monnaie du groupe."""
    return _cents(Decimal(e["amount_cents"]) * Decimal(str(e.get("rate") or 1)))


def split(e: dict) -> dict[str, int]:
    """Part de chacun (centimes, monnaie du groupe) : égale, par parts, ou montants exacts."""
    total, shares = group_amount(e), e.get("shares") or []
    if e.get("split_mode") == "amounts":
        raw = sum(int(s.get("amount_cents") or 0) for s in shares) or 1
        return _spread(total, [(s["member_id"], Decimal(int(s.get("amount_cents") or 0)) / raw) for s in shares])
    if e.get("split_mode") == "shares":
        return _spread(total, [(s["member_id"], Decimal(str(s.get("weight") or 0))) for s in shares])
    return _spread(total, [(s["member_id"], Decimal(1)) for s in shares])


def balances(member_ids: list[str], expenses: list[dict]) -> dict[str, int]:
    """Solde de chacun : ce qu'il a payé moins ce qu'il doit (remboursements compris)."""
    bal = {m: 0 for m in member_ids}
    for e in expenses:
        bal[e["paid_by"]] = bal.get(e["paid_by"], 0) + group_amount(e)
        for m, part in split(e).items():
            bal[m] = bal.get(m, 0) - part
    return bal


def settle(bal: dict[str, int]) -> list[dict]:
    """Qui doit rembourser qui, en un minimum de virements : le plus gros débiteur paie le plus gros créancier, et ainsi de suite."""
    debt = sorted(((-v, m) for m, v in bal.items() if v < 0), reverse=True)
    cred = sorted(((v, m) for m, v in bal.items() if v > 0), reverse=True)
    debt, cred = [[v, m] for v, m in debt], [[v, m] for v, m in cred]
    plan, i, j = [], 0, 0
    while i < len(debt) and j < len(cred):
        amount = min(debt[i][0], cred[j][0])
        plan.append({"from": debt[i][1], "to": cred[j][1], "amount_cents": amount})
        debt[i][0] -= amount
        cred[j][0] -= amount
        i += debt[i][0] == 0
        j += cred[j][0] == 0
    return plan


def guess_category(title: str) -> str:
    t = f" {(title or '').lower()} "
    for cat, words in KEYWORDS.items():
        if any(w in t for w in words):
            return cat
    return "other"


def clean_iban(iban: str) -> str:
    """IBAN sans espaces, en majuscules, clé de contrôle vérifiée (mod 97) ; ValueError sinon."""
    s = re.sub(r"\s+", "", iban or "").upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", s):
        raise ValueError("IBAN incomplet ou mal écrit")
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    if int(digits) % 97 != 1:
        raise ValueError("IBAN invalide : vérifie les chiffres")
    return s


def format_iban(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def clean_links(links: dict) -> dict:
    """Revolut, PayPal, Lydia : un nom suffit (lien complété) ; Twint : un numéro ; jamais autre chose qu'un lien https."""
    out = {}
    for kind, value in (links or {}).items():
        v = (value or "").strip()
        if not v:
            continue
        if kind == "twint":
            digits = re.sub(r"[^\d+]", "", v)
            if not re.fullmatch(r"\+?\d{9,15}", digits):
                raise ValueError("Twint : un numéro de téléphone")
            out[kind] = digits
        elif kind in LINK_HOSTS:
            if re.fullmatch(r"[\w.\-]{2,40}", v.lstrip("@")):
                out[kind] = LINK_HOSTS[kind] + v.lstrip("@")
            elif re.fullmatch(r"https://[\w.\-]+(/[\w.\-~%/?=&]*)?", v):
                out[kind] = v
            else:
                raise ValueError(f"Lien {kind} invalide")
        elif kind == "other":
            if not re.fullmatch(r"https://[\w.\-]+(/[\w.\-~%/?=&#]*)?", v):
                raise ValueError("Un lien commençant par https://")
            out[kind] = v
    return out


def summarize(group: dict) -> dict:
    """Tout ce que l'écran affiche : total, mon solde, ma part, par catégorie, remboursements à faire."""
    members = [m["id"] for m in group.get("members", [])]
    exps = group.get("expenses", [])
    bal = balances(members, exps)
    me = group.get("me")
    spending = [e for e in exps if e.get("kind", "expense") == "expense"]
    cats: dict[str, int] = {}
    for e in spending:
        cats[e.get("category") or "other"] = cats.get(e.get("category") or "other", 0) + group_amount(e)
    return {
        "total_cents": sum(group_amount(e) for e in spending),
        "my_balance_cents": bal.get(me, 0) if me else 0,
        "my_spent_cents": sum(split(e).get(me, 0) for e in spending) if me else 0,
        "balances": bal,
        "by_category": [{"category": c, "amount_cents": a} for c, a in sorted(cats.items(), key=lambda x: -x[1])],
        "settle": settle(bal),
    }
