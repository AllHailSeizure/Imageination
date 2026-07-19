from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, TypeAlias

from PIL import Image

from imageination.core import normalize_hex


RECIPE_FORMAT = "imageination-recipe"
RECIPE_VERSION = 1


@dataclass(frozen=True)
class RecolorOperation:
    name: str
    mappings: dict[str, str]
    enabled: bool = True

    def __post_init__(self):
        object.__setattr__(
            self,
            "mappings",
            {normalize_hex(source): normalize_hex(target) for source, target in self.mappings.items()},
        )


@dataclass(frozen=True)
class LayerOperation:
    name: str
    direction: Literal["above", "behind"]
    width: int
    height: int
    png_base64: str
    enabled: bool = True

    def __post_init__(self):
        if self.direction not in {"above", "behind"}:
            raise ValueError("Layer direction must be 'above' or 'behind'.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Layer dimensions must be positive.")
        image = _image_from_base64(self.png_base64)
        if image.size != (self.width, self.height):
            raise ValueError("Layer dimensions do not match its PNG data.")


Operation: TypeAlias = RecolorOperation | LayerOperation


@dataclass(frozen=True)
class Recipe:
    operations: tuple[Operation, ...] = ()


def layer_from_png(path: str | Path, *, name: str, direction: Literal["above", "behind"]) -> LayerOperation:
    path = Path(path)
    data = path.read_bytes()
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
        if image.format != "PNG":
            raise ValueError("Layers must be PNG files.")
    return LayerOperation(name, direction, width, height, base64.b64encode(data).decode("ascii"))


def recipe_to_json(recipe: Recipe) -> str:
    operations = []
    for operation in recipe.operations:
        if isinstance(operation, RecolorOperation):
            operations.append(
                {
                    "type": "recolor",
                    "name": operation.name,
                    "enabled": operation.enabled,
                    "mappings": operation.mappings,
                }
            )
        else:
            operations.append(
                {
                    "type": "layer",
                    "name": operation.name,
                    "enabled": operation.enabled,
                    "direction": operation.direction,
                    "width": operation.width,
                    "height": operation.height,
                    "png_base64": operation.png_base64,
                }
            )
    return json.dumps({"format": RECIPE_FORMAT, "version": RECIPE_VERSION, "operations": operations}, indent=2)


def recipe_from_json(text: str) -> Recipe:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Recipe JSON is invalid.") from exc
    if not isinstance(payload, dict) or payload.get("format") != RECIPE_FORMAT:
        raise ValueError("Recipe format is invalid.")
    if payload.get("version") != RECIPE_VERSION:
        raise ValueError("Recipe version is unsupported.")
    raw_operations = payload.get("operations")
    if not isinstance(raw_operations, list):
        raise ValueError("Recipe operations must be a list.")

    operations: list[Operation] = []
    for index, raw_operation in enumerate(raw_operations):
        if not isinstance(raw_operation, dict):
            raise ValueError(f"Recipe operation {index} is invalid.")
        operation_type = raw_operation.get("type")
        try:
            if operation_type == "recolor":
                operations.append(
                    RecolorOperation(
                        str(raw_operation["name"]),
                        dict(raw_operation["mappings"]),
                        bool(raw_operation.get("enabled", True)),
                    )
                )
            elif operation_type == "layer":
                operations.append(
                    LayerOperation(
                        str(raw_operation["name"]),
                        raw_operation["direction"],
                        int(raw_operation["width"]),
                        int(raw_operation["height"]),
                        str(raw_operation["png_base64"]),
                        bool(raw_operation.get("enabled", True)),
                    )
                )
            else:
                raise ValueError(f"Recipe operation {index} has unsupported type: {operation_type}")
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and "unsupported type" in str(exc):
                raise
            raise ValueError(f"Recipe operation {index} is invalid: {exc}") from exc
    return Recipe(tuple(operations))


def decode_layer(operation: LayerOperation) -> Image.Image:
    return _image_from_base64(operation.png_base64).convert("RGBA")


def _image_from_base64(value: str) -> Image.Image:
    try:
        data = base64.b64decode(value, validate=True)
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG":
                raise ValueError("Layer PNG data is invalid.")
            return image.copy()
    except (ValueError, OSError) as exc:
        raise ValueError("Layer PNG data is invalid.") from exc
