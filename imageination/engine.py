from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image

from imageination.core import hex_to_rgb, image_data, rgb_to_hex
from imageination.recipe import LayerOperation, Recipe, RecolorOperation, decode_layer, recipe_to_json


@dataclass(frozen=True)
class PreflightIssue:
    input_path: Path | None
    message: str


def suggest_mappings(source: Image.Image, reference: Image.Image) -> dict[str, str]:
    if source.size != reference.size:
        raise ValueError("Source and reference images must have the same dimensions.")
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for source_pixel, reference_pixel in zip(image_data(source.convert("RGBA")), image_data(reference.convert("RGBA"))):
        if source_pixel[3] and reference_pixel[3]:
            votes[rgb_to_hex(source_pixel[:3])][rgb_to_hex(reference_pixel[:3])] += 1
    return {
        source_hex: sorted(targets, key=lambda target: (-targets[target], target))[0]
        for source_hex, targets in sorted(votes.items())
    }


def apply_recipe(image: Image.Image, recipe: Recipe) -> Image.Image:
    current = image.convert("RGBA")
    for operation in recipe.operations:
        if not operation.enabled:
            continue
        if isinstance(operation, RecolorOperation):
            current = _apply_recolor(current, operation.mappings)
        else:
            current = _apply_layer(current, operation)
    return current


def preflight(inputs: Sequence[Path], recipe: Recipe, output_dir: Path, *, overwrite: bool = False) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    output_dir = Path(output_dir)
    for input_path in inputs:
        path = Path(input_path)
        try:
            with Image.open(path) as image:
                if image.format != "PNG":
                    raise ValueError("Input must be a PNG file.")
                apply_recipe(image, recipe)
        except (OSError, ValueError) as exc:
            issues.append(PreflightIssue(path, str(exc)))
            continue
        if output_dir.joinpath(path.name).exists() and not overwrite:
            issues.append(PreflightIssue(path, f"Output already exists: {path.name}"))
    return issues


def export_recipe(
    inputs: Sequence[Path], recipe: Recipe, output_dir: Path, *, include_recipe: bool, overwrite: bool
) -> list[Path]:
    output_dir = Path(output_dir)
    issues = preflight(inputs, recipe, output_dir, overwrite=overwrite)
    if issues:
        raise ValueError("\n".join(issue.message for issue in issues))
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for input_path in inputs:
        input_path = Path(input_path)
        with Image.open(input_path) as image:
            output_path = output_dir / input_path.name
            apply_recipe(image, recipe).save(output_path, format="PNG")
        outputs.append(output_path)
    if include_recipe:
        output_dir.joinpath("imageination-recipe.json").write_text(recipe_to_json(recipe), encoding="utf-8")
    return outputs


def _apply_recolor(image: Image.Image, mappings: dict[str, str]) -> Image.Image:
    pixels = []
    for red, green, blue, alpha in image_data(image):
        target = mappings.get(rgb_to_hex((red, green, blue))) if alpha else None
        pixels.append((*hex_to_rgb(target), alpha) if target else (red, green, blue, alpha))
    result = Image.new("RGBA", image.size)
    result.putdata(pixels)
    return result


def _apply_layer(current: Image.Image, operation: LayerOperation) -> Image.Image:
    layer = decode_layer(operation)
    if layer.size != current.size:
        expected = f"{current.width}x{current.height}"
        actual = f"{layer.width}x{layer.height}"
        raise ValueError(f"Layer '{operation.name}' expected {expected}; got {actual}.")
    if operation.direction == "behind":
        return Image.alpha_composite(layer, current)
    return Image.alpha_composite(current, layer)
