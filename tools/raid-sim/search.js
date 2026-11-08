'use strict';
// Exhaustive roster search per boss: every legal 8-slot roster (1 or 2 tanks,
// every other lend at most once), scored by the share of fights won with
// nobody dying ("clean kill"), coarse first, then the top rosters on a wider grid.
const { simulate, BOSSES } = require('./raid-sim.js');
const OTHERS = ['spellcrafting','herbing','jewelcrafting','smithing','alchemy','mining','construction','woodcutting','tailoring'];
function combos(arr, k, start = 0, cur = [], out = []) { if (cur.length === k) { out.push(cur.slice()); return out; } for (let i = start; i < arr.length; i++) { cur.push(arr[i]); combos(arr, k, i + 1, cur, out); cur.pop(); } return out; }
const ROSTERS = [...combos(OTHERS, 7).map(c => ['combat', ...c]), ...combos(OTHERS, 6).map(c => ['combat', 'combat', ...c])];
const SHORT = { combat:'Tank', spellcrafting:'Mend', herbing:'Regrowth', jewelcrafting:'Ward', smithing:'Fortify', alchemy:'Cleanse', mining:'WarCry', construction:'Reinforce', woodcutting:'Rend', tailoring:'Veil' };
const label = r => r.map(x => SHORT[x]).join(' ');
function grid(boss, wide) {
  const B = BOSSES[boss], target = Math.max(0, B.req - 36), out = [];
  for (const hp of wide ? [450, 525, 650] : [450, 525])
    for (const gearResist of [target, Math.max(0, target - 8)])
      for (const crush of wide ? [300, 450, 600] : [450, 600])
        for (const atkDmg of wide ? [200, 275, 350] : [200, 300])
          for (const rendTick of [3000, 10000])
            out.push({ boss, hp, tankHp: 2 * hp, gearResist, crush, atkDmg, rendTick, fortCrush: 0.3 });
  return out;
}
function score(roster, cases, runs) {
  let clean = 0, win = 0, total = 0, worst = 1, worstCase = null, kill = 0, kills = 0; const causes = {};
  for (const c of cases) {
    let ok = 0;
    for (let s = 1; s <= runs; s++) {
      const r = simulate({ ...c, roster, seed: s * 2654435761 + c.crush * 7 + c.hp + c.atkDmg, first: 12000 + (s % 7) * 1000 });
      if (r.clean) ok++; if (r.win) { win++; kill += r.killAt; kills++; }
      if (r.deaths.length) { const k = r.deaths[0].cause; causes[k] = (causes[k] || 0) + 1; }
      total++;
    }
    clean += ok; if (ok / runs < worst) { worst = ok / runs; worstCase = c; }
  }
  return { clean: clean / total, win: win / total, worst, worstCase, killS: kills ? kill / kills / 1000 : null, causes };
}
const bosses = process.argv[2] ? process.argv[2].split(',') : Object.keys(BOSSES);
const out = {};
for (const boss of bosses) {
  const t0 = Date.now();
  const coarse = ROSTERS.map(r => ({ r, ...score(r, grid(boss, false), 20) })).sort((a, b) => b.clean - a.clean || b.worst - a.worst);
  const top = coarse.slice(0, 8).map(x => ({ r: x.r, ...score(x.r, grid(boss, true), 60) })).sort((a, b) => b.clean - a.clean || b.worst - a.worst || a.killS - b.killS);
  console.log('\n### ' + boss + '   (' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)');
  top.forEach((x, i) => console.log((i + 1) + '. ' + label(x.r).padEnd(62) + ' clean ' + (100 * x.clean).toFixed(1) + '%  win ' + (100 * x.win).toFixed(1) + '%  worst ' + (100 * x.worst).toFixed(0) + '%  kill ' + (x.killS ? x.killS.toFixed(0) + ' s' : '-') + '  ' + JSON.stringify(x.causes) + (x.worstCase ? '\n     worst case: HP ' + x.worstCase.hp + ', gear resist ' + x.worstCase.gearResist + ', heavy hit ' + x.worstCase.crush + ', Attack ' + x.worstCase.atkDmg + ', Rend tick ' + x.worstCase.rendTick / 1000 + ' s' : '')));
  out[boss] = top.map(x => ({ roster: x.r, clean: x.clean, win: x.win, worst: x.worst, worstCase: x.worstCase, killS: x.killS, causes: x.causes }));
}
if (process.env.RAID_SIM_JSON) require('fs').writeFileSync(process.env.RAID_SIM_JSON, JSON.stringify(out, null, 1));
