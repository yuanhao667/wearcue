import type { CSSProperties } from "react";
import type { Audience, OutfitComponent } from "@/domain/backend";
import { resolveGarmentIcon } from "@/config/garment-icon-map";

export function assetPath(item: OutfitComponent, audience: Audience) {
  const definition = resolveGarmentIcon(item, audience);
  const key = definition?.baseIconKey || item.asset_key || item.functional_icon_key;
  const accessory = definition?.collection === "accessory" || item.slot === "equipment" || key.startsWith("acc_");
  const collection = accessory ? "accessories" : (definition?.collection || audience);
  return `/icons/garments/${collection}/${key}.svg`;
}

export function isLightOutfitColor(value?: string | null) {
  const match = value?.match(/^#([0-9a-f]{6})$/i);
  if (!match) return false;
  const rgb = [0, 2, 4].map((offset) => Number.parseInt(match[1].slice(offset, offset + 2), 16));
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 255000 > .68;
}

export function OutfitIcon({ item, audience, colorize = false }: { item: OutfitComponent; audience: Audience; colorize?: boolean }) {
  const style = {
    "--outfit-icon": `url("${assetPath(item, audience)}")`,
    "--outfit-color": colorize ? (item.color_value || "#4f565b") : "#4f565b",
  } as CSSProperties;
  const light = colorize && isLightOutfitColor(item.color_value);
  return <div className={`outfit-icon-frame${light ? " is-light" : ""}`}><span className="outfit-icon-mask" style={style} aria-hidden="true" /></div>;
}
