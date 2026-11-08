# Raid simulator

Chooses the Raids tab's suggested rosters (`RAID GUIDES` in `index.html`,
suite V). Node, no dependencies. Not deployed: `tools/` is in `.assetsignore`.

```bash
node tools/raid-sim/search.js                 # every boss: all 120 legal rosters, then the top 8 on the wide grid
node tools/raid-sim/search.js grimjaw,skarth  # some bosses
node tools/raid-sim/sens.js grimjaw combat,combat,spellcrafting,jewelcrafting,smithing,alchemy,mining,construction
                                              # one roster: clean-kill % by raider HP x Attack damage
```

`search.js` prints each boss's top rosters with their clean-kill rate (boss
dead, nobody dead), win rate, worst scenario and average kill time. Set
`RAID_SIM_JSON=<path>` to also write the results as JSON. A full run takes
about 3 minutes.

## Where the numbers come from

`raid-sim.js` marks every constant:

- **GAME**: the game's client bundle, read 2026-11-08: boss HP and ATK,
  `aoeDamage`, `aoeMaxHpFraction`, `poisonTickDamage`, `requiredResist`,
  `poisonSpreads`, `enrageStartMs` (210 s when a boss sets none),
  `tankMarkMs`, the Skarth tomb, charge and stagger fields, and each boss's
  `abilityRotation`. Also the 15 s cadence, the 10 s action bar, the
  enrage ramp `1 + (t - start) / 60 s`, Regrowth's 3 s tick, and every lend's
  formula of the lender's level, evaluated at 70.
- **ASSUME**: things the server keeps. The heavy hit on a taunting tank,
  raider max HP, Attack damage and Rend's tick rate are swept (see `grid()`
  in `search.js`). Resist cuts damage in a straight line up to the 50% cap.
  A curse halves all healing for 15 s. Fortify does not cut poison, and its
  DEF removes 30% of the heavy hit.

To refresh the GAME numbers after a balance patch, search the game's
`_next/static/chunks/*.js` for `abilityRotation` (the boss table) and
`buffName:"Rend"` (the lend formulas). Then re-run `search.js` and update
each guide's `roster`, `bench` and `sim` in `index.html`. Suite V pins them.
