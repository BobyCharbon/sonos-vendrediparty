/** Vérifie une écriture Supabase, qui peut réussir sans renvoyer de données. */
export function check(res: { error: { message: string } | null }): void {
  if (res.error) throw new Error(res.error.message);
}

/** Exige des données pour une lecture ou une écriture avec `.select()`. */
export function must<T>(res: { data: T; error: { message: string } | null }): NonNullable<T> {
  check(res);
  if (res.data == null) throw new Error('Introuvable');
  return res.data;
}
