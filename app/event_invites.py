"""Invitations v2 (bêta, drapeau invites_v2_enabled) : aperçu riche du lien d'invitation à un événement
(/events/invite/<jeton>) pour WhatsApp, iMessage, Instagram… : « Ludo t'invite : Raclette & vinyles », la date et
l'affiche de l'événement.

Lecture SANS session de public.invite_preview (migration 20261105200000), qui ne renvoie que le nécessaire : titre,
date, nom du lieu (jamais l'adresse exacte), prénom de l'organisateur, affiche. opened=false : l'aperçu du robot de
WhatsApp ne compte pas comme une ouverture. Base injoignable ou lien inconnu : aperçu générique, la page s'ouvre quand
même. Ce serveur ne garde rien.
"""
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .accounts import SUPABASE_ANON_KEY, AccountError, Accounts

INVITE_PAGE = re.compile(r"^invite/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$")
SHARE_IMAGE = "/static/icon-512.png"
ZURICH = ZoneInfo("Europe/Zurich")
DAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
TITLE_MAX = 80
NAME_MAX = 40


def short_date(iso: str | None, all_day: bool = False) -> str:
    """« ven. 14 nov. · 21:00 » (heure de Suisse) ; vide si la date manque ou est illisible."""
    if not iso:
        return ""
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZURICH)
    except ValueError:
        return ""
    day = f"{DAYS[when.weekday()]} {when.day} {MONTHS[when.month - 1]}"
    return day if all_day else f"{day} · {when:%H:%M}"


def preview(accounts: Accounts, token: str) -> dict | None:
    """Carte du lien, lue sans session (aucune ouverture notée)."""
    r = accounts._get("POST", "/rest/v1/rpc/invite_preview", SUPABASE_ANON_KEY, json={"token": token, "opened": False})
    if r.status_code != 200:
        raise AccountError("L'invitation n'a pas pu être lue.")
    row = r.json()
    return row if isinstance(row, dict) else None


def invite_meta(card: dict | None, page_url: str, public_url: str) -> str:
    """Balises Open Graph et Twitter de la carte d'invitation, texte échappé."""
    card = card or {}
    who = str(card.get("inviter") or "").strip()[:NAME_MAX]
    what = str(card.get("title") or "").strip()[:TITLE_MAX]
    if what:
        title = f"{who} t'invite : {what}" if who else f"Invitation : {what}"
    else:
        title = "Tu es invité sur Party"
    parts = [short_date(card.get("starts_at"), bool(card.get("all_day"))), str(card.get("location_name") or "").strip()[:NAME_MAX]]
    when_where = " · ".join(p for p in parts if p)
    description = (f"{when_where}. " if when_where else "") + "Réponds en quelques secondes, sans installer d'app."
    cover = str(card.get("cover_url") or "")
    large = cover.startswith("https://")
    image = cover if large else public_url.rstrip("/") + SHARE_IMAGE
    tags = {"og:type": "website", "og:site_name": "Party", "og:title": title, "og:description": description,
            "og:url": page_url, "og:image": image,
            "twitter:card": "summary_large_image" if large else "summary", "twitter:title": title,
            "twitter:description": description, "twitter:image": image}
    if not large:
        tags.update({"og:image:width": "512", "og:image:height": "512"})
    meta = "".join(f'<meta {"name" if k.startswith("twitter:") else "property"}="{k}" content="{html.escape(v, quote=True)}">'
                   for k, v in tags.items())
    return f'{meta}<meta name="description" content="{html.escape(description, quote=True)}">'


def page_meta(accounts: Accounts, token: str, public_url: str) -> str:
    try:
        card = preview(accounts, token)
    except AccountError:
        card = None
    base = public_url.rstrip("/")
    return invite_meta(card, f"{base}/events/invite/{token}", base)
