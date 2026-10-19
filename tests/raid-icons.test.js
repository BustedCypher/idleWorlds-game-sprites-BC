const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const api = require('../assets/icon-sprites-v2.js');
const root = path.resolve(__dirname, '..');
const expectedRaidIds = new Set([
  'ashmaws_scale_helm', 'ashmaws_scale_chest', 'tyrants_ember', 'ashmaws_cinderheart_band', 'tyrants_forgehands', 'cinderforged_pendant', 'cindercore_fragment',
  'thessalys_storm_grips', 'thessalys_stormstriders', 'voltaic_sigil', 'stormcallers_band', 'thessalys_tempest_lance', 'stormglass_hourglass', 'charged_core_shard',
  'morwennas_hollow_crown', 'morwennas_hollow_legwraps', 'oracles_locket', 'hollow_seers_band', 'eye_of_the_hollow_oracle', 'hollow_oracles_staff', 'hollow_core_shard',
  'grimjaws_bound_plate', 'grimjaws_bound_greaves', 'grimjaws_bound_gauntlets', 'bulwarks_unbroken_band', 'grimjaws_unbroken_march', 'anchorstone_bulwark', 'anchor_core_shard',
  'skarths_rime_helm', 'skarths_rime_chest', 'skarths_frostheart', 'skarths_hoarfrost_band', 'rimeheart_aegis', 'rimebound_torc', 'glacial_core_shard'
]);
test('all 35 raid uniques resolve through the shipped icon manifest', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const payload = JSON.parse(html.match(/<script[^>]*id="iw-embedded-items"[^>]*>([\s\S]*?)<\/script>/)[1]);
  const items = payload.items.filter(item => expectedRaidIds.has(item.item_id));
  assert.equal(items.length, 35);
  const manifestPath = html.match(/manifestUrl:\s*'\.\/([^']+)'/)[1];
  const manifest = JSON.parse(fs.readFileSync(path.join(root, manifestPath), 'utf8'));
  const resolver = api.createResolver(manifest);
  for (const item of items) {
    const cell = item.category === 'Equipment' ? resolver.gear(item.name).base : resolver.item(item.item_id);
    assert.ok(cell, `missing raid icon: ${item.item_id}`);
    const artwork = JSON.parse(fs.readFileSync(path.join(root, 'raid_artwork_manifest.json'), 'utf8'));
    const record = artwork.items.find(record => record.item_id === item.item_id);
    assert.equal(cell[0], 'raid:' + record.raid, 'raid art must use its own raid atlas');
    assert.match(manifest.chunks[cell[0]].path, /\.\.\/\.\.\/raids\/[^/]+\/atlas\.[a-f0-9]{12}\.png$/);
    assert.ok(fs.existsSync(path.join(root, path.dirname(manifestPath), manifest.chunks[cell[0]].path)));
  }
});
test('Items results, suggestions and full entries render raid artwork hosts', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const functions = [
    ['renderItemCard', '// ITEM TOOLTIP ENGINE'],
    ['renderSuggestionRow', '// renderResultGrid'],
    ['renderResultGrid', '// renderFilters']
  ];
  const nodes = new Map(['idb-grid', 'idb-pagination', 'idb-placeholder'].map(id => [id, {style:{}, innerHTML:''}]));
  const rendering = api.install({document:{documentElement:null, querySelectorAll:()=>[]}}, {manifestUrl:'./manifest.json'});
  const context = vm.createContext({IDB_CATEGORIES:{Equipment:{icon:'🛡️',label:'Equipment'},'Trade Good':{icon:'💰',label:'Trade Good'}}, IDB_STATE:{selectedId:null,activeStat:'all'}, IDB_PAGE_SIZE:20,
    IW_GEAR_SPRITES:rendering.gear,
    IW_ITEM_SPRITES:rendering.items,
    document:{getElementById:id=>nodes.get(id)}, wikiXPFor:()=>null, highlightMatch:name=>name, iwItemRef:item=>item.name});
  const helperStart = html.indexOf('function idbIconMarkup(');
  if (helperStart >= 0) vm.runInContext(html.slice(helperStart, html.indexOf('function renderItemCard(', helperStart)), context);
  for (const [name, next] of functions) {
    const start = html.indexOf(`function ${name}(`);
    const end = html.indexOf(next, start);
    vm.runInContext(html.slice(start, end), context);
  }
  for (const item of [{id:'thessalys_storm_grips', name:"Thessaly's Storm Grips", category:'Equipment'}, {id:'glacial_core_shard',name:'Glacial Core Shard',category:'Trade Good'}]) {
    const attribute = item.category === 'Equipment' ? 'data-iw-gear-sprite' : 'data-iw-item-sprite';
    assert.ok(context.renderItemCard(item).includes(attribute), 'full entry must contain sprite host');
    assert.ok(context.renderSuggestionRow(item, '').includes(attribute), 'suggestion must contain sprite host');
    context.renderResultGrid([{item}], '', 1);
    assert.ok(nodes.get('idb-grid').innerHTML.includes(attribute), 'result card must contain sprite host');
  }
});
test('each raid index contains seven unique artwork records with provenance', () => {
  const ids = new Set();
  for (const raid of ['ashmaw', 'thessaly', 'morwenna', 'grimjaw', 'skarth']) {
    const index = JSON.parse(fs.readFileSync(path.join(root, 'assets/raids', raid, 'index.json'), 'utf8'));
    assert.equal(index.items.length, 7);
    for (const item of index.items) {
      assert.ok(!ids.has(item.item_id)); ids.add(item.item_id);
      assert.match(item.sha256_png, /^[a-f0-9]{64}$/);
      assert.ok(fs.existsSync(path.join(root, item.path)));
      assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root, item.path))).digest('hex'), item.sha256_png);
    }
  }
  assert.equal(ids.size, 35);
  assert.deepEqual(ids, expectedRaidIds);
  const artwork = JSON.parse(fs.readFileSync(path.join(root, 'raid_artwork_manifest.json'), 'utf8'));
  assert.deepEqual(new Set(artwork.items.map(item => item.item_id)), ids);
  assert.equal(new Set(artwork.items.map(item => item.sha256_png)).size, 35);
});

test('raid sprites are absent from shared source atlases', () => {
  const artwork = JSON.parse(fs.readFileSync(path.join(root, 'raid_artwork_manifest.json'), 'utf8'));
  const gear = JSON.parse(fs.readFileSync(path.join(root, 'gear_icons_manifest.json'), 'utf8'));
  const names = new Set(artwork.items.map(item => item.name));
  assert.ok(gear.icons.every(icon => !names.has(icon.name)));
  const itemIndex = fs.readFileSync(path.join(root, 'item_icons_index.csv'), 'utf8');
  for (const id of expectedRaidIds) assert.ok(!itemIndex.includes(id + ','));
  for (const raid of Object.keys(artwork.raids)) {
    const index = JSON.parse(fs.readFileSync(path.join(root, artwork.raids[raid]), 'utf8'));
    const bytes = fs.readFileSync(path.join(root, index.atlas.path));
    assert.ok(bytes.length < 25 * 1024 * 1024);
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), index.atlas.sha256_png);
  }
});

test('equipment and core shard share only their own raid request', async () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const manifestPath = html.match(/manifestUrl:\s*'\.\/([^']+)'/)[1];
  const manifest = JSON.parse(fs.readFileSync(path.join(root, manifestPath), 'utf8'));
  const artwork = JSON.parse(fs.readFileSync(path.join(root, 'raid_artwork_manifest.json'), 'utf8'));
  const resolver = api.createResolver(manifest);
  const requests = [];
  const cache = api.createChunkCache(manifest, manifestPath, {baseUrl:'https://example.test/', loadImage:async url => {requests.push(url); return {};}});
  for (const item of artwork.items) {
    const cell = item.category === 'Equipment' ? resolver.gear(item.name).base : resolver.item(item.item_id);
    await cache.load(cell[0]);
  }
  assert.equal(requests.length, 5);
  for (const url of requests) {
    assert.match(url, /^https:\/\/example\.test\/assets\/raids\/[^/]+\/atlas\.[a-f0-9]{12}\.png$/);
  }
});
