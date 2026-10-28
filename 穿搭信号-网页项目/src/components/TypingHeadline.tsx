"use client";

export function TypingHeadline({ firstLine, secondLine, secondLineHighlight }: { firstLine: string; secondLine: string; secondLineHighlight: string }) {
  const highlightStart = secondLineHighlight ? secondLine.indexOf(secondLineHighlight) : -1;
  const highlightEnd = highlightStart + secondLineHighlight.length;
  const lineStyle = { fontSize: `clamp(20px, calc(100cqw / ${Math.max(11.5, Array.from(firstLine).length, Array.from(secondLine).length)}), 1em)` };
  return <h1 className="typing-headline" aria-label={`${firstLine}。${secondLine}`}>
    <span className="typing-line" aria-hidden="true" style={lineStyle}>{firstLine}</span>
    <span className="typing-line typing-suggestion" aria-hidden="true" style={lineStyle}>{highlightStart < 0 ? secondLine : <>{secondLine.slice(0, highlightStart)}<span className="headline-accent">{secondLineHighlight}</span>{secondLine.slice(highlightEnd)}</>}</span>
  </h1>;
}
