import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "rebuild_skill_atlases.py"
BASE_ATLAS = ROOT / "assets" / "skills-ui-atlas" / "source" / "skills_ui_atlas_original.webp"
PREVIEW_DIR = ROOT / "assets" / "skills-ui-atlas" / "source-previews"

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


class RebuildSkillAtlasesTest(unittest.TestCase):
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

                self.assertEqual(png.size, (860, 463), theme)
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
                for box in TARGET_BOXES:
                    allowed.paste(1, box)
                    sprite_alpha = alpha.crop(box)
                    self.assertIsNotNone(sprite_alpha.getbbox(), f"{theme}: empty slot {box}")
                    occupied = sum(1 for value in sprite_alpha.get_flattened_data() if value > 8)
                    self.assertGreater(
                        occupied,
                        sprite_alpha.width * sprite_alpha.height * 0.08,
                        f"{theme}: under-filled slot {box}",
                    )

                outside = Image.new("L", png.size, 0)
                outside.paste(alpha)
                outside.paste(0, mask=allowed)
                self.assertIsNone(outside.getbbox(), f"{theme}: sprite escaped its atlas slot")

                # The ring and square-button centres are deliberately empty or
                # dark; leaked checkerboard would make these opaque and pale.
                self.assertLess(alpha.getpixel((70, 75)), 16, theme)
                self.assertLess(sum(png.getpixel((513, 47))[:3]), 300, theme)

                if theme in {"glacial", "verdant"}:
                    vertical = np.asarray(alpha.crop(TARGET_BOXES[2])) > 8
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
