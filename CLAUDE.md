# IdleWorlds Toolkit

A single-file calculator, skill planner and gear optimiser for idleworlds.com,
plus the sprite atlases it loads at runtime. **`index.html` is the working
file** — 4.1 MB, ~34,000 lines, no build step, no dependencies, no package
manager. You edit the shipped artefact directly.

This repo is a different project from `idleworlds-fantasy-skin` (the Chrome
reskin extension). Nothing is shared between them.

## Commits

**Do not commit, push or stage anything.** Curtis batches a whole version's
worth of work into one commit he makes himself. Edit the working tree, report
what changed, and stop there. Offering is fine; doing it is not.

## Running it

Open `index.html` in a browser. There is nothing to install and nothing to
build. Verify JS still parses after an edit — this is the cheapest real gate,
and it compiles every inline block without executing any of it (20 blocks, all
passing as of v5.4):

```bash
node -e "const fs=require('fs'),vm=require('vm');const src=fs.readFileSync('index.html','utf8');let m,i=0,bad=0;const re=/<script([^>]*)>([\s\S]*?)<\/script>/gi;while((m=re.exec(src))){if(/type\s*=\s*[\"'](?!text\/javascript)/i.test(m[1]))continue;const line=src.slice(0,m.index).split('\n').length;i++;try{new vm.Script(m[2]);}catch(e){bad++;console.log('FAIL block at line '+line+': '+e.message);}}console.log(i+' blocks checked, '+bad+' failed');"
```

Note `node --check <(...)` does **not** work here — process substitution hands
node a `/proc/self/fd` path it cannot resolve on Windows, and it exits 0 while
printing a module-not-found error, so it looks like a pass. Use the command
above.

A syntax error in this file is silent in the browser except for the block that
contains it — the rest of the page keeps working, so a broken block looks like
"one feature stopped" rather than "the page is dead".

## Self-checks — use them

Fourteen regression suites ship inside the file and are the safety net for
every change. Run them from **Settings → Developer → Run engine self-checks**,
or from the console:

```javascript
iwReleaseCandidateSelfCheck()
```

Each returns an **array of failure strings — empty means pass**. The runner
auto-discovers them by name: *any* global whose exported name ends in
`SelfCheck` is picked up, so a new suite needs no registration (though
`iwReleaseCandidateSelfCheck`'s own explicit `suites` list should still name
it, for a readable per-suite label in its failure output). Stage A also runs
silently at startup and warns to the console.

Suites: `iwAugust2026RegressionSelfCheck` (A) · `iwItemDataBridgeSelfCheck` (B)
· `iwWorkOrderPotionPayoutSelfCheck` (C) · `iwPlus4EquipmentSelfCheck` (D) ·
`iwTailoringStageESelfCheck` (E) · `iwSkillBoostStageFSelfCheck` (F) ·
`iwSilkbindStageGSelfCheck` (G) · `iwAugust2026FinalSelfCheck` ·
`iwFinalAuditSelfCheck` · `iwSetOptimizerAndTaskTierSelfCheck` ·
`iwCharacterStatRoundingSelfCheck` · `iwGearPlannerCurrentDataSelfCheck` ·
`iwGearImportIntegritySelfCheck` · `iwWoodcuttingConstructionSelfCheck` (H).

A suite assertion may be **updated only by the stage that intentionally
changes that mechanic**. Unrelated assertions must stay green.

## Anatomy of index.html

Line numbers drift — grep the anchor instead. Ordered as they appear:

| Region | Anchor | Notes |
|---|---|---|
| Header comments | `IDLEWORLDS TOOLKIT —` | Version history **and an orientation guide to the load-bearing rules. Read it.** |
| Main CSS | `<style>` (first) | ~228 KB. Eight themes: sapphire (default), dark, light, office, emerald, ruby, topaz, pink |
| Body markup | `class="tab-bar"` | Tabs, panels, and a **duplicated bottom nav** (`class="botnav"`) |
| Embedded item data | `id="iw-embedded-items"` | **2.2 MB on ONE line.** 4,452-record snapshot |
| Core engine | `const TIER_NAMES` → `function switchTab` | ~862 KB, the bulk of the logic |
| Woodcutting & Construction data | `WOODCUTTING & CONSTRUCTION  (v5.4)` | Wood/building names, Parts XP, Assembly bill, add-on buffs — see `constructionPartsXpForLevel` / `buildingBuffs` |
| Persistence | `IWStore — persistence` | Generic capture by element id |
| Work Order | `WORK ORDER CALCULATOR MODULE` | |
| Village Add-ons | `VILLAGE ADD-ONS  (v5.4)` | Own IIFE, isolated from the gnModule doll/set-bonus system; feeds `iwSkillLevels()` |
| Regression suites | `AUGUST 2026 REGRESSION` | Stages A–G plus later audit suites, including Stage H (Woodcutting & Construction) |

Engine landmarks, in order: game-data constants (`const TIER_NAMES`) →
Woodcutting & Construction data (`const WOOD_NAMES` through
`villageAddonSlots`, v5.4) → app state and the daily-XP rotation (`const
appState`) → `calculate()` (the Calculator) → `generateSkillPlan()` (the
Planner) → **the gear system** (`const SLOT_META` through
`renderTaskGearAdvisor`, ~8,000 lines and by far the largest surface) → item
database, search and tooltips (`function buildItemDatabase`) → `function
switchTab` → Work Order module → **Village Add-ons module** (v5.4, its own
IIFE) → regression suites A–H.

Tabs: Start · Calculator · Planner · Gear · Community Tools (Work Order,
Jewelry) · Items · Settings.

## Non-negotiable rules

These are stated by the file about itself, in the header comment. They have
each been paid for.

1. **One normaliser.** `buildItemDatabase()`. Online and offline records share
   the API's shape deliberately. A second normaliser is precisely how the two
   drift apart in silence.
2. **Absent is not zero.** A stat that does not apply must be `undefined`,
   never `0`. The card renderer hides absent stats but prints real zeroes, so
   `""` must not be coerced through `Number()`. Empty fields are stripped from
   the embedded payload and that contract is what makes it safe.
3. **The embedded JSON tag is read in exactly ONE place** — `iwEmbeddedItems()`.
   Every other consumer goes through it.
4. **`ITEM_DB` is a frozen back-compatibility VIEW, not the data.** Twelve
   subsystems read it directly and most **fail SILENTLY** — returning empty
   rather than throwing — if a field goes missing. New code should read
   `IDB_STATE.items` instead.
5. **Declaration order is load-bearing.** `_IW_EMBEDDED_CACHE` sits above
   `ITEM_DB` to satisfy the TDZ, not for style.

## Traps

**A dropped field in `ITEM_DB` is invisible, not broken.** This is what v5.3.1
fixed: `itemFind`, `goldFind`, `warfare`, `hp` and `extraStats` were present on
the normalized records and silently dropped crossing into the view. Tooltips
render a stat row only when the field is defined, so 309 items simply never
showed an Item Find row — directly under an effect line that named it. Scoring
was unaffected because `iwItemStats` re-scrapes those numbers out of the
description text, which is exactly why it stayed invisible for so long. When a
stat "doesn't show up", suspect the view before the renderer.

**The repo is also the CDN, and the two versions are pinned by hand.**
`IW_GEAR_SPRITES` and `IW_ITEM_SPRITES` fetch the atlases and manifests from
`raw.githubusercontent.com/BustedCypher/idleWorlds-game-sprites-BC/main/`, cache-busted
by `GEAR_ASSET_VERSION` / `ITEM_ASSET_VERSION` string literals in this file.
The manifest's own `asset_version` field is **never read** — the pin is purely
the `?v=` query string, and the fetch uses `cache: 'default'`.

Measured against the real host (2026-09-03): `raw.githubusercontent.com` sends
`Cache-Control: max-age=300` and ignores the `?v=` string entirely — it always
serves whatever is currently on `main`, pinned string or not. So a forgotten pin
bump is **bookkeeping drift that self-corrects within five minutes**, not an
indefinite-cache bug; the browser's own 300s cache is the only thing the string
defeats, and even that clears itself fast. (An earlier version of this note
overstated this as a live defect — `…lapidaryfix-plus4restore1` vs a stale
`…lapidaryfix1` pin — checked and fixed in the same pass as this correction.)

Bump the pin in the same change as any atlas/manifest replacement anyway: it is
the only human-readable record of which art `index.html` expects, and it is
what would make a future move to a real long-cache CDN safe. Atlas PNG and
manifest must always be replaced together.

**Same-origin is a hard requirement for live data.** Profile import hits
`/api/player-profile` same-origin. `items.json` tries same-origin `/items.json`
first, then absolute. v5.3 exists *because* the absolute origin returns 200 with
**no `Access-Control-Allow-Origin` header** — so every browser discarded the
response and the toolkit silently ran on the embedded snapshot forever. A
data-loading change that "works" on a static host has not been tested. The
daily-XP-boost scraper falls back through `r.jina.ai` and `allorigins.win`
readers; failure there is soft by design and the built-in rotation stands.

**One import must equal one repaint.** `applyProfile()` dispatches synthetic
`change` events on housing-tier / race-select / combat-level, and `schedule()`
is bound to `change` on exactly those controls. Before v5.3 this re-entered the
repaint scheduler once per field and rebuilt the character panel 6–8 times,
re-animating every meter from 0% — the visible "stutter". `schedule()` is now
purely trailing and `applyProfile()` holds a re-entrancy guard. Do not add a
field write to `applyProfile()` outside that guard.

**Set bonuses are properties of a whole loadout.** Patching one set family at a
time can recommend mutually impossible slot combinations. The classic 6-piece,
Conqueror/Elementbound/Juggernaut and tailoring-set optimisers are deliberately
one shared system — see `FINAL OPTIMIZER CORRECTION`.

**Two paths choose a cloak** — `resolveCloakSlot()` for the tier cards and
`iwBestInSlot()` for the goal loadout. Self-check 19 asserts they agree. Read
the block beside `SLOT_META` before changing either.

**Anything written inline with `important` priority beats every stylesheet
rule.** The sprite services write `background-image`/`-position`/`-size`
inline on their host elements.

## Persistence

`localStorage` keys: `iw_state_v2` · `iw_theme_v1` · `iwSocketPlanV1` ·
`iwPlatePlanV1` · `iwEnchantPlanV1` · `iwEnhancementRemovalPlanV1` ·
`iwReTierSettingV1` · `iwShoppingOwned` · `iwShoppingGear` ·
`iwCollapseSkills` · `iw_gem_alltiers_v1` · `iwVisitedTool` ·
`iw_gear_expanders_v1` · `iwVillageAddonsV1`.

Two rules govern `IWStore`: **capture is generic** (every `<input>`/`<select>`
carrying an id is snapshotted by id, so new controls persist automatically),
and **restore replays the app's own paths** — never write engine state
directly, set a value and dispatch the event the user would have caused.

## Repo contents

- `index.html` — **v5.4, the working file**
- `index2.html` — v5.2, a stale near-duplicate. Will rot silently.
- `IdleWorlds_Toolkit_v4_8.html` — v4.8 fallback build
- `gear_icons_atlas.png` + `gear_icons_manifest.json`/`.csv` — 1280×19584,
  10×153 grid, 128 px cells (64 px logical at 2×), 1146 icons, manifest v7
- `item_icons_atlas.png` + `item_icons_index.csv`/`item_icons_cells.csv` —
  1280×4864; 1167 index rows over 375 shared cells
- `Skillsim/index.html` — separate developer balance tool
- `README.txt` — **stale**: claims 10×150, 1280×19200, 1118 icons. The atlas
  and manifest agree with each other; only the README is wrong.

`CHANGELOG.md` is referenced by the header comment as holding the relocated
~123 KB release history. **It has never been committed to this repo, on any
branch.** Do not cite it as a source.

## Verification discipline

- Say which kind of verification you did. "Parses and I read the code" is not
  "I loaded it in a browser". No session can verify live; only Curtis can.
- **A check reporting zero is broken, not passing.** The self-check suites
  return an empty array on success — confirm you are distinguishing "empty
  result" from "function missing", which the runner skips silently via
  `typeof pair[1] !== 'function'`.
- Break a new check on purpose and confirm it fails before trusting it.
- The embedded item payload is one 2.2 MB line. Never print it, and be careful
  with greps that could match inside it.
