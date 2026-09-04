#!/usr/bin/env python3
from __future__ import annotations
import hashlib,html as html_lib,json,re,unicodedata
from pathlib import Path
from PIL import Image
def norm(v):
 s=unicodedata.normalize('NFKD',str(v or '').strip());s=''.join(c for c in s if not unicodedata.combining(c));s=re.sub("[\u2018\u2019\u02bc`\u00b4]","'",s).replace('&',' and ').replace("'",'');s=re.sub(r'\blv\.\s*','lv ',s,flags=re.I);return re.sub(r'[^a-z0-9]+',' ',s,flags=re.I).strip().lower()
# Items the atlas deliberately does not cover yet. Every other non-equipment
# record must resolve to a cell, so a NEW uncovered item still fails this gate.
# premium_token (Premium Membership Token) arrived with the v5.4 payload
# refresh and no artwork was supplied for it.
ITEM_ICON_GAPS={'premium_token'}
def section(s,a,b):
 x=s.find(a);y=s.find(b,x+len(a)) if x>=0 else -1;return s[x:y] if x>=0 and y>=0 else ''
def verify(root:Path):
 root=root.resolve();h=(root/'index.html').read_text(encoding='utf-8');mm=re.search(r"manifestUrl:\s*'(\./assets/icons/v2/icon-manifest\.[0-9a-f]{12}\.json)'",h);mp=root/mm.group(1).removeprefix('./');m=json.loads(mp.read_text(encoding='utf-8'));a=json.loads((mp.parent/m['audit_path']).read_text(encoding='utf-8'))
 em=re.search(r'<script[^>]*id=["\']iw-embedded-items["\'][^>]*>([\s\S]*?)</script>',h,re.I);p=json.loads(em.group(1));items=p if isinstance(p,list) else p['items']; gear=[i for i in items if i.get('category')=='Equipment'];other=[i for i in items if i.get('category')!='Equipment']
 gm=[];im=[];ups={str(i):0 for i in range(1,5)}
 for item in gear:
  name=str(item.get('name',''));s=re.search(r'\s*\+\s*([1-4])\s*$',name);base=name[:s.start()].strip() if s else name;k=norm(base);k=m['gear']['aliases'].get(k,k)
  if k not in m['gear']['icons']:gm.append(name)
  if s: ups[s.group(1)]+=1; gm.extend([] if s.group(1) in m['gear']['upgrades'] else ['overlay:'+name])
 for item in other:
  key=m['items']['icons'].get(str(item.get('item_id','')))
  if not key or key not in m['items']['cells']:im.append(str(item.get('item_id')))
 static=[]
 for raw in re.findall(r'data-iw-gear-sprite="([^"]*)"',h):
  name=html_lib.unescape(raw).strip()
  if not name:continue
  s=re.search(r'\s*\+\s*[1-4]\s*$',name);k=norm(name[:s.start()].strip() if s else name);k=m['gear']['aliases'].get(k,k)
  if k not in m['gear']['icons']:static.append('gear:'+name)
 for raw in re.findall(r'data-iw-item-sprite="([^"]*)"',h):
  item_id=html_lib.unescape(raw).strip()
  if item_id and item_id not in m['items']['icons']:static.append('item:'+item_id)
 errors=[];images={}
 for key,meta in m['chunks'].items():
  path=mp.parent/meta['path']
  if not path.is_file():errors.append(key+':missing');continue
  if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256_png']:errors.append(key+':hash')
  try:
   image=Image.open(path).convert('RGBA');images[key]=image
   if image.size!=(meta['width'],meta['height']):errors.append(key+':dimensions')
  except Exception as e:errors.append(key+':decode:'+str(e))
 mismatches=[];gs=Image.open(root/'gear_icons_atlas.png').convert('RGBA');its=Image.open(root/'item_icons_atlas.png').convert('RGBA')
 def compare(r,source,label):
  out=images.get(r['chunk']);src=source.crop((r['source_x'],r['source_y'],r['source_x']+128,r['source_y']+128));dst=out.crop((r['x'],r['y'],r['x']+128,r['y']+128)) if out else None
  if dst is None or src.tobytes()!=dst.tobytes() or hashlib.sha256(dst.tobytes()).hexdigest()!=r['sha256_rgba']:mismatches.append(label)
 for r in a['gear_records']:compare(r,gs,'gear:'+r['name'])
 for r in a['item_cells']:compare(r,its,'item:'+r['cell_key'])
 gs.close();its.close();[x.close() for x in images.values()]
 tip=section(h,'function iwTipShow','function iwTipHide');render=section(h,'function iwTipRender','function iwTipOpenEntry');man=section(h,'function gnRenderSlots','function gnRenderStats');mantip=section(h,'window.gnOpenTooltip','window.gnCloseTooltip')
 checks={'external_loader':'assets/icon-sprites-v2.js' in h,'no_legacy_requests':'gear_icons_atlas.png?v=' not in h and 'item_icons_atlas.png?v=' not in h and 'raw.githubusercontent.com/BustedCypher/idleWorlds-game-sprites-BC/main/' not in h,'gear_tip_markup':'IW_GEAR_SPRITES.markup(item.name' in render,'item_tip_markup':'IW_ITEM_SPRITES.markup(item.id' in render,'gear_tip_hydrate':'IW_GEAR_SPRITES.hydrate(el)' in tip,'item_tip_hydrate':'IW_ITEM_SPRITES.hydrate(el)' in tip,'mannequin_mount':'IW_GEAR_SPRITES.mount' in man,'mannequin_tip':'IW_GEAR_SPRITES.hydrate(head)' in mantip,'ready_css':'.iw-gear-sprite-host[data-iw-sprite-state="ready"] .iw-gear-sprite-base' in h and '.iw-item-sprite-host[data-iw-item-sprite-state="ready"] .iw-item-sprite-base' in h,'serialized_ready_absent':not re.search(r'<(?:span|div)\b[^>]*(?:data-iw-sprite-state|data-iw-item-sprite-state)="ready"',h,re.I)}
 unhashed=[x.name for x in mp.parent.glob('*.png') if not re.search(r'\.[0-9a-f]{12}\.png$',x.name)]
 unexpected=[x for x in im if x not in ITEM_ICON_GAPS]
 ok=len(items)==4452 and len(gear)==3182 and len(other)==1270 and len(a['gear_records'])==1146 and len(a['item_cells'])==477 and ups=={'1':510,'2':510,'3':510,'4':510} and len(m['chunks'])==17 and not(gm or unexpected or static or errors or mismatches or unhashed) and all(checks.values())
 return {'status':'ok' if ok else 'failed','items':len(items),'gear':len(gear),'other':len(other),'gear_cells':len(a['gear_records']),'item_cells':len(a['item_cells']),'upgrades':ups,'chunks':len(m['chunks']),'gear_missing':gm,'item_missing':im,'item_missing_unexpected':unexpected,'static_missing':static,'chunk_errors':errors,'pixel_mismatches':mismatches,'unhashed':unhashed,'checks':checks}
if __name__=='__main__':
 import sys;result=verify(Path(__file__).resolve().parents[1]);print(json.dumps(result,indent=2,sort_keys=True));raise SystemExit(0 if result['status']=='ok' else 1)
