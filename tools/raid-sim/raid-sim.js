// General guild-raid simulator. GAME = from the game's client bundle
// (6266-*.js, 1144-*.js, fetched 2026-11-08). ASSUME = not in the client
// (the fight runs on the server); each is a parameter or a stated choice.
'use strict';

const BOSSES = {   // GAME (P{} in 6266-*.js); enrage default y=21e4 when unset
  ashmaw:      { hp: 21000, atk: 2750, aoe: 400, tick: 110, req: 60, enrage: 210000, spreads: false,
                 rot: ['single','aoe','buff','curse','single','aoe','poison'] },
  ashmaw_hard: { hp: 85000, atk: 3100, aoe: 770, tick: 220, req: 90, enrage: 360000, spreads: false,
                 rot: ['single','aoe','buff','curse','single','aoe','poison'] },
  thessaly:    { hp: 38500, atk: 3000, aoe: 400, aoeMaxHp: 0.3, tick: 210, req: 62, enrage: 330000, spreads: true,
                 rot: ['single','aoe','buff','curse','single','aoe','poison'] },
  morwenna:    { hp: 46000, atk: 3050, aoe: 610, tick: 225, req: 60, enrage: 330000, spreads: false,
                 rot: ['single','aoe','buff','curse','single','aoe','doom'] },
  grimjaw:     { hp: 50000, atk: 3100, aoe: 600, tick: 130, req: 64, enrage: 330000, spreads: true, markMs: 55000,
                 rot: ['single','mark','aoe','single','mark','poison','single','mark','aoe'] },
  skarth:      { hp: 74000, atk: 3100, aoe: 650, tick: 195, req: 90, enrage: 360000, spreads: true, aoeTankHalf: true,
                 tombFrac: 0.018, tombMs: 20000, chargeFrac: 0.034, chargeMs: 12000, blastMult: 1.6, staggerMs: 10000, staggerBonus: 0.25,
                 rot: ['single','aoe','entomb','single','charge','aoe','poison'] },
};
const T = { cadence: 15000, atb: 10000, dotTick: 3000, dotMs: 15000, buffMs: 28000, tauntMs: 32000,
            doomMs: 14000 /* wiki */, doomSplash: 0.35 /* GAME */, curseMs: 15000 /* ASSUME */, curseHeal: 0.5 /* ASSUME: Mend's stated halving, for all healing */ };
const L = 70;
const LEND = { mend: 0.21 + 0.003 * L, regrow: Math.round(1.1 * L), cleanse: 0.125 + 0.0017857142857142857 * L,
  wardP: Math.round(L * 12 / 70), wardA: Math.round(L * 36 / 70), fortAoe: Math.min(0.5, 0.0017142857142857142 * L),
  shield: Math.round(1.2 * L), veil: Math.min(95, 1.1428571428571428 * L) / 100, warcry: 0.3142857142857143 * L / 100,
  rend: Math.round(1.7 * L), tauntCut: 0.65 };
const mitigation = (res, req) => 0.5 * Math.min(1, Math.max(0, res) / req);   // ASSUME linear to the 50% cap (wiki: "scales smoothly")

function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

/** o: boss, roster, hp, tankHp, gearResist, crush (heavy hit on a taunting tank,
 *  at ATK 3100, scaled by the boss's ATK), atkDmg (one raider Attack), fortCrush
 *  (share of the heavy hit Fortify's +220% DEF removes), seed, first (ms), cap (ms). */
function simulate(o) {
  const B = BOSSES[o.boss], R = rng(o.seed || 1), n = B.rot.length;
  const rs = o.roster.map((lend, i) => ({ i, lend, maxHp: lend === 'combat' ? o.tankHp : o.hp, hp: 0, shield: 0,
    next: Math.floor(R() * T.atb), dot: null, hot: null, curseUntil: -1, doomUntil: -1, markUntil: -1, tomb: null, dead: false }));
  rs.forEach(r => { r.hp = r.maxHp; });
  const tanks = rs.filter(r => r.lend === 'combat');
  const st = { boss: B.hp, taunt: null, tauntUntil: -1, ward: -1, fort: -1, veil: -1, warcry: -1, rendUntil: -1, rendNext: 0, reinforceReady: 0,
               singleN: 0, charge: null, staggerUntil: -1, deaths: [], killAt: null };
  const has = k => rs.some(r => r.lend === k && !r.dead);
  const live = () => rs.filter(r => !r.dead);
  const first = o.first != null ? o.first : T.cadence, at = k => first + k * T.cadence;
  let k = 0, now = 0;
  const nextOf = kind => { for (let j = k; j < k + 2 * n; j++) if (B.rot[j % n] === kind) return at(j); return Infinity; };
  const enr = () => 1 + Math.max(0, (now - B.enrage) / 60000);
  const resist = () => o.gearResist + (has('jewelcrafting') ? (now < st.ward ? LEND.wardA : LEND.wardP) : 0);
  const mit = () => mitigation(resist(), B.req);
  const tanking = () => (st.taunt && !st.taunt.dead && now < st.tauntUntil) ? st.taunt : null;
  function die(r, cause) { r.dead = true; r.hp = 0; r.tomb = null; st.deaths.push({ t: now, who: r.lend, cause }); }
  function hurt(r, d, cause) {
    if (!r || r.dead || r.tomb) return;
    const s = Math.min(r.shield, d); r.shield -= s; d -= s; r.hp -= d;
    if (r.hp <= 0) die(r, cause);
  }
  function heal(r, a) { if (!r || r.dead) return; if (now < r.curseUntil) a *= T.curseHeal; r.hp = Math.min(r.maxHp, r.hp + a); }
  function hitBoss(d) {
    const ice = live().find(r => r.tomb);
    if (ice) { ice.tomb.hp -= d; if (ice.tomb.hp <= 0) ice.tomb = null; return; }
    d *= (now < st.staggerUntil ? 1 + B.staggerBonus : 1);
    st.boss -= d; if (st.charge) st.charge.dealt += d;
  }
  function attack(r) { hitBoss(o.atkDmg * (now < st.warcry ? 1 + LEND.warcry : 1)); }
  const lowest = () => live().filter(r => !r.tomb).sort((a, b) => a.hp / a.maxHp - b.hp / b.maxHp)[0];
  const urgent = () => live().some(r => r.tomb) || !!st.charge;   // patch v.256: everyone who can switches to Attack

  function act(r) {
    const tS = nextOf('single'), tA = Math.min(nextOf('aoe'), st.charge ? st.charge.until : Infinity);
    switch (r.lend) {
      case 'combat': {
        const turn = B.markMs ? tanks.filter(t => !t.dead)[st.singleN % Math.max(1, tanks.filter(t => !t.dead).length)]
                              : tanks.find(t => !t.dead);
        if (r === turn && tS - now <= T.atb && !(tanking() === r && st.tauntUntil > tS)) { st.taunt = r; st.tauntUntil = now + T.tauntMs; return; }
        break;
      }
      case 'spellcrafting': { const t = lowest(); if (t && t.maxHp - t.hp >= 0.6 * LEND.mend * t.maxHp && (!urgent() || t.hp < 0.5 * t.maxHp)) { heal(t, LEND.mend * t.maxHp); return; } break; }
      case 'herbing': {
        const t = live().filter(x => !x.hot && !x.tomb).sort((a, b) => (b.maxHp - b.hp) - (a.maxHp - a.hp))[0];
        if (t && !urgent() && (t.maxHp - t.hp >= LEND.regrow * 3 || (t === tanking() && tS - now < 12000) || tA - now < 12000)) { t.hot = { until: now + 15000, next: now + T.dotTick }; return; }
        break;
      }
      case 'alchemy': {
        const doom = live().find(x => now < x.doomUntil); if (doom) { doom.doomUntil = -1; heal(doom, LEND.cleanse * doom.maxHp); return; }
        const p = live().find(x => x.dot); if (p) { p.dot = null; p.curseUntil = -1; heal(p, LEND.cleanse * p.maxHp); return; }
        const c = live().find(x => now < x.curseUntil && x.hp < 0.8 * x.maxHp); if (c) { c.curseUntil = -1; heal(c, LEND.cleanse * c.maxHp); return; }
        const t = lowest(); if (t && t.maxHp - t.hp >= LEND.cleanse * t.maxHp) { heal(t, LEND.cleanse * t.maxHp); return; }
        break;
      }
      case 'jewelcrafting': if (tA - now < T.buffMs && st.ward < tA + 500) { st.ward = now + T.buffMs; return; } break;
      case 'smithing': if (!urgent() && ((tA - now < T.buffMs && st.fort < tA + 500) || (tS - now < T.buffMs && st.fort < tS + 500))) { st.fort = now + T.buffMs; return; } break;
      case 'construction': if (now >= st.reinforceReady && tA - now < T.buffMs) { live().forEach(x => { x.shield = LEND.shield; }); st.reinforceReady = now + T.buffMs; return; } break;
      case 'tailoring': if (!urgent() && tS - now < T.buffMs && st.veil < tS + 500) { st.veil = now + T.buffMs; return; } break;
      case 'mining': if (st.warcry < now + T.atb) { st.warcry = now + T.buffMs; return; } break;
      case 'woodcutting': if (!urgent() && st.rendUntil < now + T.atb) { st.rendUntil = now + T.buffMs; st.rendNext = Math.max(st.rendNext, now + (o.rendTick || T.dotTick)); return; } break;
    }
    attack(r);
  }

  const cap = o.cap || 600000;
  for (now = 0; now <= cap; now += 500) {
    for (const r of rs) {
      if (r.dead) continue;
      if (r.hot && now >= r.hot.next) { heal(r, LEND.regrow); r.hot.next += T.dotTick; if (r.hot.next > r.hot.until) r.hot = null; }
      if (r.dot && now >= r.dot.next) {
        hurt(r, B.tick * enr() * (1 - mit()), 'poison');            // ASSUME: Fortify does not cut poison
        if (r.dead || !r.dot) continue;
        r.dot.next += T.dotTick;
        if (r.dot.next > r.dot.until) {
          const jumped = r.dot.jumped; r.dot = null;
          if (B.spreads && !jumped) { const pool = live().filter(x => x !== r && !x.dot && !x.tomb); if (pool.length) pool[Math.floor(R() * pool.length)].dot = { until: now + T.dotMs, next: now + T.dotTick, jumped: true }; }
        }
      }
      if (r.doomUntil > 0 && now >= r.doomUntil) { r.doomUntil = -1; die(r, 'doom'); live().forEach(x => hurt(x, T.doomSplash * x.maxHp, 'doom splash')); }
      if (r.tomb && now >= r.tomb.until) die(r, 'ice tomb');
    }
    if (now < st.rendUntil && now >= st.rendNext) { hitBoss(LEND.rend); st.rendNext += (o.rendTick || T.dotTick); }   // ASSUME: Rend ticks every 3 s
    if (st.charge && now >= st.charge.until) {
      if (st.charge.dealt >= B.chargeFrac * B.hp) st.staggerUntil = now + B.staggerMs;
      else { const m = mit(); live().forEach(x => hurt(x, B.aoe * B.blastMult * enr() * (1 - m), 'glacial breath')); }
      st.charge = null;
    }
    if (now >= at(k)) {
      const kind = B.rot[k % n], e = enr(), tank = tanking();
      if (kind === 'single') {
        const tgt = tank || live().filter(x => !x.tomb)[Math.floor(R() * live().filter(x => !x.tomb).length)];
        if (tgt && !(now < st.veil && R() < LEND.veil)) {
          let d = o.crush * (B.atk / 3100) * e / (tank ? 1 : (1 - LEND.tauntCut));
          if (now < st.fort) d *= 1 - o.fortCrush;
          hurt(tgt, d, tank ? 'heavy hit (tank)' : 'heavy hit (untaunted)');
        }
        st.singleN++;
      } else if (kind === 'aoe') {
        const m = mit(), cut = now < st.fort ? LEND.fortAoe : 0;
        for (const x of live()) {
          let f = 1; if (x === tank) { if (B.aoeTankHalf) f = 0.5; else continue; }
          hurt(x, (B.aoe + (B.aoeMaxHp || 0) * x.maxHp) * e * (1 - m) * (1 - cut) * f, 'raid-wide hit');
        }
      } else if (kind === 'curse') { const p = live(); p[Math.floor(R() * p.length)].curseUntil = now + T.curseMs; }
      else if (kind === 'poison') { const p = live().filter(x => !x.tomb); const t = p[Math.floor(R() * p.length)]; if (t) { if (t.dot) t.dot.until = now + T.dotMs; else t.dot = { until: now + T.dotMs, next: now + T.dotTick, jumped: false }; } }
      else if (kind === 'doom') { const p = live().filter(x => !x.tomb); p[Math.floor(R() * p.length)].doomUntil = now + T.doomMs; }
      else if (kind === 'mark') { if (tank) { if (tank.markUntil > now) die(tank, 'soul anchor'); else tank.markUntil = now + B.markMs; } }
      else if (kind === 'entomb') { const p = live().filter(x => x !== tank && x.lend !== 'combat'); const t = p[Math.floor(R() * p.length)]; if (t) { t.tomb = { hp: B.tombFrac * B.hp, until: now + B.tombMs }; t.dot = null; } }
      else if (kind === 'charge') st.charge = { until: now + B.chargeMs, dealt: 0 };
      k++;
    }
    for (const r of rs) if (!r.dead && !r.tomb && now >= r.next) { act(r); r.next += T.atb; }
    for (const r of rs) if (r.tomb && now >= r.next) r.next += T.atb;   // entombed raiders cannot act
    if (st.boss <= 0) { st.killAt = now; break; }
    if (!live().length) break;
  }
  return { clean: st.killAt != null && !st.deaths.length, win: st.killAt != null, killAt: st.killAt, deaths: st.deaths };
}
module.exports = { simulate, BOSSES, LEND };
