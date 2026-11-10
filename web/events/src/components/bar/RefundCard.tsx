import { Linking } from 'react-native';

import { barChf, dayLabel, METHOD_LABEL, owedNow, type MyBar } from '@/lib/bar';
import { colors } from '@/lib/theme';
import { formatIban } from '@/lib/tickets';

import { CopyRow, safeLink } from '../PayOrganizer';
import { Button, Section, T } from '../ui';

/**
 * Rembourser ce qui a été servi : lien Revolut / Twint du bénéficiaire (https seulement), sinon numéro ou IBAN à copier ;
 * puis « J'ai remboursé » (le montant restant), que l'organisateur confirme.
 */
export function RefundCard({ bar, busy, onDeclare }: { bar: MyBar; busy: boolean; onDeclare: (amount: number) => void }) {
  const owed = owedNow(bar);
  if (owed <= 0) return null;
  const p = bar.payee;
  const name = p.name?.trim() || 'l’organisateur';
  const method = METHOD_LABEL[p.method];
  const link = p.method !== 'iban' && p.link ? safeLink(p.link) : null;
  const toCopy = p.method !== 'iban' && p.link && !link ? p.link : null;
  const iban = p.method === 'iban' ? p.iban : null;
  const nothing = !link && !toCopy && !iban;
  return (
    <Section title="Rembourser">
      <T size={14} color={colors.textSoft}>
        Il te reste {barChf(owed)} à rembourser à {name}{p.repay_by ? `, avant ${dayLabel(p.repay_by).replace(/\.$/, '')}` : ''}.
      </T>
      {link ? (
        <Button label={`Rembourser ${name} avec ${p.method === 'twint' ? 'Twint' : 'Revolut'}`} onPress={() => void Linking.openURL(link)} />
      ) : null}
      {toCopy ? <CopyRow label={p.method === 'twint' ? 'Twint : numéro à copier dans l’app Twint' : `${method} : à copier`} value={toCopy} /> : null}
      {iban ? <CopyRow label={`Virement · IBAN${p.holder ? ` de ${p.holder}` : ''}`} value={iban} shown={formatIban(iban)} /> : null}
      {nothing ? (
        <T size={14} color={colors.coralSoft}>{name} n’a pas encore rempli son profil de paiement : demande-lui comment rembourser.</T>
      ) : null}
      <Button variant="secondary" label="J’ai remboursé" loading={busy} onPress={() => onDeclare(owed)} />
      <T muted size={12}>{name} confirme dès qu’il ou elle a reçu tes {barChf(owed)}.</T>
    </Section>
  );
}
