#!/usr/bin/env python3
"""Regenerate gear_icons_manifest.csv from gear_icons_manifest.json."""
import csv,io,json
from pathlib import Path
from atomic_write import write_text_atomically
def sync(root:Path):
    icons=json.loads((root/'gear_icons_manifest.json').read_text(encoding='utf-8'))['icons']; fields=['name','index','row','column','x','y','width','height']
    # Built in memory, then swapped in. This overwrites a tracked 1,146-row
    # file, and a half-written manifest is worse than no edit at all.
    buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=fields,lineterminator='\r\n'); w.writeheader()
    for icon in icons:w.writerow({k:icon[k] for k in fields})
    write_text_atomically(root/'gear_icons_manifest.csv',buf.getvalue(),encoding='utf8')
if __name__=='__main__':sync(Path(__file__).resolve().parents[1])
