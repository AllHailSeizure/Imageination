from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from imageination.engine import export_recipe, preflight, suggest_mappings
from imageination.recipe import LayerOperation, Recipe, RecolorOperation, layer_from_png, recipe_from_json
from imageination.session import RecipeSession


PNG_TYPES = [("PNG images", "*.png")]


class ImageinationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Imageination")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.session = RecipeSession()
        self.before_image: ImageTk.PhotoImage | None = None
        self.after_image: ImageTk.PhotoImage | None = None
        self.status_var = tk.StringVar(value="Add PNG images to begin.")
        self.direction_var = tk.StringVar(value="above")
        self._build_ui()

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for label, command in (("Add PNGs", self.add_files), ("Add Folder", self.add_folder), ("Load Recipe", self.load_recipe), ("Export Results", self.export_results)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 6))

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        inputs = ttk.Frame(body, padding=8)
        preview = ttk.Frame(body, padding=8)
        recipe = ttk.Frame(body, padding=8)
        body.add(inputs, weight=1)
        body.add(preview, weight=3)
        body.add(recipe, weight=1)
        self._build_inputs(inputs)
        self._build_preview(preview)
        self._build_recipe(recipe)
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8, 0, 8, 8)).pack(fill="x")

    def _build_inputs(self, parent):
        ttk.Label(parent, text="Input images").pack(anchor="w")
        self.input_list = tk.Listbox(parent, exportselection=False)
        self.input_list.pack(fill="both", expand=True, pady=(6, 0))
        self.input_list.bind("<<ListboxSelect>>", self.select_input)

    def _build_preview(self, parent):
        ttk.Label(parent, text="Preview").pack(anchor="w")
        frames = ttk.Frame(parent)
        frames.pack(fill="both", expand=True, pady=8)
        for label in ("Before", "After"):
            column = ttk.Frame(frames)
            column.pack(side="left", fill="both", expand=True, padx=5)
            ttk.Label(column, text=label).pack()
            image_label = ttk.Label(column, anchor="center")
            image_label.pack(fill="both", expand=True)
            if label == "Before":
                self.before_label = image_label
            else:
                self.after_label = image_label
        controls = ttk.Frame(parent)
        controls.pack()
        ttk.Button(controls, text="← Previous", command=lambda: self.change_input(-1)).pack(side="left", padx=3)
        ttk.Button(controls, text="Next →", command=lambda: self.change_input(1)).pack(side="left", padx=3)

    def _build_recipe(self, parent):
        ttk.Label(parent, text="Recipe · top applied last").pack(anchor="w")
        self.recipe_list = tk.Listbox(parent, exportselection=False)
        self.recipe_list.pack(fill="both", expand=True, pady=6)
        self.recipe_list.bind("<<ListboxSelect>>", self.select_operation)
        buttons = ttk.Frame(parent)
        buttons.pack(fill="x")
        for label, command in (("+ Recolor", self.add_recolor), ("+ Layer", self.add_layer), ("Up", lambda: self.move_operation(1)), ("Down", lambda: self.move_operation(-1)), ("Enable/Disable", self.toggle_operation), ("Remove", self.remove_operation)):
            ttk.Button(buttons, text=label, command=command).pack(fill="x", pady=1)
        self.editor = ttk.LabelFrame(parent, text="Selected operation", padding=8)
        self.editor.pack(fill="x", pady=(8, 0))

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Add PNG images", filetypes=PNG_TYPES)
        if paths:
            self.session.add_files(Path(path) for path in paths)
            self.refresh_inputs()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Add PNG images from folder")
        if folder:
            self.session.add_folder(Path(folder))
            self.refresh_inputs()

    def refresh_inputs(self):
        self.input_list.delete(0, tk.END)
        for path in self.session.inputs:
            self.input_list.insert(tk.END, path.name)
        if self.session.selected_index is not None:
            self.input_list.selection_set(self.session.selected_index)
        self.refresh_preview()

    def select_input(self, _event=None):
        selected = self.input_list.curselection()
        if selected:
            self.session.selected_index = selected[0]
            self.refresh_preview()

    def change_input(self, offset):
        if self.session.selected_index is None:
            return
        index = self.session.selected_index + offset
        if 0 <= index < len(self.session.inputs):
            self.session.selected_index = index
            self.input_list.selection_clear(0, tk.END)
            self.input_list.selection_set(index)
            self.refresh_preview()

    def refresh_preview(self):
        if self.session.selected_index is None:
            return
        source_path = self.session.inputs[self.session.selected_index]
        try:
            with Image.open(source_path) as source:
                before = source.convert("RGBA")
            after = self.session.preview()
            self.before_image = self.to_photo(before)
            self.after_image = self.to_photo(after)
            self.before_label.configure(image=self.before_image)
            self.after_label.configure(image=self.after_image)
            self.status_var.set(f"Previewing {source_path.name}")
        except (OSError, ValueError) as exc:
            self.status_var.set(str(exc))

    @staticmethod
    def to_photo(image):
        preview = image.copy()
        preview.thumbnail((340, 340), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(preview)

    def add_recolor(self):
        self.session.recipe = Recipe((*self.session.recipe.operations, RecolorOperation("Recolor", {})))
        self.refresh_recipe(select_bottom=True)

    def add_layer(self):
        path = filedialog.askopenfilename(title="Choose same-size PNG layer", filetypes=PNG_TYPES)
        if not path:
            return
        try:
            operation = layer_from_png(path, name=Path(path).stem, direction=self.direction_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid layer", str(exc))
            return
        self.session.recipe = Recipe((*self.session.recipe.operations, operation))
        self.refresh_recipe(select_bottom=True)

    def refresh_recipe(self, select_bottom=False):
        self.recipe_list.delete(0, tk.END)
        for operation in reversed(self.session.recipe.operations):
            state = "✓" if operation.enabled else "○"
            self.recipe_list.insert(tk.END, f"{state} {operation.name}")
        if self.session.recipe.operations:
            selected = len(self.session.recipe.operations) - 1 if select_bottom else 0
            self.recipe_list.selection_set(selected)
        self.select_operation()
        self.refresh_preview()

    def selected_operation_index(self):
        selected = self.recipe_list.curselection()
        return len(self.session.recipe.operations) - 1 - selected[0] if selected else None

    def select_operation(self, _event=None):
        for child in self.editor.winfo_children():
            child.destroy()
        index = self.selected_operation_index()
        if index is None:
            return
        operation = self.session.recipe.operations[index]
        if isinstance(operation, RecolorOperation):
            self.show_recolor_editor(index, operation)
        else:
            ttk.Label(self.editor, text=f"{operation.direction.title()} layer · {operation.width}×{operation.height}px").pack(anchor="w")
            ttk.Radiobutton(self.editor, text="Above", variable=self.direction_var, value="above", command=lambda: self.set_layer_direction(index, "above")).pack(anchor="w")
            ttk.Radiobutton(self.editor, text="Behind", variable=self.direction_var, value="behind", command=lambda: self.set_layer_direction(index, "behind")).pack(anchor="w")
            self.direction_var.set(operation.direction)

    def show_recolor_editor(self, index, operation):
        source = ttk.Entry(self.editor)
        target = ttk.Entry(self.editor)
        source.pack(fill="x", pady=2)
        target.pack(fill="x", pady=2)
        mapping_list = tk.Listbox(self.editor, height=5)
        mapping_list.pack(fill="x", pady=3)
        for old, new in sorted(operation.mappings.items()):
            mapping_list.insert(tk.END, f"{old} → {new}")
        def update_mapping():
            try:
                mappings = dict(operation.mappings)
                mappings[source.get()] = target.get()
                self.session.replace_operation(index, RecolorOperation(operation.name, mappings, operation.enabled))
                self.refresh_recipe()
            except ValueError as exc:
                messagebox.showerror("Invalid color", str(exc))
        ttk.Button(self.editor, text="Add / Update mapping", command=update_mapping).pack(fill="x", pady=2)
        ttk.Button(self.editor, text="Import from reference", command=lambda: self.import_reference(index, operation)).pack(fill="x", pady=2)

    def import_reference(self, index, operation):
        if self.session.selected_index is None:
            messagebox.showinfo("Input needed", "Select an input image first.")
            return
        path = filedialog.askopenfilename(title="Choose matching reference PNG", filetypes=PNG_TYPES)
        if not path:
            return
        try:
            with Image.open(self.session.inputs[self.session.selected_index]) as source, Image.open(path) as reference:
                mappings = suggest_mappings(source, reference)
            self.session.replace_operation(index, RecolorOperation(operation.name, mappings, operation.enabled))
            self.refresh_recipe()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Reference comparison failed", str(exc))

    def set_layer_direction(self, index, direction):
        operation = self.session.recipe.operations[index]
        self.session.replace_operation(index, replace(operation, direction=direction))
        self.refresh_recipe()

    def move_operation(self, offset):
        index = self.selected_operation_index()
        if index is not None:
            self.session.move_operation(index, offset)
            self.refresh_recipe()

    def toggle_operation(self):
        index = self.selected_operation_index()
        if index is not None:
            operation = self.session.recipe.operations[index]
            self.session.replace_operation(index, replace(operation, enabled=not operation.enabled))
            self.refresh_recipe()

    def remove_operation(self):
        index = self.selected_operation_index()
        if index is not None:
            operations = list(self.session.recipe.operations)
            operations.pop(index)
            self.session.recipe = Recipe(tuple(operations))
            self.refresh_recipe()

    def load_recipe(self):
        path = filedialog.askopenfilename(title="Load recipe", filetypes=[("Imageination recipe", "*.json")])
        if not path:
            return
        try:
            self.session.replace_recipe(recipe_from_json(Path(path).read_text(encoding="utf-8")))
            self.refresh_recipe()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not load recipe", str(exc))

    def export_results(self):
        if not self.session.inputs:
            messagebox.showinfo("Inputs needed", "Add one or more PNG images first.")
            return
        folder = filedialog.askdirectory(title="Choose export folder")
        if not folder:
            return
        output = Path(folder)
        overwrite = False
        issues = preflight(self.session.inputs, self.session.recipe, output)
        if any(issue.message.startswith("Output already exists") for issue in issues):
            overwrite = messagebox.askyesno("Existing outputs", "Some output names already exist. Overwrite them?")
            issues = preflight(self.session.inputs, self.session.recipe, output, overwrite=overwrite)
        if issues:
            messagebox.showerror("Export blocked", "\n".join(issue.message for issue in issues))
            return
        try:
            outputs = export_recipe(self.session.inputs, self.session.recipe, output, include_recipe=messagebox.askyesno("Include recipe", "Include imageination-recipe.json?"), overwrite=overwrite)
            self.status_var.set(f"Exported {len(outputs)} PNG image(s) to {output}")
        except ValueError as exc:
            messagebox.showerror("Export failed", str(exc))


def main():
    ImageinationApp().mainloop()


if __name__ == "__main__":
    main()
