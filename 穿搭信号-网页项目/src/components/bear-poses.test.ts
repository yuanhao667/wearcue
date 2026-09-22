import { describe, expect, it } from "vitest";
import atlas from "../../public/brand/bear-motion/frames.json";
import { bearPose, selectBearFrame } from "./bear-poses";

describe("bear gaze from the rendered clip", () => {
  it.each([
    ["right", 1, 0], ["left", -1, 0], ["up", 0, -1], ["down", 0, 1],
    ["upper right", 1, -1], ["upper left", -1, -1],
    ["lower right", 1, 1], ["lower left", -1, 1],
  ] as const)("looks toward %s without assuming chronological frame order", (_name, x, y) => {
    const frame = atlas.frames[selectBearFrame(x, y, atlas.frames)];
    const [px, py] = bearPose(frame);
    if (x) expect(px * x).toBeGreaterThan(.3);
    else expect(Math.abs(px)).toBeLessThan(.25);
    if (y) expect(py * y).toBeGreaterThan(.3);
    else expect(Math.abs(py)).toBeLessThan(.25);
  });

  it("returns to the original front pose in the face dead zone", () => {
    for (const [x, y] of [[0, 0], [.05, -.05], [-.1, .05]]) {
      expect(atlas.frames[selectBearFrame(x, y, atlas.frames)]).toBe(0);
    }
  });

  it.each([-.6, -.8, -1])("keeps a vertical sweep at x=%s facing left and includes the one middle pose", (x) => {
    let previous = -1, previousPitch = -Infinity;
    const selected = new Set<number>();
    for (let y = -1; y <= 1.001; y += .02) {
      previous = selectBearFrame(x, y, atlas.frames, previous);
      const frame = atlas.frames[previous];
      const [yaw, pitch] = bearPose(frame);
      expect(yaw).toBeLessThanOrEqual(-.5);
      expect(pitch).toBeGreaterThanOrEqual(previousPitch);
      previousPitch = pitch;
      selected.add(frame);
    }
    expect(selected.has(193)).toBe(true);
    expect(selected.has(0)).toBe(false);
  });
});
