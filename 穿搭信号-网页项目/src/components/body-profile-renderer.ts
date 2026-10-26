import { BodyFrames, type BodyFrameState } from "@/domain/body-frames";

export function createBodyRenderer(canvas: HTMLCanvasElement, initial: BodyFrameState, onReady: () => void, onError: () => void) {
  const context = canvas.getContext("2d");
  const frames = new Map<string, HTMLCanvasElement>();
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  let current = initial, target = initial, raf = 0, ready = false, disposed = false;
  let transition: {to: BodyFrameState; start: number; duration: number} | null = null;
  function paint(state: BodyFrameState, alpha = 1) {
    if (!context) return;
    context.globalAlpha = alpha;
    context.drawImage(frames.get(BodyFrames.key(state))!,0,0);
    context.globalAlpha = 1;
  }
  function animate(now: number) {
    raf = 0;
    if (disposed || !ready) return;
    if (motion.matches || document.hidden) { current = target; transition = null; paint(current); return; }
    if (transition) {
      const t = Math.min(1,(now-transition.start)/transition.duration);
      paint(current); paint(transition.to,t);
      if (t < 1) { raf = requestAnimationFrame(animate); return; }
      current = transition.to; transition = null;
    }
    if (BodyFrames.key(current) !== BodyFrames.key(target)) {
      const to = BodyFrames.next(current,target);
      // shortcut: short dissolves may show double contours; add approved bridge frames if noticeable.
      transition = {to,start:now,duration:current.gender !== to.gender ? 120 : current.height !== to.height ? 85 : 65};
      raf = requestAnimationFrame(animate);
    } else paint(current);
  }
  function schedule() { if (!disposed && ready && !raf) raf = requestAnimationFrame(animate); }
  async function load() {
    if (!context) { onError(); return; }
    const states: BodyFrameState[] = [];
    for (const gender of ["mens","womens"] as const) for (let height=0;height<3;height++) for (let build=0;build<5;build++) states.push({gender,height,build});
    async function worker() {
      while (states.length && !disposed) {
        const state = states.shift()!, image = new Image();
        image.src = `/body-profile-v1/${BodyFrames.key(state)}.webp`;
        await image.decode();
        if (disposed) return;
        const frame = document.createElement("canvas"); frame.width=512; frame.height=768;
        const ctx = frame.getContext("2d");
        if (!ctx) throw new Error("Canvas unavailable");
        ctx.fillStyle="#fff"; ctx.fillRect(0,0,512,768);
        const p = BodyFrames.placement(state);
        ctx.drawImage(image,p.x,p.y,p.width,p.height);
        frames.set(BodyFrames.key(state),frame); image.src="";
      }
    }
    try {
      await Promise.all(Array.from({length:4},worker));
      if (disposed) return;
      ready=true; current=target; paint(current); onReady();
    } catch { states.length=0; if (!disposed) onError(); }
  }
  motion.addEventListener("change",schedule);
  document.addEventListener("visibilitychange",schedule);
  void load();
  return {
    update(next: BodyFrameState) { target=next; schedule(); },
    dispose() { disposed=true; cancelAnimationFrame(raf); frames.clear(); motion.removeEventListener("change",schedule); document.removeEventListener("visibilitychange",schedule); },
  };
}
