import base64
from collections import Counter
from io import BytesIO

import pytest
from PIL import Image

from imageination.core import image_data
from imageination.engine import apply_recipe, suggest_mappings
from imageination.recipe import LayerOperation, Recipe, RecolorOperation


def image_from_pixels(pixels, size):
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    return image


def layer_operation(name, direction, pixels, size):
    image = image_from_pixels(pixels, size)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return LayerOperation(name, direction, *size, base64.b64encode(stream.getvalue()).decode("ascii"))


def test_apply_recipe_recolors_then_composites_behind_and_above():
    source = image_from_pixels([(255, 0, 0, 255), (0, 0, 0, 0)], (2, 1))
    behind = layer_operation("Behind", "behind", [(0, 255, 0, 255), (0, 255, 0, 255)], (2, 1))
    above = layer_operation("Above", "above", [(0, 0, 255, 0), (0, 0, 255, 255)], (2, 1))
    recipe = Recipe((RecolorOperation("Recolor", {"#FF0000": "#FFFFFF"}), behind, above))

    result = apply_recipe(source, recipe)

    assert list(image_data(result)) == [(255, 255, 255, 255), (0, 0, 255, 255)]


def test_apply_recipe_rejects_mismatched_enabled_layer():
    source = image_from_pixels([(1, 2, 3, 255)], (1, 1))
    recipe = Recipe((layer_operation("Too wide", "above", [(0, 0, 0, 0)] * 2, (2, 1)),))

    with pytest.raises(ValueError, match="Too wide.*expected 1x1.*got 2x1"):
        apply_recipe(source, recipe)


def test_suggest_mappings_requires_equal_dimensions_and_returns_winners():
    source = image_from_pixels([(255, 0, 0, 255)] * 3, (3, 1))
    reference = image_from_pixels([(0, 255, 0, 255)] * 2 + [(0, 0, 255, 255)], (3, 1))

    assert suggest_mappings(source, reference) == {"#FF0000": "#00FF00"}
    with pytest.raises(ValueError, match="same dimensions"):
        suggest_mappings(source, image_from_pixels([(0, 0, 0, 255)], (1, 1)))
