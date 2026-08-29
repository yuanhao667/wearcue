"use client";

import { FormEvent, useState } from "react";
import type { City } from "@/domain/types";
import type { BackendCity } from "@/domain/backend";
import { apiJson } from "@/lib/backend-api";

export function CityPicker({ current, onSelect, onLocate, onClose }: { current: City; onSelect: (city: City) => void; onLocate?: () => Promise<void>; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [cities, setCities] = useState<City[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState("");

  async function locate() {
    if (!onLocate) return;
    setLocating(true); setLocateError("");
    try { await onLocate(); }
    catch (error) { setLocateError(error instanceof Error ? error.message : "定位失败，请重试"); }
    finally { setLocating(false); }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setStatus("loading");
    try {
      const payload = await apiJson<BackendCity[]>(`/cities?q=${encodeURIComponent(query.trim())}`);
      setCities(payload.map((city) => ({ ...city, country: city.country ?? "", admin1: city.admin1 ?? undefined })));
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet city-sheet" role="dialog" aria-modal="true" aria-labelledby="city-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="sheet-title-row">
          <div>
            <span className="eyebrow">LOCATION</span>
            <h2 id="city-title">切换常用城市</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">×</button>
        </div>
        {onLocate && <button className="locate-current-button" disabled={locating} onClick={() => void locate()}><svg className="location-pin" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 14s4-4.2 4-7.4A4 4 0 0 0 4 6.6C4 9.8 8 14 8 14Z" /><circle cx="8" cy="6.5" r="1.4" /></svg><span><strong>使用当前位置</strong><small>自动定位到所在城区</small></span><b>{locating ? "定位中…" : "定位"}</b></button>}
        {locateError && <p className="inline-error" role="alert">{locateError}</p>}
        <form className="search-form" onSubmit={search}>
          <input name="city-search" autoComplete="off" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入城市，如：上海…" aria-label="搜索城市" />
          <button type="submit" disabled={status === "loading"}>{status === "loading" ? "搜索中…" : "搜索"}</button>
        </form>
        <p className="current-city">当前城市：{current.name}{current.admin1 && current.admin1 !== current.name ? ` · ${current.admin1}` : ""}</p>
        {status === "error" && <p className="inline-error" role="alert">城市搜索失败，请检查网络后再试。</p>}
        {status === "idle" && query && cities.length === 0 && <p className="empty-hint">搜索后从列表中选择城市</p>}
        <div className="city-results">
          {cities.map((city) => (
            <button key={`${city.id}-${city.latitude}`} onClick={() => onSelect(city)}>
              <span><strong>{city.name}</strong><small>{[city.admin1, city.country].filter(Boolean).join(" · ")}</small></span>
              <span aria-hidden="true">→</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
