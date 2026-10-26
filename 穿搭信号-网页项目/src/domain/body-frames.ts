// Original PNGs remain unchanged; uniform scaling keeps their anatomy intact.
import type { Audience } from "@/domain/backend";
export type BodyFrameState = { gender: Audience; height: number; build: number };
export const BodyFrames = {
  heights: ['short', 'medium', 'tall'],
  heightLabels: ['偏矮', '中等', '偏高'],
  buildLabels: ['偏瘦', '稍瘦', '中等', '稍重', '偏重'],
  tops: {mens: [389,274,143], womens: [376,268,133]},
  bottoms: {
    mens: [[1369,1369,1369,1369,1369],[1393,1394,1394,1394,1394],[1395,1394,1395,1395,1395]],
    womens: [[1321,1323,1321,1321,1322],[1361,1363,1363,1363,1362],[1393,1393,1393,1393,1393]],
  },
  key({gender, height, build}: BodyFrameState) { return `${gender}-${this.heights[height]}-${build+1}`; },
  placement({gender,height,build}: BodyFrameState) {
    const bottom=this.bottoms[gender][height][build];
    const medium=this.bottoms[gender][1][build]-this.tops[gender][1];
    const scale=medium*(1+(height-1)*0.05)/(bottom-this.tops[gender][height])/2;
    return {x:256-512*scale,y:710-bottom*scale,width:1024*scale,height:1536*scale};
  },
  next(current: BodyFrameState, target: BodyFrameState) {
    if (current.gender !== target.gender) return {...target};
    // Finish one adjacent frame, then follow the latest pointer target (no stale queue).
    if (current.height !== target.height) return {...current, height:current.height+Math.sign(target.height-current.height)};
    return {...current, build:current.build+Math.sign(target.build-current.build)};
  },
};

export function bodyBuildIndex(value: string): number {
  if (value === "偏轻") return 0;
  const index = BodyFrames.buildLabels.indexOf(value);
  return index < 0 ? 2 : index;
}
