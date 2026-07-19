# Image Recipe Foundation Design

## Purpose

Imageination will be rebuilt as a small, project-agnostic batch image workbench. A user selects one or more PNG inputs, builds an ordered recipe from a few understandable operations, previews the result, and exports transformed copies.

The first release supports two operations:

- recolor pixels through editable source-to-target color mappings;
- composite an exact-size transparent layer above or behind the current image.

This foundation supports the proven character-skin workflow without making the application specific to Hotel Kline, spritesheets, or pixel art. Spritesheet-aware processing can be added later as a separate capability.

## Design Principles

- The app explains the user's task, not its internal machinery.
- One operation has one focused editor.
- Inputs and originals are never modified.
- One-time work should not create project-management chores.
- Reusable recipes should be portable as a single optional JSON file.
- The first release prefers strict, predictable behavior over implicit resizing or guessing.

## Main Workspace

The window has three primary areas:

1. **Inputs:** the PNG files in the current session, with the selected preview input highlighted.
2. **Preview:** a large before/after comparison for the selected input, plus previous and next controls.
3. **Recipe:** the ordered operations and the focused editor for the selected operation.

The top-level actions are limited to adding inputs, loading a recipe, and exporting results. There is no project browser, saved-project library, recent-recipe library, or persistent workspace.

The recipe stack is displayed with the last-applied operation at the top. Internally, operations run from bottom to top. Each operation can be renamed, reordered, temporarily disabled, or removed.

Selecting an operation reveals only its own controls. Raw color lists, manual-map text, separate map tables, comparison-mode toolbars, ImageMagick settings, and unrelated future-feature labels are removed from the main workspace.

## Session Model

The application starts with an empty, in-memory session. The session contains:

- the current list of input PNG paths;
- the selected preview input;
- the current ordered recipe;
- the chosen export destination for the current export only.

None of those session details are stored automatically. Closing the app discards them without a save-project prompt.

A loaded recipe populates only the recipe stack. It does not supply input paths, an output folder, recent history, or other project state, so the same recipe can be applied to any compatible batch.

## Recipe Engine

The core engine accepts a decoded RGBA input image and an ordered list of operations. It returns a new RGBA image without changing the input file.

Operations execute sequentially from the bottom of the visible stack to the top. The engine initially supports two operation types:

- `recolor`
- `layer`

The operation interface is intentionally small so that later capabilities, such as spritesheet slicing or geometric transforms, can be added without changing the batch/export workflow.

### Recolor Operation

A recolor operation stores a mapping from source RGBA colors to replacement RGBA colors. The normal UI presents colors as hex swatches, with hex entry available for precision. Transparent pixels remain transparent unless a future design explicitly introduces alpha editing.

Mappings can be created in two ways:

1. **Manual:** the user clicks a color in the source preview or enters a hex value, chooses a replacement color, and adds the pair to the mapping list.
2. **From reference:** the user selects an original/reference image pair with identical dimensions. Imageination compares aligned opaque pixels and proposes the most common target color for each source color.

Both paths produce the same editable swatch list. Generated suggestions are not applied invisibly: the user can change or remove them before export. Changes update the main preview immediately.

The first release omits cell comparison and frame-size controls. Reference comparison is whole-image, aligned-pixel comparison only. A mismatched reference pair is rejected with a clear dimensions message.

### Layer Operation

A layer operation contains:

- an embedded RGBA PNG;
- its width and height;
- a compositing direction: `above` or `behind`;
- a user-facing name;
- an enabled flag.

The layer must exactly match the current image dimensions. The first release does not resize, position, crop, tile, rotate, track, mask, or blend layers.

An `above` layer is alpha-composited over the current image. A `behind` layer is alpha-composited under the current image. This supports effects made from separate back and front artwork while keeping the operation general-purpose.

Recipe order determines which content later operations affect. For example, a recolor followed by a behind layer and then an above layer recolors the input first, places the back artwork beneath it, and finally places the front artwork over it.

## Recipe JSON

Recipes are optional, portable, and self-contained. A versioned JSON recipe stores only operation data; it does not store input paths, reference-image paths, export paths, or application history.

Recolor operations store their source-to-target mappings. Layer operations embed their PNG bytes as a base64 string together with dimensions and compositing direction. Embedding the encoded PNG preserves transparency compactly and avoids external asset paths.

Conceptual structure:

```json
{
  "format": "imageination-recipe",
  "version": 1,
  "operations": [
    {
      "type": "recolor",
      "name": "Blue palette",
      "enabled": true,
      "mappings": {
        "#F080A0": "#3040E0"
      }
    },
    {
      "type": "layer",
      "name": "Ring behind",
      "enabled": true,
      "direction": "behind",
      "width": 24,
      "height": 24,
      "png_base64": "..."
    }
  ]
}
```

The export flow includes an unchecked-by-default option to place the current recipe JSON beside the generated PNG files. One-time operations therefore require no recipe file. A previously exported recipe can be loaded into a new session.

Malformed files, unsupported versions, unknown operation types, invalid mappings, and corrupt embedded PNG data are rejected before changing the current recipe stack. The error identifies the problematic recipe field where practical.

## PNG Input and Export

The first release is PNG-only. This keeps transparency and pixel values predictable and avoids format-specific controls the intended user does not need.

Inputs can be added individually or by selecting one folder. Folder import adds supported PNG files from that folder; it is not recursive in the first release. Adding inputs does not copy, rename, or modify them.

Before export, Imageination preflights the complete recipe against every input. Preflight checks include:

- the input still exists and decodes as a PNG;
- each reference-derived recolor operation already contains valid mappings;
- every enabled layer matches that input's dimensions;
- the output destination is writable;
- existing output-name collisions are identified.

Problems appear beside the affected inputs and in a concise export summary. Imageination never stretches, crops, or silently skips incompatible images. Export does not begin until blocking preflight errors are resolved. Existing output files are not overwritten without an explicit overwrite choice in the export flow.

Successful export writes transformed PNGs to a separate selected folder using the original filenames. The optional recipe JSON is written to the same folder.

## Error Handling

- File errors are associated with the specific input or layer that caused them.
- Dimension messages show both expected and actual dimensions.
- Reference-comparison errors explain that aligned comparison requires equal dimensions.
- A failed recipe load leaves the current in-memory recipe unchanged.
- A failed export reports which output failed and does not claim that the batch completed.
- No fallback to ImageMagick is exposed in the UI. The Pillow-based pipeline is the single predictable implementation path for this release.

## Internal Structure

The current monolithic Tkinter window should be separated along the new product boundaries:

- immutable operation models and recipe serialization;
- pure image-processing functions for recolor and compositing;
- batch preflight and export services;
- input-list, preview, recipe-stack, recolor-editor, and layer-editor UI components;
- a thin application coordinator that connects UI state to the engine.

Image-processing and serialization behavior must remain usable without Tkinter so it can be tested directly and reused by later batch or spritesheet features.

## Testing

Automated tests cover:

- manual recolor mappings and preservation of unmapped/transparent pixels;
- generated mappings from aligned reference images;
- above and behind alpha compositing;
- sequential operation ordering;
- disabled and reordered operations;
- strict layer-dimension validation;
- recipe JSON round-tripping, including embedded layer PNG data;
- invalid and unsupported recipe files leaving current state unchanged;
- multi-file preflight and batch export;
- preservation of originals and explicit handling of output collisions.

Focused UI/controller tests cover selection changes, operation enable/reorder behavior, and preview invalidation. A manual smoke test verifies the complete workflow: add PNGs, build both operation types, preview multiple inputs, export, include the recipe, reload that recipe in an empty session, and reproduce the same output.

## Explicitly Deferred

The following are outside the first release:

- spritesheet detection, slicing, and reconstitution;
- accessory positioning, scaling, rotation, or tracking;
- multi-row frame grids;
- cell-based comparison;
- blend modes, masks, and opacity controls;
- non-PNG formats;
- recursive folder import;
- project files, autosave, recent items, or an internal recipe library;
- ImageMagick selection or configuration.

These capabilities may be designed later as additions to the operation model. They are not prerequisites for a useful recolor-and-layer workbench.
