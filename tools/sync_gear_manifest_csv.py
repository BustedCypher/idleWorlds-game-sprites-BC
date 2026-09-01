#!/usr/bin/env python3
import csv,json
from pathlib import Path
def sync(root:Path):
    icons=json.loads((root/'gear_icons_manifest.json').read_text())['icons']; fields=['name','index','row','column','x','y','width','height']
    with (root/'gear_icons_manifest.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\r\n'); w.writeheader()
        for icon in icons:w.writerow({k:icon[k] for k in fields})
if __name__=='__main__':sync(Path(__file__).resolve().parents[1])
