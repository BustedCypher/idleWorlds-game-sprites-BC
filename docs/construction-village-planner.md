# Construction & Village Planner

Open **Community Tools → Construction Planner**. Desktop uses a village/details split view; phones use Slot → Building → Materials → Plan. All 34 add-ons use the toolkit's existing recipes, buff descriptors and item sprites.

## Using the planner

1. Choose housing or follow toolkit settings. Enter Construction, Woodcutting and Mining levels before village bonuses; imported base and equipment values are used when available. Explicit overrides remain local to this planner.
2. Record buildings already installed in your game under **Edit current village**. This manual record is separate from the Gear panel's hypothetical add-on selection.
3. Select a village slot, browse or filter buildings, and add a local plan. Replacements show current-to-future bonuses and a refund preview. Future bonuses never grant eligibility for their own build.
4. Enter owned materials. Blank means unknown. Owned Parts reduce crafting first; their ingredients are not charged again. Timber and ore stock is deducted once from the combined crafting and Assembly bill.
5. Select **Whole village plan** to share inventory across planned buildings. Review gathering locations, missing Parts and estimated continuous action time. Copy the material plan if useful.

Housing provides one slot per tier, capped at five. Duplicate types are blocked. Lowering housing retains inactive assignments but excludes them from bonuses and the production bill. Planning and clearing a plan never change the game account.

## Sources and limits

The [official construction guide](https://idleworlds.com/wiki/construction) describes Construction as free for everyone. Recipe and buff data reuse `assemblyInputs` and `buildingBuffs` in `index.html`; timing uses the existing toolkit duration and gathering-yield rules.

Installed buildings and inventory are manual records stored locally under `iwConstructionVillageV1`. Unknown stock or unmet skill requirements suppress the total estimate. Estimates exclude travel, future level-ups and prospective refunds. Destroying a building refunds 25% of its direct Assembly cost; fractional quantities are shown before in-game rounding because the rounding rule is not verified. Refunds are never automatically credited to stock.

## Validation — 2026-09-05

- Planner engine/state and existing sprite tests: **21/21 passed**.
- Inline JavaScript parsing: **21 inline scripts, no errors**. Working-file integrity guard passed.
- Independent implementation review: approved, no actionable findings.
- Browser checks covered real sprites, inventory uncertainty, Training Yard hand-calculated deductions, Runite lower-tier Parts, shared inventory, current/future bonus separation, duplicate prevention, replacement refund, housing downgrade/restore, saved state after reload, and desktop/tablet/mobile layouts.
- The wider Python suite has **one pre-existing failure**: unsafe image writes in the unrelated `tools/rebuild_skill_atlases.py` at lines 241–242. Those files were left unchanged.
- The Developer UI's global **Run engine self-checks** action was attempted, but the in-app browser crashed before returning a report. That global check is unverified; it is not counted as passing.

Changes remain uncommitted in the current checkout.
