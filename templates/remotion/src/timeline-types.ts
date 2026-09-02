// Shared timeline schema — mirrors scripts/timeline.py output (timeline.json, storyboard v5).

export interface Style {
  bg: string;
  ink: string;
  accent: string;
  danger: string;
  muted: string;
  font_head: string;
  font_hand: string;
}

/** Per-scene colours (paper / ink / accent / danger backgrounds). */
export interface Palette {
  name: "paper" | "ink" | "accent" | "danger";
  bg: string;
  ink: string;
  muted: string;
  grid: string;
  accent: string;
  danger: string;
}

export interface Word {
  text: string;
  start: number;
  end: number;
}

export interface CameraKey {
  t: number;
  zoom: number;
  x: number;
  y: number;
  ease: "smooth" | "crash";
  shake: number;
}

export type TransitionType = "none" | "push" | "wipe" | "fade" | "flip" | "clock" | "iris" | "zoom" | "flash" | "slice";

export interface Transition {
  type: TransitionType;
  dir: "left" | "right" | "up" | "down";
  from: [number, number];
  dur: number;
}

interface LayerBase {
  t: number;
  until: number;
  x: number;
  y: number;
}

export interface KickerLayer extends LayerBase {
  type: "kicker";
  text: string;
  color: string;
  size: number;
}

export type HeadlineAnim = "rise" | "slam" | "typewriter" | "words" | "blur" | "flip";

export interface HeadlineLayer extends LayerBase {
  type: "headline";
  text: string;
  color: string;
  w: number;
  size: number;
  hl: string[];
  anim: HeadlineAnim;
  /** max lines the text may take; fitText shrinks the font until it fits */
  lines: number;
}

export interface StampLayer extends LayerBase {
  type: "stamp";
  text: string;
  color: string;
  size: number;
  rot: number;
}

export interface LabelLayer extends LayerBase {
  type: "label";
  text: string;
  color: string;
}

export interface ParsedNumber {
  prefix: string;
  num: number;
  decimals: number;
  suffix: string;
}

export interface BignumLayer extends LayerBase {
  type: "bignum";
  value: string;
  digits: number;
  size: number;
  color: string;
  deco: "none" | "circle" | "underline";
  deco_color: string;
  label: string;
  number: ParsedNumber;
}

export type ImageAnim = "pop" | "wipe" | "slide" | "run" | "shake" | "swing" | "zoomin" | "drop" | "spring" | "spin";

export interface ImageLayer extends LayerBase {
  type: "image";
  src: string;
  w: number;
  h: number;
  anim: ImageAnim;
  dur: number;
  float: boolean;
  from: "left" | "right" | "top" | "bottom";
  to_x: number;
  /** motion trail (ghost copies) for run/slide/drop */
  trail: boolean;
}

export interface ArrowLayer {
  type: "arrow";
  t: number;
  until: number;
  from: [number, number];
  to: [number, number];
  bend: number;
  color: string;
  width: number;
  dur: number;
}

export interface VideoLayer extends LayerBase {
  type: "video";
  src: string;
  w: number;
  h: number;
  rot: number;
  url: string;
  seek: number;
}

export interface ListItem {
  text: string;
  t: number;
}

export interface ListLayer extends LayerBase {
  type: "list";
  items: ListItem[];
  w: number;
  size: number;
  bullet: "check" | "dash" | "num";
  color: string;
}

export interface QuoteLayer extends LayerBase {
  type: "quote";
  text: string;
  author: string;
  w: number;
  size: number;
  color: string;
}

export interface BarItem {
  label: string;
  value: number | string;
  number: ParsedNumber;
  frac: number;
  color: string;
  suffix?: string;
  t: number;
}

export interface BarsLayer extends LayerBase {
  type: "bars";
  items: BarItem[];
  w: number;
  size: number;
  color: string;
}

export interface CheckLayer extends LayerBase {
  type: "check";
  kind: "check" | "cross";
  size: number;
  color: string;
}

export interface ScribbleLayer extends LayerBase {
  type: "scribble";
  shape: "circle" | "underline";
  w: number;
  h: number;
  color: string;
  width: number;
  dur: number;
}

export type ShapeKind = "circle" | "star" | "burst" | "triangle" | "pie" | "ellipse";

export interface ShapeLayer extends LayerBase {
  type: "shape";
  shape: ShapeKind;
  size: number;
  color: string;
  anim: "pop" | "spin" | "pulse";
  /** pie progress 0..1, star points */
  progress: number;
  points: number;
  rot: number;
}

export interface WaveformLayer extends LayerBase {
  type: "waveform";
  src: string;
  w: number;
  h: number;
  bars: number;
  color: string;
}

export interface LottieLayer extends LayerBase {
  type: "lottie";
  src: string;
  w: number;
  h: number;
  loop: boolean;
  speed: number;
}

export interface CustomLayer extends LayerBase {
  type: "custom";
  component: string;
  props: Record<string, unknown>;
}

export type Layer =
  | KickerLayer
  | HeadlineLayer
  | StampLayer
  | LabelLayer
  | BignumLayer
  | ImageLayer
  | ArrowLayer
  | VideoLayer
  | ListLayer
  | QuoteLayer
  | BarsLayer
  | CheckLayer
  | ScribbleLayer
  | ShapeLayer
  | WaveformLayer
  | LottieLayer
  | CustomLayer;

export interface Scene {
  id: string;
  start: number;
  end: number;
  next_start: number;
  transition: Transition;
  palette: Palette;
  layers: Layer[];
  camera: CameraKey[];
  words: Word[];
  /** true when the scene has crash/shake camera keys → CameraMotionBlur */
  motion_blur: boolean;
  /** handheld drift amplitude in px (0 = static) */
  handheld: number;
}

export interface SfxHit {
  name: string;
  t: number;
  vol: number;
  len: number;
}

export interface CaptionsCfg {
  y?: number;
  size?: number;
  max_words?: number;
  max_sec?: number;
  style?: "box" | "outline" | "karaoke";
}

export interface Timeline {
  id: string;
  fps: number;
  width: number;
  height: number;
  duration: number;
  style: Style;
  captions_cfg: CaptionsCfg;
  /** every script word with timing — captions are paged by @remotion/captions at render time */
  words: Word[];
  bgm: { src: string; vol: number } | null;
  sfx: SfxHit[];
  scenes: Scene[];
}

/** Contract for agent-authored components in src/custom/<Name>.tsx */
export interface CustomLayerProps {
  /** absolute seconds on the reel clock */
  now: number;
  /** layer start / scene end (absolute seconds) */
  t: number;
  until: number;
  pal: Palette;
  layer: CustomLayer;
  fps: number;
}
