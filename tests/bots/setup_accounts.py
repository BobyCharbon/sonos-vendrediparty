"""Prépare les 15 bots sur la base de TEST (jamais la prod) : numéros à code fixe, comptes, rôles, photos, groupes
« Bots » et « Bots 2 », comptes « sans l'app » remis à zéro, CGU non acceptées (la campagne les fait accepter).

Relançable : ne touche qu'aux comptes dont le numéro est dans BOTS ; les entrées sms_test_otp existantes sont gardées.
Usage : .venv/bin/python -m tests.bots.setup_accounts"""
from __future__ import annotations

import struct
import time
import zlib

import httpx

from tests.bots.common import (BOTS, GROUP_BOTS, GROUP_BOTS_2, OTP, TEST_URL, Session, auth_config, patch_auth_config,
                               phones_sql, q, sql)


def _png(rgb: tuple[int, int, int], size: int = 64) -> bytes:
    """Petit carré de couleur (photo de profil exigée pour Membre VIP et plus)."""
    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def ensure_test_numbers() -> None:
    config = auth_config()
    current = config.get("sms_test_otp") or ""
    entries = [e for e in current.split(",") if e]
    known = {e.split("=")[0] for e in entries}
    missing = [f"{b.phone}={OTP}" for b in BOTS if b.phone not in known]
    if missing:
        patch_auth_config({"sms_test_otp": ",".join(entries + missing),
                           "sms_test_otp_valid_until": config.get("sms_test_otp_valid_until") or "2027-10-25T00:00:00+00:00"})
    print(f"Numéros de test : {len(missing)} ajouté(s), {len(entries)} existant(s) gardé(s)")


def reset_no_app_bots() -> None:
    """Les bots « sans l'app » n'ont pas de compte au départ : ils le créent en arrivant par un lien."""
    phones = "(" + ",".join(q(b.phone) for b in BOTS if not b.has_account_at_start) + ")"
    sql(f"delete from auth.users where phone in {phones}")


def prepare_account(bot, color: tuple[int, int, int]) -> str:
    s = Session(bot.phone)
    # Nouveau fichier à chaque passage : aucune règle « update » sur profile-photos (un upsert d'un fichier existant
    # est refusé, banc relancé le 06.11).
    path = f"{s.uid}/bot-avatar-{time.time_ns()}.png"
    up = httpx.post(f"{TEST_URL}/storage/v1/object/profile-photos/{path}", content=_png(color),
                    headers={**s.headers, "Content-Type": "image/png"}, timeout=30)
    if up.status_code not in (200, 201):
        raise RuntimeError(f"Photo de {bot.nickname} : {up.status_code} {up.text}")
    sql(f"""update public.profiles set display_name = {q(bot.nickname)}, first_name = {q(bot.first)},
            last_name = {q(bot.last)}, avatar_url = {q(path)}, status = 'active' where id = {q(s.uid)};
            update public.profiles set role = {q(bot.role)} where id = {q(s.uid)};""")
    return s.uid


def ensure_groups(uids: dict[str, str]) -> None:
    owner = uids["admin"]
    for name in (GROUP_BOTS, GROUP_BOTS_2):
        sql(f"""insert into public.member_groups (name, created_by)
                select {q(name)}, {q(owner)} where not exists (select 1 from public.member_groups where name = {q(name)})""")
        wanted = [uids[b.key] for b in BOTS if name in b.groups and b.key in uids]
        ids = "(" + ",".join(q(u) for u in wanted) + ")"
        sql(f"""delete from public.member_group_members m using public.member_groups g
                where g.id = m.group_id and g.name = {q(name)} and m.user_id not in {ids};
                insert into public.member_group_members (group_id, user_id)
                select g.id, u::uuid from public.member_groups g, unnest(array[{','.join(q(u) for u in wanted)}]) u
                where g.name = {q(name)} on conflict do nothing""")


def reset_terms() -> None:
    sql(f"""delete from public.terms_acceptances t using public.profiles p
            where p.id = t.user_id and p.phone in {phones_sql()}""")


def main() -> dict[str, str]:
    ensure_test_numbers()
    reset_no_app_bots()
    uids = {}
    for i, bot in enumerate(b for b in BOTS if b.has_account_at_start):
        uids[bot.key] = prepare_account(bot, ((40 + i * 37) % 255, (200 - i * 23) % 255, (90 + i * 51) % 255))
        print(f"{bot.nickname:16} {bot.role:10} {uids[bot.key]}")
    ensure_groups(uids)
    reset_terms()
    return uids


if __name__ == "__main__":
    main()
