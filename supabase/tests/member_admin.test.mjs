// Migration « Membres » (Root et admins) : journal en ajout seul, liste complète, suppression d'un compte.
// Vrai Postgres local (PGlite) sur un schéma Supabase minimal simulé : `cd supabase/tests && npm ci && npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { PGlite } from '@electric-sql/pglite';

const here = new URL('.', import.meta.url);
const stub = readFileSync(new URL('supabase_stub.sql', here), 'utf8');
const migration = readFileSync(new URL('../migrations/20261025120000_member_admin_and_audit.sql', here), 'utf8');

const ROOT = '00000000-0000-0000-0000-000000000099';
const ADMIN = '00000000-0000-0000-0000-000000000004';
const ADMIN2 = '00000000-0000-0000-0000-000000000044';
const VIP = '00000000-0000-0000-0000-000000000001';
const GUEST = '00000000-0000-0000-0000-000000000000';

async function fresh() {
  const db = new PGlite();
  await db.exec(stub);
  await db.exec(migration);
  await db.exec(migration);  // rejouable : une deuxième application ne casse rien
  for (const [id, name, role, phone] of [[ROOT, 'Boby', 'admin', '+41790000099'], [ADMIN, 'Alex', 'admin', '+41790000004'],
    [ADMIN2, 'Sam', 'admin', '+41790000044'], [VIP, 'Léa', 'member', '+41790000001'], [GUEST, 'Tom', 'guest', '+41790000000']]) {
    await db.query('insert into auth.users (id, phone) values ($1, $2)', [id, phone]);
    await db.query('insert into public.profiles (id, display_name, role, phone) values ($1, $2, $3, $4)', [id, name, role, phone]);
  }
  return db;
}

// Requête faite par l'app : rôle « authenticated » avec le compte donné (comme un jeton Supabase).
async function as(db, uid, sql, params = []) {
  await db.exec(`set role authenticated; select set_config('request.jwt.claim.sub', '${uid}', false);`);
  try { return await db.query(sql, params); } finally { await db.exec('reset role;'); }
}
async function asSystem(db, uid) { await db.exec(`select set_config('request.jwt.claim.sub', '${uid}', false);`); }
const actions = async (db) => (await db.query('select action, actor, target, target_name, details from public.member_audit order by id')).rows;

test('chaque inscription, rôle, accès, bêta et groupe laisse une trace', async () => {
  const db = await fresh();
  await asSystem(db, ROOT);
  await db.query("update public.profiles set role = 'member' where id = $1", [GUEST]);
  await db.query("update public.profiles set status = 'banned' where id = $1", [GUEST]);
  await db.query('insert into public.beta_testers (user_id) values ($1)', [VIP]);
  await db.query('delete from public.beta_testers where user_id = $1', [VIP]);
  const g = (await db.query("insert into public.member_groups (name) values ('Vendredi Party') returning id")).rows[0].id;
  await db.query('insert into public.member_group_members values ($1, $2)', [g, VIP]);
  await db.query('delete from public.member_group_members where user_id = $1', [VIP]);
  await db.query("update public.profiles set display_name = 'Lé' where id = $1", [VIP]);  // le surnom seul : pas de trace
  const rows = await actions(db);
  assert.equal(rows.filter((r) => r.action === 'account.created').length, 5);
  const after = rows.filter((r) => r.action !== 'account.created');
  assert.deepEqual(after.map((r) => r.action), ['member.role', 'member.status', 'member.beta', 'member.beta', 'group.add', 'group.remove']);
  assert.deepEqual(after[0].details, { from: 'guest', to: 'member' });
  assert.equal(after[0].actor, ROOT);
  assert.equal(after[0].target_name, 'Tom');
  assert.deepEqual(after[2].details, { enabled: true });
  assert.deepEqual(after[4].details, { group: 'Vendredi Party' });
});

test('une connexion SMS (nouvelle session) est journalisée avec l’appareil', async () => {
  const db = await fresh();
  await db.query("insert into auth.sessions (user_id, user_agent) values ($1, 'iPhone Safari')", [GUEST]);
  const login = (await actions(db)).find((r) => r.action === 'account.login');
  assert.equal(login.target, GUEST);
  assert.deepEqual(login.details, { device: 'iPhone Safari' });
});

test('personne ne peut écrire, modifier, effacer ni lire le journal en direct depuis l’app', async () => {
  const db = await fresh();
  for (const sql of ["insert into public.member_audit (action) values ('faux')", "update public.member_audit set action = 'x'",
    'delete from public.member_audit', 'select * from public.member_audit']) {
    await assert.rejects(as(db, ROOT, sql), /permission denied/);
  }
  await assert.rejects(as(db, ROOT, "select private.audit('faux', null, null)"), /permission denied/);
});

test('la liste complète est réservée à Root et aux admins, et sa consultation est journalisée', async () => {
  const db = await fresh();
  await assert.rejects(as(db, VIP, 'select * from public.admin_member_list()'), /Accès admin requis/);
  await assert.rejects(as(db, GUEST, 'select * from public.admin_member_audit()'), /Accès admin requis/);
  await db.query('insert into public.beta_testers (user_id) values ($1)', [GUEST]);
  const list = (await as(db, ADMIN, 'select * from public.admin_member_list()')).rows;
  assert.equal(list.length, 5);
  const tom = list.find((p) => p.id === GUEST);
  assert.equal(tom.phone, '+41790000000');
  assert.equal(tom.beta, true);
  await as(db, ADMIN, 'select * from public.admin_member_list()');  // relu tout de suite : une seule trace
  const viewed = (await actions(db)).filter((r) => r.action === 'members.viewed');
  assert.equal(viewed.length, 1);
  assert.equal(viewed[0].actor, ADMIN);
  const mine = (await as(db, ROOT, 'select action from public.admin_member_audit($1)', [GUEST])).rows.map((r) => r.action);
  assert.deepEqual(mine, ['member.beta', 'account.created']);  // le plus récent d'abord
});

test('Root supprime un admin ; un admin ne supprime ni un autre admin, ni Root, ni lui-même', async () => {
  const db = await fresh();
  await db.query('insert into public.messages (author, mentions) values ($1, $2)', [VIP, [ADMIN2, VIP]]);
  await assert.rejects(as(db, VIP, 'select public.admin_delete_member($1, $2)', [GUEST, 'Tom']), /Accès admin requis/);
  await assert.rejects(as(db, ADMIN, 'select public.admin_delete_member($1, $2)', [ADMIN2, 'Sam']), /forbidden/);
  await assert.rejects(as(db, ADMIN, 'select public.admin_delete_member($1, $2)', [ROOT, 'Boby']), /forbidden/);
  await assert.rejects(as(db, ADMIN, 'select public.admin_delete_member($1, $2)', [ADMIN, 'Alex']), /self/);
  await assert.rejects(as(db, ROOT, 'select public.admin_delete_member($1, $2)', [ADMIN2, 'Pas lui']), /confirm/);
  await as(db, ROOT, 'select public.admin_delete_member($1, $2)', [ADMIN2, '  sam ']);  // casse et espaces ignorés
  assert.equal((await db.query('select 1 from auth.users where id = $1', [ADMIN2])).rows.length, 0);
  assert.equal((await db.query('select 1 from public.profiles where id = $1', [ADMIN2])).rows.length, 0);
  assert.deepEqual((await db.query('select mentions from public.messages')).rows[0].mentions, [VIP]);
  const gone = (await actions(db)).find((r) => r.action === 'account.deleted');
  assert.equal(gone.actor, ROOT);
  assert.equal(gone.target_name, 'Sam');
  assert.deepEqual(gone.details, { by: 'admin', phone_end: '44' });  // jamais le numéro complet
  await as(db, ADMIN, 'select public.admin_delete_member($1, $2)', [GUEST, 'Tom']);  // un admin supprime un Guest
  assert.equal((await db.query('select 1 from public.profiles where id = $1', [GUEST])).rows.length, 0);
});

test('une suppression par la personne elle-même est notée « self »', async () => {
  const db = await fresh();
  await asSystem(db, VIP);
  await db.query('delete from auth.users where id = $1', [VIP]);
  const gone = (await actions(db)).find((r) => r.action === 'account.deleted');
  assert.equal(gone.details.by, 'self');
  assert.equal(gone.target_name, 'Léa');
});
