# Skill Tools and Open Homestead Design

**Date:** 2026-09-05

## Goal

Move the Construction Planner out of Community Tools, group it with the Jewelry Planner under a new Skill Tools navigation section, and make the village feel like the player's property. The village panel becomes an open field dominated by the player's housing, while selected add-ons remain smaller interactive plots. The bonus summary immediately reflects installed, planned, and currently previewed buildings.

## Navigation

The desktop and mobile navigation gain an expandable **Skill Tools** group containing:

- Construction Planner
- Jewelry Planner

The Work Order Calculator becomes a normal standalone tool tab. The old Community Tools group is removed because it would contain only one item. Existing tab identifiers and pane identifiers remain unchanged so saved navigation and entry hooks continue to work.

Opening either Construction Planner or Jewelry Planner marks Skill Tools active and expanded. Work Order Calculator no longer marks a parent group active. Desktop and mobile navigation use the same grouping and labels.

## Open Homestead Scene

The current village panel becomes a full-frame field. A large housing sprite is centered in the scene and visually outweighs the add-on sprites by roughly three to one. Five building plots surround it in a natural arrangement and remain the interactive slot controls.

There are five new transparent housing sprites with a consistent camera angle, scale, lighting, and IdleWorlds-style fantasy rendering:

1. Camp — tent, campfire, bedrolls, and supply crates
2. Cottage — compact timber cottage with a simple garden
3. Villa — larger stone-and-timber residence with landscaping
4. Manor — fortified estate with wings and formal grounds
5. Citadel — imposing walled residence with towers

The field background is built in CSS and reused across tiers. It includes restrained terrain, paths, and depth treatment without competing with the sprites. Housing None shows an empty homestead foundation rather than a dwelling.

Installed, planned, previewed, available, and locked plots keep distinct text labels and non-color cues. The add-on sprites remain real buttons with accessible names. Housing art and environmental scenery are decorative, while the housing name and tier remain visible text.

On desktop and tablet, the full scene fills the village panel. On mobile, the Slot stage shows the full scene. Building, Materials, and Plan stages show a compact housing banner with the housing sprite, housing name, tier, selected slot, and selected building state.

## Equipped and Previewed Bonuses

Rename **Current Installed Bonuses** to **Equipped & Previewed Bonuses**.

The planner derives a display occupant for each slot in this order:

1. Start with the manually recorded installed building.
2. Replace it with the saved planned building when one exists.
3. For the selected slot, replace it with the currently previewed catalogue building.

The section shows one compact row per displayed building. Each row includes the building name, state label, primary buff, both secondary buffs, and flat skill-level bonus. The preview row has a visible Preview label. A combined active-village total follows the rows.

Preview selection changes the section immediately and does not require Add to village plan. Previewing a replacement removes the displaced building from the displayed total. A building type can contribute only once. Existing duplicate prevention remains active for installed and planned assignments.

A preview in a locked slot still appears as an individual row with **Requires housing upgrade**, satisfying the requirement to show every previewed building. It does not contribute to the combined active-village total. Likewise, saved assignments beyond the current housing capacity remain retained but inactive.

Preview state does not enter the whole-plan material bill until the player clicks **Add to village plan**. The selected-building bill continues to show the currently previewed building, as it does today. Future and previewed skill bonuses never grant eligibility for their own construction or gathering requirements.

## Data Flow

The pure planner engine remains authoritative for capacity, duplicate detection, building bonuses, resource bills, and refunds. The UI module adds a small display-lineup derivation over the existing `installed`, `planned`, `selectedSlot`, and `targetTier` state.

Two bonus concepts remain separate:

- **Confirmed current bonuses** come only from active manually recorded installed buildings. These may affect effective skill levels because the player already owns them.
- **Displayed bonuses** come from the installed/planned/preview lineup and are used only for the Equipped & Previewed Bonuses interface and comparison display.

This preserves the current protection against circular eligibility. Planned or previewed bonuses do not alter recipe gates, production duration, or resource requirements.

## Assets

Housing sprites live under `assets/housing/` with stable descriptive filenames. A small manifest or direct tier-to-path mapping associates housing tiers 1–5 with the sprites. The UI supplies a visible fallback using the existing housing SVG when an image fails to load.

The generated images are cropped consistently, use transparent backgrounds, and reserve enough surrounding space for shadows without producing mismatched visual sizes. They are optimized for browser delivery without changing the existing add-on sprite service.

## Error Handling and Persistence

Missing housing artwork falls back to the existing SVG and never prevents planner initialization. Existing local planner state remains compatible; no storage migration is needed because the design uses the current housing, installed, planned, selected-slot, and target-tier fields.

Invalid or duplicate saved assignments retain the current defensive behavior: they are surfaced and excluded where required rather than silently rewritten. Preview state remains local and reversible.

## Validation

Automated checks cover:

- Skill Tools grouping and removal of Construction/Jewelry from Community Tools
- Work Order as a standalone tab
- Display-lineup precedence from installed to planned to previewed
- Per-building buff rows and combined totals
- Preview replacement without changing saved plans or material scope
- Locked-slot preview visibility and exclusion from active totals
- Duplicate contribution prevention
- Housing sprite mapping and SVG fallback
- Existing stock, Parts expansion, refund, and persistence behavior

Browser checks cover desktop, tablet, and mobile navigation; all five housing tiers; real sprite loading and fallback; plot accessibility; mobile stage transitions; and bonus updates while browsing buildings.

## Delivery

The implementation will be committed and pushed to `main` after checks pass so the existing live host can deploy it. Unrelated untracked workspace files remain excluded.
