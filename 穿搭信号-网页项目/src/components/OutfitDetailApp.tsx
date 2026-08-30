/* eslint-disable @next/next/no-img-element */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { OutfitIcon } from "./OutfitIcon";
import { apiAsset, apiJson } from "@/lib/backend-api";
import type { AIQuota, BackendRecommendation, Outfit, OutfitAnalysis, ReplicationGuide } from "@/domain/backend";
import { outfitItemSortKey } from "@/domain/outfit-order";

const DETAIL_ADVICE_STEPS = ["AI 正在分析这套单品组合", "AI 正在生成穿搭步骤", "AI 正在检查天气适配", "AI 正在整理替代建议"];

export function detailAdviceStatus(step: number) {
  return DETAIL_ADVICE_STEPS[step % DETAIL_ADVICE_STEPS.length];
}

function subscribe() { return () => undefined; }
function snapshot() { return localStorage.getItem("wearcue_active_outfit_v1") || ""; }

export function OutfitDetailApp({ id }: { id: string }) {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "");
  const [savedOutfit, setSavedOutfit] = useState<Outfit | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiAdvice, setAiAdvice] = useState<ReplicationGuide | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<OutfitAnalysis | null>(null);
  const [adviceQuota, setAdviceQuota] = useState<AIQuota | null>(null);
  const [adviceError, setAdviceError] = useState("");
  const [imageError, setImageError] = useState("");
  const [generatedImageUrl, setGeneratedImageUrl] = useState("");
  const [adviceDone, setAdviceDone] = useState(false);
  const [adviceStatusStep, setAdviceStatusStep] = useState(0);
  const requestedDetail = useRef("");
  const recommendation = useMemo<BackendRecommendation | null>(() => {
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as BackendRecommendation;
      return parsed?.template_id === id ? parsed : null;
    } catch {
      return null;
    }
  }, [raw, id]);

  useEffect(() => {
    let active = true;
    void apiJson<Outfit>(`/outfits/${id}`).then((value) => { if (active) setSavedOutfit(value); }).catch(() => { if (active) setSavedOutfit(null); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    if (loading) return;
    const targetItems = recommendation?.items ?? savedOutfit?.components;
    if (!targetItems || savedOutfit?.inspiration_id) {
      setAdviceDone(true);
      return;
    }
    const needsAdvice = Boolean(
      recommendation?.source === "ai"
      && !recommendation.replication_guide
      && !recommendation.outfit_analysis,
    );
    const requestKey = `${id}:${needsAdvice}`;
    if (requestedDetail.current === requestKey) return;
    requestedDetail.current = requestKey;
    let active = true;
    setAdviceDone(false);
    setAdviceError("");
    setImageError("");
    void apiJson<{
      replication_guide?: ReplicationGuide;
      outfit_analysis?: OutfitAnalysis;
      image_url: string;
      ai_quota: AIQuota;
    }>("/recommendations/advice", {
      method: "POST",
      body: JSON.stringify({
        recommendation_id: id,
        label: recommendation?.label ?? savedOutfit?.label ?? "今日穿搭",
        scene: recommendation?.scene ?? savedOutfit?.scene_ids[0] ?? "commute",
        audience: recommendation?.audience ?? savedOutfit?.audience ?? "mens",
        items: targetItems,
        constraints: recommendation?.constraints ?? {},
        generate_advice: needsAdvice,
      }),
    }).then((value) => {
      if (active) {
        if (value.replication_guide) setAiAdvice(value.replication_guide);
        if (value.outfit_analysis) setAiAnalysis(value.outfit_analysis);
        setGeneratedImageUrl(apiAsset(value.image_url));
        setAdviceQuota(value.ai_quota);
        if (recommendation && value.replication_guide && value.outfit_analysis) try {
          localStorage.setItem("wearcue_active_outfit_v1", JSON.stringify({
            ...recommendation,
            replication_guide: value.replication_guide,
            outfit_analysis: value.outfit_analysis,
          }));
        } catch { /* 后端已持久化，浏览器缓存失败不影响本次结果 */ }
      }
    }).catch((error) => {
      if (active) {
        const message = error instanceof Error ? error.message : "AI 穿搭详情生成失败";
        setImageError(message);
        if (needsAdvice) {
          setAiAdvice(null);
          setAiAnalysis(null);
          setAdviceError(message);
        }
      }
    }).finally(() => {
      if (active) setAdviceDone(true);
    });
    return () => { active = false; };
  }, [id, loading, recommendation, savedOutfit]);

  const adviceLoading = Boolean(recommendation && recommendation.source === "ai" && !recommendation.replication_guide && !recommendation.outfit_analysis && !adviceDone);

  useEffect(() => {
    if (!adviceLoading) return;
    const timer = window.setInterval(() => setAdviceStatusStep((step) => step + 1), 3000);
    return () => window.clearInterval(timer);
  }, [adviceLoading]);

  if (!recommendation && loading) return <main className="paper-page outfit-detail-page"><section className="paper-state"><span>穿搭详情</span><h2>正在加载穿搭</h2></section></main>;
  if (!recommendation && !savedOutfit) return <main className="paper-page outfit-detail-page"><section className="paper-state"><span>穿搭详情</span><h2>这套穿搭不存在</h2><p>它可能已经被删除。</p><Link className="sunshine-button" href="/closet">返回穿搭灵感</Link></section></main>;

  const items = [...(recommendation?.items ?? savedOutfit?.components ?? [])].sort((a, b) => outfitItemSortKey(a) - outfitItemSortKey(b));
  const audience = recommendation?.audience ?? savedOutfit?.audience ?? "mens";
  const label = recommendation?.label ?? savedOutfit?.label ?? "今日穿搭";
  const displayLabel = recommendation ? label.trim().slice(0, 8) || "今日穿搭" : label;
  const analysis = recommendation?.outfit_analysis ?? aiAnalysis ?? savedOutfit?.outfit_analysis ?? null;
  const originalImageUrl = savedOutfit?.inspiration_id ? apiAsset(`/inspirations/${savedOutfit.inspiration_id}/image?size=medium`) : "";
  const imageUrl = originalImageUrl || generatedImageUrl;
  const showPhotoColumn = Boolean(imageUrl || imageError || (!savedOutfit?.inspiration_id && (recommendation || savedOutfit)));
  const imageLoading = showPhotoColumn && !imageUrl && !imageError && !adviceDone;
  const guide = recommendation?.replication_guide ?? aiAdvice ?? savedOutfit?.replication_guide ?? {
    formula: items.map((item) => item.variant_type).join("＋"),
    steps: items.map((item) => `选择${thicknessLabel(item.thickness)}${item.variant_type}`),
    styling_points: [], weather_note: "按当天体感增减外层。", substitute: "选择相同版型和薄厚的单品即可。",
  };
  return <main className="paper-page outfit-detail-page">
    <Link className="outfit-detail-back" href={savedOutfit ? "/closet" : "/"}>← 返回{savedOutfit ? "穿搭灵感" : "今日推荐"}</Link>
    <header className="outfit-detail-head"><h1>{displayLabel}</h1><strong>{guide.formula}</strong></header>
    <div className="outfit-detail-layout">
      <section className={`outfit-detail-visual-card${showPhotoColumn ? "" : " icons-only"}`}>
        {showPhotoColumn && <section className="outfit-detail-photo-card"><div className="card-caption">{originalImageUrl ? savedOutfit?.source === "system" ? "穿搭示例照片" : "穿搭照片" : "AI穿搭效果图"}</div>{imageUrl ? <figure className="outfit-detail-photo"><img src={imageUrl} alt={`${label}穿搭参考`} />{savedOutfit?.source === "system" && <figcaption>例图由AI生成</figcaption>}</figure> : <div className="outfit-detail-photo-placeholder" role="status" aria-live="polite">{imageLoading ? <><b aria-hidden="true"><span className="recognition-dots"><i /><i /><i /></span></b><h3>正在生成穿搭效果图</h3><p>AI 正在还原人物、场景与整套衣物</p></> : <p className="cross-audience-notice" role="alert"><span className="cross-audience-notice-icon" aria-hidden="true">!</span><span className="cross-audience-notice-copy">{imageError}</span></p>}</div>}</section>}
        <section className="outfit-detail-items"><div className="outfit-detail-grid">{items.map((item, index) => <article key={`${item.slot}-${index}`}><OutfitIcon item={item} audience={audience} /><strong>{item.variant_type}</strong><span>{item.color_name}、{thicknessLabel(item.thickness)}</span></article>)}</div></section>
      </section>
      <section className="review-card outfit-detail-result-card">
        <div className="outfit-detail-bear" aria-hidden="true"><img src="/illustrations/inspiration-bear.png" alt="" /></div>
        <section className={`replication-card${adviceLoading ? " is-loading" : ""}`} aria-busy={adviceLoading}>
          {adviceLoading ? <div className="review-empty is-loading detail-advice-loading" role="status" aria-live="polite">
            <b aria-hidden="true"><span className="recognition-dots"><i /><i /><i /></span></b>
            <h3>正在生成穿搭建议</h3>
            <p>{detailAdviceStatus(adviceStatusStep)}</p>
          </div> : <>
            <div className="card-caption">怎么穿</div>
            {adviceError && <p className="cross-audience-notice" role="alert"><span className="cross-audience-notice-icon" aria-hidden="true">!</span><span className="cross-audience-notice-copy">{adviceError}</span></p>}
            {adviceQuota && <p className="privacy-copy">AI 详情生成今日剩余 {adviceQuota.remaining}/{adviceQuota.limit} 次</p>}
            {analysis && <section className="outfit-advice detail-outfit-advice" aria-label="穿搭建议">
              <div className="outfit-advice-heading"><strong>{displayLabel}</strong></div>
              <div className="outfit-analysis-module">
                <span>穿搭分析</span>
                <p>{analysis.summary}</p>
                {analysis.structure_points.length > 0 && <ul>{analysis.structure_points.map((point) => <li key={point}>{point}</li>)}</ul>}
              </div>
              {analysis.completion_advice.length > 0 && <div className="outfit-advice-completion"><span>补全这套</span><div className="outfit-advice-completion-list">{analysis.completion_advice.map((advice) => <p key={advice}>{advice}</p>)}</div></div>}
            </section>}
            <div className="replication-steps"><span>穿搭步骤</span><ol>{guide.steps.map((step) => <li key={step}>{step}</li>)}</ol></div>
            {guide.styling_points.length > 0 && <div className="replication-note"><span>版型与层次</span><p>{guide.styling_points.join("；")}</p></div>}
            <div className="replication-note accent"><span>今天怎么调整</span><p>{guide.weather_note}</p></div>
            <div className="replication-note"><span>没有同款</span><p>{guide.substitute}</p></div>
          </>}
        </section>
      </section>
    </div>
  </main>;
}

function thicknessLabel(value: string) { return ({ thin: "薄款", regular: "常规", thick: "厚款" } as Record<string, string>)[value] ?? value; }
