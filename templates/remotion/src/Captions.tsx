import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { fitText } from "@remotion/layout-utils";
import type { CaptionsCfg, Style, Word } from "./timeline-types";
import { backOut, mix, prog } from "./ease";
import { fontHead } from "./fonts";

const hexToRgb = (hex: string): [number, number, number] => {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
};

/** @remotion/captions tokens carry leading spaces — trim() glues words in karaoke/outline. */
const tokenText = (raw: string, index: number, trimSpaces: boolean): string => {
  if (!trimSpaces) {
    const body = raw.trimEnd();
    if (index === 0) return body.trimStart();
    return body.startsWith(" ") ? body : ` ${body.trimStart()}`;
  }
  return raw.trim();
};

/**
 * Kinetic captions paged by @remotion/captions (TikTok style): 2–3 words per page, the spoken word
 * lights up in the accent colour; fitText keeps every page inside the safe width.
 */
export const Captions: React.FC<{ words: Word[]; cfg: CaptionsCfg; style: Style }> = ({ words, cfg, style }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const nowMs = (frame / fps) * 1000;
  const y = cfg.y ?? 1560;
  const maxSize = cfg.size ?? 60;
  const mode = cfg.style ?? "box";

  const pages = useMemo(() => {
    // page per sentence group: a page never spans a full stop / question / colon
    const groups: Word[][] = [[]];
    for (const w of words) {
      groups[groups.length - 1].push(w);
      if (/[.!?…:]$/.test(w.text)) groups.push([]);
    }
    const combine = Math.round((cfg.max_sec ?? 1.1) * 1000);
    return groups
      .filter((g) => g.length)
      .flatMap((g) => {
        const captions: Caption[] = g.map((w, i) => ({
          text: (i === 0 ? "" : " ") + w.text,
          startMs: Math.round(w.start * 1000),
          endMs: Math.round(w.end * 1000),
          timestampMs: Math.round(((w.start + w.end) / 2) * 1000),
          confidence: null,
        }));
        return createTikTokStyleCaptions({ captions, combineTokensWithinMilliseconds: combine, breakOnSilenceAfterMilliseconds: 350 }).pages;
      });
  }, [words, cfg.max_sec]);

  const idx = pages.findIndex((p, i) => nowMs >= p.startMs && (i + 1 >= pages.length ? nowMs < p.startMs + p.durationMs + 600 : nowMs < pages[i + 1].startMs));
  if (idx < 0) return null;
  const page = pages[idx];
  const size = Math.min(maxSize, fitText({ text: page.text, withinWidth: width - 140, fontFamily: fontHead, fontWeight: 800, textTransform: "uppercase", letterSpacing: "-0.02em" }).fontSize);
  const p = prog(nowMs / 1000, page.startMs / 1000, 0.14, backOut(2));
  const [r, g, b] = hexToRgb(style.accent);

  return (
    <div
      style={{
        position: "absolute",
        left: 48,
        right: 48,
        top: y - size,
        textAlign: "center",
        fontFamily: fontHead,
        fontWeight: 800,
        fontSize: size,
        textTransform: "uppercase",
        letterSpacing: "-0.02em",
        lineHeight: 1.15,
        transform: `translateY(${mix(18, 0, p)}px) scale(${mix(0.9, 1, p)})`,
      }}
    >
      {page.tokens.map((tok, j) => {
        const on = nowMs >= tok.fromMs ? Math.min(1, (nowMs - tok.fromMs) / 80) : 0;
        const boxBg = `rgba(${mix(255, r, on)},${mix(255, g, on)},${mix(255, b, on)},${mix(0.86, 1, on)})`;
        const trimSpaces = mode === "box";
        const text = tokenText(tok.text, j, trimSpaces);
        const gap = mode === "karaoke" ? "0 0.22em" : "0 6px";
        const common: React.CSSProperties = { display: "inline-block", margin: gap, transform: `scale(${mix(1, 1.06, on)})` };
        if (mode === "outline") {
          return (
            <span key={j} style={{ ...common, color: on ? style.accent : "#fff", WebkitTextStroke: "8px #111", paintOrder: "stroke fill" }}>
              {text}
            </span>
          );
        }
        if (mode === "karaoke") {
          return (
            <span key={j} style={{ ...common, color: on ? style.accent : "#fff", textShadow: "0 4px 0 #111, 0 0 18px rgba(0,0,0,0.6)" }}>
              {text}
            </span>
          );
        }
        return (
          <span key={j} style={{ ...common, padding: "2px 14px", borderRadius: 14, color: "#111111", backgroundColor: boxBg, boxShadow: `0 0 0 3px ${boxBg}` }}>
            {text}
          </span>
        );
      })}
    </div>
  );
};
