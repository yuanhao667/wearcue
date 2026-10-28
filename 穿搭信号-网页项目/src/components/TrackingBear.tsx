"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";
import { createBearMotionRenderer } from "./bear-motion-renderer";

const SOURCE = "/brand/bear-motion/front.png";
export function TrackingBear() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointer = window.matchMedia("(any-hover: hover) and (any-pointer: fine)");
    let renderer: Awaited<ReturnType<typeof createBearMotionRenderer>> = null;
    let loading = false;
    let failed = false;
    let frame = 0;
    let previousTime = 0;
    let visible = true;
    let activated = false;
    let disposed = false;
    let currentX = 0, currentY = 0, targetX = 0, targetY = 0;
    let lastPointer: { x: number; y: number } | null = null;
    const enabled = () => activated && !motion.matches && pointer.matches && visible && !document.hidden;

    const animate = (time: number) => {
      frame = 0;
      if (!renderer || !enabled()) return;
      const blend = 1 - Math.exp(-Math.min(time - previousTime || 16, 64) / 80);
      previousTime = time;
      currentX += (targetX - currentX) * blend;
      currentY += (targetY - currentY) * blend;
      const settled = Math.abs(targetX - currentX) + Math.abs(targetY - currentY) < 0.001;
      if (settled) { currentX = targetX; currentY = targetY; }
      const transitioning = renderer.draw(currentX, currentY, time);
      if (!settled || transitioning) frame = requestAnimationFrame(animate);
    };
    const schedule = () => {
      if (!frame && renderer && enabled()) {
        previousTime = performance.now();
        frame = requestAnimationFrame(animate);
      }
    };
    const updateTarget = () => {
      if (!lastPointer || !enabled()) return;
      const bounds = container.getBoundingClientRect();
      // Measure from the face, not the page center; keep the range reachable on both sides.
      const dx = lastPointer.x - (bounds.left + bounds.width * 0.50);
      const dy = lastPointer.y - (bounds.top + bounds.height * 0.43);
      targetX = Math.tanh(dx / Math.max(bounds.width * 0.7, 180));
      targetY = Math.tanh(dy / Math.max(bounds.height * 0.8, 140));
      schedule();
    };
    const activate = (event: PointerEvent) => {
      if (event.pointerType === "touch" || activated) return;
      activated = true;
      lastPointer = { x: event.clientX, y: event.clientY };
      refresh();
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      lastPointer = { x: event.clientX, y: event.clientY };
      updateTarget();
    };
    const reset = () => {
      lastPointer = null;
      targetX = targetY = 0;
      schedule();
    };
    const leave = (event: PointerEvent) => { if (!event.relatedTarget) reset(); };
    const refresh = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      if (!enabled()) {
        currentX = currentY = targetX = targetY = 0;
        lastPointer = null;
        container.removeAttribute("data-tracking");
      } else if (renderer) {
        const transitioning = renderer.draw(currentX, currentY);
        if (transitioning) schedule();
        container.dataset.tracking = "true";
        updateTarget();
      } else if (!loading && !failed) {
        loading = true;
        void createBearMotionRenderer(canvas).then((result) => {
          if (disposed) { result?.dispose(); return; }
          renderer = result;
          loading = false;
          if (!renderer) failed = true;
          refresh();
        }).catch(() => { loading = false; failed = true; });
      }
    };
    container.addEventListener("pointerenter", activate, { passive: true });
    refresh();
    const resize = new ResizeObserver(refresh);
    resize.observe(container);
    const intersection = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      refresh();
    });
    intersection.observe(container);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerout", leave, { passive: true });
    window.addEventListener("blur", reset);
    window.addEventListener("scroll", updateTarget, { passive: true, capture: true });
    window.addEventListener("resize", refresh);
    document.addEventListener("visibilitychange", refresh);
    motion.addEventListener("change", refresh);
    pointer.addEventListener("change", refresh);

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      container.removeEventListener("pointerenter", activate);
      resize.disconnect();
      intersection.disconnect();
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerout", leave);
      window.removeEventListener("blur", reset);
      window.removeEventListener("scroll", updateTarget, true);
      window.removeEventListener("resize", refresh);
      document.removeEventListener("visibilitychange", refresh);
      motion.removeEventListener("change", refresh);
      pointer.removeEventListener("change", refresh);
      container.removeAttribute("data-tracking");
      renderer?.dispose();
    };
  }, []);

  return (
    <div ref={containerRef} className="recommendation-mascot" aria-hidden="true">
      <Image className="recommendation-mascot-still" src={SOURCE} alt="" width={576} height={384} priority draggable={false} />
      <canvas ref={canvasRef} className="recommendation-mascot-canvas" />
    </div>
  );
}
