import atlas from "../../public/brand/bear-motion/frames.json";
import { bearPose, selectBearFrame } from "./bear-poses";

export async function createBearMotionRenderer(canvas: HTMLCanvasElement) {
  const context = canvas.getContext("2d");
  if (!context) return null;
  const poses = new window.Image();
  poses.src = "/brand/bear-motion/poses.png";
  const middle = new window.Image();
  middle.src = "/brand/bear-motion/left-middle-clean.png";
  const between = new window.Image();
  between.src = "/brand/bear-motion/left-between.png";
  await Promise.all([poses.decode(), middle.decode(), between.decode()]);
  // Calibrate only the added frame once at load time. Its yellow-green material
  // is 4.6 degrees warmer than the original clip; white fur, dark details and
  // every alpha value must remain unchanged.
  const calibratedMiddle = document.createElement("canvas");
  calibratedMiddle.width = atlas.canvas.width;
  calibratedMiddle.height = atlas.canvas.height;
  const middleContext = calibratedMiddle.getContext("2d");
  if (!middleContext) return null;
  middleContext.drawImage(middle, 0, 0);
  const pixels = middleContext.getImageData(0, 0, calibratedMiddle.width, calibratedMiddle.height);
  for (let i = 0; i < pixels.data.length; i += 4) {
    const [r, g, b, a] = pixels.data.subarray(i, i + 4);
    const high = Math.max(r, g), chroma = high - b;
    if (!a || chroma < 60 || b >= Math.min(r, g)) continue;
    const hue = 60 * (r >= g ? (g - b) / chroma : 2 - (r - b) / chroma);
    if (hue < 40 || hue > 95) continue;
    const corrected = hue + 4.6;
    pixels.data[i] = corrected <= 60 ? high : high - (corrected - 60) / 60 * chroma;
    pixels.data[i + 1] = corrected >= 60 ? high : b + corrected / 60 * chroma;
  }
  middleContext.putImageData(pixels, 0, 0);
  canvas.width = atlas.canvas.width;
  canvas.height = atlas.canvas.height;
  const from = document.createElement("canvas");
  from.width = canvas.width;
  from.height = canvas.height;
  const fromContext = from.getContext("2d");
  if (!fromContext) return null;
  let target = -1, started = 0, duration = 0, transitioning = false;
  let continuousLeftTransition = false;
  const middleIndex = atlas.frames.indexOf(193);
  const betweenIndex = atlas.frames.indexOf(194);

  const paint = (index: number) => {
    if (index === betweenIndex) {
      // This PNG already includes the same color and position calibration.
      context.drawImage(between, 0, 0, canvas.width, canvas.height);
      return;
    }
    if (index === middleIndex) {
      // Match the original paws' center; translation only, never scale the bear.
      context.drawImage(calibratedMiddle, 1, 2, canvas.width, canvas.height);
      return;
    }
    const { width, height, columns } = atlas.tile;
    context.drawImage(poses, index % columns * width, Math.floor(index / columns) * height,
      width, height, 0, 0, canvas.width, canvas.height);
  };
  const render = (time: number) => {
    context.clearRect(0, 0, canvas.width, canvas.height);
    const t = transitioning ? Math.min(1, (time - started) / duration) : 1;
    if (t < 1) {
      // The left bridge is one continuous movement, not two stop/start easings.
      const ease = continuousLeftTransition ? t : t * t * (3 - 2 * t);
      context.globalAlpha = 1 - ease;
      context.drawImage(from, 0, 0);
      // Add premultiplied pixels: unlike source-over, opacity stays intact at the mouth.
      context.globalCompositeOperation = "lighter";
      context.globalAlpha = ease;
      paint(target);
      context.globalCompositeOperation = "source-over";
      context.globalAlpha = 1;
    } else {
      paint(target);
      transitioning = false;
    }
  };
  return {
    draw(x: number, y: number, time = performance.now()) {
      let wanted = selectBearFrame(x, y, atlas.frames, target);
      const completedAt = transitioning && time >= started + duration ? started + duration : null;
      if (target < 0) { target = wanted; render(time); }
      else if (transitioning) render(time);
      // Finish the short transition before taking another snapshot, so partially
      // blended heads cannot accumulate when pointer events arrive rapidly.
      if (wanted !== target && !transitioning) {
        const [fromX, fromY] = bearPose(atlas.frames[target]);
        const [toX, toY] = bearPose(atlas.frames[wanted]);
        if (fromX <= -.5 && toX <= -.5 && target !== middleIndex && wanted !== middleIndex
          && (fromY + .5) * (toY + .5) < 0) wanted = middleIndex;
        if ((atlas.frames[target] === 112 && wanted === middleIndex)
          || (target === middleIndex && atlas.frames[wanted] === 112)) wanted = betweenIndex;
        continuousLeftTransition = fromX <= -.5 && toX <= -.5
          && (target === middleIndex || wanted === middleIndex
            || target === betweenIndex || wanted === betweenIndex);
        fromContext.clearRect(0, 0, from.width, from.height);
        fromContext.drawImage(canvas, 0, 0);
        // Two 50 ms steps preserve the pair's agreed 100 ms total duration.
        duration = 50;
        target = wanted;
        // Carry a late RAF's remainder into the next bridge segment instead of
        // holding the completed pose for another tick. Cap catch-up to one frame.
        started = continuousLeftTransition && completedAt !== null
          ? Math.max(completedAt, time - 1000 / 60) : time;
        transitioning = true;
        if (continuousLeftTransition) render(time);
      }
      canvas.dataset.sourceFrame = String(atlas.frames[target]);
      return transitioning;
    },
    dispose() {
      context.clearRect(0, 0, canvas.width, canvas.height);
      from.width = from.height = 0;
    },
  };
}
