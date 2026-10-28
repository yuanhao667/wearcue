"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const steps = [
  { target: "home-tour-items", title: "今天穿这些", copy: "根据今天的天气和你选择的出行场景，为你推荐这套衣物。" },
  { target: "home-tour-detail", title: "看看怎么搭", copy: "点这里，查看完整穿搭效果和搭配建议。" },
  { target: "home-tour-profile", title: "让推荐更适合你", copy: "在设置中完善体型和风格偏好，让推荐更适合你。" },
];

export function HomeTour({ accountKey, ready }: { accountKey: string; ready: boolean }) {
  const [step, setStep] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const bubble = useRef<HTMLElement>(null);
  const ring = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const storageKey = `wearcue_home_tour_v1:${accountKey}`;

  useEffect(() => {
    if (!ready || !accountKey || dismissed || step !== null) return;
    try { if (localStorage.getItem(storageKey) === "done") return; } catch { /* Still usable when storage is unavailable. */ }
    // Let the existing card entrance finish before anchoring the first tooltip.
    const timer = window.setTimeout(() => setStep(0), 800);
    return () => window.clearTimeout(timer);
  }, [accountKey, dismissed, ready, step, storageKey]);

  const close = useCallback(() => {
    try { localStorage.setItem(storageKey, "done"); } catch { /* Keep the dismissal for this mounted page. */ }
    if (step !== null) document.getElementById(steps[step].target)?.focus({ preventScroll: true });
    setDismissed(true);
    setStep(null);
  }, [step, storageKey]);

  useEffect(() => {
    if (step === null || !ready) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close, ready, step]);

  useLayoutEffect(() => {
    if (step === null || !ready) return;
    const target = document.getElementById(steps[step].target);
    const panel = bubble.current;
    const outline = ring.current;
    if (!target || !panel || !outline) return;
    function position() {
      const r = target!.getBoundingClientRect();
      Object.assign(outline!.style, { left: `${r.left - 6}px`, top: `${r.top - 6}px`, width: `${r.width + 12}px`, height: `${r.height + 12}px`, borderRadius: step === 2 ? "50%" : step === 1 ? "999px" : "18px" });
      const w = panel!.offsetWidth, h = panel!.offsetHeight;
      const x = Math.max(16, Math.min(step === 0 ? r.left + (r.width - w) / 2 : r.right - w, innerWidth - w - 16));
      let side = step === 0 ? "top" : "bottom";
      let y = side === "top" ? r.top - h - 22 : r.bottom + 22;
      if (y < 16) { side = "bottom"; y = r.bottom + 22; }
      if (y + h > innerHeight - 96 && r.top - h - 22 >= 16) { side = "top"; y = r.top - h - 22; }
      panel!.dataset.side = side;
      Object.assign(panel!.style, { left: `${x}px`, top: `${Math.max(16, Math.min(y, innerHeight - h - 96))}px`, visibility: "visible" });
      panel!.style.setProperty("--arrow-x", `${Math.max(25, Math.min(w - 25, r.left + r.width / 2 - x))}px`);
    }
    // Scroll the window only: scrollIntoView can scroll the card's clipped contents.
    const r = target.getBoundingClientRect();
    window.scrollTo({ top: step === 2 ? 0 : Math.max(0, scrollY + r.top + r.height / 2 - innerHeight / 2), behavior: "instant" });
    position();
    next.current?.focus({ preventScroll: true });
    const observer = new ResizeObserver(position);
    observer.observe(target);
    observer.observe(panel);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, { passive: true });
    return () => { observer.disconnect(); window.removeEventListener("resize", position); window.removeEventListener("scroll", position); };
  }, [ready, step]);

  if (step === null || !ready) return null;
  return createPortal(<div className="home-tour">
    <div className="tour-ring" ref={ring} aria-hidden="true" />
    <section className="tour-bubble" ref={bubble} role="dialog" aria-labelledby="home-tour-title" aria-describedby="home-tour-copy" style={{ visibility: "hidden" }}>
      <div className="tour-top"><span className="tour-step"><i />认识 WearCue · {step + 1} / 3</span><button className="tour-close" aria-label="跳过引导" onClick={close}>×</button></div>
      <h2 id="home-tour-title">{steps[step].title}</h2><p id="home-tour-copy">{steps[step].copy}</p>
      <div className="tour-footer"><div className="tour-dots" aria-hidden="true">{steps.map((_, index) => <i key={index} className={index === step ? "active" : ""} />)}</div>
        <div className="tour-actions">{step > 0 && <button className="tour-back" onClick={() => setStep(step - 1)}>上一步</button>}<button className="tour-next" ref={next} onClick={() => step < 2 ? setStep(step + 1) : close()}>{step === 2 ? "知道了 ✓" : "下一步 →"}</button></div>
      </div>
    </section>
  </div>, document.body);
}
