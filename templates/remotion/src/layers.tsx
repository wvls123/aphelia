import React, { useEffect, useState } from "react";
import { Img, OffthreadVideo, Sequence, continueRender, delayRender, spring, staticFile, useVideoConfig } from "remotion";
import { fitText } from "@remotion/layout-utils";
import { evolvePath } from "@remotion/paths";
import { Trail } from "@remotion/motion-blur";
import { Circle, Ellipse, Pie, Star, Triangle } from "@remotion/shapes";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";
import { Lottie } from "@remotion/lottie";
import type { LottieAnimationData } from "@remotion/lottie";
import type {
  ArrowLayer,
  BarsLayer,
  BignumLayer,
  CheckLayer,
  CustomLayer,
  HeadlineLayer,
  ImageLayer,
  KickerLayer,
  LabelLayer,
  Layer,
  ListLayer,
  LottieLayer,
  Palette,
  QuoteLayer,
  ScribbleLayer,
  ShapeLayer,
  StampLayer,
  VideoLayer,
  WaveformLayer,
} from "./timeline-types";
import { backOut, bounceOut, elasticOut, expoOut, linear, mix, power2InOut, power2Out, power3Out, power4Out, prog, sineInOut, yoyo } from "./ease";
import { fontHand, fontHead } from "./fonts";
import { registry } from "./custom";

const W = 1080;
const H = 1920;

export const color = (pal: Palette, name: string): string => (pal as unknown as Record<string, string>)[name] ?? name;

const fmtRu = (v: number) => Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");

/** Russian number formatting with thin-space thousands and comma decimals. */
export const fmtNum = (v: number, decimals: number): string => {
  if (decimals === 0) return fmtRu(v);
  const [int, frac] = Math.abs(v).toFixed(decimals).split(".");
  return `${v < 0 ? "-" : ""}${fmtRu(Number(int))},${frac}`;
};

/** Accent colour that stays visible on an accent (lime) background. */
const accentOn = (pal: Palette) => (pal.name === "accent" ? pal.ink : pal.accent);

/** Marker bar behind highlighted words: must contrast with the palette's text colour. */
export const markBar = (pal: Palette): string => {
  switch (pal.name) {
    case "paper":
      return pal.accent;
    case "ink":
      return pal.danger;
    case "accent":
      return "#FFFFFF";
    case "danger":
      return "#111111";
    default: {
      const never: never = pal.name;
      return never;
    }
  }
};

/** Physics pop 0→1 with overshoot (remotion spring). */
const pop = (now: number, at: number, fps: number, damping = 11, stiffness = 170) => (now < at ? 0 : spring({ frame: (now - at) * fps, fps, config: { damping, stiffness, mass: 0.8 } }));

const jitter = (now: number, at: number, half: number, legs: number, amp: number) => amp * yoyo(now, at, half, legs, linear);

/** Largest font size ≤ max at which the text fits `width` on `lines` lines (longest word must never break). */
const fitLines = (text: string, width: number, max: number, lines: number, weight: number, spacing: string): number => {
  const words = text.split(/\s+/).filter(Boolean);
  const longest = words.reduce((a, b) => (b.length > a.length ? b : a), "");
  const wordFit = fitText({ text: longest, withinWidth: width, fontFamily: fontHead, fontWeight: weight, textTransform: "uppercase", letterSpacing: spacing }).fontSize;
  const allFit = fitText({ text, withinWidth: width * lines * 0.92, fontFamily: fontHead, fontWeight: weight, textTransform: "uppercase", letterSpacing: spacing }).fontSize;
  return Math.max(28, Math.min(max, wordFit, allFit));
};

// ---------- HUD layers ----------

const Kicker: React.FC<{ l: KickerLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const p = prog(now, l.t, 0.28, power3Out);
  const size = Math.min(l.size, fitText({ text: l.text, withinWidth: W - l.x - 40, fontFamily: fontHand, textTransform: "uppercase", letterSpacing: "0.02em" }).fontSize);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, fontFamily: fontHand, fontSize: size, letterSpacing: "0.02em", textTransform: "uppercase", whiteSpace: "nowrap", color: color(pal, l.color), opacity: p, transform: `translateX(${mix(-24, 0, p)}px)` }}>
      {l.text}
    </div>
  );
};

const splitHighlights = (text: string, hl: string[]): { chunk: string; mark: boolean }[] => {
  const out: { chunk: string; mark: boolean }[] = [];
  const phrases = [...hl].sort((a, b) => b.length - a.length);
  let rest = text;
  while (rest.length) {
    let best: { idx: number; phrase: string } | null = null;
    for (const phrase of phrases) {
      const idx = rest.indexOf(phrase);
      if (idx >= 0 && (best === null || idx < best.idx)) best = { idx, phrase };
    }
    if (!best) {
      out.push({ chunk: rest, mark: false });
      break;
    }
    if (best.idx > 0) out.push({ chunk: rest.slice(0, best.idx), mark: false });
    out.push({ chunk: best.phrase, mark: true });
    rest = rest.slice(best.idx + best.phrase.length);
  }
  return out;
};

const Mark: React.FC<{ mk: number; bar: string; children: React.ReactNode }> = ({ mk, bar, children }) => (
  <span style={{ position: "relative", display: "inline-block", zIndex: 0 }}>
    <span style={{ position: "absolute", left: "-0.06em", right: "-0.06em", top: "0.12em", bottom: "0.02em", background: bar, zIndex: -1, borderRadius: "0.12em", transformOrigin: "left center", transform: `skewX(-6deg) scaleX(${mk})` }} />
    {children}
  </span>
);

const Headline: React.FC<{ l: HeadlineLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const size = fitLines(l.text, l.w, l.size, l.lines, 900, "-0.035em");
  const parts = splitHighlights(l.text, l.hl);
  let markIndex = 0;
  let opacity = 1;
  let transform = "";
  let filter = "";
  switch (l.anim) {
    case "rise": {
      const p = prog(now, l.t, 0.38, backOut(1.5));
      opacity = prog(now, l.t, 0.38, linear);
      transform = `translateY(${mix(46, 0, p)}px)`;
      break;
    }
    case "slam": {
      const p = prog(now, l.t, 0.18, expoOut);
      opacity = prog(now, l.t, 0.18, linear);
      transform = `translateX(${now >= l.t + 0.16 ? jitter(now, l.t + 0.16, 0.05, 4, 7) : 0}px) scale(${mix(1.7, 1, p)})`;
      break;
    }
    case "blur": {
      const p = prog(now, l.t, 0.45, power2Out);
      opacity = p;
      filter = `blur(${mix(18, 0, p)}px)`;
      transform = `scale(${mix(1.08, 1, p)})`;
      break;
    }
    case "flip": {
      const s = pop(now, l.t, fps, 14, 120);
      opacity = Math.min(1, s * 1.5);
      transform = `perspective(900px) rotateX(${mix(-90, 0, s)}deg)`;
      break;
    }
    case "words":
    case "typewriter":
      break;
    default: {
      const never: never = l.anim;
      return never;
    }
  }
  let wordIdx = 0;
  let charIdx = 0;
  const renderText = (chunk: string) => {
    if (l.anim !== "words" && l.anim !== "typewriter") return chunk;
    return chunk.split(/(\s+)/).map((tok, i) => {
      if (!tok) return null;
      if (/^\s+$/.test(tok)) return <React.Fragment key={i}> </React.Fragment>;
      if (l.anim === "words") {
        const s = pop(now, l.t + wordIdx * 0.07, fps, 12, 200);
        wordIdx += 1;
        return (
          <span key={i} style={{ display: "inline-block", opacity: Math.min(1, s * 1.4), transform: `translateY(${mix(40, 0, s)}px) scale(${mix(0.8, 1, s)})` }}>
            {tok}
          </span>
        );
      }
      const chars = [...tok].map((c, k) => {
        const on = now >= l.t + charIdx * 0.028 ? 1 : 0;
        charIdx += 1;
        return (
          <span key={k} style={{ opacity: on }}>
            {c}
          </span>
        );
      });
      return (
        <span key={i} style={{ display: "inline-block" }}>
          {chars}
        </span>
      );
    });
  };
  return (
    <h1 style={{ position: "absolute", left: l.x, top: l.y, width: l.w, margin: 0, fontFamily: fontHead, fontWeight: 900, fontSize: size, lineHeight: 1.02, letterSpacing: "-0.035em", textTransform: "uppercase", color: color(pal, l.color), opacity, filter, transformOrigin: "left center", transform }}>
      {parts.map((part, i) => {
        if (!part.mark) return <React.Fragment key={i}>{renderText(part.chunk)}</React.Fragment>;
        const mk = prog(now, l.t + 0.22 + markIndex * 0.08, 0.32, power3Out);
        markIndex += 1;
        return (
          <Mark key={i} mk={mk} bar={markBar(pal)}>
            {renderText(part.chunk)}
          </Mark>
        );
      })}
    </h1>
  );
};

// ---------- stage layers ----------

const Stamp: React.FC<{ l: StampLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const p = prog(now, l.t, 0.16, power4Out);
  const shake = now >= l.t + 0.14 ? jitter(now, l.t + 0.14, 0.05, 4, 6) : 0;
  const size = Math.min(l.size, fitText({ text: l.text, withinWidth: W - l.x - 60, fontFamily: fontHead, fontWeight: 900, textTransform: "uppercase", letterSpacing: "-0.02em" }).fontSize / 1.5);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, fontFamily: fontHead, fontWeight: 900, fontSize: size, lineHeight: 1, textTransform: "uppercase", letterSpacing: "-0.02em", whiteSpace: "nowrap", padding: "0.12em 0.22em", border: "0.09em solid currentColor", borderRadius: "0.14em", color: color(pal, l.color), background: "rgba(255,255,255,0.72)", mixBlendMode: "multiply", opacity: p, transformOrigin: "center", transform: `translateX(${shake}px) rotate(${l.rot}deg) scale(${mix(2.2, 1, p)})` }}>
      {l.text}
    </div>
  );
};

const Label: React.FC<{ l: LabelLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const s = pop(now, l.t, fps, 12, 210);
  const size = Math.min(34, fitText({ text: l.text, withinWidth: W - l.x - 80, fontFamily: fontHead, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.02em" }).fontSize);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, fontFamily: fontHead, fontWeight: 800, fontSize: size, letterSpacing: "0.02em", textTransform: "uppercase", padding: "14px 26px", borderRadius: 999, color: l.color === "ink" ? pal.bg : pal.ink, background: color(pal, l.color), whiteSpace: "nowrap", opacity: Math.min(1, s * 1.4), transform: `translateY(${mix(18, 0, s)}px) scale(${mix(0.7, 1, s)})` }}>
      {l.text}
    </div>
  );
};

const Bignum: React.FC<{ l: BignumLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const size = l.size;
  const p = prog(now, l.t, 0.34, backOut(1.6));
  const alpha = prog(now, l.t, 0.34, linear);
  const parsed = l.number;
  const count = prog(now, l.t + 0.04, 0.5, power2Out) * parsed.num;
  const decoP = prog(now, l.t + 0.28, 0.4, power2InOut);
  const textW = l.value.length * size * 0.62;
  let deco: React.ReactNode = null;
  if (l.deco === "circle") {
    const rx = textW / 2 + size * 0.18;
    const ry = size * 0.6;
    const cx = textW / 2;
    const cy = size * 0.5;
    // ellipse as a path so evolvePath can draw it on
    const d = `M ${cx - rx} ${cy} a ${rx} ${ry} 0 1 0 ${rx * 2} 0 a ${rx} ${ry} 0 1 0 ${-rx * 2} 0`;
    const ev = evolvePath(decoP, d);
    deco = (
      <svg viewBox={`${-size} ${-size} ${textW + 2 * size} ${size * 3}`} style={{ position: "absolute", left: -size, top: -size, width: textW + 2 * size, height: size * 3, overflow: "visible", zIndex: 0 }}>
        <path d={d} transform={`rotate(-6 ${cx} ${cy})`} fill="none" stroke={color(pal, l.deco_color)} strokeWidth={Math.max(8, size * 0.06)} strokeLinecap="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
      </svg>
    );
  } else if (l.deco === "underline") {
    const d = `M 0 ${size * 1.02} Q ${textW * 0.5} ${size * 1.12} ${textW} ${size * 1.0}`;
    const ev = evolvePath(decoP, d);
    deco = (
      <svg viewBox={`0 0 ${textW} ${size * 1.3}`} style={{ position: "absolute", left: 0, top: 0, width: textW, height: size * 1.3, overflow: "visible", zIndex: 0 }}>
        <path d={d} fill="none" stroke={color(pal, l.deco_color)} strokeWidth={Math.max(10, size * 0.09)} strokeLinecap="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
      </svg>
    );
  }
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, fontFamily: fontHead, fontWeight: 900, fontSize: size, lineHeight: 1, letterSpacing: "-0.06em", fontVariantNumeric: "tabular-nums", color: color(pal, l.color), opacity: alpha, transform: `translateY(${mix(40, 0, p)}px) scale(${mix(0.9, 1, p)})` }}>
      {deco}
      <span style={{ position: "relative", zIndex: 1, display: "inline-block", whiteSpace: "nowrap" }}>
        {parsed.prefix}
        {fmtNum(count, parsed.decimals)}
        {parsed.suffix}
      </span>
      {l.label ? <div style={{ fontFamily: fontHand, fontSize: size * 0.24, letterSpacing: "0.04em", color: pal.muted, marginTop: size * 0.22, textTransform: "uppercase", fontWeight: 400 }}>{l.label}</div> : null}
    </div>
  );
};

const slideOffset = (l: ImageLayer): { axis: "x" | "y"; dist: number } => {
  switch (l.from) {
    case "right":
      return { axis: "x", dist: (W - l.x) * 1.4 + 100 };
    case "left":
      return { axis: "x", dist: -((l.x + l.w) * 1.4 + 100) };
    case "bottom":
      return { axis: "y", dist: (H - l.y) * 1.4 + 100 };
    case "top":
      return { axis: "y", dist: -((l.y + l.h) * 1.4 + 100) };
    default: {
      const never: never = l.from;
      return never;
    }
  }
};

const CutoutImg: React.FC<{ l: ImageLayer; pal: Palette; now: number; fps: number; sceneEnd: number }> = ({ l, pal, now, fps, sceneEnd }) => {
  let opacity = 1;
  let tx = 0;
  let ty = 0;
  let scale = 1;
  let rot = 0;
  let clip: string | undefined;
  let origin = "center";
  switch (l.anim) {
    case "pop": {
      const p = prog(now, l.t, l.dur, backOut(1.7));
      opacity = prog(now, l.t, l.dur, linear);
      scale = mix(0.55, 1, p);
      rot = mix(-7, 0, p);
      ty = mix(60, 0, p);
      break;
    }
    case "spring": {
      const s = pop(now, l.t, fps, 8, 150);
      opacity = Math.min(1, s * 2);
      scale = s;
      break;
    }
    case "spin": {
      const s = pop(now, l.t, fps, 14, 90);
      opacity = Math.min(1, s * 1.5);
      scale = mix(0.3, 1, s);
      rot = mix(-540, 0, s);
      break;
    }
    case "wipe": {
      const p = prog(now, l.t, l.dur + 0.15, power2InOut);
      clip = `inset(0 ${(1 - p) * 100}% 0 0)`;
      break;
    }
    case "slide": {
      const off = slideOffset(l);
      const p = prog(now, l.t, l.dur, expoOut);
      if (off.axis === "x") tx = mix(off.dist, 0, p);
      else ty = mix(off.dist, 0, p);
      break;
    }
    case "run": {
      if (now > l.t + l.dur + 0.02) return null;
      tx = mix(0, l.to_x - l.x, prog(now, l.t, l.dur, linear));
      ty = -22 * yoyo(now, l.t, 0.14, Math.floor(l.dur / 0.14) + 1, sineInOut);
      break;
    }
    case "shake": {
      const p = prog(now, l.t, 0.2, backOut(2));
      opacity = prog(now, l.t, 0.2, linear);
      scale = mix(0.7, 1, p);
      if (now >= l.t + 0.2) {
        const j = yoyo(now, l.t + 0.2, 0.07, Math.max(2, Math.floor((sceneEnd - l.t - 0.2) / 0.07)) + 1, linear);
        tx = 9 * j;
        rot = 2.5 * j;
      }
      break;
    }
    case "swing": {
      const p = prog(now, l.t, l.dur + 0.5, elasticOut);
      opacity = prog(now, l.t, 0.2, linear);
      rot = mix(-28, 0, p);
      origin = "50% 0%";
      break;
    }
    case "zoomin": {
      const d = Math.max(0.22, l.dur * 0.6);
      const p = prog(now, l.t, d, expoOut);
      opacity = prog(now, l.t, d, linear);
      scale = mix(1.9, 1, p);
      break;
    }
    case "drop": {
      const p = prog(now, l.t, l.dur + 0.25, bounceOut);
      ty = mix(-(l.y + l.h + 200), 0, p);
      break;
    }
    default: {
      const never: never = l.anim;
      return never;
    }
  }
  if (l.float && l.anim !== "run" && l.anim !== "shake") {
    const t0 = l.t + l.dur + 0.03;
    if (now >= t0) {
      ty += -12 * yoyo(now, t0, 0.55, Math.max(1, Math.floor((sceneEnd - t0) / 0.55)) + 1, sineInOut);
      rot += 2.2 * yoyo(now, t0, 0.8, Math.max(1, Math.floor((sceneEnd - t0) / 0.8)) + 1, sineInOut);
    }
  }
  const shadow = pal.name === "ink" ? "invert(1) drop-shadow(0 18px 22px rgba(0,0,0,0.35))" : "drop-shadow(0 18px 22px rgba(17,17,17,0.12))";
  return <Img src={staticFile(l.src)} style={{ position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h, objectFit: "contain", opacity, clipPath: clip, filter: shadow, transformOrigin: origin, transform: `translate(${tx}px, ${ty}px) rotate(${rot}deg) scale(${scale})` }} />;
};

const Cutout: React.FC<{ l: ImageLayer; pal: Palette; now: number; fps: number; sceneEnd: number }> = (props) => {
  const { l, now } = props;
  if (now < l.t) return null;
  const moving = l.trail && now < l.t + l.dur + 0.1 && (l.anim === "run" || l.anim === "slide" || l.anim === "drop" || l.anim === "zoomin");
  if (!moving) return <CutoutImg {...props} />;
  // Trail needs absolutely-positioned children — CutoutImg is
  return (
    <Trail layers={6} lagInFrames={0.6} trailOpacity={0.5}>
      <CutoutImg {...props} />
    </Trail>
  );
};

const quadPath = (p0: [number, number], p1: [number, number], bend: number) => {
  const [x0, y0] = p0;
  const [x1, y1] = p1;
  const dx = x1 - x0;
  const dy = y1 - y0;
  const length = Math.hypot(dx, dy) || 1;
  const cx = (x0 + x1) / 2 + (-dy / length) * bend * length;
  const cy = (y0 + y1) / 2 + (dx / length) * bend * length;
  const angle = (Math.atan2(y1 - cy, x1 - cx) * 180) / Math.PI;
  return { d: `M ${x0} ${y0} Q ${cx} ${cy} ${x1} ${y1}`, angle };
};

const Arrow: React.FC<{ l: ArrowLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const { d, angle } = quadPath(l.from, l.to, l.bend);
  const ev = evolvePath(prog(now, l.t, l.dur, power2Out), d);
  const headP = prog(now, l.t + l.dur - 0.08, 0.18, backOut(3));
  const w = l.width;
  const col = color(pal, l.color);
  const [ex, ey] = l.to;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: W, height: H, overflow: "visible" }}>
      <path d={d} fill="none" stroke={col} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
      <g transform={`translate(${ex} ${ey}) rotate(${angle}) scale(${Math.max(0, headP)})`}>
        <path d={`M ${-w * 2.6} ${-w * 1.9} L 0 0 L ${-w * 2.6} ${w * 1.9}`} fill="none" stroke={col} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
};

const VideoFrame: React.FC<{ l: VideoLayer; pal: Palette; now: number; sceneStart: number }> = ({ l, pal, now, sceneStart }) => {
  const { fps } = useVideoConfig();
  if (now < l.t) return null;
  const p = prog(now, l.t, 0.42, backOut(1.3));
  const alpha = prog(now, l.t, 0.42, linear);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h, borderRadius: 22, overflow: "hidden", background: "#fff", border: `4px solid ${pal.ink}`, boxShadow: `18px 18px 0 ${pal.ink}`, opacity: alpha, transform: `rotate(${l.rot}deg) translateY(${mix(80, 0, p)}px) scale(${mix(0.94, 1, p)})` }}>
      <div style={{ height: 64, display: "flex", alignItems: "center", gap: 12, padding: "0 22px", borderBottom: `4px solid ${pal.ink}`, background: "#fff", fontFamily: fontHand, fontSize: 28, color: pal.muted, boxSizing: "border-box" }}>
        {[0, 1, 2].map((i) => (
          <i key={i} style={{ width: 18, height: 18, borderRadius: "50%", border: `3px solid ${pal.ink}`, display: "inline-block", boxSizing: "border-box" }} />
        ))}
        <span style={{ marginLeft: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.url}</span>
      </div>
      <Sequence from={Math.round((l.t - sceneStart) * fps)} layout="none">
        <OffthreadVideo src={staticFile(l.src)} muted startFrom={Math.round(l.seek * fps)} style={{ display: "block", width: "100%", height: l.h - 64 - 8, objectFit: "cover", objectPosition: "top" }} />
      </Sequence>
    </div>
  );
};

const List: React.FC<{ l: ListLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const bul = { check: "✓", dash: "—", num: "" }[l.bullet];
  const size = fitLines(l.items.map((i) => i.text).reduce((a, b) => (b.length > a.length ? b : a), ""), l.w - l.size * 1.5, l.size, 2, 800, "-0.02em");
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, fontFamily: fontHead, fontWeight: 800, fontSize: size, lineHeight: 1.15, textTransform: "uppercase", letterSpacing: "-0.02em", color: color(pal, l.color) }}>
      {l.items.map((it, j) => {
        if (now < it.t) return null;
        const s = pop(now, it.t, fps, 13, 190);
        const b = pop(now, it.t + 0.08, fps, 10, 260);
        return (
          <div key={j} style={{ display: "flex", gap: "0.35em", alignItems: "flex-start", marginBottom: "0.42em", opacity: Math.min(1, s * 1.4), transform: `translateX(${mix(-48, 0, s)}px)` }}>
            <span style={{ display: "inline-block", fontFamily: fontHand, fontWeight: 400, minWidth: "1.1em", fontSize: "1.1em", lineHeight: 1, color: accentOn(pal), transform: `scale(${Math.max(0, b)})` }}>{l.bullet === "num" ? `${j + 1}.` : bul}</span>
            <span>{it.text}</span>
          </div>
        );
      })}
    </div>
  );
};

const Quote: React.FC<{ l: QuoteLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const s = pop(now, l.t, fps, 13, 140);
  const q = pop(now, l.t, fps, 9, 200);
  const size = Math.min(l.size, fitText({ text: l.text, withinWidth: l.w * 3.2, fontFamily: fontHand }).fontSize);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, fontFamily: fontHand, fontSize: size, lineHeight: 1.18, color: color(pal, l.color), opacity: Math.min(1, s * 1.4), transform: `translateY(${mix(30, 0, s)}px) scale(${mix(0.92, 1, s)})` }}>
      <div style={{ fontFamily: fontHead, fontWeight: 900, fontSize: "3.2em", lineHeight: 0.6, marginBottom: "0.1em", color: accentOn(pal), transformOrigin: "left bottom", transform: `rotate(${mix(-30, 0, q)}deg) scale(${mix(0.4, 1, q)})` }}>“</div>
      <div>{l.text}</div>
      {l.author ? <div style={{ marginTop: "0.4em", fontSize: "0.6em", textTransform: "uppercase", letterSpacing: "0.04em", color: pal.muted }}>— {l.author}</div> : null}
    </div>
  );
};

const Bars: React.FC<{ l: BarsLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const a = prog(now, l.t, 0.3, linear);
  const p = prog(now, l.t, 0.3, power3Out);
  const col = color(pal, l.color);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, fontFamily: fontHead, fontWeight: 800, fontSize: l.size, textTransform: "uppercase", color: col, opacity: a, transform: `translateY(${mix(30, 0, p)}px)` }}>
      {l.items.map((it, j) => {
        if (now < it.t) return null;
        const ra = prog(now, it.t, 0.25, linear);
        const rp = prog(now, it.t, 0.25, power3Out);
        const fill = prog(now, it.t + 0.05, 0.6, power3Out);
        const fillCol = pal.name === "accent" && it.color === "accent" ? pal.ink : color(pal, it.color);
        return (
          <div key={j} style={{ display: "grid", gridTemplateColumns: "5.2em 1fr 4.8em", alignItems: "center", gap: "0.5em", marginBottom: "0.55em", opacity: ra, transform: `translateX(${mix(-30, 0, rp)}px)` }}>
            <div style={{ fontFamily: fontHand, fontWeight: 400, fontSize: "0.85em", textTransform: "none" }}>{it.label}</div>
            <div style={{ height: "1.15em", border: `4px solid ${col}`, borderRadius: "0.2em", overflow: "hidden", background: "rgba(255,255,255,0.4)", boxSizing: "border-box" }}>
              <div style={{ height: "100%", width: `${it.frac * 100}%`, background: fillCol, transformOrigin: "0 50%", transform: `scaleX(${fill})` }} />
            </div>
            <div style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap", fontSize: "0.85em" }}>
              {it.number.prefix}
              {fmtNum(fill * it.number.num, it.number.decimals)}
              {it.number.suffix}
              {it.suffix ?? ""}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const checkPath = (kind: "check" | "cross", s: number): string =>
  kind === "check" ? `M ${s * 0.14} ${s * 0.55} L ${s * 0.4} ${s * 0.82} L ${s * 0.88} ${s * 0.2}` : `M ${s * 0.18} ${s * 0.18} L ${s * 0.82} ${s * 0.82} M ${s * 0.82} ${s * 0.18} L ${s * 0.18} ${s * 0.82}`;

const Check: React.FC<{ l: CheckLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const s = l.size;
  const scale = pop(now, l.t, fps, 10, 220);
  const ev = evolvePath(prog(now, l.t + 0.05, 0.32, power2InOut), checkPath(l.kind, s));
  return (
    <svg viewBox={`0 0 ${s} ${s}`} style={{ position: "absolute", left: l.x, top: l.y, width: s, height: s, overflow: "visible", opacity: Math.min(1, scale * 1.5), transformOrigin: "center", transform: `scale(${mix(0.6, 1, scale)})` }}>
      <path d={checkPath(l.kind, s)} fill="none" stroke={color(pal, l.color)} strokeWidth={Math.max(10, s * 0.11)} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
    </svg>
  );
};

const wavyUnderline = (w: number, h: number): string => {
  const n = Math.max(3, Math.floor(w / 90));
  const step = w / n;
  let d = `M 0 ${h * 0.5}`;
  for (let i = 0; i < n; i++) d += ` Q ${i * step + step / 2} ${h * (i % 2 === 0 ? 0.15 : 0.85)} ${(i + 1) * step} ${h * 0.5}`;
  return d;
};

const Scribble: React.FC<{ l: ScribbleLayer; pal: Palette; now: number }> = ({ l, pal, now }) => {
  if (now < l.t) return null;
  const draw = prog(now, l.t, l.dur, power2InOut);
  const col = color(pal, l.color);
  const rx = l.w / 2 - l.width;
  const ry = l.h / 2 - l.width;
  const d = l.shape === "circle" ? `M ${l.w / 2 - rx} ${l.h / 2} a ${rx} ${ry} 0 1 0 ${rx * 2} 0 a ${rx} ${ry} 0 1 0 ${-rx * 2} 0` : wavyUnderline(l.w, l.h);
  const ev = evolvePath(draw, d);
  return (
    <svg viewBox={`0 0 ${l.w} ${l.h}`} style={{ position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h, overflow: "visible" }}>
      <path d={d} transform={l.shape === "circle" ? `rotate(-4 ${l.w / 2} ${l.h / 2})` : undefined} fill="none" stroke={col} strokeWidth={l.width} strokeLinecap="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
    </svg>
  );
};

/** @remotion/shapes decor: burst behind a stamp, pie for a share, star/triangle accents. */
const Shape: React.FC<{ l: ShapeLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  if (now < l.t) return null;
  const fill = color(pal, l.color);
  const s = pop(now, l.t, fps, 10, 200);
  const spin = l.anim === "spin" ? (now - l.t) * 40 : 0;
  const pulse = l.anim === "pulse" ? 1 + 0.06 * Math.sin((now - l.t) * 5) : 1;
  const size = l.size;
  let node: React.ReactNode;
  switch (l.shape) {
    case "circle":
      node = <Circle radius={size / 2} fill={fill} />;
      break;
    case "ellipse":
      node = <Ellipse rx={size / 2} ry={size / 3} fill={fill} />;
      break;
    case "star":
      node = <Star innerRadius={size / 4} outerRadius={size / 2} points={l.points || 5} fill={fill} />;
      break;
    case "burst":
      node = <Star innerRadius={size * 0.36} outerRadius={size / 2} points={l.points || 14} fill={fill} />;
      break;
    case "triangle":
      node = <Triangle length={size} direction="up" fill={fill} />;
      break;
    case "pie":
      node = <Pie radius={size / 2} progress={Math.min(l.progress, prog(now, l.t, 0.8, power2InOut) * l.progress)} fill={fill} />;
      break;
    default: {
      const never: never = l.shape;
      return never;
    }
  }
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, opacity: Math.min(1, s * 1.5), transformOrigin: "center", transform: `rotate(${l.rot + spin}deg) scale(${s * pulse})` }}>
      {node}
    </div>
  );
};

/** Audio-reactive bars driven by the voice (or bgm) — @remotion/media-utils visualizeAudio. */
const Waveform: React.FC<{ l: WaveformLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  const data = useAudioData(staticFile(l.src));
  if (now < l.t || !data) return null;
  const vis = visualizeAudio({ fps, frame: Math.round(now * fps), audioData: data, numberOfSamples: l.bars, optimizeFor: "speed" });
  const col = color(pal, l.color);
  const gap = 6;
  const bw = (l.w - gap * (l.bars - 1)) / l.bars;
  const a = prog(now, l.t, 0.3, linear);
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h, display: "flex", alignItems: "flex-end", gap, opacity: a }}>
      {vis.map((v, i) => (
        <div key={i} style={{ width: bw, height: Math.max(6, Math.min(1, v * 4) * l.h), background: col, borderRadius: bw / 2 }} />
      ))}
    </div>
  );
};

/** Lottie sticker (JSON in assets/lottie/, licence-clear only). */
const LottieLayerView: React.FC<{ l: LottieLayer; now: number }> = ({ l, now }) => {
  const [data, setData] = useState<LottieAnimationData | null>(null);
  const [handle] = useState(() => delayRender("lottie"));
  useEffect(() => {
    fetch(staticFile(l.src))
      .then((r) => r.json())
      .then((json) => {
        setData(json as LottieAnimationData);
        continueRender(handle);
      })
      .catch(() => continueRender(handle));
  }, [handle, l.src]);
  if (now < l.t || !data) return null;
  return (
    <div style={{ position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h }}>
      <Lottie animationData={data} loop={l.loop} playbackRate={l.speed} style={{ width: l.w, height: l.h }} />
    </div>
  );
};

const CustomView: React.FC<{ l: CustomLayer; pal: Palette; now: number; fps: number }> = ({ l, pal, now, fps }) => {
  const Comp = registry[l.component];
  if (!Comp) throw new Error(`custom layer component not registered: ${l.component} (add src/custom/${l.component}.tsx and register it in src/custom/index.ts)`);
  return <Comp now={now} t={l.t} until={l.until} pal={pal} layer={l} fps={fps} />;
};

export const HUD_TYPES: ReadonlySet<Layer["type"]> = new Set(["kicker", "headline"]);

export const LayerView: React.FC<{ l: Layer; pal: Palette; now: number; sceneStart: number; sceneEnd: number }> = ({ l, pal, now, sceneStart, sceneEnd }) => {
  const { fps } = useVideoConfig();
  switch (l.type) {
    case "kicker":
      return <Kicker l={l} pal={pal} now={now} />;
    case "headline":
      return <Headline l={l} pal={pal} now={now} fps={fps} />;
    case "stamp":
      return <Stamp l={l} pal={pal} now={now} />;
    case "label":
      return <Label l={l} pal={pal} now={now} fps={fps} />;
    case "bignum":
      return <Bignum l={l} pal={pal} now={now} />;
    case "image":
      return <Cutout l={l} pal={pal} now={now} fps={fps} sceneEnd={sceneEnd} />;
    case "arrow":
      return <Arrow l={l} pal={pal} now={now} />;
    case "video":
      return <VideoFrame l={l} pal={pal} now={now} sceneStart={sceneStart} />;
    case "list":
      return <List l={l} pal={pal} now={now} fps={fps} />;
    case "quote":
      return <Quote l={l} pal={pal} now={now} fps={fps} />;
    case "bars":
      return <Bars l={l} pal={pal} now={now} />;
    case "check":
      return <Check l={l} pal={pal} now={now} fps={fps} />;
    case "scribble":
      return <Scribble l={l} pal={pal} now={now} />;
    case "shape":
      return <Shape l={l} pal={pal} now={now} fps={fps} />;
    case "waveform":
      return <Waveform l={l} pal={pal} now={now} fps={fps} />;
    case "lottie":
      return <LottieLayerView l={l} now={now} />;
    case "custom":
      return <CustomView l={l} pal={pal} now={now} fps={fps} />;
    default: {
      const never: never = l;
      return never;
    }
  }
};