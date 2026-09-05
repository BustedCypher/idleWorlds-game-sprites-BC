'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {normalizeState, resolveSetup} = require('../assets/construction-planner.js');

test('malformed saved state cannot inject invalid tiers or turn blank stock into owned zero', () => {
  const s = normalizeState({housing:9,installed:[1,1,90,'3','bad',5],planned:[34,-2],stock:{'parts:1':'','wood:1':0,'ore:2':-1,'ore:3':'25','wood:34':Infinity,'bad:1':7},levels:{construction:'',woodcutting:29,mining:-4},selectedSlot:99,targetTier:300});
  assert.equal(s.housing,null);
  assert.deepEqual(s.installed,[1,1,null,3,null]);
  assert.deepEqual(s.planned,[34,null,null,null,null]);
  assert.deepEqual(s.stock,{'wood:1':0,'ore:3':25});
  assert.deepEqual(s.levels,{construction:null,woodcutting:29,mining:null});
  assert.equal(s.selectedSlot,0);
  assert.equal(s.targetTier,1);
});

test('current village bonuses affect effective levels but targets never do', () => {
  const s=normalizeState({installed:[9,null,null,null,null],planned:[18,null,null,null,null]});
  const context={housing:1,levels:{construction:28,woodcutting:25,mining:null},gatherYield:2.5};
  const setup=resolveSetup(s,context,{construction:1,mining:1});
  assert.equal(setup.levels.construction,29);
  assert.equal(setup.levels.woodcutting,25);
  assert.equal(setup.levels.mining,null);
  assert.equal(setup.gatherYield,2.5);
  assert.equal(setup.housing,1);
  assert.equal(context.levels.construction,28);
});

test('manual overrides survive a new profile while unknown values follow the toolkit', () => {
  const s=normalizeState({housing:5,levels:{construction:50},gatherYield:1.75});
  const setup=resolveSetup(s,{housing:2,levels:{construction:10,woodcutting:37,mining:41},gatherYield:3},{construction:2});
  assert.deepEqual(setup.levels,{construction:52,woodcutting:37,mining:41});
  assert.equal(setup.housing,5);
  assert.equal(setup.gatherYield,1.75);
});
