import base64
from collections import Counter
from io import BytesIO

import pytest
from PIL import Image

from imageination.core import image_data
from imageination.engine import apply_recipe, export_recipe, preflight, suggest_mappings
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


def test_preflight_blocks_mismatched_inputs_before_export(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output"
    image_from_pixels([(1, 2, 3, 255)], (1, 1)).save(source)
    recipe = Recipe((layer_operation("Ring", "above", [(0, 0, 0, 0)] * 2, (2, 1)),))

    issues = preflight([source], recipe, output)

    assert [issue.message for issue in issues] == ["Layer 'Ring' expected 1x1; got 2x1."]
    assert not output.exists()


def test_export_writes_pngs_and_optional_recipe_without_touching_input(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "skin"
    image_from_pixels([(255, 0, 0, 255)], (1, 1)).save(source)
    recipe = Recipe((RecolorOperation("Blue", {"#FF0000": "#0000FF"}),))

    written = export_recipe([source], recipe, output, include_recipe=True, overwrite=False)

    assert written == [output / "source.png"]
    assert (output / "imageination-recipe.json").exists()
    assert source.read_bytes() != (output / "source.png").read_bytes()
