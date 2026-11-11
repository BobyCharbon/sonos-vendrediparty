"""Agenda abonné d'un sondage de dates (retour de l'admin du 11.11.2026) : lu avec le jeton secret de la personne,
sans session (l'agenda de l'iPhone ou Google Agenda le relit tout seul). La base décide de ce qui est montré
(fonction calendar_feed) ; ici on ne fait que la lire."""
import re

from .accounts import SUPABASE_ANON_KEY, AccountError, Accounts

TOKEN = re.compile(r"[0-9a-f]{36}")
LOOKUP_TIMEOUT = 6.0


def read(accounts: Accounts, token: str) -> tuple[dict | None, bool]:
    """(contenu, joignable). Base injoignable : joignable = False (on ne vide pas l'agenda pour une panne)."""
    if not TOKEN.fullmatch(token or ""):
        return None, True
    try:
        r = accounts._get("POST", "/rest/v1/rpc/calendar_feed", SUPABASE_ANON_KEY, json={"t": token},
                          timeout=LOOKUP_TIMEOUT)
    except AccountError:
        return None, False
    if r.status_code != 200:
        return None, False
    try:
        row = r.json()
    except ValueError:
        return None, False
    return (row if isinstance(row, dict) else None), True
