from __future__ import annotations

from collections import Counter, defaultdict

from PIL import Image

from imageination.core import hex_to_rgb, image_data, rgb_to_hex
from imageination.recipe import LayerOperation, Recipe, RecolorOperation, decode_layer


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
