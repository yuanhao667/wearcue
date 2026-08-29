const GARMENT_COLOR_HEX: Record<string, string> = {
  冰灰: "#b9c1c6",
  卡其: "#b29a72",
  奶油白: "#eee3cb",
  奶白: "#f0eadb",
  棕色: "#7a5238",
  橄榄绿: "#66704f",
  浅灰: "#c4c7c6",
  浅色: "#dddcd4",
  浅蓝: "#9fc0d5",
  深灰: "#4e5355",
  灰白: "#d9d9d2",
  灰粉: "#b99198",
  灰绿: "#788e81",
  灰色: "#8e9394",
  灰黑: "#353a3c",
  炭灰: "#42484a",
  白色: "#f4f2e9",
  石墨灰: "#555b5e",
  米白: "#e9dfc9",
  薄荷绿: "#8dcbb3",
  藏蓝: "#24364e",
  银灰: "#aeb6bb",
  雾蓝: "#7898aa",
  麻灰: "#979b96",
  黑色: "#171918",
};

export function garmentColorHex(color: string) {
  return GARMENT_COLOR_HEX[color] ?? "#171918";
}
