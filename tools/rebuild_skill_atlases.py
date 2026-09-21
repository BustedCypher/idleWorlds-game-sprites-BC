"""Rebuild themed skill UI atlases from the approved generated previews.

The image generator preserved the overall layout but not exact sprite
coordinates. Resizing the complete preview and applying the production alpha
mask clipped artwork across neighbouring slots. This tool instead extracts
each generated sprite, removes the baked checkerboard, and fits it into the
corresponding production slot independently.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

from atomic_write import replace_atomically


THEMES = (
    "celestial",
    "forged-metal",
    "glacial",
    "infernal",
    "lunar-spectral",
    "runic-arcane",
    "tempest-oceanic",
    "verdant",
    "voidborn",
)

LOGICAL_SIZE = (860, 463)
PIXEL_RATIO = 2
PHYSICAL_SIZE = tuple(dimension * PIXEL_RATIO for dimension in LOGICAL_SIZE)

# Maximum occupied rectangles from the original 860 x 463 production atlas.
TARGET_BOXES = (
    (6, 6, 134, 145),
    (140, 6, 204, 113),
    (210, 6, 242, 245),
    (248, 6, 467, 79),
    (473, 6, 553, 89),
    (559, 6, 639, 89),
    (6, 251, 66, 356),
    (72, 251, 336, 326),
    (342, 251, 606, 326),
    (6, 362, 94, 457),
    (282, 362, 544, 396),
    (554, 364, 854, 435),
)

# Image generation preserved the composition but shifted individual objects by
# as much as 80 pixels. Theme-specific windows keep every object intact while
# preventing neighbouring sprites from entering the crop.
# The remastered sheets use one consistent three-row composition. Regions
# deliberately overlap the gutters: connected-component selection keeps the
# requested ornament while tolerating small generator shifts between themes.
SOURCE_REGIONS = (
    (0, 0, 385, 410),
    (320, 0, 520, 370),
    (480, 0, 670, 560),
    (620, 0, 1190, 320),
    (1120, 0, 1420, 330),
    (1370, 0, 1710, 330),
    (0, 420, 180, 770),
    (145, 420, 805, 750),
    (755, 420, 1415, 750),
    (0, 690, 260, 920),
    (470, 690, 1135, 920),
    (1040, 680, 1710, 920),
)

SOURCE_REGION_OVERRIDES = {
    # Verdant's generated nav pair sits about 110 px left of the otherwise
    # consistent top-row layout. Without explicit windows, the idle crop picks
    # the active frame and the active crop stretches only its right-hand side.
    "verdant": {
        4: (1000, 0, 1235, 330),
        5: (1225, 0, 1480, 330),
    },
}


def _largest_component(mask: Image.Image) -> Image.Image:
    """Keep the largest connected foreground component in a binary mask."""

    pixels = np.asarray(mask, dtype=np.uint8) > 0
    height, width = pixels.shape
    seen = np.zeros_like(pixels, dtype=bool)
    best: list[tuple[int, int]] = []

    for start_y in range(height):
        for start_x in range(width):
            if not pixels[start_y, start_x] or seen[start_y, start_x]:
                continue
            stack = [(start_y, start_x)]
            seen[start_y, start_x] = True
            component: list[tuple[int, int]] = []
            while stack:
                y, x = stack.pop()
                component.append((y, x))
                for next_y, next_x in (
                    (y - 1, x),
                    (y + 1, x),
                    (y, x - 1),
                    (y, x + 1),
                ):
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and pixels[next_y, next_x]
                        and not seen[next_y, next_x]
                    ):
                        seen[next_y, next_x] = True
                        stack.append((next_y, next_x))
            if len(component) > len(best):
                best = component

    output = np.zeros((height, width), dtype=np.uint8)
    for y, x in best:
        output[y, x] = 255
    return Image.fromarray(output, mode="L")


def _foreground_mask(
    image: Image.Image,
    background_range: tuple[float, float],
    grow_iterations: int = 5,
) -> Image.Image:
    """Remove the preview's near-white generated checkerboard background."""

    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    lightness = rgb.mean(axis=2)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)

    background_low, background_high = background_range
    # Strongly coloured pixels and tones outside the two checkerboard levels
    # seed the sprite. A permissive connected edge mask retains pale silver
    # and ice without admitting either checkerboard shade.
    core = (
        (saturation > 18)
        | (lightness < background_low - 16)
        | (lightness > background_high + 10)
    )
    soft = (
        (saturation > 6)
        | (lightness < background_low - 4)
        | (lightness > background_high + 4)
    )
    core_image = Image.fromarray((core * 255).astype(np.uint8), mode="L")
    soft_image = Image.fromarray((soft * 255).astype(np.uint8), mode="L")

    grown = core_image
    for _ in range(grow_iterations):
        grown = ImageChops.multiply(grown.filter(ImageFilter.MaxFilter(5)), soft_image)
    return _largest_component(grown)


def _extract_sprite(
    preview: Image.Image,
    region: tuple[int, int, int, int],
    background_range: tuple[float, float],
    grow_iterations: int = 5,
    trim_detached_tail: bool = False,
) -> Image.Image:
    crop = preview.crop(region).convert("RGBA")
    source_alpha = crop.getchannel("A")
    if source_alpha.getextrema()[0] < 255:
        alpha = source_alpha
    else:
        alpha = _foreground_mask(crop, background_range, grow_iterations)
    if trim_detached_tail:
        row_widths = (np.asarray(alpha) > 0).sum(axis=1)
        for row in range(int(len(row_widths) * 0.7), len(row_widths) - 12):
            if row_widths[row] <= 2 and row_widths[row + 1 : row + 12].max() > 8:
                crop = crop.crop((0, 0, crop.width, row + 1))
                alpha = alpha.crop((0, 0, alpha.width, row + 1))
                break
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError(f"No sprite found in source region {region}")
    # Generated RGB sheets carry white in pixels outside their artwork. A hard
    # alpha cut followed by resampling pulls that white into the edge and makes
    # the halo seen in the browser. Bleed the nearest foreground colour a few
    # pixels outward, then soften only the coverage channel.
    source_rgb = np.asarray(crop.convert("RGB"), dtype=np.uint8)
    rgb = source_rgb.copy()
    filled = np.asarray(alpha, dtype=np.uint8) > 0
    for _ in range(4):
        sums = np.zeros_like(rgb, dtype=np.uint16)
        counts = np.zeros(filled.shape, dtype=np.uint8)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            shifted_filled = np.roll(filled, (dy, dx), axis=(0, 1))
            shifted_rgb = np.roll(rgb, (dy, dx), axis=(0, 1))
            if dy < 0:
                shifted_filled[dy:] = False
            elif dy > 0:
                shifted_filled[:dy] = False
            if dx < 0:
                shifted_filled[:, dx:] = False
            elif dx > 0:
                shifted_filled[:, :dx] = False
            sums += shifted_rgb.astype(np.uint16) * shifted_filled[..., None]
            counts += shifted_filled
        frontier = ~filled & (counts > 0)
        rgb[frontier] = (sums[frontier] / counts[frontier, None]).astype(np.uint8)
        filled |= frontier

    softened = np.asarray(
        alpha.filter(ImageFilter.GaussianBlur(radius=0.7)), dtype=np.float32
    ) / 255.0

    # Recover coverage from an opaque white render. The multiplier makes solid
    # pale metal stay opaque while a near-white antialias pixel becomes
    # translucent. Unmatting reverses the white compositing in those pixels;
    # this is what removes the light outline over the game's near-black panels.
    white_coverage = np.clip(
        (255.0 - source_rgb.astype(np.float32).min(axis=2)) * 6.0 / 255.0,
        0.0,
        1.0,
    )
    coverage = np.minimum(softened, white_coverage)
    safe_coverage = np.maximum(coverage, 1.0 / 255.0)
    unmatted = (
        source_rgb.astype(np.float32)
        - 255.0 * (1.0 - coverage[..., None])
    ) / safe_coverage[..., None]
    visible = coverage > 0
    rgb[visible] = np.clip(unmatted[visible], 0, 255).astype(np.uint8)
    output_alpha = np.rint(coverage * 255.0).astype(np.uint8)
    rgba = Image.fromarray(
        np.dstack((rgb, output_alpha)), mode="RGBA")
    return rgba.crop(bounds)


def rebuild_atlas(base_atlas: Image.Image, preview: Image.Image, theme: str) -> Image.Image:
    if base_atlas.size != LOGICAL_SIZE:
        raise ValueError(f"Expected 860 x 463 base atlas, got {base_atlas.size}")
    if not 920 <= preview.height <= 921 or not 1708 <= preview.width <= 1710:
        raise ValueError(f"Expected an approximately 1710 x 920 preview, got {preview.size}")
    if preview.size != (1710, 920):
        preview = preview.resize((1710, 920), Image.Resampling.LANCZOS)

    empty_sample = np.asarray(preview.crop((650, 230, 1050, 430)), dtype=np.int16)
    sample_saturation = empty_sample.max(axis=2) - empty_sample.min(axis=2)
    neutral_lightness = empty_sample.mean(axis=2)[sample_saturation <= 4]
    if neutral_lightness.size < 1000:
        raise ValueError("Could not estimate the generated checkerboard colours")
    background_range = (
        float(np.percentile(neutral_lightness, 8)),
        float(np.percentile(neutral_lightness, 92)),
    )

    source_regions = list(SOURCE_REGIONS)
    for index, region in SOURCE_REGION_OVERRIDES.get(theme, {}).items():
        source_regions[index] = region

    atlas = Image.new("RGBA", PHYSICAL_SIZE, (0, 0, 0, 0))
    for index, (region, target) in enumerate(
        zip(source_regions, TARGET_BOXES, strict=True)
    ):
        sprite = _extract_sprite(
            preview,
            region,
            background_range,
            grow_iterations=2 if index == 2 else 5,
            trim_detached_tail=(index == 2 and theme in {"glacial", "verdant"}),
        )
        left, top, right, bottom = (value * PIXEL_RATIO for value in target)
        padding = PIXEL_RATIO
        width = right - left - padding * 2
        height = bottom - top - padding * 2
        # Generated ornaments vary slightly in aspect ratio. Stretching every
        # crop to both slot dimensions independently warped flourishes, frames,
        # and corner connection points. Fit proportionally inside the fixed
        # logical slot instead. The corner sprite is registered to the outer
        # top-left edges; all standalone ornaments are optically centred.
        sprite = ImageOps.contain(
            sprite, (width, height), Image.Resampling.LANCZOS)
        if index == 9:
            offset_x = 0
            offset_y = 0
        else:
            offset_x = (width - sprite.width) // 2
            offset_y = (height - sprite.height) // 2
        atlas.alpha_composite(
            sprite,
            (left + padding + offset_x, top + padding + offset_y),
        )
    return atlas


def _write_image(path: Path, image: Image.Image, image_format: str, **options) -> None:
    """Encode to memory, then swap the finished bytes into place.

    `image.save(path, ...)` truncates `path` the instant it opens it, before
    the encoder has produced a single byte — so a failure part-way through
    (an unencodable mode, a full disk, a killed process) leaves a 0-byte or
    half-written PNG where the previous atlas used to be, with no rollback.
    This tool re-runs over its own output directory, so that target is
    routinely a real, good atlas rather than a fresh file.

    That is the exact shape of the 2026-09-04 incident that emptied
    index.html. `tools/atomic_write.py` exists for it, and
    `tests/test_no_unsafe_writes.py` enforces the route.
    """
    encoded = io.BytesIO()
    image.save(encoded, format=image_format, **options)
    replace_atomically(path, encoded.getvalue())


def rebuild_all(base_path: Path, preview_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(base_path) as base_image:
        base = base_image.convert("RGBA")
        for theme in THEMES:
            preview_path = preview_dir / f"{theme}.png"
            with Image.open(preview_path) as preview_image:
                atlas = rebuild_atlas(base, preview_image.convert("RGBA"), theme)
            stem = f"skills_ui_atlas_theme_{theme}"
            _write_image(output_dir / f"{stem}.png", atlas, "PNG", optimize=True)
            _write_image(output_dir / f"{stem}.webp", atlas, "WEBP",
                         lossless=True, method=6)
            print(f"rebuilt {theme}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-atlas", required=True, type=Path)
    parser.add_argument("--preview-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rebuild_all(args.base_atlas, args.preview_dir, args.output_dir)


if __name__ == "__main__":
    main()
