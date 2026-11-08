'use strict';
// For a boss, which raider HP and Attack damage does a roster need for 100%?
// Usage: node sens.js <boss> <lend,lend,...> [lend,... more rosters]
const { simulate, BOSSES } = require('./raid-sim.js');
const boss = process.argv[2], rosters = process.argv.slice(3).map(s => s.split(','));
const B = BOSSES[boss], target = Math.max(0, B.req - 36), N = 100;
const HPS = [450, 525, 700, 900], ATK = [200, 275, 400, 550];
for (const roster of rosters) {
  console.log('\n' + boss + ': ' + roster.join(' ') + '   (rows raider HP, tanks 2x; columns Attack damage; heavy hit 450, gear resist ' + target + ', Rend tick 3 s and 10 s)');
  console.log('        ' + ATK.map(a => ('atk ' + a).padStart(16)).join(''));
  for (const hp of HPS) {
    const cells = ATK.map(atkDmg => {
      let ok = 0, kill = 0, k = 0;
      for (const rendTick of [3000, 10000]) for (let s = 1; s <= N; s++) {
        const r = simulate({ boss, roster, hp, tankHp: 2 * hp, gearResist: target, crush: 450, atkDmg, rendTick, fortCrush: 0.3, seed: s * 7919 + hp + atkDmg, first: 12000 + (s % 7) * 1000 });
        if (r.clean) ok++; if (r.win) { kill += r.killAt; k++; }
      }
      return ((100 * ok / (2 * N)).toFixed(0) + '% ' + (k ? Math.round(kill / k / 1000) + 's' : '-')).padStart(16);
    });
    console.log(('hp ' + hp).padEnd(8) + cells.join(''));
  }
}
