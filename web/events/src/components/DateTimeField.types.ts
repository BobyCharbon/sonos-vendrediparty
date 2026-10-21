export type DateTimeFieldProps = {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  hint?: string;
  /** Champ facultatif : un bouton « Effacer » le vide (le sélecteur iOS n’en propose pas). */
  optional?: boolean;
  /** Date au plus tôt (JJ.MM.AAAA HH:MM) : les dates antérieures sont grisées, et le champ vide s’ouvre dessus. */
  min?: string;
};
