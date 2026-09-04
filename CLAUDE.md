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

**Icon loading was rewritten from a GitHub-hosted atlas to same-origin,
demand-loaded chunks (2026-09-01, `publish-icon-split.yml` CI, merged into
`index.html` alongside the v5.4 Woodcutting & Construction work).** The old
`IW_GEAR_SPRITES` / `IW_ITEM_SPRITES` IIFEs — hand-pinned
`GEAR_ASSET_VERSION` / `ITEM_ASSET_VERSION` strings, fetches from
`raw.githubusercontent.com` — are **gone from `index.html` entirely**. Any
note (including in old commit messages or stale docs) about bumping those
version strings no longer applies to anything; there is nothing left in this
file to bump.

In their place: `index.html` loads `./assets/icon-sprites-v2.js` (a UMD
module, `window.IWIconSpritesV2`), which is `.install()`ed against
`./assets/icons/v2/icon-manifest.<hash>.json` right where the old IIFEs used
to sit — search `ICON CHUNKS v2` in the header comment region. That install
call sets `window.IW_GEAR_SPRITES` / `window.IW_ITEM_SPRITES`, and
`index.html` just reads them (`var IW_GEAR_SPRITES = window.IW_GEAR_SPRITES;`)
— the two globals still exist and every existing call site
(`IW_GEAR_SPRITES.markup(...)`, `.hydrate(...)`, `.splitItemName(...)`, etc.)
is unchanged. The manifest and every PNG chunk filename carries a content
hash (`icon-manifest.b9aa386e5137.json`, `weapon.5dc16a6236f1.png`, …), so
each one is immutable and self-versioning — there is no cache-pin string to
maintain by hand any more, and no bookkeeping-drift trap either. Chunks
demand-load via `IntersectionObserver` as icons approach the viewport
(`rootMargin: '300px 0px'`), decoded once and cached per session.

The legacy `gear_icons_atlas.png` / `gear_icons_manifest.json`/`.csv` and
`item_icons_atlas.png` / `item_icons_index.csv`/`item_icons_cells.csv` files
remain in the repo as the deterministic **build source** for the chunks
(`python tools/build_icon_chunks.py` regenerates `assets/icons/v2/*` from
them) and as a rollback path — `index.html` itself no longer reads any of
them at runtime. Validate a chunk rebuild with
`python tools/verify_icon_migration.py`, `node --test tests/icon-sprites-v2.test.js`,
and `node tools/check-inline-scripts.js index.html`.

**Adding new art means editing the legacy source, then rebuilding.** Paint the
128 px cells into `item_icons_atlas.png` (or the gear atlas), add the matching
rows to the two CSVs, run `build_icon_chunks.py`, and **re-pin `manifestUrl` in
`index.html` to the new manifest hash it prints** — the rebuild renames every
chunk, so an un-repinned `index.html` 404s the manifest and every icon falls
back to its emoji. `verify_icon_migration.py` catches exactly that. The rebuild
is byte-reproducible for a given Pillow, but a Pillow upgrade re-encodes every
chunk (same pixels, new hashes); that is expected, not a content change.

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
  10×153 grid, 128 px cells (64 px logical at 2×), 1146 icons, manifest v7.
  **Legacy build source only** since the 2026-09-01 icon-split — `index.html`
  no longer fetches these at runtime; see the icon-loading note above.
- `item_icons_atlas.png` + `item_icons_index.csv`/`item_icons_cells.csv` —
  1280×6144; 1269 index rows over 477 shared cells. Same legacy-build-source
  status as the gear atlas above. Both CSVs are **CRLF** — keep it that way or
  a small addition reads as a whole-file diff.
- `construction_icon_manifest.json` — provenance for the 102 v5.4 Woodcutting
  & Construction icons (34 timber, 34 Building Parts, 34 buildings) added to
  the item atlas on 2026-09-04: source filename, pixel size and sha256 per
  item. The art pack itself is ~390 MB of 1.5k-square PNGs and is **not in
  this repo** — it lives at `Desktop/idleWorlds-art-source/construction-2026-09-04/`.
  `tools/import_construction_icons.py <art-pack-dir>` folds it in (idempotent;
  alpha-trim → fit 112×112 → centre on a transparent 128×128 cell).
- `assets/icon-sprites-v2.js` + `assets/icons/v2/*` — the runtime icon
  system `index.html` actually loads now: a UMD loader plus content-hashed,
  demand-loaded manifest/PNG chunks. Rebuilt from the legacy atlases by
  `tools/build_icon_chunks.py`.
- `Skillsim/index.html` — separate developer balance tool
- `README.txt` — describes the current `assets/icon-sprites-v2.js` runtime
  and its build/validate commands. Rewritten 2026-09-01 in the same pass as
  the icon split; the old "stale — claims 10×150, 1280×19200, 1118 icons"
  problem this note used to flag no longer applies (that text is gone).

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

## Never patch `index.html` by rewriting the whole file

**Paid for on 2026-09-04: a Python read-modify-write truncated `index.html` to
0 bytes.** Use a surgical editor (the Claude Code Edit tool, or `sed -i`) that
replaces a matched span. If a script must rewrite the file, it MUST serialise
to memory and then `os.replace()` a temp file into place — that is what
`tools/atomic_write.py` exists for, and it is the **only** sanctioned way for a
tool here to overwrite anything.

Three gates now enforce this. They are not advice; two of them run whether you
remember them or not.

| # | Gate | Fires | What it does |
|---|---|---|---|
| 1 | `tools/atomic_write.py` | when a tool writes | `replace_atomically()` — the corruption never happens |
| 2 | `tools/guard_working_files.py`, wired to hooks in `.claude/settings.json` | **every** Bash/Write/Edit call, and at session start | tripwire + rolling backup: damage becomes a blocking error on the very next tool call, with a known-good snapshot named in the message |
| 3 | `tests/test_no_unsafe_writes.py` | `python -m unittest discover -s tests` | AST scan of `tools/` and `tests/` — the pattern cannot be reintroduced |

Recovery, when gate 2 trips:

```bash
python tools/guard_working_files.py --restore
```

Snapshots live in `.claude/backups/` (gitignored, last 8 per file). Gate 2
costs ~75 ms per tool call and skips the byte-level check entirely when
`(size, mtime)` say nothing moved. `--self-test` breaks all 12 of its own
checks on purpose; run it if you change one.

Two things combined to cause the original loss, and each is invisible on its own:

1. `Path.write_text()` / `open(path, 'w')` **truncates the target the instant
   it returns** — before the encoder has looked at a single byte. So *any*
   exception during encode or write leaves 0 bytes where the file was. It is
   not a transaction and there is no rollback.
2. **`'🏛'` means different things to Python and to JavaScript.** JS
   folds the surrogate pair into 🏛. Python keeps two lone surrogates, which
   `str` permits and UTF-8 cannot encode — `UnicodeEncodeError: surrogates not
   allowed`, raised *after* step 1 truncated the file. Writing a JS escape
   sequence inside a Python string literal is the trap. `index.html` already
   holds 219 literal astral emoji, so just type the character.

3. **A trailing `# comment` on a one-line Python statement swallows the rest of
   it.** These tools pack whole statements into 140 characters; appending a
   marker to `...write_bytes(ad); runtime['audit_path']=an` silently dropped
   the assignment and shipped a manifest with no `audit_path`. Put the comment
   on the line *above* — gate 3 accepts the marker there for exactly this reason.

Also: `Path.read_text()` with **no** `encoding=` uses the locale codec — cp1252
on Windows, which cannot decode this file at all. Every tool here now passes
`encoding='utf-8'` explicitly, and gate 3 fails if a new one does not, so
`PYTHONUTF8=1` is **no longer needed** for anything in this repo. Older notes
telling you to prefix commands with it are stale.

**A fourth trap, outside the repo's control:** backslash escapes in a script
delivered through a shell heredoc are **not** reliable — `'\\uD83C'` written in
a quoted `<<'EOF'` heredoc arrived on disk as `'\uD83C'` (confirmed with
`od -c`), which is what produced the lone surrogates in the first place. Do not
put `\u`, `\r\n` or `\t` escapes in heredoc-delivered Python. Use a real editor
tool, or build the characters with `chr()`.
