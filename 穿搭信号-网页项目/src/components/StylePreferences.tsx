/* eslint-disable @next/next/no-img-element */
"use client";

import { useId, useState } from "react";
import type { Audience, StyleId } from "@/domain/backend";

export const preferenceStyles: { id: StyleId; name: string; description: string }[] = [
  { id: "minimal", name: "简约", description: "克制配色与利落剪裁，注重面料质感和比例，用简洁搭配穿出不费力的高级感。" },
  { id: "casual", name: "休闲", description: "以卫衣、牛仔等日常单品为主，版型舒展、搭配自然，日常出行也能轻松自在。" },
  { id: "street", name: "潮流", description: "通过醒目图案、特别的廓形和个性叠穿表达自己，让日常穿搭更有辨识度与态度。" },
  { id: "sport", name: "运动", description: "以运动单品与活力搭配为主，注重舒适和活动空间，随季节调整层次，兼顾日常与运动。" },
  { id: "outdoor", name: "户外", description: "用冲锋衣、抓绒等功能单品营造山野感，兼顾实用与搭配层次，也能融入城市日常。" },
];

// Calibrated separately for portrait cards and square settings thumbnails.
const photoFraming: Record<Audience, Record<StyleId, { height: string; thumbnailPosition: string }>> = {
  mens: {
    minimal: { height: "100%", thumbnailPosition: "center top" },
    casual: { height: "112.5%", thumbnailPosition: "center 39%" },
    street: { height: "100%", thumbnailPosition: "center 10%" },
    sport: { height: "100%", thumbnailPosition: "center top" },
    outdoor: { height: "116.5%", thumbnailPosition: "center 47%" },
  },
  womens: {
    minimal: { height: "101%", thumbnailPosition: "center 12%" },
    casual: { height: "100%", thumbnailPosition: "center top" },
    street: { height: "100%", thumbnailPosition: "center top" },
    sport: { height: "100%", thumbnailPosition: "center 10%" },
    outdoor: { height: "103.5%", thumbnailPosition: "center 18%" },
  },
};

export function PreferenceHeart() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5 3.8 12.3a5.2 5.2 0 0 1 7.4-7.4l.8.8.8-.8a5.2 5.2 0 0 1 7.4 7.4L12 20.5Z" /></svg>;
}

export function StylePreferences({ audience, selected, onSave, onboarding = false, disabled = false, embedded = false }: {
  audience: Audience; selected: StyleId[]; onSave: (styles: StyleId[]) => Promise<boolean>;
  onboarding?: boolean; disabled?: boolean; embedded?: boolean;
}) {
  const [draft, setDraft] = useState<StyleId[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [tooltip, setTooltip] = useState<StyleId | null>(null);
  const tooltipId = useId();
  const styles = draft ?? selected;
  const selectionSummary = styles.length > 0 ? `已选择 ${styles.length} 种风格` : "不选择则不限风格";
  async function save(nextStyles = styles) {
    setSaving(true); setError("");
    try {
      if (await onSave(nextStyles)) setDraft(null);
      else setError("保存失败，选择已保留，请重试。");
    } catch { setError("保存失败，选择已保留，请重试。"); }
    finally { setSaving(false); }
  }
  return <section className={`style-preferences${onboarding ? " is-onboarding" : embedded ? " is-compact is-embedded" : " is-compact settings-paper-card"}`} aria-label="服装风格偏好">
    {onboarding ? <header className="style-preferences-heading">
      <h1>选择你喜欢的风格类型</h1>
      <p>可多选。在每日穿搭推荐时，我们会优先推荐你所选风格的穿搭。</p>
    </header> : embedded ? <header className="style-preferences-compact-heading"><h3>服装风格偏好</h3><span>{selectionSummary}</span></header> : <><div className="card-caption">穿搭偏好</div><h2>服装风格偏好</h2></>}
    <div className="style-preferences-scroll">
      <div className="style-preferences-cards">
        {preferenceStyles.map(({ id, name, description }) => <button type="button" key={id}
          className="style-preference-card" aria-label={name} aria-pressed={styles.includes(id)} disabled={saving || disabled}
          aria-describedby={!onboarding && tooltip === id ? `${tooltipId}-${id}` : undefined}
          onMouseEnter={() => setTooltip(id)} onMouseLeave={() => setTooltip(null)}
          onFocus={() => setTooltip(id)} onBlur={() => setTooltip(null)}
          onKeyDown={(event) => { if (event.key === "Escape") setTooltip(null); }}
          onClick={() => {
            const next = styles.includes(id) ? styles.filter((style) => style !== id) : [...styles, id];
            setDraft(next);
            if (embedded) void save(next);
          }}>
          <span className="style-preference-visual">
            <img src={`/style-preferences/${audience}-${id}.jpg`} alt={`${audience === "womens" ? "女装" : "男装"} · ${name}风格穿搭`}
              style={{ height: onboarding ? photoFraming[audience][id].height : undefined, objectPosition: onboarding ? "center top" : photoFraming[audience][id].thumbnailPosition }} />
            {onboarding && <span className="style-preference-shade" aria-hidden="true" />}
            {onboarding && <span className="style-preference-copy"><strong>{name}</strong><span>{description}</span></span>}
          </span>
          {!onboarding && <span className="style-preference-label">{name}</span>}
          {!onboarding && tooltip === id && <span role="tooltip" id={`${tooltipId}-${id}`} className="outfit-save-tooltip style-preference-tooltip">{description}</span>}
        </button>)}
      </div>
    </div>
    {(!embedded || error) && <footer className="style-preferences-actions">
      {!embedded && <span style={{ visibility: onboarding && styles.length === 0 ? "hidden" : undefined }}>{styles.length > 0 || onboarding ? `已选择 ${styles.length} 种风格${onboarding ? "，可在设置中更改" : ""}` : "不选择则不限风格"}</span>}
      {onboarding && <button type="button" className="ghost-button" disabled={saving || disabled} onClick={() => void save([])}>跳过</button>}
      {!embedded && <button type="button" className="sunshine-button" disabled={saving || disabled || (!onboarding && draft === null)} onClick={() => void save()}>{saving ? "正在保存…" : onboarding ? "保存并进入穿搭灵感" : "保存风格偏好"}</button>}
      {embedded && error && <button type="button" className="ghost-button" disabled={saving || disabled} onClick={() => void save()}>重试保存</button>}
      {error && <p role="alert">{error}</p>}
    </footer>}
  </section>;
}
