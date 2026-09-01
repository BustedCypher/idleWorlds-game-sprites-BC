# Icon atlas splitting specification

Split the two eager legacy atlases into 17 same-origin, content-hashed chunks.
Fetch the compact manifest only when an icon approaches the viewport, cache one
promise per chunk, retain visible fallbacks, preserve all +1 through +4 overlays
and 84 cloak aliases, and keep every generated cell pixel-identical to source.
Acceptance requires all 4,349 records, 1,146 gear cells, 375 item cells and all
Gear/mannequin/tooltip consumers to validate with zero misses.
