"""Agenda de Party (17.11.2026) côté serveur. La base décide de tout (supabase/migrations/20261117140000_agenda.sql) ;
ici on lit et on affiche, sans rien garder.

- Page publique d'un lien de dispo : GET /d/<jeton> (sobre, vouvoiement, vue graphique + « Voir en liste », demande de
  rendez-vous si le lien l'accepte). Même page neutre 404 pour un lien inconnu, arrêté ou expiré. noindex, nofollow,
  noarchive ; no-referrer ; aucune ressource externe (polices système, script et style en ligne avec nonce).
- Adresse lisible (17.11) : /agenda/<nom>/<lien> (agenda_resolve) sert la même page, ses demandes, son signalement et
  son aperçu, sans jamais montrer le jeton ; lien inconnu, arrêté ou expiré : la même page neutre.
- POST /d/<jeton>/demande (JSON) : la demande (champ piège, temps de saisie minimal, IP passée à la base qui la hache) ;
  POST /d/<jeton>/signaler : « Signaler cette page » sans compte ; GET /d/<jeton>/apercu.png : image de l'aperçu.
- Suivi de l'inconnu : GET /d/r/<secret> ; POST …/annuler, …/effacer, …/confirmer (e-mails futurs) ; GET …/rendez-vous.ics.
- Membres : POST /api/account/agenda/rpc (relais des fonctions de l'agenda pour l'app iPhone) et
  POST /api/account/agenda/ics (lecture d'un agenda ajouté avec un lien).
Toute adresse se construit depuis PARTY_PUBLIC_URL (configured_public_url) : jamais de domaine écrit en dur.

E-mails (pas en v1) : le point d'accroche est dans la base (private.agenda_bookings.mail_state, statut 'to_confirm' et
private.agenda_settings.double_opt_in) ; /d/r/<secret>/confirmer est déjà la cible du futur lien « Confirmer ma demande »."""
import html
import io
import json
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from . import agenda_ics, calendar_ics
from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError, Accounts

SWISS = ZoneInfo("Europe/Zurich")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
SECRET = re.compile(r"^[A-Za-z0-9_-]{24,64}$")
UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
MIN_FILL_SECONDS = 3      # temps de saisie minimal d'une demande (anti-robot, sans CAPTCHA)
LOOKUP_TIMEOUT = 6.0
# Robots d'aperçu (WhatsApp, iMessage, Mail…) : ils lisent la page sans compter une vue.
PREVIEW_BOTS = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|WhatsApp|Slack|Telegram|Discord|Twitterbot|"
                          r"LinkedIn|Applebot|Google|bing|Embedly|Iframely|Signal|Skype|vkShare|Pinterest", re.I)
# Fonctions de l'agenda que l'app iPhone appelle par le serveur (la base vérifie le compte et les droits).
RELAY = {
    "agenda_calendars_list", "agenda_calendar_save", "agenda_calendar_delete", "agenda_prefs_get", "agenda_prefs_save",
    "agenda_window", "agenda_item_save", "agenda_item_delete", "agenda_sharing", "agenda_set_sharing", "agenda_stop_sharing",
    "agenda_set_busy", "agenda_group_free", "agenda_links", "agenda_link_save", "agenda_link_set", "agenda_link_preview",
    "agenda_handle", "agenda_handle_set", "agenda_link_set_slug",
    "agenda_booking_requests", "agenda_badge", "agenda_booking_decide", "agenda_booking_owner_cancel",
    "agenda_booking_report", "agenda_booking_block", "agenda_unblock_senders",
}
ERROR_STATUS = {"not_found": 404, "closed": 409, "full": 409, "slot_taken": 409, "duplicate": 409, "rate_limited": 429,
                "invalid": 400, "content_refused": 400, "reason": 400, "forbidden": 403, "profile_incomplete": 403,
                "terms_required": 403, "self": 400}
FIELD_LABELS = {"first_name": "Prénom", "last_name": "Nom", "email": "Adresse e-mail", "phone": "Téléphone", "message": "Message"}
REASONS = (("harassment", "Harcèlement"), ("shocking", "Contenu choquant"), ("spam", "Spam"),
           ("scam", "Arnaque ou fraude"), ("other", "Autre raison"))
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


# ───────────────────────── Base ─────────────────────────
class Db:
    def __init__(self, accounts: Accounts):
        self.accounts = accounts

    def call(self, name: str, args: dict, token: str = SUPABASE_ANON_KEY) -> tuple[int, Any]:
        """(statut HTTP, corps JSON) ; 503 si la base ne répond pas."""
        try:
            r = self.accounts._get("POST", f"/rest/v1/rpc/{name}", token, json=args, timeout=LOOKUP_TIMEOUT)
        except AccountError:
            return 503, None
        try:
            body = r.json() if r.content else None
        except ValueError:
            body = None
        return r.status_code, body

    def get(self, path: str, token: str) -> tuple[int, Any]:
        try:
            r = self.accounts._get("GET", path, token, timeout=LOOKUP_TIMEOUT)
        except AccountError:
            return 503, None
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, None


def refusal(body: Any) -> tuple[str, str]:
    """« code: phrase » de la base → (code, phrase) ; ('error', '') sinon."""
    message = str(body.get("message", "")) if isinstance(body, dict) else ""
    found = re.match(r"^([a-z_]+): (.+)$", message.strip(), re.S)
    return (found.group(1), found.group(2).strip()) if found else ("error", "")


# ───────────────────────── Textes ─────────────────────────
def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _local(at: str | datetime) -> datetime:
    dt = at if isinstance(at, datetime) else datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    return dt.astimezone(SWISS)


def hour(at: str | datetime) -> str:
    """« 9 h », « 16 h 30 »."""
    d = _local(at)
    return f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "")


def long_day(at: str | datetime) -> str:
    """« Lundi 23 novembre »."""
    d = _local(at)
    return f"{WEEKDAYS[d.weekday()].capitalize()} {d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]}"


def span(s: str, e: str) -> str:
    return f"{hour(s)} – {hour(e)}"


def contact_line(contact: str | None, base: str) -> str:
    """Adresse de contact des réglages de modération (jamais écrite en dur) ; sans elle, la politique."""
    if contact:
        return f'<a href="mailto:{esc(contact)}">{esc(contact)}</a>'
    return f'voir la <a href="{esc(base)}/events/privacy" rel="noreferrer">politique de confidentialité</a>'


# ───────────────────────── Style et scripts (aucune ressource externe) ─────────────────────────
CSS = r"""
:root{--bg:#FFFFFF;--surf:#F6F7F6;--fg:#141615;--mut:#5A605C;--line:#E1E5E2;--soft:#EDF0EE;--acc:#2C5B4B;--accsoft:#E8F1EC;
--slot:#E3F0E9;--slotb:#2C5B4B;--onacc:#FFFFFF;--hatch:repeating-linear-gradient(135deg,#E6E9E7 0 1.5px,transparent 1.5px 7px);
--wait:#8A5A12;--waitsoft:#FBF1E1;--no:#8E2F2A;--nosoft:#F8E9E7;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#111312;--surf:#191C1A;--fg:#ECEFED;--mut:#A0A8A3;--line:#2A2F2C;--soft:#202522;
--acc:#8FC9AF;--accsoft:#16251E;--slot:#17291F;--slotb:#8FC9AF;--onacc:#0E1F17;
--hatch:repeating-linear-gradient(135deg,#2A302C 0 1.5px,transparent 1.5px 7px);--wait:#E8B86B;--waitsoft:#2A2216;--no:#F09A93;--nosoft:#2C1A19}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
button,input,textarea,select{font:inherit;color:inherit}a{color:var(--acc)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.pg{max-width:1120px;margin:0 auto;padding:0 16px;min-height:100vh;display:flex;flex-direction:column}
.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px 24px;padding:22px 0 14px}
.hd{display:flex;align-items:center;gap:12px}
.av{width:48px;height:48px;flex:none;border-radius:50%;display:grid;place-items:center;background:var(--soft);font-size:20px;font-weight:600}
.ov{margin:0;font-size:13px;color:var(--mut)}
.nm{margin:0;font-size:24px;line-height:1.15;font-weight:650;letter-spacing:-.01em}
.ln{margin:2px 0 0;font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.du{font-size:13px;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.vt{display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:4px;border-radius:14px;background:var(--soft);min-width:280px}
.vt button{min-height:44px;border:0;border-radius:10px;background:transparent;cursor:pointer;font-size:15px;font-weight:550;color:var(--mut)}
.vt button[aria-pressed="true"]{background:var(--bg);color:var(--fg);font-weight:650;box-shadow:0 1px 2px rgba(0,0,0,.12),inset 0 -2px 0 var(--acc)}
.bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.wn{display:flex;align-items:center;gap:10px}
.ib{width:44px;height:44px;display:grid;place-items:center;border-radius:12px;border:1px solid var(--line);background:var(--bg);cursor:pointer;font-size:18px}
.ib:disabled{opacity:.35;cursor:default}
.wk{margin:0;display:flex;flex-direction:column;line-height:1.2;min-width:170px;text-align:center}
.wk b{font-size:17px}.wk span{font-size:13px;color:var(--mut)}
.zb{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 12px;border-radius:12px;border:1px solid var(--line);background:var(--bg);cursor:pointer;font-size:14px}
.zb u{color:var(--acc);font-weight:600;text-underline-offset:3px}
.strip{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:6px;margin:14px 0 4px}
.ds{display:flex;flex-direction:column;align-items:center;min-height:64px;padding:8px 2px;border-radius:12px;border:1px solid var(--line);background:var(--bg);cursor:pointer}
.ds .a{font-size:12px;color:var(--mut)}.ds .b{font-size:18px;font-weight:650}.ds .c{font-size:11px;color:var(--acc);font-weight:600}
.ds.nil .c{color:var(--mut);font-weight:400}
.ds[aria-selected="true"]{background:var(--acc);border-color:var(--acc);color:var(--onacc)}
.ds[aria-selected="true"] .a,.ds[aria-selected="true"] .c{color:var(--onacc)}
.lg{list-style:none;display:flex;flex-wrap:wrap;gap:6px 14px;margin:12px 0 4px;padding:0;font-size:13px;color:var(--mut)}
.lg li{display:inline-flex;align-items:center;gap:6px}
.sw{width:16px;height:12px;border-radius:3px;flex:none}
.sw.ok{background:var(--slot);box-shadow:inset 3px 0 0 var(--slotb)}.sw.no{background:var(--bg);box-shadow:inset 0 0 0 1px var(--line)}
.sw.out{background:var(--hatch),var(--bg);box-shadow:inset 0 0 0 1px var(--line)}
.grid{display:grid;grid-template-columns:48px repeat(var(--n),minmax(0,1fr));margin-top:10px}
.gh{height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:13px;color:var(--mut);line-height:1.2;margin:0}
.gh b{font-size:19px;color:var(--fg)}.gh small{font-size:11.5px;color:var(--acc);font-weight:600}
.gc{border-left:1px solid var(--line);min-width:0}.gc:last-child{border-right:1px solid var(--line)}
.ax{position:relative}
.ax span{position:absolute;right:8px;top:-9px;font-size:12px;color:var(--mut)}
.tl{position:relative}
.hl{position:absolute;left:0;right:0;border-top:1px solid var(--line)}
.hz{position:absolute;left:0;right:0;background:var(--hatch);display:flex;align-items:flex-start;justify-content:center;padding-top:8px;overflow:hidden}
.hz span{font-size:12px;color:var(--mut);background:var(--bg);padding:2px 8px;border-radius:6px;text-align:center}
.slot{position:absolute;left:5px;right:5px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:0;padding:0 10px;
border:1px solid color-mix(in srgb,var(--slotb) 35%,transparent);border-left:4px solid var(--slotb);border-radius:6px 10px 10px 6px;background:var(--slot);text-align:left;overflow:hidden}
button.slot{cursor:pointer}
.slot .st{font-size:14.5px;font-weight:650;line-height:1.2;white-space:nowrap}.slot .sa{font-size:12px;color:var(--acc);font-weight:600;line-height:1.2}
.slot[aria-pressed="true"]{background:var(--acc);border-color:var(--acc);color:var(--onacc)}.slot[aria-pressed="true"] .sa{color:var(--onacc)}
.none{position:absolute;left:4px;right:4px;top:38%;text-align:center;color:var(--mut);margin:0;font-size:14px}
.ldays{display:flex;flex-direction:column;margin-top:8px}
.lday{padding:14px 0;border-bottom:1px solid var(--line)}.lday:last-child{border-bottom:0}
.lh{margin:0 0 8px;font-size:15.5px;font-weight:650}
.lss{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr;gap:8px}
.ls{width:100%;min-height:48px;display:flex;align-items:center;justify-content:space-between;gap:6px;padding:0 12px;border:1px solid var(--line);border-left:4px solid var(--slotb);border-radius:6px 10px 10px 6px;background:var(--bg);text-align:left}
button.ls{cursor:pointer}.ls .t{font-size:15.5px;font-weight:650}.ls .go{font-size:13px;color:var(--acc);font-weight:600}
.ls[aria-pressed="true"]{background:var(--acc);color:var(--onacc)}.ls[aria-pressed="true"] .go{color:var(--onacc)}
.lday .nil{margin:0;color:var(--mut);font-style:italic}
.ew{text-align:center;padding:36px 6px 20px}.ew h2{font-size:19px;margin:0 0 6px}.ew p{color:var(--mut);margin:0 0 16px}
.ew-a{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
.note{margin:14px 0 0;font-size:13.5px;color:var(--mut)}
.full{margin:12px 0 0;padding:10px 12px;border-radius:12px;background:var(--waitsoft);color:var(--fg);border-left:4px solid var(--wait)}
.ft{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:4px 8px;font-size:12.5px;color:var(--mut);padding:22px 0;margin-top:auto}
.ft button,.ft a{color:var(--mut);background:none;border:0;min-height:44px;cursor:pointer;text-decoration:underline;text-underline-offset:3px;font-size:12.5px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:48px;padding:0 18px;border-radius:12px;background:var(--acc);color:var(--onacc);border:0;text-decoration:none;font-weight:650;cursor:pointer;font-size:15.5px}
.btn.wide{width:100%;min-height:52px}.btn.ghost{background:transparent;color:var(--fg);border:1px solid var(--line)}
.btn.danger{background:transparent;color:var(--no);border:1px solid var(--line)}
dialog{border:0;border-radius:18px;padding:0;background:var(--bg);color:var(--fg);width:min(520px,calc(100vw - 24px));max-height:calc(100vh - 24px);box-shadow:0 20px 60px rgba(0,0,0,.25)}
dialog::backdrop{background:rgba(10,12,11,.45)}
.dl{padding:18px 20px 22px}
.dh{display:flex;align-items:center;justify-content:space-between;gap:12px}.dh h2{font-size:19px;margin:0}
.x{width:44px;height:44px;border-radius:50%;border:0;background:var(--soft);cursor:pointer;font-size:15px;flex:none}
.ctx{margin:12px 0 4px;padding:10px 12px;border-radius:12px;background:var(--accsoft);border-left:4px solid var(--acc)}
.ctx b{display:block}.ctx span{font-size:13px;color:var(--mut)}
.fld{display:block;margin:12px 0 0}
.fl{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:14px;font-weight:650;margin-bottom:6px}
.need{font-size:12px;font-weight:500;background:var(--soft);border-radius:6px;padding:1px 6px}.opt{font-size:12px;font-weight:400;color:var(--mut)}
.fld input,.fld textarea,.fld select{width:100%;min-height:46px;border:1px solid var(--line);border-radius:12px;background:var(--surf);padding:10px 12px;font-size:16px}
.fld textarea{resize:vertical;min-height:96px;line-height:1.4}.fld small{display:block;font-size:12px;color:var(--mut);margin-top:4px}
.fld.bad input,.fld.bad textarea{border:2px solid var(--no)}
.err{margin:8px 0 0;padding:8px 10px;border-radius:10px;background:var(--nosoft);font-size:13.5px;line-height:1.4;border-left:4px solid var(--no)}
.err b{color:var(--no);display:block}
.hp{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}
.notice{margin:14px 0 12px;font-size:12.5px;color:var(--mut);line-height:1.45;border-top:1px solid var(--line);padding-top:10px}
.notice summary{cursor:pointer;list-style:none;min-height:44px}.notice summary::-webkit-details-marker{display:none}
.notice .more{color:var(--acc);font-weight:600;text-decoration:underline;white-space:nowrap}.notice p{margin:4px 0 0}
.zl{list-style:none;margin:10px 0 0;padding:0;max-height:50vh;overflow:auto}
.zi{display:flex;align-items:center;gap:12px;width:100%;min-height:56px;border:0;border-bottom:1px solid var(--line);background:none;text-align:left;padding:8px 2px;cursor:pointer}
.zi small{display:block;color:var(--mut);font-size:13px}.zi[aria-checked="true"] b::after{content:" ✓";color:var(--acc)}
.off{margin:auto;max-width:420px;text-align:center;padding:60px 0 20px}.off h1{font-size:24px;margin:14px 0 8px}.off p{color:var(--mut)}
.stt{text-align:center;padding:26px 0 6px}.stt h1{font-size:24px;margin:6px 0 10px}.stt p{color:var(--mut);margin:0 0 10px}
.stt .when{color:var(--fg);font-size:17px}.stt .when span{display:block;color:var(--mut);font-size:15px}
.badge{display:inline-block;font-size:13px;font-weight:650;border-radius:999px;padding:3px 12px}
.wait .badge{background:var(--waitsoft);color:var(--wait)}.ok .badge{background:var(--accsoft);color:var(--acc)}.no .badge{background:var(--nosoft);color:var(--no)}
.box{max-width:560px;margin:0 auto;width:100%}
.secret{margin-top:12px;background:var(--surf);border:1px solid var(--line);border-radius:14px;padding:14px}
.secret p{margin:0 0 6px}.secret .lnk{word-break:break-all;font-size:15px}
.mine{margin-top:12px;border:1px solid var(--line);border-radius:14px;padding:0 14px}
.mine summary{min-height:48px;display:flex;align-items:center;font-weight:600;cursor:pointer}
.mine dl{margin:0}.mine dl div{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-top:1px solid var(--line);font-size:14px}
.mine dt{color:var(--mut)}.mine dd{margin:0;text-align:right;word-break:break-word}
.two{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.two form{display:contents}
.fine{font-size:12.5px;color:var(--mut);line-height:1.45;margin:10px 0 0}
@media (max-width:759px){.grid.week{display:none}.vt{min-width:0;width:100%}.top>.vt{order:3;flex:1 1 100%}}
@media (min-width:760px){.grid.day,.strip{display:none}.lss{grid-template-columns:repeat(3,minmax(0,280px))}
.lday{display:grid;grid-template-columns:180px 1fr;gap:16px;align-items:start}.lh{margin-top:12px}}
@media (prefers-reduced-motion:no-preference){.slot,.ls,.ds{transition:background .15s}}
"""

PAGE_JS = r"""
(function(){
var D=JSON.parse(document.getElementById('agenda-data').textContent);
var TZ0=D.tz,tz=TZ0,dev=(Intl.DateTimeFormat().resolvedOptions().timeZone||TZ0);
var booking=!!(D.booking&&!D.booking.full);
var slots=D.slots.map(function(x){return [new Date(x[0]),new Date(x[1])];});
var M=['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];
var MS=['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'];
var W=['dimanche','lundi','mardi','mercredi','jeudi','vendredi','samedi'];
var WS=['Dim.','Lun.','Mar.','Mer.','Jeu.','Ven.','Sam.'];
var CITY={Zurich:'Zurich',London:'Londres',Paris:'Paris',Brussels:'Bruxelles',Berlin:'Berlin',Rome:'Rome',Madrid:'Madrid',Lisbon:'Lisbonne',
New_York:'New York',Montreal:'Montréal',Toronto:'Toronto',Los_Angeles:'Los Angeles',Chicago:'Chicago',Tokyo:'Tokyo',Dubai:'Dubaï',
Dakar:'Dakar',Abidjan:'Abidjan',Casablanca:'Casablanca',Tunis:'Tunis',Algiers:'Alger',Beirut:'Beyrouth',Mauritius:'Maurice'};
function city(z){var c=z.split('/').pop();return CITY[c]||c.replace(/_/g,' ');}
var fmtCache={};
function P(d,z){var f=fmtCache[z]||(fmtCache[z]=new Intl.DateTimeFormat('en-GB',{timeZone:z,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}));
 var o={};f.formatToParts(d).forEach(function(p){o[p.type]=p.value;});return {y:+o.year,m:+o.month,d:+o.day,h:+o.hour%24,mi:+o.minute};}
function off(t,z){var p=P(new Date(t),z);return Date.UTC(p.y,p.m-1,p.d,p.h,p.mi)-Math.floor(t/60000)*60000;}
function zoned(y,m,d,h,mi,z){var g=Date.UTC(y,m-1,d,h,mi);var t=g-off(g,z);return new Date(g-off(t,z));}
function key(d){var p=P(d,tz);return p.y+'-'+String(p.m).padStart(2,'0')+'-'+String(p.d).padStart(2,'0');}
function kd(k){var a=k.split('-');return new Date(Date.UTC(+a[0],+a[1]-1,+a[2]));}
function mins(d){var p=P(d,tz);return p.h*60+p.mi;}
function hm(d){var p=P(d,tz);return p.h+' h'+(p.mi?' '+String(p.mi).padStart(2,'0'):'');}
function hmEnd(d){var p=P(d,tz);if(p.h===0&&p.mi===0)return '24 h';return hm(d);}
function dur(s,e){var m=Math.round((e-s)/60000),h=Math.floor(m/60),r=m%60;return (h?h+' h':'')+(h&&r?' '+String(r).padStart(2,'0'):(!h?r+' min':''));}
function longDay(k){var d=kd(k);return W[d.getUTCDay()].replace(/^./,function(c){return c.toUpperCase();})+' '+d.getUTCDate()+(d.getUTCDate()===1?'er':'')+' '+M[d.getUTCMonth()];}
function shortDay(k){var d=kd(k);return WS[d.getUTCDay()]+' '+d.getUTCDate();}
function addDays(k,n){var d=kd(k);d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);}
function monday(k){var d=kd(k),w=(d.getUTCDay()+6)%7;return addDays(k,-w);}
// Fenêtres du lien (heure de Suisse), de demain à l'horizon.
var wins=[];(function(){var k=D.from;while(k<=D.to){var dow=((kd(k).getUTCDay()+6)%7)+1;var a=k.split('-');
 D.rules.forEach(function(r){if(r.days.indexOf(dow)<0)return;var f=r.from.split(':'),t=r.to.split(':');
  var s=zoned(+a[0],+a[1],+a[2],+f[0],+f[1],TZ0),e=(r.to==='24:00')?zoned(+addDays(k,1).slice(0,4),+addDays(k,1).slice(5,7),+addDays(k,1).slice(8,10),0,0,TZ0):zoned(+a[0],+a[1],+a[2],+t[0],+t[1],TZ0);
  wins.push([s,e]);});k=addDays(k,1);}})();
var days,weeks,wi=0,sel=null,view='grid';
function build(){days={};wins.forEach(function(w){var k=key(w[0]);(days[k]=days[k]||{w:[],s:[]}).w.push(w);});
 slots.forEach(function(s){var k=key(s[0]);(days[k]=days[k]||{w:[],s:[]}).s.push(s);});
 var ws={};Object.keys(days).forEach(function(k){(ws[monday(k)]=ws[monday(k)]||[]).push(k);});
 weeks=Object.keys(ws).sort().map(function(m){return {m:m,d:ws[m].sort()};});}
function el(t,c,txt){var e=document.createElement(t);if(c)e.className=c;if(txt!=null)e.textContent=txt;return e;}
function label(s,e){return hm(s)+' – '+hmEnd(e);}
function weekLabel(w){var a=kd(w.d[0]),b=kd(w.d[w.d.length-1]);return a.getUTCMonth()===b.getUTCMonth()?a.getUTCDate()+' – '+b.getUTCDate()+' '+M[b.getUTCMonth()]:a.getUTCDate()+' '+MS[a.getUTCMonth()]+' – '+b.getUTCDate()+' '+MS[b.getUTCMonth()];}
function count(n){return D.booking?(n?n+' créneau'+(n>1?'x':''):'aucun'):(n?n+' plage'+(n>1?'s':''):'aucune');}
function pick(s,btn){document.querySelectorAll('[data-pick]').forEach(function(b){b.setAttribute('aria-pressed','false');var a=b.querySelector('.sa,.go');if(a)a.textContent=b.dataset.idle;});
 btn.setAttribute('aria-pressed','true');var a=btn.querySelector('.sa,.go');if(a)a.textContent='✓ Choisi';openAsk(s);}
function slotEl(s,cls,inGrid){var b=el(booking?'button':'div',cls);if(booking){b.type='button';b.dataset.pick='1';b.dataset.idle=inGrid?'Disponible':'Demander';b.setAttribute('aria-pressed','false');
 b.setAttribute('aria-label','Disponible de '+label(s[0],s[1]).replace(' – ',' à ')+', '+longDay(key(s[0]))+'. Demander ce créneau.');b.addEventListener('click',function(){pick(s,b);});}
 b.appendChild(el('span',inGrid?'st':'t',label(s[0],s[1])));b.appendChild(el('span',inGrid?'sa':'go',booking?(inGrid?'Disponible':'Demander'):(inGrid?'Disponible':dur(s[0],s[1]))));return b;}
function column(k,axis,head){var c=el('div','gc');if(head){var h=el('p','gh');h.appendChild(el('span',null,WS[kd(k).getUTCDay()]));h.appendChild(el('b',null,String(kd(k).getUTCDate())));
 h.appendChild(el('small',null,count(days[k].s.length)));c.appendChild(h);}
 var tl=el('div','tl'),H=56,h0=axis[0];tl.style.height=((axis[1]-axis[0])*H)+'px';
 for(var x=axis[0];x<=axis[1];x++){var l=el('div','hl');l.style.top=((x-h0)*H)+'px';tl.appendChild(l);}
 var iv=days[k].w.map(function(w){return [mins(w[0]),key(w[1])!==k?1440:mins(w[1])];}).sort(function(a,b){return a[0]-b[0];});
 var cur=h0*60,gaps=[];iv.forEach(function(v){if(v[0]>cur)gaps.push([cur,v[0]]);cur=Math.max(cur,v[1]);});if(cur<axis[1]*60)gaps.push([cur,axis[1]*60]);
 gaps.forEach(function(g){if(g[1]-g[0]<30)return;var z=el('div','hz');z.style.top=((g[0]/60-h0)*H)+'px';z.style.height=((g[1]-g[0])/60*H)+'px';
  if(g[1]-g[0]>=90)z.appendChild(el('span',null,'Hors des heures de ce lien'));z.setAttribute('aria-hidden','true');tl.appendChild(z);});
 var list=el('div');list.setAttribute('role','list');
 days[k].s.forEach(function(s){var b=slotEl(s,'slot',true);var m0=mins(s[0]),m1=key(s[1])!==k?1440:mins(s[1]);b.style.top=((m0/60-h0)*H+2)+'px';b.style.height=Math.max(((m1-m0)/60*H)-4,26)+'px';
  if(!booking)b.setAttribute('role','listitem');list.appendChild(b);});
 tl.appendChild(list);if(!days[k].s.length)tl.appendChild(el('p','none','Pas de disponibilité ce jour'));c.appendChild(tl);return c;}
function axisOf(w){var a=24,b=0;w.d.forEach(function(k){days[k].w.forEach(function(x){a=Math.min(a,Math.floor(mins(x[0])/60));b=Math.max(b,key(x[1])!==k?24:Math.ceil(mins(x[1])/60));});});
 if(a>=b){a=8;b=18;}return [a,b];}
function axisCol(axis){var c=el('div','ax'),H=56;c.style.marginTop='56px';for(var x=axis[0];x<=axis[1];x++){var s=el('span',null,x+' h');s.style.top=((x-axis[0])*H)+'px';c.appendChild(s);}return c;}
function nextFree(after){for(var i=0;i<slots.length;i++)if(slots[i][0]>=after)return slots[i];return null;}
function render(){var root=document.getElementById('cal');root.innerHTML='';var w=weeks[wi];
 document.getElementById('prev').disabled=wi<=0;document.getElementById('next').disabled=wi>=weeks.length-1;
 document.getElementById('wkl').textContent=w?weekLabel(w):'';document.getElementById('zl').textContent='Heure de '+city(tz);
 if(!slots.length){var e=el('div','ew');e.appendChild(el('h2',null,'Pas de disponibilité pour le moment'));e.appendChild(el('p',null,'Rien n’est libre dans les heures de ce lien jusqu’au '+longDay(D.to).toLowerCase()+'.'));root.appendChild(e);return;}
 var total=w.d.reduce(function(n,k){return n+days[k].s.length;},0);
 if(!total){var e2=el('div','ew');e2.appendChild(el('h2',null,'Pas de disponibilité cette semaine'));var nf=nextFree(kd(addDays(w.d[w.d.length-1],1)));
  if(nf)e2.appendChild(el('p',null,'Prochain créneau libre : '+longDay(key(nf[0])).toLowerCase()+'.'));var acts=el('div','ew-a');
  if(wi<weeks.length-1){var bn=el('button','btn ghost','Semaine suivante');bn.type='button';bn.addEventListener('click',function(){wi++;sel=null;render();});acts.appendChild(bn);}
  if(nf){var bg=el('button','btn','Aller au '+kd(key(nf[0])).getUTCDate()+' '+M[kd(key(nf[0])).getUTCMonth()]);bg.type='button';bg.addEventListener('click',function(){var k=key(nf[0]);wi=weeks.findIndex(function(x){return x.d.indexOf(k)>=0;});sel=k;render();});acts.appendChild(bg);}
  e2.appendChild(acts);root.appendChild(e2);return;}
 if(view==='list'){var ld=el('div','ldays');w.d.forEach(function(k){var sec=el('section','lday');sec.appendChild(el('h2','lh',longDay(k)));
   if(!days[k].s.length)sec.appendChild(el('p','nil','Pas de disponibilité ce jour'));else{var ul=el('ul','lss');days[k].s.forEach(function(s){var li=el('li');li.appendChild(slotEl(s,'ls',false));ul.appendChild(li);});sec.appendChild(ul);}
   ld.appendChild(sec);});root.appendChild(ld);return;}
 if(!sel||w.d.indexOf(sel)<0)sel=w.d.find(function(k){return days[k].s.length;})||w.d[0];
 var strip=el('div','strip');strip.style.setProperty('--n',w.d.length);strip.setAttribute('role','tablist');
 w.d.forEach(function(k){var b=el('button','ds'+(days[k].s.length?'':' nil'));b.type='button';b.setAttribute('role','tab');b.setAttribute('aria-selected',String(k===sel));
  b.appendChild(el('span','a',WS[kd(k).getUTCDay()]));b.appendChild(el('span','b',String(kd(k).getUTCDate())));b.appendChild(el('span','c',count(days[k].s.length)));
  b.setAttribute('aria-label',longDay(k)+', '+count(days[k].s.length));b.addEventListener('click',function(){sel=k;render();});strip.appendChild(b);});
 root.appendChild(strip);root.appendChild(legend());var axis=axisOf(w);
 var g1=el('div','grid day');g1.style.setProperty('--n',1);g1.appendChild(axisCol([axis[0],axis[1]]));g1.firstChild.style.marginTop='0';
 var dt=el('h2','sr',longDay(sel));root.appendChild(dt);g1.appendChild(column(sel,axis,false));root.appendChild(g1);
 var g=el('div','grid week');g.style.setProperty('--n',w.d.length);g.appendChild(axisCol(axis));w.d.forEach(function(k){g.appendChild(column(k,axis,true));});root.appendChild(g);}
function legend(){var u=el('ul','lg');[['ok',booking?'Disponible : touchez pour demander':'Disponible'],['no','Non disponible'],['out','Hors des heures de ce lien']].forEach(function(x){var li=el('li');li.appendChild(el('span','sw '+x[0]));li.appendChild(el('span',null,x[1]));u.appendChild(li);});return u;}
function setView(v){view=v;document.querySelectorAll('[data-view]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.view===v));});render();}
document.querySelectorAll('[data-view]').forEach(function(b){b.addEventListener('click',function(){setView(b.dataset.view);});});
document.getElementById('prev').addEventListener('click',function(){if(wi>0){wi--;sel=null;render();}});
document.getElementById('next').addEventListener('click',function(){if(wi<weeks.length-1){wi++;sel=null;render();}});
build();wi=Math.max(0,weeks.findIndex(function(w){return w.d.some(function(k){return days[k].s.length;});}));render();
// Fuseau : seul l'affichage change.
var zd=document.getElementById('tzd');document.getElementById('zbtn').addEventListener('click',function(){var ul=document.getElementById('tzl');ul.innerHTML='';
 var zs=[TZ0];if(dev!==TZ0)zs.push(dev);['Europe/Paris','Europe/London','America/Montreal','America/New_York','Africa/Dakar'].forEach(function(z){if(zs.indexOf(z)<0)zs.push(z);});
 zs.forEach(function(z){var b=el('button','zi');b.type='button';b.setAttribute('role','menuitemradio');b.setAttribute('aria-checked',String(z===tz));var t=el('span');t.appendChild(el('b',null,'Heure de '+city(z)));
  var o=off(Date.now(),z)/3600000,os='UTC'+(o>=0?'+':'−')+Math.abs(o);t.appendChild(el('small',null,os+(z===TZ0?' · fuseau de '+D.name:z===dev?' · fuseau de cet appareil':'')));b.appendChild(t);
  b.addEventListener('click',function(){tz=z;zd.close();build();wi=Math.max(0,weeks.findIndex(function(w){return w.d.some(function(k){return days[k].s.length;});}));sel=null;render();});var li=el('li');li.appendChild(b);ul.appendChild(li);});
 zd.showModal();});
document.querySelectorAll('[data-close]').forEach(function(b){b.addEventListener('click',function(){b.closest('dialog').close();});});
// Demande.
var ask=document.getElementById('ask'),form=document.getElementById('askf'),opened=Date.now(),chosen=null;
function openAsk(s){if(!ask)return;chosen=s;document.getElementById('ctxd').textContent=longDay(key(s[0]));document.getElementById('ctxt').textContent=label(s[0],s[1]);
 document.getElementById('ctxz').textContent=dur(s[0],s[1])+' · heure de '+city(tz);clearErr();ask.showModal();}
function clearErr(){if(!form)return;form.querySelectorAll('.err').forEach(function(e){e.remove();});form.querySelectorAll('.bad').forEach(function(e){e.classList.remove('bad');});}
function showErr(field,title,text){var where=field&&form.querySelector('[data-field="'+field+'"]');var box=el('div','err');box.setAttribute('role','alert');if(title)box.appendChild(el('b',null,title));box.appendChild(el('span',null,text));
 if(where){where.classList.add('bad');where.appendChild(box);}else form.querySelector('.actions').before(box);box.scrollIntoView({block:'nearest'});}
if(form)form.addEventListener('submit',function(ev){ev.preventDefault();clearErr();if(!chosen)return;var btn=form.querySelector('[type=submit]');btn.disabled=true;
 var a={};form.querySelectorAll('[data-answer]').forEach(function(i){a[i.name]=i.value;});
 fetch(location.pathname.replace(/\/$/,'')+'/demande',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',
  body:JSON.stringify({starts_at:chosen[0].toISOString(),answers:a,site:form.querySelector('[name=site]').value,elapsed:Math.round((Date.now()-opened)/1000)})})
 .then(function(r){return r.json().then(function(j){return [r.status,j];});}).then(function(x){if(x[0]===200&&x[1].url){location.assign(x[1].url);return;}btn.disabled=false;var j=x[1]||{};
  showErr(j.field,j.title||null,j.message||'La demande n’est pas partie. Réessayez dans un instant.');
  if(j.code==='slot_taken'||j.code==='full'){var r=el('button','btn ghost','Voir les créneaux à jour');r.type='button';r.addEventListener('click',function(){location.reload();});form.querySelector('.actions').before(r);}})
 .catch(function(){btn.disabled=false;showErr(null,null,'Pas de réseau. Réessayez dans un instant.');});});
// Signaler.
var rep=document.getElementById('rep'),repf=document.getElementById('repf');
document.getElementById('repbtn').addEventListener('click',function(){rep.showModal();});
repf.addEventListener('submit',function(ev){ev.preventDefault();var fd=new FormData(repf);fetch(location.pathname.replace(/\/$/,'')+'/signaler',{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({reason:fd.get('reason'),comment:fd.get('comment')||''})}).then(function(r){return r.json();}).then(function(j){var p=document.getElementById('repmsg');p.textContent=j.message||'Merci.';p.hidden=false;repf.hidden=true;})
 .catch(function(){var p=document.getElementById('repmsg');p.textContent='Pas de réseau. Réessayez dans un instant.';p.hidden=false;});});
})();
"""

STATUS_JS = r"""
(function(){
var c=document.getElementById('copy');if(c)c.addEventListener('click',function(){var t=document.getElementById('lnk').textContent;
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(function(){c.textContent='Lien copié';},function(){c.textContent='Sélectionnez le lien pour le copier';});});
document.querySelectorAll('form[data-confirm]').forEach(function(f){f.addEventListener('submit',function(ev){if(!confirm(f.dataset.confirm))ev.preventDefault();});});
})();
"""


# ───────────────────────── Pages ─────────────────────────
def _shell(title: str, body: str, nonce: str, meta: str = "", script: str = "") -> str:
    return (f'<!doctype html><html lang="fr-CH"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer">'
            f'<meta name="color-scheme" content="light dark"><title>{esc(title)}</title>{meta}'
            f'<style nonce="{nonce}">{CSS}</style></head><body>{body}'
            + (f'<script nonce="{nonce}">{script}</script>' if script else "") + "</body></html>")


def _footer(report: bool) -> str:
    rep = '<span aria-hidden="true">·</span><button type="button" id="repbtn">Signaler cette page</button>' if report else ""
    return f'<footer class="ft"><span>Agenda partagé avec Vendredi Party</span>{rep}</footer>'


def gone_page(nonce: str, base: str, title: str = "Ce lien n’est plus actif",
              text: str = "Il a été arrêté ou a expiré. Si vous en avez besoin, demandez un nouveau lien à la personne qui vous l’a envoyé.") -> str:
    meta = _og("Lien d’agenda", "Vendredi Party", f"{base}/d/apercu-inactif.png")
    body = (f'<main class="pg"><div class="off"><svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>'
            f'<h1>{esc(title)}</h1><p>{esc(text)}</p></div>{_footer(False)}</main>')
    return _shell(title, body, nonce, meta)


def _og(title: str, description: str, image: str) -> str:
    tags = {"og:type": "website", "og:site_name": "Vendredi Party", "og:title": title, "og:description": description,
            "og:image": image, "og:image:width": "1200", "og:image:height": "630", "twitter:card": "summary_large_image",
            "twitter:title": title, "twitter:description": description}
    return "".join(f'<meta {"name" if k.startswith("twitter:") else "property"}="{k}" content="{esc(v)}">' for k, v in tags.items())


def _field(key: str, mode: str, name: str, label: str | None) -> str:
    if mode == "off":
        return ""
    need = '<span class="need">obligatoire pour ce rendez-vous</span>' if mode == "required" else '<span class="opt">facultatif</span>'
    req = " required" if mode == "required" else ""
    if key == "message":
        title = label or "Votre message"
        return (f'<label class="fld" data-field="message"><span class="fl">{esc(title)} {need}</span>'
                f'<textarea name="message" data-answer maxlength="500" rows="4"{req}></textarea>'
                f'<small>500 caractères au plus · les liens ne sont pas acceptés</small></label>')
    kind = {"first_name": ('text', 'given-name', 40), "last_name": ('text', 'family-name', 40),
            "email": ('email', 'email', 254), "phone": ('tel', 'tel', 25)}[key]
    hint = f'<small>Pour que {esc(name)} puisse vous répondre.</small>' if key == "email" else ""
    return (f'<label class="fld" data-field="{key}"><span class="fl">{FIELD_LABELS[key]} {need}</span>'
            f'<input type="{kind[0]}" name="{key}" data-answer autocomplete="{kind[1]}" maxlength="{kind[2]}"{req}>{hint}</label>')


def notice(name: str, contact: str | None, base: str) -> str:
    """Notice de la conformité (3e volet, 🔴 1), au vouvoiement, sans case à cocher ; responsable : Vendredi Party."""
    return (f'<details class="notice"><summary>Vos réponses (champs remplis, créneau) sont transmises à {esc(name)}, et à personne '
            f'd’autre, pour répondre à votre demande. <span class="more">En savoir plus</span></summary>'
            f'<p>Responsable : Vendredi Party (Suisse), {contact_line(contact, base)}. Données gardées en Suisse ; effacées aussitôt si la '
            f'demande est refusée, annulée ou sans réponse sous 48 h, sinon 30 jours après le rendez-vous. Votre adresse IP est gardée '
            f'sous forme chiffrée 24 h contre les abus. N’indiquez aucune donnée sensible (santé…). Vous suivez, annulez ou effacez '
            f'votre demande avec le lien secret qui s’affiche après l’envoi ; vos droits (accès, effacement, opposition, plainte au '
            f'PFPDT / à la CNIL) : voir la <a href="{esc(base)}/events/privacy" rel="noreferrer">politique de confidentialité</a>.</p></details>')


def rules_text(rules: list) -> str:
    """« Lundi à vendredi » ; sinon les jours abrégés."""
    days = sorted({d for r in rules for d in r.get("days", [])})
    names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    if len(days) > 2 and days == list(range(days[0], days[-1] + 1)):
        return f"{names[days[0] - 1].capitalize()} à {names[days[-1] - 1]}"
    return ", ".join(names[d - 1] for d in days).capitalize()


def noscript_list(data: dict) -> str:
    """Les mêmes créneaux en texte, sans JavaScript (heure de Suisse)."""
    by_day: dict[str, list] = {}
    for s, e in data.get("slots") or []:
        by_day.setdefault(long_day(s), []).append(span(s, e))
    if not by_day:
        return "<p>Pas de disponibilité pour le moment.</p>"
    return "".join(f'<section class="lday"><h2 class="lh">{esc(day)}</h2><ul class="lss">'
                   + "".join(f"<li>Disponible de {esc(x)}</li>" for x in xs) + "</ul></section>" for day, xs in by_day.items())


def link_page(data: dict, path: str, base: str, nonce: str) -> str:
    """path : adresse de la page (/d/<jeton> ou /agenda/<nom>/<lien>) ; l'adresse lisible ne montre jamais le jeton."""
    name, booking = data["name"], data.get("booking")
    over = "Prendre rendez-vous avec" if booking else "Disponibilités de"
    title = f"{over} {name}"
    h, m = divmod(int(data["duration_min"]), 60)
    dur = (f"{h} h" if h else "") + (f" {m:02d}" if h and m else f"{m} min" if m else "")
    meta = _og(f"{'Prendre rendez-vous' if booking else 'Disponibilités'}", f"{name} — {data['link_name']}",
               f"{base}{path}/apercu.png")
    form = ""
    if booking:
        fields = booking["fields"]
        inputs = "".join(_field(k, fields.get(k, "off"), name, booking.get("message_label")) for k in
                         ("first_name", "last_name", "email", "phone", "message"))
        form = (f'<dialog id="ask" aria-labelledby="askt"><form id="askf" class="dl" novalidate>'
                f'<div class="dh"><h2 id="askt">Demander un rendez-vous</h2><button type="button" class="x" data-close aria-label="Fermer">✕</button></div>'
                f'<div class="ctx"><b id="ctxd"></b><b id="ctxt"></b><span id="ctxz"></span> · '
                f'<button type="button" class="opt" data-close>Changer de créneau</button></div>'
                f'{inputs}<label class="hp" aria-hidden="true">Ne pas remplir<input name="site" tabindex="-1" autocomplete="off"></label>'
                f'{notice(name, data.get("contact_email"), base)}'
                f'<div class="actions"><button type="submit" class="btn wide">Demander ce rendez-vous</button></div>'
                f'<p class="fine">{esc(name)} a {int(booking.get("pending_hours", 48))} h pour répondre ; sans réponse, le créneau se libère.</p>'
                f'</form></dialog>')
    full = (f'<p class="full" role="status">Ce lien ne prend plus de demandes pour le moment. Les disponibilités restent affichées.</p>'
            if booking and booking.get("full") else "")
    tail = ("" if booking else
            f'<p class="note">Les heures affichées sont libres dans l’agenda de {esc(name)}. Pour convenir d’un moment, '
            f'répondez-lui là où vous avez reçu ce lien.</p>')
    report = (f'<dialog id="rep" aria-labelledby="rept"><div class="dl"><div class="dh"><h2 id="rept">Signaler cette page</h2>'
              f'<button type="button" class="x" data-close aria-label="Fermer">✕</button></div>'
              f'<form id="repf"><label class="fld"><span class="fl">Raison</span><select name="reason" required>'
              + "".join(f'<option value="{k}">{v}</option>' for k, v in REASONS) +
              f'</select></label><label class="fld"><span class="fl">Précisions <span class="opt">facultatif</span></span>'
              f'<textarea name="comment" maxlength="500" rows="3"></textarea></label>'
              f'<p class="fine">Le signalement part à l’équipe de modération de Vendredi Party, pas à {esc(name)}.</p>'
              f'<div class="actions"><button type="submit" class="btn wide">Envoyer le signalement</button></div></form>'
              f'<p id="repmsg" role="status" hidden></p></div></dialog>')
    tz = ('<dialog id="tzd" aria-labelledby="tzt"><div class="dl"><div class="dh"><h2 id="tzt">Afficher les heures de…</h2>'
          '<button type="button" class="x" data-close aria-label="Fermer">✕</button></div><ul class="zl" id="tzl" role="menu"></ul>'
          f'<p class="fine">Seul votre affichage change. {esc(name)} n’en sait rien.</p></div></dialog>')
    payload = json.dumps({k: data[k] for k in ("name", "tz", "rules", "from", "to", "slots", "booking")}, ensure_ascii=False)
    body = (f'<main class="pg"><header class="top"><div class="hd"><div class="av" aria-hidden="true">{esc(name[:1].upper())}</div>'
            f'<div><p class="ov">{over}</p><h1 class="nm">{esc(name)}</h1><p class="ln">{esc(data["link_name"])}'
            + (f' <span class="du">{esc(dur)}</span>' if booking else "") + '</p></div></div>'
            f'<div class="vt" role="group" aria-label="Affichage"><button type="button" data-view="grid" aria-pressed="true">Voir en grille</button>'
            f'<button type="button" data-view="list" aria-pressed="false">Voir en liste</button></div></header>'
            f'<div class="bar"><div class="wn"><button type="button" class="ib" id="prev" aria-label="Semaine précédente">‹</button>'
            f'<p class="wk" aria-live="polite"><b id="wkl"></b><span>{esc(rules_text(data["rules"]))}</span></p>'
            f'<button type="button" class="ib" id="next" aria-label="Semaine suivante">›</button></div>'
            f'<button type="button" class="zb" id="zbtn"><span id="zl">Heure de Zurich</span> <u>Changer</u></button></div>'
            f'{full}<div id="cal"><noscript>{noscript_list(data)}</noscript></div>{tail}{_footer(True)}</main>'
            f'{form}{report}{tz}'
            f'<script type="application/json" id="agenda-data">{payload.replace("<", chr(92) + "u003c")}</script>')
    return _shell(title, body, nonce, meta, PAGE_JS)


STATES = {
    "to_confirm": ("wait", "À confirmer", "Confirmez votre demande"),
    "pending": ("wait", "En attente de confirmation", "Demande envoyée"),
    "accepted": ("ok", "Confirmé", "Rendez-vous confirmé"),
    "refused": ("no", "Non retenu", "{name} ne peut pas ce jour-là"),
    "expired": ("no", "Non retenu", "{name} ne peut pas ce jour-là"),
    "cancelled": ("no", "Annulé", "Rendez-vous annulé"),
}


def status_page(data: dict, secret: str, base: str, nonce: str) -> str:
    name, st = data["name"], data["status"]
    tone, badge, h1 = STATES.get(st, STATES["pending"])
    when = (f'<p class="when">{esc(long_day(data["starts_at"]))} <span>{esc(span(data["starts_at"], data["ends_at"]))} · '
            f'heure de Zurich</span></p>')
    here = f"/d/r/{secret}"
    if st == "pending":
        left = max(1, round((_local(data["expires_at"]) - datetime.now(timezone.utc)).total_seconds() / 3600)) if data.get("expires_at") else 48
        lead = f"Ce créneau vous est réservé. {esc(name)} a encore {left} h pour confirmer ; sans réponse, il se libère."
    elif st == "to_confirm":
        lead = "Confirmez votre demande pour qu’elle parte. Sans confirmation, le créneau se libère."
    elif st == "accepted":
        lead = f"{esc(name)} a accepté votre demande."
    elif st == "cancelled":
        lead = "Le rendez-vous est annulé. Vos informations ont été effacées."
    else:
        lead = "Votre demande n’a pas été retenue. Vos informations ont été effacées."
    parts = [f'<div class="stt {tone}"><span class="badge">{esc(badge)}</span><h1>{esc(h1.format(name=name))}</h1>{when}<p>{lead}</p></div>']
    if st in ("pending", "to_confirm", "accepted"):
        parts.append(f'<div class="secret"><p class="fine">Votre lien pour suivre la demande</p><p class="lnk" id="lnk">{esc(base + here)}</p>'
                     f'<button type="button" class="btn ghost" id="copy">Copier le lien</button>'
                     f'<p class="fine">Gardez-le : aucun e-mail n’est envoyé pour l’instant. Il ne montre que cette demande.</p></div>')
    if st == "to_confirm":
        parts.append(f'<form method="post" action="{here}/confirmer"><button class="btn wide">Confirmer ma demande</button></form>')
    if st == "accepted":
        parts.append(f'<p><a class="btn wide" href="{here}/rendez-vous.ics" download>Ajouter à mon agenda</a></p>'
                     f'<p class="fine">Fichier .ics, lisible par tous les agendas.</p>')
    answers = data.get("answers") or {}
    if answers:
        labels = {**FIELD_LABELS, "message": data.get("message_label") or "Message"}
        rows = "".join(f"<div><dt>{esc(labels[k])}</dt><dd>{esc(answers[k])}</dd></div>" for k in labels if answers.get(k))
        parts.append(f'<details class="mine" open><summary>Ce que vous avez envoyé</summary><dl>{rows}</dl>'
                     f'<p class="fine">« Effacer mes données » retire aussi la demande ; dans l’agenda de {esc(name)}, il ne reste que '
                     f'« Rendez-vous ».</p></details>')
    actions = []
    if data.get("can_cancel"):
        what = "le rendez-vous" if st == "accepted" else "la demande"
        actions.append(f'<form method="post" action="{here}/annuler" data-confirm="Annuler {what} ? Vos informations seront effacées.">'
                       f'<button class="btn ghost">Annuler {what}</button></form>')
    if answers:
        actions.append(f'<form method="post" action="{here}/effacer" data-confirm="Effacer vos données ? Cette page ne montrera plus rien.">'
                       f'<button class="btn danger">Effacer mes données</button></form>')
    if actions:
        parts.append(f'<div class="two">{"".join(actions)}</div>')
    if st in ("refused", "expired", "cancelled") and data.get("link_path"):
        parts.append(f'<p class="ew-a"><a class="btn ghost" href="{esc(data["link_path"])}">Voir d’autres créneaux</a></p>')
    parts.append(f'<p class="fine">Une question : {contact_line(data.get("contact_email"), base)}.</p>')
    body = f'<main class="pg"><div class="box">{"".join(parts)}</div>{_footer(False)}</main>'
    return _shell(h1.format(name=name), body, nonce, script=STATUS_JS)


# ───────────────────────── Image d'aperçu (1200 × 630, jamais de photo) ─────────────────────────
def preview_png(title: str, name: str | None, link_name: str | None) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1200, 630), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 17, 630), fill="#2C5B4B")

    def font(size: int):
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # Pillow ancien : police fixe
            return ImageFont.load_default()

    def fit(text: str, size: int, width: int) -> tuple[str, Any]:
        f = font(size)
        while draw.textlength(text, font=f) > width and len(text) > 1:
            text = text[:-2] + "…"
        return text, f
    draw.text((96, 90), title, fill="#5A605C", font=font(36))
    if name:
        text, f = fit(name, 96, 1000)
        draw.text((96, 160), text, fill="#141615", font=f)
    if link_name:
        text, f = fit(link_name, 44, 1000)
        draw.text((96, 300), text, fill="#3A3F3C", font=f)
    draw.text((96, 530), "Agenda partagé avec Vendredi Party" if name else "Vendredi Party", fill="#6F7672", font=font(28))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


# ───────────────────────── Routes ─────────────────────────
class BookingBody(BaseModel):
    starts_at: str = Field(min_length=10, max_length=40)
    answers: dict[str, str] = Field(default_factory=dict)
    site: str = Field(default="", max_length=200)       # champ piège : un humain ne le voit pas
    elapsed: int = Field(default=0, ge=0, le=86400)     # secondes passées sur la page avant l'envoi


class ReportBody(BaseModel):
    reason: str = Field(max_length=20)
    comment: str = Field(default="", max_length=500)


class RelayBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    fn: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = Field(default_factory=dict)


class IcsBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    calendar_id: str = Field(pattern=UUID_RE)
    from_ts: str = Field(alias="from", min_length=10, max_length=40)
    to_ts: str = Field(alias="to", min_length=10, max_length=40)


def _headers(nonce: str) -> dict:
    return {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow, noarchive", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                                        "img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; "
                                        "frame-ancestors 'none'"),
            "X-Frame-Options": "DENY"}


def agenda_router(accounts: Accounts, public_url: Callable[[], str], client_ip: Callable[[Request], str]) -> APIRouter:
    db = Db(accounts)
    router = APIRouter()
    ics_cache: dict[str, tuple[float, str]] = {}

    def html_response(page: str, nonce: str, status: int = 200) -> Response:
        return Response(page, status_code=status, media_type="text/html; charset=utf-8", headers=_headers(nonce))

    def gone(nonce: str) -> Response:
        return html_response(gone_page(nonce, public_url()), nonce, 404)

    def plain_headers() -> dict:
        return {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow, noarchive", "Referrer-Policy": "no-referrer"}

    # Suivi de l'inconnu (déclaré avant /d/<jeton>/… : /d/r/… n'est jamais un jeton).
    @router.get("/d/r/{secret}")
    def booking_status(secret: str):
        nonce = secrets.token_urlsafe(12)
        if not SECRET.fullmatch(secret):
            return html_response(gone_page(nonce, public_url(), "Cette demande n’existe plus",
                                           "Elle a été effacée ou le lien est incomplet."), nonce, 404)
        status, data = db.call("agenda_booking_status", {"secret": secret})
        if status == 503 or status >= 500:
            return html_response(gone_page(nonce, public_url(), "Réessayez dans un instant", "Le service ne répond pas."), nonce, 503)
        if not isinstance(data, dict):
            return html_response(gone_page(nonce, public_url(), "Cette demande n’existe plus",
                                           "Elle a été effacée ou le lien est incomplet."), nonce, 404)
        return html_response(status_page(data, secret, public_url(), nonce), nonce)

    def secret_action(secret: str, fn: str) -> Response:
        if SECRET.fullmatch(secret):
            db.call(fn, {"secret": secret})
        return RedirectResponse(f"/d/r/{secret}", status_code=303, headers=plain_headers())

    @router.post("/d/r/{secret}/annuler")
    def booking_cancel(secret: str):
        return secret_action(secret, "agenda_booking_cancel")

    @router.post("/d/r/{secret}/effacer")
    def booking_erase(secret: str):
        return secret_action(secret, "agenda_booking_erase")

    @router.post("/d/r/{secret}/confirmer")
    def booking_confirm(secret: str):
        return secret_action(secret, "agenda_booking_confirm")

    @router.get("/d/r/{secret}/rendez-vous.ics")
    def booking_ics(secret: str):
        status, data = db.call("agenda_booking_status", {"secret": secret}) if SECRET.fullmatch(secret) else (404, None)
        if not isinstance(data, dict) or data.get("status") != "accepted":
            raise HTTPException(404, "Rendez-vous introuvable")
        body = calendar_ics.build(uid=str(uuid.uuid5(uuid.NAMESPACE_URL, secret)), title=f"Rendez-vous avec {data['name']}",
                                  start=data["starts_at"], end=data["ends_at"])
        return Response(body, media_type="text/calendar; charset=utf-8", headers={
            **plain_headers(), "Content-Disposition": 'attachment; filename="rendez-vous.ics"'})

    @router.get("/d/apercu-inactif.png")
    def preview_neutral():
        return Response(preview_png("Lien d’agenda", None, None), media_type="image/png", headers=plain_headers())

    NICE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

    def resolve(handle: str, slug: str) -> str:
        """Jeton d'une adresse lisible active ; « » sinon (page neutre, comme un jeton inconnu)."""
        handle, slug = handle.lower(), slug.lower()
        if not (NICE.fullmatch(handle) and NICE.fullmatch(slug)):
            return ""
        status, data = db.call("agenda_resolve", {"handle": handle, "slug": slug})
        return data if status == 200 and isinstance(data, str) and TOKEN.fullmatch(data) else ""

    @router.get("/agenda/{handle}/{slug}")
    def nice_link(handle: str, slug: str, request: Request):
        return link(resolve(handle, slug), request, f"/agenda/{handle.lower()}/{slug.lower()}")

    @router.get("/agenda/{handle}/{slug}/apercu.png")
    def nice_preview(handle: str, slug: str):
        return link_preview(resolve(handle, slug))

    @router.post("/agenda/{handle}/{slug}/demande")
    def nice_request(handle: str, slug: str, body: BookingBody, request: Request):
        return booking_request(resolve(handle, slug), body, request)

    @router.post("/agenda/{handle}/{slug}/signaler")
    def nice_report(handle: str, slug: str, body: ReportBody, request: Request):
        return report(resolve(handle, slug), body, request)

    @router.get("/d/{token}")
    def token_link(token: str, request: Request):
        return link(token, request)

    def link(token: str, request: Request, path: str | None = None):
        nonce = secrets.token_urlsafe(12)
        if not TOKEN.fullmatch(token):
            return gone(nonce)
        bot = bool(PREVIEW_BOTS.search(request.headers.get("user-agent", "")))
        status, data = db.call("agenda_public_page", {"t": token, "count_view": not bot})
        if status >= 500:
            return html_response(gone_page(nonce, public_url(), "Réessayez dans un instant", "Le service ne répond pas."), nonce, 503)
        if not isinstance(data, dict):
            return gone(nonce)
        return html_response(link_page(data, path or f"/d/{token}", public_url(), nonce), nonce)

    @router.get("/d/{token}/apercu.png")
    def link_preview(token: str):
        data = db.call("agenda_public_page", {"t": token, "count_view": False})[1] if TOKEN.fullmatch(token) else None
        png = (preview_png("Prendre rendez-vous" if data.get("booking") else "Disponibilités", data["name"], data["link_name"])
               if isinstance(data, dict) else preview_png("Lien d’agenda", None, None))
        return Response(png, media_type="image/png", headers={**plain_headers(), "Cache-Control": "public, max-age=300"})

    @router.post("/d/{token}/demande")
    def booking_request(token: str, body: BookingBody, request: Request):
        def fail(code: str, message: str, status: int, field: str | None = None, title: str | None = None):
            return JSONResponse({"code": code, "message": message, "field": field, "title": title}, status_code=status,
                                headers=plain_headers())
        if not TOKEN.fullmatch(token):
            return fail("not_found", "Ce lien n’est plus actif.", 404)
        if body.site.strip() or body.elapsed < MIN_FILL_SECONDS:
            return fail("invalid", "La demande n’est pas partie. Prenez le temps de remplir le formulaire, puis réessayez.", 400)
        status, data = db.call("agenda_booking_request", {
            "t": token, "starts_at": body.starts_at, "ip": client_ip(request) or None,
            "answers": {k: v for k, v in body.answers.items() if k in FIELD_LABELS}})
        if status == 200 and isinstance(data, dict) and data.get("secret"):
            return JSONResponse({"ok": True, "url": f"/d/r/{data['secret']}", "status": data["status"]}, headers=plain_headers())
        code, text = refusal(data)
        if code == "error" or status >= 500:
            return fail("error", "La demande n’est pas partie. Réessayez dans un instant.", 503)
        field = next((k for k, label in FIELD_LABELS.items() if text.startswith(label)), None)
        title = None
        if code == "content_refused":
            title, _, text = text.partition(" : ")
            text = "Il contient " + text.split("il contient ", 1)[-1] if "il contient " in text else text
            page = db.call("agenda_public_page", {"t": token, "count_view": False})[1]
            contact = (page or {}).get("contact_email") if isinstance(page, dict) else None
            name = page.get("name") if isinstance(page, dict) else "la personne"
            text = text.replace("Rien n'a été transmis.", f"Rien n’a été transmis à {name}.") + \
                (f" Une question : {contact}." if contact else "")
        return fail(code, text, ERROR_STATUS.get(code, 400), field, title)

    @router.post("/d/{token}/signaler")
    def report(token: str, body: ReportBody, request: Request):
        if TOKEN.fullmatch(token):
            status, data = db.call("agenda_public_report", {"t": token, "reason": body.reason, "comment": body.comment,
                                                             "ip": client_ip(request) or None})
            code, text = refusal(data)
            if status >= 400 and code in ("rate_limited", "reason"):
                return JSONResponse({"code": code, "message": text}, status_code=ERROR_STATUS[code], headers=plain_headers())
        return JSONResponse({"ok": True, "message": "Merci, votre signalement a été transmis à l’équipe de modération de Vendredi Party."},
                            headers=plain_headers())

    # ── Membres ──
    @router.post("/api/account/agenda/rpc")
    def relay(body: RelayBody):
        if body.fn not in RELAY:
            raise HTTPException(404, "Fonction inconnue")
        status, data = db.call(body.fn, body.args, body.token)
        if status in (200, 204):
            if body.fn == "agenda_badge":  # pastille de l'app iPhone : elle écoute ensuite le signal user:<id>
                return JSONResponse({"result": data, "realtime": {
                    "url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket", "key": SUPABASE_ANON_KEY}})
            return JSONResponse({"result": data})
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        code, text = refusal(data)
        if code == "error":
            raise HTTPException(503 if status >= 500 else 400, "Ça n'a pas marché. Réessaie dans un instant.")
        return JSONResponse({"code": code, "detail": text}, status_code=ERROR_STATUS.get(code, 400))

    @router.post("/api/account/agenda/ics")
    def ics(body: IcsBody):
        status, rows = db.get(f"/rest/v1/agenda_calendars?id=eq.{body.calendar_id}&kind=eq.ics&select=id,ics_url", body.token)
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        if status != 200 or not rows:
            raise HTTPException(404, "Agenda introuvable")
        try:
            f = datetime.fromisoformat(body.from_ts.replace("Z", "+00:00"))
            t = datetime.fromisoformat(body.to_ts.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Dates illisibles") from None
        if f.tzinfo is None or t.tzinfo is None or not timedelta(0) < t - f <= timedelta(days=62):
            raise HTTPException(400, "Période de 62 jours au plus")
        url = rows[0]["ics_url"]
        cache_key = f"{body.calendar_id}:{hash(url)}"
        hit = ics_cache.get(cache_key)
        if hit and time.time() - hit[0] < 600:
            text = hit[1]
        else:
            try:
                text = agenda_ics.fetch(url)
            except agenda_ics.IcsError as e:
                db.call("agenda_calendar_fetched", {"cal": body.calendar_id, "error": str(e)}, body.token)
                return JSONResponse({"error": str(e)}, status_code=502)
            for k in [k for k, v in ics_cache.items() if time.time() - v[0] >= 600]:
                ics_cache.pop(k, None)
            ics_cache[cache_key] = (time.time(), text)
            db.call("agenda_calendar_fetched", {"cal": body.calendar_id, "error": None}, body.token)
        return JSONResponse({"events": agenda_ics.events_between(text, f, t)}, headers={"Cache-Control": "no-store"})

    return router
