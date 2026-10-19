const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const sprites = require('../assets/icon-sprites-v2.js');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const items = JSON.parse(html.match(/<script[^>]*id="iw-embedded-items"[^>]*>([\s\S]*?)<\/script>/)[1]).items;
const manifestPath = html.match(/manifestUrl:\s*'\.\/([^']+)'/)[1];
const resolver = sprites.createResolver(JSON.parse(fs.readFileSync(path.join(root, manifestPath), 'utf8')));
// Missing data, stale pre-buff XP, a wrong slot, or an absent atlas mapping
// must all fail before the new trinkets can reach Gear and its tooltips.
const trinkets = [
  ['deepvein_lodestone', 'Deepvein Lodestone', 'mining', 24, 61],
  ['emberheart_anvilstone', 'Emberheart Anvilstone', 'smithing', 24, 61],
  ['rimebloom_satchel', 'Rimebloom Satchel', 'herbing', 25, 65],
  ['stormwoven_grimoire', 'Stormwoven Grimoire', 'spellcrafting', 26, 69],
  ['astral_loupe', 'Astral Loupe', 'jewelcrafting', 26, 69],
  ['cinderthread_spindle', 'Cinderthread Spindle', 'tailoring', 28, 72],
  ['rimebark_charm', 'Rimebark Charm', 'woodcutting', 31, 73],
  ['stormset_plumb_line', 'Stormset Plumb Line', 'construction', 36, 76],
  ['hollow_lantern', 'Hollow Lantern', null, 10, null],
];
test('new trinkets carry current stats and resolve to distinct gear atlas cells', () => {
  const cells = new Set();
  for (const [id, name, skill, xp, level] of trinkets) {
    const item = items.find(row => row.item_id === id);
    assert.ok(item, 'missing item: ' + id);
    assert.equal(item.name, name);
    assert.equal(item.subcategory, 'Trinket slot');
    assert.equal(item.xp_per_task, xp);
    if (skill) {
      assert.equal(item.skill_bonus_skill, skill);
      assert.equal(item.skill_bonus_value, 2);
      assert.equal(item.req_level, level);
    }
    const cell = resolver.gear(name).base;
    assert.ok(cell, 'missing artwork: ' + id);
    assert.equal(cell[0], 'gear:trinket');
    cells.add(JSON.stringify(cell));
  }
  assert.equal(cells.size, 9);
});
test('Skeleton Key resolves and all ten skill scrolls reuse the existing scroll sprite', () => {
  assert.ok(items.some(row => row.item_id === 'hollow_skeleton_key'));
  assert.ok(resolver.item('hollow_skeleton_key'));
  const scrollCell = resolver.item('hollow_scroll');
  assert.ok(scrollCell, 'legacy scroll art remains available');
  for (const skill of ['combat', 'mining', 'smithing', 'herbing', 'alchemy', 'jewelcrafting', 'spellcrafting', 'tailoring', 'woodcutting', 'construction']) {
    const id = 'hollow_scroll_' + skill;
    assert.ok(items.some(row => row.item_id === id), 'missing scroll: ' + id);
    assert.deepEqual(resolver.item(id), scrollCell, 'missing shared scroll art: ' + id);
  }
});


function toolkitEngine() {
  const vm = require('node:vm');
  const context = vm.createContext({
    IDB_WIKI_BASE: 'https://idleworlds.com/wiki/items',
    IW_RAID_DROP_SOURCES: {},
    iwRaidforgedSetForName: () => null,
  });
  for (const name of ['idbFromApi', 'iwCompatItemRow', 'iwCanonicalSkillKey',
    'iwResolveSkillBonusDbItem', 'iwSkillBonusFromEquippedItem',
    'iwEquipmentSkillBonusSources', 'iwEquipmentSkillBonus', 'iwEffectText', 'iwParseGearStats']) {
    const start = html.indexOf('function ' + name + '(');
    assert.notEqual(start, -1, 'engine function exists: ' + name);
    vm.runInContext(html.slice(start, html.indexOf('\n}', start) + 2), context);
  }
  const normalized = items.map(row => context.idbFromApi(row));
  context.IDB_STATE = {items: normalized, idMap: new Map(normalized.map(row => [row.id, row]))};
  return context;
}

test('profession trinkets grant their matching +2 skill boost through the real item engine', () => {
  const engine = toolkitEngine();
  for (const [id, name, skill, xp] of trinkets.slice(0, 8)) {
    const profile = {equipped: {trinket: {id, name}}};
    assert.equal(engine.iwEquipmentSkillBonus(skill, profile), 2, name);
    assert.equal(engine.iwEquipmentSkillBonus('alchemy', profile), 0, name + ' does not boost Alchemy');
    const normalized = engine.IDB_STATE.idMap.get(id);
    const compact = engine.iwCompatItemRow(normalized);
    assert.equal(engine.iwParseGearStats(compact).xpPerTask, xp, name + ' planner XP');
    assert.equal(normalized.atk, undefined, name + ' has no phantom ATK');
  }
  const lodestone = engine.iwParseGearStats(engine.IDB_STATE.idMap.get('deepvein_lodestone'));
  assert.equal(lodestone.gather, 10);
  assert.equal(lodestone.fire, 6);
  const lantern = engine.iwParseGearStats(engine.IDB_STATE.idMap.get('hollow_lantern'));
  assert.equal(lantern.itemFind, 6);
  assert.equal(lantern.goldFind, 6);
  assert.equal(lantern.xpPerTask, 10);
});
