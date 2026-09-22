// Calibrated from the rendered clip: x is screen-right, y is down.
// It doubles back several times, so timestamps cannot be mapped linearly to angles.
const KEYS = [
  [0, 0, 0], [8, -.08, -.15], [16, -.55, -.85], [24, -.65, -1],
  [32, -.3, -.85], [40, 0, -.85], [48, .4, -.8], [56, .72, -.65],
  [64, .92, -.35], [74, 1, 0], [80, 1, .2], [88, .5, .7],
  [92, 0, 1], [100, -.75, .7], [108, -1, .2], [112, -1, 0],
  [118, -.75, .2], [120, -.45, .25], [124, .1, .35], [128, .6, .5],
  [136, .95, .45], [144, .2, .85], [152, -.3, -.4], [160, -.55, -1],
  [168, -.45, -.9], [176, 0, -.12], [184, 0, 0], [192, 0, 0],
] as const;

export function bearPose(frame: number): readonly [number, number] {
  // The two added left-side poses, ordered by gaze rather than source-video time.
  if (frame === 193) return [-.825, -.5];
  if (frame === 194) return [-.9125, -.25];
  for (let i = 1; i < KEYS.length; i++) {
    const [end, x, y] = KEYS[i];
    if (frame <= end) {
      const [start, px, py] = KEYS[i - 1];
      const t = (frame - start) / (end - start);
      return [px + (x - px) * t, py + (y - py) * t];
    }
  }
  return [0, 0];
}

export function selectBearFrame(x: number, y: number, frames: readonly number[], previous = -1) {
  if (Math.hypot(x, y) < .15) return 0;
  let best = 0, distance = Infinity;
  frames.forEach((frame, index) => {
    const [px, py] = bearPose(frame);
    // Keep a leftward vertical sweep on the left side of the face.
    if (x <= -.55 && px > -.5) return;
    const continuity = previous < 0 ? 0 : .018 * Math.min(1, Math.abs(frame - frames[previous]) / 24);
    const next = (px - x) ** 2 + (py - y) ** 2 + continuity;
    if (next < distance) { best = index; distance = next; }
  });
  return best;
}
