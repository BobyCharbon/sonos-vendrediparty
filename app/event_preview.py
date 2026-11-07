"""Aperçu des liens d'un événement PUBLIC (WhatsApp, iMessage, Instagram…) : /events/event/<id>, /events/share/<id> et
le lien de « Partager le lien » (/?tab=events&event=<id>) montrent le titre, la date, le nom du lieu et l'affiche
(https) ou, sans affiche, l'image de Party.

Lecture SANS session de public.public_event, qui ne rend que les événements publics avec lien public (visibility
'all', public_link, publié ou annulé). Tout autre événement (sur invitation, groupe, brouillon) : aucun aperçu propre à
l'événement, donc aucune fuite. Jamais l'adresse exacte, ni la description. Base injoignable : pas d'aperçu, la page
s'ouvre quand même. Ce serveur ne garde rien.
"""
import html
import re

from .accounts import SUPABASE_ANON_KEY, AccountError, Accounts
from .event_invites import NAME_MAX, TITLE_MAX, image_tags, short_date

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
EVENT_PAGE = re.compile(rf"^(?:event|share)/({UUID})/?$")
EVENT_ID = re.compile(rf"^{UUID}$")
SHARE_PATH = "/events/share/"
DESCRIPTION_TAIL = "Réponds en quelques secondes sur Party."
# La page attend l'aperçu : base lente → page sans aperçu après ce délai, jamais une page qui traîne.
LOOKUP_TIMEOUT = 2.0


def event_id_of_page(resource: str) -> str | None:
    """« event/<id> » ou « share/<id> » du module Événements → identifiant (minuscules), sinon None."""
    found = EVENT_PAGE.match(resource)
    return found.group(1).lower() if found else None


def event_id_of_query(tab: str, event: str) -> str | None:
    """Lien de « Partager le lien » : /?tab=events&event=<id>."""
    return event.lower() if tab == "events" and EVENT_ID.match(event or "") else None


def public_card(accounts: Accounts, event_id: str) -> dict | None:
    """L'événement s'il est public, lu sans session ; None sinon ou si la base ne répond pas."""
    try:
        r = accounts._get("POST", "/rest/v1/rpc/public_event", SUPABASE_ANON_KEY, json={"e": event_id},
                          timeout=LOOKUP_TIMEOUT)
    except AccountError:
        return None
    if r.status_code != 200:
        return None
    try:
        row = r.json()
    except ValueError:
        return None
    return row if isinstance(row, dict) and str(row.get("id", "")).lower() == event_id else None


def event_meta(card: dict, public_url: str) -> str:
    """Balises Open Graph et Twitter de l'événement public, texte échappé ; jamais l'adresse exacte."""
    base = public_url.rstrip("/")
    name = str(card.get("title") or "").strip()[:TITLE_MAX] or "Événement"
    title = f"Annulé : {name}" if card.get("status") == "cancelled" else name
    parts = [short_date(card.get("starts_at"), bool(card.get("all_day"))), str(card.get("location_name") or "").strip()[:NAME_MAX]]
    when_where = " · ".join(p for p in parts if p)
    description = (f"{when_where}. " if when_where else "") + DESCRIPTION_TAIL
    tags = {"og:type": "website", "og:site_name": "Party", "og:title": title, "og:description": description,
            "og:url": f"{base}{SHARE_PATH}{card['id']}", "twitter:title": title, "twitter:description": description,
            **image_tags(card, base)}
    meta = "".join(f'<meta {"name" if k.startswith("twitter:") else "property"}="{k}" content="{html.escape(str(v), quote=True)}">'
                   for k, v in tags.items())
    return f'{meta}<meta name="description" content="{html.escape(description, quote=True)}">'


def with_preview(page: str, accounts: Accounts, event_id: str | None, public_url: str) -> str:
    """La page avec l'aperçu de l'événement public dans <head> ; inchangée sinon."""
    card = public_card(accounts, event_id) if event_id else None
    if not card:
        return page
    return page.replace("</head>", event_meta(card, public_url) + "</head>", 1)
