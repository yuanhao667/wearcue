/* eslint-disable @next/next/no-img-element */
"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { OutfitIcon } from "./OutfitIcon";
import { apiAsset, apiJson } from "@/lib/backend-api";
import type { BackendRecommendation, Outfit } from "@/domain/backend";


function subscribe() { return () => undefined; }
function snapshot() { return localStorage.getItem("wearcue_active_outfit_v1") || ""; }

export function OutfitDetailApp({ id }: { id: string }) {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "");
  const [savedOutfit, setSavedOutfit] = useState<Outfit | null>(null);
  const [loading, setLoading] = useState(true);
  let recommendation: BackendRecommendation | null = null;
  try {
    const parsed = raw ? JSON.parse(raw) as BackendRecommendation : null;
    if (parsed?.template_id === id) recommendation = parsed;
  } catch { recommendation = null; }

  useEffect(() => {
    let active = true;
    void apiJson<Outfit>(`/outfits/${id}`).then((value) => { if (active) setSavedOutfit(value); }).catch(() => { if (active) setSavedOutfit(null); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  if (!recommendation && loading) return <main className="paper-page outfit-detail-page"><section className="paper-state"><span>穿搭详情</span><h2>正在加载穿搭</h2></section></main>;
  if (!recommendation && !savedOutfit) return <main className="paper-page outfit-detail-page"><section className="paper-state"><span>穿搭详情</span><h2>这套穿搭不存在</h2><p>它可能已经被删除。</p><Link className="sunshine-button" href="/closet">返回穿搭灵感</Link></section></main>;

  const items = recommendation?.items ?? savedOutfit?.components ?? [];
  const audience = recommendation?.audience ?? savedOutfit?.audience ?? "mens";
  const label = recommendation?.label ?? savedOutfit?.label ?? "今日穿搭";
  const analysis = recommendation?.outfit_analysis ?? savedOutfit?.outfit_analysis ?? null;
  const imageUrl = savedOutfit?.inspiration_id ? apiAsset(`/inspirations/${savedOutfit.inspiration_id}/image?size=medium`) : "";
  const guide = recommendation?.replication_guide ?? savedOutfit?.replication_guide ?? {
    formula: items.map((item) => item.variant_type).join("＋"),
    steps: items.map((item) => `选择${thicknessLabel(item.thickness)}${item.variant_type}`),
    styling_points: [], weather_note: "按当天体感增减外层。", substitute: "选择相同版型和薄厚的单品即可。",
  };
  return <main className="paper-page outfit-detail-page">
    <Link className="outfit-detail-back" href={savedOutfit ? "/closet" : "/"}>← 返回{savedOutfit ? "穿搭灵感" : "今日推荐"}</Link>
    <header className="outfit-detail-head"><h1>{label}</h1><strong>{guide.formula}</strong></header>
    <div className={`outfit-detail-layout${imageUrl ? "" : " single"}`}>
      {imageUrl && <section className="outfit-detail-photo-card"><div className="card-caption">穿搭照片</div><figure className="outfit-detail-photo"><img src={imageUrl} alt={`${label}穿搭参考`} /></figure></section>}
      <section className="review-card outfit-detail-result-card">
        <section className="replication-card">
          <div className="card-caption">怎么穿</div>
          {analysis && <section className="outfit-advice detail-outfit-advice" aria-label="穿搭建议">
            <div className="outfit-advice-heading"><strong>{analysis.summary}</strong></div>
            {analysis.structure_points.length > 0 && <ul>{analysis.structure_points.map((point) => <li key={point}>{point}</li>)}</ul>}
            {analysis.completion_advice.length > 0 && <div className="outfit-advice-completion"><span>补全这套</span><p>{analysis.completion_advice.join("；")}</p></div>}
          </section>}
          <ol>{guide.steps.map((step) => <li key={step}>{step}</li>)}</ol>
          {guide.styling_points.length > 0 && <div className="replication-note"><span>版型与层次</span><p>{guide.styling_points.join("；")}</p></div>}
          <div className="replication-note accent"><span>今天怎么调整</span><p>{guide.weather_note}</p></div>
          <div className="replication-note"><span>没有同款</span><p>{guide.substitute}</p></div>
        </section>
        <section className="outfit-detail-items"><div className="card-caption">照着选这些单品</div><div className="outfit-detail-grid">{items.map((item, index) => <article key={`${item.slot}-${index}`}><OutfitIcon item={item} audience={audience} colorize /><strong>{item.variant_type}</strong><span>{thicknessLabel(item.thickness)}</span></article>)}</div></section>
      </section>
    </div>
  </main>;
}

function thicknessLabel(value: string) { return ({ thin: "薄款", regular: "常规", thick: "厚款" } as Record<string, string>)[value] ?? value; }
