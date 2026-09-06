# Shared zone atlas themes

Nine themed atlases cover all 34 zones. Each atlas is supplied as a lossless WebP for the game and a PNG for inspection or editing.

| Theme | Zones |
| --- | --- |
| Verdant | 1 Greenwake Den, 3 Silverroot Hollow, 34 Primordial Spire |
| Forged Metal | 2 Ironfang Trail, 5 Mythril Bastion, 24 Titanium Wastes |
| Infernal | 4 Goldfire Pass, 9 Dragonfall Ridge, 13 Bloodstone Scar, 15 Sunforge Expanse, 16 Nethergate Chasm, 26 Emberium Caldera, 29 Worldforge Core, 32 Ashspire Ruins |
| Celestial | 6 Starsteel Frontier, 10 Aether Spires, 12 Celestial Crown, 25 Skysteel Pinnacle |
| Voidborn | 7 Obsidian Depths, 11 Voidiron Abyss, 19 Eternium Verge, 20 Astral Crucible, 30 Voidglass Sanctum |
| Runic Arcane | 8 Runic Barrens, 18 Kingsfall Citadel, 21 Gravite Maw, 28 Chronite Spiral |
| Lunar Spectral | 14 Moonsteel Basin, 23 Dusksteel Strand, 27 Soulsteel Necropolis |
| Tempest Oceanic | 17 Stormglass Reach, 31 Thalassic Abyss |
| Glacial | 22 Frostiron Shelf, 33 Glacial Abyss |

All atlases retain the original 860 x 463 canvas and twelve production sprite slots. They are rebuilt sprite-by-sprite from the approved themed previews so ornament edges are not clipped by the original atlas mask. `zone-theme-map.json` is the machine-readable assignment list.

The reproducible sources and rebuild utilities are in `../source-previews/`, `../source/`, and `../../../tools/rebuild_skill_atlases.py`. The superseded broken exports are preserved in `archive-broken-v1/`.
