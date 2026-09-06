from pathlib import Path
from collections import deque

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


ROOT = Path(r"C:\Users\curti\Desktop\idleWorlds-game-sprites-BC")
SOURCE = Path(r"C:\Users\curti\Desktop\idleworlds-fantasy-skin\assets\skills_ui_atlas.webp")
OUTPUT = ROOT / "assets" / "skills-ui-atlas" / "families"
INDEX = Path(r"C:\Users\curti\Desktop\idleworlds-fantasy-skin\assets\skills_ui_index.json")

JOBS = [
    (
        "verdant",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-7f26f5a0-bf88-4f2a-bd83-6839556927f4.png"),
        "#17120d",
        "#b8d77c",
    ),
    (
        "forged-metal",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-d231f986-5c4d-4e1c-865e-9c1371509955.png"),
        "#0d1218",
        "#d8edf7",
    ),
    (
        "infernal",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-b2b08035-ab9e-477c-8687-f7f6af741440.png"),
        "#160604",
        "#ff9a45",
    ),
    (
        "celestial",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-82e9e356-8acb-4f80-9e52-0c94ca3aef12.png"),
        "#142038",
        "#fff0ae",
    ),
    (
        "voidborn",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-08eb1351-fb5e-403b-a98c-64fa4fa00c2d.png"),
        "#090a10",
        "#8f5ad9",
    ),
    (
        "runic-arcane",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-34ed31fe-ef26-4272-9947-eaeabeccc6c3.png"),
        "#0e1715",
        "#83d7bd",
    ),
    (
        "lunar-spectral",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-4ad5a3ea-c342-4abc-a7e3-84d6d4aec06e.png"),
        "#0b1020",
        "#c4cfff",
    ),
    (
        "tempest-oceanic",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-41634115-e2ea-4c80-9022-acbd1fdfc528.png"),
        "#07151c",
        "#64dce7",
    ),
    (
        "glacial",
        Path(r"C:\Users\curti\.codex\generated_images\01a06971-b76c-7eb1-a0e9-aa458c86cf9d\exec-28143320-43b3-491f-b939-37eaa421dfd0.png"),
        "#132233",
        "#d8f5ff",
    ),
]


def generated_foreground_mask(image: Image.Image) -> Image.Image:
    """Mask away the generator's baked white/gray checkerboard."""
    rgb = image.convert("RGB")
    pixels = []
    for red, green, blue in rgb.getdata():
        chroma = max(red, green, blue) - min(red, green, blue)
        is_checkerboard = min(red, green, blue) > 210 and chroma < 13
        pixels.append(0 if is_checkerboard else 255)
    mask = Image.new("L", rgb.size)
    mask.putdata(pixels)
    return mask


def component_boxes(mask: Image.Image) -> list[tuple[int, int, int, int, int]]:
    scale = 4
    small = mask.resize(
        (max(1, mask.width // scale), max(1, mask.height // scale)),
        Image.Resampling.NEAREST,
    ).filter(ImageFilter.MaxFilter(3))
    pixels = small.load()
    visited = bytearray(small.width * small.height)
    boxes = []
    for start_y in range(small.height):
        for start_x in range(small.width):
            index = start_y * small.width + start_x
            if visited[index] or pixels[start_x, start_y] < 128:
                continue
            queue = deque([(start_x, start_y)])
            visited[index] = 1
            min_x = max_x = start_x
            min_y = max_y = start_y
            area = 0
            while queue:
                x, y = queue.popleft()
                area += 1
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for next_y in range(max(0, y - 1), min(small.height, y + 2)):
                    for next_x in range(max(0, x - 1), min(small.width, x + 2)):
                        next_index = next_y * small.width + next_x
                        if not visited[next_index] and pixels[next_x, next_y] >= 128:
                            visited[next_index] = 1
                            queue.append((next_x, next_y))
            if area >= 35:
                boxes.append((min_x * scale, min_y * scale, (max_x + 1) * scale, (max_y + 1) * scale, area))
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def nearest_valley(projection: np.ndarray, target: float, radius: float) -> int:
    width = projection.shape[0]
    center = int(round(target * width))
    low = max(1, int(round((target - radius) * width)))
    high = min(width - 1, int(round((target + radius) * width)))
    candidates = np.arange(low, high)
    values = projection[low:high]
    minimum = values.min()
    quiet = candidates[values <= minimum + 1]
    return int(quiet[np.argmin(np.abs(quiet - center))])


def valley_between(projection: np.ndarray, target: float, low_fraction: float, high_fraction: float) -> int:
    """Find a quiet cut near target while keeping adjacent searches disjoint."""
    width = projection.shape[0]
    center = int(round(target * width))
    low = max(1, int(round(low_fraction * width)))
    high = min(width - 1, int(round(high_fraction * width)))
    candidates = np.arange(low, high)
    values = projection[low:high]
    minimum = values.min()
    quiet = candidates[values <= minimum + 1]
    return int(quiet[np.argmin(np.abs(quiet - center))])


def generated_regions(mask: Image.Image, slug: str) -> list[tuple[int, int, int, int]]:
    pixels = np.asarray(mask, dtype=np.uint8) >= 128
    height, width = pixels.shape

    top_projection = pixels[: int(height * 0.25), :].sum(axis=0)
    if slug == "glacial":
        # This material pass compacted the two navigation frames farther left.
        top_edges = [
            0,
            int(width * 0.155),
            int(width * 0.231),
            int(width * 0.275),
            int(width * 0.535),
            int(width * 0.628),
            int(width * 0.745),
        ]
    elif slug == "lunar-spectral":
        # This pass places the flourish and navigation pair farther right.
        top_edges = [
            0,
            int(width * 0.195),
            int(width * 0.292),
            int(width * 0.345),
            int(width * 0.646),
            int(width * 0.760),
            int(width * 0.880),
        ]
    else:
        top_cuts = [
            valley_between(top_projection, 0.164, 0.13, 0.20),
            valley_between(top_projection, 0.245, 0.21, 0.28),
            valley_between(top_projection, 0.315, 0.29, 0.36),
            valley_between(top_projection, 0.558, 0.50, 0.63),
            valley_between(top_projection, 0.680, 0.64, 0.76),
        ]
        top_edges = [0, *top_cuts, int(width * 0.86)]

    middle_projection = pixels[int(height * 0.46) : int(height * 0.79), :].sum(axis=0)
    middle_cuts = [nearest_valley(middle_projection, target, 0.04) for target in (0.082, 0.405)]
    middle_edges = [0, *middle_cuts, int(width * 0.76)]

    bottom_projection = pixels[int(height * 0.68) :, :].sum(axis=0)
    bottom_cuts = [nearest_valley(bottom_projection, target, 0.055) for target in (0.22, 0.63)]
    bottom_edges = [0, *bottom_cuts, width]

    regions = [
        (top_edges[0], 0, top_edges[1], int(height * 0.38)),
        (top_edges[1], 0, top_edges[2], int(height * 0.33)),
        (top_edges[2], 0, top_edges[3], int(height * 0.57)),
        (top_edges[3], 0, top_edges[4], int(height * 0.26)),
        (top_edges[4], 0, top_edges[5], int(height * 0.26)),
        (top_edges[5], 0, top_edges[6], int(height * 0.26)),
        (middle_edges[0], int(height * 0.43), middle_edges[1], int(height * 0.80)),
        (middle_edges[1], int(height * 0.43), middle_edges[2], int(height * 0.80)),
        (middle_edges[2], int(height * 0.43), middle_edges[3], int(height * 0.80)),
        (bottom_edges[0], int(height * 0.66), bottom_edges[1], height),
        (bottom_edges[1], int(height * 0.66), bottom_edges[2], height),
        (bottom_edges[2], int(height * 0.66), bottom_edges[3], height),
    ]
    return regions


def crop_foreground(image: Image.Image, mask: Image.Image, region: tuple[int, int, int, int]) -> Image.Image:
    region_image = image.crop(region).convert("RGBA")
    region_mask = mask.crop(region)
    cleaned = region_mask.filter(ImageFilter.MinFilter(3))
    bbox = cleaned.getbbox() or region_mask.getbbox()
    if bbox is None:
        raise RuntimeError(f"No generated ornament found in region {region}")
    left, top, right, bottom = bbox
    left, top = max(0, left - 2), max(0, top - 2)
    right, bottom = min(region_mask.width, right + 2), min(region_mask.height, bottom + 2)
    ornament = region_image.crop((left, top, right, bottom))
    ornament.putalpha(region_mask.crop((left, top, right, bottom)))
    return ornament


def process(job, source: Image.Image) -> tuple[Path, Path]:
    slug, generated_path, shadow, highlight = job
    generated = Image.open(generated_path).convert("RGB")
    generated_mask = generated_foreground_mask(generated)
    regions = generated_regions(generated_mask, slug)

    import json
    cells = json.loads(INDEX.read_text(encoding="utf-8"))["entries"]
    composed = Image.new("RGBA", source.size, (0, 0, 0, 0))
    for cell, region in zip(cells, regions, strict=True):
        source_box = (
            cell["x"],
            cell["y"],
            cell["x"] + cell["width"],
            cell["y"] + cell["height"],
        )
        source_cell = source.crop(source_box)
        alpha = source_cell.getchannel("A")

        ornament = crop_foreground(generated, generated_mask, region)
        ornament = ornament.resize((cell["width"], cell["height"]), Image.Resampling.LANCZOS)

        gray = ImageOps.grayscale(source_cell.convert("RGB"))
        fallback = ImageOps.colorize(gray, black=shadow, white=highlight)
        fallback = Image.blend(source_cell.convert("RGB"), fallback, 0.85)
        ornament_alpha = ImageChops.multiply(ornament.getchannel("A"), alpha)
        output_cell = Image.composite(ornament.convert("RGB"), fallback, ornament_alpha)
        output_cell.putalpha(alpha)
        composed.alpha_composite(output_cell, (cell["x"], cell["y"]))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = f"skills_ui_atlas_theme_{slug}"
    png_path = OUTPUT / f"{stem}.png"
    webp_path = OUTPUT / f"{stem}.webp"
    composed.save(png_path, format="PNG", optimize=True)
    composed.save(webp_path, format="WEBP", lossless=True, method=6)
    return png_path, webp_path


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    results = []
    for job in JOBS:
        png_path, webp_path = process(job, source)
        results.append((job[0], png_path))
        print(png_path)
        print(webp_path)

    preview_dir = OUTPUT / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    cell_width, cell_height, label_height = 860, 463, 24
    columns = 3
    rows = (len(results) + 1 + columns - 1) // columns
    sheet = Image.new("RGB", (cell_width * columns, (cell_height + label_height) * rows), "#101116")
    draw = ImageDraw.Draw(sheet)
    samples = [("original", SOURCE), *results]
    for index, (label, path) in enumerate(samples):
        image = Image.open(path).convert("RGBA")
        x = (index % columns) * cell_width
        y = (index // columns) * (cell_height + label_height)
        sheet.paste(image, (x, y + label_height), image)
        draw.text((x + 8, y + 5), label, fill="white")
    preview_path = preview_dir / "atlas-theme-families.png"
    sheet.save(preview_path, format="PNG", optimize=True)
    print(preview_path)


if __name__ == "__main__":
    main()
