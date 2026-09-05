'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const engineModule = require('../assets/construction-planner-engine.js');

const BUILDINGS = {
  1: {
    tier: 1,
    name: 'Training Yard',
    inputs: [
      { key: 'parts', tier: 1, qty: 200, label: 'Copper Building Parts' },
      { key: 'wood', tier: 1, qty: 100, label: 'Greenwake Timber' },
      { key: 'ore', tier: 1, qty: 50, label: 'Copper Ore' }
    ],
    buffs: {
      primary: { stat: 'atk', value: 1 },
      secondary: [{ stat: 'doubleGather', value: 2 }, { stat: 'xp', value: 3 }],
      skill: { skill: 'mining', amount: 1 }
    }
  },
  2: {
    tier: 2,
    name: 'Ironfang Palisade',
    inputs: [
      { key: 'parts', tier: 2, qty: 10, label: 'Iron Building Parts' },
      { key: 'parts', tier: 1, qty: 4, label: 'Copper Building Parts' },
      { key: 'wood', tier: 2, qty: 5, label: 'Ironbark' },
      { key: 'ore', tier: 2, qty: 7, label: 'Iron Ore' }
    ],
    buffs: {
      primary: { stat: 'def', value: 2 },
      secondary: [{ stat: 'atk', value: 1 }, { stat: 'xp', value: 2 }],
      skill: { skill: 'smithing', amount: 1 }
    }
  },
  3: {
    tier: 3,
    name: 'Silverroot Infirmary',
    inputs: [
      { key: 'parts', tier: 3, qty: 10, label: 'Silver Building Parts' },
      { key: 'parts', tier: 1, qty: 6, label: 'Copper Building Parts' },
      { key: 'wood', tier: 3, qty: 8, label: 'Silverwood' },
      { key: 'ore', tier: 3, qty: 9, label: 'Silver Ore' }
    ],
    buffs: {
      primary: { stat: 'atk', value: 4 },
      secondary: [{ stat: 'def', value: 1 }, { stat: 'xp', value: 2 }],
      skill: { skill: 'mining', amount: 2 }
    }
  }
};

const WOODS = { 1: 'Greenwake Timber', 2: 'Ironbark', 3: 'Silverwood' };
const ORES = { 1: 'Copper Ore', 2: 'Iron Ore', 3: 'Silver Ore' };
const planner = engineModule.create({
  building(tier) { return BUILDINGS[tier]; },
  woodName(tier) { return WOODS[tier]; },
  oreName(tier) { return ORES[tier]; }
});

function byId(rows, id) {
  return rows.find(row => row.id === id);
}

const VALID_TIMING = {
  woodcuttingSeconds: 10,
  miningSeconds: 12,
  partsSeconds: 20,
  assemblySeconds: 180,
  gatherYield: 5
};

test('Training Yard expands only missing Parts into raw requirements', () => {
  const result = planner.requirements([1], {
    'parts:1': 50,
    'wood:1': 100,
    'ore:1': 25
  }, VALID_TIMING);

  assert.deepEqual(byId(result.partsRows, 'parts:1'), {
    id: 'parts:1', kind: 'parts', tier: 1, name: 'Copper Building Parts',
    required: 200, owned: 50, missing: 150, upperBound: 150, provisional: false
  });
  assert.deepEqual(byId(result.rawRows, 'wood:1'), {
    id: 'wood:1', kind: 'wood', tier: 1, name: 'Greenwake Timber',
    required: 400, owned: 100, missing: 300, upperBound: 300, provisional: false
  });
  assert.deepEqual(byId(result.rawRows, 'ore:1'), {
    id: 'ore:1', kind: 'ore', tier: 1, name: 'Copper Ore',
    required: 200, owned: 25, missing: 175, upperBound: 175, provisional: false
  });
  assert.equal(byId(result.assemblyRows, 'wood:1').missing, 0);
  assert.equal(result.completeInventory, true);
  assert.deepEqual(result.unknownItems, []);
  assert.equal(result.craftCount, 150);
  assert.deepEqual(result.gatherActions, { woodcutting: 60, mining: 35 });
  assert.deepEqual(result.times, {
    woodcutting: 600, mining: 420, parts: 3000, assembly: 180, total: 4200
  });
});

test('zero stock is known while blank, negative and NaN stock are unknown', () => {
  const knownZero = planner.requirements([1], {
    'parts:1': 0, 'wood:1': 0, 'ore:1': 0
  }, VALID_TIMING);
  assert.equal(byId(knownZero.partsRows, 'parts:1').owned, 0);
  assert.equal(byId(knownZero.partsRows, 'parts:1').missing, 200);
  assert.equal(knownZero.completeInventory, true);

  for (const bad of ['', '   ', -1, NaN]) {
    const inventory = { 'parts:1': bad, 'wood:1': 0, 'ore:1': 0 };
    const result = planner.requirements([1], inventory, VALID_TIMING);
    const parts = byId(result.partsRows, 'parts:1');
    assert.equal(parts.owned, null);
    assert.equal(parts.missing, null);
    assert.equal(parts.upperBound, 200);
    assert.equal(byId(result.rawRows, 'wood:1').provisional, true);
    assert.equal(byId(result.rawRows, 'wood:1').missing, null);
    assert.equal(result.completeInventory, false);
    assert.deepEqual(result.unknownItems, ['parts:1']);
    assert.equal(result.craftCount, null);
    assert.deepEqual(result.gatherActions, { woodcutting: null, mining: null });
    assert.deepEqual(result.times, {
      woodcutting: null, mining: null, parts: null, assembly: null, total: null
    });
  }
});

test('unknown raw stock reports an upper bound without treating blank as zero', () => {
  const result = planner.requirements([1], {
    'parts:1': 200, 'wood:1': '', 'ore:1': 50
  }, VALID_TIMING);
  const wood = byId(result.rawRows, 'wood:1');
  assert.equal(wood.required, 100);
  assert.equal(wood.owned, null);
  assert.equal(wood.missing, null);
  assert.equal(wood.upperBound, 100);
  assert.equal(wood.provisional, false);
  assert.deepEqual(result.unknownItems, ['wood:1']);
  assert.deepEqual(result.gatherActions, { woodcutting: null, mining: 0 });
});

test('lower-tier Parts share stock across buildings and use their own tier recipe', () => {
  const result = planner.requirements([2, 3], {
    'parts:1': 5, 'parts:2': 0, 'parts:3': 0,
    'wood:1': 0, 'ore:1': 0,
    'wood:2': 0, 'ore:2': 0,
    'wood:3': 0, 'ore:3': 0
  }, VALID_TIMING);

  assert.equal(byId(result.partsRows, 'parts:1').required, 10);
  assert.equal(byId(result.partsRows, 'parts:1').missing, 5);
  assert.deepEqual(
    result.rawRows.map(row => [row.id, row.required]),
    [
      ['wood:2', 45], ['ore:2', 27],
      ['wood:1', 10], ['ore:1', 5],
      ['wood:3', 68], ['ore:3', 39]
    ]
  );
  assert.equal(result.craftCount, 25);
});

test('owned Parts are not charged again as raw ingredients', () => {
  const result = planner.requirements([1], {
    'parts:1': 200, 'wood:1': 100, 'ore:1': 50
  }, VALID_TIMING);
  assert.equal(byId(result.rawRows, 'wood:1').required, 100);
  assert.equal(byId(result.rawRows, 'ore:1').required, 50);
  assert.equal(result.craftCount, 0);
  assert.deepEqual(result.gatherActions, { woodcutting: 0, mining: 0 });
});

test('invalid timing nulls all time estimates and empty valid plans cost zero time', () => {
  const inventory = { 'parts:1': 200, 'wood:1': 100, 'ore:1': 50 };
  for (const timing of [undefined, {}, { ...VALID_TIMING, partsSeconds: 0 }, { ...VALID_TIMING, gatherYield: NaN }]) {
    assert.deepEqual(planner.requirements([1], inventory, timing).times, {
      woodcutting: null, mining: null, parts: null, assembly: null, total: null
    });
  }
  assert.deepEqual(planner.requirements([], {}, VALID_TIMING), {
    assemblyRows: [], partsRows: [], rawRows: [], completeInventory: true,
    unknownItems: [], craftCount: 0, gatherActions: { woodcutting: 0, mining: 0 },
    times: { woodcutting: 0, mining: 0, parts: 0, assembly: 0, total: 0 }
  });
});

test('requirements validates tiers and does not mutate caller data', () => {
  const tiers = [1, 0, 35, 1.5, '2'];
  const inventory = { 'parts:1': 200, 'wood:1': 100, 'ore:1': 50 };
  const timing = { ...VALID_TIMING };
  const before = JSON.stringify({ tiers, inventory, timing });
  const result = planner.requirements(tiers, inventory, timing);
  assert.equal(result.times.assembly, 180);
  assert.equal(JSON.stringify({ tiers, inventory, timing }), before);
});

test('village preserves five slots, applies housing capacity and retains inactive assignments', () => {
  assert.deepEqual(
    planner.village(2, [1, 2, null, 3, 4], [null, 3, null, null, 2]),
    {
      capacity: 2,
      installed: [1, 2, null, 3, 4],
      planned: [null, 3, null, null, 2],
      currentTiers: [1, 2],
      futureTiers: [1, 3],
      conflicts: [],
      inactiveSlots: [3, 4]
    }
  );
  const none = planner.village('None', [1], [null, 2]);
  assert.equal(none.capacity, 0);
  assert.deepEqual(none.installed, [1, null, null, null, null]);
  assert.deepEqual(none.currentTiers, []);
  assert.deepEqual(none.futureTiers, []);
  assert.deepEqual(none.inactiveSlots, [0, 1]);
});

test('village reports current and planned duplicate buildings without rewriting slots', () => {
  const current = planner.village(5, [1, 1, null, null, null], []);
  assert.deepEqual(current.conflicts, [{ kind: 'current', tier: 1, slots: [0, 1] }]);
  assert.deepEqual(current.installed, [1, 1, null, null, null]);

  const planned = planner.village(2, [1, 2], [2, null]);
  assert.deepEqual(planned.futureTiers, [2, 2]);
  assert.deepEqual(planned.conflicts, [{ kind: 'planned', tier: 2, slots: [0, 1] }]);
  assert.deepEqual(planned.planned, [2, null, null, null, null]);
});

test('bonuses aggregate stat and skill descriptors supplied by the adapter', () => {
  assert.deepEqual(planner.bonuses([1, 3]), {
    stats: { atk: 5, doubleGather: 2, xp: 5, def: 1 },
    skills: { mining: 3 }
  });
  assert.deepEqual(planner.bonuses([]), { stats: {}, skills: {} });
});

test('refund uses 25 percent of direct Assembly rows and flags fractional quantities', () => {
  const result = planner.refund(1);
  assert.deepEqual(result.rows.map(row => [row.id, row.qty, row.roundingRequired]), [
    ['parts:1', 50, false],
    ['wood:1', 25, false],
    ['ore:1', 12.5, true]
  ]);
  assert.equal(result.roundingRequired, true);
});
