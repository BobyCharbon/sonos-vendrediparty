-- L'admin principal ne peut pas être retiré sans successeur actif.
create or replace function private.protect_last_admin() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.role='admin' and old.status='active' and (new.role<>'admin' or new.status<>'active') then
    lock table public.profiles in share row exclusive mode;
    if not exists(select 1 from public.profiles where id<>old.id and role='admin' and status='active') then
      raise exception 'last_admin: désigne un autre administrateur actif avant de retirer cet accès';
    end if;
  end if;
  return new;
end;
$$;
revoke all on function private.protect_last_admin() from public, anon, authenticated;
create trigger profiles_last_admin before update of role,status on public.profiles
  for each row execute function private.protect_last_admin();

-- La fonction Edge est maintenant déployée et assure sa propre authentification.
select cron.schedule('send-push','* * * * *','select private.dispatch_push_job();');
