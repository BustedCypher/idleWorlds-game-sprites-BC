(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IWConstructionPlannerEngine = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var MAX_TIER = 34;
  var MAX_SLOTS = 5;

  function validTier(value) {
    return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= MAX_TIER;
  }

  function slotTier(value) {
    if (value === null || value === undefined || value === '') return null;
    var tier = Number(value);
    return Number.isInteger(tier) && tier >= 1 && tier <= MAX_TIER ? tier : null;
  }

  function stockValue(inventory, id) {
    if (!inventory || !Object.prototype.hasOwnProperty.call(inventory, id)) return null;
    var value = inventory[id];
    if (value === null || value === undefined || typeof value === 'boolean') return null;
    if (typeof value === 'string' && value.trim() === '') return null;
    var number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : null;
  }

  function positiveNumber(value) {
    var number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : null;
  }

  function addAmount(map, kind, tier, name, amount, provisional) {
    var id = kind + ':' + tier;
    var row = map.get(id);
    if (!row) {
      row = { id: id, kind: kind, tier: tier, name: name || id, required: 0, provisional: false };
      map.set(id, row);
    }
    row.required += amount;
    if (provisional) row.provisional = true;
    return row;
  }

  function finishRows(map, inventory, unknownSet) {
    return Array.from(map.values(), function (source) {
      var owned = stockValue(inventory, source.id);
      if (owned === null) unknownSet.add(source.id);
      var upperBound = Math.max(0, source.required - (owned === null ? 0 : owned));
      return {
        id: source.id,
        kind: source.kind,
        tier: source.tier,
        name: source.name,
        required: source.required,
        owned: owned,
        missing: source.provisional || owned === null ? null : upperBound,
        upperBound: upperBound,
        provisional: !!source.provisional
      };
    });
  }

  function nullTimes() {
    return { woodcutting: null, mining: null, parts: null, assembly: null, total: null };
  }

  function fixedSlots(values) {
    var source = Array.isArray(values) ? values : [];
    var result = [];
    for (var index = 0; index < MAX_SLOTS; index += 1) result.push(slotTier(source[index]));
    return result;
  }

  function duplicateGroups(tiers) {
    var positions = new Map();
    tiers.forEach(function (tier, index) {
      if (tier === null) return;
      if (!positions.has(tier)) positions.set(tier, []);
      positions.get(tier).push(index);
    });
    var groups = [];
    positions.forEach(function (slots, tier) {
      if (slots.length > 1) groups.push({ tier: tier, slots: slots });
    });
    return groups;
  }

  function create(adapter) {
    if (!adapter || typeof adapter.building !== 'function' ||
        typeof adapter.woodName !== 'function' || typeof adapter.oreName !== 'function') {
      throw new TypeError('A construction planner adapter must provide building, woodName and oreName');
    }

    function requirements(tiers, inventory, timing) {
      var selected = Array.isArray(tiers) ? tiers.filter(validTier) : [];
      var assemblyMap = new Map();

      selected.forEach(function (tier) {
        var building = adapter.building(tier);
        if (!building || !Array.isArray(building.inputs)) return;
        building.inputs.forEach(function (input) {
          if (!input || !validTier(input.tier) ||
              (input.key !== 'parts' && input.key !== 'wood' && input.key !== 'ore')) return;
          var quantity = Number(input.qty);
          if (!Number.isFinite(quantity) || quantity <= 0) return;
          addAmount(assemblyMap, input.key, input.tier, input.label, quantity, false);
        });
      });

      var unknownSet = new Set();
      var assemblyRows = finishRows(assemblyMap, inventory, unknownSet);
      var partsRows = assemblyRows.filter(function (row) { return row.kind === 'parts'; });
      var rawMap = new Map();

      assemblyRows.forEach(function (row) {
        if (row.kind === 'wood' || row.kind === 'ore') {
          addAmount(rawMap, row.kind, row.tier, row.name, row.required, false);
          return;
        }
        if (row.kind !== 'parts') return;
        var craftUpperBound = row.missing === null ? row.upperBound : row.missing;
        if (craftUpperBound <= 0) return;
        var provisional = row.missing === null;
        addAmount(rawMap, 'wood', row.tier, adapter.woodName(row.tier), craftUpperBound * 2 * row.tier, provisional);
        addAmount(rawMap, 'ore', row.tier, adapter.oreName(row.tier), craftUpperBound * row.tier, provisional);
      });

      var rawRows = finishRows(rawMap, inventory, unknownSet);
      var completeInventory = unknownSet.size === 0 && rawRows.every(function (row) { return !row.provisional; });
      var craftCount = partsRows.every(function (row) { return row.missing !== null; })
        ? partsRows.reduce(function (sum, row) { return sum + row.missing; }, 0)
        : null;
      var gatherYield = timing ? positiveNumber(timing.gatherYield) : null;

      function actionCount(kind) {
        var relevant = rawRows.filter(function (row) { return row.kind === kind; });
        if (relevant.some(function (row) { return row.missing === null; })) return null;
        if (relevant.length === 0) return 0;
        if (gatherYield === null) return null;
        return relevant.reduce(function (sum, row) {
          return sum + Math.ceil(row.missing / gatherYield);
        }, 0);
      }

      var gatherActions = {
        woodcutting: actionCount('wood'),
        mining: actionCount('ore')
      };
      var woodcuttingSeconds = timing ? positiveNumber(timing.woodcuttingSeconds) : null;
      var miningSeconds = timing ? positiveNumber(timing.miningSeconds) : null;
      var partsSeconds = timing ? positiveNumber(timing.partsSeconds) : null;
      var assemblySeconds = timing ? positiveNumber(timing.assemblySeconds) : null;
      var timingComplete = gatherYield !== null && woodcuttingSeconds !== null && miningSeconds !== null &&
        partsSeconds !== null && assemblySeconds !== null;
      var times = nullTimes();

      if (completeInventory && timingComplete && craftCount !== null &&
          gatherActions.woodcutting !== null && gatherActions.mining !== null) {
        times.woodcutting = gatherActions.woodcutting * woodcuttingSeconds;
        times.mining = gatherActions.mining * miningSeconds;
        times.parts = craftCount * partsSeconds;
        times.assembly = selected.length * assemblySeconds;
        times.total = times.woodcutting + times.mining + times.parts + times.assembly;
      }

      return {
        assemblyRows: assemblyRows,
        partsRows: partsRows,
        rawRows: rawRows,
        completeInventory: completeInventory,
        unknownItems: Array.from(unknownSet),
        craftCount: craftCount,
        gatherActions: gatherActions,
        times: times
      };
    }

    function village(housingTier, installedValues, plannedValues) {
      var parsedCapacity = parseInt(housingTier, 10);
      var capacity = Number.isFinite(parsedCapacity) ? Math.max(0, Math.min(MAX_SLOTS, parsedCapacity)) : 0;
      var installed = fixedSlots(installedValues);
      var planned = fixedSlots(plannedValues);
      var activeInstalled = installed.slice(0, capacity);
      var futureBySlot = activeInstalled.map(function (tier, index) {
        return planned[index] === null ? tier : planned[index];
      });
      var currentGroups = duplicateGroups(activeInstalled);
      var futureGroups = duplicateGroups(futureBySlot);
      var conflicts = currentGroups.map(function (group) {
        return { kind: 'current', tier: group.tier, slots: group.slots.slice() };
      });

      futureGroups.forEach(function (group) {
        var currentMatch = currentGroups.some(function (current) {
          return current.tier === group.tier && current.slots.length === group.slots.length &&
            current.slots.every(function (slot, index) { return slot === group.slots[index]; });
        });
        var involvesPlan = group.slots.some(function (slot) { return planned[slot] !== null; });
        if (!currentMatch || involvesPlan) {
          conflicts.push({ kind: 'planned', tier: group.tier, slots: group.slots.slice() });
        }
      });

      var inactiveSlots = [];
      for (var slot = capacity; slot < MAX_SLOTS; slot += 1) {
        if (installed[slot] !== null || planned[slot] !== null) inactiveSlots.push(slot);
      }

      return {
        capacity: capacity,
        installed: installed,
        planned: planned,
        currentTiers: activeInstalled.filter(function (tier) { return tier !== null; }),
        futureTiers: futureBySlot.filter(function (tier) { return tier !== null; }),
        conflicts: conflicts,
        inactiveSlots: inactiveSlots
      };
    }

    function bonuses(tiers) {
      var stats = {};
      var skills = {};
      var selected = Array.isArray(tiers) ? tiers.filter(validTier) : [];

      function addStat(descriptor) {
        if (!descriptor || typeof descriptor.stat !== 'string') return;
        var value = Number(descriptor.value);
        if (!Number.isFinite(value)) return;
        stats[descriptor.stat] = (stats[descriptor.stat] || 0) + value;
      }

      selected.forEach(function (tier) {
        var building = adapter.building(tier);
        var buffs = building && building.buffs;
        if (!buffs) return;
        addStat(buffs.primary);
        var secondary = Array.isArray(buffs.secondary) ? buffs.secondary : [buffs.secondary];
        secondary.forEach(addStat);
        if (buffs.skill && typeof buffs.skill.skill === 'string') {
          var amount = Number(buffs.skill.amount);
          if (Number.isFinite(amount)) {
            skills[buffs.skill.skill] = (skills[buffs.skill.skill] || 0) + amount;
          }
        }
      });
      return { stats: stats, skills: skills };
    }

    function refund(tier) {
      if (!validTier(tier)) return { rows: [], roundingRequired: false };
      var building = adapter.building(tier);
      var inputs = building && Array.isArray(building.inputs) ? building.inputs : [];
      var rows = inputs.reduce(function (result, input) {
        if (!input || !validTier(input.tier) ||
            (input.key !== 'parts' && input.key !== 'wood' && input.key !== 'ore')) return result;
        var directQuantity = Number(input.qty);
        if (!Number.isFinite(directQuantity) || directQuantity <= 0) return result;
        var quantity = directQuantity * 0.25;
        result.push({
          id: input.key + ':' + input.tier,
          kind: input.key,
          key: input.key,
          tier: input.tier,
          name: input.label || input.key + ':' + input.tier,
          label: input.label || input.key + ':' + input.tier,
          qty: quantity,
          roundingRequired: !Number.isInteger(quantity)
        });
        return result;
      }, []);
      return {
        rows: rows,
        roundingRequired: rows.some(function (row) { return row.roundingRequired; })
      };
    }

    return {
      requirements: requirements,
      village: village,
      bonuses: bonuses,
      refund: refund
    };
  }

  return { create: create };
}));
