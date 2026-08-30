"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { OutfitIcon } from "./OutfitIcon";
import { apiJson } from "@/lib/backend-api";
import type { Outfit } from "@/domain/backend";
import { seasonLabel } from "@/domain/season";
import { outfitItemSortKey } from "@/domain/outfit-order";
import { crossAudienceGarmentLabels } from "@/config/garment-icon-map";

export function LibraryApp() {
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Outfit | null>(null);
  const [deleting, setDeleting] = useState(false);
  const load = useCallback(async () => {
    setStatus("loading"); setMessage("");
    try { setOutfits(await apiJson<Outfit[]>("/outfits")); setStatus("success"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "穿搭灵感加载失败"); setStatus("error"); }
  }, []);
  useEffect(() => {
    // Loading the backend is the intended external-system synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);
  useEffect(() => {
    if (!deleteTarget) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !deleting) setDeleteTarget(null);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [deleteTarget, deleting]);
  async function togglePersonalRecommendation(outfit: Outfit) {
    try {
      const updated = await apiJson<Outfit>(`/outfits/${outfit.id}/status`, { method: "POST", body: JSON.stringify({ in_pool: !outfit.in_pool }) });
      setOutfits((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) { setMessage(error instanceof Error ? error.message : "状态更新失败"); }
  }

  async function remove(outfit: Outfit) {
    setDeleting(true);
    try {
      await apiJson<{ deleted: boolean }>(`/outfits/${outfit.id}`, { method: "DELETE" });
      setOutfits((current) => current.filter((item) => item.id !== outfit.id));
      setDeleteTarget(null);
    } catch (error) { setMessage(error instanceof Error ? error.message : "删除失败"); }
    finally { setDeleting(false); }
  }

  const poolOutfits = outfits.filter((outfit) => outfit.in_pool);

  function outfitCard(outfit: Outfit) {
    const crossAudienceLabels = crossAudienceGarmentLabels(outfit.components, outfit.audience);
    const icons = <div className="library-icons">{[...outfit.components].sort((a, b) => outfitItemSortKey(a) - outfitItemSortKey(b)).map((item, index) => <div className="library-outfit-item" key={`${item.slot}-${index}`}><OutfitIcon item={item} audience={outfit.audience} /><div><strong>{item.variant_type}</strong><em>{item.color_name}、{thicknessLabel(item.thickness)}</em></div></div>)}</div>;
    return <article className="library-card" key={outfit.id}>
      <div className="library-card-head">
        <div className="library-card-eyebrow-row">
          <span className={`library-card-source${outfit.source === "system" ? " is-system" : ""}`}>{outfit.source === "system" ? "系统示例" : outfit.source === "inspiration" ? "图片灵感" : "手动创建"}</span>
          <div className="outfit-range-tags">
            <span className="temperature-chip">{outfit.suitable_min}°—{outfit.suitable_max}°</span>
            <span className="season-chip">{seasonLabel(outfit.suitable_min, outfit.suitable_max)}</span>
          </div>
        </div>
        <h2 title={outfit.label}>{outfit.label}</h2>
      </div>
      {icons}
      <div className="library-meta"><span>{outfit.scene_ids.map(sceneLabel).join(" · ")}</span><span className={crossAudienceLabels.length ? "is-cross-audience" : undefined}>{crossAudienceLabels.length ? (outfit.audience === "mens" ? "女装" : "男装") : outfit.audience === "mens" ? "男装" : "女装"}</span></div>
      <div className="library-actions">
        <button type="button" aria-pressed={outfit.in_pool} className={`library-toggle-button${outfit.in_pool ? " is-active" : ""}`} onClick={() => void togglePersonalRecommendation(outfit)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 8.5 10 3.5c.7 0 1.3.6 1.3 1.4v3h3.3c1.1 0 1.8 1 1.5 2l-1.2 5c-.2.7-.8 1.2-1.5 1.2H7.5V8.5ZM4 8.5h3.5v7.6H4V8.5Z" /></svg><span>{outfit.in_pool ? "移出个人首页推荐" : "设为个人首页推荐"}</span></button>
        <div className="library-card-primary-actions"><button className="library-delete-button" onClick={() => setDeleteTarget(outfit)}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 6h12M8 3.5h4M6 6l.7 10h6.6L14 6M8.5 9v4.5M11.5 9v4.5" /></svg><span>删除穿搭</span></button><Link className="library-detail-button" href={`/outfit/${outfit.id}`}><span>查看详情</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 10h12M11 5.5l4.5 4.5-4.5 4.5" /></svg></Link></div>
      </div>
    </article>;
  }

  return <main className="paper-page library-paper">
    <div className="library-toolbar"><Link href="/inspiration" className="sunshine-button library-upload-button"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 13V3m0 0L6.5 6.5M10 3l3.5 3.5M4 11.5V16h12v-4.5" /></svg><span>上传穿搭参考</span></Link></div>
    {status === "loading" && <section className="paper-loading"><div /><div /><div /></section>}
    {status === "error" && <section className="paper-state"><h2>穿搭灵感暂时打不开</h2><p>{message}</p><button className="sunshine-button" onClick={() => void load()}>重新加载</button></section>}
    {status === "success" && <>
      <section className="library-section">
        <div className="library-section-head"><div><h1>个人首页推荐 <span>{poolOutfits.length} 套</span></h1><p><span className="library-highlight-copy">符合当天的天气和场景时，会出现在首页推荐里。</span></p></div></div>
        <div className="library-grid">{poolOutfits.length ? poolOutfits.map(outfitCard) : <Link className="library-empty" href="/inspiration"><div><b aria-hidden="true">＋</b><strong>上传穿搭参考</strong></div></Link>}</div>
      </section>
      <section className="library-section">
        <div className="library-section-head"><div><h1>全部穿搭 <span>{outfits.length} 套</span></h1><p><span className="library-highlight-copy">账号下的所有穿搭都在这里，设为个人首页推荐后仍会保留。</span></p></div></div>
        <div className="library-grid">{outfits.length ? outfits.map(outfitCard) : <Link className="library-empty" href="/inspiration"><div><b aria-hidden="true">＋</b><strong>上传穿搭参考</strong></div></Link>}</div>
      </section>
    </>}
    {message && status === "success" && <p className="inline-message">{message}</p>}
    {deleteTarget && <div
      className="library-delete-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !deleting) setDeleteTarget(null);
      }}
    >
      <section
        className="library-delete-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="library-delete-title"
        aria-describedby="library-delete-description"
      >
        <button className="library-delete-close" type="button" aria-label="关闭删除确认" disabled={deleting} onClick={() => setDeleteTarget(null)}>
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" /></svg>
        </button>
        <h2 id="library-delete-title">确认删除这套穿搭？</h2>
        <p id="library-delete-description">删除“{deleteTarget.label}”后，它会同时从“个人首页推荐”和“全部穿搭”中消失，且无法恢复。</p>
        <div className="library-delete-actions">
          <button type="button" className="library-delete-cancel" disabled={deleting} autoFocus onClick={() => setDeleteTarget(null)}>取消</button>
          <button type="button" className="library-delete-confirm" disabled={deleting} onClick={() => void remove(deleteTarget)}>{deleting ? "正在删除…" : "确认删除"}</button>
        </div>
      </section>
    </div>}
  </main>;
}

function sceneLabel(value: string) { return ({ commute: "通勤", date: "约会", travel: "出行" } as Record<string, string>)[value] ?? value; }
function thicknessLabel(value: string) { return ({ thin: "薄款", regular: "常规", thick: "厚款" } as Record<string, string>)[value] ?? value; }
