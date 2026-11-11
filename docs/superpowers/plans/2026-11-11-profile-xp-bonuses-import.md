# Profile `xpBonuses` import: implementation plan (v7.7)

## Status

Implemented in the working tree:

- Step 1: parser — implemented.
- Step 2: multi-skill Skill Boost chips — implemented.
- Step 3: percentage controls — implemented.
- Step 4 (including 4b): flats, potion import and housing-independent XP — implemented.
- Step 5: profile daily boost — implemented.
- Step 6: per-skill catch-up — implemented.
- Step 7: game breakdown row — implemented.
- Step 8: suite AB — implemented.
- Step 9: v7.7 documentation and version — implemented.

Verified 2026-11-11 in a browser on a local server: the full self-check run
is empty (suite AB included), AB fails when its checks are broken on purpose,
and an import of the real 2026-11-11 profile fills every control. Nothing is
committed or deployed.

Found and fixed during that check:
- `/api/player-profile` has no `guildHallLevels` (only player.json does), so
  Guild Hall stayed at 0 and every skill read 2% short. The importer now
  fills the level from `everySkill` `guildHall` (2 × level) when the profile
  has no levels. Suite AB covers it.
- Suite Z's `calculate()` check failed once real flats were loaded (gear 171,
  potion 44, world boss 24 diluted the second ore below its ×1.5 bar). It
  now zeroes and restores the flats for that check; the assertion itself is
  unchanged.
- Suite AB's catch-up checks could not tell the profile path from the rule
  (they agree on the sample). Cases where the two disagree were added.

**Goal:** a profile import fills every Calculator XP input from the game's own
per-skill XP breakdown, so the Calculator, the Planner and the task advisors
show the XP the game would pay with no manual ticking. The Daily XP Boost gets
its first offline answer.

**Source:** `/api/player-profile?username=…&league=…`, sample saved 2026-11-11
(`Desktop/player-profile (1).json`). Compared with the 2026-10-22 sample, it
adds `xpBonuses`, `serverBoosts`, `zoneNumber`, `guildName` and `isPatron`.
player.json (`/api/player`) still has no `xpBonuses` or `combatStats`, so
this work is profile-only.

**Release:** v7.7, staged as `index2.html` first (see CLAUDE.md → Commits).
New suite: **AB** (`iwProfileXpBonusesSelfCheck`).

---

## 1. What the payload says

```text
xpBonuses.formula      "xp per action = (base + flatPerTask.total) * (daily ? 1.2 : 1)
                        * (1 + percent / 100) * (catchUp ? 1.2 : 1)"
xpBonuses.flatPerTask  { gear: 171, potion: 44, worldBosses: 24, total: 239 }
xpBonuses.everySkill   [ achievements 50, server 25, zcRank 20, guildHall 2, teamZone 10 ]
xpBonuses.skills.<k>   { percent, daily, catchUp, effectivePercent, parts:[{key,label,percent}] }
                       parts = everySkill + per-skill keys seen so far: skillBoost (25), race (5)
```

Checked by hand: `effectivePercent = (daily?1.2:1) × (1+percent/100) × (catchUp?1.2:1) − 1`
(herbing 148.4, spellcrafting 198.1). `flatPerTask.gear` equals
`combatStats.xpTaskBonus`. The `parts` add up to `percent` for every skill in
the sample.

The Calculator already uses this formula (`calculate()`, `actionXP` line). The
work is about filling its inputs, not changing the math.

### Findings this changes in the toolkit

1. **Several skill boosts at once.** This sample has +25 `skillBoost` on
   combat, mining **and** jewelcrafting. player.json's `activeXpBoosters` has
   `boostKind:"skill"` rows for all three. `#skill-boost-skill` is a
   single-select, and `iwSkillBoostPct(group)` returns 25 for only one skill.
   So the toolkit underpays every boosted skill but one. This is a model bug,
   not just a missing import.
2. **Daily XP Boost has an answer.** `skills.<k>.daily` names today's three
   skills (herbing, alchemy, spellcrafting in the sample). It is valid only
   for the game day of the fetch.
3. **Catch-up is per skill from the server.** The toolkit hard-codes
   Spellcrafting ≤ 70 (`iwSpellcraftCatchupMult`). The flag agrees today
   (Spellcrafting 68 → true), but the server value is authoritative and
   covers other skills if the game extends catch-up.
4. **Zone Control is now imported.** The values are `zcRank` (20, matching the
   `#zc-leaderboard` options 0–25 in steps of 5) and `teamZone` (10, matching
   `#zc-team`). Both were manual until now.
5. **Potion and world-boss flats come back as numbers.** `potion` 44 matches
   player.json `activeXpBuffPercent: 44` (`frostiron_xp_potion_super`).
   `worldBosses` 24 matches `#boss-active`.
6. `serverBoosts.itemFindPercent` (25) is new. The 2x Gather half is already
   handled (suite Z). Item find is out of scope for the Calculator. Note it
   for the Gear and loot work.

---

## 2. Design decisions

**D1. Prefill, don't lock.** The import writes each value into the existing
control through `setInput` / the control's own change event, the same way
achievements and Guild Hall already do. The player can still change any field
to model "what if". There are no hidden overrides inside the XP functions, so
the three XP paths (below) keep reading the controls and stay in agreement.

**D2. Absent means "leave the manual value alone", never zero.**
- A missing `xpBonuses` (an older endpoint or a cached profile) changes nothing.
- A part that is missing from a present `xpBonuses` *does* mean 0 for that
  source. The server lists every non-zero part, and the sample omits `race`
  where it doesn't apply. So when `xpBonuses` is present, the import untoggles
  `#server-bonus` and `#zc-team` if their keys are absent. The plan pins this
  reading with a fixture in suite AB.
- **`#new-player-promo` is never touched by the import** (Curtis,
  2026-11-11). It stays a manual checkbox for new players.
- An unknown part key is not dropped. It is summed into an "Other (from
  profile)" bucket (D5), so a new game bonus is counted rather than lost.

**D3. Snapshot data goes stale. Each field is stored with its lifetime.**

| Field | Lifetime | Where it goes |
|---|---|---|
| `daily` flags | until the next noon-ET reset | `iwDailyBoostV1` with `serverDay` from `serverDayString()` (existing same-day rule) |
| `skillBoost` parts | until each boost's `endsAt`, which only player.json has | the new multi-skill control; the import helper says "from your profile, <time>" |
| `server`, `zcRank`, `teamZone` | hours to a month | controls, like the other imports |
| `achievements`, `guildHall`, `race` | until the player changes them | already imported; cross-check only |
| `catchUp` | until the level passes the cap | per-skill flag on the stored profile, falling back to the hard-coded rule |
| `flatPerTask.potion` | until the potion expires | matched to a `#potion-tier` option; else helper text only |

Because `window.IWProfile` persists `xpBonuses` with the rest of the profile,
nothing reads `xpBonuses.daily` from the stored profile on a later day. Daily
flows only through the dated cache.

**D4. Daily precedence.** `getActiveDailyBonus()` order is unchanged: user
override → event override → live/cached → unknown. A profile import writes
the cache with `source:'profile'`. A wiki scrape on the same day may overwrite
it, but if the two disagree, the profile wins and the disagreement is logged
to the console. The profile is the game's own answer for this player.
`DAILY_BONUS_LIVE.bonus` stays `DAILY_BONUS_CONFIG.bonusPercent` (20, which
the formula's ×1.2 confirms).

**D5. Show the server's breakdown.** Under the Calculator's XP line, add a
compact "From your profile" row listing the selected skill's `parts` and
`effectivePercent`. Mark a mismatch when the toolkit's own `totalPct` for that
skill differs from `xpBonuses.skills[k].percent`. That warning is how the next
missing bonus gets caught, the way Guild Hall was found by a 1% gap.

---

## 3. Steps

### Step 1: Parser (pure, no DOM)
`iwXpBonusesFromProfile(profile)` → `undefined` | normalised object:
```js
{ fetchedAt, serverDay,
  flat: { gear, potion, worldBosses, total },
  every: { achievements, server, zcRank, guildHall, teamZone, …unknown },
  skills: { mining: { percent, daily, catchUp, effectivePercent,
                      parts: { skillBoost:25, race:5, … } }, … } }
```
- Map skill keys through `iwCanonicalSkillKey`. The profile says `herbing`;
  the skill-boost select and some groups say `gathering`. Pin the mapping for
  all 10 keys in the suite.
- Numbers only: a non-finite value becomes `undefined`, never 0 (rule 2).
- `fetchedAt` is the import time. `serverDay` is `serverDayString(fetchedAt)`.

### Step 2: Multiple skill boosts (fixes finding 1)
- Replace `#skill-boost-skill` (single select) with a **chip row**, one
  toggle chip per skill, backed by one hidden input `#skill-boost-skills`
  holding a comma list. IWStore captures by id, so the new control persists
  automatically. Chips (Curtis: "more fun, be creative"):
  - each chip carries the skill's item-atlas icon and its name; off chips are
    dim and outlined, on chips fill with the skill's colour and show a
    small "+25%" badge;
  - toggling a chip on plays a short pop (scale 1 → 1.08 → 1, ~150 ms) with
    a spark burst behind the badge; `prefers-reduced-motion` gets a plain
    colour change;
  - chips set from the profile get a small profile marker (the import icon)
    until the player changes them, so you can see at a glance which boosts
    the game reported and which you added;
  - a running total after the row, e.g. "3 skills boosted";
  - Ashen sheet first, mirrored in the legacy sheet's parity block so it
    works under both skins (suite L). Keyboard: chips are `<button
    aria-pressed>`, so Space/Enter toggle them.
- Migrate: if the stored single value exists, check that one skill.
- `iwSkillBoostPct(group)` returns 25 when `group` is in the set. Its two
  current suite assertions (lines `eq('Skill Boost reader, …')`) are updated
  in this stage, since this stage intentionally changes that mechanic.
- Import: tick exactly the skills whose `parts` hold `skillBoost`, using the
  part's percent rather than the hard-coded 25 when they differ. If they
  differ, keep the constant and log it, since the select has no free field.

### Step 3: Fill the percent controls from `everySkill`
In `applyProfileCore`, inside the existing re-entrancy guard (CLAUDE.md:
one import = one repaint), and only when `xpBonuses` is present:
- `#server-bonus` ← `server` present
- `#zc-team` ← `teamZone` present
- `#zc-leaderboard` ← `zcRank` (add an option for an off-grid value, like
  `iwApplyAchievementFromProfile` does)
- `#new-player-promo`: not touched (manual only, D2)
- `achievements` and `guildHall`: already imported from
  `achievementXpBoostPercent` / `guildHallLevels`. Cross-check only; on a
  mismatch, trust the existing source and warn.
- Each control's helper text: "From your imported profile. Change it to
  override."

### Step 4: Flats
- `#xp-per-task` ← `flat.gear` (same value as today's
  `combatStats.xpTaskBonus`; keep the existing fallback).
- `#boss-active` ← `flat.worldBosses > 0`. If `worldBosses` is not 24 (or 30
  with the Hollow Rider), warn. Don't invent a control.
- Potion: find the `#potion-tier` / `#potion-super` selection whose
  `potionFlatForSelection()` equals `flat.potion`. If exactly one matches,
  apply it; otherwise leave it and put "Profile reports +N XP/task from
  potions" in `#potion-helper`. The player's own player.json
  `activePotionKey` can settle ties later (out of scope).

### Step 5: Daily boost from the profile
- If the import's `serverDay` is today: set `DAILY_BONUS_LIVE.groups` to the
  canonical keys where `daily === true`, set `source = 'profile'`, then call
  `saveCachedDailyBoost()` and `renderDailyBonus()`.
- If no skill is daily, still write an empty set dated today. That means
  "no daily boost today" (Curtis, 2026-11-11), unlike `isUnknown`. It should
  never happen in game, but the path exists and suite AB covers it. The panel
  says "No daily boost today (from your profile)", not "unavailable".
  `loadCachedDailyBoost()` currently rejects an empty `groups` array, so it
  needs a `source === 'profile'` exception, or the empty answer is lost on
  reload.
- The wiki path at the `source = 'wiki'` line must not clobber a same-day
  `profile` answer. Apply the D4 rule.

### Step 6: Catch-up per skill
- `iwSpellcraftCatchupMult(skillKey, level)` checks
  `iwXpBonusesFromProfile(window.IWProfile)` first. If the profile has the
  skill's `catchUp`, and the profile level for that skill equals the level
  passed in (so a Planner run to a future level doesn't use today's flag),
  it returns 1.2 or 1 from the flag. Otherwise it falls back to the current
  Spellcrafting ≤ 70 rule.
- Rename is optional. If renamed, keep the old name as an alias so the three
  call sites and any suite references keep working.

### Step 7: Breakdown row and mismatch check (D5)
- `iwToolkitXpPercentFor(skill)` returns the sum that `calculate()` already
  builds (`totalPct`, minus the Jewelcrafting event term, which the server
  would list as its own part). Refactor the three paths to share it, or call
  it alongside them. Do not change their results.
- Render the server's `parts` list and `effectivePercent` for the active
  skill. Show "Toolkit differs from game: +X%" when
  `|toolkit − server.percent| ≥ 0.5`.
- No row without an imported `xpBonuses`.

### Step 8: Suite AB (`iwProfileXpBonusesSelfCheck`)
Fixture: a trimmed copy of the 2026-11-11 profile, inline (only `skills`,
`xpBonuses`, `serverBoosts`, `race`, `achievementXpBoostPercent`,
`guildHallLevels`, `combatStats.xpTaskBonus`). Assert:
1. The parser normalises all 10 skills and maps `herbing` correctly.
2. `effectivePercent` recomputes from `percent` / `daily` / `catchUp` for every skill.
3. The `parts` sum equals `percent` for every skill.
4. After an import: `iwSkillBoostPct` gives 25 for combat, mining and
   jewelcrafting and 0 for the other 7; `#zc-leaderboard` = 20; `#zc-team`,
   `#server-bonus` and `#boss-active` checked; `#new-player-promo` unchanged by the import (test it both on and off);
   `#xp-per-task` = 171.
5. The toolkit's `totalPct` equals the server's `percent` for every skill
   (with the daily override off and no Jewelcrafting event). This is the
   headline assertion.
6. `calculate()` on a fixed action (e.g. a Mining tier with a known base)
   gives `round((base + 239) × (1 + 137/100))` for mining.
7. Daily: dated today, `getActiveDailyBonus().skills` = the three daily
   groups. Dated yesterday, nothing is applied (`isUnknown`). Dated today
   with no daily skill: an empty set that is *not* `isUnknown`, and it
   survives `loadCachedDailyBoost()`.
8. Catch-up: spellcrafting is 1.2 at the profile level and falls back to the
   rule at another level.
9. Absent `xpBonuses` changes no control (snapshot before/after).
10. Break one assertion on purpose and confirm the suite fails (verification
    discipline).

Also add `iwProfileXpBonusesSelfCheck` to `iwReleaseCandidateSelfCheck`'s
`suites` list. The storage guard wraps it automatically.

### Step 9: Docs and release
- CLAUDE.md: a suite AB paragraph, the multi-skill-boost rule, and the "daily
  from profile" exception to the Daily XP Boost trap note.
- Header comment version entry and the `ver-pill` = `<title>` = v7.7.
- Update `docs/player-json-loadouts-request.md` #8. It is still open for
  player.json, so ask for `xpBonuses` there too.
- Parse gate, all suites green, staging push to `index2.html` on request.

---

## 4. The three XP paths (all must agree)

| Path | Where | Reads |
|---|---|---|
| `calculate()` | Calculator | controls directly |
| `getEffectiveXPParams()` | Planner | controls via `g()` |
| `taskBonusEnv()` | task / gear advisors | controls via `g()` |

Every change above goes through the controls or a shared helper
(`iwSkillBoostPct`, `iwSpellcraftCatchupMult`, `getActiveDailyBonus`), so all
three move together. Suite AB #5 checks the Calculator path; add a one-line
equality check that the other two give the same `totalPct` for each skill.

---

### Step 4b: Flat XP is not scaled by housing (Q1)
Curtis: flat XP comes from the skill and tier, not housing. Today every XP
path multiplies the flats by `getDurationFactor(actionTime, housingTier)` =
`max(1, round(effectiveDuration / 10))`. Since v6.9 every craft is a 10 s
action, and housing only shortens it, so `df` is already 1 for every 10 s
action and no current figure changes. The term is dead weight that disagrees
with the game's formula.
- Remove `df` from the flat term in `calculate()`, `getEffectiveXPParams()`
  and `taskBonusEnv()`: `flatBonus = xpBuffBonus`.
- Before removing it, list every `actionTime` the three paths can receive. If
  any is over 14 s (where `df` would reach 2), report it rather than
  silently changing that action's XP.
- Keep `effectiveDuration()` for action *time*: housing still speeds actions
  up, which is XP/hour, not XP/action. Curtis (2026-11-11): a T4 house makes
  every action 6 s. The existing rule already gives that
  (`max(5, 10 − housingTier)` for a 10 s action → 10 − 4 = 6). Suite AB pins
  it for tiers 0–5: 10, 9, 8, 7, 6, 5 s. The flat XP per action stays the
  same at every tier.
- Update the formula comments (the "durationFactor" blocks), and the
  `DFA`/`DFC` use in the later suite if it asserts the scaling.

---

## 5. Answers (Curtis, 2026-11-11)

1. **Duration factor:** flat XP does not depend on housing → Step 4b.
2. **New-player promo:** leave it as a manual checkbox; the import never
   touches it (D2). Other unseen part keys still go to the "Other" bucket
   and the mismatch row.
3. **Empty daily set:** means "none today". It should never happen, but it
   is planned for (Step 5, suite AB #7).
4. **Skill boost UI:** chips, made fun (Step 2).
5. **Lock option:** no. Prefill + override (D1) only.
