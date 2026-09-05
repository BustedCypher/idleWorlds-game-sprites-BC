'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('index.html','utf8');

function section(id) {
  const start=html.indexOf(`id="${id}"`);
  assert.notEqual(start,-1,`${id} exists`);
  const end=html.indexOf('</div>',start);
  return html.slice(start,end);
}

test('desktop and mobile expose a Skill Tools group', () => {
  assert.equal((html.match(/class="tab-btn skill-tools-toggle"/g)||[]).length,2);
  assert.match(html,/aria-label="Skill Tools"/);
  for (const id of ['skill-tools-desktop','skill-tools-mobile']) {
    const group=section(id);
    assert.match(group,/data-tab="construction-village"/);
    assert.match(group,/data-tab="jewelry"/);
    assert.doesNotMatch(group,/data-tab="work-order"/);
  }
});

test('Work Order remains a standalone desktop and mobile tool', () => {
  assert.equal((html.match(/class="tab-btn" data-tab="work-order"/g)||[]).length,2);
});

test('tab switching marks only Construction and Jewelry as Skill Tools', () => {
  assert.match(html,/const isSkillTool = name === 'construction-village' \|\| name === 'jewelry';/);
  assert.match(html,/querySelectorAll\('\.skill-tools-toggle'\)/);
  assert.doesNotMatch(html,/const isCommunityTool/);
});
