"""Quarantaine des notifications pendant une campagne de bots (base de TEST seulement).

La base de TEST contient de vrais bêta-testeurs avec leur iPhone (jetons push). Un bot qui signale un événement, écrit
dans un forum, publie un événement public… préviendrait l'admin ou les membres réels. Pendant la campagne, un trigger
supprime toute notification destinée à un compte qui n'est pas un bot lorsqu'elle est causée par un bot (auteur de la
requête = bot, ou événement créé par un bot). Les notifications entre bots passent normalement. Retiré à la fin.
Les notifications ainsi retenues sont comptées dans private.bots_quarantine_log (preuve pour le rapport)."""
from __future__ import annotations

from tests.bots.common import phones_sql, sql

INSTALL = f"""
create table if not exists private.bots_quarantine_log (at timestamptz default now(), user_id uuid, kind text, event_id uuid);
create or replace function private.bots_quarantine() returns trigger language plpgsql security definer set search_path = '' as $$
declare bots uuid[];
begin
  select coalesce(array_agg(id), '{{}}') into bots from public.profiles where phone in {phones_sql()};
  if new.user_id = any (bots) then return new; end if;
  if auth.uid() = any (bots)
     or exists (select 1 from public.events e where e.id = new.event_id and e.created_by = any (bots)) then
    insert into private.bots_quarantine_log (user_id, kind, event_id) values (new.user_id, new.kind, new.event_id);
    return null;
  end if;
  return new;
end $$;
drop trigger if exists zz_bots_quarantine on public.notifications;
create trigger zz_bots_quarantine before insert on public.notifications for each row execute function private.bots_quarantine();
"""

REMOVE = """
drop trigger if exists zz_bots_quarantine on public.notifications;
drop function if exists private.bots_quarantine();
drop table if exists private.bots_quarantine_log;
"""


def install() -> None:
    sql(INSTALL)


def remove() -> None:
    sql(REMOVE)


def held() -> list:
    return sql("select kind, count(*) n from private.bots_quarantine_log group by 1 order by 2 desc") or []


def leaked_since(started_at: str) -> list:
    """Notifications reçues par un compte non-bot pour un événement de bot depuis le début (doit être vide)."""
    return sql(f"""select n.kind, n.user_id from public.notifications n join public.events e on e.id = n.event_id
                   join public.profiles p on p.id = e.created_by
                   where p.phone in {phones_sql()} and n.created_at >= '{started_at}'
                     and n.user_id not in (select id from public.profiles where phone in {phones_sql()})""") or []
