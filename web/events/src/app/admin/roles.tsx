import { Redirect } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Button, Card, Chip, ConfirmButton, ErrorText, Field, Screen, s, Section, T, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { moveRole, ROLE_COLORS, roleBook, roleError, type Role } from '@/lib/roles';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { Permission } from '@/lib/types';

type RoleRow = Role & { members: number | null };
type Draft = { label: string; color: string | null; icon: string };

/**
 * Rôles et droits : la liste des rôles (du plus haut au plus bas : l'ordre est la hiérarchie), créer, renommer,
 * changer couleur et icône, monter / descendre, supprimer (en réaffectant ses comptes), puis cocher les droits.
 * Toujours seulement les rôles en dessous du sien ; on ne donne que les droits qu'on a soi-même (la base vérifie).
 */
export default function Roles() {
  const { can, rank, perms: mine, refreshProfile } = useAuth();
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const busy = useRef(false);
  const { data, reload } = useQuery(async () => {
    const [catalog, grants, roles, overview] = await Promise.all([
      supabase.from('permissions').select('*').order('sort'),
      supabase.from('role_permissions').select('role, perm'),
      supabase.from('roles').select('key, label, color, icon, rank, builtin').order('rank'),
      supabase.rpc('roles_overview'),
    ]);
    const counts = new Map(((overview.data as { key: string; members: number }[] | null) ?? []).map((r) => [r.key, r.members]));
    // Base sans la table des rôles : anciens rôles figés, seuls les droits se règlent.
    const rows = roles.error ? [] : ((roles.data as Role[] | null) ?? []);
    const book: RoleRow[] = rows.length
      ? rows.map((r) => ({ ...r, members: counts.get(r.key) ?? null }))
      : roleBook().map((r) => ({ ...r, members: null }));  // anciens rôles figés (lib/roles)
    return {
      catalog: must(catalog) as Permission[],
      grants: must(grants) as { role: string; perm: string }[],
      book,
      manage: rows.length > 0,
    };
  }, []);

  if (!(can('roles.manage') || rank >= 99)) return <Redirect href="/" />;

  const book = data?.book ?? [];
  const ascending = book.map((r) => r.key);
  const editable = book.filter((r) => r.rank < rank);
  const current = editable.find((r) => r.key === selected) ?? editable.find((r) => r.key === 'member') ?? editable.at(-1);

  async function run(key: string, operation: () => PromiseLike<{ error: { message: string } | null }>, after?: () => void) {
    if (busy.current) return;
    busy.current = true;
    setSaving(key);
    setError(null);
    try {
      const { error: failed } = await operation();
      if (failed) throw failed;
      after?.();
      await Promise.all([reload(), refreshProfile()]);  // noms et rangs partout dans l'app
    } catch (e) {
      setError(roleError(e && typeof e === 'object' && 'message' in e ? String(e.message) : String(e)));
    } finally {
      busy.current = false;
      setSaving(null);
    }
  }

  const move = (key: string, step: 1 | -1) => {
    const order = moveRole(ascending, key, step, rank);
    if (order) void run(`move.${key}`, () => supabase.rpc('reorder_roles', { role_keys: order }));
  };
  const granted = (role: string, perm: string) => !!data?.grants.some((g) => g.role === role && g.perm === perm);
  const groups = [...new Set((data?.catalog ?? []).map((p) => p.grp))];

  return (
    <Screen edges={[]}>
      <T muted size={14}>
        Du plus haut au plus bas : l’ordre est la hiérarchie. Tu gères les rôles en dessous du tien
        {rank >= 99 ? ' (en tant que root, tous sauf Admin, qui reste en haut).' : ', et tu ne donnes que les droits que tu as toi-même.'}
      </T>
      <ErrorText error={error} />

      <Section title="Rôles" right={data?.manage && !creating ? <Button small variant="secondary" label="+ Nouveau rôle" onPress={() => setCreating(true)} /> : undefined}>
        {creating && data ? (
          <NewRole
            roles={editable}
            busy={saving === 'create'}
            onCancel={() => setCreating(false)}
            onCreate={(draft, copyFrom) => run('create', () => supabase.rpc('create_role', {
              role_label: draft.label, role_color: draft.color, role_icon: draft.icon.trim() || null, copy_from: copyFrom,
            }), () => setCreating(false))}
          />
        ) : null}
        {[...book].reverse().map((r) => {
          const canEdit = r.rank < rank;
          const up = data?.manage ? moveRole(ascending, r.key, 1, rank) : null;
          const down = data?.manage ? moveRole(ascending, r.key, -1, rank) : null;
          return (
            <View key={r.key} style={[st.row, current?.key === r.key && st.current]}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${r.label}${r.members != null ? `, ${r.members} compte(s)` : ''}${canEdit ? '' : ', au-dessus de toi'}`}
                accessibilityState={{ selected: current?.key === r.key, disabled: !canEdit }}
                disabled={!canEdit}
                onPress={() => setSelected(r.key)}
                style={st.name}
              >
                <View style={[st.dot, { backgroundColor: r.color ?? colors.line }]} />
                <T weight={current?.key === r.key ? 'bold' : 'semibold'} style={{ flexShrink: 1 }}>
                  {r.icon ? `${r.icon} ` : ''}{r.label}
                </T>
                {r.members != null ? <T muted size={12}>{r.members}</T> : null}
                {!canEdit ? <T muted size={12}>🔒</T> : null}
              </Pressable>
              {data?.manage ? (
                <View style={s.row}>
                  <Arrow label={`Monter ${r.label}`} glyph="▲" disabled={!up || !!saving} onPress={() => move(r.key, 1)} />
                  <Arrow label={`Descendre ${r.label}`} glyph="▼" disabled={!down || !!saving} onPress={() => move(r.key, -1)} />
                </View>
              ) : null}
            </View>
          );
        })}
        {!editable.length && data ? <T muted>Aucun rôle en dessous du tien à régler.</T> : null}
      </Section>

      {current && data?.manage ? (
        <RoleEditor
          key={current.key}
          role={current}
          others={editable.filter((r) => r.key !== current.key)}
          canDelete={rank >= 99 || can('roles.delete')}
          busy={!!saving}
          onSave={(draft) => run('update', () => supabase.rpc('update_role', {
            role_key: current.key, role_label: draft.label, role_color: draft.color, role_icon: draft.icon.trim() || null,
          }))}
          onDelete={(moveTo) => run('delete', () => supabase.rpc('delete_role', { role_key: current.key, move_to: moveTo }),
            () => setSelected(null))}
        />
      ) : null}

      {current ? (
        <>
          <T weight="bold" size={17}>Droits de « {current.label} »</T>
          <T muted size={13}>Les changements s’appliquent tout de suite, à tous les comptes de ce rôle.</T>
          {groups.map((grp) => (
            <Section key={grp} title={grp}>
              {data!.catalog.filter((p) => p.grp === grp).map((p) => {
                const on = granted(current.key, p.key);
                return (
                  <ToggleRow
                    key={p.key}
                    label={p.label}
                    hint={p.hint ?? undefined}
                    value={on}
                    disabled={saving !== null || (!on && rank < 99 && !mine.includes(p.key))}
                    onChange={(v) => { void run(p.key, () => supabase.rpc('set_role_permission', { target: current.key, perm: p.key, granted: v })); }}
                  />
                );
              })}
            </Section>
          ))}
        </>
      ) : null}
    </Screen>
  );
}


function Arrow({ label, glyph, disabled, onPress }: { label: string; glyph: string; disabled: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled }} disabled={disabled}
      onPress={onPress} style={[st.arrow, disabled && { opacity: 0.25 }]}>
      <T size={13}>{glyph}</T>
    </Pressable>
  );
}

function Colors({ value, onChange }: { value: string | null; onChange: (c: string) => void }) {
  return (
    <View style={s.wrap}>
      {ROLE_COLORS.map((c) => (
        <Pressable key={c} accessibilityRole="button" accessibilityLabel={`Couleur ${c}`} accessibilityState={{ selected: value === c }}
          onPress={() => onChange(c)} style={st.swatchHit}>
          <View style={[st.swatch, { backgroundColor: c }, value === c && st.swatchOn]} />
        </Pressable>
      ))}
    </View>
  );
}

function DraftFields({ draft, onChange, nameLabel = 'Nom' }: { draft: Draft; onChange: (d: Draft) => void; nameLabel?: string }) {
  return (
    <>
      <Field label={nameLabel} value={draft.label} maxLength={30} onChangeText={(label) => onChange({ ...draft, label })} placeholder="Ex. Videurs" />
      <Field label="Icône (un emoji, facultatif)" value={draft.icon} maxLength={8} onChangeText={(icon) => onChange({ ...draft, icon })} placeholder="🎟️" />
      <T muted size={13}>Couleur</T>
      <Colors value={draft.color} onChange={(color) => onChange({ ...draft, color })} />
    </>
  );
}

function NewRole({ roles, busy, onCancel, onCreate }: {
  roles: RoleRow[]; busy: boolean; onCancel: () => void; onCreate: (draft: Draft, copyFrom: string | null) => void;
}) {
  const [draft, setDraft] = useState<Draft>({ label: '', color: ROLE_COLORS[8]!, icon: '' });
  const [copyFrom, setCopyFrom] = useState<string | null>(null);
  return (
    <Card>
      <T weight="bold">Nouveau rôle</T>
      <DraftFields draft={draft} onChange={setDraft} nameLabel="Nom du nouveau rôle" />
      <T muted size={13}>Partir des droits de (seulement ceux que tu as toi-même) :</T>
      <View style={s.wrap}>
        <Chip label="Aucun droit" selected={copyFrom === null} onPress={() => setCopyFrom(null)} />
        {[...roles].reverse().map((r) => <Chip key={r.key} label={r.label} selected={copyFrom === r.key} onPress={() => setCopyFrom(r.key)} />)}
      </View>
      <T muted size={13}>Il se place juste au-dessus de Guest ; monte-le ensuite à sa place dans la liste.</T>
      <View style={s.row}>
        <Button small variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={onCancel} />
        <Button small label="Créer le rôle" style={{ flex: 1 }} loading={busy} disabled={!draft.label.trim()} onPress={() => onCreate(draft, copyFrom)} />
      </View>
    </Card>
  );
}

function RoleEditor({ role, others, canDelete, busy, onSave, onDelete }: {
  role: RoleRow; others: RoleRow[]; canDelete: boolean; busy: boolean; onSave: (d: Draft) => void; onDelete: (moveTo: string | null) => void;
}) {
  const [draft, setDraft] = useState<Draft>({ label: role.label, color: role.color, icon: role.icon ?? '' });
  const [moveTo, setMoveTo] = useState<string | null>(null);
  const changed = draft.label.trim() !== role.label || draft.color !== role.color || draft.icon.trim() !== (role.icon ?? '');
  const occupied = (role.members ?? 0) > 0;
  return (
    <Section title={`Modifier « ${role.label} »`}>
      <DraftFields draft={draft} onChange={setDraft} />
      <Button small label="Enregistrer" disabled={!changed || !draft.label.trim() || busy} onPress={() => onSave(draft)} />
      {role.builtin ? (
        <T muted size={13}>Rôle de base : il se renomme mais ne se supprime pas.</T>
      ) : !canDelete ? (
        <T muted size={13}>Pour supprimer ce rôle, il faut aussi le droit « Supprimer un rôle ».</T>
      ) : (
        <>
          {occupied ? (
            <>
              <T muted size={13}>{role.members} compte(s) ont ce rôle. Ils passeront à :</T>
              <View style={s.wrap}>
                {[...others].reverse().map((r) => <Chip key={r.key} label={r.label} selected={moveTo === r.key} onPress={() => setMoveTo(r.key)} />)}
              </View>
            </>
          ) : null}
          {!occupied || moveTo ? (
            <ConfirmButton small label="Supprimer ce rôle" confirmLabel="Oui, supprimer" onConfirm={() => onDelete(occupied ? moveTo : null)} />
          ) : null}
        </>
      )}
    </Section>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4, paddingHorizontal: 6, borderRadius: 10 },
  current: { backgroundColor: colors.fill },
  name: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  dot: { width: 14, height: 14, borderRadius: 7 },
  arrow: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  swatchHit: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  swatch: { width: 28, height: 28, borderRadius: 14 },
  swatchOn: { borderWidth: 3, borderColor: colors.text },
});
