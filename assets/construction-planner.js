(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.IWConstructionPlanner = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var SKILLS = ['construction', 'woodcutting', 'mining'];
  var STORE_KEY = 'iwConstructionVillageV1';
  var HOUSING_SPRITES = {
    1:'./assets/housing/camp.png?v=20260906',
    2:'./assets/housing/cottage.png?v=20260906',
    3:'./assets/housing/villa.png?v=20260906',
    4:'./assets/housing/manor.png?v=20260906',
    5:'./assets/housing/citadel.png?v=20260906'
  };
  var STAT_NAMES = {atk:'ATK',def:'DEF',xp:'XP/task',goldFind:'Gold Find',itemFind:'Item Find',doubleGather:'2× Gather Chance'};
  var SKILL_NAMES = {mining:'Mining',smithing:'Smithing',herbing:'Gathering',alchemy:'Alchemy',jewelcrafting:'Jewelcrafting',spellcrafting:'Spellcrafting',tailoring:'Tailoring',woodcutting:'Woodcutting',construction:'Construction'};
  function number(value, min, max, integer) {
    if (value == null || value === '' || typeof value === 'boolean' || typeof value === 'object') return null;
    var n = Number(value);
    if (!Number.isFinite(n) || n < min || n > max || (integer && !Number.isInteger(n))) return null;
    return n;
  }
  function normalizeState(raw) {
    var r = raw && typeof raw === 'object' ? raw : {};
    function slots(arr) { return Array.from({length:5},function (_,i) { return number(Array.isArray(arr) ? arr[i] : null,1,34,true); }); }
    var levels = {}, stock = {};
    SKILLS.forEach(function (k) { levels[k] = number(r.levels && r.levels[k],1,999,true); });
    if (r.stock && typeof r.stock === 'object') Object.keys(r.stock).forEach(function (key) {
      if (!/^(parts|wood|ore):([1-9]|[12][0-9]|3[0-4])$/.test(key)) return;
      var n = number(r.stock[key],0,Number.MAX_SAFE_INTEGER,true);
      if (n != null) stock[key] = n;
    });
    return {version:1,housing:number(r.housing,0,5,true),levels:levels,gatherYield:number(r.gatherYield,1,1000,false),
      installed:slots(r.installed),planned:slots(r.planned),stock:stock,
      selectedSlot:number(r.selectedSlot,0,4,true) || 0,targetTier:number(r.targetTier,1,34,true) || 1,
      stage:number(r.stage,0,3,true) || 0,scope:r.scope === 'plan' ? 'plan' : 'selected'};
  }
  function resolveSetup(state, context, currentSkills) {
    var c = context || {}, levels = {}, baseLevels = {};
    SKILLS.forEach(function (k) {
      var value = state.levels[k] != null ? state.levels[k] : number(c.levels && c.levels[k],1,999,false);
      baseLevels[k] = value;
      levels[k] = value == null ? null : value + ((currentSkills || {})[k] || 0);
    });
    return {housing:state.housing != null ? state.housing : (number(c.housing,0,5,true) || 0),
      levels:levels,baseLevels:baseLevels,gatherYield:state.gatherYield != null ? state.gatherYield : number(c.gatherYield,1,1000,false)};
  }
  function displayLineup(state, village) {
    var capacity = village && Number.isInteger(village.capacity) ? village.capacity : 0;
    var installed = Array.isArray(state.installed) ? state.installed : [];
    var planned = Array.isArray(state.planned) ? state.planned : [];
    var rows = [];
    for (var slot=0;slot<5;slot++) {
      var tier=installed[slot], rowState='installed';
      if (planned[slot]!=null) { tier=planned[slot]; rowState='planned'; }
      if (slot===state.selectedSlot && state.targetTier!=null) { tier=state.targetTier; rowState='preview'; }
      if (tier!=null) rows.push({slot:slot,tier:tier,state:rowState,active:slot<capacity});
    }
    var seen = {}, activeTiers=[];
    rows.forEach(function(row){
      if (!row.active || seen[row.tier]) return;
      seen[row.tier]=true;activeTiers.push(row.tier);
    });
    return {rows:rows,activeTiers:activeTiers};
  }
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  function fmt(n) { return n == null ? 'Unknown' : Number(n).toLocaleString(undefined,{maximumFractionDigits:2}); }
  function duration(seconds) {
    if (seconds == null || !Number.isFinite(seconds)) return '—';
    var n = Math.ceil(seconds), days = Math.floor(n/86400), hours = Math.floor(n%86400/3600), mins = Math.floor(n%3600/60);
    if (days) return days+'d '+hours+'h '+mins+'m';
    if (hours) return hours+'h '+mins+'m';
    return mins ? mins+'m '+(n%60)+'s' : n+'s';
  }
  function install(options) {
    var o = options, host = document.getElementById(o.rootId);
    if (!host || host.dataset.cvInitialized === 'true') return;
    host.dataset.cvInitialized = 'true';
    var engine = o.engine, state;
    try { state = normalizeState(JSON.parse(localStorage.getItem(STORE_KEY))); } catch (_) { state = normalizeState(null); }
    var context, setup, village, currentBonuses, futureBonuses, selectedResult, displayedResult;
    var search = '', filter = 'all', onlyEligible = false, saveFailed = false;
    function $(selector) { return host.querySelector(selector); }
    function $$(selector) { return Array.from(host.querySelectorAll(selector)); }
    function save() {
      try { localStorage.setItem(STORE_KEY,JSON.stringify(state)); saveFailed = false; }
      catch (_) { saveFailed = true; }
      if (saveFailed) announce('Browser storage is unavailable. Changes last for this visit only.');
    }
    function announce(message) { var e = $('[data-cv-message]'); if (e) e.textContent = message; }
    function building(t) { return o.adapter.building(t); }
    function label(k) { return STAT_NAMES[k] || SKILL_NAMES[k] || k; }
    function stat(k,v,includeName) { return (v >= 0 ? '+' : '') + fmt(v) + (['goldFind','itemFind','doubleGather'].includes(k) ? '%' : '') + (includeName ? ' '+label(k) : ''); }
    function sprite(t) { return o.art('construction_building_tier_'+t,building(t).name,'🏛️'); }
    function item(row) { return o.item(row.name); }
    function housingArt(tier) {
      var fallback='<span class="cv-house-fallback" aria-hidden="true">'+o.houseArt(tier)+'</span>';
      if (!HOUSING_SPRITES[tier]) return '<span class="cv-house-art cv-house-art-fallback-only">'+fallback+'</span>';
      return '<span class="cv-house-art"><img class="cv-house-sprite" src="'+HOUSING_SPRITES[tier]+'" alt="" decoding="async">'+fallback+'</span>';
    }
    function computeContext() {
      context = o.context();
      var h = state.housing != null ? state.housing : context.housing;
      village = engine.village(h,state.installed,state.planned);
      currentBonuses = engine.bonuses(village.currentTiers);
      futureBonuses = engine.bonuses(village.futureTiers);
      setup = resolveSetup(state,context,currentBonuses.skills);
    }
    function plannedTiers() { return state.planned.filter(function(t,i){return t != null && i<village.capacity && t!==state.installed[i];}); }
    function timing() { return {woodcuttingSeconds:o.seconds(10,setup.housing),miningSeconds:o.seconds(10,setup.housing),partsSeconds:o.seconds(10,setup.housing),assemblySeconds:o.seconds(o.assemblySeconds,setup.housing),gatherYield:setup.gatherYield}; }
    function duplicate(t,slot) { return state.installed.some(function(current,i){return i<village.capacity && i!==slot && (state.planned[i] || current)===t;}); }
    function recipeGates(t) {
      var req = 1+(t-1)*4, out = [];
      [['construction',req],['woodcutting',Math.max(1,req-4)]].forEach(function(pair){
        var k=pair[0],v=setup.levels[k];
        if (v == null) out.push('Enter '+label(k)+' level');
        else if (v<pair[1]) out.push(label(k)+' '+pair[1]+' needed (current '+fmt(v)+')');
      });
      return out;
    }
    function readiness(result,tiers) {
      var out = [];
      if ($$('[data-cv-field]').some(function(e){return !e.checkValidity();})) out.push('Correct the highlighted player value.');
      tiers.forEach(function(t){out.push.apply(out,recipeGates(t));});
      result.rawRows.forEach(function(r){
        if (!r.upperBound) return;
        var skill=r.kind==='wood'?'woodcutting':'mining', req=1+(r.tier-1)*4, value=setup.levels[skill];
        if (value==null) out.push('Enter '+label(skill)+' level for gathering');
        else if (value<req) out.push(label(skill)+' '+req+' needed to gather '+r.name);
      });
      if (village.conflicts.length) out.push('Resolve duplicate village buildings');
      if (state.scope==='selected' && state.selectedSlot>=village.capacity) out.push('Selected slot is locked');
      return Array.from(new Set(out));
    }
    host.innerHTML = `
      <div class="pane-head cv-page-head"><div><div class="pane-eyebrow">Skill Tools · Construction</div><h2 class="pane-title">Construction & Village Planner</h2><p class="pane-sub">Shape your village. Compare the benefits. Plan every material.</p></div><a class="cv-wiki" href="https://idleworlds.com/wiki/construction" target="_blank" rel="noopener noreferrer">Construction guide ↗</a></div>
      <div class="cv-setup panel"><div class="cv-setup-top"><span class="cv-eyebrow">Your setup</span><span class="cv-source" data-cv-source></span><button type="button" class="cv-link-button" data-cv-action="sync">Use toolkit settings</button></div>
        <div class="cv-fields"><label>Housing<select data-cv-field="housing" aria-label="Planner housing"></select><small data-cv-housing-source></small></label>
          <label>Construction<input type="number" min="1" max="999" step="1" data-cv-field="construction" placeholder="Enter level"><small data-cv-level-note="construction"></small></label>
          <label>Woodcutting<input type="number" min="1" max="999" step="1" data-cv-field="woodcutting" placeholder="Enter level"><small data-cv-level-note="woodcutting"></small></label>
          <label>Mining<input type="number" min="1" max="999" step="1" data-cv-field="mining" placeholder="Enter level"><small data-cv-level-note="mining"></small></label>
          <label>Gather yield<input type="number" min="1" max="1000" step="0.01" data-cv-field="gatherYield" placeholder="Units / action"><small>Current units per action</small></label></div>
        <details class="cv-assumptions"><summary>Player values and timing</summary><p>Skill inputs are base + equipment, before village bonuses. Confirmed current buildings add their skill bonuses below. The Gear tab's hypothetical add-ons are excluded. Gather yield comes from your current toolkit settings; adjust it if your in-game value differs. Planned buffs are never applied to their own construction.</p><p>Time estimates use the toolkit's housing-adjusted action durations and expected gathering yield. They assume continuous actions, current levels and no travel delay or future level-ups. Woodcutting and Construction are free for all players.</p></details>
      </div>
      <nav class="cv-mobile-steps" aria-label="Construction planning steps"><button type="button" data-cv-stage="0">1 · Slot</button><button type="button" data-cv-stage="1">2 · Building</button><button type="button" data-cv-stage="2">3 · Materials</button><button type="button" data-cv-stage="3">4 · Plan</button></nav>
      <div class="cv-layout">
        <section class="cv-village panel" aria-label="Your current and planned village"><div class="cv-section-head"><div><span class="cv-eyebrow">The village</span><h3 data-cv-village-name></h3></div><span class="cv-chip" data-cv-capacity></span></div>
          <div class="cv-scene"><div class="cv-terrain" aria-hidden="true"></div><div class="cv-path cv-path-a" aria-hidden="true"></div><div class="cv-path cv-path-b" aria-hidden="true"></div><div class="cv-house" data-cv-house></div><div class="cv-plot cv-plot-0"></div><div class="cv-plot cv-plot-1"></div><div class="cv-plot cv-plot-2"></div><div class="cv-plot cv-plot-3"></div><div class="cv-plot cv-plot-4"></div></div>
          <div class="cv-legend"><span>● Installed</span><span>◇ Planned</span><span>+ Available</span><span>▧ Locked</span></div>
          <p class="cv-slot-notice" data-cv-slot-notice></p><div class="cv-alert" data-cv-capacity-warning hidden></div>
          <details class="cv-current-editor"><summary>Edit current village / choose a slot</summary><p>Enter buildings you already have installed in IdleWorlds. This is a manual record; it does not change your game or Gear plan.</p><div data-cv-current-editor></div></details>
          <div class="cv-equipped-bonuses"><div class="cv-equipped-head"><span class="cv-eyebrow">Equipped &amp; previewed bonuses</span><span class="cv-small">Every building shown in your working lineup</span></div><div class="cv-bonus-lineup" data-cv-bonus-lineup></div><div class="cv-equipped-total"><span class="cv-eyebrow">Combined active total</span><div class="cv-facts" data-cv-equipped-total></div></div></div>
          <div class="cv-saved-plan"><div class="cv-section-head"><h3>Village plan</h3><button type="button" class="cv-link-button" data-cv-action="clear-plan">Clear plan</button></div><div data-cv-saved-plan></div><p class="cv-small">Saved locally. Planning never installs or destroys a building in your game.</p></div>
        </section>
        <section class="cv-details" aria-label="Selected building and production plan">
          <div class="cv-slot-intro panel" data-cv-stage-panel="0"><span class="cv-eyebrow">Choose a plot</span><h3 data-cv-slot-intro></h3><p>Select a plot in your village, then choose the building you want to work toward.</p><button type="button" class="cv-primary" data-cv-next="1">Choose a building →</button></div>
          <section class="panel cv-building-panel" data-cv-stage-panel="1"><div class="cv-section-head"><span class="cv-eyebrow" data-cv-selection-label></span><span class="cv-chip" data-cv-selection-status></span></div><div class="cv-building-hero" data-cv-building-hero></div><div class="cv-buff-lines" data-cv-buffs></div><div class="cv-eligibility" data-cv-eligibility></div>
            <details class="cv-catalogue"><summary>Browse buildings <span>34 Village Add-ons</span></summary><div class="cv-search-controls"><label class="cv-search-label">Find a building<input type="search" data-cv-search placeholder="Search by name or tier"></label><label>Benefit<select data-cv-filter><option value="all">All benefits</option></select></label><label class="cv-check"><input type="checkbox" data-cv-eligible>Levels met only</label></div><div class="cv-catalogue-grid" data-cv-catalogue></div><p class="cv-small" data-cv-result-count></p></details>
            <div class="cv-bonus-compare" data-cv-bonus-compare></div><details class="cv-refund" hidden><summary>Replacement refund · 25% of Assembly cost</summary><div data-cv-refund></div><p class="cv-small">Preview only. Refunds are not added to your inventory or gathering estimate. Fractional quantities are shown before in-game rounding. Removing the old building also removes its bonuses.</p></details>
            <div class="cv-actions"><button type="button" class="cv-primary" data-cv-action="add">Add to village plan</button><button type="button" class="cv-secondary cv-mobile-next" data-cv-next="2">Materials →</button></div>
          </section>
          <section class="panel cv-material-panel" data-cv-stage-panel="2"><div class="cv-section-head"><div><span class="cv-eyebrow">The complete bill</span><h3>Construction materials</h3></div><label class="cv-scope-label">Calculate<select data-cv-scope><option value="selected">Selected building</option><option value="plan">Whole village plan</option></select></label></div>
            <div class="cv-scope-note" data-cv-scope-note></div><div class="cv-table-wrap"><table class="cv-table"><thead><tr><th>Assembly input</th><th>Required</th><th>Owned</th><th>Missing</th></tr></thead><tbody data-cv-direct></tbody></table></div>
            <details class="cv-parts-details"><summary>Expand missing Parts into raw materials</summary><div data-cv-parts></div></details>
            <div class="cv-raw-head"><h4>Total timber & ore</h4><span class="cv-small">Assembly + missing Parts</span></div><div class="cv-table-wrap"><table class="cv-table"><thead><tr><th>Raw resource</th><th>Required</th><th>Owned</th><th>Gather</th></tr></thead><tbody data-cv-raw></tbody></table></div>
            <div class="cv-stock-help"><span>Blank means unknown.</span><button type="button" class="cv-link-button" data-cv-action="zero-unknown">Set unknown stock to 0 for this bill</button></div><p class="cv-small">Owned Parts are deducted first. Raw stock is shared once across the complete bill.</p><button type="button" class="cv-secondary cv-mobile-next" data-cv-next="3">Production plan →</button>
          </section>
          <section class="panel cv-production-panel" data-cv-stage-panel="3"><div class="cv-section-head"><div><span class="cv-eyebrow">From resources to village</span><h3>Production plan</h3></div><span class="cv-chip" data-cv-readiness></span></div><div class="cv-alert" data-cv-blockers hidden></div><ol class="cv-production" data-cv-production></ol><div class="cv-time-total"><span>Estimated action time</span><strong data-cv-total-time>—</strong></div><p class="cv-small" data-cv-time-note></p><div class="cv-actions"><button type="button" class="cv-secondary" data-cv-action="copy">Copy material plan</button><button type="button" class="cv-link-button cv-mobile-next" data-cv-next="0">← Change slot</button></div></section>
        </section>
      </div><p class="cv-live-message" data-cv-message role="status" aria-live="polite"></p>`;

    $('[data-cv-field="housing"]').innerHTML = Array.from({length:6},function(_,i){return '<option value="'+i+'">'+esc(o.houseName(i))+' · '+i+' slot'+(i===1?'':'s')+'</option>';}).join('');
    $('[data-cv-filter]').insertAdjacentHTML('beforeend','<optgroup label="Passive stat">'+Object.keys(STAT_NAMES).map(function(k){return '<option value="'+k+'">'+esc(label(k))+'</option>';}).join('')+'</optgroup><optgroup label="Skill bonus">'+Object.keys(SKILL_NAMES).map(function(k){return '<option value="'+k+'">'+esc(label(k))+'</option>';}).join('')+'</optgroup>');

    function renderSetup() {
      $('[data-cv-field="housing"]').value = String(setup.housing);
      $('[data-cv-housing-source]').textContent = state.housing == null ? 'Following toolkit housing' : 'Manual housing scenario';
      SKILLS.forEach(function(k){
        var e = $('[data-cv-field="'+k+'"]'); if (document.activeElement!==e) e.value = setup.baseLevels[k] == null ? '' : setup.baseLevels[k];
        $('[data-cv-level-note="'+k+'"]').textContent = (state.levels[k] == null ? (context.source || 'Toolkit') : 'Manual')+' · Effective '+fmt(setup.levels[k]);
      });
      var gy=$('[data-cv-field="gatherYield"]');if(document.activeElement!==gy)gy.value=setup.gatherYield==null?'':setup.gatherYield;
      $('[data-cv-source]').textContent = 'Current village: manual · Player values: '+(state.housing!=null || state.gatherYield!=null || SKILLS.some(function(k){return state.levels[k]!=null;}) ? 'manual / toolkit' : (context.source || 'toolkit'));
    }
    function factRows(totals) {
      return Object.keys(totals.stats).map(function(k){return '<span class="cv-fact">'+esc(stat(k,totals.stats[k],true))+'</span>';}).concat(Object.keys(totals.skills).map(function(k){return '<span class="cv-fact">+'+fmt(totals.skills[k])+' '+esc(label(k))+'</span>';})).join('') || '<span class="cv-small">No active bonuses in this lineup.</span>';
    }
    function renderEquippedBonuses() {
      var lineup=displayLineup(state,village), seen={};
      $('[data-cv-bonus-lineup]').innerHTML=lineup.rows.map(function(row){
        var b=building(row.tier), counted=row.active&&!seen[row.tier];
        if(row.active)seen[row.tier]=true;
        var stateLabel=!row.active?'Requires housing upgrade':!counted?'Already represented':row.state==='preview'?'Preview':row.state==='planned'?'Planned':'Installed';
        return '<article class="cv-bonus-card cv-bonus-'+row.state+(row.active?'':' cv-bonus-inactive')+(counted?'':' cv-bonus-duplicate')+'">'+
          '<div class="cv-bonus-card-head">'+sprite(row.tier)+'<div><strong>'+esc(b.name)+'</strong><span>Slot '+(row.slot+1)+' · '+esc(stateLabel)+'</span></div></div>'+
          '<div class="cv-bonus-card-lines"><span><small>Primary</small>'+esc(stat(b.buffs.primary.stat,b.buffs.primary.value,true))+'</span><span><small>Secondary</small>'+b.buffs.secondary.map(function(v){return esc(stat(v.stat,v.value,true));}).join(' · ')+'</span><span><small>Skill</small>+'+fmt(b.buffs.skill.amount)+' '+esc(label(b.buffs.skill.skill))+'</span></div></article>';
      }).join('')||'<p class="cv-small">Choose a building to preview its permanent bonuses.</p>';
      $('[data-cv-equipped-total]').innerHTML=factRows(engine.bonuses(lineup.activeTiers));
    }
    function renderVillage() {
      $('[data-cv-village-name]').textContent = o.houseName(setup.housing);
      $('[data-cv-capacity]').textContent = village.currentTiers.length+' installed / '+village.capacity+' slots';
      $('[data-cv-house]').innerHTML = housingArt(setup.housing)+'<strong>'+esc(o.houseName(setup.housing))+'</strong><span>Housing tier '+setup.housing+'</span>';
      for(var i=0;i<5;i++) {
        var locked=i>=village.capacity, current=state.installed[i], planned=state.planned[i], tier=planned || current;
        var status=locked?'Locked':planned && planned!==current?'Planned':current?'Installed':'Available';
        var art=tier?sprite(tier):'<span class="cv-empty-plot">'+o.houseArt(0)+'</span>';
        $('.cv-plot-'+i).innerHTML='<button type="button" class="cv-plot-button '+(planned&&planned!==current?'cv-planned ':'')+(locked?'cv-locked ':'')+'" data-cv-slot="'+i+'" aria-pressed="'+(state.selectedSlot===i)+'" aria-label="Slot '+(i+1)+' · '+esc(status)+(tier?' · '+esc(building(tier).name):'')+'">'+art+'<span class="cv-plot-name">'+esc(tier?building(tier).name:'Slot '+(i+1))+'</span><span class="cv-plot-status">'+(locked?'Needs '+esc(o.houseName(i+1)):status)+'</span></button>';
      }
      var name=state.installed[state.selectedSlot]?building(state.installed[state.selectedSlot]).name:'Empty plot';
      $('[data-cv-slot-notice]').textContent = 'Slot '+(state.selectedSlot+1)+' · '+name+(state.selectedSlot>=village.capacity?' · Locked at this housing tier':'');
      $('[data-cv-slot-intro]').textContent = 'Slot '+(state.selectedSlot+1)+' selected';
      var warn=[];
      if(village.inactiveSlots.length) warn.push('Assignments in slots '+village.inactiveSlots.map(function(i){return i+1;}).join(', ')+' are retained but inactive at this housing tier.');
      if(village.conflicts.length)warn.push('Duplicate building types need resolving before this village is valid.');
      $('[data-cv-capacity-warning]').hidden=!warn.length;$('[data-cv-capacity-warning]').textContent=warn.join(' ');
      $('[data-cv-current-editor]').innerHTML=state.installed.map(function(t,i){return '<div class="cv-current-row"><button type="button" class="cv-secondary" data-cv-slot="'+i+'">Slot '+(i+1)+'</button><label><span class="cv-sr-only">Installed building in slot '+(i+1)+'</span><select data-cv-installed="'+i+'"><option value="">Empty</option>'+Array.from({length:34},function(_,j){var tier=j+1,used=state.installed.some(function(v,s){return s!==i&&v===tier;});return '<option value="'+tier+'"'+(t===tier?' selected':'')+(used?' disabled':'')+'>T'+tier+' · '+esc(building(tier).name)+'</option>';}).join('')+'</select></label>'+(i>=village.capacity?'<span class="cv-small">Inactive</span>':'')+'</div>';}).join('');
      renderEquippedBonuses();
      var plans=state.planned.map(function(t,i){if(t==null)return '';return '<div class="cv-plan-row"><button type="button" class="cv-plan-select" data-cv-slot="'+i+'">'+sprite(t)+'<span>Slot '+(i+1)+' · '+esc(building(t).name)+'<small>'+(i>=village.capacity?'Housing locked':state.installed[i]===t?'Already installed':state.installed[i]?'Replacement plan':'New add-on')+'</small></span></button><button type="button" class="cv-link-button" data-cv-remove="'+i+'" aria-label="Remove plan for slot '+(i+1)+'">Remove</button></div>';}).join('');
      $('[data-cv-saved-plan]').innerHTML=plans||'<p class="cv-small">Select an available slot and add your first building.</p>';
    }
    function renderCatalogue() {
      var choices=[];
      for(var t=1;t<=34;t++){
        var b=building(t),values=[b.buffs.primary].concat(b.buffs.secondary), match=filter==='all'||values.some(function(v){return v.stat===filter;})||b.buffs.skill.skill===filter;
        if(!match || (search && (b.name+' '+t+' tier '+t).toLowerCase().indexOf(search)<0) || (onlyEligible&&recipeGates(t).length))continue;
        var dup=duplicate(t,state.selectedSlot);
        choices.push('<button type="button" class="cv-building-choice" data-cv-building="'+t+'" aria-pressed="'+(t===state.targetTier)+'"'+(dup?' disabled':'')+'>'+sprite(t)+'<strong>'+esc(b.name)+'</strong><span>T'+t+' · +'+b.buffs.skill.amount+' '+esc(label(b.buffs.skill.skill))+'</span><small>'+esc(dup?'Already in village plan':recipeGates(t).length?'Levels needed':'Levels met')+'</small></button>');
      }
      $('[data-cv-catalogue]').innerHTML=choices.join('');$('[data-cv-result-count]').textContent=choices.length+' buildings shown';
    }
    function comparisonRows(current,next) {
      var html='';['stats','skills'].forEach(function(group){Object.keys(Object.assign({},current[group],next[group])).forEach(function(k){var a=current[group][k]||0,b=next[group][k]||0;if(a===b)return;html+='<div class="cv-delta"><span>'+esc(label(k))+'</span><span>'+fmt(a)+' → '+fmt(b)+'</span><strong class="'+(b>=a?'cv-gain':'cv-loss')+'">'+esc(stat(k,b-a,false))+'</strong></div>';});});return html;
    }
    function renderBuilding() {
      var t=state.targetTier,b=building(t),current=state.installed[state.selectedSlot],future=state.planned.slice();future[state.selectedSlot]=t;
      var preview=engine.village(setup.housing,state.installed,future),after=engine.bonuses(preview.futureTiers);
      $('[data-cv-selection-label]').textContent='Slot '+(state.selectedSlot+1)+' · '+(current?'Inspect / replace':'Choose a building');
      $('[data-cv-selection-status]').textContent=current===t?'Installed':state.planned[state.selectedSlot]===t?'Planned':'Preview';
      $('[data-cv-building-hero]').innerHTML='<div class="cv-hero-art">'+sprite(t)+'</div><div><span class="cv-eyebrow">Village Add-on · Tier '+t+'</span><h3>'+esc(b.name)+'</h3><span class="cv-small">Permanent passive benefits while installed</span></div>';
      $('[data-cv-buffs]').innerHTML='<div><span>Primary</span><strong>'+esc(stat(b.buffs.primary.stat,b.buffs.primary.value,true))+'</strong></div><div><span>Secondary</span><strong>'+b.buffs.secondary.map(function(v){return esc(stat(v.stat,v.value,true));}).join(' · ')+'</strong></div><div><span>Skill level</span><strong>+'+b.buffs.skill.amount+' '+esc(label(b.buffs.skill.skill))+'</strong></div>';
      var gates=recipeGates(t),req=1+(t-1)*4;
      $('[data-cv-eligibility]').textContent=(gates.length?'○ ':'✓ ')+'Construction '+req+' · Woodcutting '+Math.max(1,req-4)+(gates.length?' · '+gates.join('; '):' · Recipe levels met');
      $('[data-cv-bonus-compare]').innerHTML='<div class="cv-eyebrow">Village totals · current → planned</div>'+(comparisonRows(currentBonuses,after)||'<p class="cv-small">No change to current bonuses.</p>');
      $('.cv-refund').hidden=!current||current===t;
      if(current&&current!==t){var refund=engine.refund(current);$('[data-cv-refund]').innerHTML='<p class="cv-small">If '+esc(building(current).name)+' is destroyed:</p>'+refund.rows.map(function(r){return '<div class="cv-refund-row"><span>'+item({name:r.label})+'</span><strong>'+fmt(r.qty)+(Number.isInteger(r.qty)?'':' <small>before rounding</small>')+'</strong></div>';}).join('');}
      var add=$('[data-cv-action="add"]');add.disabled=state.selectedSlot>=village.capacity||duplicate(t,state.selectedSlot)||current===t;add.textContent=state.planned[state.selectedSlot]===t?'Update village plan':current?'Plan replacement':'Add to village plan';
      renderCatalogue();
    }
    function rowHtml(r,kind) {
      return '<tr data-cv-row="'+r.id+'"><td>'+item(r)+'</td><td data-cv-required="'+r.id+'">'+(r.provisional?'Up to ':'')+fmt(r.required)+'</td><td><input type="number" min="0" max="9007199254740991" step="1" inputmode="numeric" data-cv-stock="'+r.id+'" aria-label="Owned '+esc(r.name)+(kind==='raw'?' raw stock':'')+'" value="'+(state.stock[r.id]==null?'':state.stock[r.id])+'" placeholder="?"></td><td data-cv-missing="'+r.id+'">'+(r.missing==null?'?':fmt(r.missing))+'</td></tr>';
    }
    function updateRows(selector,rows,kind,preserve) {
      var table=$(selector),ids=rows.map(function(r){return r.id;}).join('|');
      if(!preserve||table.dataset.rowIds!==ids){table.innerHTML=rows.map(function(r){return rowHtml(r,kind);}).join('');table.dataset.rowIds=ids;}
      else rows.forEach(function(r){
        var row=table.querySelector('[data-cv-row="'+r.id+'"]');
        row.querySelector('[data-cv-required]').textContent=(r.provisional?'Up to ':'')+fmt(r.required);
        row.querySelector('[data-cv-missing]').textContent=r.missing==null?'?':fmt(r.missing);
        var input=row.querySelector('input');if(input!==document.activeElement)input.value=state.stock[r.id]==null?'':state.stock[r.id];
      });
    }
    function scopeTiers() { return state.scope==='plan'?plannedTiers():[state.targetTier]; }
    function refreshResults(preserve) {
      var tiers=scopeTiers();
      displayedResult=engine.requirements(tiers,state.stock,timing());
      selectedResult=state.scope==='selected'?displayedResult:engine.requirements([state.targetTier],state.stock,timing());
      var r=displayedResult, blockers=readiness(r,tiers);
      if(!tiers.length)blockers.push('Add a building to your village plan.');
      $('[data-cv-scope]').value=state.scope;
      $('[data-cv-scope-note]').textContent=state.scope==='plan'?tiers.length+' planned building'+(tiers.length===1?'':'s')+' · stock shared once · locked slots excluded':building(state.targetTier).name+' · one Assembly';
      updateRows('[data-cv-direct]',r.assemblyRows,'direct',preserve);updateRows('[data-cv-raw]',r.rawRows,'raw',preserve);
      $('[data-cv-parts]').innerHTML=r.partsRows.map(function(p){return '<div class="cv-parts-row"><strong>'+(p.missing==null?'Up to '+fmt(p.upperBound):fmt(p.missing))+' '+esc(p.name)+'</strong><span>'+fmt(p.upperBound*2*p.tier)+' '+esc(o.adapter.woodName(p.tier))+' + '+fmt(p.upperBound*p.tier)+' '+esc(o.adapter.oreName(p.tier))+'</span></div>';}).join('')||'<p class="cv-small">No Parts needed.</p>';
      var complete=r.completeInventory&&!blockers.length&&tiers.length>0;
      $('[data-cv-readiness]').textContent=blockers.length?'Requirements pending':!r.completeInventory?'Inventory incomplete':'Ready to gather';
      var warnings=blockers.slice();if(!r.completeInventory)warnings.push('Enter missing inventory values or explicitly set unknown stock to zero.');
      $('[data-cv-blockers]').hidden=!warnings.length;$('[data-cv-blockers]').innerHTML=warnings.map(function(w){return '<div>'+esc(w)+'</div>';}).join('');
      function rawSummary(kind){return r.rawRows.filter(function(row){return row.kind===kind&&row.upperBound>0;}).map(function(row){return (row.missing==null?'Up to ':'')+fmt(row.upperBound)+' '+esc(row.name)+'<small>'+esc(o.zone(row.tier))+' · '+(kind==='wood'?'Woodcutting':'Mining')+' '+(1+(row.tier-1)*4)+'</small>';}).join('<br>')||'No gathering needed';}
      var steps=[['Woodcutting',rawSummary('wood'),complete?r.times.woodcutting:null],['Mining',rawSummary('ore'),complete?r.times.mining:null],['Craft Building Parts',r.partsRows.filter(function(p){return p.upperBound>0;}).map(function(p){return (p.missing==null?'Up to ':'')+fmt(p.upperBound)+' '+esc(p.name);}).join('<br>')||'All required Parts owned',complete?r.times.parts:null],['Assembly',tiers.length+' building'+(tiers.length===1?'':'s')+'<small>Raw Assembly materials already included above.</small>',complete?r.times.assembly:null]];
      $('[data-cv-production]').innerHTML=steps.map(function(step,i){return '<li><span class="cv-step-number">'+(i+1)+'</span><div><strong>'+step[0]+'</strong><p>'+step[1]+'</p></div><span class="cv-step-time">'+duration(step[2])+'</span></li>';}).join('');
      $('[data-cv-total-time]').textContent=complete?duration(r.times.total):'—';
      $('[data-cv-time-note]').textContent=complete?'Estimated continuous action time at current levels and gather yield. Excludes travel, future level-ups and prospective refunds.':'A total appears when inventory, skill requirements and timing inputs are complete.';
    }
    function renderStages() {host.dataset.cvStage=String(state.stage);$$('[data-cv-stage]').forEach(function(b){b.setAttribute('aria-current',+b.dataset.cvStage===state.stage?'step':'false');});}
    function render() {computeContext();renderSetup();renderVillage();renderBuilding();refreshResults(false);renderStages();}
    function selectSlot(i) {state.selectedSlot=i;state.targetTier=state.planned[i]||state.installed[i]||state.targetTier;save();render();announce('Slot '+(i+1)+' selected.');}
    function stage(n) {state.stage=n;save();renderStages();if(window.matchMedia('(max-width: 760px)').matches)$('.cv-mobile-steps').scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}

    host.addEventListener('click',function(event){
      var b=event.target.closest('button');if(!b||!host.contains(b)||b.disabled)return;
      if(b.dataset.cvSlot!=null){selectSlot(+b.dataset.cvSlot);return;}
      if(b.dataset.cvStage!=null){stage(+b.dataset.cvStage);return;}
      if(b.dataset.cvNext!=null){stage(+b.dataset.cvNext);return;}
      if(b.dataset.cvBuilding!=null){state.targetTier=+b.dataset.cvBuilding;$('.cv-catalogue').open=false;save();renderBuilding();renderEquippedBonuses();refreshResults(false);return;}
      if(b.dataset.cvRemove!=null){state.planned[+b.dataset.cvRemove]=null;save();render();announce('Building removed from the local plan.');return;}
      var action=b.dataset.cvAction;
      if(action==='sync'){state.housing=null;state.gatherYield=null;SKILLS.forEach(function(k){state.levels[k]=null;});save();render();announce('Player values now follow toolkit settings. Current village and stock retained.');}
      if(action==='add'){if(state.selectedSlot>=village.capacity||duplicate(state.targetTier,state.selectedSlot))return;state.planned[state.selectedSlot]=state.targetTier;save();render();announce(building(state.targetTier).name+' saved to the local village plan.');}
      if(action==='clear-plan'){state.planned=[null,null,null,null,null];save();render();announce('Local building plans cleared. Installed buildings and stock retained.');}
      if(action==='zero-unknown'){
        displayedResult.assemblyRows.forEach(function(r){if(state.stock[r.id]==null)state.stock[r.id]=0;});
        var full=engine.requirements(scopeTiers(),state.stock,timing());full.rawRows.forEach(function(r){if(state.stock[r.id]==null)state.stock[r.id]=0;});save();refreshResults(false);announce('Unknown stock for this bill recorded as zero.');
      }
      if(action==='copy'){
        var lines=['IdleWorlds Construction & Village Planner',state.scope==='plan'?'Whole village plan':building(state.targetTier).name,'Raw materials to gather:'];
        displayedResult.rawRows.forEach(function(r){lines.push((r.missing==null?'Unknown (up to '+fmt(r.upperBound)+')':fmt(r.missing))+' '+r.name);});
        lines.push('Building Parts to craft:');displayedResult.partsRows.forEach(function(r){lines.push((r.missing==null?'Unknown (up to '+fmt(r.upperBound)+')':fmt(r.missing))+' '+r.name);});lines.push('Estimated action time: '+$('[data-cv-total-time]').textContent);
        if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(lines.join('\n')).then(function(){announce('Material plan copied.');},function(){announce('Clipboard unavailable. Select the material rows to copy them.');});
        else announce('Clipboard unavailable. Select the material rows to copy them.');
      }
    });
    host.addEventListener('input',function(event){
      var e=event.target;
      if(e.dataset.cvField){e.setAttribute('aria-invalid',e.checkValidity()?'false':'true');if(!e.checkValidity())refreshResults(true);}
      if(e.dataset.cvSearch!=null){search=e.value.trim().toLowerCase();renderCatalogue();return;}
      if(e.dataset.cvStock!=null){var value=number(e.value,0,Number.MAX_SAFE_INTEGER,true);if(value==null)delete state.stock[e.dataset.cvStock];else state.stock[e.dataset.cvStock]=value;e.setAttribute('aria-invalid',e.value!==''&&value==null?'true':'false');save();refreshResults(true);}
    });
    host.addEventListener('error',function(event){
      if(event.target&&event.target.classList&&event.target.classList.contains('cv-house-sprite'))event.target.parentElement.classList.add('cv-house-art-failed');
    },true);
    host.addEventListener('change',function(event){
      var e=event.target;
      if(e.dataset.cvField){if(!e.checkValidity()){e.setAttribute('aria-invalid','true');refreshResults(true);return;}e.setAttribute('aria-invalid','false');var field=e.dataset.cvField;
        if(field==='housing')state.housing=number(e.value,0,5,true);
        else if(field==='gatherYield')state.gatherYield=number(e.value,1,1000,false);
        else state.levels[field]=number(e.value,1,999,true);
        save();render();
      }
      if(e.dataset.cvInstalled!=null){var i=+e.dataset.cvInstalled,t=number(e.value,1,34,true);if(t!=null&&state.installed.some(function(v,j){return j!==i&&v===t;})){announce('Only one of each building type can be installed.');render();return;}state.installed[i]=t;save();render();announce('Current village record updated locally.');}
      if(e.dataset.cvFilter!=null){filter=e.value;renderCatalogue();}
      if(e.dataset.cvEligible!=null){onlyEligible=e.checked;renderCatalogue();}
      if(e.dataset.cvScope!=null){state.scope=e.value;save();refreshResults(false);}
    });
    function refresh() {if(host.closest('.tab-pane').classList.contains('active'))render();}
    ['iw:profile','iw:profile-refreshed','iw:equipment','iw:item-data'].forEach(function(name){window.addEventListener(name,refresh);});
    ['housing-tier','gather-toggle','gather-chance'].forEach(function(id){var e=document.getElementById(id);if(e)e.addEventListener('change',refresh);});
    window.addEventListener('storage',function(e){if(e.key===STORE_KEY){try{state=normalizeState(JSON.parse(e.newValue));}catch(_){state=normalizeState(null);}refresh();}});
    window.iwConstructionPlannerEnter=render;
    window.iwConstructionPlannerSelfCheck=function(){
      var failures=[];
      try{var result=engine.requirements([1],{'parts:1':50,'wood:1':100,'ore:1':25},{woodcuttingSeconds:10,miningSeconds:10,partsSeconds:10,assemblySeconds:180,gatherYield:1});
        if(result.rawRows.find(function(r){return r.id==='wood:1';}).missing!==300)failures.push('Training Yard timber stock allocation');
        if(result.rawRows.find(function(r){return r.id==='ore:1';}).missing!==175)failures.push('Training Yard ore stock allocation');
        if(result.times.total!==6430)failures.push('Training Yard total timing');
        if(!document.querySelector('#tab-construction-village'))failures.push('Construction tab missing');
      }catch(e){failures.push('Construction planner: '+e.message);}return failures;
    };
    render();
  }
  return {normalizeState:normalizeState,resolveSetup:resolveSetup,displayLineup:displayLineup,install:install};
});
