import { parsePhoneNumberFromString } from 'libphonenumber-js/max';

export type PhoneCountry = 'CH' | 'FR' | 'international';

/** Keep explicit +/00 country codes; use the selected country only for local numbers. */
export function parseLoginPhone(raw: string, country: PhoneCountry) {
  const input = raw.trim().replace(/^00/, '+');
  if (!input || !/^[+\d\s().-]+$/.test(input)) return null;
  if (country === 'international' && !input.startsWith('+')) return null;
  const parsed = parsePhoneNumberFromString(input, {
    defaultCountry: country === 'international' ? undefined : country,
    extract: false,
  });
  if (!parsed?.isValid() || parsed.ext) return null;
  return { number: parsed.number, formatted: parsed.formatInternational(), country: parsed.country };
}
