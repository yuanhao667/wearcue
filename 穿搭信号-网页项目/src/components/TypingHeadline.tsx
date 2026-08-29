"use client";

import { useEffect, useState } from "react";

export function TypingHeadline({ firstLine, secondLine }: { firstLine: string; secondLine: string }) {
  const totalLength = firstLine.length + secondLine.length;
  const [typedLength, setTypedLength] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const timer = window.setTimeout(() => setTypedLength(totalLength), 0);
      return () => window.clearTimeout(timer);
    }
    if (typedLength >= totalLength) return;
    const timer = window.setTimeout(() => setTypedLength((current) => current + 1), 130);
    return () => window.clearTimeout(timer);
  }, [totalLength, typedLength]);

  const complete = typedLength >= totalLength;
  return <h1 className="typing-headline" aria-label={`${firstLine}${secondLine}`}>
    <span className="typing-line" aria-hidden="true">{firstLine.slice(0, typedLength)}{!complete && typedLength <= firstLine.length && <span className="typing-caret" />}</span>
    <span className="headline-accent typing-line" aria-hidden="true">{secondLine.slice(0, Math.max(0, typedLength - firstLine.length))}{!complete && typedLength > firstLine.length && <span className="typing-caret" />}</span>
  </h1>;
}
