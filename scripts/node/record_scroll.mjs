import { chromium } from "playwright";

// Record a smooth scroll of a web page (browser-frame insert for reels).
// usage: node record_scroll.mjs <url> <outDir> [seconds=8] [scrollPx=42]
const url = process.argv[2];
const outDir = process.argv[3] || "./videos";
const seconds = Number(process.argv[4] || 8);
const step = Number(process.argv[5] || 42);

const browser = await chromium.launch();
const t0 = Date.now(); // recording starts with the context
const context = await browser.newContext({
  viewport: { width: 1080, height: 1400 },
  deviceScaleFactor: 1,
  locale: "ru-RU",
  recordVideo: { dir: outDir, size: { width: 1080, height: 1400 } },
});
const page = await context.newPage();
await page.goto(url, { waitUntil: "load", timeout: 60000 });
await page.waitForTimeout(2500);
// dismiss common cookie banners
for (const sel of [
  "button:has-text('Принять')",
  "button:has-text('Accept')",
  "button:has-text('Согласен')",
  "button:has-text('Хорошо')",
  "button:has-text('Понятно')",
  "button:has-text('ОК')",
  "button:has-text('OK')",
  "[aria-label='Close']",
]) {
  const b = page.locator(sel).first();
  if (await b.count()) {
    try {
      await b.click({ timeout: 800 });
    } catch {}
  }
}
await page.waitForTimeout(700);
// short pages: scale the step so the scroll lasts the whole clip instead of hitting the bottom early
const maxScroll = await page.evaluate(() => Math.max(0, document.documentElement.scrollHeight - window.innerHeight));
const ticks = Math.round((seconds * 1000) / 90);
const px = Math.max(8, Math.min(step, Math.floor(maxScroll / Math.max(1, ticks))));
const scrollStartMs = Date.now() - t0;
const tickStart = Date.now();
for (let i = 0; i < ticks; i++) {
  await page.mouse.wheel(0, px);
  await page.waitForTimeout(90);
}
const scrollEndMs = Date.now() - t0;
await page.waitForTimeout(600);
const video = page.video();
await context.close();
await browser.close();
console.log(JSON.stringify({ file: await video.path(), scrollStartMs, scrollEndMs, tickMs: (Date.now() - tickStart) / ticks, px, maxScroll }));
