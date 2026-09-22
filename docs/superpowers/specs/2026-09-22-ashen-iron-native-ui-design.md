# Ashen Iron — native UI rewrite of the toolkit

Date: 2026-09-22. Status: in progress, developer-gated.

## Goal

Rebuild the toolkit's page in the Fantasy Skin's "Ashen Iron" design language
(`idleworlds-fantasy-skin`, `src/styles/base.css` + `ui-system.css`). The aim is
not to paint over the existing panels. The artwork and styles become the panels
themselves: native markup and one stylesheet written for it.

Decisions (Curtis, 2026-09-22):

| Question | Decision |
| --- | --- |
| Scope | Everything — shell and every tab — bug-fixing as we go |
| Default | **Not** default. Enabled from Settings → Developer only, until Curtis flips it |
| Zone themes | Single theme only (the un-themed Ashen Iron palette and art) |
| Old 8 themes | Retired — deleted at cutover, not before |
| Workspace | In place in `index.html`, tab by tab, page shippable after every step |

## The switch: one stylesheet system per mode

`<html data-skin="ashen">` is the only switch. It is independent of
`data-theme`, so the user's chosen legacy theme survives a round trip through
the preview.

- **Legacy CSS** is every existing sheet, each tagged `data-iw-sheet="legacy"`:
  the main `<style>`, `#iw-panel-styles`, the jewelry block, the footer block,
  `construction-planner.css`, and the Google Fonts link.
- **Ashen CSS** is the new sheet, tagged `data-iw-sheet="ashen"`.
- The `<head>` boot script runs before first paint. It reads `iw_skin_v1`, sets
  `data-skin`, and parks the inactive family under `media="not all"`. In Ashen
  mode no legacy rule applies, so nothing is "overridden". Every surface is
  styled by rules written for it, or it visibly is not styled yet. That is how
  unconverted work shows up.
- `iwSetSkin(name)` does the same live and fires `iw:skinchange`.

Why not scope the legacy CSS under `:root:not([data-skin])`? That would raise
the specificity of all ~228 KB of rules by (0,1,1) and reorder them against the
JS-injected and inline styles. `@font-face` and `@keyframes` also cannot nest.
Disabling whole sheets changes nothing about how the legacy page cascades.

**Inline styles are the leak.** 365 static `style=""` attributes and about 116
JS `.style.x =` writes apply in both modes. Converting a surface means moving
its inline styles into classes. The legacy sheet gains the equivalent rule so
the default look is unchanged.

## Markup rules during the transition

1. **Every id and every JS-queried class stays.** The engine finds its UI by
   `$('id')`, `querySelector`, and class toggles (`.active`, `.on`, `.open`,
   `dev-mode`, `mode-simple`…). Before removing a class from markup, grep
   `index.html` for it as a string, including `classList` and `className` sites.
2. New component classes are added next to the legacy ones (`class="panel
   ash-frame"`). The legacy sheet ignores `ash-*`, and the Ashen sheet ignores
   the legacy classes except the ones that carry state.
3. A new wrapper element must not change the legacy layout. Check both modes in
   the browser after each tab.
4. `data-ui` names (see `docs/ui-theme-hooks.md`) stay stable. New containers
   get names too.
5. At cutover, legacy-only classes, the legacy sheets, the 8 themes, the swatch
   picker, `iwSetTheme` / `iw_theme_v1` and `data-theme` are deleted in one pass.

## Design language (from the skin)

- **Ink:** `--iw-ink-950 #070806` → `--iw-ink-600 #29251C`. Text `#DDD6C6`, hi
  `#F0E8D6`, dim `#938A79`, faint `#666052`.
- **Accent layer `--iw-th-*`:** brass accent `#D4AD63`, edge `#6B4F28`, gold
  hairline `#9B7437` → `#D09A4B`, ember CTA `#B64619` / `#D15A22`, ground
  gradient `#171713` → `#0D0E0C`.
- **Semantic:** good `#82B88A`, bad `#D27171`, info `#75A8C8`. Tier colours
  common through mythic. State colours are never repainted uniformly (skin
  rule 5).
- **Type:** Cinzel for headings (frame title 18px, letter-spacing .035em),
  Barlow for UI, Crimson Text italic for flavour text.
- **Shape:** radii 2–4px. A control is 32px high (36px large). Spacing scale is
  4 / 6 / 9 / 12 / 16.
- **Forged frame:**
  - Ground: texture over the gradient, with an inset black keyline and an inset
    top glow.
  - A 1px `--iw-th-edge` border.
  - A gold hairline `::before` across the top.
  - Corner filigree `::after` drawn with `border-image` (34×32 at desktop,
    27×25 at ≤1024px), so the corners stay a fixed size at any panel height.
  - Content is raised to z-index 1.
- **Controls:** a "carved slate" bevel with an inset shadow. Hover lights an
  ember inner glow. Focus is a gold outline with 2px offset. Inputs are recessed
  troughs.
- **Dividers:** the separator flourish.
- **Density:** dense ARPG utility, not dashboard cards. Boxes are reserved for
  real controls and actions. Data is flat.

Because the toolkit owns its markup, none of the skin's detection, `:has()`
chains or `!important` escalation carries over. The frame is a class.

## Assets

`assets/ashen/` holds the un-themed set only (single theme), about 285 KB:

- `panel_corners.webp`
- `separator_flourish.webp`
- `panel_texture.webp`
- `skills_ui_atlas.webp` + `skills_ui_index.json`
- `fonts/` — Cinzel variable, Barlow 400–700, Crimson Text italic (all SIL OFL)

Everything is same-origin. `assets/ashen/` is not caught by any `.assetsignore`
exclusion.

## Components (`ash-` prefix)

`ash-frame` (major, with filigree) · `ash-frame--inset` (nested, no filigree)
· `ash-frame-head` / `ash-title` / `ash-sub` · `ash-rule` (flourish) · `ash-btn`
/ `--cta` / `--ghost` · `ash-field` · `ash-seg` · `ash-chip` · `ash-stat` ·
`ash-table` · `ash-nav` / `ash-tab`. The baseline sheet also styles bare
elements (h1–h3, inputs, selects, buttons, tables, details) so that an
unconverted tab is usable in Ashen mode from day one.

## Phases

1. **Foundation:** assets, boot switch, sheet tagging, tokens + base elements,
   Developer toggle, self-check suite L.
2. **Shell:** appbar, rail, tab bar, bottom nav, skill-tools menus, footer.
3. **Shared components:** panel/frame, heads, fields, buttons, seg, chips,
   tables, `iw-tip`, result hero, settings rows.
4. **Tabs, in order:** Calculator → Start → Planner → Gear → Work Order →
   Jewelry → Construction → Items → Settings.
5. **JS-rendered markup and inline-style migration**, per tab as it is reached.
6. **Cutover (on Curtis's word):** Ashen becomes the default and legacy is
   deleted.

## Progress

- **Phase 1 — foundation (done 2026-09-22).** Switch, tokens, the legacy
  token bridge, behaviour parity, suite L, and the shell (appbar, rail,
  bottom nav).
- **Calculator (done 2026-09-22).** Section 9 of the Ashen sheet.
  - **Markup changes:**
    - 36 static inline styles lifted into classes, each with a verbatim
      `!important` twin at the end of the legacy main sheet.
    - The skill emoji is wrapped in `.skill-glyph`, which the Ashen sheet
      masks with the skin's skill artwork (`assets/ashen/skills/*.svg`).
    - `updateHouseArt()` writes `data-tier`, which paints the game's own
      housing art (`assets/ashen/housing/*.webp`, 128px thumbnails).
    - The gather toggle uses `.is-on` / `.is-off` instead of inline colours.
  - **Legacy mode is unchanged.** A computed-style diff of every element in
    the tab (663 elements × 38 properties) against the pre-edit snapshot
    reports 0 differences. The diff was negative-controlled: a 2px font nudge
    is caught.

- **Start (done 2026-09-22).** Section 10 of the Ashen sheet.
  - **The hero** is a banner on the skin's header surface
    (`assets/ashen/hero_surface.webp`), with the skin's crest
    (`assets/ashen/crest.webp`) painted onto the tier-ring SVG. The appbar
    uses the same crest. The SVGs stay in the DOM for legacy.
  - **Import status:** `setStatus()` writes `data-state` (info/ok/warn/err)
    instead of inline colours.
  - **Inline styles:** four static inline styles in the Start markup and in
    `iwRenderCharacter()`'s templates are lifted into classes, each with a
    verbatim legacy twin.
  - **Skill map:** a single `[data-skill]` block now supplies `--sk-tint` and
    `--glyph` to every surface. Character-panel cards reuse it, and so will
    the Planner's tiles.
  - **Stat cards:** `renderInfoPanels()`'s cards (the legacy
    `#iw-panel-styles` sheet) are re-authored.
  - **Content fix:** the hero said "8 skills"; it now says 10.
  - **Legacy mode is unchanged:** 327 elements in the tab, with the test
    profile imported, diff to 0 against the pre-edit snapshot. The check is
    negative-controlled.

- **Planner (done 2026-09-22).** Section 11 of the Ashen sheet, plus shared
  section 12.
  - **Inline styles:** 29 sites lifted into classes, each with a verbatim
    legacy twin. The sites span the static markup and the `renderPlan()`,
    plan-bonus-profile, `resetPlanOutput()` and
    `injectGearMilestonesIntoPlanner()` templates.
  - **Planner skill tiles** reuse the `[data-skill]` artwork map.
  - **Section 12 (shared):** the item-reference reset (`<button
    class="iw-item-ref">`, which drew as grey UA buttons everywhere) and the
    item/gear sprite hosts with their ready/fallback state rules. The Gear
    tab builds on this.
  - **Also:** the footer links, and the `.plan-empty` / `.gear-empty` /
    `.idb-empty` empty state.
  - **Legacy mode is unchanged:**
    - Planner: 929 elements, with a Smithing 1→60 plan (15 cards, 30 loop
      steps, 8 gear milestones) and every disclaimer forced visible.
    - Calculator: 659 elements.
    - Both diff to 0 at matching state, negative-controlled.
- **Switch hardened (2026-09-22).** Two changes:
  - Inactive sheets go under `media="not all"` instead of `disabled` (see
    CLAUDE.md).
  - Suite L gained a **re-show** check: a selector legacy hides but re-shows
    for the same selector under a media query must be mirrored. The
    rendered check had caught the construction planner's phone pager, but
    only at phone width.
  - Suite L also asserts every same-origin legacy sheet was actually read.
    Both new checks are negative-controlled.

- **Gear, first pass (2026-09-22).** Section 13 of the Ashen sheet. No
  Gear markup was changed: its inline styles resolve through the token
  bridge, so legacy Gear is untouched.
  - **Converted:**
    - Doll: recessed slots and a lit alcove with the crest. The slot states
      stay distinct: bonus is green, empty is dashed, enchanted keeps the
      violet breathe/sheen (own keyframes), and reinforced keeps the steel
      plate and rivets.
    - Stats ledger, enhancement plates, the shopping list, the `.iw-dd`
      dropdown and the Best-in-Slot table.
    - Search and recommendation `<details>` groups.
    - Slot dialog: scrim and forged panel, gem/enchant/upgrade chips, the
      reinforcement states, and the gem tile picker.
  - **Shared, affecting every tab:** the global item tooltip `#iw-tip` and the
    `.jump-pill`.
  - **Village Add-ons (done 2026-09-22):**
    - All 16 inline styles in `render()`, plus the static shell's, are
      lifted into `va-*` classes, each with a verbatim legacy twin.
    - Legacy is unchanged: 247 elements with 3 add-ons installed, 0
      differences, negative-controlled.
    - Ashen: slot plates, a framed building-art socket, green bonus lines, a
      cost ledger and the totals facts.
  - **Found on the way:** suite F (skill boosts) failed for any player with
    Village Add-ons installed ("got 9, expected 7"). Add-ons are a second
    skill-level source and its fixtures assumed none. It now clears and
    restores the add-on plan around its run, as suite H does. Assertions are
    unchanged.
- **Found and fixed on the way:**
  - **Item tooltip always visible in Ashen mode.** It hides with
    opacity/visibility, which no parity check covered. Suite L now pins
    opacity/visibility hides; negative-controlled.
  - **Self-checks corrupted saved data** (both skins, pre-existing). See
    CLAUDE.md. The fix is the storage guard plus suite M; negative-controlled
    (the unguarded gear suite leaks 4 keys).
  - **Recommended Gear printed raw floats** ("+0.6666666666666666% Fire
    Resist"). It now uses the slot tooltip's display rule (Tailoring rounds
    up, whole numbers elsewhere).

- **Work Orders (done 2026-09-22).** Section 14 of the Ashen sheet.
  - **No markup changes.** The only inline styles are the dynamic bar widths
    and two token-coloured dots, so legacy is untouched by construction.
  - **Converted:**
    - Notices: info on a blue rail, the results disclaimer on a warn rail.
    - The "loaded" profile tag, and the view switcher as tabs over a rule.
    - The best-order hero and the comparison table (sticky head and first
      column; the winning row lit brass with a gold rail).
    - The phone card list, and the time and gold breakdowns (plain plates,
      no filigree, since there are many).
    - The rules and data section.
  - **Fixed on the way:** Work Orders said "Profile: profile" (loaded) with
    no import. That exposed a real engine bug: load-time self-checks saved a
    stub profile on every page load. See CLAUDE.md for the shape rule, the
    repair and suite M's assertion, each verified in both directions.
  - **Browser pane:** it stopped painting midway (entire frame black,
    appbar included). The table and phone checks were verified through
    computed styles instead.

- **Jewelry (done 2026-09-22).** Section 15 of the Ashen sheet.
  - **No markup changes:** there are no inline styles in the markup or in the
    renderer, so legacy is untouched by construction.
  - **Converted:**
    - Intro note on a violet (epic) rail and the import card in Cinzel.
    - The three overridable settings: dimmed while they use the profile
      value, live once "Custom" is ticked.
    - Eight summary tallies in Cinzel, the two primary ones brass-edged.
    - Gem cards with a violet head wash, a need-quantity tag and a stat
      ledger.
    - The flavour-italic footnote.
  - **Phone width:** every grid collapses to one column (settings, controls,
    summary at ≤420px, details, stats), with no horizontal scroll.

- **Construction planner (done 2026-09-22).** Section 16 of the Ashen sheet.
  - **A native rewrite of all 175 rules** of `assets/construction-planner.css`.
    Geometry is unchanged: the five plot positions, the sticky village and
    the phone four-stage pager. The materials are Ashen:
    - The scene is a forged niche with a vignette over
      `assets/ashen/village_terrain.webp` (1100px, 240 KB, in place of the
      3 MB PNG, which the legacy path still uses).
    - The selected plot and selected building card are lit brass.
    - Step numbers are wax seals, the primary action is ember, gain/loss
      keep their colours, and the time total is in Cinzel.
  - **No markup or JS changes**, so legacy is untouched by construction.
  - **Caught by suite L's rendered check:** the phone re-show rules had been
    appended after `[data-cv-stage-panel]{display:none}`. At equal
    specificity that showed the slot intro on every stage. They now sit in
    legacy's order. Suite L is green at each of the four stages at phone
    width, with exactly one stage panel visible.

## Lessons (read before converting the next tab)

- **Positional reads of engine markup.** Before wrapping anything, grep for
  `querySelector('span')`, `firstChild`, `children[0]` and `textContent` on
  the element. The Planner read the skill tile's label as "the first span".
  It now reads `[data-ui="skill-text"]`.
- **The `.field label` trap.** A descendant selector reaches nested
  checkbox-row labels. Scope it with `:not(.check-row)`.
- **Same-specificity grids.** When a component rule and a modifier sit at
  equal specificity, the one later in the sheet wins. Qualify the modifier
  (`.check-group.check-grid-2`).
- **Frozen frames in the browser pane.** The pane does not advance animation
  frames while hidden, so computed colours read mid-transition after a skin
  switch, and panes read mid-`ashRise`. Before trusting a colour reading,
  freeze transitions (`body.force-reduce-motion` plus
  `*{transition:none!important}`).
- **Split browser checks.** In the hidden pane a full
  `iwReleaseCandidateSelfCheck()` takes about 27 s, so run it in its own call.
  A combined call exceeds the tool's 45 s limit. Any re-render path, such as
  the Test import, also wipes inline style nudges, so plant a negative
  control as a stylesheet rule.
- **Never `sed` a CSS line that also exists in the legacy sheet.** Many
  Ashen rules are line-for-line copies of legacy ones. A pattern that matches
  both edits legacy too, which has happened twice (`.plainline`,
  `.iw-addon-icon`). Use a script that anchors on the Ashen sheet's offset,
  and re-diff legacy afterwards.
- **Diff under identical conditions.** The pane's emulation can change its
  device-pixel-ratio between runs (borders then read 0.667px), and scroll
  moves every `y`. Capture baseline and working copy back to back, in one
  batch.
- **Parity rules keep legacy's source order.** When two display rules for
  the same element have equal specificity (a re-show against a stage or
  state hide), the later one wins. Copy them in the order legacy has them,
  and run suite L in each state (stage, breakpoint), not just the default.
- **Do not set `display` on parity elements.** `.potion-warn-banner`,
  `.lookup-pending`, `.active-skill-banner`, `.lookup-result`, `.error` and
  the others get their `display` from section 4 only.

## Verification

- A parse gate after every edit (the CLAUDE.md command). The self-check suites
  must stay green.
- Suite L, `iwAshenSkinSelfCheck`, asserts the following:
  - Exactly one sheet family is enabled.
  - `data-skin` matches `iw_skin_v1`.
  - Every `ash` sheet has rules.
  - The switch round-trips without losing `data-theme`.
- Browser check of both modes after every tab, at desktop and phone width.
