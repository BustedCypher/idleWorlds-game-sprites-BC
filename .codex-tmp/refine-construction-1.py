from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from atomic_write import replace_atomically
root = Path(__file__).resolve().parents[1]

def update(relative, replacements, append=''):
    path=root/relative
    original=path.read_bytes()
    text=original.decode('utf-8')
    for old,new,expected in replacements:
        assert text.count(old)==expected,(relative,old,text.count(old))
        text=text.replace(old,new)
    text+=append
    assert path.read_bytes()==original,'Concurrent write: '+relative
    replace_atomically(path,text.encode('utf-8'))

update('assets/construction-planner.css',[], '''
#cv-root .cv-item { display:flex; align-items:center; gap:7px; }
#cv-root .cv-item .iw-item-sprite-host { flex:none; width:28px; height:28px; }
#cv-root .cv-item .iw-item-ref { min-width:0; }
@media(max-width:760px) { #cv-root .cv-item .iw-item-sprite-host { display:none; } }
''')
update('index.html',[
 ('<span class="tab-label">Construction &amp; Village Planner</span>','<span class="tab-label">Construction Planner</span>',2),
 ("  document.querySelector('.wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });", "  if (name === 'construction-village') window.scrollTo({top:0,behavior:'smooth'});\n  else document.querySelector('.wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });",1)
])
update('assets/construction-planner.js',[
 ("      var out = [];\n      tiers.forEach", "      var out = [];\n      if ($$('[data-cv-field]').some(function(e){return !e.checkValidity();})) out.push('Correct the highlighted player value.');\n      tiers.forEach",1),
 ("      if(e.dataset.cvSearch!=null)", "      if(e.dataset.cvField){e.setAttribute('aria-invalid',e.checkValidity()?'false':'true');if(!e.checkValidity())refreshResults(true);}\n      if(e.dataset.cvSearch!=null)",1),
 ("      if(e.dataset.cvField){var field=e.dataset.cvField;", "      if(e.dataset.cvField){if(!e.checkValidity()){e.setAttribute('aria-invalid','true');refreshResults(true);return;}e.setAttribute('aria-invalid','false');var field=e.dataset.cvField;",1)
])
update('.codex-tmp/construction-village-progress.md',[("Task 1: in progress.","Task 1: complete. Engine tests: 11/11; read-only task review approved.\nTask 2: in progress. UI state tests: 3/3. Desktop/mobile navigation integrated; browser validation in progress.\nBaseline: Python suite fails on two unsafe writes in unrelated, pre-existing untracked tools/rebuild_skill_atlases.py. Icon tests 7/7, original inline script check clean.",1)])
print('Refined planner layout, field validation and integration')
