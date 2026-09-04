# Woodcutting & Construction — findings and implementation plan

**Target toolkit:** `index.html` v5.3.1 (3.9 MB, 32,898 lines, 19 inline script blocks)
**Written:** 2026-09-03
**Audience:** the implementing session. Every anchor below is a **grep string**, not a
line number, because line numbers drift. Every formula below was verified against
data, not inferred — see §1.4 for what was checked and how.

**Implementation status (2026-09-03): Phases 0–6, 8 and 9 done, tested end-to-end in a
real browser against the actual code (not simulated), and shipped as v5.4.** Phase 7
(sprite atlas art) was not done — it needs real image assets nobody has produced yet;
the tooltip falls back to the category emoji, which is fine. Phase 8 (the companion
gather-skill gate, described below as optional) was done on request: generic across
all five craft skills, not a Construction-only special case — see
`CRAFT_LEAF_COMPANION_SKILL` / `companionSkillGateNote()`, verified against the game
client's own generic label helper and wired into the Calculator's "Skill level
required" row ("Lv 69 + Mining Lv 65"). Two things were found and fixed along the way
that this plan didn't anticipate: `onSkillBtnClick`'s hardcoded sub-panel-hiding array
and the per-panel sub-button click-listener wiring both needed a `construct-*` entry
added, or the Construction sub-panel would have been dead on arrival. `index.html`'s
own header comment (search `v5.4 Woodcutting & Construction`) and `CLAUDE.md` were
both updated to match what actually shipped.

---

# PART 1 — FINDINGS

## 1.1 Sources consulted, and which of them is authoritative

| Source | What it gave | Trust |
|---|---|---|
| `C:\Users\curti\Desktop\woodcutting-construction.json` (attached, 152 KB, generated 2026-09-02) | 34 wood resources, 34 chop activities, 34 Parts items, 34 Parts recipes, a 143-row effective-level XP table, 34 buildings with buffs, 34 assembly recipes | **Authoritative.** Every row reproduced exactly by the formulas in §1.4. |
| `https://idleworlds.com/wiki/construction` | Full prose + three tables, "pulled live from the actual game data" | Authoritative, agrees with the JSON. One display quirk: it prints **"Gathering"** where the JSON says **`herbing`** (tiers 3, 12, 21, 30). Same skill; the wiki uses the in-game display name. |
| `https://idleworlds.com/items.json` (fetched live, 5.49 MB, **4,452 records**) | The 102 new item records + `premium_token` | Authoritative. |
| **The game's own client bundle** — `/_next/static/chunks/9811-e028299d74e5f530.js` and `6912-bfe0330e5f3ba0a6.js` | The literal source expressions for every XP curve, every recipe input, the lower-tier pick RNG, the buff generator, the skill-bonus aggregation and the add-on slot rule | **Decisive.** This is generated code, not documentation, so it cannot be stale relative to the wiki. |
| `https://idleworlds.com/api/player-profile?id=cmocbus5z0e3kkqo3sgg7iw7d` (Curtis's own, fetched live) | Proof the live profile API **already returns both skills** | Decisive. |
| `https://idleworlds.com/wiki/daily-xp-boost` | The 4-day rotation, unchanged | Authoritative but see §1.7 Q3. |

Everything in Part 2 is derived from those. Nothing is invented.

---

## 1.2 The two skills, mechanically

### Woodcutting — a third gathering skill, structurally identical to Mining

- 34 activities, one per zone, `Chop <Wood>`, 10 s, yields **1** wood.
- Level gate `1 + (t−1)×4` — the toolkit's existing `TIER_LVL`, unchanged.
- XP/action `Math.round(skillXpForTier(t) × 1.1)` — the **same expression** the
  game uses for `mine_*` and `gather_*`. See §1.5 for why this matters.
- Benefits from 2× Gather Chance (it is `type:"gathering"` in the game data,
  `rewards:[{quantity:1}]`, same as ore/herb/fibre).
- Requires Premium Membership.
- **No equipment anywhere in the game grants a Woodcutting level bonus.** The only
  sources are three village add-ons (T8 +1, T17 +2, T26 +2).

### Construction — two tracks that must never be conflated

**Track A — Building Parts. This is the whole levelling loop.**

- 34 recipes, 10 s each, `2t` wood + `t` ore → 1 Parts.
- **XP is decoupled from the recipe tier.** It is a function of your *effective
  Construction level* only. Crafting T1 Copper Building Parts at Construction 133
  awards the identical 2,736 XP as crafting T34 Primordite Building Parts — but
  costs 3 gathers instead of 102.
- Consequence, and this is the single most important thing the toolkit can tell a
  player:

  | Recipe used at effective Construction 133 | inputs | loop | XP/craft | XP/hr |
  |---|---|---|---|---|
  | **T1 Copper Building Parts** | 2 wood + 1 ore | 40 s | 2,736 | **246,240** |
  | T10 Aethersteel | 20 + 10 | 310 s | 2,736 | 31,773 |
  | T18 Kingssteel | 36 + 18 | 550 s | 2,736 | 17,908 |
  | T34 Primordite | 68 + 34 | 1,030 s | 2,736 | 9,563 |

  *(10 s actions, no housing reduction, no gather bonus — the ratios are what
  matter and they are invariant to those.)*

  **T1 is optimal at every level, by 25.7×.** The existing optimiser cannot see
  this, because `chooseBestAction()` only ever evaluates `maxTierForLevel(fromLvl)`.
  Fixing that is Phase 4.2 and it is the highest-value part of this whole change.

**Track B — Assembly. Not a levelling action.**

- 34 recipes, 180 s each, one per building.
- Inputs: `200t` current-tier Parts + `100t²` raw wood + `50t²` ore + up to three
  deterministic lower-tier Parts stacks of `40×(that tier)`.
- XP `round(1.8 × skillXpForTier(t) × 2)` — 338 at T18, i.e. **6,760 XP/hr in-action**
  and, counting the stockpile at one gather per 10 s, roughly **685 hours** of
  upstream work for a single T18 building.
- It is a *building acquisition* action. If the optimiser is allowed to rank it with
  its stockpile treated as free it will recommend it, and that recommendation is a
  lie. Treat it exactly the way `tailor_thread_upgrade` is already treated — exposed
  in the Calculator, deliberately excluded from `SKILL_GROUP_ACTIONS`.

### Village add-ons

- Slots = **housing tier**, capped at 5. Housing "None" ⇒ 0 slots.
- One of each *building type* installed at a time (server-enforced).
- Destroying refunds 25% of the assembly cost.
- Each grants: one primary stat, one secondary stat, `+N XP/task`, and **+1 or +2
  levels to exactly one non-combat skill**.
- Skill rotation, from the client verbatim:
  `["mining","smithing","herbing","alchemy","jewelcrafting","spellcrafting","tailoring","woodcutting","construction"]`
  → `skill = ROT[(tier−1) % 9]`, `amount = tier ≤ 9 ? 1 : 2`. Never higher than 2.
- The game aggregates skill bonuses from exactly three places:
  `[equippedArmor.gloves, equippedArmor.trinket, ...villageAddons.installed]`.

### The cross-skill level gate

The client prints, on every Construction recipe card:

> `Needs Construction Lv {minLevel} + Woodcutting Lv {max(1, minLevel − 4)}`

This is a general game rule the toolkit has **never modelled for any skill**:
`smithing`/`jewelcrafting` need Mining `Lv−4`; `alchemy`/`tailoring` need Gathering
`Lv−4`; `construction` needs Woodcutting `Lv−4`. Pre-existing gap; Construction just
makes it visible. Scoped as optional Phase 8.

*(Aside, do not copy it: the game's own generic label helper `ew()` has a display bug
— for `construction` it resolves the companion skill correctly to `woodcutting` but
then prints the literal string "Gathering", because its label branch only handles
mining vs herbing. The recipe card uses a separate hardcoded string that says
"Woodcutting" correctly.)*

---

## 1.3 The three headline numbers

1. **Woodcutting XP/action = Mining XP/action at the same tier.** Identical game
   expression. §1.5 explains the trap here.
2. **Construction Parts XP = `SMELT_XP[tierUnlockedAt(effectiveConstructionLevel)]`.**
   The toolkit **already has this exact table**. No new XP curve is needed.
3. **Assembly XP = `round(SMITHING_XP_MULTIPLIER × skillXpForTier(t) × 2)`**, i.e.
   `round(3.6 × skillXpForTier(t))`. Also reuses an existing constant.

---

## 1.4 Verified formulas — and what was actually checked

Every expression below was extracted from the game's client bundle and then run
against **all** the attached JSON's rows. Mismatch counts are from an actual
execution, not a claim.

```js
// ── from the game bundle, chunk 9811 ───────────────────────────────────────────
// gathering (mine_ / chop_ / gather_ are all this expression):
skillXp: Math.round(1.1 * e.skillXp)

// Building Parts recipe:
{ durationSeconds: 10,
  inputs: [{ itemKey: woodKey, quantity: 2*tier }, { itemKey: oreKey, quantity: tier }],
  outputs:[{ itemKey: partsKey, quantity: 1 }],
  xp: q(minLevel) }

function J(e){ return 1===e?2 : 2===e?4 : 3===e?6 : 4===e?7 : 8 }   // == toolkit oresPerBar()
function q(e){ let t=Math.min(f.length-1, Math.max(0, Math.floor((e-1)/4))), n=f[t];
               return Math.round(n.skillXp * J(n.tier) * 1.8) }      // == toolkit SMELT_XP[T]

// Assembly recipe:
inputs = [ {partsKey, 200*n}, {woodKey, 100*n*n}, {oreKey, 50*n*n} ]
         .concat(lowerTierPicks(n).map(p => ({ partsKey_of_p, 40*p })))
durationSeconds: 180
xp: Math.round(1.8 * e.skillXp * 2)

function lowerTierPicks(e){                       // deterministic Lehmer PRNG
  let t = Math.min(3, e-1); if (t <= 0) return [];
  let n = [], a = 0x9e3779b1 * e % 0x7fffffff;
  while (n.length < t) {
    let x = Math.abs(a = (48271*a + 1) % 0x7fffffff) % (e-1) + 1;
    if (!n.includes(x)) n.push(x);
  }
  return n.sort((p,q) => p-q);
}

// Building buffs:
B = ["atk","def","goldFind","itemFind","doubleGather"]
w = ["atk","def","doubleGather","itemFind","goldFind","atk","doubleGather","atk","def",
     "def","itemFind","goldFind","itemFind","doubleGather","atk","def","def","itemFind",
     "goldFind","itemFind","doubleGather","atk","def","def","itemFind","goldFind",
     "goldFind","doubleGather","atk","def","doubleGather","itemFind","goldFind","atk"]
primaryStat(t)   = w[t-1]
secondaryStat(t) = B[(B.indexOf(w[t-1]) + 2) % 5]      // plus an always-present xp buff
function R(stat, t, isPrimary){
  switch(stat){
    case "atk": case "def": return Math.max(1, Math.round((isPrimary?1:0.4)*t));
    case "xp":              return Math.max(2, Math.round((isPrimary?1.4:0.6)*t));
    default:                return Math.max(2, Math.round((isPrimary?0.7:0.3)*t));
  }
}
```

**Verification results (executed, not asserted):**

| Claim | Rows checked | Mismatches |
|---|---|---|
| `effectiveLevelXpTable[L] === SMELT_XP[clamp(floor((L−1)/4)+1, 1, 34)]` | 143 | **0** |
| `buildingPartsRecipes[t].static_xp_field === SMELT_XP[t]` | 34 | **0** |
| `assemblyRecipes[t].xp === round(1.8 × skillXpForTier(t) × 2)` | 34 | **0** |
| `woodcuttingActivities[t].skill_xp_per_action === round(skillXpForTier(t) × 1.1)` | 34 | **0** |
| Parts recipe inputs `= 2t wood + t ore` | 34 | **0** |
| Assembly inputs incl. the PRNG lower-tier picks | 34 (146 input rows) | **0** |
| Building primary/secondary/xp/skill-bonus all derived from `w`, `B`, `R`, `ROT` | 34 × 4 assertions | **0** |
| `PARTS_NAMES[t] === TIER_NAMES[t] + " Building Parts"` | 34 | **0** |
| parts `item_id === woodKey + "_building_parts"` | 34 | **0** |
| ore key `=== TIER_NAMES[t].toLowerCase() + "_ore"` | 34 | **0** |

So the only genuinely new *data* the toolkit needs is:
**34 wood names** and **34 building names**. Everything else is derivable from tables
`index.html` already holds.

---

## 1.5 The XP-convention trap — read this before writing `WOODCUT_XP`

The game gives mining, chopping and herbing the **identical** per-action expression:
`Math.round(1.1 * skillXp)`. The attached JSON reports Woodcutting T1 = **4 XP**,
consistent with that.

The toolkit, however, holds:

```js
// index.html, anchor: "// Gather actions: 2 × round(skillXp × 1.1)"
MINING_XP[t]    = 2 * Math.round(skillXpForTier(t) * 1.1);   // T1 = 8
GATHERING_XP[t] = 2 * Math.round(skillXpForTier(t) * 1.1);   // T1 = 8
```

i.e. the toolkit's gather figures are **2× the game's raw activity number**, and have
been since long before this change. That 2× is a pre-existing, calibrated,
toolkit-wide convention (the whole Calculator/Planner buff chain and every
XP/hr figure is built on it).

**Therefore: `WOODCUT_XP[t] = MINING_XP[t]`, verbatim.** Do not use the JSON's raw
4/9/13/… numbers. Using them would make Woodcutting display exactly half of Mining
for the same action at the same tier — a visible, wrong, internally-inconsistent
result. Mirroring `MINING_XP` is the only choice that keeps the file self-consistent.

**Do not reopen the 2× question as part of this change.** It is orthogonal, it
touches every skill, and it is not what this work is for. Note it in the header
comment and move on.

---

## 1.6 Live bugs in the toolkit, today, right now

These are already firing against Curtis's real profile. Verified by fetching the
live endpoint:

```json
"skills": [ … {"skillKey":"woodcutting","level":49,"xp":6302454},
                {"skillKey":"construction","level":44,"xp":2683590} ]
```

**BUG 1 — `woodcutting` is aliased to `gathering` in two separate places.**

```js
// anchor: "var SKILL_ALIAS = {"      (the shared resolver, ~line 6444)
woodcutting:'gathering', foraging:'gathering', farming:'gathering',
// anchor: "var ALIAS = {"           (character panel, ~line 26889)
woodcutting: 'gathering', foraging: 'gathering',
```

Both predate the skill existing. Consequences today:

- `indexSkills()` folds Woodcutting into Gathering with "highest wins". Curtis is
  Gathering 64 / Woodcutting 49 so nothing *visibly* breaks — **but the moment
  Woodcutting exceeds Gathering, the Gathering level silently displays the
  Woodcutting level.** A latent, data-dependent, silent corruption.
- The character panel renders **two 🌿 cards**, one labelled "Gathering" and one
  labelled "Woodcutting", both carrying `data-skill="gathering"` (so both inherit
  the collapsed-mode `order: 6`), and **both clicking through to Gathering** in the
  Calculator.
- **Self-check 17 cannot catch it.** Its dropped-skill test is
  `if (k != null && !window.iwResolveSkillKey(k)) dropped.push(k)` — Woodcutting
  resolves to a *wrong but truthy* key, so it passes. It will correctly flag
  `construction` (which resolves to `null`) and stay silent about `woodcutting`.
  This is precisely the failure class the suite was written for, defeated by a
  stale alias.

**BUG 2 — `construction` is dropped entirely.** No alias, no button ⇒
`resolveSkillKey('construction') === null` ⇒ skipped by `indexSkills()`, and the
character panel renders it as a non-clickable `<div>` with a `•` bullet and no tint.

**BUG 3 — both skills are invisible to every any-skill gate.**

```js
// anchor: "const IW_EFFECTIVE_SKILL_KEYS = ["
['combat','mining','herbing','smithing','tailoring','alchemy','jewelcrafting','spellcrafting']
```

`iwHighestBaseSkillLevel()` / `iwHighestEffectiveSkillLevel()` iterate only this
list, and they drive `zoneBypassLevel` / `highestZoneForSkillLevel` /
`iwCanEquip`'s any-skill branch. A Construction-main would be told they cannot wear
"Requires Lv 61 (any skill)" gear they can in fact wear.

**BUG 4 — `wikiSkillToGroup()` returns `null` for both.** Harmless today (they are
not in the daily rotation) but it means the live wiki scraper would silently drop
them if that ever changed.

**BUG 5 — the embedded snapshot is 103 records stale.** 4,349 vs the live 4,452:
34 wood, 34 Parts, 34 buildings, plus `premium_token`.

---

## 1.7 What is *not* affected — do not touch these

- **Work Orders.** No wood and no Building Parts carry `work_order_turn_in_gold`.
  Verified across all 2,448 rows that do. The Work Order module needs zero changes.
- **The gear scorer and the Task Gear Advisor index.** Buildings carry
  `atk`/`def`/`xp_per_task`/`gold_find_pct`/`item_find_pct`/`double_gather_pct` **and**
  `skill_bonus_skill`/`skill_bonus_value`, which looks alarming — but
  `buildTaskGearIndex()` filters `r.cat === 'Equipment' && /slot$/.test(r.sub)`, and
  buildings are `Trade Good / Trade good`. They cannot leak in. Confirmed.
- **`idbFromApi()` / `buildItemDatabase()` / `iwCompatItemRow()`.** The 103 new
  records need **no normaliser change**; they use existing categories and existing
  fields. This is the one-normaliser rule paying off.
- **The Items tab.** `IDB_CATEGORIES` is built dynamically by
  `iwBuildCategoryMetadata()`; no filter list to extend.
- **`IWStore` persistence.** Capture is generic over `input[id], select[id]`, and
  `snapshotSelection()` reads `.skill-btn.active` / `.sub-btn.active`. New controls
  persist automatically — **provided** the new sub-type container's id ends in
  `-types` (see `sub.closest('[id$="-types"]')`).
- **The Planner's skill tile grid.** `iwRenderPlannerSkills()` derives itself from
  `document.querySelectorAll('#skill-grid .skill-btn')`. Adding two buttons is enough.
- **`TIER_LVL`, `maxTierForLevel`, `MAX_TIER`.** Both new skills use the standard
  `1 + (t−1)×4` curve.
- **The legacy `renderTaskGearAdvisor` / `#tab-gear` pane.** It is already dead —
  `renderGearRecommendations()` returns early because `#gear-placeholder` and
  `#gear-output` no longer exist, and `#gear-task-output` / `#gear-task-dd` are
  absent from the markup entirely. Keep its data tables consistent (cheap) but do
  not build features there.

---

## 1.8 Open questions only Curtis can settle

**Q1 — Does `combatStats` include installed village-add-on buffs? — ANSWERED: assume no.**
`/api/player-profile` does **not** expose `villageAddons` at all (verified: the
response keys are `id, displayName, level, createdAt, teamColor, leagueType,
hasAlternateLeague, skills, equipped, marketListings, housingTier, combatStats,
equippedTitleKey, race, chatNameColorKey, itemEnchants, itemReinforcements`).

**Curtis's ruling (2026-09-03): assume `combatStats` does NOT include add-on buffs.**
This is a working assumption, not an observation — nobody has an add-on installed
yet, so there is no data either way. Build to it, but make it **one named constant**
so flipping it later is a one-line change, not an archaeology exercise. See 6.4.

**Q2 — Do village add-on skill bonuses widen the "any skill" gates and zone travel?**
The client feeds `pg()` (add-ons included) into `pj()` and into
`pw = Math.max(...skills.map(s => s.level + pg(s.key)))`, which strongly suggests
yes. The toolkit's own Stage F comment deliberately keeps *equipment* gates on the
base-level path. Match the toolkit's existing convention: use effective level for
access/tier/zone, base level for equip gates.

**Q3 — Is the daily-XP rotation really unchanged?**
The wiki still shows the same 4 slots and says "the other six professions split into
three grouped slots" — no Woodcutting, no Construction. Phase 3.6 assumes that.
If it is wrong, the fix is two entries in `DAILY_BONUS_CONFIG.rotation` and nothing
else, because `dailyBonusAppliesTo()` reads config.

**Q4 — Icons.** There is no atlas art for any of the 102 new items. `item_icons_index.csv`
has 1,167 rows across 375 shared cells and contains none of them. See Phase 7.

---

# PART 2 — IMPLEMENTATION PLAN

## Ground rules for this work

1. **Do not commit, stage, or push anything.** Edit the working tree, report, stop.
2. After **every** phase, run the parse gate. Baseline is `19 blocks checked, 0 failed`:
   ```bash
   node -e "const fs=require('fs'),vm=require('vm');const src=fs.readFileSync('index.html','utf8');let m,i=0,bad=0;const re=/<script([^>]*)>([\s\S]*?)<\/script>/gi;while((m=re.exec(src))){if(/type\s*=\s*[\"'](?!text\/javascript)/i.test(m[1]))continue;const line=src.slice(0,m.index).split('\n').length;i++;try{new vm.Script(m[2]);}catch(e){bad++;console.log('FAIL block at line '+line+': '+e.message);}}console.log(i+' blocks checked, '+bad+' failed');"
   ```
3. **Never print the embedded payload.** It is one 2.2 MB line at
   `<script type="application/json" id="iw-embedded-items">`. Any `sed -n 'A,Bp'`
   spanning it will dump megabytes. Use
   `awk 'NR>=A && NR<=B { if (length($0)>400) print NR": <<LONG>>"; else print NR": "$0 }' index.html`.
4. **Absent is not zero.** A stat that does not apply is `undefined`, never `0`.
5. Existing self-check assertions may only be changed by the phase that intentionally
   changes that mechanic. Everything else stays green.
6. A syntax error is silent in the browser except for the block containing it. The
   parse gate is the only cheap real signal.

---

## Phase 0 — Baseline and payload refresh

### 0.1 Record the baseline
Run the parse gate. Confirm `19 blocks checked, 0 failed`.

### 0.2 Regenerate the embedded item payload to 4,452 records

The embedded payload is the offline fallback and it is 103 records stale.

```bash
curl -s https://idleworlds.com/items.json -o /tmp/items_live.json
```

Then rebuild the `<script id="iw-embedded-items">` line. **Preserve the existing
payload's compaction contract exactly**, or the "absent is not zero" rule breaks:

- Top-level shape: `{"generatedAt":…, "itemCount":4452, "items":[…], "schemaNotes":…}`
  (keep the existing `schemaNotes` block verbatim).
- Per row, **strip every key whose value is `""` or `null`**. This is what makes
  absent-vs-zero safe.
- **Omit `wiki_slug`** (always equals `item_id`; `idbFromApi` restores it) and
  **omit `acquisition_detail`** (written, never read; ~253 KB).
- Keep the retained key order identical to the current payload so a diff is readable.
- The result must remain **one single line**.

Write a script; do not hand-edit. Verify afterwards:

```bash
node -e "
const fs=require('fs');const src=fs.readFileSync('index.html','utf8');
const m=/<script[^>]*id=[\"']iw-embedded-items[\"'][^>]*>([\s\S]*?)<\/script>/i.exec(src);
const p=JSON.parse(m[1]);
console.log('count', p.items.length, 'declared', p.itemCount);
console.log('has empty-string values:', p.items.some(r=>Object.values(r).some(v=>v==='')));
console.log('has wiki_slug:', p.items.some(r=>'wiki_slug' in r));
console.log('newline in payload:', /\n/.test(m[1]));
"
```
Expect `4452 4452`, `false`, `false`, `false`.

### 0.3 Update the one assertion that pins the count

```js
// anchor: "eq('embedded item count', rows.length, 4349);"
eq('embedded item count', rows.length, 4452);
```

This is the *only* hardcoded item count in a live assertion. `4322` appears only
inside comments.

### 0.4 Header comment

Add a `v5.4` block at the top of `index.html` in the existing style. State: the two
new skills, the 4,452-record sync, and — explicitly — the §1.5 note that
`WOODCUT_XP` mirrors `MINING_XP` and that the toolkit's 2× gather convention was
deliberately not revisited.

**Gate:** parse gate green; `iwAugust2026RegressionSelfCheck()` returns `[]`.

---

## Phase 1 — Skill identity (fixes BUGS 1–4)

Do this phase **before** any data or engine work. It is the live-bug fix and
everything else depends on the two skills having distinct identities.

### 1.1 Delete the two stale aliases

```js
// anchor: "var SKILL_ALIAS = {"   —  DELETE the woodcutting entry only
- woodcutting:'gathering', foraging:'gathering', farming:'gathering',
+ foraging:'gathering', farming:'gathering',
```

```js
// anchor: "var ALIAS = {"  (inside the character-panel IIFE) — same deletion
- woodcutting: 'gathering', foraging: 'gathering',
+ foraging: 'gathering',
```

Leave a one-line comment at each site: these were speculative aliases written before
the skill existed; the skill now exists and is distinct.

### 1.2 Add the two Calculator skill buttons

```html
<!-- anchor: <button class="skill-btn" data-skill="tailoring">🧵<span>Tailoring</span></button> -->
<button class="skill-btn" data-skill="woodcutting">🪓<span>Woodcutting</span></button>
<button class="skill-btn" data-skill="construction">🏗️<span>Construction</span></button>
```

Icons are the game's own (`\uD83E\uDE93` axe, `\uD83C\uDFD7\uFE0F` building
construction), taken from the client's skill-tab table. Order matters: append after
Tailoring so the calculator grid, the Planner tile grid and the persisted selection
all stay in a stable order.

Adding the buttons is what makes `resolveSkillKey('woodcutting')` and
`resolveSkillKey('construction')` resolve to themselves — `calcSkillSet()` reads the
DOM. **Note `_skillBtnCache`**: it caches only once non-empty, so the buttons must be
in the static markup, not injected later.

### 1.3 CSS

**a) Theme tokens — 8 blocks.** Every block that already defines `--sk-tailoring`
needs two more. Anchors, in file order: `:root, [data-theme="dark"]`,
`[data-theme="light"]`, `[data-theme="office"]`, `[data-theme="pink"]`,
`[data-theme="emerald"]`, `[data-theme="sapphire"]`, `[data-theme="ruby"]`,
`[data-theme="topaz"]`. Grep for `--sk-tailoring:` to find all 8.

Dark-family blocks (dark, pink, emerald, sapphire, ruby, topaz — the six that use
`#e88fb8` for tailoring):
```css
    --sk-woodcutting: #c99a63;
    --sk-construction: #9aa7b8;
```
Light-family blocks (light, office — the two that use `#b8447e`):
```css
    --sk-woodcutting: #8a5f2a;
    --sk-construction: #5c6a7d;
```

**b) Button tints** — anchor `.skill-btn[data-skill="tailoring"]`:
```css
  .skill-btn[data-skill="woodcutting"]  { --tint: var(--sk-woodcutting); }
  .skill-btn[data-skill="construction"] { --tint: var(--sk-construction); }
```

**c) Character-panel tints** — anchor `.cp-skill[data-skill="tailoring"]`:
```css
  .cp-skill[data-skill="woodcutting"]  { --cp-tint: var(--sk-woodcutting); }
  .cp-skill[data-skill="construction"] { --cp-tint: var(--sk-construction); }
```

**d) Collapsed reorder** — anchor `.cp-skills.collapsed .cp-skill[data-skill="tailoring"] { order: 8; }`:
```css
  .cp-skills.collapsed .cp-skill[data-skill="woodcutting"]  { order: 9; }
  .cp-skills.collapsed .cp-skill[data-skill="construction"] { order: 10; }
```

### 1.4 Character-panel icon map

```js
// anchor: "spellcrafting: '\u2728', tailoring: '\uD83E\uDDF5'"
    spellcrafting: '\u2728', tailoring: '\uD83E\uDDF5',
    woodcutting: '\uD83E\uDE93', construction: '\uD83C\uDFD7\uFE0F'
```

`PRETTY_OVERRIDE` needs nothing — generic title-casing already produces
"Woodcutting" and "Construction".

### 1.5 The canonical-key resolver

```js
// anchor: "const IW_EFFECTIVE_SKILL_KEYS = ["
const IW_EFFECTIVE_SKILL_KEYS = [
  'combat','mining','herbing','smithing','tailoring',
  'alchemy','jewelcrafting','spellcrafting','woodcutting','construction'
];
```

`iwCanonicalSkillKey()` already returns `'woodcutting'` / `'construction'` unchanged
(they hit no alias). Add defensive aliases anyway, next to the existing ones:

```js
// anchor: "    mine:'mining', ore:'mining'"  (inside iwCanonicalSkillKey's alias map)
    mine:'mining', ore:'mining',
    woodcut:'woodcutting', chopping:'woodcutting', lumberjack:'woodcutting',
    build:'construction', building:'construction', constructing:'construction'
```

```js
// anchor: "function iwSkillDisplayName(skillName) {" — extend the returned map
    spellcrafting:'Spellcrafting',
    woodcutting:'Woodcutting', construction:'Construction'
```

### 1.6 The wiki daily-boost parser

```js
// anchor: "function wikiSkillToGroup(name) {"
// Insert BEFORE the herb/gather branch is not required (neither string collides),
// but keep them grouped with the other gathering-ish tests for readability.
  if (/woodcut|chopping|lumber/.test(s)) return 'woodcutting';
  if (/construct|building/.test(s))      return 'construction';
```

```js
// anchor: "const DAILY_GROUP_EMOJI = {"
  woodcutting:'🪓', construction:'🏗️',
```
```js
// anchor: "  const nice = { combat:'Combat', mining:'Mining', gathering:'Gathering',"
    spellcrafting:'Spellcrafting', tailoring:'Tailoring',
    woodcutting:'Woodcutting', construction:'Construction' };
```

Do **not** add them to `DAILY_BONUS_CONFIG.rotation` — see §1.8 Q3.

### 1.7 Extend self-check 17 so BUG 1 can never recur

This is the check that failed to catch the alias. Anchor:
`"// 2. Known API spellings must land on a real button."`

```js
    // 2. Known API spellings must land on a real button.
    [['herbing','gathering'], ['tailoring','tailoring'], ['weaving','tailoring'],
     ['spellcrafting','spellcrafting'], ['jewelcrafting','jewelcrafting'],
     ['smithing','smithing'], ['mining','mining'], ['alchemy','alchemy'],
     ['combat','combat'],
     ['woodcutting','woodcutting'], ['construction','construction']].forEach(...)

    // 2b. NEW — an API key must never resolve to a DIFFERENT real skill.
    //     The dropped-skill test in (4) below only catches keys that resolve to
    //     null. From v5.3.1 to v5.4 'woodcutting' resolved to 'gathering': a
    //     wrong-but-truthy answer that every existing assertion accepted, and
    //     that silently overwrote the Gathering level whenever Woodcutting was
    //     the higher of the two. Assert the identity, not just the presence.
    ['woodcutting','construction','mining','smithing','alchemy','tailoring',
     'jewelcrafting','spellcrafting','combat'].forEach(function (k) {
      if (keys.indexOf(k) === -1) return;
      var got = window.iwResolveSkillKey(k);
      if (got !== k)
        warn.push('API key "' + k + '" resolves to "' + got + '" — a different skill');
    });
```

**Break it on purpose before trusting it:** temporarily restore
`woodcutting:'gathering'` in `SKILL_ALIAS`, load the page with `?selfcheck=1`, and
confirm the console prints the new warning. Then remove it again.

**Gate:** parse gate green. Load with `?selfcheck=1`, import Curtis's profile, and
confirm: 10 skill cards, distinct icons/tints, Woodcutting and Construction each
click through to their own Calculator button, and no `selfcheck 17` warning.

---

## Phase 2 — Game-data tables

Place all of this **immediately after** `const ORE_NAMES = {…};` and before
`// NOTE: GEM_NAMES is now defined above`. That region is the game-data constants
block and `skillXpForTier` / `oresPerBar` / `TIER_NAMES` are already in scope there.

Declaration order is load-bearing: `SMELT_XP` is defined *below* `ORE_NAMES`, so
`CONSTRUCT_PARTS_XP_FOR_LEVEL` (which reads `SMELT_XP`) must be a **function**, not
a precomputed table, or it will read an empty object. This is deliberate; do not
"optimise" it into a lookup table at the top.

```js
// ═══════════════════════════════════════════════════════════════
// WOODCUTTING & CONSTRUCTION  (v5.4)
// ───────────────────────────────────────────────────────────────
// Sources: idleworlds.com/wiki/construction, items.json (4,452 records),
// and the game client's own generated content module. Every expression
// below reproduces 100% of the 245 rows in the vendor data packet; the
// self-check suite (H) re-asserts that at runtime.
//
// Two things here are NOT new curves — they are existing toolkit tables
// reached through a different key, which is why nothing was invented:
//   • Woodcutting XP/action  === MINING_XP[t]   (same game expression)
//   • Building Parts XP      === SMELT_XP[T]    (T from EFFECTIVE level)
// ═══════════════════════════════════════════════════════════════

const WOOD_NAMES = {
  1:'Greenwake Timber', 2:'Ironbark', 3:'Silverwood', 4:'Goldenbough', 5:'Mythril Heartwood',
  6:'Starwood', 7:'Obsidian Root', 8:'Runic Oak', 9:'Dragonwood', 10:'Aetherwood',
  11:'Voidbark', 12:'Celestial Bough', 13:'Bloodoak', 14:'Moonwood', 15:'Sunwood',
  16:'Netherwood', 17:'Stormwood', 18:'Regal Timber', 19:'Eternal Heartwood', 20:'Astral Bough',
  21:'Graviwood', 22:'Frostwood', 23:'Duskwood', 24:'Titanwood', 25:'Skywood',
  26:'Emberwood', 27:'Soulwood', 28:'Chronowood', 29:'Worldwood', 30:'Voidglass Timber',
  31:'Abyssal Driftwood', 32:'Ashwood', 33:'Glacial Timber', 34:'Primordial Heartwood'
};

// Parts are named for the METAL tier, not the wood — "Copper Building Parts"
// is made from Greenwake Timber. Derived, verified against all 34 records.
function partsName(t) { return (TIER_NAMES[t] || '') + ' Building Parts'; }

const BUILDING_NAMES = {
  1:'Training Yard', 2:'Ironfang Palisade', 3:'Silverroot Infirmary', 4:'Goldfire Scriptorium',
  5:'Mythril Countinghouse', 6:'Starsteel Trophy Hall', 7:'Obsidian Greenhouse',
  8:'Runite War College', 9:'Dragonfall Rampart', 10:'Aether Sanatorium',
  11:'Voidiron Archive', 12:'Celestial Exchange', 13:'Bloodstone Reliquary',
  14:'Moonsteel Arboretum', 15:'Sunforge Arena', 16:'Nethergate Bastion',
  17:'Stormglass Chapel of Healing', 18:'Kingsfall Grand Library', 19:'Eternium Treasury',
  20:'Astral Museum', 21:'Gravite Botanical Dome', 22:'Frostiron Warfront Hall',
  23:'Dusksteel Citadel Wall', 24:'Titanium Grand Infirmary', 25:'Skysteel Observatory',
  26:'Emberium Mint', 27:'Soulsteel Vault of Relics', 28:'Chronite Greenhouse Spire',
  29:'Worldforge Coliseum', 30:'Voidglass Bulwark', 31:'Thalassic Sanctum of Tides',
  32:'Ashspire Hall of Records', 33:'Glacirite Royal Treasury', 34:'Primordial Wonder'
};

// ── Woodcutting ────────────────────────────────────────────────
// The game defines mine_/chop_/gather_ with ONE expression:
//   skillXp: Math.round(1.1 * skillXp)
// The toolkit's own gather convention is 2× that figure (see MINING_XP).
// Mirroring MINING_XP is therefore the only internally consistent choice;
// using the raw game number would show Woodcutting at half of Mining for the
// same action. The 2× convention itself is pre-existing and out of scope here.
const WOODCUT_XP = {};
for (let t = 1; t <= 34; t++) WOODCUT_XP[t] = MINING_XP[t];

// ── Construction, Track A: Building Parts ──────────────────────
// XP is DECOUPLED from the recipe tier. It is a pure function of the
// player's EFFECTIVE Construction level, and equals the smelt-XP figure of
// whichever tier that level has unlocked.
//   game: q(L) = round(f[floor((L-1)/4)].skillXp * J(tier) * 1.8)
//   J() is byte-identical to oresPerBar(), 1.8 is SMITHING_XP_MULTIPLIER,
//   so q(L) === SMELT_XP[tierUnlockedAtLevel(L)]. Verified on all 143 rows.
// Reads SMELT_XP, which is declared BELOW this point, so this must stay a
// function. Do not hoist it into a table.
function constructionPartsTierForLevel(effLevel) {
  const L = Number(effLevel);
  if (!Number.isFinite(L)) return 1;
  return Math.min(34, Math.max(1, Math.floor((L - 1) / 4) + 1));
}
function constructionPartsXpForLevel(effLevel) {
  return SMELT_XP[constructionPartsTierForLevel(effLevel)];
}

// Parts recipe inputs: 2t wood + t ore. Both are 10s gathers with the same
// yield, so the single `cost` field the engine uses is EXACT here (3t units),
// not an approximation — which is why the standard upstream model is safe for
// Parts and is NOT safe for Assembly (see below).
function constructPartsWoodInput(t) { return 2 * t; }
function constructPartsOreInput(t)  { return t; }
function constructPartsTotalInput(t) { return 3 * t; }

// ── Construction, Track B: Assembly ────────────────────────────
// xp = round(SMITHING_XP_MULTIPLIER * skillXpForTier(t) * 2). Verified × 34.
const ASSEMBLY_XP = {};
for (let t = 1; t <= 34; t++)
  ASSEMBLY_XP[t] = Math.round(SMITHING_XP_MULTIPLIER * skillXpForTier(t) * 2);

const ASSEMBLY_TIME = 180;   // EQUIPMENT_CRAFT_SECONDS class

// Deterministic lower-tier Parts stacks. Straight Lehmer PRNG lifted from the
// game; reproduces all 146 lower-tier input rows exactly. Do not "simplify".
function constructionLowerTierPicks(tier) {
  const n = Math.min(3, tier - 1);
  if (n <= 0) return [];
  const out = [];
  let a = (0x9e3779b1 * tier) % 0x7fffffff;
  while (out.length < n) {
    a = (48271 * a + 1) % 0x7fffffff;
    const pick = Math.abs(a) % (tier - 1) + 1;
    if (out.indexOf(pick) === -1) out.push(pick);
  }
  return out.sort((x, y) => x - y);
}

/** Full, exact assembly bill for one building. */
function assemblyInputs(tier) {
  const t = parseInt(tier);
  const rows = [
    { key: 'parts', tier: t, qty: 200 * t,     label: partsName(t) },
    { key: 'wood',  tier: t, qty: 100 * t * t, label: WOOD_NAMES[t] },
    { key: 'ore',   tier: t, qty: 50  * t * t, label: ORE_NAMES[t]  },
  ];
  constructionLowerTierPicks(t).forEach(function (p) {
    rows.push({ key: 'parts', tier: p, qty: 40 * p, label: partsName(p) });
  });
  return rows;
}

// ── Village add-ons ────────────────────────────────────────────
// One building = one non-combat skill, cycling in this fixed order. Tiers
// 1-9 grant +1; tier 10 onward grants +2 — the cap, never higher.
// NOTE: 'herbing' is the API/game key; the toolkit's group key is 'gathering'.
// Route through iwCanonicalSkillKey / iwResolveSkillKey rather than comparing raw.
const BUILDING_SKILL_ROTATION = [
  'mining','smithing','herbing','alchemy','jewelcrafting',
  'spellcrafting','tailoring','woodcutting','construction'
];
function buildingSkillBonus(tier) {
  const t = parseInt(tier);
  if (!t || t < 1 || t > 34) return null;
  return { skill: BUILDING_SKILL_ROTATION[(t - 1) % 9], amount: t <= 9 ? 1 : 2 };
}

// Primary/secondary buff stats and magnitudes, derived from the game's own
// generator. Verified against all 34 buildings × 4 assertions. `xp` is always
// present as the second secondary.
const BUILDING_STAT_CYCLE   = ['atk','def','goldFind','itemFind','doubleGather'];
const BUILDING_PRIMARY_STAT = [
  'atk','def','doubleGather','itemFind','goldFind','atk','doubleGather','atk','def',
  'def','itemFind','goldFind','itemFind','doubleGather','atk','def','def','itemFind',
  'goldFind','itemFind','doubleGather','atk','def','def','itemFind','goldFind',
  'goldFind','doubleGather','atk','def','doubleGather','itemFind','goldFind','atk'
];
function buildingStatMagnitude(stat, tier, isPrimary) {
  const t = parseInt(tier);
  switch (stat) {
    case 'atk': case 'def': return Math.max(1, Math.round((isPrimary ? 1   : 0.4) * t));
    case 'xp':              return Math.max(2, Math.round((isPrimary ? 1.4 : 0.6) * t));
    default:                return Math.max(2, Math.round((isPrimary ? 0.7 : 0.3) * t));
  }
}
// Maps a building stat key to the combatStats field the profile uses.
const BUILDING_STAT_FIELD = {
  atk:'attackBonus', def:'defenseBonus', xp:'xpTaskBonus',
  goldFind:'goldFindPercent', itemFind:'itemFindPercent',
  doubleGather:'doubleGatherChancePercent'
};
const BUILDING_STAT_LABEL = {
  atk:'ATK', def:'DEF', xp:'XP/task',
  goldFind:'Gold Find', itemFind:'Item Find', doubleGather:'2x Gather Chance'
};
const BUILDING_STAT_IS_PCT = { goldFind:true, itemFind:true, doubleGather:true };

/** Full buff descriptor for one building tier. */
function buildingBuffs(tier) {
  const t = parseInt(tier);
  if (!t || t < 1 || t > 34) return null;
  const pri = BUILDING_PRIMARY_STAT[t - 1];
  const sec = BUILDING_STAT_CYCLE[(BUILDING_STAT_CYCLE.indexOf(pri) + 2) % 5];
  return {
    tier: t,
    name: BUILDING_NAMES[t],
    primary:   { stat: pri, value: buildingStatMagnitude(pri, t, true)  },
    secondary: [
      { stat: sec,  value: buildingStatMagnitude(sec,  t, false) },
      { stat: 'xp', value: buildingStatMagnitude('xp', t, false) }
    ],
    skill: buildingSkillBonus(t)
  };
}

// 1 add-on slot per housing tier, capped at 5. Housing "None" => 0 slots.
const VILLAGE_ADDON_MAX_SLOTS = 5;
function villageAddonSlots(housingTier) {
  return Math.max(0, Math.min(VILLAGE_ADDON_MAX_SLOTS, parseInt(housingTier) || 0));
}
const VILLAGE_ADDON_REFUND_PCT = 25;
```

**Gate:** parse gate green. In the console:
`constructionPartsXpForLevel(133) === 2736`, `constructionPartsXpForLevel(1) === 14`,
`ASSEMBLY_XP[18] === 338`, `assemblyInputs(2).length === 4`,
`buildingBuffs(14).skill.skill === 'jewelcrafting'`.

---

## Phase 3 — Calculator wiring

### 3.1 The effective-Construction-level reader

Construction Parts XP needs the player's **effective** level. Add this next to
`iwSpellcraftingLevel()` (anchor: `"function iwSpellcraftingLevel(){"`), following
the same shape but routing through the shared resolver:

```js
/**
 * iwConstructionEffectiveLevel() — base Construction level + every skill-level
 * bonus that applies to it. This is the ONLY input to Building Parts XP.
 *
 * Sources, in the game's own order: gloves, trinket, installed village add-ons.
 * No equipment in the game grants Construction levels today, so in practice this
 * resolves to base + the planned add-on bonus (Phase 6). Returns null when the
 * level cannot be determined at all — callers must then fall back to their own
 * context rather than guessing, exactly as iwSpellcraftCatchupMult does.
 */
function iwConstructionEffectiveLevel() {
  try {
    var s = iwSkillLevels('construction', { manualBonus: iwPlannerManualSkillBonus() });
    if (s && s.effectiveLevel != null) return s.effectiveLevel;
  } catch (e) {}
  return null;
}
```

### 3.2 `getActions()` — an optional third argument

`getActions(tier, skill)` is called from ~8 places. **Do not change the first two
parameters.** Add an optional third:

```js
// anchor: "function getActions(tier, skill) {"
/**
 * getActions(tier, skill, [effLevel])
 *
 * effLevel is the player's EFFECTIVE level in the skill being evaluated, and is
 * read by exactly one branch: construct_parts, whose XP is decoupled from the
 * recipe tier. Every other branch ignores it, so the two-argument call sites are
 * unaffected. When it is omitted the construct_parts branch falls back to the
 * imported profile via iwConstructionEffectiveLevel(), and to the recipe's own
 * unlock level as a last resort — never to a guess.
 */
function getActions(tier, skill, effLevel) {
```

New cases, inserted after the `gather_fiber` case (keeping gatherers together) and
after the tailoring block respectively:

```js
    case 'woodcutting':
      // Third gathering skill. Same 10s cycle, same 1-per-action yield and the
      // same XP expression the game gives Mining and Herbing, so it shares the
      // toolkit's MINING_XP convention rather than defining a parallel curve.
      return [{ label:`Chop ${WOOD_NAMES[t]}`, time:10, xp:WOODCUT_XP[t], cost:null,
                outputLabel:`1 ${WOOD_NAMES[t]}` }];
```

```js
    case 'construct_parts': {
      // XP does NOT come from `t`. It comes from the player's effective
      // Construction level, which is why this branch reads effLevel. The cost
      // field is EXACT (2t wood + t ore, both 10s gathers at the same yield),
      // so the single-number cost contract upstreamTimePerInput relies on is
      // sound here — unlike Assembly, whose bill is heterogeneous.
      let lvl = (effLevel != null && Number.isFinite(Number(effLevel)))
        ? Number(effLevel) : iwConstructionEffectiveLevel();
      if (lvl == null) lvl = TIER_LVL[t];   // recipe's own unlock, not a guess
      const wood = constructPartsWoodInput(t), ore = constructPartsOreInput(t);
      return [{ label:`Craft ${partsName(t)}`, time:10,
                xp: constructionPartsXpForLevel(lvl),
                cost: constructPartsTotalInput(t),
                costLabel:`${wood} ${WOOD_NAMES[t]}, ${ore} ${ORE_NAMES[t]}`,
                outputLabel:`1 ${partsName(t)}`,
                xpNote:`XP scales to your effective Construction level (${lvl}), not the recipe tier` }];
    }
    case 'construct_assemble': {
      // Deliberately absent from SKILL_GROUP_ACTIONS — see the comment there.
      // Exposed here so a player can price one specific building.
      const bill = assemblyInputs(t);
      return [{ label:`Assemble ${BUILDING_NAMES[t]}`, time: ASSEMBLY_TIME,
                xp: ASSEMBLY_XP[t],
                cost: null,   // heterogeneous bill; NOT a single upstream unit
                costLabel: bill.map(r => `${r.qty.toLocaleString()} ${r.label}`).join(', '),
                outputLabel:`1 ${BUILDING_NAMES[t]}`,
                assemblyBill: bill }];
    }
```

`cost: null` on assembly is load-bearing. `calculateBracketEfficiency` computes
`upstream = (cost != null) ? cost * dep.perUnit : 0` — a non-null cost here would
silently price a 6-line bill as N units of one thing.

### 3.3 `tierMaterialName()`

```js
// anchor: "    case 'gather_fiber':    return FIBER_NAMES[t] || `${metal} Fibre`;"
    case 'woodcutting':     return WOOD_NAMES[t]  || `${metal} Wood`;
```
```js
// anchor: "    case 'jewel_amulet':    return GEM_NAMES[t] || metal;"  (add after)
    case 'construct_parts':
    case 'construction':    return partsName(t);
    case 'construct_assemble': return BUILDING_NAMES[t] || metal;
```

Then extend the adjacent `tierMaterialSelfCheck` fixture list:
```js
      ['woodcutting',       15, 'Sunwood'],
      ['construct_parts',   15, 'Sunforged Building Parts'],
      ['construct_assemble',15, 'Sunforge Arena'],
      ['woodcutting',        1, 'Greenwake Timber'],
```

### 3.4 Skill wiring constants

```js
// anchor: "  smithing:'🔨 Smithing', spellcrafting:'✨ Spellcrafting',"  (SKILL_LABELS)
  woodcutting:'🪓 Woodcutting',
  construct_parts:'🏗️ Construction — Building Parts',
  construct_assemble:'🏗️ Construction — Assemble Building',
  construction:'🏗️ Construction',
```

```js
// anchor: "const LEAF_SKILLS = { combat:'combat', mining:'mining', alchemy:'alchemy' };"
const LEAF_SKILLS = { combat:'combat', mining:'mining', alchemy:'alchemy',
                      woodcutting:'woodcutting' };

// anchor: "const SUB_PANEL_MAP = {"
const SUB_PANEL_MAP = { gathering:'gather-sub', smithing:'smith-sub',
  jewelcrafting:'jewel-sub', spellcrafting:'spell-sub', tailoring:'tailor-sub',
  construction:'construct-sub' };
```

```js
// anchor: "const SKILL_GROUP_ACTIONS = {"  — append inside the object
  woodcutting:  ['woodcutting'],
  // construct_assemble is intentionally NOT here, for the same reason
  // tailor_thread_upgrade is not: its 180s craft and XP are exact, but its
  // input bill is a stockpile of 200t Parts + 100t² wood + 50t² ore + lower-tier
  // Parts — roughly 685 hours of upstream work for one T18 building. Treating
  // that as free would make it a fake levelling recommendation. It is priced in
  // the Calculator instead, where the player asks about one specific building.
  construction: ['construct_parts'],
```

```js
// anchor: "const GATHER_SKILLS = new Set(["
const GATHER_SKILLS = new Set([
  'mining', 'gathering', 'gather_herb', 'gather_fiber', 'spell_harvest', 'woodcutting'
]);
```
Extend `iwManaGatherClassificationSelfCheck` alongside it:
```js
  if (!iwIsGatherActionSkill('woodcutting', 'woodcutting'))
    warn.push('woodcutting is not classified as gather-capable');
  if (iwIsGatherActionSkill('construction', 'construct_parts'))
    warn.push('construct_parts incorrectly inherits Extra Gather Chance');
```

### 3.5 Race bonuses — **two sites, both must change**

`RACE_BONUS` is duplicated. Grep `"human:  { skills: ['combat','mining','gathering','alchemy',"`
— there are **two** hits (one in `calculate()`'s neighbourhood, one in
`getEffectiveXPParams()`). Human is `+1% XP All Skills`, so both new skills belong
in that array. No other race touches them.

```js
    human:  { skills: ['combat','mining','gathering','alchemy',
                       'smithing','jewelcrafting','spellcrafting','tailoring',
                       'woodcutting','construction'], pct: 1 },
```

Leave the `troll` entry alone — it is not in the game's race list any more, but that
is a pre-existing question and not this change's business.

### 3.6 Sub-type panel markup

Insert after the `#tailor-sub` div (anchor: `<div id="tailor-sub" style="display: none;">`).
**The container id must end in `-types`** — `IWStore.snapshotSelection()` finds it
with `sub.closest('[id$="-types"]')`.

```html
        <div id="construct-sub" style="display:none;">
          <div class="step-label">What are you doing?</div>
          <div class="subtype-row" id="construct-types">
            <button class="sub-btn active" data-sub="construct_parts">Building Parts</button>
            <button class="sub-btn" data-sub="construct_assemble">Assemble Building</button>
          </div>
        </div>
```

Woodcutting is a `LEAF_SKILLS` entry, so it needs **no** sub panel — same as Mining.

### 3.7 The tier dropdown / lookup card

`buildTierDropdown(skill)` and `showLookupResult(skill, tier)` call `getActions`
with two arguments. Read both and pass the effective level through for construction
so the lookup card shows the right XP:

```js
// inside showLookupResult, where it calls getActions(tier, skill)
const acts = getActions(tier, skill,
  skill === 'construct_parts' ? iwConstructionEffectiveLevel() : undefined);
```

If an action carries `xpNote`, render it under the XP figure. That one line is what
stops a player concluding the toolkit has the Parts XP wrong when they see T1 and
T34 showing the same number.

**Gate:** parse gate green. Manually: pick Woodcutting → tier ladder works → XP/hr
matches Mining at the same tier. Pick Construction → Building Parts → change the
tier and confirm **XP does not change** while **resources do**. Switch to Assemble
Building and confirm the full material bill renders.

---

## Phase 4 — Planner wiring

### 4.1 Upstream cost model

```js
// anchor: "function upstreamTimePerInput(skill, tier) {"  — add inside the switch,
// after the 'alchemy' case.
    case 'construct_parts':
      // One Parts craft consumes 2t wood + t ore. Both are 10s gather actions
      // and both scale with the same gather yield, so the per-unit cost is a
      // single exact figure and `cost` (3t) multiplies it correctly.
      // Neither producer grants CONSTRUCTION XP — wood is Woodcutting, ore is
      // Mining — so this is a pure time cost with no SAME_SKILL_INPUT entry.
      return { perUnit: HERB_TIME,
               note: GY > 1
                 ? `+${r1(HERB_TIME)}s gathering / wood+ore unit (×${r1(GY)} gather yield)`
                 : `+${GATHER_TIME}s chopping/mining per input unit` };
```

`HERB_TIME` and `GATHER_TIME` are already in scope at the top of that function and
are both `actionSeconds(10, h)` — the same 10 s gather cycle chopping uses. Reusing
them keeps the housing reduction applied.

Do **not** add anything to `SAME_SKILL_INPUT`. Wood → Woodcutting XP and ore →
Mining XP; neither levels Construction. Adding an entry would count another skill's
XP toward Construction — precisely the mistake the map's own comment warns about.

### 4.2 Cross-tier evaluation — the important one

`chooseBestAction(group, tier, level)` evaluates the full *action space* but only at
one tier. Construction's XP is tier-independent, so its optimum is always **T1**,
and the current optimiser structurally cannot see that.

```js
// anchor: "function chooseBestAction(group, tier, level) {"

// Groups whose XP per action is decoupled from the recipe tier, so a LOWER tier
// can be strictly better: same XP, fewer inputs. Construction is the only one.
// For every other skill the highest unlocked tier dominates and scanning lower
// tiers would be pure waste.
const CROSS_TIER_GROUPS = new Set(['construction']);

function chooseBestAction(group, tier, level) {
  const leaves = SKILL_GROUP_ACTIONS[group] || [];
  const all = [];
  const scanFrom = CROSS_TIER_GROUPS.has(group) ? 1 : tier;
  for (const leaf of leaves) {
    for (let tt = scanFrom; tt <= tier; tt++) {
      const cands = calculateBracketEfficiency(leaf, tt, level);
      for (const c of cands) { c.leaf = leaf; all.push(c); }
    }
  }
  if (!all.length) return { candidate: null, ranked: [], runnerUp: null };
  all.sort((a, b) => b.ehpPerSec - a.ehpPerSec);
  return { candidate: all[0], ranked: all, runnerUp: all[1] || null };
}
```

Cost: at most 34 tiers × 1 leaf × ≤34 brackets. Negligible.

**Then fix the reasoning note**, which currently prints
`Best of ${SKILL_GROUP_ACTIONS[group].length} actions` — wrong once candidates span
tiers. Anchor: `"note = \`Best of ${SKILL_GROUP_ACTIONS[group].length} actions: \`"`:

```js
      const scope = CROSS_TIER_GROUPS.has(group)
        ? `${choice.ranked.length} recipes across every unlocked tier`
        : `${SKILL_GROUP_ACTIONS[group].length} actions`;
      note = `Best of ${scope}: ${best.label} (${planFmt(a)} XP/hr effective) ` +
             `beats ${ru.label} (${planFmt(b)}${pct > 0 ? `, +${pct}%` : ''}).`;
```

And add a Construction-specific explanation, because the result looks wrong until
it is explained:

```js
      if (group === 'construction' && best.tier < tier) {
        note += ` Building Parts XP is fixed by your effective Construction level, ` +
                `not by the recipe tier — so the cheapest unlocked recipe (T${best.tier}) ` +
                `wins outright. At T${tier} the XP per craft is identical and the ` +
                `material cost is ${Math.round(constructPartsTotalInput(tier) /
                constructPartsTotalInput(best.tier))}× higher.`;
      }
```

### 4.3 Bracket boundaries

`generateSkillPlan()` already breaks at every `TIER_LVL[t]`, and Construction's XP
steps at exactly those levels (`floor((L−1)/4)+1`). **No change needed** — but add a
comment at the `tierBreaks` loop saying so, otherwise a future reader will "fix" it.

Note that `calculateBracketEfficiency(skill, tier, level)` passes `level` (the
bracket's **base** from-level) into `getActions`. For Construction the XP curve needs
the **effective** level. Patch the one call:

```js
// anchor: "  const actions = getActions(tier, skill);"   (inside calculateBracketEfficiency)
  // Construction Parts XP keys off EFFECTIVE level, so the bracket's base level
  // must have the planner's skill bonus added before it is used. Every other
  // leaf ignores the third argument.
  const effForActions = (skill === 'construct_parts' && level != null)
    ? Number(level) + (iwPlannerSkillBonus('construction') || 0)
    : undefined;
  const actions = getActions(tier, skill, effForActions);
```

### 4.4 Task tables

Extend all four in the block anchored at `"const TASK_LEAVES = {"`:

```js
const TASK_LEAVES = { …,
  woodcutting:['woodcutting'],
  construction:['construct_parts'],
};
const TASK_GATHER_LEAVES = new Set(['mining','gather_herb','gather_fiber','spell_harvest','woodcutting']);
const TASK_GROUP = { …, woodcutting:'woodcutting', construct_parts:'construction',
  construction:'construction' };
const TASK_LABEL = { …, woodcutting:'Woodcutting', construct_parts:'Construction',
  construction:'Construction' };
```

```js
// anchor: "var IW_TASK_LABELS = { combat:'Combat', mining:'Mining', gathering:'Gathering',"
var IW_TASK_LABELS = { combat:'Combat', mining:'Mining', gathering:'Gathering',
  alchemy:'Alchemy', smithing:'Smithing', jewelcrafting:'Jewelcrafting',
  spellcrafting:'Spellcrafting', tailoring:'Tailoring',
  woodcutting:'Woodcutting', construction:'Construction' };
```
(`tailoring` is a pre-existing omission here; adding it is a free, safe fix.)

These feed `renderTaskGearAdvisor`, whose DOM host no longer exists — see §1.7. The
tables are cheap to keep honest; do not build UI against them.

**Gate:** parse gate green. Plan Construction 44 → 50 and confirm the recommendation
is **T1 Copper Building Parts**, with a note explaining why. Plan Woodcutting 49 → 55
and confirm the XP/hr matches Mining at the same tier and level.

---

## Phase 5 — Character panel and profile import

Most of this falls out of Phase 1. Verify rather than build:

1. **Skill cards** — 10 render, correct icons, correct tints, both clickable.
2. **`iwProfileLevel('woodcutting')` / `('construction')`** return 49 / 44.
3. **Planner tiles** — auto-derived from the buttons.
4. **`iwUseSkill('construction')`** selects the Construction button and opens
   `#construct-sub`.
5. **Sub-line** reads `10 skills`.

One real change: **the highest-effective-skill readout**. `iwHighestEffectiveSkillLevel`
now includes both new skills (Phase 1.5), which is correct and is what feeds the
zone bypass. Confirm the Start-page "highest effective X" line still names the right
skill for Curtis (Jewelcrafting 70).

---

## Phase 6 — Village add-ons (new feature)

This is the largest genuinely new surface. Build it **last** and keep it isolated.

### 6.1 Where it lives

The Gear tab is already ~8,000 lines and set-bonus-coupled. Put this in its own
collapsible section on the **Gear tab**, below the existing panels, in its own IIFE
(follow the `gnModule` / Work Order module pattern). Do **not** thread it into
`iwBestInSlot` / `iwBuildGoalLoadout` / the set optimiser — add-ons are not
equipment, occupy no slot, and have no set interaction.

### 6.2 What it does

- Slot count from the existing `#housing-tier` control: `villageAddonSlots(value)`.
  Bind to `change` on that select (it is already an import-driven control).
- N slot pickers, each listing all 34 buildings, showing
  `buildingBuffs(t)` — primary, secondary, XP/task, skill bonus.
- Enforce **one of each type**: a building chosen in one slot is disabled in the others.
- Totals panel: summed ATK / DEF / XP-per-task / Gold Find / Item Find / 2× Gather,
  plus per-skill level bonuses.
- A "best add-ons for…" helper keyed to the existing gear-goal selector
  (`IW_GEAR_GOAL`) — pick the N buildings maximising that goal stat. With ≤5 slots
  and 34 candidates this is a trivial sort, not a knapsack.
- **Cost readout** per building, from `assemblyInputs(t)`, plus the 25% destroy refund.

### 6.3 Persistence

Add `iwVillageAddonsV1` to the localStorage key list documented in `CLAUDE.md`.
Store `{ slots: [tierOrNull × 5] }`. Follow the `iwSocketPlanV1` / `iwPlatePlanV1`
pattern exactly (guarded read/write; a blocked localStorage must degrade, not throw).

### 6.4 Feeding the skill-bonus system — and the double-count risk

The planned add-ons should raise effective skill levels. That means
`iwSkillLevels()` must see them.

**Do not touch `iwEquipmentSkillBonusSources()`** — it walks `profile.equipped` and
must keep meaning *equipment*. Instead add a parallel source and sum it in
`iwSkillLevels()`:

```js
/** Skill-level bonus from PLANNED village add-ons. Never from the profile —
 *  /api/player-profile does not expose villageAddons (verified 2026-09-03), so
 *  this is always user-entered, and it is kept separate from equipment for
 *  exactly that reason. */
function iwVillageAddonSkillBonus(skillName) { … }
```

In `iwSkillLevels()`, add the add-on total to `bonus` in **both** branches
(imported and manual), and push descriptor rows into `sources` so
`iwSkillBoostSourceSummary()` names the building. Add a `source` value of
`'profile+addons'` / `'manual+addons'` so the UI can be honest about where the
number came from.

**Stat buffs — the Q1 assumption, isolated behind one constant.**

Curtis's ruling: assume `combatStats` does **not** already contain add-on stat
buffs, so the toolkit adds them. That is an assumption with no supporting
observation (nobody has an add-on installed yet), so it must not be spread across
the codebase as an implicit belief. Declare it once, name it, and read it
everywhere:

```js
/**
 * IW_ADDON_BUFFS_IN_COMBATSTATS — is the profile's combatStats block already
 * inclusive of installed village add-on buffs?
 *
 * UNVERIFIED ASSUMPTION (2026-09-03, Curtis's call): false.
 * /api/player-profile does not expose villageAddons at all, and no test account
 * had an add-on installed when this was written, so there is no observation
 * either way. We assume the buffs are ABSENT from combatStats and therefore
 * additive here.
 *
 * If it turns out the server does fold them in, flip this to true — every
 * consumer reads this constant, so nothing else changes. To settle it: install
 * one add-on, re-read /api/player-profile?id=<id>, and see whether combatStats
 * moved by that building's primary/secondary magnitudes.
 */
const IW_ADDON_BUFFS_IN_COMBATSTATS = false;
```

Then:

- **Skill-level bonuses**: unconditionally safe to add. `combatStats` has no
  skill-level field of any kind, so there is nothing to double-count. Do not gate
  these on the constant.
- **Stat buffs** (ATK / DEF / XP-per-task / Gold Find / Item Find / 2× Gather):
  add them on top of the imported `combatStats` **only when
  `!IW_ADDON_BUFFS_IN_COMBATSTATS`**, and label them in the UI as coming from
  planned add-ons rather than from the import. Everything the player sees should
  make clear which numbers were measured and which were computed from a plan.
- **Do not write add-on stat buffs into `#xp-per-task` or any other Calculator
  input.** That field is import-authoritative; a planned, unverified bonus
  silently mutating an imported value is exactly the class of bug v4.8.8 fixed.
  Surface the combined figure in the add-on panel and let the player decide.

### 6.5 Wire the Construction XP loop to it

Once `iwSkillLevels('construction')` includes add-ons, `iwConstructionEffectiveLevel()`
picks it up for free, and the Parts XP figure moves when the player plans a
Construction add-on. That is the payoff: the toolkit can then answer *"is the
Kingsfall Grand Library worth a slot for my Construction grind?"* — and with the
+2 buildings at T9/T18/T27 a player can reach effective Construction +5, which is
worth one full XP step every 4 levels.

---

## Phase 7 — Sprite atlas (art work, separate change)

> **DONE 2026-09-04.** All 102 now have art. `item_icons_atlas.png` is
> 1280×6144 with 477 cells; `item_icons_index.csv` has 1,269 rows. Groups
> landed as `resources.wood` / `processed.building_parts` /
> `trade.village_addon`, as suggested in 7.2. Everything below about
> `ITEM_ASSET_VERSION` and the GitHub-raw pin is **historical** — that whole
> mechanism was deleted by the 2026-09-01 icon-chunk split; what gets re-pinned
> now is `manifestUrl` in the `ICON CHUNKS v2` block. See CLAUDE.md.

The original statement of the gap, kept for context:

There is **no icon for any of the 102 new items**. `item_icons_index.csv` has 1,167
rows over 375 shared cells; none match `*_timber`, `*_building_parts` or
`construction_building_tier_*`. The tooltip falls back to the category emoji, which
is acceptable but plain.

### 7.1 How the version pin actually behaves — measured, 2026-09-03

`CLAUDE.md` says replacing an atlas without bumping the pin "serves the old art
from cache indefinitely". **Measured against the real host, that is overstated.**

```
GET raw.githubusercontent.com/BustedCypher/idleWorlds-game-sprites-BC/main/gear_icons_manifest.json?v=…
→ HTTP/1.1 200 · Cache-Control: max-age=300 · ETag: "151efa1e…"
```

Three facts follow, and they change what the pin is for:

1. **The `?v=` string does not select a version.** GitHub raw always serves whatever
   is currently on `main` and ignores the query string entirely. Fetching the *old*
   pinned URL right now returns `asset_version: …lapidaryfix-plus4restore1` — the new
   manifest. The pin's only job is to make the URL *different*, so a browser cannot
   reuse a cache entry stored under the previous string.
2. **The cache lifetime is 300 seconds**, not a year. The usual reason cache-busting
   query strings exist is a host sending `max-age=31536000`; GitHub raw is the
   opposite. So a stale atlas self-corrects within five minutes even with no pin bump.
3. Therefore the current mismatch — manifest `…plus4restore1`, `index.html` pinned to
   `…lapidaryfix1`, from commit `39bc876` which changed the PNG and manifest but not
   `index.html` — is a **bookkeeping drift, not a live user-facing defect**. Nobody is
   stuck on the old +4 art.

**Bump the pin anyway, in the same change as any asset replacement.** Not because of
the five-minute window, but because the pin is the only human-readable record of
which art `index.html` expects, and because the repo is the CDN: if it ever moves
behind a real CDN, or GitHub changes its cache policy, the pin is what makes that
migration safe. Treat it as a version stamp that also busts caches, not as a
correctness mechanism the app depends on today.

Fix the existing drift in this pass — one line — and correct the CLAUDE.md wording
while you are there.

### 7.2 The work itself

- Bump `var ITEM_ASSET_VERSION = 'item-icons-2026-08-10';` in the **same commit** as
  the PNG/CSV replacement. Same for `GEAR_ASSET_VERSION` if gear art moves.
- The manifest's own `asset_version` field is never read by the app. It is
  documentation; keep the two in step by hand.
- Grouping suggestion, matching the existing naming: `resources.wood`,
  `processed.building_parts`, `trade.village_addon` (34 each).

---

## Phase 8 — Optional: the companion gather-skill gate

The game gates every crafting recipe on a **second** skill at `level − 4`:

| Craft skill | Companion | Gate |
|---|---|---|
| smithing, jewelcrafting | mining | `Lv − 4` |
| alchemy, tailoring | herbing | `Lv − 4` |
| **construction** | **woodcutting** | `Lv − 4` |

The toolkit has never modelled this for any skill. It is a pre-existing gap that
Construction merely makes visible, so it is genuinely optional here. If done, do it
generically for all five craft skills in one place — a one-skill special case would
be worse than the current uniform omission.

---

## Phase 9 — Self-check suite H

Add `window.iwWoodcuttingConstructionSelfCheck` following the Stage A–G pattern.
The runner auto-discovers any global whose name ends in `SelfCheck`, so **no
registration is needed** — but add it to the `suites` array in
`iwReleaseCandidateSelfCheck` for an explicit label, matching the others.

Return an **array of failure strings; empty means pass.**

```js
window.iwWoodcuttingConstructionSelfCheck = function iwWoodcuttingConstructionSelfCheck(){
  var fail = [];
  function ok(label, cond){ if(!cond) fail.push(label); }
  function eq(label, actual, expected){
    if(actual !== expected) fail.push(label + ': got ' + String(actual) + ', expected ' + String(expected));
  }
  try {
    // ── 1. Skill identity — the v5.3.1 alias bug, permanently pinned ──
    ok('woodcutting resolves to itself',  window.iwResolveSkillKey('woodcutting')  === 'woodcutting');
    ok('construction resolves to itself', window.iwResolveSkillKey('construction') === 'construction');
    ok('herbing still resolves to gathering', window.iwResolveSkillKey('herbing') === 'gathering');
    ok('woodcutting is in IW_EFFECTIVE_SKILL_KEYS',
       IW_EFFECTIVE_SKILL_KEYS.indexOf('woodcutting') >= 0);
    ok('construction is in IW_EFFECTIVE_SKILL_KEYS',
       IW_EFFECTIVE_SKILL_KEYS.indexOf('construction') >= 0);

    // ── 2. Woodcutting mirrors Mining exactly ──
    [1, 9, 18, 34].forEach(function(t){
      eq('WOODCUT_XP T' + t + ' mirrors MINING_XP', WOODCUT_XP[t], MINING_XP[t]);
    });
    eq('chop action count T18', getActions(18, 'woodcutting').length, 1);
    eq('chop label T18', getActions(18, 'woodcutting')[0].label, 'Chop Regal Timber');
    eq('chop is gather-capable', iwIsGatherActionSkill('woodcutting', 'woodcutting'), true);

    // ── 3. Parts XP: the full 143-row vendor table ──
    // The packet's effectiveLevelXpTable, spot-checked at every boundary that
    // matters plus both clamps. Values are the vendor's, not re-derived.
    [[1,14],[4,14],[5,58],[8,58],[9,130],[33,576],[69,1354],[100,1958],
     [129,2650],[132,2650],[133,2736],[143,2736]].forEach(function(p){
      eq('parts XP at effective level ' + p[0], constructionPartsXpForLevel(p[0]), p[1]);
    });
    eq('parts XP clamps below 1',  constructionPartsXpForLevel(0),   14);
    eq('parts XP clamps above 34', constructionPartsXpForLevel(999), 2736);

    // ── 4. Parts XP is INDEPENDENT of recipe tier — the core mechanic ──
    var a1  = getActions(1,  'construct_parts', 133)[0];
    var a34 = getActions(34, 'construct_parts', 133)[0];
    eq('T1 and T34 Parts award identical XP', a1.xp, a34.xp);
    eq('T1 Parts cost 3 units',  a1.cost,  3);
    eq('T34 Parts cost 102 units', a34.cost, 102);
    ok('T1 Parts is 34x cheaper than T34', a34.cost === a1.cost * 34);

    // ── 5. Assembly ──
    eq('assembly XP T1',  ASSEMBLY_XP[1],  14);
    eq('assembly XP T18', ASSEMBLY_XP[18], 338);
    eq('assembly XP T34', ASSEMBLY_XP[34], 684);
    var asm = getActions(18, 'construct_assemble')[0];
    eq('assembly duration', asm.time, 180);
    ok('assembly cost must stay null (heterogeneous bill)', asm.cost === null);
    ok('assembly is excluded from the optimiser action space',
       SKILL_GROUP_ACTIONS.construction.indexOf('construct_assemble') === -1);

    // ── 6. Assembly bill, exact ──
    var b2 = assemblyInputs(2);
    eq('T2 bill row count', b2.length, 4);
    eq('T2 current-tier Parts', b2[0].qty, 400);
    eq('T2 raw wood',           b2[1].qty, 400);
    eq('T2 ore',                b2[2].qty, 200);
    eq('T2 lower-tier Parts',   b2[3].qty, 40);
    eq('T1 has no lower-tier picks', constructionLowerTierPicks(1).length, 0);
    eq('T34 lower-tier picks',
       constructionLowerTierPicks(34).join(','), '11,12,31');
    var b34 = assemblyInputs(34);
    eq('T34 raw wood', b34[1].qty, 115600);
    eq('T34 ore',      b34[2].qty, 57800);

    // ── 7. Buildings ──
    eq('T1 building name',  BUILDING_NAMES[1],  'Training Yard');
    eq('T34 building name', BUILDING_NAMES[34], 'Primordial Wonder');
    eq('T1 skill bonus', JSON.stringify(buildingSkillBonus(1)),
       JSON.stringify({skill:'mining', amount:1}));
    eq('T9 skill bonus', JSON.stringify(buildingSkillBonus(9)),
       JSON.stringify({skill:'construction', amount:1}));
    eq('T10 skill bonus caps at +2', JSON.stringify(buildingSkillBonus(10)),
       JSON.stringify({skill:'mining', amount:2}));
    eq('T19 skill bonus never exceeds +2', buildingSkillBonus(19).amount, 2);
    var b14 = buildingBuffs(14);
    eq('T14 primary stat',  b14.primary.stat,  'doubleGather');
    eq('T14 primary value', b14.primary.value, 10);
    eq('T14 secondary stat',  b14.secondary[0].stat,  'def');
    eq('T14 secondary value', b14.secondary[0].value, 6);
    eq('T14 xp buff',         b14.secondary[1].value, 8);
    eq('T14 skill', b14.skill.skill, 'jewelcrafting');

    // ── 8. Add-on slots ──
    eq('no housing, no slots',   villageAddonSlots(0), 0);
    eq('Villa gives 3 slots',    villageAddonSlots(3), 3);
    eq('Citadel gives 5 slots',  villageAddonSlots(5), 5);
    eq('slots cap at 5',         villageAddonSlots(9), 5);

    // ── 9. Names ──
    eq('T18 wood',  WOOD_NAMES[18],  'Regal Timber');
    eq('T18 parts', partsName(18),   'Kingssteel Building Parts');
    eq('T1 parts',  partsName(1),    'Copper Building Parts');

    // ── 10. Item data reaches the DB ──
    if (typeof IDB_STATE !== 'undefined' && IDB_STATE && IDB_STATE.idMap) {
      ['copper_timber','primordial_heartwood','copper_timber_building_parts',
       'construction_building_tier_1','construction_building_tier_34']
        .forEach(function(id){ ok('item present: ' + id, !!IDB_STATE.idMap.get(id)); });
      var bld = IDB_STATE.idMap.get('construction_building_tier_1');
      if (bld) eq('building carries its skill bonus', bld.skillBonusSkill, 'mining');
      // Buildings must NOT be reachable as equipment.
      var gear = (typeof iwGearPlannerItems === 'function') ? iwGearPlannerItems() : [];
      ok('buildings never enter the gear candidate pool',
         !gear.some(function(r){ return /^construction_building_tier_/.test(String(r && r.id || '')); }));
    }
  } catch(e){ fail.push('suite threw: ' + (e && e.message ? e.message : String(e))); }
  if (fail.length && typeof console !== 'undefined')
    console.warn('[Woodcutting/Construction] FAILED:', fail.join(' | '));
  return fail;
};
```

Then:
```js
// anchor: "        ['Gear import integrity',window.iwGearImportIntegritySelfCheck]"
        ['Gear import integrity',window.iwGearImportIntegritySelfCheck],
        ['Woodcutting/Construction',window.iwWoodcuttingConstructionSelfCheck]
```

**Prove the suite works before trusting it.** A suite that returns `[]` because a
function is missing is indistinguishable from a pass — the runner skips non-functions
silently via `typeof pair[1] !== 'function'`. So:
1. Temporarily change `ASSEMBLY_XP[18]` to `339`, run
   `iwWoodcuttingConstructionSelfCheck()`, confirm a non-empty array. Revert.
2. Confirm `typeof window.iwWoodcuttingConstructionSelfCheck === 'function'` — not
   just that it returned `[]`.
3. Confirm `iwReleaseCandidateSelfCheck()` returns `[]` overall.

**Update `CLAUDE.md`**: the suite list becomes fourteen, and the new suite name goes
in the enumerated list.

---

## Recommended sequencing and verification

| Phase | Risk | Independently shippable | Gate |
|---|---|---|---|
| 0 Payload + baseline | low | yes | parse gate + suite A count |
| **1 Skill identity** | low | **yes — ship this first, it fixes live bugs** | parse gate + selfcheck 17 |
| 2 Data tables | low | yes (dead code until 3) | parse gate + console spot-checks |
| 3 Calculator | medium | yes | manual: chop + parts + assemble |
| 4 Planner | medium | yes | plan Construction 44→50 ⇒ T1 |
| 5 Character panel | low | falls out of 1 | visual |
| 6 Village add-ons | high | yes | new panel only |
| 7 Sprites | low | separate change | version pin |
| 8 Companion gate | medium | optional | — |
| 9 Suite H | low | after 2–4 | break-it-on-purpose |

**Phase 1 alone is worth shipping immediately.** It costs about 40 lines and it fixes
a silent data-corruption path that is already live against Curtis's own profile.

## Verification discipline for the report-back

State plainly which kind of verification was done. "Parses and I read the code" is
not "I loaded it in a browser". No session can verify live behaviour — only Curtis
can. Distinguish "the suite returned an empty array" from "the suite exists and
returned an empty array", and say which one you checked.
