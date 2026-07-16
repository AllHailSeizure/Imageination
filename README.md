# Imageination

A small local GUI tool for extracting image hex colors, comparing two images, building color transform maps, editing those maps manually, and exporting transformed images with ImageMagick.

## Run

```powershell
cd D:\Libraries\Imageination
python .\run_imageination.py
```

## Current workflow

1. Pick a source image.
2. Pick a comparison image.
3. Use `Compare Pixels` to map aligned source colors to comparison colors.
4. Or enter a frame size and use `Compare Cells` to map dominant colors per frame/cell.
5. Double-click extracted colors or type mappings manually, such as:

```text
#FF0000 -> #00FF00
#0000FF, #111111
```

6. Preview or export the transformed source image.

## Notes

- ImageMagick is used for export when the checkbox is enabled.
- Preview uses the built-in Pillow path so it is fast and local.
- Transform maps can be saved and loaded as JSON.
- Future work: batch layering, spritesheet frame layering, and per-frame nudging.

## Test

```powershell
cd D:\Libraries\Imageination
python -m pytest tests
```
