import { afterEach, expect, it, vi } from "vitest";
import { createBearMotionRenderer } from "./bear-motion-renderer";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function setup() {
  vi.stubGlobal("Image", class { src = ""; decode() { return Promise.resolve(); } });
  let blended = false;
  const main = {
    globalAlpha: 1, globalCompositeOperation: "source-over",
    clearRect: vi.fn(() => { blended = false; }),
    drawImage: vi.fn(() => { if (main.globalAlpha < 1) blended = true; }),
  };
  const snapshots: boolean[] = [];
  const colorSample = new Uint8ClampedArray([
    223, 215, 42, 255, // The added jacket's yellow cast.
    28, 25, 23, 255, // Opaque mouth detail.
    240, 235, 226, 255, // White fur.
    223, 215, 42, 100, // Soft transparent edge.
  ]);
  const from = {
    clearRect: vi.fn(),
    drawImage: vi.fn((image) => { if (image === canvas) snapshots.push(blended); }),
    getImageData: vi.fn(() => ({ data: colorSample })),
    putImageData: vi.fn(),
  };
  const canvas = document.createElement("canvas");
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(function (this: HTMLCanvasElement) {
    return (this === canvas ? main : from) as unknown as CanvasRenderingContext2D;
  });
  const renderer = (await createBearMotionRenderer(canvas))!;
  return { renderer, canvas, snapshots, colorSample, main };
}

it("uses the single middle PNG in both directions instead of detouring through the front", async () => {
  const { renderer, canvas } = await setup();
  renderer.draw(-1, 0, 0);
  let time = 0;
  for (const y of [-1, 0]) {
    const seen = new Set<number>();
    for (let step = 0; step < 30; step++) {
      renderer.draw(-1, y, time += 16.7);
      seen.add(Number(canvas.dataset.sourceFrame));
      expect([canvas.width, canvas.height]).toEqual([576, 384]);
    }
    expect(seen.has(193)).toBe(true);
    expect(seen.has(194)).toBe(true);
    expect(seen.has(0)).toBe(false);
    expect(Number(canvas.dataset.sourceFrame)).toBe(y === -1 ? 24 : 112);
  }
});

it("never recaptures a partially blended image under rapid pointer changes", async () => {
  const { renderer, snapshots } = await setup();
  renderer.draw(0, 0, 0);
  for (let i = 1; i < 100; i++) renderer.draw(i % 2 ? -1 : 1, Math.sin(i), i * 16.7);
  expect(snapshots.length).toBeGreaterThan(10);
  expect(snapshots.every(value => !value)).toBe(true);
});

it("corrects only the added material color and offsets it without scaling or changing alpha", async () => {
  const { renderer, canvas, colorSample, main } = await setup();
  expect(colorSample[1] - colorSample[0]).toBeGreaterThanOrEqual(4);
  expect([...colorSample.slice(4, 12)]).toEqual([28, 25, 23, 255, 240, 235, 226, 255]);
  expect([colorSample[3], colorSample[15]]).toEqual([255, 100]);
  renderer.draw(-.825, -.5, 0);
  expect(canvas.dataset.sourceFrame).toBe("193");
  expect(main.drawImage).toHaveBeenLastCalledWith(expect.any(HTMLCanvasElement), 1, 2, 576, 384);
});

it("carries a delayed frame through the left bridge without a stationary extra tick", async () => {
  const { renderer, canvas, main, snapshots } = await setup();
  renderer.draw(-1, 0, 0);
  renderer.draw(-1, -1, 10);
  expect(canvas.dataset.sourceFrame).toBe("194");
  // Each half lasts 50 ms; delayed RAFs carry into the next half without a pause.
  const alphas: number[] = [];
  main.drawImage.mockImplementation(() => { alphas.push(main.globalAlpha); });
  renderer.draw(-1, -1, 74);
  expect(canvas.dataset.sourceFrame).toBe("193");
  expect(alphas.at(-1)).toBeCloseTo(14 / 50);
  renderer.draw(-1, -1, 124);
  expect(canvas.dataset.sourceFrame).toBe("24");
  expect(alphas.at(-1)).toBeCloseTo(14 / 50);
  expect(snapshots.every(value => !value)).toBe(true);
  expect(renderer.draw(-1, -1, 160)).toBe(false);
});

it.each([false, true])("passes through exactly one new pose in 100 ms (reverse=%s)", async (reverse) => {
  const { renderer, canvas } = await setup();
  const first = reverse ? [-.825, -.5] : [-1, 0];
  const last = reverse ? [-1, 0] : [-.825, -.5];
  renderer.draw(first[0], first[1], 0);
  expect(renderer.draw(last[0], last[1], 10)).toBe(true);
  expect(canvas.dataset.sourceFrame).toBe("194");
  expect(renderer.draw(last[0], last[1], 60)).toBe(true);
  expect(canvas.dataset.sourceFrame).toBe(reverse ? "112" : "193");
  expect(renderer.draw(last[0], last[1], 110)).toBe(false);
});
