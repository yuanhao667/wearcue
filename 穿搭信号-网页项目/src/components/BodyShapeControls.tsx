"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { BodyFrames, bodyBuildIndex, type BodyFrameState } from "@/domain/body-frames";
import type { Audience, BackendSettings } from "@/domain/backend";
import { createBodyRenderer } from "./body-profile-renderer";

type BodyProfile = Pick<BackendSettings,"height_group" | "weight_group">;

function BodyPreview({state}: {state: BodyFrameState}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<ReturnType<typeof createBodyRenderer> | null>(null);
  const [initial] = useState(state);
  const [status,setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [attempt,setAttempt] = useState(0);
  useEffect(() => {
    if (!canvas.current) return;
    const instance = createBodyRenderer(canvas.current,initial,() => setStatus("ready"),() => setStatus("error"));
    renderer.current=instance;
    return () => { instance.dispose(); renderer.current=null; };
  },[initial,attempt]);
  useEffect(() => { renderer.current?.update(state); },[state,attempt]);
  return <div className="body-shape-stage">
    <canvas ref={canvas} width={512} height={768} role="img" aria-label={`${state.gender === "mens" ? "男装" : "女装"}身形：${BodyFrames.heightLabels[state.height]}、${BodyFrames.buildLabels[state.build]}`} />
    {status !== "ready" && <div className="body-shape-loading" role="status">{status === "loading" ? "正在准备人物图…" : <><span>人物图片加载失败</span><button type="button" className="ghost-button" onClick={() => {setStatus("loading");setAttempt(attempt+1);}}>重试</button></>}</div>}
  </div>;
}

export function BodyShapeControls({audience,profile,onChange}: {
  audience: Audience; profile: BodyProfile; onChange: (patch: BodyProfile) => void;
}) {
  const height = Math.max(0,BodyFrames.heightLabels.indexOf(profile.height_group));
  const build = bodyBuildIndex(profile.weight_group);
  const state = {gender:audience,height,build};
  function chooseHeight(value: number) { onChange({...profile,height_group:BodyFrames.heightLabels[value] as BodyProfile["height_group"]}); }
  function chooseBuild(value: number) { onChange({...profile,weight_group:BodyFrames.buildLabels[value] as BodyProfile["weight_group"]}); }
  return <div className="body-shape-controls">
    <div className="body-shape-layout">
      <BodyPreview state={state} />
      <fieldset className="body-height-field" aria-label="身高"><div className="body-height-track">
        <input aria-label="身高" aria-orientation="vertical" aria-valuetext={BodyFrames.heightLabels[height]} type="range" min="0" max="2" step="1" value={height} style={{"--range-progress":`${height*50}%`} as CSSProperties} onChange={event => chooseHeight(Number(event.target.value))} />
        <div className="body-range-labels">{BodyFrames.heightLabels.map((label,index) => <button type="button" key={label} aria-pressed={index===height} onClick={() => chooseHeight(index)}>{label}</button>)}</div>
      </div></fieldset>
    </div>
    <fieldset className="body-build-field" aria-label="体型">
      <input aria-label="体型" aria-valuetext={BodyFrames.buildLabels[build]} type="range" min="0" max="4" step="1" value={build} style={{"--range-progress":`${build*25}%`} as CSSProperties} onChange={event => chooseBuild(Number(event.target.value))} />
      <div className="body-range-labels">{BodyFrames.buildLabels.map((label,index) => <button type="button" key={label} aria-pressed={index===build} onClick={() => chooseBuild(index)}>{label}</button>)}</div>
    </fieldset>
  </div>;
}
