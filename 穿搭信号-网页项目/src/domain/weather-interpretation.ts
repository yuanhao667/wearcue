export type WeatherMetricTone = "calm" | "notice" | "strong" | "danger";

export interface WeatherMetricInterpretation {
  label: string;
  action: string;
  percent: number;
  tone: WeatherMetricTone;
  scaleMax: string;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

export function interpretPrecipitationProbability(probability: number): WeatherMetricInterpretation {
  const value = clampPercent(probability);

  if (value < 20) return { label: "很低", action: "基本不用担心下雨", percent: value, tone: "calm", scaleMax: "100%" };
  if (value < 50) return { label: "有可能", action: "出门前再看一眼", percent: value, tone: "notice", scaleMax: "100%" };
  if (value < 80) return { label: "较高", action: "建议随身带伞", percent: value, tone: "strong", scaleMax: "100%" };
  return { label: "很高", action: "出门记得带伞", percent: value, tone: "danger", scaleMax: "100%" };
}

export function interpretWindGust(speedKmh: number): WeatherMetricInterpretation {
  const speed = Math.max(0, speedKmh);
  const percent = clampPercent((speed / 75) * 100);

  if (speed < 20) return { label: "微风", action: "体感轻柔，正常出行", percent, tone: "calm", scaleMax: "75+" };
  if (speed < 39) return { label: "有点风", action: "正常出行，轻薄外套更稳", percent, tone: "notice", scaleMax: "75+" };
  if (speed < 62) return { label: "风较强", action: "优先防风，注意帽子和衣摆", percent, tone: "strong", scaleMax: "75+" };
  return { label: "风很强", action: "尽量避开空旷处，慎用雨伞", percent, tone: "danger", scaleMax: "75+" };
}

export function interpretUvIndex(index: number): WeatherMetricInterpretation {
  const value = Math.max(0, index);
  const percent = clampPercent((value / 11) * 100);

  if (value < 3) return { label: "低", action: "一般无需额外防晒", percent, tone: "calm", scaleMax: "11+" };
  if (value < 6) return { label: "中等", action: "需要基础防晒", percent, tone: "notice", scaleMax: "11+" };
  if (value < 8) return { label: "高", action: "建议防晒霜、帽子或遮阳", percent, tone: "strong", scaleMax: "11+" };
  if (value < 11) return { label: "很高", action: "减少正午暴晒，做好防护", percent, tone: "danger", scaleMax: "11+" };
  return { label: "极高", action: "尽量避开正午户外活动", percent: 100, tone: "danger", scaleMax: "11+" };
}
