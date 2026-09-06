from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from atomic_write import replace_atomically

root = Path(__file__).resolve().parents[1]
path = root / 'index.html'
original = path.read_bytes()
source = original.decode('utf-8')
newline = '\r\n' if '\r\n' in source else '\n'
assert 'id="tab-construction-village"' not in source, 'Integration already exists'

def insert_before(anchor, text, expected=1):
    global source
    assert source.count(anchor) == expected, (anchor, source.count(anchor))
    source = source.replace(anchor, text.replace('\n', newline) + anchor)

def replace_once(old, new):
    global source
    assert source.count(old) == 1, (old, source.count(old))
    source = source.replace(old, new)

nav = '''        <button class="tab-btn community-tool-child" data-tab="construction-village" role="tab" aria-selected="false" aria-controls="tab-construction-village" onclick="switchTab(&#39;construction-village&#39;)">
          <span class="tab-icon" aria-hidden="true">🏘️</span>
          <span class="tab-label">Construction &amp; Village Planner</span>
        </button>
'''
insert_before('        <button class="tab-btn community-tool-child" data-tab="jewelry"', nav, 2)
insert_before('</head>', '<link rel="stylesheet" href="./assets/construction-planner.css?v=20260905">\n')
pane = '''  <!-- Construction & Village Planner: independent current village, target plan and stock. -->
  <div class="tab-pane" id="tab-construction-village" role="tabpanel" aria-label="Construction & Village Planner">
    <div id="cv-root"><div class="panel">Loading the Construction &amp; Village Planner…</div></div>
  </div>

'''
work_order = source.index('  <div class="tab-pane" id="tab-work-order"')
comment = source.rfind('<!--', 0, work_order)
assert source[comment:work_order].count('<!--') == 1
source = source[:comment] + pane.replace('\n',newline) + source[comment:]
replace_once("const isCommunityTool = name === 'work-order' || name === 'jewelry';", "const isCommunityTool = name === 'work-order' || name === 'jewelry' || name === 'construction-village';")
replace_once("name === 'database' || name === 'work-order' || name === 'jewelry') {", "name === 'database' || name === 'work-order' || name === 'jewelry' || name === 'construction-village') {")
insert_before("  if (name === 'jewelry') {", "  if (name === 'construction-village' && typeof window.iwConstructionPlannerEnter === 'function') {\n    window.iwConstructionPlannerEnter();\n  }\n\n")
replace_once("        'iwVillageAddonsV1',", "        'iwVillageAddonsV1', 'iwConstructionVillageV1',")
replace_once("['Woodcutting/Construction',window.iwWoodcuttingConstructionSelfCheck]", "['Woodcutting/Construction',window.iwWoodcuttingConstructionSelfCheck],"+newline+"        ['Construction village planner',window.iwConstructionPlannerSelfCheck]")

bridge = '''
<!-- Construction & Village Planner: consumes the shared data after all toolkit modules load. -->
<script src="./assets/construction-planner-engine.js?v=20260905"></script>
<script src="./assets/construction-planner.js?v=20260905"></script>
<script>
(function () {
  'use strict';
  var host = document.getElementById('cv-root');
  try {
    if (!window.IWConstructionPlanner || !window.IWConstructionPlannerEngine)
      throw new Error('Planner assets could not load. Reload the toolkit to retry.');
    var adapter = {
      building: function (tier) { return {tier:tier,name:BUILDING_NAMES[tier],inputs:assemblyInputs(tier),buffs:buildingBuffs(tier)}; },
      woodName: function (tier) { return WOOD_NAMES[tier]; },
      oreName: function (tier) { return ORE_NAMES[tier]; }
    };
    // Timber zones read from idleworlds.com/wiki/construction on 2026-09-05.
    var zones = ['Greenwake Den','Ironfang Trail','Silverroot Hollow','Goldfire Pass','Mythril Bastion','Starsteel Frontier','Obsidian Depths','Runic Barrens','Dragonfall Ridge','Aether Spires','Voidiron Abyss','Celestial Crown','Bloodstone Scar','Moonsteel Basin','Sunforge Expanse','Nethergate Chasm','Stormglass Reach','Kingsfall Citadel','Eternium Verge','Astral Crucible','Gravite Maw','Frostiron Shelf','Dusksteel Strand','Titanium Wastes','Skysteel Pinnacle','Emberium Caldera','Soulsteel Necropolis','Chronite Spiral','Worldforge Core','Voidglass Sanctum','Thalassic Abyss','Ashspire Ruins','Glacial Abyss','Primordial Spire'];
    function art(id, name, fallback) {
      return window.IW_ITEM_SPRITES && typeof window.IW_ITEM_SPRITES.markup === 'function'
        ? window.IW_ITEM_SPRITES.markup(id, name, fallback) : '<span aria-hidden="true">'+fallback+'</span>';
    }
    window.IWConstructionPlanner.install({
      rootId:'cv-root', adapter:adapter, engine:window.IWConstructionPlannerEngine.create(adapter),
      seconds:effectiveDuration, assemblySeconds:ASSEMBLY_TIME,
      houseName:function(tier){return HOUSING_NAMES[tier];},
      houseArt:function(tier){return SVG_OPEN+(HOUSE_ICONS[tier] || HOUSE_ICONS[0])+'</svg>';},
      zone:function(tier){return 'Zone '+tier+' · '+(zones[tier-1] || '');},
      art:art,
      item:function(name){
        var ref = typeof iwItemRefIfKnown === 'function' ? iwItemRefIfKnown(name) : iwTipEsc(name);
        var found = typeof iwTipFindItem === 'function' ? iwTipFindItem({name:name}) : null;
        var id = found && (found.id || found.item_id);
        return '<span class="cv-item">'+(id?art(id,name,'📦'):'')+ref+'</span>';
      },
      context:function(){
        var levels = {};
        ['construction','woodcutting','mining'].forEach(function(k){
          var resolved = iwSkillLevels(k);
          // The Gear panel's add-ons are hypothetical. Remove that source;
          // this planner separately adds the user's confirmed current village.
          var hypothetical = resolved.sources.filter(function(s){return s.via === 'addon';})
            .reduce(function(sum,s){return sum+Number(s.value || 0);},0);
          levels[k] = resolved.effectiveLevel == null ? null : resolved.effectiveLevel-hypothetical;
        });
        var house = document.getElementById('housing-tier');
        return {housing:house?Number(house.value):0,levels:levels,gatherYield:iwGatherYield(),
          source:window.IWProfile?'Imported base + equipment':'Manual / toolkit'};
      }
    });
  } catch (error) {
    if (host) host.textContent = 'Construction planner unavailable: '+error.message;
    window.iwConstructionPlannerSelfCheck = function(){return ['Construction planner initialization: '+error.message];};
  }
})();
</script>
'''
insert_before('</body></html>', bridge)
updated = source.encode('utf-8')
assert len(updated) > len(original)
assert updated.count(b'id="iw-embedded-items"') == original.count(b'id="iw-embedded-items"')
assert path.read_bytes() == original, 'Concurrent index.html edit; re-read before applying'
replace_atomically(path, updated)
print('Integrated construction planner:',len(original),'->',len(updated),'bytes')
