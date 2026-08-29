export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand-mark" aria-label="穿搭信号，每天少想一件事：穿什么。">
      <span className="brand-glyph" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {!compact && (
        <span className="brand-lockup">
          <span className="brand-name">穿搭信号 <small>OUTFIT SIGNAL</small></span>
          <span className="brand-slogan">每天少想一件事：穿什么。</span>
        </span>
      )}
    </div>
  );
}
