/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { OutfitIcon } from "./OutfitIcon";
import { ApiError, apiForm, apiJson } from "@/lib/backend-api";
import type { Audience, BackendSettings, Inspiration, Outfit, OutfitComponent, SceneId } from "@/domain/backend";
import { crossAudienceGarmentLabels, garmentIconsFor, resolveGarmentIcon } from "@/config/garment-icon-map";

const sceneOptions: Array<{ id: SceneId; label: string }> = [
  { id: "commute", label: "通勤" }, { id: "date", label: "约会" }, { id: "travel", label: "出行" },
];
const thicknessOptions = [{ value: "thin", label: "薄款" }, { value: "regular", label: "常规" }, { value: "thick", label: "厚款" }] as const;
const seasonOptions = [
  { value: "spring-autumn", label: "春秋", minimum: 10, maximum: 24 },
  { value: "winter", label: "冬", minimum: -10, maximum: 10 },
  { value: "summer", label: "夏", minimum: 25, maximum: 40 },
] as const;
const recognitionSteps = [
  "AI 正在识别服装款式、颜色与薄厚",
  "AI 正在补全缺失单品并匹配图标库",
  "AI 正在生成场景、温度与快速复刻建议",
];

function normalizeComponent(item: OutfitComponent, audience: Audience): OutfitComponent {
  const definition = resolveGarmentIcon(item, audience);
  return definition ? { ...item, asset_key: definition.iconKey } : item;
}

function recognitionAudience(result: Inspiration["result"], fallback: Audience): Audience {
  if (result.garment_audience === "mens" || result.garment_audience === "womens") return result.garment_audience;
  const womenOnlyKeys = new Set(["top_camisole", "bottom_skirt_short", "bottom_skirt_long", "onepiece_dress", "shoe_pump"]);
  return result.components?.some((item) => womenOnlyKeys.has((item.asset_key ?? "").replace(/^womens_/, ""))) ? "womens" : fallback;
}

export function recognitionOutfitName(result: Inspiration["result"], audience: Audience) {
  const scene = result.suggested_scenes?.[0] ?? "commute";
  const names: Record<Audience, Record<SceneId, string>> = {
    mens: { commute: "利落通勤", date: "帅气约会", travel: "活力出行" },
    womens: { commute: "简约通勤", date: "精致约会", travel: "轻旅出行" },
  };
  return names[audience][scene];
}

function thicknessLabel(value: OutfitComponent["thickness"]) {
  return thicknessOptions.find((option) => option.value === value)?.label ?? "常规";
}

function applySuggestions(result: Inspiration["result"], setScenes: (value: SceneId[]) => void, setRange: (value: { minimum: number; maximum: number }) => void, setSeason: (value: (typeof seasonOptions)[number]["value"]) => void) {
  if (result.suggested_scenes?.length) setScenes(result.suggested_scenes);
  if (result.suggested_temperature) setRange({ minimum: result.suggested_temperature.min, maximum: result.suggested_temperature.max });
  if (result.suggested_season) setSeason(result.suggested_season);
}

export function InspirationApp() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [inspiration, setInspiration] = useState<Inspiration | null>(null);
  const [savedOutfit, setSavedOutfit] = useState<Outfit | null>(null);
  const [components, setComponents] = useState<OutfitComponent[]>([]);
  const [audience, setAudience] = useState<Audience>("mens");
  const [garmentAudience, setGarmentAudience] = useState<Audience>("mens");
  const [label, setLabel] = useState("我的穿搭");
  const [scenes, setScenes] = useState<SceneId[]>(["commute"]);
  const [suitableRange, setSuitableRange] = useState({ minimum: 10, maximum: 30 });
  const [season, setSeason] = useState<(typeof seasonOptions)[number]["value"]>("spring-autumn");
  const [stage, setStage] = useState<"idle" | "uploading" | "analysing" | "review" | "saving" | "error">("idle");
  const [message, setMessage] = useState("");
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const [recognitionStep, setRecognitionStep] = useState(0);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [styleMenuOpen, setStyleMenuOpen] = useState(false);
  const [crossAudienceAcknowledged, setCrossAudienceAcknowledged] = useState(false);
  const [remainingAnalyses, setRemainingAnalyses] = useState<number | null>(null);
  const [generatingName, setGeneratingName] = useState(false);

  useEffect(() => {
    void apiJson<BackendSettings>("/settings").then((settings) => { setAudience(settings.audience); setGarmentAudience(settings.audience); }).catch(() => undefined);
  }, []);

  useEffect(() => {
    void apiJson<{ remaining: number }>("/inspirations/analysis-quota").then((quota) => { setRemainingAnalyses(quota.remaining); }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!inspiration) return;
    let active = true;
    void apiJson<Outfit[]>("/outfits")
      .then((outfits) => { if (active) setSavedOutfit(outfits.find((outfit) => outfit.inspiration_id === inspiration.id) ?? null); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [inspiration]);

  useEffect(() => {
    if (stage !== "analysing") return;
    const timer = window.setInterval(() => setRecognitionStep((current) => Math.min(current + 1, recognitionSteps.length - 1)), 5500);
    return () => window.clearInterval(timer);
  }, [stage]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function chooseFile(next?: File) {
    if (!next) return;
    if (!/^image\/(jpeg|png|webp)$/.test(next.type)) { setMessage("请选择 JPEG、PNG 或 WebP 图片"); setStage("error"); return; }
    if (next.size > 5 * 1024 * 1024) { setMessage("图片不能超过 5MB"); setStage("error"); return; }
    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setPreview(URL.createObjectURL(next));
    setGarmentAudience(audience);
    setLabel("我的穿搭");
    setSuitableRange({ minimum: 10, maximum: 30 }); setSeason("spring-autumn");
    setInspiration(null); setSavedOutfit(null); setComponents([]); setMessage(""); setStage("idle");
    setCrossAudienceAcknowledged(false);
  }

  function chooseAnotherImage() {
    if (!inputRef.current) return;
    inputRef.current.value = "";
    inputRef.current.click();
  }

  function clearSelectedImage() {
    if (preview) URL.revokeObjectURL(preview);
    if (inputRef.current) inputRef.current.value = "";
    setPreview(""); setFile(null); setInspiration(null); setSavedOutfit(null); setComponents([]);
    setGarmentAudience(audience);
    setMessage(""); setEditingIndex(null); setStage("idle");
    setCrossAudienceAcknowledged(false);
  }

  async function analyse(force = false) {
    if (!file) return;
    setMessage("");
    setRecognitionStep(0);
    try {
      setStage("uploading");
      const form = new FormData();
      form.append("image", file);
      const uploaded = await apiForm<Inspiration>("/inspirations/upload", form);
      setInspiration(uploaded);
      if (!force && uploaded.status === "needs_review" && uploaded.result.components?.length && uploaded.result.outfit_analysis?.summary && uploaded.result.components.every((item) => typeof item.suggested === "boolean")) {
        const detectedAudience = recognitionAudience(uploaded.result, audience);
        const cachedComponents = uploaded.result.components.map((item) => normalizeComponent(item, detectedAudience));
        setGarmentAudience(detectedAudience);
        setComponents(cachedComponents);
        setLabel(recognitionOutfitName(uploaded.result, detectedAudience));
        applySuggestions(uploaded.result, setScenes, setSuitableRange, setSeason);
        setStage("review");
        return;
      }
      setStage("analysing");
      const analysed = await apiJson<Inspiration & { remaining_analyses?: number }>(`/inspirations/${uploaded.id}/analyze`, { method: "POST" });
      if (typeof analysed.remaining_analyses === "number") setRemainingAnalyses(analysed.remaining_analyses);
      const detectedAudience = recognitionAudience(analysed.result, audience);
      const nextComponents = (analysed.result.components ?? []).map((item) => normalizeComponent(item, detectedAudience));
      setGarmentAudience(detectedAudience);
      setInspiration(analysed);
      setComponents(nextComponents);
      setLabel(recognitionOutfitName(analysed.result, detectedAudience));
      applySuggestions(analysed.result, setScenes, setSuitableRange, setSeason);
      setStage("review");
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) setRemainingAnalyses(0);
      setMessage(error instanceof Error ? error.message : "图片识别失败");
      setStage("error");
    }
  }

  async function generateName() {
    if (!inspiration) return;
    setGeneratingName(true); setMessage("");
    try {
      const result = await apiJson<{ name: string }>(`/inspirations/${inspiration.id}/generate-name`, { method: "POST" });
      setLabel(result.name.slice(0, 30));
      setInspiration((current) => current ? { ...current, result: { ...current.result, ai_generated_name: result.name } } : current);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "AI 名称生成失败");
    } finally {
      setGeneratingName(false);
    }
  }

  function toggleScene(scene: SceneId) {
    setScenes((current) => current.includes(scene) ? current.filter((item) => item !== scene) : [...current, scene]);
  }

  function adjustTemperature(key: "minimum" | "maximum", amount: number) {
    setSuitableRange((current) => ({ ...current, [key]: Math.max(-30, Math.min(50, current[key] + amount)) }));
  }

  function componentEditor(item: OutfitComponent, index: number) {
    return <article key={`${item.slot}-${index}`} className="component-row">
      {item.suggested && <span className="suggested-component-badge">AI 补充</span>}
      <OutfitIcon item={item} audience={garmentAudience} />
      <div className="component-result"><strong>{item.variant_type}</strong><span>{item.color_name}、{thicknessLabel(item.thickness)}</span></div>
      <button className="component-edit-button" type="button" onClick={() => { setStyleMenuOpen(false); setEditingIndex(index); }}>编辑</button>
    </article>;
  }

  const editingComponent = editingIndex === null ? null : components[editingIndex];
  const updateEditingComponent = (patch: Partial<OutfitComponent>) => {
    if (editingIndex === null) return;
    setComponents((current) => current.map((item, index) => index === editingIndex ? { ...item, ...patch } : item));
  };

  async function save(addToPersonalRecommendation: boolean) {
    if (!inspiration || !components.length || !scenes.length) return;
    if (!addToPersonalRecommendation && savedOutfit) {
      setToast({ message: "已保存到全部穿搭", tone: "success" });
      return;
    }
    const removing = addToPersonalRecommendation && Boolean(savedOutfit?.in_pool);
    setStage("saving"); setMessage("");
    try {
      const saved = removing && savedOutfit
        ? await apiJson<Outfit>(`/outfits/${savedOutfit.id}/status`, { method: "POST", body: JSON.stringify({ in_pool: false }) })
        : await apiJson<Outfit>(`/inspirations/${inspiration.id}/confirm`, {
          method: "POST",
          body: JSON.stringify({
            label: label.trim() || "我的穿搭", audience, components, scene_ids: scenes,
            suitable_min: suitableRange.minimum, suitable_max: suitableRange.maximum,
            in_pool: addToPersonalRecommendation || Boolean(savedOutfit?.in_pool),
            outfit_analysis: inspiration.result.outfit_analysis,
            replication_guide: inspiration.result.replication_guide,
          }),
        });
      setSavedOutfit(saved);
      setStage("review");
      setToast({ message: removing ? "已移出个人首页推荐，穿搭仍保留在全部穿搭" : addToPersonalRecommendation ? "已加入个人首页推荐" : "已保存到全部穿搭", tone: "success" });
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : "保存失败", tone: "error" }); setStage("review");
    }
  }

  const crossAudienceLabels = crossAudienceGarmentLabels(components, audience);
  const crossAudienceGate = crossAudienceLabels.length > 0 && !crossAudienceAcknowledged;
  const crossAudienceNotice = crossAudienceLabels.length > 0 ? <p className="cross-audience-notice" role="status"><span className="cross-audience-notice-icon" aria-hidden="true">!</span><span className="cross-audience-notice-copy">当前为{audience === "mens" ? "男装" : "女装"}账号，识别到 <strong>{garmentAudience === "womens" ? "女士服装" : "男士服装"}</strong></span></p> : null;

  return <main className="paper-page upload-paper">
    <div className="upload-layout">
      <nav className="upload-breadcrumb" aria-label="面包屑"><Link href="/closet"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="m11.5 5-5 5 5 5" /></svg><span>穿搭灵感</span></Link></nav>
      <section className="upload-source-card">
        <div className="card-caption">穿搭照片</div>
        {!preview ? <button className="paper-dropzone" onClick={chooseAnotherImage}><b>＋</b><strong>选择一张穿搭照片</strong><span className="photo-guidance">建议上传单人全身穿搭照，衣物和鞋子尽量完整入镜</span><span>JPEG · PNG · WEBP / 最大 5MB</span></button> : <div className="upload-preview"><img src={preview} alt="待识别穿搭" width={800} height={800} /><button className="upload-clear-image" type="button" aria-label="移除已选图片" title="移除图片" disabled={stage === "uploading" || stage === "analysing" || generatingName} onClick={clearSelectedImage}><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4l10 10M14 4 4 14" /></svg></button></div>}
        <input hidden ref={inputRef} name="outfit-photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseFile(event.target.files?.[0])} />
        {components.length ? <div className="source-actions">
          <button className="source-regenerate-button" type="button" aria-label="重新生成识别结果" title="重新生成识别结果" disabled={stage === "uploading" || stage === "analysing" || generatingName} onClick={() => void analyse(true)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.34 5.66M20 5v6h-6" /></svg></button>
          <button className="ghost-button source-change-button" type="button" disabled={stage === "uploading" || stage === "analysing" || generatingName} onClick={chooseAnotherImage}>识别下一张</button>
        </div> : <button className={`sunshine-button full-button${!file ? " is-empty" : ""}`} disabled={!file || stage === "uploading" || stage === "analysing"} onClick={() => void analyse()}>{stage === "uploading" ? "正在上传…" : stage === "analysing" ? "正在识别…" : "上传识别"}</button>}
        <p className="privacy-copy">AI 视觉识别每日 30 次，今日剩余 {remainingAnalyses ?? "--"} 次。</p>
      </section>

      <section className="review-card">
        <div className="section-title-row"><div className="card-caption">识别结果</div>{components.length > 0 && !crossAudienceGate && <span className="mint-chip">{components.length} 件</span>}</div>
        {!components.length ? <div className={`review-empty${stage === "idle" ? " is-idle" : stage === "uploading" || stage === "analysing" ? " is-loading" : ""}`}>
          {stage === "idle" ? <>
            <div className="review-empty-bear" aria-hidden="true"><img src="/illustrations/inspiration-bear.png" alt="" /></div>
            <h3>等待图片识别</h3>
            <p>一张照片，变成可复用穿搭。</p>
          </> : <>
            <b>{stage === "error" ? "!" : <span className="recognition-dots" aria-label="识别处理中"><i /><i /><i /></span>}</b>
            <h3>{stage === "analysing" ? "正在识别中" : stage === "uploading" ? "正在准备图片" : "识别暂时失败"}</h3>
            {stage === "analysing" ? <div className="recognition-progress" aria-live="polite">{recognitionSteps.slice(0, recognitionStep + 1).reverse().map((step, age) => <p key={step} className={age === 0 ? "is-active" : `is-age-${age}`}>{step}</p>)}</div> : <p>{stage === "error" ? "请检查提示后重新识别，已选择的图片不会丢失。" : "正在优化图片并安全上传。"}</p>}
          </>}
        </div> : crossAudienceGate ? <div className="cross-audience-gate">
          {crossAudienceNotice}
          <div className="cross-audience-gate-actions">
            <button className="ghost-button" type="button" onClick={() => setCrossAudienceAcknowledged(true)}>继续查看</button>
            <button className="sunshine-button" type="button" onClick={chooseAnotherImage}>重新上传</button>
          </div>
        </div> : <>
          {crossAudienceNotice}
          <div className="outfit-name-row">
            <label className="paper-field"><span>这套穿搭叫什么？（最多30字）</span><input value={label} onChange={(event) => setLabel(event.target.value)} maxLength={30} placeholder="例如：松弛通勤" /></label>
            <button className="ai-name-button" type="button" disabled={generatingName} onClick={() => void generateName()}>{generatingName ? "生成中…" : "AI生成"}</button>
          </div>
          <p className="outfit-name-hint">建议按“风格＋场景”命名，例如：{garmentAudience === "mens" ? "利落通勤、帅气约会、活力出行" : "简约通勤、精致约会、轻旅出行"}。</p>
          <div className="review-suggestions">
            <div className="scene-review suggestion-block"><span>建议场景</span><div className="filter-row">{sceneOptions.map((scene) => <button type="button" key={scene.id} aria-pressed={scenes.includes(scene.id)} className={scenes.includes(scene.id) ? "dark-filter" : "filter-pill"} onClick={() => toggleScene(scene.id)}>{scene.label}</button>)}</div></div>
            <div className="suggestion-block"><span>建议温度</span><div className="temperature-inputs"><label><input type="number" min="-30" max="50" value={suitableRange.minimum} onChange={(event) => setSuitableRange((current) => ({ ...current, minimum: Number(event.target.value) }))} /><b>°</b><span className="temperature-stepper"><button type="button" aria-label="提高最低温度" onClick={() => adjustTemperature("minimum", 1)}><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 7.5 6 4.5l3 3" /></svg></button><button type="button" aria-label="降低最低温度" onClick={() => adjustTemperature("minimum", -1)}><svg viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4.5 3 3 3-3" /></svg></button></span></label><i>—</i><label><input type="number" min="-30" max="50" value={suitableRange.maximum} onChange={(event) => setSuitableRange((current) => ({ ...current, maximum: Number(event.target.value) }))} /><b>°</b><span className="temperature-stepper"><button type="button" aria-label="提高最高温度" onClick={() => adjustTemperature("maximum", 1)}><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 7.5 6 4.5l3 3" /></svg></button><button type="button" aria-label="降低最高温度" onClick={() => adjustTemperature("maximum", -1)}><svg viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4.5 3 3 3-3" /></svg></button></span></label></div></div>
            <div className="suggestion-block"><span>建议季节</span><div className="season-options">{seasonOptions.map((option) => <button type="button" key={option.value} aria-pressed={season === option.value} className={season === option.value ? "active" : ""} onClick={() => { setSeason(option.value); setSuitableRange({ minimum: option.minimum, maximum: option.maximum }); }}>{option.label}</button>)}</div></div>
          </div>
          {(inspiration?.result.outfit_analysis || inspiration?.result.replication_guide) && <div className="recognition-guide" aria-label="穿搭建议与快速复刻">
            <span>穿搭建议 · 快速复刻</span>
            {inspiration.result.replication_guide && <strong>{inspiration.result.replication_guide.formula}</strong>}
            {inspiration.result.outfit_analysis && <p className="recognition-summary">{inspiration.result.outfit_analysis.summary}</p>}
            <p>{[
              ...(inspiration.result.outfit_analysis?.structure_points ?? []),
              ...(inspiration.result.outfit_analysis?.completion_advice ?? []),
              ...(inspiration.result.replication_guide?.styling_points ?? []),
            ].join(" · ")}</p>
          </div>}
          <div className="component-list">{components.map(componentEditor)}</div>
          {message && <p className="inline-message" role="alert" aria-live="polite">{message}</p>}
          <div className="save-actions">
            <div className="save-action-option"><button className={`sunshine-button${savedOutfit?.in_pool ? " is-saved" : ""}`} aria-pressed={Boolean(savedOutfit?.in_pool)} disabled={stage === "saving" || generatingName || !scenes.length || suitableRange.minimum > suitableRange.maximum} onClick={() => void save(true)}>{savedOutfit?.in_pool && <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3.5 8 3 3 6-6" /></svg>}{savedOutfit?.in_pool ? "已加入个人首页推荐" : "加入个人首页推荐"}</button><p className="privacy-copy">符合当天的天气和场景时，将在<strong>首页推荐展示</strong>。</p></div>
            <div className="save-action-option"><button className={`ghost-button${savedOutfit ? " is-saved" : ""}`} disabled={Boolean(savedOutfit) || stage === "saving" || generatingName || !scenes.length || suitableRange.minimum > suitableRange.maximum} onClick={() => void save(false)}>{savedOutfit && <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3.5 8 3 3 6-6" /></svg>}{savedOutfit ? "已保存到全部穿搭" : "保存到全部穿搭"}</button></div>
            <div className="save-action-option"><Link className="ghost-button view-inspiration-button" href="/closet">查看灵感穿搭</Link></div>
          </div>
        </>}
        {message && !components.length && <p className="inline-message" role="alert" aria-live="polite">{message}</p>}
      </section>
    </div>
    {toast && <div className={`save-toast show ${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"} aria-live={toast.tone === "error" ? "assertive" : "polite"}>
      <span className="save-toast-icon" aria-hidden="true">{toast.tone === "success" ? <svg viewBox="0 0 16 16"><path d="m3.5 8 3 3 6-6" /></svg> : <svg viewBox="0 0 16 16"><path d="M8 4.2v4.5M8 11.8v.1" /></svg>}</span>
      <span>{toast.message}</span>
    </div>}
    {editingComponent && <div className="component-editor-backdrop" role="presentation" onMouseDown={() => { setStyleMenuOpen(false); setEditingIndex(null); }}>
      <section className="component-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="component-editor-title" onKeyDown={(event) => { if (event.key === "Escape") { setStyleMenuOpen(false); setEditingIndex(null); } }} onMouseDown={(event) => event.stopPropagation()}>
        <div className="component-editor-head"><h2 id="component-editor-title">编辑单品</h2><button type="button" aria-label="关闭编辑" onClick={() => { setStyleMenuOpen(false); setEditingIndex(null); }}>×</button></div>
        <OutfitIcon item={editingComponent} audience={garmentAudience} />
        <div className="component-editor-field"><span>款式</span><div className={`component-style-select${styleMenuOpen ? " is-open" : ""}`}>
          <button className="component-style-trigger" type="button" aria-haspopup="listbox" aria-expanded={styleMenuOpen} onClick={() => setStyleMenuOpen((open) => !open)}><span>{editingComponent.variant_type}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg></button>
          {styleMenuOpen && <div className="component-style-menu" role="listbox" aria-label="选择服装款式">{garmentIconsFor(editingComponent.slot, garmentAudience).map((option) => <button type="button" role="option" aria-selected={editingComponent.asset_key === option.iconKey} className={editingComponent.asset_key === option.iconKey ? "is-selected" : ""} key={option.iconKey} onClick={() => { updateEditingComponent({ asset_key: option.iconKey, variant_type: option.label }); setStyleMenuOpen(false); }}>{option.label}</button>)}</div>}
        </div></div>
        <div className="component-editor-thickness"><span>薄厚</span><div>{thicknessOptions.map((option) => <button type="button" key={option.value} className={editingComponent.thickness === option.value ? "active" : ""} onClick={() => updateEditingComponent({ thickness: option.value })}>{option.label}</button>)}</div></div>
        <button className="sunshine-button full-button" type="button" onClick={() => { setStyleMenuOpen(false); setEditingIndex(null); }}>完成</button>
      </section>
    </div>}
  </main>;
}
