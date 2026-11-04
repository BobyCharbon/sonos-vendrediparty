"""Invitations dans Party (avis 84fab3987f68) : lien personnel de chaque compte, aperçu avant connexion, parrainage,
et « Invité par » sur la fiche d'un membre (droit members.view_referrals, admins seulement).

Relais entre l'app iPhone et la base (fonctions my_app_invite, app_invite_preview, claim_app_invite, member_invited_by
de la migration 20261104090000) avec la session de la personne ; la base vérifie tout (droits, compte de moins de 24 h,
une seule fois, jamais soi-même, 5 nouveaux liens par jour). Ce serveur ne garde rien.
"""
import html
import re

from .accounts import SUPABASE_ANON_KEY, AccountError, Accounts
from .contact_names import signed_photos

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
INVITE_PATH = "/events/join/"


def invite_url(public_url: str, token: str) -> str:
    """Adresse partagée : la page « X t'invite sur Party » du module web (lien universel : l'app l'ouvre si installée)."""
    return public_url.rstrip("/") + INVITE_PATH + token


VIA = {"app", "group", "event"}
JOIN_PAGE = re.compile(r"^join/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$")
SHARE_IMAGE = "/static/icon-512.png"


def join_meta(inviter: str | None, page_url: str, public_url: str) -> str:
    """Aperçu riche du lien (WhatsApp, iMessage, Instagram…) : balises Open Graph et Twitter, texte échappé."""
    who = (inviter or "").strip()[:60]
    title = f"{who} t'invite sur Party" if who else "Rejoins tes amis sur Party"
    description = "Événements, discussions de groupe, jeux et musique de la soirée. Inscription avec ton numéro."
    image = public_url.rstrip("/") + SHARE_IMAGE
    tags = {"og:type": "website", "og:site_name": "Party", "og:title": title, "og:description": description,
            "og:url": page_url, "og:image": image, "og:image:width": "512", "og:image:height": "512",
            "twitter:card": "summary", "twitter:title": title, "twitter:description": description, "twitter:image": image}
    meta = "".join(f'<meta {"name" if k.startswith("twitter:") else "property"}="{k}" content="{html.escape(v, quote=True)}">'
                   for k, v in tags.items())
    return f"{meta}<meta name=\"description\" content=\"{html.escape(description, quote=True)}\">"


class AppInvites:
    def __init__(self, accounts: Accounts, public_url):
        self.accounts = accounts
        self.public_url = public_url  # fonction : l'adresse publique peut changer (site de test / principal)

    def mine(self, token: str, renew: bool = False) -> dict:
        row = self.accounts._rpc_json(token, "my_app_invite", {"renew": renew}, "Ton lien d'invitation n'a pas pu être créé.")
        if not isinstance(row, dict) or not UUID.match(str(row.get("token", ""))):
            raise AccountError("Ton lien d'invitation n'a pas pu être créé.")
        return {"token": row["token"], "url": invite_url(self.public_url(), row["token"]),
                "joined": int(row.get("joined") or 0)}

    def preview(self, invite: str) -> dict | None:
        """Avant connexion : surnom de la personne qui invite (aucune session)."""
        if not UUID.match(invite):
            return None
        r = self.accounts._get("POST", "/rest/v1/rpc/app_invite_preview", SUPABASE_ANON_KEY, json={"token": invite})
        if r.status_code != 200:
            raise AccountError("L'invitation n'a pas pu être lue. Réessaie dans un instant.")
        row = r.json()
        if not isinstance(row, dict):
            return None
        # Sans session, la photo (bucket privé) ne se signe pas : le surnom seul (l'app montre son initiale).
        return {"inviter": str(row.get("inviter") or "")}

    def claim(self, token: str, invite: str) -> dict:
        if not UUID.match(invite):
            raise AccountError("Ce lien d'invitation n'est plus valable.")
        row = self.accounts._rpc_json(token, "claim_app_invite", {"token": invite}, "L'invitation n'a pas pu être enregistrée.")
        # Le nom de l'inviteur n'est jamais renvoyé à l'invité (« qui a invité qui » : admins seulement).
        return {"new": bool(row.get("new")) if isinstance(row, dict) else False}

    def invited_by(self, token: str, member: str) -> list[dict] | None:
        """Fiche d'un membre › « Invité par » : None sans le droit members.view_referrals (vérifié par la base)."""
        if not UUID.match(member):
            raise AccountError("Profil inconnu")
        rows = self.accounts._rpc_json(token, "member_invited_by", {"target": member}, "« Invité par » n'a pas pu être lu.")
        if rows is None:
            return None
        return [{"inviter": str(r.get("inviter") or ""), "invited_by": r.get("invited_by"), "via": r["via"],
                 "target": r.get("target"), "target_name": r.get("target_name"), "at": r.get("at")}
                for r in rows if isinstance(r, dict) and r.get("via") in VIA]
