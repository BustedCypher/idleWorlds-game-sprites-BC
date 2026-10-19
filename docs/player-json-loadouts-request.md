# player.json loadout fields: request to the IdleWorlds developer

The toolkit's Gear tab can now import `player.json` and put any loadout in it
on the gear planner. As of 2026-10-19, `player.json` says `canUseLoadouts:
true` but does not include the loadouts themselves, so only the worn gear
comes through. These are the fields we need, most important first. The
toolkit already parses item 1 exactly as written below, so nothing has to
change on our side when it ships.

## Status after the 2026-10-19 game patch

The patch shipped `player.loadouts`, and the toolkit reads all 12 of
BustedCypher's loadouts with no changes. Each entry has `id`, `name`,
`sortOrder`, `updatedAt`, `slots`, plus a new `boundSkillKeys` (the skills the
game swaps that loadout in for). All 12 slot keys are always present, and all
144 slot references resolve, including all 82 copy ids.

| # | Request | Status |
|---|---|---|
| 1 | `player.loadouts` | **Done**, as specified. No `isActive` / `activeLoadoutId`; the toolkit finds the worn one by comparing gear instead. |
| 2 | Every referenced copy in `inventory` | **Done** for every copy id. One key-only reference (`enchanted_belt_lv_31` in "Gold Find") names an item no longer owned; the belt has since become Lv. 36. |
| 3 | `variantId` on `itemReinforcements` | Not yet |
| 4 | `variantId` on `itemEnchants` | Not yet |
| 5 | Amulet/belt/trinket `VariantId` fields | **Done** (sent as `null`) |
| 6 | `socketCount` on every socketable item | Partly: added to `itemVariants` rows, not to `inventory[].item` |
| 7 | `socketEffect` on `itemVariants` | **Done** |
| 8 | `combatStats` in player.json | Not yet |

New question for the developer: `itemVariants[].socketCount` is `1` on rings,
cloaks and profession uniques (Prospector's Pick, Jeweler's Chisel), which
cannot take gems, and none of them holds one. It looks like a column default.
Is it meant to be the real socket count? If so, it should be `0` there. Until
that's answered, the toolkit ignores the field and keeps its own socket rules.

## Must have

**1. `player.loadouts`: an array with one entry per saved loadout.**

```json
"loadouts": [
  {
    "id": "cm…",
    "name": "Herbing",
    "sortOrder": 0,
    "isActive": false,
    "updatedAt": "2026-10-19T00:00:00.000Z",
    "slots": {
      "weapon":  { "itemKey": "prospectors_pick",       "variantId": "cmtc2egiln6z8idwakr4p0qek" },
      "shield":  { "itemKey": "prospectors_buckler",    "variantId": null },
      "helmet":  { "itemKey": "regal_silk_hood_plus_4", "variantId": "cmtf2v603ijdu13byfr6f8vjg" },
      "chest":   null,
      "gloves":  null, "legs": null, "boots": null, "cloak": null,
      "ring":    null, "amulet": null, "belt": null, "trinket": null
    }
  }
]
```

- `id`: stable across requests, so re-importing updates the same loadout.
- `name`: the name the player gave it in game.
- `slots`: keyed by the same 12 slot names as `equipmentSlot` (`weapon`,
  `shield`, `helmet`, `chest`, `gloves`, `legs`, `boots`, `cloak`, `ring`,
  `amulet`, `belt`, `trinket`). Use `null` for an empty slot.
- `variantId`: the exact copy, the same id `equippedXVariantId` uses. Without
  it, a player who owns three Stormglass Sword+3s (one plain, two with
  different gems) gets the wrong gems.
- `isActive` (or a `player.activeLoadoutId`): which loadout is on now, if the
  game tracks that.

**2. Every copy a loadout names should appear in `inventory`,** with its `item`
definition and per-copy fields (`socketedGemKey`/`socketEffect`,
`socketedGemKey2`/`socketEffect2`, `enchantTier`/`enchantExpiresAt`,
`cloakUpgrade*`). That includes copies in the bank, if banked gear can be in a
loadout. Today 3 of the 74 `itemVariants` rows have no `inventory` row, so the
toolkit can only show their gem keys, not their effects.

## Should have

**3. `variantId` on each `itemReinforcements` row.** Rows are keyed by
`itemKey` only, so with two copies of `kingssteel_leggings_plus_3` we cannot
tell which one carries the plate. The toolkit already uses `variantId` when it
is present.

**4. `variantId` on each `itemEnchants` row,** for the same reason. (The
`enchantTier` on `inventory` rows is already per copy, which covers most
cases.)

**5. `equippedAmuletVariantId`, `equippedBeltVariantId`,
`equippedTrinketVariantId`.** The other nine slots send these, `null` when
there is no copy id. These three are missing from the payload entirely, not
`null`.

## Nice to have

**6. `socketCount` on every socketable item.** Tailoring pieces send it;
metal-set pieces (for example `kingssteel_chest_plus_3`, which has a gem in
it) do not, so the toolkit has to guess the count.

**7. `socketEffect` / `socketEffect2` on `itemVariants` rows,** not only the
gem key, so effects never have to be looked up from the gem tier.

**8. `combatStats` in `player.json`,** the same aggregate block
`/api/player-profile` has (XP per task, item find and so on). It lets
`player.json` stand in for a full profile import.

**9. Anything else a loadout stores** (title, potions, enchant choice): send it
as extra fields on the loadout entry. The toolkit ignores fields it does not
know, so adding them later breaks nothing.

## Shapes the toolkit also accepts

If item 1's exact shape does not suit the game's data model, any of these
works without a toolkit change:

- the list under `loadouts`, `gearLoadouts`, `equipmentLoadouts` or
  `savedLoadouts`, on `player` or at the top level;
- an object keyed by loadout name instead of an array;
- `slots` as an array of `{ "slot": "weapon", "itemKey": …, "variantId": … }`;
- flat fields on the entry, like the player row: `weaponKey` /
  `weaponVariantId` or `equippedWeaponKey` / `equippedWeaponVariantId`;
- a slot value that is a bare item key string, or a full item object with
  `key`.
