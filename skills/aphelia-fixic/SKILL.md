---
name: aphelia-fixic
description: Fixic Aphelia — после прогона читает pipeline-fix-queue.md и incident_report во фрагментах, вносит долговременные правки в skills/scripts/shared плагина, обновляет pitfalls, закрывает инциденты.
---

# Aphelia Fixic

Вход: `<run>/pipeline-fix-queue.md`, `<run>/fragments/*.md` (все `incident_report`), `qa-report.md`. Выход: правки файлов плагина, `shared/agent-pipeline-pitfalls.md` (дополнен), `<run>/fixic-report.md`, `fragments/fixic.md`.

## Шаги

1. Собери все инциденты (`severity`, `what`, `workaround`, `durable_fix`). Дедуплицируй.
2. Для каждого решай: правка **скрипта** (`scripts/*.py`, `templates/remotion/src/*`), правка **инструкции** (`skills/*/SKILL.md`, `shared/*.md`), или **pitfall** (запись в `shared/agent-pipeline-pitfalls.md`: симптом → причина → что делать).
3. Скрипты правь минимально и проверяй: `python scripts/validate_storyboard.py --project <run>`, `python scripts/timeline.py --project <run>`, `npx tsc --noEmit` в `templates/remotion`. Ничего не рендерь заново.
4. В `pipeline-fix-queue.md` меняй `status: open` → `status: fixed (<файл>)` или `status: wontfix (<почему>)`.
5. `fixic-report.md`: таблица инцидент → действие → файл.

## Правила

- Не менять контракт `timeline.json` без синхронной правки `templates/remotion/src/timeline-types.ts` и `layers.tsx`/`Scene.tsx`/`Reel.tsx` (tsc должен проходить).
- Не удалять чужие pitfalls.
- Не трогать `voices/` и `aphelia-memory/runs/*` (кроме отчёта и очереди).

## Фрагмент

`=== FIXIC ===`, status, outputs (изменённые файлы), summary, `incident_report: none`.
