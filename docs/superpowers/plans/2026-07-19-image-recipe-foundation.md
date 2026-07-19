# Image Recipe Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Imageination as a stateless PNG batch workbench with editable recolor and exact-size layer recipes.

**Architecture:** Move image-recipe models, serialization, image processing, and batch validation into pure modules, with Tkinter acting only as a session coordinator and renderer. A recipe stores recolor mappings and embedded layer PNG bytes; it never stores inputs, output paths, or app history. The UI rebuilds preview images from the selected input and current recipe rather than writing temporary files.

**Tech Stack:** Python 3, Tkinter/ttk, Pillow, JSON, pytest.

## Global Constraints

- Execute in an isolated worktree created from `HEAD`; the shared workspace has user-owned changes in `tests/test_core.py`.
- Support PNG input and output only; keep alpha intact.
- Never modify source inputs.
- Do not add ImageMagick or another dependency.
- Recipe JSON is optional, versioned, self-contained, and contains no input/output paths.
- Only `RecolorOperation` and `LayerOperation` are in scope; no spritesheet splitting, positioning, scaling, blend modes, masks, non-PNG formats, or recipe library.
- Follow test-driven development: add the failing test, run it, implement the smallest behavior, re-run the focused test, then commit the task.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `imageination/recipe.py` | Immutable operation models, PNG embedding, JSON parsing and serialization. |
| `imageination/engine.py` | Pure reference mapping, recipe application, preflight, and export functions. |
| `imageination/session.py` | In-memory inputs, selected preview index, recipe mutation, and preview cache invalidation. |
| `imageination/app.py` | Tkinter workspace, file dialogs, focused operation editors, and user-visible errors. |
| `tests/test_recipe.py` | Recipe serialization and invalid-file tests. |
| `tests/test_engine.py` | Image operation, reference mapping, preflight, and export tests. |
| `tests/test_session.py` | Stateless session/controller tests. |
| `tests/test_core.py` | Existing legacy helpers; preserve until a separately approved cleanup. |
| `README.md` | New workflow and PNG-only usage instructions. |

## Interfaces

```python
# imageination/recipe.py
@dataclass(frozen=True)
class RecolorOperation:
    name: str
    mappings: dict[str, str]
    enabled: bool = True

@dataclass(frozen=True)
class LayerOperation:
    name: str
    direction: Literal["above", "behind"]
    width: int
    height: int
    png_base64: str
    enabled: bool = True

Operation = RecolorOperation | LayerOperation

@dataclass(frozen=True)
class Recipe:
    operations: tuple[Operation, ...] = ()

def layer_from_png(path: str | Path, *, name: str, direction: str) -> LayerOperation: ...
def recipe_to_json(recipe: Recipe) -> str: ...
def recipe_from_json(text: str) -> Recipe: ...
```

```python
# imageination/engine.py
@dataclass(frozen=True)
class PreflightIssue:
    input_path: Path | None
    message: str

def suggest_mappings(source: Image.Image, reference: Image.Image) -> dict[str, str]: ...
def apply_recipe(image: Image.Image, recipe: Recipe) -> Image.Image: ...
def preflight(inputs: Sequence[Path], recipe: Recipe, output_dir: Path, *, overwrite: bool = False) -> list[PreflightIssue]: ...
def export_recipe(inputs: Sequence[Path], recipe: Recipe, output_dir: Path, *, include_recipe: bool, overwrite: bool) -> list[Path]: ...
```

```python
# imageination/session.py
class RecipeSession:
    inputs: list[Path]
    recipe: Recipe
    selected_index: int | None

    def add_files(self, paths: Iterable[Path]) -> None: ...
    def add_folder(self, folder: Path) -> None: ...
    def replace_recipe(self, recipe: Recipe) -> None: ...
    def replace_operation(self, index: int, operation: Operation) -> None: ...
    def move_operation(self, index: int, offset: int) -> None: ...
    def preview(self) -> Image.Image | None: ...
```

### Task 1: Versioned recipe models and portable JSON

**Files:**

- Create: `imageination/recipe.py`
- Create: `tests/test_recipe.py`
- Modify: `imageination/__init__.py`

**Consumes:** Pillow and existing `normalize_hex`/`hex_to_rgb` helpers from `imageination.core`.

**Produces:** `Recipe`, `RecolorOperation`, `LayerOperation`, `layer_from_png`, `recipe_to_json`, and `recipe_from_json` for the engine and UI.

- [ ] **Step 1: Write the failing serialization and embedded-layer tests**

```python
def test_recipe_json_round_trip_embeds_a_layer_png(tmp_path):
    layer_path = tmp_path / "ring.png"
    save_rgba(layer_path, [(1, 2, 3, 0), (4, 5, 6, 255)], size=(2, 1))
    recipe = Recipe((
        RecolorOperation("Blue", {"#FF0000": "#0000FF"}),
        layer_from_png(layer_path, name="Ring behind", direction="behind"),
    ))

    loaded = recipe_from_json(recipe_to_json(recipe))

    assert loaded == recipe
    assert loaded.operations[1].width == 2
    assert loaded.operations[1].png_base64


@pytest.mark.parametrize("payload, message", [
    ({"format": "wrong", "version": 1, "operations": []}, "format"),
    ({"format": "imageination-recipe", "version": 2, "operations": []}, "version"),
    ({"format": "imageination-recipe", "version": 1, "operations": [{"type": "blur"}]}, "type"),
])
def test_recipe_from_json_rejects_invalid_payloads(payload, message):
    with pytest.raises(ValueError, match=message):
        recipe_from_json(json.dumps(payload))
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_recipe.py -v`

Expected: FAIL because `imageination.recipe` does not exist.

- [ ] **Step 3: Implement the model and serializer**

```python
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
        try:
            Image.open(BytesIO(base64.b64decode(self.png_base64, validate=True))).verify()
        except Exception as exc:
            raise ValueError("Layer PNG data is invalid.") from exc
```

Serialize operations with explicit `type`, `name`, and `enabled` fields. Decode JSON into local temporary operations before constructing and returning a `Recipe`; never mutate a caller's existing recipe while loading.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `python -m pytest tests/test_recipe.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the recipe model task**

```bash
git add imageination/recipe.py imageination/__init__.py tests/test_recipe.py
git commit -m "feat: add portable image recipe models"
```

### Task 2: Pure recolor, layer, and reference-mapping engine

**Files:**

- Create: `imageination/engine.py`
- Create: `tests/test_engine.py`

**Consumes:** `Recipe` and operations from `imageination.recipe`; `rgb_to_hex` and `hex_to_rgb` from `imageination.core`.

**Produces:** `suggest_mappings` and `apply_recipe` for session previews and exports.

- [ ] **Step 1: Write the failing operation tests**

```python
def test_apply_recipe_recolors_then_composites_behind_and_above():
    source = image_from_pixels([(255, 0, 0, 255), (0, 0, 0, 0)], (2, 1))
    behind = layer_operation("Behind", "behind", [(0, 255, 0, 255), (0, 255, 0, 255)], (2, 1))
    above = layer_operation("Above", "above", [(0, 0, 255, 0), (0, 0, 255, 255)], (2, 1))
    recipe = Recipe((
        RecolorOperation("Recolor", {"#FF0000": "#FFFFFF"}),
        behind,
        above,
    ))

    result = apply_recipe(source, recipe)

    assert list(result.getdata()) == [(255, 255, 255, 255), (0, 0, 255, 255)]


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
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_engine.py -v`

Expected: FAIL because `imageination.engine` does not exist.

- [ ] **Step 3: Implement image processing without file I/O**

```python
def apply_recipe(image: Image.Image, recipe: Recipe) -> Image.Image:
    current = image.convert("RGBA")
    for operation in recipe.operations:
        if not operation.enabled:
            continue
        if isinstance(operation, RecolorOperation):
            current = _apply_recolor(current, operation.mappings)
        else:
            layer = _decode_layer(operation)
            if layer.size != current.size:
                expected = f"{current.width}x{current.height}"
                actual = f"{layer.width}x{layer.height}"
                raise ValueError(f"Layer '{operation.name}' expected {expected}; got {actual}.")
            current = (
                Image.alpha_composite(layer, current)
                if operation.direction == "behind"
                else Image.alpha_composite(current, layer)
            )
    return current

def suggest_mappings(source: Image.Image, reference: Image.Image) -> dict[str, str]:
    if source.size != reference.size:
        raise ValueError("Source and reference images must have the same dimensions.")
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for source_pixel, reference_pixel in zip(source.convert("RGBA").getdata(), reference.convert("RGBA").getdata()):
        if source_pixel[3] and reference_pixel[3]:
            votes[rgb_to_hex(source_pixel[:3])][rgb_to_hex(reference_pixel[:3])] += 1
    return {source_hex: min((-count, target) for target, count in targets.items())[1] for source_hex, targets in sorted(votes.items())}
```

Keep `_decode_layer` and `_apply_recolor` private. Preserve alpha for unmapped and transparent source pixels.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `python -m pytest tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the engine task**

```bash
git add imageination/engine.py tests/test_engine.py
git commit -m "feat: apply recolor and layer recipes"
```

### Task 3: Stateless session, preflight, and safe batch export

**Files:**

- Create: `imageination/session.py`
- Modify: `imageination/engine.py`
- Create: `tests/test_session.py`
- Modify: `tests/test_engine.py`

**Consumes:** recipe models and `apply_recipe` from Tasks 1–2.

**Produces:** `RecipeSession`, `PreflightIssue`, `preflight`, and `export_recipe` for the UI.

- [ ] **Step 1: Write failing session and export tests**

```python
def test_session_add_folder_uses_only_top_level_pngs(tmp_path):
    (tmp_path / "nested").mkdir()
    save_rgba(tmp_path / "a.png", [(1, 2, 3, 255)], size=(1, 1))
    save_rgba(tmp_path / "nested" / "b.png", [(1, 2, 3, 255)], size=(1, 1))
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    session = RecipeSession()

    session.add_folder(tmp_path)

    assert session.inputs == [tmp_path / "a.png"]
    assert session.selected_index == 0


def test_preflight_blocks_mismatched_inputs_before_export(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output"
    save_rgba(source, [(1, 2, 3, 255)], size=(1, 1))
    recipe = Recipe((layer_operation("Ring", "above", [(0, 0, 0, 0)] * 2, (2, 1)),))

    issues = preflight([source], recipe, output)

    assert issues == [PreflightIssue(source, "Layer 'Ring' expected 1x1; got 2x1.")]
    assert not output.exists()


def test_export_writes_pngs_and_optional_self_contained_recipe_without_touching_input(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "skin"
    save_rgba(source, [(255, 0, 0, 255)], size=(1, 1))
    recipe = Recipe((RecolorOperation("Blue", {"#FF0000": "#0000FF"}),))

    written = export_recipe([source], recipe, output, include_recipe=True, overwrite=False)

    assert written == [output / "source.png"]
    assert (output / "imageination-recipe.json").exists()
    assert source.read_bytes() != (output / "source.png").read_bytes()


def test_preflight_reports_existing_output_without_overwrite_permission(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output"
    output.mkdir()
    save_rgba(source, [(255, 0, 0, 255)], size=(1, 1))
    save_rgba(output / "source.png", [(0, 0, 255, 255)], size=(1, 1))

    issues = preflight([source], Recipe(), output, overwrite=False)

    assert issues == [PreflightIssue(source, "Output already exists: source.png")]
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_session.py tests/test_engine.py -v`

Expected: FAIL because `RecipeSession`, `preflight`, and `export_recipe` do not exist.

- [ ] **Step 3: Implement session and preflight/export services**

```python
@dataclass
class RecipeSession:
    inputs: list[Path] = field(default_factory=list)
    recipe: Recipe = field(default_factory=Recipe)
    selected_index: int | None = None

    def add_files(self, paths: Iterable[Path]) -> None:
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
```

`preflight` opens each input and calls `apply_recipe` in memory, accumulating `PreflightIssue` values. Its complete signature is `preflight(inputs, recipe, output_dir, *, overwrite=False)`. It must check output collisions without creating the directory when it does not exist. `export_recipe` calls `preflight(..., overwrite=overwrite)` first, raises one `ValueError` containing all issue messages when errors exist, creates the output directory only after a clean preflight, writes output PNGs with source filenames, and writes `imageination-recipe.json` only when `include_recipe=True`.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `python -m pytest tests/test_session.py tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the session and export task**

```bash
git add imageination/session.py imageination/engine.py tests/test_session.py tests/test_engine.py
git commit -m "feat: add stateless batch recipe export"
```

### Task 4: Replace the Tkinter window with the recipe workspace

**Files:**

- Modify: `imageination/app.py`
- Modify: `tests/test_session.py`

**Consumes:** `RecipeSession`, operation models, recipe loader, `suggest_mappings`, `preflight`, and `export_recipe`.

**Produces:** a runnable Tkinter workbench with inputs, preview, recipe stack, focused recolor/layer editors, recipe load, and safe export.

- [ ] **Step 1: Write controller-level failing tests for recipe mutation**

```python
def test_session_reorders_and_disables_operations():
    red = RecolorOperation("Red", {"#FF0000": "#00FF00"})
    blue = RecolorOperation("Blue", {"#0000FF": "#FFFFFF"})
    session = RecipeSession(recipe=Recipe((red, blue)))

    session.move_operation(0, 1)
    session.replace_operation(0, replace(blue, enabled=False))

    assert session.recipe.operations == (replace(blue, enabled=False), red)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_session.py::test_session_reorders_and_disables_operations -v`

Expected: FAIL because the session has no operation-mutation methods.

- [ ] **Step 3: Add session mutation methods and rebuild `ImageinationApp` around them**

```python
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
```

Build the new window with these concrete controls:

- toolbar buttons: `Add PNGs`, `Add Folder`, `Load Recipe`, and `Export Results`;
- a left `Listbox` for input filenames, with selection assigning `session.selected_index`;
- central `ttk.Label` widgets for before and after previews, generated from the selected input and `session.preview()`;
- a right `Listbox` showing the recipe in reverse order, prefixed by its enabled state and operation name;
- right-side recipe controls: `+ Recolor`, `+ Layer`, `Up`, `Down`, `Enable/Disable`, and `Remove`;
- a recolor editor with source/target hex entries, `Add/Update Mapping`, `Remove Mapping`, and `Import From Reference`;
- a layer editor with `Choose Layer`, Above/Behind radio buttons, and a read-only dimensions summary.

`Import From Reference` asks for one matching reference PNG for the selected input, calls `suggest_mappings`, and places the returned mappings into the selected recolor operation. `Choose Layer` calls `layer_from_png`; it does not offer position or scale fields. Preview refreshes after every input selection or recipe mutation. Load Recipe parses before replacing `session.recipe`, so a parsing error leaves the existing work visible.

Use `Image.Resampling.NEAREST` only when reducing preview images, retain `ImageTk.PhotoImage` instances on the app object, and show user errors with `messagebox.showerror`.

- [ ] **Step 4: Run controller tests and manually smoke-test the window**

Run: `python -m pytest tests/test_session.py -v`

Expected: PASS.

Run: `python .\run_imageination.py`

Manual checks:

1. Add two PNGs and select each in the left list.
2. Add a recolor mapping and confirm after-preview changes without creating a file.
3. Import a same-size reference and edit one suggested mapping.
4. Add an above and a behind layer, reorder them, and confirm the preview order changes.
5. Load an invalid recipe and confirm the current recipe stack remains unchanged.
6. Export to a new folder with and without the JSON option; confirm sources remain unchanged.

- [ ] **Step 5: Commit the UI task**

```bash
git add imageination/app.py imageination/session.py tests/test_session.py
git commit -m "feat: build the image recipe workspace"
```

### Task 5: Update the user documentation and run the full verification suite

**Files:**

- Modify: `README.md`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_recipe.py`
- Modify: `tests/test_session.py`

**Consumes:** the completed application and all prior test fixtures.

**Produces:** accurate run instructions and an end-to-end regression test for portable recipe export/import.

- [ ] **Step 1: Write the end-to-end failing regression test**

```python
def test_exported_recipe_can_be_loaded_and_reproduce_output(tmp_path):
    source = tmp_path / "source.png"
    output_one = tmp_path / "one"
    output_two = tmp_path / "two"
    save_rgba(source, [(255, 0, 0, 255), (0, 0, 0, 0)], size=(2, 1))
    recipe = Recipe((
        RecolorOperation("Blue", {"#FF0000": "#0000FF"}),
        layer_operation("Ring", "above", [(0, 0, 0, 0), (0, 255, 0, 255)], (2, 1)),
    ))

    export_recipe([source], recipe, output_one, include_recipe=True, overwrite=False)
    reloaded = recipe_from_json((output_one / "imageination-recipe.json").read_text(encoding="utf-8"))
    export_recipe([source], reloaded, output_two, include_recipe=False, overwrite=False)

    assert (output_one / "source.png").read_bytes() == (output_two / "source.png").read_bytes()
```

- [ ] **Step 2: Run the focused regression test and verify its initial state**

Run: `python -m pytest tests/test_engine.py::test_exported_recipe_can_be_loaded_and_reproduce_output -v`

Expected: PASS after Tasks 1–4. If it fails, correct the smallest serialization or export defect before continuing.

- [ ] **Step 3: Replace README workflow and scope notes**

```markdown
## Workflow

1. Add PNG files or a folder of PNGs.
2. Add a recolor operation manually or generate mappings from a matching reference image.
3. Add same-size transparent layers above or behind the image.
4. Preview any input and reorder or disable operations as needed.
5. Export transformed copies to a separate folder. Optionally include a portable `imageination-recipe.json`.

Recipes contain operations only; Imageination does not save projects, input folders, or output folders.
```

Remove the old image-type, ImageMagick, cells, frames, raw manual-map, map-save/load, and future-layering language.

- [ ] **Step 4: Run complete verification**

Run: `python -m pytest tests -v`

Expected: PASS in the isolated worktree.

Run: `python -m compileall imageination`

Expected: every module compiles with no syntax errors.

- [ ] **Step 5: Commit documentation and final regression coverage**

```bash
git add README.md tests/test_engine.py tests/test_recipe.py tests/test_session.py
git commit -m "docs: document image recipe workflow"
```

## Plan Self-Review

### Spec coverage

| Spec requirement | Planned task |
| --- | --- |
| Stateless PNG input workflow and no automatic persistence | Tasks 3–4 |
| Manual and reference-derived recoloring | Tasks 2 and 4 |
| Exact-size above/behind layers | Task 2 and Task 4 |
| Self-contained versioned JSON recipes | Task 1 |
| Optional recipe beside export | Task 3 and Task 5 |
| Safe preflight, collisions, and source preservation | Task 3 |
| Focused three-area desktop UI | Task 4 |
| Unit, batch, controller, and manual verification | Tasks 1–5 |
| Deferred spritesheet and geometric features | Global constraints and Task 4 scope |

### Placeholder scan

The plan has no unresolved implementation markers, undefined implementation step, or unassigned validation requirement. Each public interface is defined before its first consuming task.

### Type consistency

`Recipe`, `RecolorOperation`, `LayerOperation`, `Operation`, `RecipeSession`, `PreflightIssue`, `apply_recipe`, `suggest_mappings`, `preflight`, and `export_recipe` use the same names and signatures across all tasks.
