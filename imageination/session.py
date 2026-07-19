from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from imageination.engine import apply_recipe
from imageination.recipe import Recipe


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

    def preview(self) -> Image.Image | None:
        if self.selected_index is None:
            return None
        with Image.open(self.inputs[self.selected_index]) as image:
            return apply_recipe(image, self.recipe)
