"""Campagne 2 des bots (07.11.2026), lot « réponses » : corrections de la migration 20261107110000, sur la VRAIE base
de TEST (jamais la prod). Presque tout se passe dans des transactions ANNULÉES, avec la session des comptes de test
(Testeur 1, Testeur 2, VIP test, Admin test) : aucune ligne ne reste, aucune notification ne part.
Seule la course à la dernière place utilise de vraies transactions simultanées (événement de test supprimé à la fin).
- complet SANS liste d'attente : « Présent » refusé (« C'est complet. »), personne n'est mis en attente ;
- fixer une date quand « Peut-être » est désactivé et que quelqu'un a voté « Si besoin » ; date passée refusée ;
- deux « Présent » simultanés sur la dernière place : une seule personne confirmée (verrou de l'événement) ;
- événement terminé : « Présent » refusé à l'invité, l'organisateur note encore les présences ;
- petit mot pour l'organisateur : lu par la personne et l'organisation seulement, filtré, CGU, signalable ;
- forum : seul l'auteur réécrit son texte, un message supprimé n'a plus de texte, épingler = organisation ;
- sondages et « Qui amène quoi » : filtre, CGU, signalables ; proposer une date passée refusé ;
- pot commun : supprimer l'événement supprime (ou clôt) son pot ; photos de tickets orphelines purgées."""
import json
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
ADMIN = 'a7610087-3f63-43d0-8657-a3459f0fddcb'  # Admin test (41790000004)
T1 = '407eb502-c0b8-45f3-8d3a-be471b72c4b5'     # Testeur 1, CGU acceptées
T2 = 'b539febf-3f90-42b0-ab6b-ed18f3a2380c'     # Testeur 2, sans CGU
VIP = '63364824-6982-4a3c-befc-fb37d204a3e8'    # VIP test (Guest)


def sql_test(query: str) -> str:
    out = subprocess.run(['python3', str(ROOT / 'supabase/tools/sbq.py'), 'test', 'rw'], input=query,
                         capture_output=True, text=True, timeout=180)
    return out.stdout + out.stderr


def as_(uid: str) -> str:
    """Passe à la session de `uid` (rôle authenticated), à l'intérieur du bloc."""
    claims = json.dumps({'sub': uid, 'role': 'authenticated'})
    return f"execute 'reset role'; perform set_config('request.jwt.claims', '{claims}', true); execute 'set local role authenticated';"


SYSTEM = "execute 'reset role'; perform set_config('request.jwt.claims', '', true);"


def attempt(label: str, stmt: str) -> str:
    """Essaie `stmt` : ajoute « label=ok » ou « label=ERR:<message> » au résultat r (sous-transaction)."""
    return f"begin {stmt}; r := r || ' {label}=ok'; exception when others then r := r || ' {label}=ERR:' || sqlerrm; end;"


def event_sql(extra: str = '', start: str = "now() + interval '30 days'", end: str = 'null') -> str:
    """Événement public (lien) de l'Admin test, sans annonce, créé par le système dans la transaction.
    extra : « colonne=valeur; colonne=valeur »."""
    pairs = [p.split('=', 1) for p in extra.split(';') if p.strip()]
    cols = ''.join(f', {k.strip()}' for k, _ in pairs)
    vals = ''.join(f', {v.strip()}' for _, v in pairs)
    return f"""{SYSTEM}
      insert into public.events (title, created_by, status, visibility, public_link, notify_on_publish, starts_at, ends_at{cols})
        values ('Test C2 réponses', '{ADMIN}', 'published', 'all', true, false, {start}, {end}{vals})
        returning id into e;"""


def scenario(body: str, declare: str = '') -> str:
    """Transaction annulée : CGU acceptées pour l'Admin test et Testeur 1 seulement, puis le corps.
    Le corps finit par `raise exception 'résultat:%', r;` (la transaction est de toute façon annulée)."""
    return sql_test(f"""
    begin;
    update private.moderation_settings set terms_enforced = true where id = 1;  -- comme en prod (annulé avec le reste)
    insert into public.terms_acceptances (user_id, version)
      select u, (select terms_version from private.moderation_settings where id = 1) from unnest(array['{ADMIN}', '{T1}']::uuid[]) u
      on conflict do nothing;
    delete from public.terms_acceptances where user_id = '{T2}';
    do $$ declare e uuid; o uuid; x uuid; y uuid; r text := ''; {declare} begin
      {body}
    end $$;
    rollback;""")


# 1. Complet sans liste d'attente ---------------------------------------------------------------------------------

def test_a_full_event_without_waitlist_refuses_present_and_waitlists_nobody():
    out = scenario(f"""{event_sql("max_participants=1; waitlist_enabled=false")}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes');
      {as_(T2)} {attempt('t2', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T2}', 'yes')")}
      {SYSTEM}
      r := r || ' attente=' || (select count(*) from public.rsvps where event_id = e and waitlisted);
      raise exception 'résultat:%', r;""")
    assert "t2=ERR:C'est complet." in out, out
    assert 'attente=0' in out, out


def test_a_full_event_with_waitlist_still_waitlists():
    out = scenario(f"""{event_sql("max_participants=1; waitlist_enabled=true")}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes');
      {as_(T2)} {attempt('t2', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T2}', 'yes')")}
      {SYSTEM}
      r := r || ' attente=' || (select count(*) from public.rsvps where event_id = e and waitlisted);
      raise exception 'résultat:%', r;""")
    assert 't2=ok' in out and 'attente=1' in out, out


# 2. Fixer une date ----------------------------------------------------------------------------------------------

def test_fixing_a_date_with_maybe_disabled_turns_if_needed_votes_into_no_answer():
    out = scenario(f"""{event_sql("date_mode='poll'; allow_maybe=false")}
      insert into public.date_options (event_id, starts_at) values (e, now() + interval '20 days') returning id into o;
      insert into public.date_votes (option_id, user_id, vote) values (o, '{T1}', 'yes'), (o, '{T2}', 'if_needed');
      {as_(ADMIN)} {attempt('fixer', 'perform public.fix_event_date(e, o)')}
      {SYSTEM}
      r := r || ' t1=' || coalesce((select status::text from public.rsvps where event_id = e and user_id = '{T1}'), 'aucune')
             || ' t2=' || coalesce((select status::text from public.rsvps where event_id = e and user_id = '{T2}'), 'aucune')
             || ' mode=' || (select date_mode::text from public.events where id = e);
      raise exception 'résultat:%', r;""")
    assert 'fixer=ok' in out and 't1=yes' in out and 't2=aucune' in out and 'mode=fixed' in out, out


def test_fixing_a_date_without_waitlist_registers_only_what_fits():
    out = scenario(f"""{event_sql("date_mode='poll'; max_participants=1; waitlist_enabled=false")}
      insert into public.date_options (event_id, starts_at) values (e, now() + interval '20 days') returning id into o;
      insert into public.date_votes (option_id, user_id, vote) values (o, '{T1}', 'yes'), (o, '{T2}', 'yes');
      {as_(ADMIN)} {attempt('fixer', 'perform public.fix_event_date(e, o)')}
      {SYSTEM}
      r := r || ' presents=' || (select count(*) from public.rsvps where event_id = e and status = 'yes' and not waitlisted)
             || ' attente=' || (select count(*) from public.rsvps where event_id = e and waitlisted);
      raise exception 'résultat:%', r;""")
    assert 'fixer=ok' in out and 'presents=1' in out and 'attente=0' in out, out


def test_a_past_date_can_be_neither_proposed_nor_fixed():
    out = scenario(f"""{event_sql("date_mode='poll'; members_can_propose_dates=true")}
      insert into public.date_options (event_id, starts_at) values (e, now() + interval '20 days') returning id into o;
      {as_(T1)} {attempt('proposer', f"insert into public.date_options (event_id, starts_at, proposed_by) values (e, now() - interval '3 days', '{T1}')")}
      {attempt('proposer_futur', f"insert into public.date_options (event_id, starts_at, proposed_by) values (e, now() + interval '9 days', '{T1}')")}
      {SYSTEM} update public.date_options set starts_at = now() - interval '1 day' where id = o;
      {as_(ADMIN)} {attempt('fixer', 'perform public.fix_event_date(e, o)')}
      raise exception 'résultat:%', r;""")
    assert 'proposer=ERR:Cette date est déjà passée' in out, out
    assert 'proposer_futur=ok' in out, out
    assert 'fixer=ERR:Cette date est déjà passée' in out, out


# 3. Course à la dernière place (vraies transactions simultanées) ------------------------------------------------

def test_two_simultaneous_present_on_the_last_seat_confirm_only_one():
    title = f'Test C2 course {uuid.uuid4().hex[:6]}'
    created = sql_test(f"""
      insert into public.events (title, created_by, status, visibility, public_link, notify_on_publish, starts_at, max_participants, waitlist_enabled)
      values ('{title}', '{ADMIN}', 'published', 'all', true, false, now() + interval '30 days', 1, true) returning id;""")
    event = json.loads(created)[0]['id']
    try:
        def answer(uid: str) -> str:
            claims = json.dumps({'sub': uid, 'role': 'authenticated'})
            # pg_sleep après l'insertion : sans verrou, les deux transactions se voient « une place libre ».
            return sql_test(f"""begin; set local role authenticated; set local request.jwt.claims = '{claims}';
              insert into public.rsvps (event_id, user_id, status) values ('{event}', '{uid}', 'yes');
              select pg_sleep(3); commit;""")
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(answer, [T1, T2, VIP]))
        counts = json.loads(sql_test(f"""select count(*) filter (where status = 'yes' and not waitlisted) as confirmes,
              count(*) filter (where waitlisted) as attente from public.rsvps where event_id = '{event}';"""))[0]
        assert counts == {'confirmes': 1, 'attente': 2}, counts
    finally:
        sql_test(f"delete from public.events where id = '{event}';")


# 4. Événement terminé --------------------------------------------------------------------------------------------

def test_a_finished_event_refuses_present_but_the_organizer_can_still_note_attendance():
    out = scenario(f"""{event_sql(start="now() - interval '2 days'", end="now() - interval '2 days' + interval '4 hours'")}
      {as_(T1)} {attempt('invite', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes')")}
      {as_(ADMIN)} {attempt('orga', f"perform public.set_rsvp_for(e, '{T2}', 'yes')")}
      raise exception 'résultat:%', r;""")
    assert 'invite=ERR:Cet événement est terminé' in out, out
    assert 'orga=ok' in out, out


def test_an_event_is_finished_six_hours_after_its_end_or_start_like_the_screen():
    """Même règle que web/events/src/lib/eventTime.ts (eventEnded) : fin (ou début sans fin) + 6 h."""
    out = scenario(f"""{event_sql(start="now() - interval '7 hours'")}
      {as_(T1)} {attempt('debut7h', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes')")}
      {SYSTEM} update public.events set starts_at = now() - interval '8 hours', ends_at = now() - interval '5 hours' where id = e;
      {as_(T1)} {attempt('fin5h', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes')")}
      raise exception 'résultat:%', r;""")
    assert 'debut7h=ERR:Cet événement est terminé' in out and 'fin5h=ok' in out, out


# 5. Petit mot pour l'organisateur --------------------------------------------------------------------------------

def test_the_note_is_read_only_by_its_author_and_the_organizers():
    out = scenario(f"""{event_sql("show_participants=true")}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 'Allergique aux noix');
      r := r || ' moi=' || coalesce((select note from public.rsvp_notes where event_id = e and user_id = '{T1}'), 'rien');
      {as_(VIP)} insert into public.rsvps (event_id, user_id, status) values (e, '{VIP}', 'yes');
      r := r || ' autre=' || (select count(*) from public.rsvp_notes where event_id = e)
             || ' colonne=' || coalesce((select note from public.rsvps where event_id = e and user_id = '{T1}'), 'vide');
      {as_(ADMIN)} r := r || ' orga=' || coalesce((select note from public.rsvp_notes where event_id = e and user_id = '{T1}'), 'rien');
      {as_(T1)} update public.rsvps set note = '' where event_id = e and user_id = '{T1}';
      r := r || ' efface=' || (select count(*) from public.rsvp_notes where event_id = e);
      raise exception 'résultat:%', r;""")
    assert 'moi=Allergique aux noix' in out, out
    assert 'autre=0' in out and 'colonne=vide' in out, out
    assert 'orga=Allergique aux noix' in out, out
    assert 'efface=0' in out, out


def test_a_status_change_does_not_erase_the_note():
    out = scenario(f"""{event_sql()}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 'Je viens tard');
      update public.rsvps set status = 'no', note = null where event_id = e and user_id = '{T1}';
      r := r || ' mot=' || coalesce((select note from public.rsvp_notes where event_id = e), 'rien');
      raise exception 'résultat:%', r;""")
    assert 'mot=Je viens tard' in out, out


def test_the_note_is_filtered_needs_the_terms_and_can_be_reported():
    out = scenario(f"""{event_sql()}
      {as_(T1)} {attempt('haine', f"insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 'Coucou sale arabe')")}
      insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 't''es un connard');
      r := r || ' masque=' || (select note from public.rsvp_notes where event_id = e and user_id = '{T1}');
      {as_(T2)} {attempt('sans_cgu', f"insert into public.rsvps (event_id, user_id, status, note) values (e, '{T2}', 'yes', 'Bonjour')")}
      {attempt('sans_cgu_sans_mot', f"insert into public.rsvps (event_id, user_id, status) values (e, '{T2}', 'yes')")}
      {as_(ADMIN)} {attempt('signaler', "perform public.report_content('rsvp_note', (select id::text from public.rsvp_notes where event_id = e), 'harassment', null)")}
      {SYSTEM} r := r || ' type=' || coalesce((select target_kind || ':' || (snapshot ->> 'text') from public.content_reports
                                            where target_kind = 'rsvp_note' and reporter_id = '{ADMIN}' order by created_at desc limit 1), 'aucun');
      raise exception 'résultat:%', r;""")
    assert 'haine=ERR:content_refused' in out, out
    assert "masque=t'es un •••••••" in out, out
    assert 'sans_cgu=ERR:terms_required' in out and 'sans_cgu_sans_mot=ok' in out, out
    assert 'signaler=ok' in out and "type=rsvp_note:t'es un •••••••" in out, out


def test_a_guest_cannot_report_a_note_he_cannot_read():
    out = scenario(f"""{event_sql()}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 'Mot privé');
      {SYSTEM} x := (select id from public.rsvp_notes where event_id = e);
      {as_(VIP)} {attempt('signaler', "perform public.report_content('rsvp_note', x::text, 'spam', null)")}
      raise exception 'résultat:%', r;""")
    assert 'signaler=ERR:not_found' in out, out


# 6. Forum --------------------------------------------------------------------------------------------------------

def test_only_the_author_rewrites_a_message_deleted_text_is_erased_and_pinning_is_for_organizers():
    out = scenario(f"""{event_sql("forum_enabled=true")}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes');
      insert into public.messages (event_id, user_id, body) values (e, '{T1}', 'Message de Testeur 1') returning id into x;
      {attempt('epingle_invite', 'update public.messages set pinned = true where id = x')}
      {attempt('auteur_modifie', "update public.messages set body = 'Message corrigé', edited_at = now() where id = x")}
      {as_(ADMIN)} {attempt('orga_reecrit', "update public.messages set body = 'Réécrit par l''orga' where id = x")}
      {attempt('orga_epingle', 'update public.messages set pinned = true where id = x')}
      {as_(T1)} update public.messages set deleted_at = now() where id = x;
      {as_(VIP)} r := r || ' texte=' || (select body from public.messages where id = x);
      raise exception 'résultat:%', r;""")
    assert 'epingle_invite=ERR:' in out, out
    assert 'auteur_modifie=ok' in out, out
    assert 'orga_reecrit=ERR:Seul l' in out, out
    assert 'orga_epingle=ok' in out, out
    assert 'texte=•' in out and 'corrigé' not in out.split('texte=')[1], out


def test_a_guest_inserting_a_pinned_message_is_not_pinned():
    out = scenario(f"""{event_sql("forum_enabled=true")}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes');
      insert into public.messages (event_id, user_id, body, pinned) values (e, '{T1}', 'Épinglé ?', true) returning id into x;
      r := r || ' epingle=' || (select pinned from public.messages where id = x);
      raise exception 'résultat:%', r;""")
    assert 'epingle=false' in out, out


# 7. Sondages et « Qui amène quoi » -------------------------------------------------------------------------------

def test_poll_texts_and_bring_items_are_filtered_need_the_terms_and_can_be_reported():
    out = scenario(f"""{event_sql()}
      {as_(ADMIN)} {attempt('question_haine', "insert into public.polls (event_id, question, created_by) values (e, 'Sale arabe ?', auth.uid())")}
      insert into public.polls (event_id, question, created_by, members_can_add_options) values (e, 'Quel apéro ?', auth.uid(), true) returning id into x;
      {as_(T1)} insert into public.rsvps (event_id, user_id, status) values (e, '{T1}', 'yes');
      {attempt('option_haine', f"insert into public.poll_options (poll_id, label, created_by) values (x, 'sale arabe', '{T1}')")}
      insert into public.poll_options (poll_id, label, created_by) values (x, 'Bière connard', '{T1}') returning id into y;
      r := r || ' option=' || (select label from public.poll_options where id = y);
      {attempt('objet_haine', f"insert into public.bring_items (event_id, label, added_by, claimed_by) values (e, 'sale arabe', '{T1}', '{T1}')")}
      insert into public.bring_items (event_id, label, added_by, claimed_by) values (e, 'Chips', '{T1}', '{T1}') returning id into o;
      {as_(T2)} insert into public.rsvps (event_id, user_id, status) values (e, '{T2}', 'yes');
      {attempt('option_sans_cgu', f"insert into public.poll_options (poll_id, label, created_by) values (x, 'Vin', '{T2}')")}
      {attempt('objet_sans_cgu', f"insert into public.bring_items (event_id, label, added_by, claimed_by) values (e, 'Pain', '{T2}', '{T2}')")}
      {attempt('signaler_objet', "perform public.report_content('bring_item', o::text, 'spam', null)")}
      {attempt('signaler_option', "perform public.report_content('poll_option', y::text, 'harassment', null)")}
      {attempt('signaler_sondage', "perform public.report_content('poll', x::text, 'other', null)")}
      raise exception 'résultat:%', r;""")
    assert 'question_haine=ERR:content_refused' in out, out
    assert 'option_haine=ERR:content_refused' in out and 'option=Bière •••••••' in out, out
    assert 'objet_haine=ERR:content_refused' in out, out
    assert 'option_sans_cgu=ERR:terms_required' in out and 'objet_sans_cgu=ERR:terms_required' in out, out
    assert 'signaler_objet=ok' in out and 'signaler_option=ok' in out and 'signaler_sondage=ok' in out, out


def test_a_moderator_hides_a_reported_note_option_and_item():
    out = scenario(f"""{event_sql()}
      {as_(T1)} insert into public.rsvps (event_id, user_id, status, note) values (e, '{T1}', 'yes', 'Mot à masquer');
      insert into public.bring_items (event_id, label, added_by, claimed_by) values (e, 'Objet à masquer', '{T1}', '{T1}') returning id into o;
      {as_(ADMIN)} insert into public.polls (event_id, question, created_by, members_can_add_options) values (e, 'Question ?', auth.uid(), true) returning id into x;
      {as_(T1)} insert into public.poll_options (poll_id, label, created_by) values (x, 'Option à masquer', '{T1}') returning id into y;
      {as_(ADMIN)} x2 := (select id from public.rsvp_notes where event_id = e);
      perform public.report_content('rsvp_note', x2::text, 'spam', null);
      perform public.report_content('bring_item', o::text, 'spam', null);
      perform public.report_content('poll_option', y::text, 'spam', null);
      {SYSTEM} perform set_config('request.jwt.claims', '{json.dumps({'sub': ADMIN, 'role': 'authenticated'})}', true);
      perform private.moderation_hide(c) from public.content_reports c
        where c.reporter_id = '{ADMIN}' and c.status = 'open' and c.target_id in (x2::text, o::text, y::text);
      perform private.moderation_hide(row(gen_random_uuid(), '{ADMIN}', 'poll', x::text, '{ADMIN}', 'spam', null, '{{}}'::jsonb,
                                          'open', null, null, null, null, now())::public.content_reports);
      r := r || ' mots=' || (select count(*) from public.rsvp_notes where event_id = e)
             || ' objets=' || (select count(*) from public.bring_items where id = o)
             || ' options=' || (select count(*) from public.poll_options where id = y)
             || ' question=' || (select question from public.polls where id = x);
      raise exception 'résultat:%', r;""", declare='x2 uuid;')
    assert 'mots=0' in out and 'objets=0' in out and 'options=0' in out, out
    assert 'question=Question masquée par la modération' in out, out


# 8. Pot commun -----------------------------------------------------------------------------------------------------

def test_deleting_an_event_deletes_its_empty_pot_and_closes_a_pot_with_expenses():
    out = scenario(f"""{event_sql("pot_enabled=true")}
      x := (select id from public.tc_groups where event_id = e);
      delete from public.events where id = e;
      {event_sql("pot_enabled=true")}
      y := (select id from public.tc_groups where event_id = e);
      insert into public.tc_expenses (group_id, title, amount_cents, paid_by)
        values (y, 'Courses', 1200, (select id from public.tc_members where group_id = y limit 1));
      delete from public.events where id = e;
      r := r || ' vide=' || (select count(*) from public.tc_groups where id = x)
             || ' plein=' || coalesce((select archived::text from public.tc_groups where id = y), 'supprime');
      raise exception 'résultat:%', r;""")
    assert 'vide=0' in out and 'plein=true' in out, out


def test_receipts_of_deleted_expenses_and_deleted_accounts_are_orphans_to_purge():
    out = scenario(f"""{event_sql("pot_enabled=true")}
      y := (select id from public.tc_groups where event_id = e);
      insert into public.tc_expenses (group_id, title, amount_cents, paid_by, receipt_path, created_by)
        values (y, 'Courses', 1200, (select id from public.tc_members where group_id = y limit 1), y || '/ticket.jpg', '{ADMIN}');
      perform private.tc_forget_receipts('{ADMIN}');
      r := r || ' chemin=' || coalesce((select receipt_path from public.tc_expenses where group_id = y), 'efface')
             || ' purge=' || (select count(*) from pg_proc where proname = 'tc_purge_receipts')
             || ' job=' || (select count(*) from cron.job where jobname = 'tc-receipts-purge')
             || ' declencheur=' || (select count(*) from pg_trigger where tgname = 'tc_forget_receipts' and tgrelid = 'auth.users'::regclass);
      raise exception 'résultat:%', r;""")
    assert 'chemin=efface' in out and 'purge=1' in out and 'job=1' in out and 'declencheur=1' in out, out
