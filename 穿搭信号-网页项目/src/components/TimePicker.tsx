"use client";

import { useEffect, useRef, useState } from "react";

const HOURS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const MINUTES = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, "0"));

export function TimePicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const [hour = "00", minute = "00"] = value.split(":");

  useEffect(() => {
    if (!open) return;
    function onDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function pick(nextHour: string, nextMinute: string) {
    onChange(`${nextHour}:${nextMinute}`);
    setOpen(false);
  }

  return (
    <div className="time-picker" ref={rootRef}>
      <button
        type="button"
        className="time-picker-trigger"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="选择提醒时间"
      >
        <svg className="time-picker-clock" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v4.5l3 2" /></svg>
        <span className="time-picker-value"><span>{hour}</span><i>:</i><span>{minute}</span></span>
        <svg className="time-picker-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2.5 4.5 3.5 3 3.5-3" /></svg>
      </button>
      {open && (
        <div className="time-picker-popover" role="dialog" aria-label="选择提醒时间">
          <div className="time-picker-columns">
            <div className="time-picker-column" aria-label="小时">
              {HOURS.map((item) => (
                <button type="button" key={item} className={item === hour ? "active" : ""} onClick={() => pick(item, minute)}>
                  {item}
                </button>
              ))}
            </div>
            <span className="time-picker-sep" aria-hidden="true">:</span>
            <div className="time-picker-column" aria-label="分钟">
              {MINUTES.map((item) => (
                <button type="button" key={item} className={item === minute ? "active" : ""} onClick={() => pick(hour, item)}>
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
