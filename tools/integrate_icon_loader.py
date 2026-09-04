#!/usr/bin/env python3
"""Replace eager legacy sprite loaders with the v2 demand loader."""
from __future__ import annotations
import re
from pathlib import Path
from atomic_write import replace_atomically
def integrate(repo_root:Path)->None:
    root=Path(repo_root).resolve(); path=root/'index.html'; html=path.read_text(encoding='utf-8')
    manifests=sorted((root/'assets/icons/v2').glob('icon-manifest.*.json'))
    if len(manifests)!=1: raise ValueError('expected one runtime manifest')
    manifest_url='./assets/icons/v2/'+manifests[0].name
    embedded=re.search(r'(<script[^>]*id=["\']iw-embedded-items["\'][^>]*>[\s\S]*?</script>)',html,re.I)
    if not embedded: raise ValueError('embedded items not found')
    external='\n<script src="./assets/icon-sprites-v2.js"></script>'
    if external.strip() not in html: html=html[:embedded.end()]+external+html[embedded.end():]
    start=html.find('/* ═══════════════════════════════════════════════════════════════\n   GEAR ICON ATLAS')
    end=html.find('// Equipped-set pip grid (mirrors buildSlotPips, but from real gear).',start)
    if start<0 or end<0: raise ValueError('legacy loader boundary not found')
    replacement=f'''/* ═══════════════════════════════════════════════════════════════
   ICON CHUNKS v2 — same-origin, demand-loaded gear and item sprites
   The manifest is fetched only when an icon approaches the viewport; each
   compact atlas chunk is fetched and decoded once, on first use.
   ═══════════════════════════════════════════════════════════════ */
var IW_ICON_SPRITES = window.IWIconSpritesV2.install(window, {{
  manifestUrl: '{manifest_url}'
}});
var IW_GEAR_SPRITES = window.IW_GEAR_SPRITES;
var IW_ITEM_SPRITES = window.IW_ITEM_SPRITES;

window.iwPlus4SpriteBadgeCheck = function iwPlus4SpriteBadgeCheck() {{
  var fail = [];
  try {{
    if (!window.IW_GEAR_SPRITES) return ['IW_GEAR_SPRITES missing'];
    var parsed = IW_GEAR_SPRITES.splitItemName('Copper Sword+4');
    if (!parsed || parsed.base !== 'Copper Sword' || parsed.upgrade !== 4)
      fail.push('Copper Sword+4 parser did not resolve base + upgrade 4');
    var markup = IW_GEAR_SPRITES.markup('Copper Sword+4', '⚔️');
    if (String(markup).indexOf('iw-gear-sprite-upgrade') < 0 || String(markup).indexOf('>+4<') < 0)
      fail.push('+4 markup is missing its upgrade layer or fallback text');
    var status = IW_GEAR_SPRITES.getStatus();
    if (status && status.state === 'ready') {{
      var resolved = IW_GEAR_SPRITES.resolve('Copper Sword+4');
      if (!resolved || !resolved.base || !resolved.overlay)
        fail.push('ready v2 loader did not resolve Copper Sword+4 base and overlay');
    }}
  }} catch (error) {{ fail.push(String(error && error.message || error)); }}
  return fail;
}};

'''
    html=html[:start]+replacement+html[end:]
    gear="""      if (typeof IW_GEAR_SPRITES !== 'undefined' && IW_GEAR_SPRITES &&
          typeof IW_GEAR_SPRITES.hydrate === 'function') IW_GEAR_SPRITES.hydrate(el);
    } catch (e) {}"""
    both=gear+"""
    try {
      if (typeof IW_ITEM_SPRITES !== 'undefined' && IW_ITEM_SPRITES &&
          typeof IW_ITEM_SPRITES.hydrate === 'function') IW_ITEM_SPRITES.hydrate(el);
    } catch (e) {}"""
    if gear not in html: raise ValueError('tooltip hydration not found')
    html=html.replace(gear,both,1)
    def reset(m):
        tag=m.group(0).replace('data-iw-sprite-state="ready"','data-iw-sprite-state="pending"')
        tag=tag.replace('data-iw-item-sprite-state="ready"','data-iw-item-sprite-state="pending"')
        return tag.replace('data-iw-upgrade-state="ready"','data-iw-upgrade-state="pending"')
    html=re.sub(r'<(?:span|div)\b[^>]*>',reset,html,flags=re.I)
    sprite=re.compile(r'(<span\b[^>]*class="[^"]*(?:iw-gear-sprite-base|iw-gear-sprite-upgrade|iw-item-sprite-base)[^"]*"[^>]*)(>)',re.I)
    html=sprite.sub(lambda m:re.sub(r'\sstyle="[^"]*"','',m.group(1),flags=re.I)+m.group(2),html)
    replace_atomically(path,(html.rstrip('\n')+'\n').encode('utf-8'))
if __name__=='__main__': integrate(Path(__file__).resolve().parents[1])
