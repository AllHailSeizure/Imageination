from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from imageination.engine import apply_recipe
from imageination.recipe import Operation, Recipe


@dataclass
class RecipeSession:
    inputs: list[Path] = field(default_factory=list)
    recipe: Recipe = field(default_factory=Recipe)
    selected_index: int | None = None

    def add_files(self, paths) -> None:
        additions = [Path(path) for path in paths if Path(path).suffix.lower() == ".png"]
        self.inputs.extend(path for path in additions if path not in self.inputs)
        if self.selected_index is None and self.inputs:
            self.selected_index = 0

    def add_folder(self, folder: Path) -> None:
        self.add_files(sorted(path for path in Path(folder).iterdir() if path.is_file() and path.suffix.lower() == ".png"))

    def replace_recipe(self, recipe: Recipe) -> None:
        self.recipe = recipe

    def replace_operation(self, index: int, operation: Operation) -> None:
        operations = list(self.recipe.operations)
        operations[index] = operation
        self.recipe = Recipe(tuple(operations))

    def move_operation(self, index: int, offset: int) -> None:
        target = index + offset
        if not 0 <= index < len(self.recipe.operations) or not 0 <= target < len(self.recipe.operations):
            return
        operations = list(self.recipe.operations)
        operations[index], operations[target] = operations[target], operations[index]
        self.recipe = Recipe(tuple(operations))

    def preview(self) -> Image.Image | None:
        if self.selected_index is None:
            return None
        with Image.open(self.inputs[self.selected_index]) as image:
            return apply_recipe(image, self.recipe)
