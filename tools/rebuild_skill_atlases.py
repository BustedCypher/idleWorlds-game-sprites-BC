"""Rebuild themed skill UI atlases from the approved generated previews.

The image generator preserved the overall layout but not exact sprite
coordinates. Resizing the complete preview and applying the production alpha
mask clipped artwork across neighbouring slots. This tool instead extracts
each generated sprite, removes the baked checkerboard, and fits it into the
corresponding production slot independently.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter


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
TOP_SOURCE_REGIONS = {
    "celestial": ((0, 0, 295, 340), (295, 0, 440, 280), (440, 0, 525, 530), (525, 0, 1005, 230), (1005, 0, 1190, 230), (1190, 0, 1380, 230)),
    "forged-metal": ((0, 0, 290, 340), (290, 0, 435, 280), (435, 0, 525, 530), (520, 0, 980, 230), (980, 0, 1155, 230), (1155, 0, 1335, 230)),
    "glacial": ((0, 0, 265, 340), (265, 0, 395, 280), (395, 0, 470, 442), (470, 0, 915, 230), (910, 0, 1078, 230), (1078, 0, 1245, 230)),
    "infernal": ((0, 0, 305, 340), (305, 0, 460, 280), (460, 0, 545, 540), (545, 0, 1025, 230), (1025, 0, 1210, 230), (1210, 0, 1405, 230)),
    "lunar-spectral": ((0, 0, 335, 350), (335, 0, 495, 290), (495, 0, 585, 520), (585, 0, 1100, 230), (1100, 0, 1300, 230), (1300, 0, 1500, 230)),
    "runic-arcane": ((0, 0, 325, 350), (325, 0, 480, 290), (480, 0, 565, 540), (565, 0, 1065, 230), (1065, 0, 1255, 230), (1255, 0, 1460, 230)),
    "tempest-oceanic": ((0, 0, 295, 340), (295, 0, 440, 280), (440, 0, 525, 530), (525, 0, 990, 230), (990, 0, 1170, 230), (1170, 0, 1350, 230)),
    "verdant": ((0, 0, 300, 350), (300, 0, 445, 290), (445, 0, 530, 490), (530, 0, 1010, 230), (1010, 0, 1195, 230), (1195, 0, 1385, 230)),
    "voidborn": ((0, 0, 285, 340), (280, 0, 425, 280), (425, 0, 500, 510), (495, 0, 950, 230), (945, 0, 1118, 230), (1115, 0, 1305, 230)),
}

MIDDLE_SOURCE_REGIONS = {
    "celestial": ((0, 400, 145, 720), (140, 400, 720, 720), (720, 400, 1285, 720)),
    "forged-metal": ((0, 400, 145, 720), (145, 400, 710, 720), (710, 400, 1275, 720)),
    "glacial": ((0, 390, 140, 720), (135, 390, 660, 720), (660, 390, 1190, 720)),
    "infernal": ((0, 400, 150, 730), (145, 400, 750, 730), (750, 400, 1320, 730)),
    "lunar-spectral": ((0, 400, 170, 730), (165, 400, 765, 730), (760, 400, 1300, 730)),
    "runic-arcane": ((0, 400, 160, 730), (155, 400, 745, 730), (740, 400, 1320, 730)),
    "tempest-oceanic": ((0, 400, 150, 730), (145, 400, 720, 730), (715, 400, 1285, 730)),
    "verdant": ((0, 400, 155, 730), (150, 400, 720, 730), (715, 400, 1250, 730)),
    "voidborn": ((0, 400, 150, 730), (145, 400, 690, 730), (685, 400, 1245, 730)),
}

BOTTOM_START = {
    "celestial": 710,
    "forged-metal": 710,
    "glacial": 610,
    "infernal": 710,
    "lunar-spectral": 715,
    "runic-arcane": 710,
    "tempest-oceanic": 710,
    "verdant": 670,
    "voidborn": 690,
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
    crop = preview.crop(region).convert("RGB")
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
    rgba = crop.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba.crop(bounds)


def rebuild_atlas(base_atlas: Image.Image, preview: Image.Image, theme: str) -> Image.Image:
    if base_atlas.size != (860, 463):
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

    bottom_start = BOTTOM_START[theme]
    source_regions = (
        *TOP_SOURCE_REGIONS[theme],
        *MIDDLE_SOURCE_REGIONS[theme],
        (0, bottom_start, 240, 920),
        (480, bottom_start, 1120, 880),
        (1030, bottom_start, 1710, 920),
    )

    atlas = Image.new("RGBA", base_atlas.size, (0, 0, 0, 0))
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
        left, top, right, bottom = target
        width = right - left - 2
        height = bottom - top - 2
        sprite = sprite.resize((width, height), Image.Resampling.LANCZOS)
        atlas.alpha_composite(sprite, (left + 1, top + 1))
    return atlas


def rebuild_all(base_path: Path, preview_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(base_path) as base_image:
        base = base_image.convert("RGBA")
        for theme in THEMES:
            preview_path = preview_dir / f"{theme}.png"
            with Image.open(preview_path) as preview_image:
                atlas = rebuild_atlas(base, preview_image.convert("RGB"), theme)
            stem = f"skills_ui_atlas_theme_{theme}"
            atlas.save(output_dir / f"{stem}.png", "PNG", optimize=True)
            atlas.save(output_dir / f"{stem}.webp", "WEBP", lossless=True, method=6)
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
