export function seasonLabel(minimum: number, maximum: number) {
  const midpoint = (minimum + maximum) / 2;

  if (maximum <= 12 || midpoint < 12) return "冬";
  if (minimum >= 25 || midpoint >= 24) return "夏";
  return "春秋";
}
