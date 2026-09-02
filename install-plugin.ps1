# Installs the Framepro plugin into Cursor's local plugins folder.
# From plugin root:  .\install-plugin.ps1
# Copies rules/agents/skills/commands/scripts/shared/templates/voices (no node_modules, no runs),
# installs Remotion + Playwright deps, sets up ACE-Step 1.5 (music generation) via uv.
# Restart Cursor afterwards so the framepro-* subagents appear in Task.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:USERPROFILE ".cursor\plugins\local\framepro"

if ($here -ieq $dest) {
  Write-Host "Already running from the installed location: $dest" -ForegroundColor Yellow
  exit 0
}

Write-Host "Installing Framepro -> $dest" -ForegroundColor Cyan
if (Test-Path $dest) {
  # keep the heavy ACE-Step checkout (venv + model checkpoints) between reinstalls
  Get-ChildItem $dest -Force | Where-Object { $_.Name -ne "vendor" } | Remove-Item -Recurse -Force
} else {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
}

$items = @(".cursor-plugin", "assets", "rules", "agents", "skills", "commands", "scripts", "shared", "templates", "voices", "docs", "README.md", "LICENSE", "install-plugin.ps1", ".gitignore")
foreach ($item in $items) {
  $src = Join-Path $here $item
  if (-not (Test-Path $src)) { continue }
  if ((Get-Item $src).PSIsContainer) {
    robocopy $src (Join-Path $dest $item) /E /XD node_modules public out __pycache__ .pytest_cache /XF render-*.mp4 data.ts /NFL /NDL /NJH /NJS /NP | Out-Null
  } else {
    Copy-Item $src (Join-Path $dest $item) -Force
  }
}
# sfx/bgm library lives in templates/audio (copied above); vendor/video-shotcraft is only the source and is not copied

Write-Host "npm install (Remotion template)..." -ForegroundColor Cyan
Push-Location (Join-Path $dest "templates\remotion")
npm install --silent
# src/data.ts is generated per run by scripts/sync_remotion.py; a typed empty placeholder keeps `tsc` green before the first render
$dataTs = Join-Path (Get-Location) "src\data.ts"
if (-not (Test-Path $dataTs)) {
  $placeholder = @'
/* eslint-disable */
import type { Timeline } from "./timeline-types";

// PLACEHOLDER — overwritten by scripts/sync_remotion.py before every render.
export const timeline: Timeline = {
  id: "placeholder", fps: 30, width: 1080, height: 1920, duration: 1,
  style: { bg: "#FFFFFF", ink: "#111111", accent: "#C8FF3D", danger: "#FF3B30", muted: "#6B7280", font_head: "Inter", font_hand: "Neucha" },
  captions_cfg: {}, words: [], bgm: null, sfx: [], scenes: [],
};
'@
  [System.IO.File]::WriteAllText($dataTs, $placeholder, (New-Object System.Text.UTF8Encoding $false))
}
Pop-Location

Write-Host "npm install (Playwright capture)..." -ForegroundColor Cyan
Push-Location (Join-Path $dest "scripts\node")
npm install --silent
npx playwright install chromium | Out-Null
Pop-Location

Write-Host "ACE-Step 1.5 (music generation, MIT)..." -ForegroundColor Cyan
$ace = Join-Path $dest "vendor\ace-step"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "  uv not found - install: powershell -ExecutionPolicy ByPass -c ""irm https://astral.sh/uv/install.ps1 | iex""  then re-run" -ForegroundColor Yellow
} else {
  if (-not (Test-Path (Join-Path $ace "pyproject.toml"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $ace) | Out-Null
    git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git $ace
  }
  Push-Location $ace
  uv sync
  Pop-Location
  Write-Host "  model weights (~5 GB) download automatically on the first music generation" -ForegroundColor DarkGray
}

Write-Host "Python deps check..." -ForegroundColor Cyan
python -c "import qwen_tts, whisper, ruaccent, rembg, torchaudio, PIL; print('python deps OK')"

Write-Host "Done. Restart Cursor -> Task shows framepro-* agents. Try: /framepro-new <topic or URL>" -ForegroundColor Green
