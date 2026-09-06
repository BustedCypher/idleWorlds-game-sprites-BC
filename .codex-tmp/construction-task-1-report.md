# Construction planner engine report

## API notes

- `IWConstructionPlannerEngine.create(adapter)` exports through UMD/CommonJS and returns `requirements`, `village`, `bonuses`, and `refund`.
- `requirements` validates integer building tiers 1–34, aggregates shared direct inputs, expands only missing Parts using the Parts tier recipe, and distinguishes known zero stock from unknown blank/negative/non-finite stock.
- Unknown Parts make dependent raw rows provisional. Counts that cannot be known are `null`; all time fields are `null` unless relevant inventory and every positive timing/yield input are complete. A valid empty selection returns zero counts and times.
- `village` preserves fixed five-slot `installed` and `planned` arrays. Confirmed with the parent task: `currentTiers` and `futureTiers` are compact active-tier lists; planned values replace installed values only when non-null.
- `refund` returns `{rows, roundingRequired}`. Rows preserve direct Assembly identity/labels, return the 25% quantity, and include their own `roundingRequired` flag.

## Test evidence

- RED: `node --test tests/construction-planner.test.js` exited 1 with `MODULE_NOT_FOUND` for `../assets/construction-planner-engine.js` before production code existed.
- GREEN: the same focused command passed 11/11 tests after implementation.
- Parse: `node --check assets/construction-planner-engine.js` exited 0.
- Whitespace: `git diff --check -- assets/construction-planner-engine.js tests/construction-planner.test.js` exited 0.

The focused tests cover the Training Yard fixture, known zero and unknown stock variants, lower-tier/shared Parts stock, owned Parts, input immutability, invalid timing, empty selections, housing capacity and None, inactive slots, current/planned duplicates, bonus aggregation, and direct-cost refund rounding.

## Concerns

- None in the pure-model contract. The repository's unrelated Python baseline failure in untracked `tools/rebuild_skill_atlases.py` was reported by the parent task and was intentionally left untouched.
