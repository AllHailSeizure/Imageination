import json
from pathlib import Path

import pytest
from PIL import Image

from imageination.recipe import (
    LayerOperation,
    Recipe,
    RecolorOperation,
    layer_from_png,
    recipe_from_json,
    recipe_to_json,
)


def save_rgba(path: Path, pixels, size=(2, 2)):
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    image.save(path)


def test_recipe_json_round_trip_embeds_a_layer_png(tmp_path):
    layer_path = tmp_path / "ring.png"
    save_rgba(layer_path, [(1, 2, 3, 0), (4, 5, 6, 255)], size=(2, 1))
    recipe = Recipe(
        (
            RecolorOperation("Blue", {"#FF0000": "#0000FF"}),
            layer_from_png(layer_path, name="Ring behind", direction="behind"),
        )
    )

    loaded = recipe_from_json(recipe_to_json(recipe))

    assert loaded == recipe
    assert isinstance(loaded.operations[1], LayerOperation)
    assert loaded.operations[1].width == 2
    assert loaded.operations[1].png_base64


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"format": "wrong", "version": 1, "operations": []}, "format"),
        ({"format": "imageination-recipe", "version": 2, "operations": []}, "version"),
        ({"format": "imageination-recipe", "version": 1, "operations": [{"type": "blur"}]}, "type"),
    ],
)
def test_recipe_from_json_rejects_invalid_payloads(payload, message):
    with pytest.raises(ValueError, match=message):
        recipe_from_json(json.dumps(payload))
