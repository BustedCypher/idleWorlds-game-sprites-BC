'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('index.html', 'utf8');
const ashenStart = html.indexOf('<style data-iw-sheet="ashen"');
const ashenEnd = html.indexOf('</style>', ashenStart);
const ashenCss = html.slice(ashenStart, ashenEnd);
const rendererStart = html.indexOf('function renderInfoPanels');
const rendererEnd = html.indexOf('window.iwRenderInfoPanels', rendererStart);
const renderer = html.slice(rendererStart, rendererEnd);

test('Ashen achievement hero gives the description a full second row', () => {
  assert.match(ashenCss, /\.iwp-ach-hero\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*auto\s+minmax\(0,\s*1fr\)/s);
  assert.match(ashenCss, /\.iwp-ach-medallion\s*\{[^}]*grid-row:\s*1\s*\/\s*span\s+2/s);
  assert.match(ashenCss, /\.iwp-ach-pct\s*\{[^}]*grid-column:\s*2/s);
  assert.match(ashenCss, /\.iwp-ach-sub\s*\{[^}]*grid-column:\s*2/s);
});

test('achievement disclosure is labelled Achievement List', () => {
  assert.match(renderer, /class="iwp-ach-count">Achievement List<\/span>/);
  assert.doesNotMatch(renderer, /feat[^<]*of strength/i);
});
