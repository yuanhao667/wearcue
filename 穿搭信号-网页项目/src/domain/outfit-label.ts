const TRAILING_SEQUENCE = /\s+(?:0?\d{1,3}|[０-９]{1,3})$/u;

export function displayOutfitLabel(label: string) {
  return label.trim().replace(TRAILING_SEQUENCE, "").trim();
}

export function displayGarmentLabel(label: string) {
  let name = label.trim().replace(/\s+/gu, "");
  if (Array.from(name).length <= 7) return name;
  name = name.replace(/([黑白灰蓝绿红棕黄紫橙]|卡其|藏青|米白)色/gu, "$1");
  for (const modifier of ["做旧", "落肩", "基础款", "常规款", "宽松", "修身", "质感", "大尺寸", "多层"]) {
    if (Array.from(name).length <= 7) break;
    name = name.replaceAll(modifier, "");
  }
  // shortcut: 未识别的长名称由卡片单行省略显示，出现新命名模式时再补充简化词。
  return name;
}
