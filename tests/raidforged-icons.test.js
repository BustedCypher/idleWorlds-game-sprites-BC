const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const api = require('../assets/icon-sprites-v2.js');
const root = path.resolve(__dirname, '..');
const sets = ['cinderforged', 'stormforged', 'hollowforged', 'anchorforged'];
const slots = ['blade', 'bulwark', 'helm', 'breastplate', 'gauntlets', 'greaves', 'sabatons'];
const other = ['welcome_back_xp_potion', 'premium_token', 'hollow_candy', 'hollow_scroll'];
const expected = new Set([...sets.flatMap(set => slots.map(slot => set+'_'+slot)), ...other]);
function shipped() {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const manifestPath = html.match(/manifestUrl:\s*'\.\/([^']+)'/)[1];
  const manifest = JSON.parse(fs.readFileSync(path.join(root, manifestPath), 'utf8'));
  return {html, manifest, manifestPath, resolver:api.createResolver(manifest)};
}
test('32 new icons resolve through five separate expansion atlases', () => {
  const {resolver, manifest, manifestPath} = shipped();
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const items = JSON.parse(html.match(/<script[^>]*id="iw-embedded-items"[^>]*>([\s\S]*?)<\/script>/)[1]).items;
  const groups = new Set();
  for (const id of expected) {
    const item = items.find(item => item.item_id === id);
    assert.ok(item, id);
    const cell = item.category === 'Equipment' ? resolver.gear(item.name).base : resolver.item(id);
    assert.ok(cell, 'missing art: '+id);
    assert.match(cell[0], /^(raidforged:|expansion:)/);
    groups.add(cell[0]);
    assert.ok(fs.existsSync(path.resolve(root, path.dirname(manifestPath), manifest.chunks[cell[0]].path)));
  }
  assert.equal(groups.size, 5);
});
test('expansion manifests cover every item and verify atlas and sprite hashes', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'raidforged_artwork_manifest.json'), 'utf8'));
  assert.deepEqual(new Set(manifest.items.map(item => item.item_id)), expected);
  const shared = JSON.parse(fs.readFileSync(path.join(root, 'gear_icons_manifest.json'), 'utf8'));
  const index = fs.readFileSync(path.join(root, 'item_icons_index.csv'), 'utf8');
  for (const item of manifest.items) {
    assert.ok(!shared.icons.some(icon => icon.name === item.name));
    assert.ok(!index.includes(item.item_id+','));
    const bytes = fs.readFileSync(path.join(root, item.path));
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), item.sha256_png);
  }
  for (const [key, atlas] of Object.entries(manifest.atlases)) {
    const bytes = fs.readFileSync(path.join(root, atlas.path));
    assert.ok(bytes.length < 25*1024*1024, key);
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), atlas.sha256_png);
    const index = JSON.parse(fs.readFileSync(path.join(root, manifest.indexes[key]), 'utf8'));
    assert.equal(index.items.length, key.startsWith('raidforged:') ? 7 : 4);
    assert.equal(index.atlas.path, atlas.path);
  }
});
test('the toolkit Items needing art worklist becomes empty', async () => {
  const {html, resolver} = shipped();
  const items = JSON.parse(html.match(/<script[^>]*id="iw-embedded-items"[^>]*>([\s\S]*?)<\/script>/)[1]).items;
  const gear = {resolve:resolver.gear, splitItemName:api.splitGearName};
  const other = {resolve:resolver.item, load:async()=>{}};
  const context = vm.createContext({window:{IW_GEAR_SPRITES:gear,IW_ITEM_SPRITES:other},
    IW_GEAR_SPRITES:gear,IW_ITEM_SPRITES:other,iwArtItems:()=>items.map(item=>({...item,id:item.item_id})),iwArtBrief:()=>''});
  const start = html.indexOf('window.iwItemsNeedingArt = function');
  vm.runInContext(html.slice(start, html.indexOf('function iwArtNeededCsv', start)), context);
  assert.equal((await context.window.iwItemsNeedingArt()).length, 0);
});
