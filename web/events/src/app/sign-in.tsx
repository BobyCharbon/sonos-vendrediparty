import { useState } from 'react';
import { router } from 'expo-router';
import { KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';

import { Button, ErrorText, Field, Screen, T, Title } from '@/components/ui';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { parseLoginPhone, type PhoneCountry } from '@/lib/phone';

export default function SignIn() {
  const [phone, setPhone] = useState('');
  const [country, setCountry] = useState<PhoneCountry>('CH');
  const parsedPhone = parseLoginPhone(phone, country);
  const [code, setCode] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendCode() {
    setError(null);
    if (busy) return;
    const parsed = parseLoginPhone(phone, country);
    if (!parsed) return setError(country === 'international'
      ? 'Saisis le numéro complet avec son indicatif, par exemple +32…'
      : 'Vérifie le pays et saisis un numéro complet, avec ou sans le zéro initial.');
    const e164 = parsed.number;
    setBusy(true);
    const { error } = await supabase.auth.signInWithOtp({ phone: e164 });
    setBusy(false);
    if (error) return setError(error.message);
    setSentTo(e164);
  }

  async function verify() {
    if (!sentTo) return;
    setError(null);
    setBusy(true);
    const { error } = await supabase.auth.verifyOtp({ phone: sentTo, token: code.trim(), type: 'sms' });
    setBusy(false);
    if (error) setError('Code incorrect ou expiré');
    // La redirection est gérée par le layout racine.
  }

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 24 }}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ gap: 24 }}>
        <View style={{ gap: 6 }}>
          <Title size={40}>
            Ton compte Party
          </Title>
          <T muted>Connecte-toi par SMS : ton surnom et ta photo te suivent dans les jeux, et tu peux demander à rejoindre les événements du groupe.</T>
        </View>

        {!sentTo ? (
          <View style={{ gap: 14 }}>
            <View style={{ gap: 8 }} accessibilityRole="radiogroup" accessibilityLabel="Pays et indicatif">
              <T weight="semibold">Pays et indicatif</T>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {([
                  { key: 'CH', label: 'Suisse +41' },
                  { key: 'FR', label: 'France +33' },
                  { key: 'international', label: 'Autre pays' },
                ] as const).map((option) => (
                  <Pressable
                    key={option.key}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: country === option.key, disabled: busy }}
                    aria-checked={country === option.key}  // React Native Web ne le déduit pas pour un radio (axe : aria-required-attr)
                    disabled={busy}
                    onPress={() => { setCountry(option.key); setError(null); }}
                    style={{ minHeight: 44, justifyContent: 'center', paddingHorizontal: 14,
                      borderRadius: 12, backgroundColor: country === option.key ? colors.accent : colors.bg,
                      borderWidth: 1, borderColor: country === option.key ? colors.accent : colors.line }}
                  >
                    <T size={14} weight="semibold" color={country === option.key ? colors.onAccent : colors.text}>{option.label}</T>
                  </Pressable>
                ))}
              </View>
            </View>
            <Field
              label={country === 'international' ? 'Numéro avec indicatif' : 'Ton numéro de téléphone'}
              placeholder={country === 'FR' ? '06 12 34 56 78' : country === 'CH' ? '079 123 45 67' : '+32 470 12 34 56'}
              keyboardType="phone-pad"
              autoComplete="tel"
              textContentType="telephoneNumber"
              value={phone}
              onChangeText={(value) => {
                setPhone(value);
                setError(null);
                if (/^(\+|00)/.test(value.trim())) {
                  const international = parseLoginPhone(value, 'international');
                  if (international) setCountry(international.country === 'CH' || international.country === 'FR' ? international.country : 'international');
                }
              }}
              editable={!busy}
              onSubmitEditing={sendCode}
            />
            <T muted size={14}>Un numéro commençant par + ou 00 conserve son propre indicatif.</T>
            {parsedPhone && <View accessibilityLiveRegion="polite"><T>Le code sera envoyé au {parsedPhone.formatted}</T></View>}
            <ErrorText error={error} />
            <Button label="Recevoir un code par SMS" onPress={sendCode} loading={busy} disabled={!phone} />
          </View>
        ) : (
          <View style={{ gap: 14 }}>
            <Field
              label={`Code reçu au ${sentTo}`}
              placeholder="123456"
              keyboardType="number-pad"
              autoComplete="sms-otp"
              textContentType="oneTimeCode"
              maxLength={6}
              value={code}
              onChangeText={setCode}
              onSubmitEditing={verify}
              autoFocus
            />
            <ErrorText error={error} />
            <Button label="Se connecter" onPress={verify} loading={busy} disabled={code.length < 6} />
            <Button label="Changer de numéro" variant="ghost" onPress={() => { setSentTo(null); setCode(''); }} />
          </View>
        )}
      </KeyboardAvoidingView>
      <Button label="Confidentialité" variant="ghost" onPress={() => router.push('/privacy')} />
    </Screen>
  );
}
