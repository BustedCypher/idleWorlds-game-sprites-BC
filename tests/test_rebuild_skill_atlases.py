import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# numpy is an OPTIONAL dependency: it belongs to this art tool, not to the
# toolkit. Importing it at module scope made `python -m unittest discover -s
# tests` ERROR on any machine without it — which took the whole run red and
# buried test_no_unsafe_writes, the gate that actually protects index.html.
# A missing art dependency must degrade to "skipped", never to "the gate is
# unreadable". Install it with `pip install -r requirements-dev.txt`.
try:
    import numpy as np
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment-dependent
    np = None
    Image = None
    _MISSING = str(exc)
else:
    _MISSING = ""


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "rebuild_skill_atlases.py"
BASE_ATLAS = ROOT / "assets" / "skills-ui-atlas" / "source" / "skills_ui_atlas_original.webp"
PREVIEW_DIR = ROOT / "assets" / "skills-ui-atlas" / "source-previews"
THEME_MAP = ROOT / "assets" / "skills-ui-atlas" / "families" / "zone-theme-map.json"

LOGICAL_SIZE = (860, 463)
PIXEL_RATIO = 2
PHYSICAL_SIZE = tuple(dimension * PIXEL_RATIO for dimension in LOGICAL_SIZE)

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

# Hand-checked from the original production atlas. These are the maximum
# occupied rectangles for the twelve independent sprites.
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


def setUpModule() -> None:
    """Skip the whole module when its optional deps are absent.

    Raised here rather than decorating each test so the reason is reported
    once, and so `discover` still returns a clean, readable result for the
    gates that matter."""
    if _MISSING:
        raise unittest.SkipTest(
            f"{_MISSING} - optional; pip install -r requirements-dev.txt")


class RebuildSkillAtlasesTest(unittest.TestCase):
    def test_theme_map_declares_logical_canvas_and_physical_pixel_ratio(self):
        import json

        data = json.loads(THEME_MAP.read_text(encoding="utf-8"))
        self.assertEqual(data["canvas"], {"width": 860, "height": 463})
        self.assertEqual(data["pixelRatio"], PIXEL_RATIO)

    def test_rebuilds_complete_unclipped_atlases_in_original_slots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--base-atlas",
                    str(BASE_ATLAS),
                    "--preview-dir",
                    str(PREVIEW_DIR),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            for theme in THEMES:
                png_path = output_dir / f"skills_ui_atlas_theme_{theme}.png"
                webp_path = output_dir / f"skills_ui_atlas_theme_{theme}.webp"
                self.assertTrue(png_path.is_file(), theme)
                self.assertTrue(webp_path.is_file(), theme)

                with Image.open(png_path) as png_image:
                    png = png_image.convert("RGBA")
                with Image.open(webp_path) as webp_image:
                    webp = webp_image.convert("RGBA")

                self.assertEqual(png.size, PHYSICAL_SIZE, theme)
                self.assertEqual(png.mode, "RGBA", theme)
                png_pixels = np.asarray(png)
                webp_pixels = np.asarray(webp)
                self.assertTrue(
                    np.array_equal(png_pixels[:, :, 3], webp_pixels[:, :, 3]),
                    f"{theme}: WebP alpha differs from PNG",
                )
                visible = png_pixels[:, :, 3] > 0
                self.assertTrue(
                    np.array_equal(png_pixels[:, :, :3][visible], webp_pixels[:, :, :3][visible]),
                    f"{theme}: WebP visible pixels differ from PNG",
                )

                alpha = png.getchannel("A")
                allowed = Image.new("1", png.size, 0)
                for logical_box in TARGET_BOXES:
                    box = tuple(value * PIXEL_RATIO for value in logical_box)
                    allowed.paste(1, box)
                    sprite_alpha = alpha.crop(box)
                    self.assertIsNotNone(sprite_alpha.getbbox(), f"{theme}: empty slot {logical_box}")
                    occupied = sum(1 for value in sprite_alpha.getdata() if value > 8)
                    self.assertGreater(
                        occupied,
                        sprite_alpha.width * sprite_alpha.height * 0.08,
                        f"{theme}: under-filled slot {box}",
                    )

                # The idle/active nav frames (slots 4 and 5) are the same
                # ornament, so their opaque widths must match. A crop window
                # that slices one side off leaves the occupancy check above
                # satisfied; this catches it. Healthy themes sit at 0.947+;
                # the clipped lunar-spectral idle frame was 106 vs 142 = 0.746.
                def opaque_width(logical_box):
                    x0, y0, x1, y1 = (value * PIXEL_RATIO for value in logical_box)
                    columns = np.where((png_pixels[y0:y1, x0:x1, 3] > 40).sum(axis=0) > 20)[0]
                    return int(columns.max() - columns.min() + 1) if columns.size else 0

                idle_width = opaque_width(TARGET_BOXES[4])
                active_width = opaque_width(TARGET_BOXES[5])
                self.assertGreaterEqual(
                    min(idle_width, active_width) / max(idle_width, active_width, 1),
                    0.9,
                    f"{theme}: nav frames differ in width ({idle_width} vs {active_width}) - one is clipped",
                )

                outside = Image.new("L", png.size, 0)
                outside.paste(alpha)
                outside.paste(0, mask=allowed)
                self.assertIsNone(outside.getbbox(), f"{theme}: sprite escaped its atlas slot")

                partial_alpha = np.logical_and(png_pixels[:, :, 3] > 0, png_pixels[:, :, 3] < 255)
                self.assertGreater(
                    int(partial_alpha.sum()),
                    1000,
                    f"{theme}: antialiased edge coverage is missing",
                )
                if theme in {"infernal", "runic-arcane", "tempest-oceanic", "verdant", "voidborn"}:
                    rgb = png_pixels[:, :, :3]
                    lightness = rgb.mean(axis=2)
                    saturation = rgb.max(axis=2) - rgb.min(axis=2)
                    bright_neutral = np.logical_and.reduce((
                        png_pixels[:, :, 3] > 32,
                        lightness > 245,
                        saturation < 8,
                    ))
                    self.assertLess(
                        int(bright_neutral.sum()),
                        3000,
                        f"{theme}: bright neutral matte remains around the sprites",
                    )

                for logical_box in TARGET_BOXES[4:6]:
                    box = tuple(value * PIXEL_RATIO for value in logical_box)
                    nav = np.asarray(alpha.crop(box)) > 8
                    edge_width = max(1, nav.shape[1] // 5)
                    minimum_edge_ink = nav.shape[0] * edge_width * 0.08
                    self.assertGreater(
                        int(nav[:, :edge_width].sum()), minimum_edge_ink,
                        f"{theme}: square frame is missing its left edge",
                    )
                    self.assertGreater(
                        int(nav[:, -edge_width:].sum()), minimum_edge_ink,
                        f"{theme}: square frame is missing its right edge",
                    )
                    nav_rgb = png_pixels[box[1]:box[3], box[0]:box[2], :3].astype(np.int16)
                    mirror_error = np.abs(nav_rgb - nav_rgb[:, ::-1]).mean()
                    self.assertLess(
                        mirror_error,
                        70,
                        f"{theme}: square frame crop is horizontally distorted",
                    )

                # Generated objects do not all share the destination slot's
                # aspect ratio. The rebuild must letterbox them rather than
                # independently scaling X and Y, which visibly stretches the
                # inventory flourish and misaligns theme corners. These
                # literal ranges are hand-measured from the source previews.
                def strong_ink_aspect(logical_box):
                    box = tuple(value * PIXEL_RATIO for value in logical_box)
                    mask = alpha.crop(box).point(
                        lambda value: 255 if value >= 160 else 0)
                    bounds = mask.getbbox()
                    self.assertIsNotNone(bounds, f"{theme}: no strong sprite ink")
                    return (bounds[2] - bounds[0]) / (bounds[3] - bounds[1]), bounds

                if theme == "celestial":
                    aspect, _ = strong_ink_aspect(TARGET_BOXES[3])
                    self.assertTrue(2.35 < aspect < 2.55, aspect)
                if theme == "lunar-spectral":
                    # Source idle frame: 202 x 231 px = 0.874. The old
                    # 0.62-0.72 range was measured off the CLIPPED crop
                    # (0.66) and pinned the bug it should have caught.
                    aspect, _ = strong_ink_aspect(TARGET_BOXES[4])
                    self.assertTrue(0.82 < aspect < 0.93, aspect)
                if theme == "runic-arcane":
                    aspect, bounds = strong_ink_aspect(TARGET_BOXES[9])
                    self.assertTrue(1.18 < aspect < 1.36, aspect)
                    self.assertLessEqual(bounds[0], 8, bounds)
                    self.assertLessEqual(bounds[1], 8, bounds)
                if theme == "voidborn":
                    aspect, _ = strong_ink_aspect(TARGET_BOXES[3])
                    self.assertTrue(2.40 < aspect < 2.70, aspect)

                # The ring and square-button centres are deliberately empty or
                # dark; leaked checkerboard would make these opaque and pale.
                self.assertLess(alpha.getpixel((140, 150)), 16, theme)
                self.assertLess(sum(png.getpixel((1026, 94))[:3]), 300, theme)

                if theme in {"glacial", "verdant"}:
                    vertical_box = tuple(value * PIXEL_RATIO for value in TARGET_BOXES[2])
                    vertical = np.asarray(alpha.crop(vertical_box)) > 8
                    tail_rows = vertical[-12:-1]
                    full_width_tail_rows = (
                        tail_rows.sum(axis=1) >= vertical.shape[1] * 0.75
                    ).sum()
                    self.assertLess(
                        full_width_tail_rows,
                        3,
                        f"{theme}: neighbouring panel leaked into vertical ornament",
                    )


if __name__ == "__main__":
    unittest.main()
