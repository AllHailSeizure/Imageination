from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

HEX_RE = re.compile(r"#?[0-9a-fA-F]{6}")
SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
}


def image_data(image: Image.Image):
    if hasattr(image, "get_flattened_data"):
        return image.get_flattened_data()
    return image.getdata()


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def normalize_hex(value: str) -> str:
    match = HEX_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid hex color: {value}")
    stripped = value.strip().lstrip("#")
    return f"#{stripped.upper()}"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = normalize_hex(value).lstrip("#")
    return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))


def extract_hex_values(image_path: str | Path, include_transparent: bool = False) -> list[str]:
    with Image.open(image_path).convert("RGBA") as image:
        colors = {
            rgb_to_hex((r, g, b))
            for r, g, b, a in image_data(image)
            if include_transparent or a > 0
        }
    return sorted(colors)


def build_color_map(source_path: str | Path, target_path: str | Path) -> dict[str, dict[str, int | str]]:
    with Image.open(source_path).convert("RGBA") as source, Image.open(target_path).convert("RGBA") as target:
        width = min(source.width, target.width)
        height = min(source.height, target.height)
        votes: dict[str, Counter[str]] = defaultdict(Counter)

        for y in range(height):
            for x in range(width):
                source_rgba = source.getpixel((x, y))
                target_rgba = target.getpixel((x, y))
                if source_rgba[3] == 0 or target_rgba[3] == 0:
                    continue
                votes[rgb_to_hex(source_rgba[:3])][rgb_to_hex(target_rgba[:3])] += 1

    return _winner_map(votes)


def build_cell_color_map(
    source_path: str | Path,
    target_path: str | Path,
    frame_width: int,
    frame_height: int,
) -> dict[str, dict[str, int | str]]:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("Frame size must be positive.")

    with Image.open(source_path).convert("RGBA") as source, Image.open(target_path).convert("RGBA") as target:
        columns = min(source.width, target.width) // frame_width
        rows = min(source.height, target.height) // frame_height
        votes: dict[str, Counter[str]] = defaultdict(Counter)

        for row in range(rows):
            for column in range(columns):
                box = (
                    column * frame_width,
                    row * frame_height,
                    (column + 1) * frame_width,
                    (row + 1) * frame_height,
                )
                source_color = dominant_hex(source.crop(box))
                target_color = dominant_hex(target.crop(box))
                if source_color and target_color:
                    votes[source_color][target_color] += 1

    return _winner_map(votes)


def dominant_hex(image: Image.Image) -> str | None:
    counts: Counter[str] = Counter()
    converted = image.convert("RGBA")
    for r, g, b, a in image_data(converted):
        if a > 0:
            counts[rgb_to_hex((r, g, b))] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _winner_map(votes: dict[str, Counter[str]]) -> dict[str, dict[str, int | str]]:
    winners = {}
    for source_hex in sorted(votes):
        target_hex, count = votes[source_hex].most_common(1)[0]
        winners[source_hex] = {"target": target_hex, "count": count}
    return winners


def parse_manual_map(text: str) -> dict[str, str]:
    mappings = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        colors = HEX_RE.findall(line)
        if len(colors) != 2:
            raise ValueError(f"Line {line_number} must contain exactly two hex colors.")
        mappings[normalize_hex(colors[0])] = normalize_hex(colors[1])
    return mappings


def flatten_suggested_map(suggested_map: dict[str, dict[str, int | str]]) -> dict[str, str]:
    return {source: str(info["target"]) for source, info in suggested_map.items()}


def apply_color_map(
    source_path: str | Path,
    output_path: str | Path,
    color_map: dict[str, str],
    use_imagemagick: bool = False,
) -> Path:
    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_map = {normalize_hex(source): normalize_hex(target) for source, target in color_map.items()}
    if use_imagemagick and normalized_map:
        try:
            return apply_color_map_imagemagick(source_path, output_path, normalized_map)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    with Image.open(source_path).convert("RGBA") as image:
        pixels = []
        for r, g, b, a in image_data(image):
            if a == 0:
                pixels.append((r, g, b, a))
                continue
            replacement = normalized_map.get(rgb_to_hex((r, g, b)))
            if replacement:
                pixels.append((*hex_to_rgb(replacement), a))
            else:
                pixels.append((r, g, b, a))
        image.putdata(pixels)
        image.save(output_path)
    return output_path


def apply_color_map_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    color_map: dict[str, str],
    use_imagemagick: bool = False,
) -> list[Path]:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    for source_path in sorted(input_dir.iterdir()):
        if not source_path.is_file() or source_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        output_path = output_dir / source_path.name
        apply_color_map(source_path, output_path, color_map, use_imagemagick=use_imagemagick)
        outputs.append(output_path)
    return outputs


def apply_color_map_imagemagick(source_path: Path, output_path: Path, color_map: dict[str, str]) -> Path:
    command = ["magick", str(source_path)]
    for source_hex, target_hex in color_map.items():
        command.extend(["-fill", target_hex, "-opaque", source_hex])
    command.append(str(output_path))
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path
