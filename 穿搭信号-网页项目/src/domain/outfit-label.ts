const TRAILING_SEQUENCE = /\s+(?:0?\d{1,3}|[０-９]{1,3})$/u;

export function displayOutfitLabel(label: string) {
  return label.trim().replace(TRAILING_SEQUENCE, "").trim();
}
