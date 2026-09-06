

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

- [ ] Write failing tests. Independently derived fixtures must include Training Yard (200 Copper Parts,100 timber,50 ore); stock Parts50/timber100/ore25 => Parts150, timber300, ore175. Test known zero, unknown/blank/negative/NaN stock, lower-tier Parts and shared stock across two buildings, all Parts owned, no input mutation, invalid timing, housing cap/None, planned duplicates, current-vs-future bonuses, and direct-cost refund (50 Parts,25 timber,12.5 ore before rounding).
- [ ] Run node --test tests/construction-planner.test.js and observe the expected missing feature failure.
- [ ] Implement the module against these contracts. Use supplied data callbacks; do not read DOM/localStorage or reimplement building formulas.
- [ ] Run the focused tests and node --check assets/construction-planner-engine.js; report behavior and any interface clarifications.

