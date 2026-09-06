from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    thumb_width, thumb_height, label_height = 430, 232, 26
    sheet = Image.new(
        "RGBA",
        (thumb_width * 3, (thumb_height + label_height) * 3),
        (24, 24, 28, 255),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)

    for index, theme in enumerate(THEMES):
        source = args.source_dir / f"skills_ui_atlas_theme_{theme}.png"
        atlas = Image.open(source).convert("RGBA")
        preview = Image.new("RGBA", atlas.size, (12, 12, 15, 255))
        preview.alpha_composite(atlas)
        preview.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)

        left = (index % 3) * thumb_width
        top = (index // 3) * (thumb_height + label_height)
        sheet.alpha_composite(preview, (left, top))
        draw.text(
            (left + 8, top + thumb_height + 4),
            theme,
            fill=(235, 235, 240, 255),
            font=font,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(args.output, optimize=True)


if __name__ == "__main__":
    main()
