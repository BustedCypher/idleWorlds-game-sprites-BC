# Skill Tools and Open Homestead Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Construction and Jewelry into Skill Tools, replace the village panel with an illustrated open homestead, and show installed, planned, and previewed building buffs immediately.

**Architecture:** Keep the existing tab and planner state identifiers. Add navigation grouping through the existing expandable-nav pattern, add a pure display-lineup helper to the planner UI module, and load one optimized housing sprite atlas with an existing SVG fallback. Confirmed installed bonuses remain the only bonuses that affect effective skill levels.

**Tech Stack:** Classic HTML/CSS/JavaScript, Node test runner, existing IdleWorlds sprite and housing SVG infrastructure, generated transparent PNG atlas.

**Spec:** `docs/superpowers/specs/2026-09-05-skill-tools-village-scene-design.md`

## Global Constraints

- Construction Planner and Jewelry Planner belong to Skill Tools on desktop and mobile.
- Work Order Calculator is a standalone tab; the one-item Community Tools group is removed.
- Existing tab names, pane IDs, entry hooks, storage key, recipes, buffs, and material behavior remain compatible.
- Preview replaces the selected slot only in displayed bonuses; it never changes confirmed skill levels or the saved whole-plan bill.
- Locked-slot previews remain visible but do not contribute to active totals.
- Use five consistent transparent housing sprites with SVG fallback and keep plot buttons accessible.
- Exclude unrelated untracked workspace files from every commit.

---

### Task 1: Display-lineup bonus model

**Files:**
- Modify: `assets/construction-planner.js`
- Modify: `tests/construction-planner-ui.test.js`

**Interfaces:**
- Consumes: normalized planner state and `engine.village(housing, installed, planned)`.
- Produces: exported `displayLineup(state, village)` returning `{rows, activeTiers}`. Each row is `{slot,tier,state,active}` where state is `installed`, `planned`, or `preview`.

- [ ] **Step 1: Write failing precedence tests**

Add fixtures proving installed tier 1 becomes planned tier 2, then preview tier 3 in the selected slot; other slots retain their effective occupants. Assert a locked preview row exists with `active:false`, and assert duplicate tiers occur only once in `activeTiers`.

```js
const result = ui.displayLineup(
  {selectedSlot:0,targetTier:3,installed:[1,4,null,null,null],planned:[2,null,null,null,null]},
  {capacity:2}
);
assert.deepEqual(result.rows[0], {slot:0,tier:3,state:'preview',active:true});
assert.deepEqual(result.activeTiers, [3,4]);
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `node --test tests/construction-planner-ui.test.js`

Expected: FAIL because `displayLineup` is not exported.

- [ ] **Step 3: Implement the pure helper**

Build effective rows from installed and planned slots, replace the selected slot with `targetTier`, mark slots at or above capacity inactive, and deduplicate `activeTiers` without dropping visible rows. Export the helper through the existing UMD return object.

- [ ] **Step 4: Render per-building bonuses and totals**

Rename the section to Equipped & Previewed Bonuses. Render each display row with building name, state, primary, two secondary buffs, and skill buff. Mark locked previews Requires housing upgrade. Calculate the summary from `activeTiers`. Keep `currentBonuses = engine.bonuses(village.currentTiers)` for `resolveSetup`; do not substitute displayed bonuses.

- [ ] **Step 5: Verify focused tests**

Run: `node --test tests/construction-planner-ui.test.js tests/construction-planner.test.js`

Expected: all planner tests pass.

---

### Task 2: Skill Tools navigation

**Files:**
- Modify: `index.html`
- Create: `tests/skill-tools-navigation.test.js`

**Interfaces:**
- Consumes: existing `switchTab`, expandable desktop navigation, and mobile bottom-navigation group pattern.
- Produces: `.skill-tools-toggle`, `#skill-tools-desktop`, and `#skill-tools-mobile` containing the existing construction-village and jewelry tab buttons.

- [ ] **Step 1: Write static integration tests**

Read `index.html` and assert two Skill Tools toggles exist, Construction and Jewelry each appear once within desktop and mobile Skill Tools containers, Work Order occurs outside those containers, and `switchTab` recognizes only construction-village and jewelry as Skill Tools children.

- [ ] **Step 2: Run the navigation test and confirm failure**

Run: `node --test tests/skill-tools-navigation.test.js`

Expected: FAIL because Skill Tools markup does not exist.

- [ ] **Step 3: Replace the navigation group surgically**

Promote Work Order to a direct tab button. Rename the expandable parent, container IDs, classes, labels, toggle function, and active-state logic from Community Tools to Skill Tools. Keep data-tab values `construction-village` and `jewelry` unchanged.

- [ ] **Step 4: Verify navigation and script parsing**

Run:

```text
node --test tests/skill-tools-navigation.test.js
node tools/check-inline-scripts.js index.html
```

Expected: tests pass and `parseErrors` is empty.

---

### Task 3: Housing sprite atlas and open-field scene

**Files:**
- Create: `assets/housing/player-housing.webp`
- Modify: `assets/construction-planner.js`
- Modify: `assets/construction-planner.css`
- Modify: `index.html`
- Modify: `tests/construction-planner-ui.test.js`

**Interfaces:**
- Consumes: `houseArt(tier)` callback and existing `HOUSE_ICONS` fallback.
- Produces: `housingArt(tier, label)` markup selecting one of five horizontal atlas cells; falls back to supplied SVG through an image error handler or CSS fallback layer.

- [ ] **Step 1: Generate and inspect housing artwork**

Create a transparent five-cell atlas in a consistent three-quarter fantasy-game perspective: Camp, Cottage, Villa, Manor, Citadel. Each cell uses the same canvas footprint, ground contact, warm lighting, and detail level. Inspect at original resolution and at the intended rendered size; regenerate if silhouettes, transparency, or tier progression are unclear.

- [ ] **Step 2: Add failing sprite mapping tests**

Assert housing tiers 1–5 emit distinct atlas positions, tier 0 emits only the empty-foundation fallback, and accessible housing names remain visible text outside decorative artwork.

- [ ] **Step 3: Implement the housing-art bridge**

Pass the atlas URL and existing SVG fallback through the planner install options. Build housing art markup without changing the add-on sprite service. Add cache-version query parameters to changed assets.

- [ ] **Step 4: Rebuild the scene as Open Homestead**

Let the field fill the village panel, center the large housing artwork, and arrange five smaller plot buttons around it. Keep explicit Installed, Planned, Preview, Available, and Locked labels. Set the housing art near 180px desktop and the add-on art near 70px, with responsive reductions at tablet and mobile widths.

- [ ] **Step 5: Implement compact later-stage housing banner**

On mobile stage 0, show the full field. On stages 1–3, show the housing artwork, housing name and tier, selected slot, and selected building state in a compact row before the active content.

- [ ] **Step 6: Verify focused tests and assets**

Run:

```text
node --test tests/construction-planner-ui.test.js tests/construction-planner.test.js tests/skill-tools-navigation.test.js
node --check assets/construction-planner.js
```

Expected: all tests and syntax checks pass.

---

### Task 4: Browser verification and delivery

**Files:**
- Modify: `docs/construction-village-planner.md`

**Interfaces:**
- Consumes: completed navigation, lineup, art, and scene tasks.
- Produces: tested responsive feature on `main` and updated user documentation.

- [ ] **Step 1: Verify desktop navigation and scene**

At 1280px, open Skill Tools, enter Construction Planner, cycle housing None through Citadel, and confirm the field, housing art, plot accessibility, active parent state, and no horizontal overflow. Open Jewelry Planner and confirm Skill Tools remains active. Open Work Order and confirm it is standalone.

- [ ] **Step 2: Verify preview bonus behavior**

Record installed buildings, add planned replacements, and browse a third building without saving it. Confirm per-building rows and total precedence, no duplicate contribution, unchanged effective skill levels, unchanged whole-plan scope, and locked-preview labeling.

- [ ] **Step 3: Verify tablet and mobile**

At 768px and 360px, verify scene layout, readable housing art, all four guided steps, compact later-stage banner, touch targets, and zero horizontal overflow.

- [ ] **Step 4: Run complete relevant checks**

Run:

```text
node --test tests/construction-planner.test.js tests/construction-planner-ui.test.js tests/skill-tools-navigation.test.js tests/icon-sprites-v2.test.js
node tools/check-inline-scripts.js index.html
python tools/guard_working_files.py --check
git diff --check
```

Record the known unrelated Python unsafe-write failure only if the wider discovery suite is rerun and still fails in `tools/rebuild_skill_atlases.py`.

- [ ] **Step 5: Update documentation**

Document Skill Tools placement, Open Homestead behavior, housing sprites, Equipped & Previewed Bonuses semantics, locked-preview behavior, and the distinction between displayed and confirmed skill bonuses.

- [ ] **Step 6: Commit and push only feature files**

Stage the modified planner, navigation, tests, sprite asset, design/plan documentation, and user documentation. Confirm unrelated untracked files remain unstaged. Commit with `Add Skill Tools open homestead` and push `main` to `origin`.
