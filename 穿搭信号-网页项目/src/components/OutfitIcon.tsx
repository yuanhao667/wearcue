import type { CSSProperties } from "react";
import type { Audience, OutfitComponent } from "@/domain/backend";
import { resolveGarmentIcon } from "@/config/garment-icon-map";

function iconKey(item: OutfitComponent, audience: Audience) {
  const definition = resolveGarmentIcon(item, audience);
  return definition?.baseIconKey || item.asset_key || item.functional_icon_key;
}

export function assetPath(item: OutfitComponent, audience: Audience) {
  const definition = resolveGarmentIcon(item, audience);
  const key = iconKey(item, audience);
  const accessory = definition?.collection === "accessory" || item.slot === "equipment" || key.startsWith("acc_");
  const collection = accessory ? "accessories" : (definition?.collection || audience);
  return `/icons/garments/${collection}/${key}.svg`;
}

export function OutfitIcon({ item, audience }: { item: OutfitComponent; audience: Audience }) {
  const style = {
    "--outfit-icon": `url("${assetPath(item, audience)}")`,
  } as CSSProperties;
  return <div className="outfit-icon-frame"><span className="outfit-icon-mask" data-icon-key={iconKey(item, audience)} style={style} aria-hidden="true" /></div>;
}
