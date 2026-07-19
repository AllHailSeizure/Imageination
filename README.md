# Imageination

Imageination is a small local PNG batch workbench. Build a simple image recipe, preview it against any input, and export transformed copies without touching the originals.

## Run

```powershell
cd D:\Libraries\Imageination
python .\run_imageination.py
```

## Workflow

1. Add individual PNGs or every top-level PNG from a folder.
2. Add a recolor operation manually, or generate its mappings from a same-size reference image.
3. Add transparent PNG layers above or behind the current image. Layers must match the input size exactly.
4. Preview inputs and reorder, disable, or remove recipe operations as needed.
5. Export transformed copies to a separate folder. Optionally include a portable `imageination-recipe.json` alongside them.

Recipes contain only the operations. Imageination does not save projects, input folders, output folders, or recipe history. Embedded layer data keeps an exported recipe self-contained.

## Test

```powershell
python -m pytest tests -v
```
