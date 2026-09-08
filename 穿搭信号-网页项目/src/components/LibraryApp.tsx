/* eslint-disable @next/next/no-img-element */
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiAsset, apiJson } from "@/lib/backend-api";
import type { Outfit, SceneId, SeasonId, StyleId } from "@/domain/backend";
import { displayOutfitLabel } from "@/domain/outfit-label";

type DiscoveryTab = "all" | "mine";
const DISCOVERY_SEASON_STORAGE_KEY = "wearcue_discovery_season_v1";

const seasonOptions: Array<{ value: "all" | SeasonId; label: string }> = [
  { value: "all", label: "全部季节" }, { value: "spring-autumn", label: "春秋" },
  { value: "summer", label: "夏季" }, { value: "winter", label: "冬季" },
];
const sceneOptions: Array<{ value: "all" | SceneId; label: string }> = [
  { value: "all", label: "全部场景" }, { value: "commute", label: "通勤" },
  { value: "date", label: "约会" }, { value: "travel", label: "出行" },
];
const styleOptions: Array<{ value: "all" | StyleId; label: string }> = [
  { value: "all", label: "全部" }, { value: "minimal", label: "简约" },
  { value: "sport", label: "运动" }, { value: "outdoor", label: "户外" },
];

export function currentSeason(month = new Date().getMonth() + 1): SeasonId {
  if (month >= 6 && month <= 8) return "summer";
  if (month === 12 || month <= 2) return "winter";
  return "spring-autumn";
}

export function storedDiscoverySeason(
  storage: Pick<Storage, "getItem">,
  fallback: SeasonId = currentSeason(),
): "all" | SeasonId {
  try {
    const stored = storage.getItem(DISCOVERY_SEASON_STORAGE_KEY);
    return seasonOptions.some((option) => option.value === stored) ? stored as "all" | SeasonId : fallback;
  } catch {
    return fallback;
  }
}

export function LibraryApp() {
  const router = useRouter();
  const [tab, setTab] = useState<DiscoveryTab>("all");
  const [season, setSeason] = useState<"all" | SeasonId>(() => currentSeason());
  const [seasonRestored, setSeasonRestored] = useState(false);
  const [scene, setScene] = useState<"all" | SceneId>("all");
  const [style, setStyle] = useState<"all" | StyleId>("all");
  const [openFilter, setOpenFilter] = useState<"season" | "scene" | null>(null);
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [tabCounts, setTabCounts] = useState<Record<DiscoveryTab, number | null>>({ all: null, mine: null });
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Outfit | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async (showLoading = true) => {
    if (showLoading) setStatus("loading");
    setMessage("");
    const paramsFor = (targetTab: DiscoveryTab) => {
      const params = new URLSearchParams({ tab: targetTab });
      if (season !== "all") params.set("season", season);
      if (scene !== "all") params.set("scene", scene);
      if (style !== "all") params.set("style", style);
      return params;
    };
    try {
      const [allOutfits, mineOutfits] = await Promise.all([
        apiJson<Outfit[]>(`/outfits?${paramsFor("all")}`),
        apiJson<Outfit[]>(`/outfits?${paramsFor("mine")}`),
      ]);
      setTabCounts({ all: allOutfits.length, mine: mineOutfits.length });
      setOutfits(tab === "all" ? allOutfits : mineOutfits);
      setStatus("success");
    }
    catch (error) { setMessage(error instanceof Error ? error.message : "穿搭灵感加载失败"); setStatus("error"); }
  }, [scene, season, style, tab]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSeason(storedDiscoverySeason(window.sessionStorage));
      setSeasonRestored(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!seasonRestored) return;
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load, seasonRestored]);
  useEffect(() => {
    if (!deleteTarget) return;
    function closeOnEscape(event: KeyboardEvent) { if (event.key === "Escape" && !deleting) setDeleteTarget(null); }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [deleteTarget, deleting]);
  useEffect(() => {
    function closeFilter(event: PointerEvent) {
      if (!(event.target as Element).closest("[data-discovery-select]")) setOpenFilter(null);
    }
    function closeFilterOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenFilter(null);
    }
    document.addEventListener("pointerdown", closeFilter);
    window.addEventListener("keydown", closeFilterOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeFilter);
      window.removeEventListener("keydown", closeFilterOnEscape);
    };
  }, []);

  async function updateStatus(outfit: Outfit, patch: { in_pool?: boolean; favorite?: boolean }) {
    try {
      const updated = await apiJson<Outfit>(`/outfits/${outfit.id}/status`, { method: "POST", body: JSON.stringify(patch) });
      if (tab === "mine" && outfit.source === "system" && patch.favorite === false) {
        setOutfits((current) => current.filter((item) => item.id !== outfit.id));
      } else {
        setOutfits((current) => current.map((item) => item.id === updated.id ? updated : item));
      }
      await load(false);
    } catch (error) { setMessage(error instanceof Error ? error.message : "状态更新失败"); }
  }

  async function remove(outfit: Outfit) {
    setDeleting(true);
    try {
      await apiJson<{ deleted: boolean }>(`/outfits/${outfit.id}`, { method: "DELETE" });
      setOutfits((current) => current.filter((item) => item.id !== outfit.id)); setDeleteTarget(null);
      await load(false);
    } catch (error) { setMessage(error instanceof Error ? error.message : "删除失败"); }
    finally { setDeleting(false); }
  }

  function outfitCard(outfit: Outfit) {
    const displayLabel = displayOutfitLabel(outfit.label);
    const fallbackImageUrl = `/images/example_${outfit.audience}_ai.jpg`;
    const imageUrl = outfit.inspiration_id
      ? apiAsset(`/inspirations/${outfit.inspiration_id}/image?size=medium`)
      : outfit.image_url ? apiAsset(outfit.image_url) : fallbackImageUrl;
    return <article className="library-card discovery-card" key={outfit.id} onClick={(event) => {
      if ((event.target as HTMLElement).closest("a, button")) return;
      router.push(`/outfit/${outfit.id}?from=closet`);
    }}>
      <Link className="discovery-card-visual" href={`/outfit/${outfit.id}?from=closet`}>
        <img src={imageUrl} alt={`${displayLabel}完整穿搭`} onError={(event) => {
          if (event.currentTarget.src.endsWith(fallbackImageUrl)) return;
          event.currentTarget.src = fallbackImageUrl;
        }} />
        <span className="discovery-card-primary-tags"><b>{sceneLabel(outfit.scene_ids[0])}</b><b>{styleLabel(outfit.style_tags[0])}</b></span>
      </Link>
      <div className="discovery-card-overlay">
        <span className="discovery-card-overlay-blur" aria-hidden="true" />
        <div className="library-card-head">
          <span className={`library-card-source${outfit.source === "system" ? " is-system" : ""}`}>{outfit.source === "system" ? "系统推荐" : "我的穿搭"}</span>
          <h2 title={displayLabel}>{displayLabel}</h2>
          <div className="discovery-card-meta">
            <p className="discovery-card-secondary"><span>{seasonLabel(outfit.season)} · {audienceLabel(outfit.audience)}{outfit.style_tags[1] ? ` · ${styleLabel(outfit.style_tags[1])}` : ""}</span><span>{outfit.suitable_min}～{outfit.suitable_max}℃</span></p>
          </div>
        </div>
        <div className="library-actions discovery-card-actions">
          {outfit.source === "system"
            ? <button type="button" aria-label={outfit.favorite ? "取消喜欢" : "喜欢"} aria-pressed={outfit.favorite} className={`library-toggle-button is-favorite${outfit.favorite ? " is-active" : ""}`} onClick={() => void updateStatus(outfit, { favorite: !outfit.favorite })}><HeartIcon /></button>
            : <button type="button" aria-label={outfit.in_pool ? "移出首页推荐" : "加入首页推荐"} aria-pressed={outfit.in_pool} className={`library-toggle-button is-home${outfit.in_pool ? " is-active" : ""}`} onClick={() => void updateStatus(outfit, { in_pool: !outfit.in_pool })}><HeartIcon /></button>}
          <div className="library-card-primary-actions"><button className="library-delete-button" type="button" aria-label={`删除${displayLabel}`} onClick={() => setDeleteTarget(outfit)}><TrashIcon /></button><Link className="library-detail-button" href={`/outfit/${outfit.id}?from=closet`} aria-label={`查看${displayLabel}详情`}><span className="library-detail-label">查看详情</span><span className="library-detail-icon" aria-hidden="true">→</span></Link></div>
        </div>
      </div>
    </article>;
  }

  return <main className="paper-page library-paper discovery-paper">
    <h1 className="sr-only">穿搭灵感</h1>
    <div className="discovery-tabs-sticky">
      <div className="discovery-tabs-sticky-inner">
        <div className="discovery-tabs" role="tablist" aria-label="穿搭范围">
          <button role="tab" aria-selected={tab === "all"} className={tab === "all" ? "active" : ""} onClick={() => setTab("all")}><span>全部穿搭</span><small>{tabCounts.all ?? "—"}套</small></button>
          <button role="tab" aria-selected={tab === "mine"} className={tab === "mine" ? "active" : ""} onClick={() => setTab("mine")}><span>我的穿搭</span><small>{tabCounts.mine ?? "—"}套</small></button>
        </div>
      </div>
    </div>
    <section className="discovery-filters" aria-label="穿搭筛选">
      <div className="discovery-filter-row">
        <DiscoverySelect label="季节" value={season} options={seasonOptions} open={openFilter === "season"} onToggle={() => setOpenFilter((current) => current === "season" ? null : "season")} onChange={(value) => {
          const next = value as "all" | SeasonId;
          setSeason(next);
          try { window.sessionStorage.setItem(DISCOVERY_SEASON_STORAGE_KEY, next); } catch { /* 无会话存储时仍可正常筛选 */ }
          setOpenFilter(null);
        }} />
        <DiscoverySelect label="场景" value={scene} options={sceneOptions} open={openFilter === "scene"} onToggle={() => setOpenFilter((current) => current === "scene" ? null : "scene")} onChange={(value) => { setScene(value as "all" | SceneId); setOpenFilter(null); }} />
        <div className="discovery-style-filter" aria-label="风格">{styleOptions.map((option) => <button type="button" key={option.value} aria-pressed={style === option.value} className={style === option.value ? "active" : ""} onClick={() => setStyle(option.value)}>{option.label}</button>)}</div>
      </div>
    </section>

    {status === "loading" && <section className="paper-loading"><div /><div /><div /></section>}
    {status === "error" && <section className="paper-state"><h2>穿搭灵感暂时打不开</h2><p>{message}</p><button className="sunshine-button" onClick={() => void load()}>重新加载</button></section>}
    {status === "success" && <section className="library-section">{outfits.length ? <div className="library-grid">{outfits.map(outfitCard)}</div> : tab === "mine" ? <div className="discovery-empty"><h2>还没有符合筛选条件的穿搭</h2><p>上传自己的穿搭，或去全部穿搭标记喜欢。</p><div><Link className="sunshine-button" href="/inspiration">上传穿搭</Link><button className="ghost-button" type="button" onClick={() => setTab("all")}>去全部穿搭看看</button></div></div> : <div className="discovery-empty"><h2>当前筛选暂无穿搭</h2><p>可以调整筛选条件，或上传一套自己的穿搭。</p><Link className="sunshine-button" href="/inspiration">上传穿搭</Link></div>}</section>}
    {message && status === "success" && <p className="inline-message">{message}</p>}
    <Link className="discovery-upload-fab" href="/inspiration" aria-label="上传穿搭灵感"><span className="discovery-upload-fab-tip">上传穿搭灵感</span><span className="discovery-upload-fab-plus" aria-hidden="true">＋</span></Link>

    {deleteTarget && <div className="library-delete-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !deleting) setDeleteTarget(null); }}><section className="library-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="library-delete-title" aria-describedby="library-delete-description"><button className="library-delete-close" type="button" aria-label="关闭删除确认" disabled={deleting} onClick={() => setDeleteTarget(null)}>×</button><h2 id="library-delete-title">确认删除这套穿搭？</h2><p id="library-delete-description">{deleteTarget.source === "system" ? `“${deleteTarget.label}”会从你的穿搭库中移除，不影响其他用户。` : `删除“${deleteTarget.label}”后无法恢复。`}</p><div className="library-delete-actions"><button type="button" className="library-delete-cancel" disabled={deleting} autoFocus onClick={() => setDeleteTarget(null)}>取消</button><button type="button" className="library-delete-confirm" disabled={deleting} onClick={() => void remove(deleteTarget)}>{deleting ? "正在删除…" : "确认删除"}</button></div></section></div>}
  </main>;
}

function HeartIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 16.2 3.8 10A3.8 3.8 0 0 1 9.2 4.6l.8.8.8-.8A3.8 3.8 0 0 1 16.2 10L10 16.2Z" /></svg>; }
function TrashIcon() { return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 6.2h11M8 3.8h4l.7 2.4H7.3L8 3.8Zm-2 2.4.7 10h6.6l.7-10M8.4 8.7v4.8m3.2-4.8v4.8" /></svg>; }
function DiscoverySelect({ label, value, options, open, onToggle, onChange }: { label: string; value: string; options: Array<{ value: string; label: string }>; open: boolean; onToggle: () => void; onChange: (value: string) => void }) {
  const selected = options.find((option) => option.value === value) ?? options[0];
  return <div className={`discovery-select${open ? " is-open" : ""}`} data-discovery-select>
    <button className="discovery-select-trigger" type="button" aria-label={`${label}：${selected.label}`} aria-haspopup="listbox" aria-expanded={open} onClick={onToggle}><span>{selected.label}</span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="m2.5 4.5 3.5 3 3.5-3" /></svg></button>
    {open && <div className="discovery-select-menu" role="listbox" aria-label={`选择${label}`}>{options.map((option) => <button type="button" role="option" aria-selected={option.value === value} className={option.value === value ? "is-selected" : ""} key={option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>}
  </div>;
}
function sceneLabel(value?: string) { return ({ commute: "通勤", date: "约会", travel: "出行" } as Record<string, string>)[value ?? ""] ?? "通勤"; }
function styleLabel(value?: string) { return ({ minimal: "简约", sport: "运动", outdoor: "户外" } as Record<string, string>)[value ?? ""] ?? "简约"; }
function seasonLabel(value: SeasonId) { return ({ "spring-autumn": "春秋", summer: "夏季", winter: "冬季" } as const)[value]; }
function audienceLabel(value: Outfit["audience"]) { return value === "womens" ? "女装" : "男装"; }
