#!/usr/bin/env python3
"""Build deterministic, demand-loadable icon chunks from legacy atlases."""
from __future__ import annotations
import csv, hashlib, io, json, math, re, shutil, unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any
from PIL import Image

CELL=128; MAX_COLUMNS=10
def normalise_name(value:Any)->str:
    s=unicodedata.normalize('NFKD',str(value or '').strip())
    s=''.join(c for c in s if not unicodedata.combining(c))
    s=re.sub("[\u2018\u2019\u02bc`\u00b4]","'",s).replace('&',' and ').replace("'",'')
    s=re.sub(r'\blv\.\s*','lv ',s,flags=re.I)
    return re.sub(r'[^a-z0-9]+',' ',s,flags=re.I).strip().lower()
def split_upgrade(name:str)->tuple[str,int]:
    m=re.search(r'\s*\+\s*([1-4])\s*$',name)
    return (name[:m.start()].strip(),int(m.group(1))) if m else (name.strip(),0)
def items_from(html:str):
    m=re.search(r'<script[^>]*id=["\']iw-embedded-items["\'][^>]*>([\s\S]*?)</script>',html,re.I)
    p=json.loads(m.group(1)); return p if isinstance(p,list) else p['items']
def aliases_from(html:str,root:Path):
    m=re.search(r'var\s+GEAR_ICON_NAME_ALIASES\s*=\s*Object\.freeze\((\{[\s\S]*?\})\);',html)
    if m: raw=json.loads(m.group(1))
    else:
        found=sorted((root/'assets/icons/v2').glob('icon-manifest.*.json'))
        if len(found)!=1: raise ValueError('aliases unavailable')
        raw=json.loads(found[0].read_text(encoding='utf-8'))['gear']['aliases']
    return {normalise_name(k):normalise_name(v) for k,v in raw.items()}
def slot_slug(s:str)->str:
    v=str(s).removesuffix(' slot').strip().lower()
    return {'helm':'helmet','relic':'trinket','leggings':'legs'}.get(v,v)
def compact(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def file_hash(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_chunk(out:Path,family:str,name:str,source:Image.Image,records:list[dict]):
    cols=min(MAX_COLUMNS,max(1,len(records))); rows=max(1,math.ceil(len(records)/cols))
    image=Image.new('RGBA',(cols*CELL,rows*CELL),(0,0,0,0))
    for i,r in enumerate(records):
        x=i%cols*CELL; y=i//cols*CELL
        cell=source.crop((r['source_x'],r['source_y'],r['source_x']+CELL,r['source_y']+CELL))
        image.paste(cell,(x,y)); r.update(x=x,y=y,sha256_rgba=hashlib.sha256(cell.tobytes()).hexdigest())
    buf=io.BytesIO(); image.save(buf,format='PNG',compress_level=9,optimize=False); data=buf.getvalue()
    digest=hashlib.sha256(data).hexdigest(); filename=f'{name}.{digest[:12]}.png'; (out/filename).write_bytes(data)  # guard-ok: brand-new hashed chunk in a dir this run just created
    return f'{family}:{name}',dict(path=filename,width=image.width,height=image.height,columns=cols,rows=rows,cell_count=len(records),sha256_png=digest)

def build_icon_chunks(repo_root:Path)->Path:
    root=Path(repo_root).resolve(); html=(root/'index.html').read_text(encoding='utf-8'); items=items_from(html); aliases=aliases_from(html,root)
    gear_manifest=json.loads((root/'gear_icons_manifest.json').read_text(encoding='utf-8'))
    out=root/'assets/icons/v2'; shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True)
    base_slots={}
    for item in items:
        if item.get('category')!='Equipment': continue
        base,_=split_upgrade(str(item.get('name',''))); key=normalise_name(base); slot=slot_slug(item.get('subcategory',''))
        if key in base_slots and base_slots[key]!=slot: raise ValueError('slot conflict '+base)
        base_slots[key]=slot
    reverse=defaultdict(list)
    for current,atlas in aliases.items(): reverse[atlas].append(current)
    groups=defaultdict(list)
    for entry in gear_manifest['icons']:
        name=str(entry['name']); _,up=split_upgrade(name); key=normalise_name(name)
        record=dict(name=name,normalised_name=key,source_index=int(entry['index']),source_x=int(entry['x']),source_y=int(entry['y']))
        if up and name.strip().startswith('+'): group='overlays'
        else:
            group=base_slots.get(key,'') or next((base_slots[a] for a in reverse.get(key,[]) if a in base_slots),'')
            if not group: raise ValueError('unassigned gear '+name)
        groups[group].append(record)
    runtime={'version':2,'cell_size':128,'display_cell_size':64,'chunks':{},'gear':{'icons':{},'aliases':aliases,'upgrades':{}},'items':{'icons':{},'cells':{}}}
    audit={'gear_records':[],'item_cells':[],'source':{}}
    gear_path=root/'gear_icons_atlas.png'
    with Image.open(gear_path) as im:
        source=im.convert('RGBA'); audit['source']['gear']={'path':gear_path.name,'sha256_png':file_hash(gear_path),'width':source.width,'height':source.height}
        for group in sorted(groups):
            records=sorted(groups[group],key=lambda r:r['source_index']); ck,meta=write_chunk(out,'gear',group,source,records); runtime['chunks'][ck]=meta
            for r in records:
                r['chunk']=ck
                if group=='overlays': runtime['gear']['upgrades'][str(split_upgrade(r['name'])[1])]=[ck,r['x'],r['y']]
                else: runtime['gear']['icons'][r['normalised_name']]=[ck,r['x'],r['y']]
                audit['gear_records'].append(r)
    with (root/'item_icons_index.csv').open(newline='',encoding='utf-8-sig') as f: index=list(csv.DictReader(f))
    with (root/'item_icons_cells.csv').open(newline='',encoding='utf-8-sig') as f: cells={int(r['index']):r for r in csv.DictReader(f)}
    by_id={str(i.get('item_id','')):i for i in items if i.get('category')!='Equipment'}; categories=defaultdict(set)
    for r in index:
        if r['item_id'] not in by_id: raise ValueError('unknown id '+r['item_id'])
        categories[int(r['index'])].add(by_id[r['item_id']]['category'])
    cat_slug={'Resource':'resources','Processed':'processed','Trade Good':'trade','Consumable':'consumables'}; item_groups=defaultdict(list); cell_keys={}
    for ix,cell in cells.items():
        if len(categories[ix])!=1: raise ValueError('cross category cell')
        group=cat_slug[next(iter(categories[ix]))]; key=cell.get('icon_key') or f'cell.{ix}'; cell_keys[ix]=key
        item_groups[group].append({'cell_key':key,'source_index':ix,'source_x':int(cell['x']),'source_y':int(cell['y']),'name':cell.get('name','')})
    item_path=root/'item_icons_atlas.png'
    with Image.open(item_path) as im:
        source=im.convert('RGBA'); audit['source']['items']={'path':item_path.name,'sha256_png':file_hash(item_path),'width':source.width,'height':source.height}
        for group in sorted(item_groups):
            records=sorted(item_groups[group],key=lambda r:r['source_index']); ck,meta=write_chunk(out,'items',group,source,records); runtime['chunks'][ck]=meta
            for r in records:
                r['chunk']=ck; runtime['items']['cells'][r['cell_key']]=[ck,r['x'],r['y']]; audit['item_cells'].append(r)
    for r in index: runtime['items']['icons'][r['item_id']]=cell_keys[int(r['index'])]
    audit['counts']={'gear_physical_cells':len(audit['gear_records']),'item_physical_cells':len(audit['item_cells']),'item_mappings':len(runtime['items']['icons']),'chunks':len(runtime['chunks'])}
    # guard-ok: brand-new hashed audit file, nothing pre-existing to destroy
    ad=compact(audit); an=f'icon-audit.{hashlib.sha256(ad).hexdigest()[:12]}.json'; (out/an).write_bytes(ad); runtime['audit_path']=an
    md=compact(runtime); mn=f'icon-manifest.{hashlib.sha256(md).hexdigest()[:12]}.json'; mp=out/mn; mp.write_bytes(md); return mp  # guard-ok: brand-new hashed manifest
if __name__=='__main__': print(build_icon_chunks(Path(__file__).resolve().parents[1]))
