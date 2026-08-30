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

export function OutfitIcon({ item, audience }: { item: OutfitComponent; audience: Audience }) {
  const style = {
    "--outfit-icon": `url("${assetPath(item, audience)}")`,
  } as CSSProperties;
  return <div className="outfit-icon-frame"><span className="outfit-icon-mask" style={style} aria-hidden="true" /></div>;
}
