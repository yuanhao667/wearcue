import { expect, it } from "vitest";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { BodyFrames, bodyBuildIndex, type BodyFrameState } from "./body-frames";

it("preserves proportions, a shared floor and ±5% heights across all 30 original frames", () => {
  const states: BodyFrameState[]=[];
  for (const gender of ["mens","womens"] as const) for(let height=0;height<3;height++) for(let build=0;build<5;build++) states.push({gender,height,build});
  for (const state of states) {
    expect(existsSync(join(process.cwd(),"public/body-profile-v1",BodyFrames.key(state)+".webp"))).toBe(true);
    const p=BodyFrames.placement(state), scale=p.width/1024;
    expect(p.height/1536).toBeCloseTo(scale);
    expect(BodyFrames.bottoms[state.gender][state.height][state.build]*scale+p.y).toBeCloseTo(710);
    const size=(BodyFrames.bottoms[state.gender][state.height][state.build]-BodyFrames.tops[state.gender][state.height])*scale;
    const middle=(BodyFrames.bottoms[state.gender][1][state.build]-BodyFrames.tops[state.gender][1])/2;
    expect(size/middle).toBeCloseTo(1+(state.height-1)*.05);
  }
  for (const start of states) for (const target of states) {
    let current=start,steps=0;
    while(BodyFrames.key(current)!==BodyFrames.key(target)) {
      const next=BodyFrames.next(current,target);
      if(current.gender===target.gender) expect(Math.abs(current.height-next.height)+Math.abs(current.build-next.build)).toBe(1);
      current=next; expect(++steps).toBeLessThanOrEqual(6);
    }
  }
});
it("maps legacy saved weights without losing the five new choices", () => {
  expect(bodyBuildIndex("偏轻")).toBe(0); expect(bodyBuildIndex("中等")).toBe(2); expect(bodyBuildIndex("偏重")).toBe(4);
  expect(BodyFrames.buildLabels).toEqual(["偏瘦","稍瘦","中等","稍重","偏重"]);
  BodyFrames.buildLabels.forEach((label,index)=>expect(bodyBuildIndex(label)).toBe(index));
});
