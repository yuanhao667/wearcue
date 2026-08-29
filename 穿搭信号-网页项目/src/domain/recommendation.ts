import { OUTFIT_TEMPLATES } from "@/config/outfits";
import { GARMENT_ICON_BY_KEY } from "@/config/garment-icon-map";
import type { ExtractedGarment, InspirationLook } from "@/domain/inspiration";
import type {
  GarmentItem,
  GarmentThickness,
  OutfitTemplate,
  Recommendation,
  Scene,
  ThermalBand,
  WeatherAdjustments,
  WeatherSnapshot,
} from "@/domain/types";

const THICKNESS_BY_THERMAL_BAND: Record<ThermalBand, GarmentThickness> = {
  hot: "thin",
  warm: "thin",
  mild: "regular",
  cool: "regular",
  cold: "thick",
  freezing: "thick",
  severe: "thick",
};

export function getGarmentThickness(thermalBand: ThermalBand): GarmentThickness {
  return THICKNESS_BY_THERMAL_BAND[thermalBand];
}

export function garmentThicknessLabel(thickness?: GarmentThickness) {
  if (!thickness) return undefined;
  return { thin: "薄款", regular: "常规款", thick: "厚款" }[thickness];
}

export function getThermalBand(apparentMin: number, coldOffset = 0): ThermalBand {
  const adjusted = apparentMin + coldOffset;
  if (adjusted >= 28) return "hot";
  if (adjusted >= 24) return "warm";
  if (adjusted >= 20) return "mild";
  if (adjusted >= 15) return "cool";
  if (adjusted >= 10) return "cold";
  if (adjusted >= 5) return "freezing";
  return "severe";
}

export function getWeatherAdjustments(weather: WeatherSnapshot): WeatherAdjustments {
  const apparentDelta = weather.apparentMax - weather.apparentMin;
  return {
    needsRemovableLayer: apparentDelta >= 8,
    needsWaterproof: weather.totalPrecipitation > 0.2 || weather.maxPrecipitationProbability >= 50,
    needsHeavyRainProtection: weather.totalPrecipitation >= 5,
    needsSnowProtection: weather.totalSnowfall > 0,
    needsWindproof: weather.maxWindSpeed >= 30 || weather.maxWindGust >= 40,
    avoidUmbrella: weather.maxWindGust >= 50,
    needsSunProtection: weather.uvIndexMax >= 6,
    needsStrongSunProtection: weather.uvIndexMax >= 8,
  };
}

function extraItems(adjustments: WeatherAdjustments): GarmentItem[] {
  const items: GarmentItem[] = [];
  if (adjustments.needsWaterproof && !adjustments.avoidUmbrella) {
    items.push({
      id: "weather-umbrella",
      name: "折叠伞",
      category: "accessory",
      icon: "umbrella",
      color: "黑色",
      sourceIconKey: "acc_umbrella",
    });
  }
  if (adjustments.needsStrongSunProtection) {
    items.push({
      id: "weather-cap",
      name: "遮阳帽",
      category: "accessory",
      icon: "cap",
      color: "浅色",
      sourceIconKey: "acc_sun_hat",
    });
  }
  return items;
}

function builtInSourceIconKey(item: GarmentItem, audience: "mens" | "womens") {
  const prefix = audience;
  let baseKey: string;
  if (item.icon === "tee") baseKey = "top_tshirt_short";
  else if (item.icon === "shirt") baseKey = item.name.includes("长袖") || item.name.includes("打底") ? "top_tshirt_long" : "top_shirt";
  else if (item.icon === "sweater") {
    if (item.name.includes("卫衣")) baseKey = "top_sweatshirt";
    else if (item.name.includes("打底") || item.name.includes("保暖层")) baseKey = "top_tshirt_long";
    else baseKey = "top_knit";
  } else if (item.icon === "jacket") baseKey = item.name.includes("牛仔") ? "outer_denim_jacket" : "outer_light_jacket";
  else if (item.icon === "coat") baseKey = item.name.includes("风衣") ? "outer_trench" : "outer_wool_coat";
  else if (item.icon === "down") baseKey = item.name.includes("长款") ? "outer_down_long" : "outer_down_short";
  else if (item.icon === "shorts") baseKey = "bottom_shorts";
  else if (item.icon === "skirt") baseKey = item.name.includes("短") ? "bottom_skirt_short" : "bottom_skirt_long";
  else if (item.icon === "pants") {
    if (item.name.includes("牛仔")) baseKey = "bottom_jeans";
    else if (item.name.includes("工装")) baseKey = "bottom_cargo_pants";
    else if (item.name.includes("运动") || item.name.includes("卫裤")) baseKey = "bottom_sweatpants";
    else if (item.name.includes("西裤")) baseKey = "bottom_suit_pants";
    else baseKey = "bottom_casual_pants";
  } else if (item.icon === "sneaker") {
    if (item.name.includes("跑鞋")) baseKey = "shoe_running";
    else if (item.name.includes("厚底")) baseKey = "shoe_dad_sneaker";
    else if (item.name.includes("板鞋")) baseKey = "shoe_canvas";
    else baseKey = "shoe_sneaker";
  } else if (item.icon === "boot") baseKey = item.name.includes("雪地") || item.name.includes("保暖靴") ? "shoe_snow_boot" : "shoe_boot";
  else if (item.icon === "umbrella") return "acc_umbrella";
  else return "acc_sun_hat";

  const key = `${prefix}_${baseKey}`;
  return GARMENT_ICON_BY_KEY.has(key) ? key : undefined;
}

function genericIconFor(item: ExtractedGarment): GarmentItem["icon"] {
  if (item.category === "bottom") {
    if (item.iconKey.includes("shorts")) return "shorts";
    if (item.iconKey.includes("skirt")) return "skirt";
    return "pants";
  }
  if (item.category === "shoes") return item.iconKey.includes("boot") ? "boot" : "sneaker";
  if (item.category === "outerwear") {
    if (item.iconKey.includes("down")) return "down";
    if (item.iconKey.includes("coat") || item.iconKey.includes("trench")) return "coat";
    return "jacket";
  }
  if (item.category === "accessory") return item.iconKey.includes("umbrella") ? "umbrella" : "cap";
  if (item.category === "onepiece") return "skirt";
  if (item.iconKey.includes("shirt")) return "shirt";
  if (item.iconKey.includes("knit") || item.iconKey.includes("sweat") || item.iconKey.includes("hoodie")) return "sweater";
  return "tee";
}

function categoryFor(item: ExtractedGarment): GarmentItem["category"] {
  if (item.category === "onepiece") return "top";
  if (["top", "bottom", "outerwear", "shoes", "accessory"].includes(item.category)) {
    return item.category as GarmentItem["category"];
  }
  return "accessory";
}

function lookMatchesThickness(look: InspirationLook, thickness: GarmentThickness) {
  const apparel = look.items.filter((item) => item.category !== "shoes" && item.category !== "accessory");
  if (apparel.length === 0) return false;
  return apparel.filter((item) => item.thickness === thickness).length >= Math.ceil(apparel.length / 2);
}

function personalTemplate(look: InspirationLook, thermalBand: ThermalBand, scene: Scene): OutfitTemplate {
  return {
    id: `personal-${look.id}`,
    thermalBand,
    scenes: [scene],
    label: look.title,
    styleTags: ["穿搭灵感"],
    rationale: look.note || "来自你保存的穿搭，今天的气温和衣物薄厚正合适。",
    audiences: [look.collection],
    source: "personal",
    items: look.items.map((item) => ({
      id: `personal-${look.id}-${item.id}`,
      name: `${item.colorName} ${item.label}`.trim(),
      category: categoryFor(item),
      icon: genericIconFor(item),
      color: item.colorName,
      colorHex: item.colorHex,
      sourceIconKey: item.iconKey,
      thickness: item.category === "shoes" || item.category === "accessory" ? undefined : item.thickness,
    })),
  };
}

export function recommendOutfit(options: {
  weather: WeatherSnapshot;
  scene: Scene;
  coldOffset?: number;
  audience?: "mens" | "womens";
  excludedTemplateIds?: string[];
  personalLooks?: InspirationLook[];
  random?: () => number;
}): Recommendation {
  const {
    weather,
    scene,
    coldOffset = 0,
    audience,
    excludedTemplateIds = [],
    personalLooks = [],
    random = Math.random,
  } = options;
  const thermalBand = getThermalBand(weather.apparentMin, coldOffset);
  const thickness = getGarmentThickness(thermalBand);
  const personalCandidates = personalLooks.filter(
    (look) => look.recommendationEnabled
      && (!audience || look.collection === audience)
      && lookMatchesThickness(look, thickness),
  );
  const unseenPersonal = personalCandidates.filter((look) => !excludedTemplateIds.includes(`personal-${look.id}`));
  const candidates = OUTFIT_TEMPLATES.filter(
    (template) => template.thermalBand === thermalBand
      && template.scenes.includes(scene)
      && (!audience || (template.audiences ?? ["mens", "womens"]).includes(audience)),
  );
  const unseen = candidates.filter((template) => !excludedTemplateIds.includes(template.id));
  const pool = unseen.length > 0 ? unseen : candidates;
  const chosenPersonal = unseenPersonal[Math.floor(random() * unseenPersonal.length)];
  const template = chosenPersonal
    ? personalTemplate(chosenPersonal, thermalBand, scene)
    : pool[Math.floor(random() * pool.length)] ?? OUTFIT_TEMPLATES[0];
  const adjustments = getWeatherAdjustments(weather);
  const resolvedAudience = audience ?? template.audiences?.[0] ?? "mens";
  const apparelItems = template.items.map((item) =>
    item.category === "shoes" || item.category === "accessory"
      ? { ...item, sourceIconKey: item.sourceIconKey ?? builtInSourceIconKey(item, resolvedAudience) }
      : { ...item, thickness, sourceIconKey: item.sourceIconKey ?? builtInSourceIconKey(item, resolvedAudience) },
  );
  const weatherTags = [
    `${Math.round(weather.apparentMin)}–${Math.round(weather.apparentMax)}° 体感`,
    ...(adjustments.needsWaterproof ? ["可能有雨"] : []),
    ...(adjustments.needsWindproof ? ["风力较强"] : []),
    ...(adjustments.needsSunProtection ? [`UV ${Math.round(weather.uvIndexMax)}`] : []),
  ];
  const tips = [
    ...(adjustments.needsRemovableLayer ? ["早晚温差明显，带一件方便穿脱的外层。"] : []),
    ...(adjustments.needsHeavyRainProtection ? ["雨量不小，优先防水外层和不吸水鞋履。"] : []),
    ...(adjustments.needsSnowProtection ? ["可能下雪，鞋底注意防滑。"] : []),
    ...(adjustments.needsWindproof ? ["风力较强，外层优先选择防风面料。"] : []),
    ...(adjustments.avoidUmbrella ? ["阵风较大，雨伞不安全，优先雨衣或带帽外套。"] : []),
    ...(adjustments.needsStrongSunProtection
      ? ["紫外线很强，建议帽子、防晒霜并减少正午暴晒。"]
      : adjustments.needsSunProtection
        ? ["紫外线偏强，外出记得基础防晒。"]
        : []),
  ];

  return {
    thermalBand,
    template,
    items: [...apparelItems, ...extraItems(adjustments)],
    summary: `${template.label} · ${template.rationale}`,
    weatherTags,
    tips,
    adjustments,
  };
}

export function sceneLabel(scene: Scene) {
  return { commute: "通勤", date: "约会", travel: "出游" }[scene];
}

export function weatherCodeLabel(code: number) {
  if (code === 0) return "晴";
  if (code <= 3) return "多云";
  if ([45, 48].includes(code)) return "有雾";
  if (code >= 71 && code <= 77) return "下雪";
  if (code >= 95) return "雷雨";
  if (code >= 51 && code <= 67) return "有雨";
  if (code >= 80 && code <= 82) return "阵雨";
  return "天气变化";
}
