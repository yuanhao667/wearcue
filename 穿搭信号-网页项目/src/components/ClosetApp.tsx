/* eslint-disable @next/next/no-img-element */
"use client";

import type { CSSProperties, DragEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { GARMENT_ICON_BY_KEY, GARMENT_ICON_MAP, getGarmentIconPath } from "@/config/garment-icon-map";
import type { ExtractedGarment, ImageAnalysisResult, InspirationLook } from "@/domain/inspiration";
import type { GarmentThickness } from "@/domain/types";
import { prepareImage, type PreparedImage } from "@/lib/image-processing";
import { deleteInspirationLook, loadInspirationLooks, saveInspirationLook } from "@/lib/inspiration";
import { loadSettings } from "@/lib/settings";

type Collection = "mens" | "womens";
type IconStyle = CSSProperties & { "--icon-url": string; "--icon-color": string };

const thicknessOptions: Array<{ value: GarmentThickness; label: string }> = [
  { value: "thin", label: "薄款" },
  { value: "regular", label: "常规" },
  { value: "thick", label: "厚款" },
];

const analysisStages = ["读取画面", "识别衣物", "匹配图标"];

export function ClosetApp() {
  const fileInput = useRef<HTMLInputElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const [collection, setCollection] = useState<Collection>("mens");
  const [prepared, setPrepared] = useState<PreparedImage | null>(null);
  const [fileName, setFileName] = useState("");
  const [items, setItems] = useState<ExtractedGarment[]>([]);
  const [summary, setSummary] = useState("");
  const [analysisMode, setAnalysisMode] = useState<ImageAnalysisResult["mode"] | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [looks, setLooks] = useState<InspirationLook[]>([]);
  const [saveNotice, setSaveNotice] = useState("");

  useEffect(() => {
    const settings = loadSettings();
    if (settings.garmentPresentation === "mens" || settings.garmentPresentation === "womens") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollection(settings.garmentPresentation);
    }
    setLooks(loadInspirationLooks());
  }, []);

  const iconOptions = useMemo(
    () => GARMENT_ICON_MAP.filter((item) => item.collection === collection || item.collection === "accessory"),
    [collection],
  );

  async function selectFile(file?: File) {
    if (!file) return;
    setError("");
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      setError("请选择 JPEG、PNG 或 WebP 图片");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("图片不能超过 5MB");
      return;
    }
    try {
      const next = await prepareImage(file);
      setPrepared(next);
      setFileName(file.name);
      setItems([]);
      setSummary("");
      setAnalysisMode(null);
      setEditingId(null);
      setTitle(file.name.replace(/\.[^.]+$/, "").slice(0, 30));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "图片处理失败");
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    void selectFile(event.dataTransfer.files[0]);
  }

  async function analyse() {
    if (!prepared) return;
    setAnalysing(true);
    setAnalysisStage(0);
    setError("");
    const timer = window.setInterval(() => setAnalysisStage((current) => Math.min(current + 1, analysisStages.length - 1)), 650);
    try {
      const response = await fetch("/api/analyze-outfit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageDataUrl: prepared.dataUrl, collection, dominantColor: prepared.dominantColor, fileName }),
      });
      const payload = await response.json() as ImageAnalysisResult & { error?: string };
      if (!response.ok) throw new Error(payload.error || "图片分析失败");
      setItems(payload.items);
      setSummary(payload.summary);
      setAnalysisMode(payload.mode);
      window.setTimeout(() => editorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "图片分析失败");
    } finally {
      window.clearInterval(timer);
      setAnalysing(false);
    }
  }

  function updateItem(id: string, patch: Partial<ExtractedGarment>) {
    setItems((current) => current.map((item) => {
      if (item.id !== id) return item;
      if (patch.iconKey) {
        const definition = GARMENT_ICON_BY_KEY.get(patch.iconKey);
        return definition ? { ...item, ...patch, label: definition.label, category: definition.category } : item;
      }
      return { ...item, ...patch };
    }));
  }

  function addItem() {
    const definition = iconOptions[0];
    if (!definition) return;
    setItems((current) => [...current, {
      id: crypto.randomUUID(),
      iconKey: definition.iconKey,
      label: definition.label,
      category: definition.category,
      colorName: "黑色",
      colorHex: "#171918",
      thickness: "regular",
      confidence: 1,
      note: "手动添加",
    }]);
  }

  function saveLook(destination: "inspiration" | "recommendation") {
    if (!prepared || !items.length) {
      setError("请先上传图片并至少保留一件衣物");
      return;
    }
    const now = new Date().toISOString();
    const previous = editingId ? looks.find((look) => look.id === editingId) : undefined;
    const look: InspirationLook = {
      id: editingId ?? crypto.randomUUID(),
      title: title.trim() || `穿搭灵感 ${looks.length + 1}`,
      note: note.trim(),
      imageDataUrl: prepared.dataUrl,
      collection,
      createdAt: previous?.createdAt ?? now,
      updatedAt: now,
      items,
      recommendationEnabled: destination === "recommendation" ? true : previous?.recommendationEnabled,
    };
    try {
      setLooks(saveInspirationLook(look));
      setEditingId(look.id);
      setSaveNotice(destination === "recommendation" ? "已加入每日推荐，首页会按气温为你匹配" : "方案已保存到灵感库");
      window.setTimeout(() => setSaveNotice(""), 2200);
    } catch {
      setError("本机存储空间不足。请删除一条旧灵感，或换一张体积更小的图片。 ");
    }
  }

  function editLook(look: InspirationLook) {
    setPrepared({ dataUrl: look.imageDataUrl, dominantColor: look.items[0]?.colorHex ?? "#777b78", width: 0, height: 0 });
    setFileName(look.title);
    setCollection(look.collection);
    setItems(look.items);
    setTitle(look.title);
    setNote(look.note);
    setEditingId(look.id);
    setAnalysisMode(null);
    setSummary("已从灵感库载入，可以继续修改后覆盖保存。");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function removeLook(id: string) {
    if (!window.confirm("确定从灵感库删除这套方案吗？")) return;
    setLooks(deleteInspirationLook(id));
    if (editingId === id) setEditingId(null);
  }

  function toggleRecommendation(look: InspirationLook) {
    const updated: InspirationLook = {
      ...look,
      recommendationEnabled: !look.recommendationEnabled,
      updatedAt: new Date().toISOString(),
    };
    setLooks(saveInspirationLook(updated));
    setSaveNotice(updated.recommendationEnabled ? "已加入每日推荐" : "已从每日推荐移出");
    window.setTimeout(() => setSaveNotice(""), 1800);
  }

  return (
    <main className="page-shell closet-page">
      <section className="closet-intro">
        <div>
          <span className="eyebrow">IMAGE → ICON → LOOK</span>
          <h1>把一张穿搭照，变成可复用的方案</h1>
          <p>上传图片，确认系统提取的服装 icon、颜色和薄厚，再保存进你的灵感库。</p>
        </div>
        <div className="workflow-steps" aria-label="工作流程">
          <span className={prepared ? "done" : "active"}><b>01</b> 上传</span>
          <i />
          <span className={items.length ? "done" : prepared ? "active" : ""}><b>02</b> 提取</span>
          <i />
          <span className={editingId ? "done" : items.length ? "active" : ""}><b>03</b> 保存</span>
        </div>
      </section>

      <div className="closet-workflow">
        <section className="upload-panel">
          <div className="panel-heading">
            <div><span className="card-index">01 / SOURCE</span><h2>上传穿搭图片</h2></div>
            {prepared && <button className="text-button" onClick={() => fileInput.current?.click()}>更换图片</button>}
          </div>

          {!prepared ? (
            <label
              className={`photo-dropzone ${dragging ? "dragging" : ""}`}
              htmlFor="closet-photo-input"
              onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <div className="upload-symbol"><span>＋</span><i /></div>
              <strong>拖入图片，或点击选择</strong>
              <p>建议使用全身或平铺穿搭照，衣物边界越清楚，识别越准确。</p>
              <small>JPEG · PNG · WEBP / 最大 5MB</small>
            </label>
          ) : (
            <div className="uploaded-photo">
              <img src={prepared.dataUrl} alt="待分析的穿搭图片" />
              <div className="photo-meta">
                <span><i style={{ background: prepared.dominantColor }} />图片主色</span>
                <small>{fileName}</small>
              </div>
              {analysing && (
                <div className="analysis-overlay" aria-live="polite">
                  <div className="scan-line" />
                  <span>{String(analysisStage + 1).padStart(2, "0")} / 03</span>
                  <strong>{analysisStages[analysisStage]}</strong>
                </div>
              )}
            </div>
          )}
          <input id="closet-photo-input" ref={fileInput} hidden type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => void selectFile(event.target.files?.[0])} />

          <div className="collection-choice">
            <span>使用哪套衣物映射？</span>
            <div>
              <button className={collection === "mens" ? "active" : ""} onClick={() => setCollection("mens")} disabled={analysing}>男性衣物库</button>
              <button className={collection === "womens" ? "active" : ""} onClick={() => setCollection("womens")} disabled={analysing}>女性衣物库</button>
            </div>
          </div>

          <button className="analyse-button" disabled={!prepared || analysing} onClick={() => void analyse()}>
            <span>{analysing ? "正在分析图片" : items.length ? "重新分析图片" : "分析图片并提取 icon"}</span>
            <b>{analysing ? "···" : "→"}</b>
          </button>
          <p className="upload-privacy">图片会先在浏览器压缩；没有启用模型密钥时不会上传到第三方。</p>
        </section>

        <section className="extraction-panel" ref={editorRef}>
          <div className="panel-heading">
            <div><span className="card-index">02 / EXTRACTION</span><h2>确认识别结果</h2></div>
            {!!items.length && <span className="result-count">{items.length} ITEMS</span>}
          </div>

          {!items.length ? (
            <div className="extraction-empty">
              <div className="empty-orbit"><span>SVG</span></div>
              <strong>{prepared ? "图片已就绪" : "等待一张图片"}</strong>
              <p>{prepared ? "点击左侧分析按钮，系统会把衣物映射成可编辑的 SVG icon。" : "识别出的服装品类、颜色和薄厚会出现在这里。"}</p>
            </div>
          ) : (
            <>
              <div className={`analysis-note ${analysisMode === "demo" ? "demo" : "ai"}`}>
                <span>{analysisMode === "demo" ? "DEMO" : analysisMode === "ai" ? "AI" : "EDIT"}</span>
                <p>{summary}</p>
              </div>
              <div className="extracted-list">
                {items.map((item, index) => (
                  <ExtractedItemEditor
                    key={item.id}
                    item={item}
                    index={index}
                    options={iconOptions}
                    onChange={(patch) => updateItem(item.id, patch)}
                    onRemove={() => setItems((current) => current.filter((candidate) => candidate.id !== item.id))}
                  />
                ))}
              </div>
              <button className="add-garment-button" onClick={addItem}>＋ 手动补一件衣物或配件</button>

              <div className="save-look-form">
                <div className="save-look-heading"><span className="card-index">03 / SAVE LOOK</span><strong>{editingId ? "更新这套方案" : "保存为穿搭方案"}</strong></div>
                <label><span>方案名称</span><input value={title} maxLength={32} placeholder="例如：周末逛展 · 灰蓝层次" onChange={(event) => setTitle(event.target.value)} /></label>
                <label><span>灵感备注 <small>选填</small></span><textarea value={note} maxLength={120} placeholder="记录适合的场景、温度或搭配想法……" onChange={(event) => setNote(event.target.value)} /></label>
                <p className="save-destination-note">确认无误后，选择这套穿搭接下来要去哪里。</p>
                <div className="save-destination-actions">
                  <button className="save-look-button secondary" onClick={() => saveLook("inspiration")}><span>{editingId ? "更新到我的灵感" : "保存到我的灵感"}</span><b>＋</b></button>
                  <button className="save-look-button recommendation" onClick={() => saveLook("recommendation")}><span>{editingId && looks.find((look) => look.id === editingId)?.recommendationEnabled ? "更新每日推荐" : "加入每日推荐"}</span><b>→</b></button>
                </div>
                <small className="recommendation-explainer">加入后，首页会根据气温、衣物薄厚和性别，从你的方案中优先推荐。</small>
              </div>
            </>
          )}
        </section>
      </div>

      {error && <div className="closet-error" role="alert"><span>!</span>{error}<button onClick={() => setError("")}>×</button></div>}

      <section className="inspiration-section">
        <div className="section-heading inspiration-heading">
          <div><span className="eyebrow">MY INSPIRATION LIBRARY</span><h2>我的灵感库</h2><p>保存在这个浏览器里，随时可以重新打开修改。</p></div>
          <span className="library-count">{String(looks.length).padStart(2, "0")} LOOKS</span>
        </div>

        {!looks.length ? (
          <div className="library-empty">
            <span>00</span><div><strong>第一套灵感，还在上面等你</strong><p>上传一张穿搭图，确认 icon 后保存，它就会出现在这里。</p></div>
          </div>
        ) : (
          <div className="inspiration-grid">
            {looks.map((look, index) => (
              <article className="look-card" key={look.id}>
                <div className="look-photo">
                  <img src={look.imageDataUrl} alt={look.title} />
                  <span className="look-number">{String(index + 1).padStart(2, "0")}</span>
                  {look.recommendationEnabled && <span className="look-photo-recommendation"><i /> 推荐中</span>}
                </div>
                <div className="look-card-body">
                  <div className="look-meta"><span>{look.collection === "mens" ? "男性衣物库" : "女性衣物库"}</span><time>{formatDate(look.updatedAt)}</time></div>
                  <h3>{look.title}</h3>
                  {look.note && <p className="look-note">{look.note}</p>}
                  <div className="look-card-footer">
                    <div className="look-icons">
                      {look.items.slice(0, 6).map((item) => <IconPreview key={item.id} item={item} compact />)}
                      {look.items.length > 6 && <span className="more-items">+{look.items.length - 6}</span>}
                    </div>
                    <div className="look-actions">
                      <button className={`recommendation-toggle ${look.recommendationEnabled ? "active" : ""}`} onClick={() => toggleRecommendation(look)}>{look.recommendationEnabled ? "移出每日推荐" : "加入每日推荐"}</button>
                      <button className="secondary-action" onClick={() => editLook(look)}>修改</button>
                      <button className="danger" aria-label={`删除${look.title}`} onClick={() => removeLook(look.id)}>删除</button>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <div className={`save-toast ${saveNotice ? "show" : ""}`}>{saveNotice}</div>
    </main>
  );
}

function ExtractedItemEditor({ item, index, options, onChange, onRemove }: {
  item: ExtractedGarment;
  index: number;
  options: typeof GARMENT_ICON_MAP;
  onChange: (patch: Partial<ExtractedGarment>) => void;
  onRemove: () => void;
}) {
  return (
    <article className="extracted-item">
      <div className="extracted-item-top">
        <IconPreview item={item} />
        <div className="item-identity"><small>ITEM {String(index + 1).padStart(2, "0")}</small><strong>{item.label}</strong><span>{Math.round(item.confidence * 100)}% 识别把握</span></div>
        <button className="remove-item" aria-label={`删除${item.label}`} onClick={onRemove}>×</button>
      </div>
      <div className="item-fields">
        <label className="wide"><span>服装品类</span><select value={item.iconKey} onChange={(event) => onChange({ iconKey: event.target.value })}>
          {(["top", "outerwear", "bottom", "onepiece", "shoes", "accessory"] as const).map((category) => {
            const entries = options.filter((option) => option.category === category);
            if (!entries.length) return null;
            return <optgroup key={category} label={categoryLabel(category)}>{entries.map((option) => <option key={option.iconKey} value={option.iconKey}>{option.label}</option>)}</optgroup>;
          })}
        </select></label>
        <label><span>颜色名称</span><div className="color-field"><input type="color" value={item.colorHex} aria-label={`${item.label}颜色`} onChange={(event) => onChange({ colorHex: event.target.value })} /><input value={item.colorName} maxLength={12} onChange={(event) => onChange({ colorName: event.target.value })} /></div></label>
        <fieldset><legend>衣物薄厚</legend><div className="thickness-choice">{thicknessOptions.map((option) => <button type="button" key={option.value} className={item.thickness === option.value ? "active" : ""} onClick={() => onChange({ thickness: option.value })}>{option.label}</button>)}</div></fieldset>
      </div>
    </article>
  );
}

function IconPreview({ item, compact = false }: { item: ExtractedGarment; compact?: boolean }) {
  const path = getGarmentIconPath(item.iconKey);
  if (!path) return <span className="icon-preview missing">?</span>;
  const style: IconStyle = { "--icon-url": `url(${path})`, "--icon-color": item.colorHex };
  return <span className={`icon-preview ${compact ? "compact" : ""}`} style={style} title={`${item.colorName} ${item.label}`} />;
}

function categoryLabel(category: string) {
  return { top: "上装", outerwear: "外套", bottom: "下装", onepiece: "连体", shoes: "鞋履", accessory: "配件与饰品" }[category] ?? category;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(new Date(value));
}
