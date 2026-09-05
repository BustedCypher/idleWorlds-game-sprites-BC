# Construction & Village Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add the approved split desktop / guided mobile Construction & Village Planner to Community Tools.

**Architecture:** Keep the existing recipe and artwork sources authoritative. Add a pure, dependency-free planner engine and a scoped UI module/style sheet, loaded by small guarded integration changes in index.html. Current village, hypothetical targets, and manually entered inventory are separate local state; do not mutate the legacy Gear add-on plan or imported stats.

**Tech Stack:** Classic JavaScript, existing HTML/CSS theme tokens and sprite loader, Node's test runner; no build step or package dependencies.

**Spec:** C:/Users/curti/.codex/visualizations/2026/09/05/01a06f15-bf19-7b60-9a73-c749e4f8d544/design-review.md. Approved by user: split view desktop, guided mobile; user explicitly said proceed.

## Global Constraints

- Work in the current checkout, uncommitted; no staging, commit, push or deployment.
- Preserve unrelated and untracked user work. Overwrites in this repository must use tools/atomic_write.py.
- No membership gate: the live construction wiki says free for everyone.
- Reuse assemblyInputs, WOOD_NAMES, ORE_NAMES, BUILDING_NAMES, buildingBuffs, HOUSE_ICONS, effectiveDuration and sprite APIs. Do not copy the embedded item payload.
- One slot per housing tier, maximum five. One installed building of each type. Retain assignments beyond a reduced housing tier, flagged as inactive.
- Separate manually confirmed current buildings from planned buildings. The Gear panel's iwVillageAddonsV1 is hypothetical and must never be silently imported as current.
- Blank stock is unknown, not zero; never deduct raw materials used in owned Parts again.
- Refund is 25% of direct Assembly cost, not expanded raw cost. Show fractional results as before rounding; do not automatically credit them to inventory.
- No invented acquisition routes, prices, travel durations, account writes or optimization claims.

## Task 1: Pure resource and village model

**Files:** Create assets/construction-planner-engine.js and tests/construction-planner.test.js.

**Interfaces:** Export UMD/CommonJS IWConstructionPlannerEngine.create(adapter). Adapter provides building(tier) => {tier,name,inputs:[{key:'parts'|'wood'|'ore',tier,qty,label}],buffs:{primary,secondary,skill}}, woodName(tier), oreName(tier). Instance exposes requirements(tiers,inventory,timing), village(housingTier,installed,planned), bonuses(tiers), refund(tier).

requirements output: assemblyRows, partsRows, rawRows. Every row has id (kind:tier), kind, tier, name, required, owned (number or null), missing (number or null), upperBound (nonnegative), provisional (boolean). Assembly rows aggregate direct inputs; partsRows contain the Parts subset; rawRows aggregate direct raw inputs and ingredients of missing Parts. Unknown Parts make their raw dependency provisional. Unknown raw stock or provisional required input makes missing null; upperBound assumes zero for unknown stock. Inventory keys are kind:tier. Include completeInventory, unknownItems (IDs), craftCount, gatherActions:{woodcutting,mining}, times:{woodcutting,mining,parts,assembly,total}. Timing accepts woodcuttingSeconds,miningSeconds,partsSeconds,assemblySeconds,gatherYield. Missing/invalid timing or stock => null times, never a plausible exact total. Only known, positive timing and complete stock produce totals. Sum Math.ceil(missing/gatherYield) separately for each raw item. craftCount is sum of missing Parts; each selected tier is one Assembly.

village returns {capacity,installed,planned,currentTiers,futureTiers,conflicts,inactiveSlots}. Arrays preserve all five entries (null or integer 1–34); planned null means no replacement. Only active slots contribute tiers. Conflicts are {kind:'current'|'planned',tier,slots:[zero-based indices]}; retain invalid duplicate assignments to report rather than silently changing them. Housing None yields zero capacity. inactiveSlots includes occupied or planned indices beyond capacity. bonuses returns {stats:{stat:number},skills:{skill:number}}. refund returns direct bill rows with qty multiplied by 0.25 and roundingRequired.

- [x] Write failing tests. Independently derived fixtures must include Training Yard (200 Copper Parts,100 timber,50 ore); stock Parts50/timber100/ore25 => Parts150, timber300, ore175. Test known zero, unknown/blank/negative/NaN stock, lower-tier Parts and shared stock across two buildings, all Parts owned, no input mutation, invalid timing, housing cap/None, planned duplicates, current-vs-future bonuses, and direct-cost refund (50 Parts,25 timber,12.5 ore before rounding).
- [x] Run node --test tests/construction-planner.test.js and observe the expected missing feature failure.
- [x] Implement the module against these contracts. Use supplied data callbacks; do not read DOM/localStorage or reimplement building formulas.
- [x] Run the focused tests and node --check assets/construction-planner-engine.js; report behavior and any interface clarifications.

## Task 2: Scoped UI and toolkit integration

**Files:** Create assets/construction-planner.js, assets/construction-planner.css; update index.html through atomic writes; add the planner key to the toolkit reset allowlist.

**Consumes:** Task 1 engine contract. Existing game constants/functions are passed in a bridge built at the end of index.html, after all source modules exist.

**Produces:** window.iwConstructionPlannerEnter(), window.iwConstructionPlannerSelfCheck(), Community Tools tab construction-village. UI persists under iwConstructionVillageV1.

- [x] Add desktop and mobile Community Tools children and a tab-pane, mark it as a Community Tool in switchTab, refresh on entry. Load CSS and engine/UI scripts once. Preserve all original hooks.
- [x] Build the approved desktop split layout with a central housing illustration and five accessible plot buttons. On mobile show Slot → Building → Requirements → Production with a compact dwelling after slot selection. Provide equivalent slot-list selection.
- [x] Add setup controls: use toolkit settings, local housing override, pre-village effective Construction/Woodcutting/Mining levels, current gathering yield, and current-village editor. Reuse imported base+equipment via iwSkillLevels but subtract its source entries with via:'addon' before adding this module's confirmed current bonuses. Never write to shared settings or the Gear add-on model.
- [x] Build the 34-entry searchable catalogue with exact artwork/buffs, stat and skill filters, level status and duplicate prevention. Allow aspirational plans with visible unmet gates; current building editing must reject duplicate types. Display one primary, two secondary, and one skill bonus distinctly. Use the existing item tooltip service for material details where available.
- [x] Display selected building direct bill with manual owned quantities and missing Parts expansion. Add whole-plan resource scope so multiple saved buildings share stock once. A plan may be edited or cleared locally; no action pretends to construct/install in game.
- [x] Wire raw stock inputs and production sequence. Use wiki timber zones from the existing zone table, or zone tier labels if unavailable. Estimate gathering, Parts and Assembly using current validated inputs and existing effectiveDuration. Suppress elapsed total when inventory, skills or activity access are incomplete. No planned bonuses or prospective refunds in gathering timing.
- [x] Show current/future village bonus deltas and direct-cost 25% refund previews on replacements. Preserve hidden-slot assignments when housing changes. Distinguish source labels: toolkit, manual current village, local plan, unknown inventory.
- [x] Persist and restore local state defensively; re-render on profile/equipment and shared setting changes without overwriting manual overrides. Avoid whole-form replacement while typing to preserve focus.

## Task 3: Review and verification

**Files:** Tests and docs as needed; no unrelated repairs.

- [x] Run node tools/check-inline-scripts.js index.html, node --test tests/construction-planner.test.js tests/icon-sprites-v2.test.js, Python unittest discovery and tools/guard_working_files.py --check.
- [x] Inspect browser desktop, tablet and mobile; exercise navigation, art loading, unknown stock, lower-tier expansion, duplicate rejection, replacement preview, housing downgrade/restore, plan persistence and local clear. All-owned stock and profile refresh semantics also covered by focused Node tests.
- [x] Attempt the toolkit's real engine self-checks through its Developer UI. Attempted: the in-app browser crashed before a report; global suite remains unverified, not counted as passing.
- [x] Request a focused implementation review; fix supported findings and rerun affected checks.
- [x] Update docs with actual completed behavior and remaining limitations. Leave the working tree uncommitted and report changed files and validation.

Completion: see docs/construction-village-planner.md for behavior, verification and limitations. The unrelated Python unsafe-write failure persists; the global browser self-check run crashed before reporting. No staging, commit, push or deployment performed.
